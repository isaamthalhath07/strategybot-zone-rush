"""Inventory unique committed/exported policies without changing any branch.

The source corpus is immutable and deduplicated by exact bytes. Research
modules requiring project imports are reported, not mislabeled submissions.
"""
import argparse
import ast
import hashlib
import json
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/"validation/branch_audit"
CORPUS = ROOT/"consolidation_candidates/branch_audit"


def git(*args):
    result = subprocess.run(["git",*args],cwd=ROOT,capture_output=True,check=True)
    return result.stdout


def tree(commit):
    rows = []
    for part in git("ls-tree","-r","-z",commit).split(b"\0"):
        if not part:
            continue
        info,path = part.split(b"\t",1)
        mode,kind,blob = info.decode().split()
        if kind == "blob" and path.endswith(b".py"):
            rows.append((blob,path.decode("utf8")))
    return rows


def blobs(names):
    names = sorted(set(names))
    result = subprocess.run(["git","cat-file","--batch"],cwd=ROOT,
                            input=("\n".join(names)+"\n").encode(),capture_output=True,check=True)
    data,position,out = result.stdout,0,{}
    for name in names:
        end = data.index(b"\n",position)
        sha,kind,size = data[position:end].decode().split()
        size = int(size)
        if sha != name or kind != "blob":
            raise ValueError("unexpected object")
        position = end+1
        out[name] = data[position:position+size]
        position += size+1
    return out


def inspect(body):
    try:
        module = ast.parse(body)
    except (SyntaxError,ValueError,UnicodeError) as e:
        return dict(parses=False,error=str(e),entry=False,eligible=False)
    imports = set()
    relative = False
    calls = set()
    for node in ast.walk(module):
        if isinstance(node,ast.Import):
            imports.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node,ast.ImportFrom):
            relative |= bool(node.level)
            if node.module:
                imports.add(node.module.split(".")[0])
        elif isinstance(node,ast.Call) and isinstance(node.func,ast.Name):
            if node.func.id in ("open","input","exec","eval","compile","__import__"):
                calls.add(node.func.id)
    entry = any(isinstance(n,ast.FunctionDef) and n.name=="act" for n in module.body)
    classes = [n.name for n in module.body if isinstance(n,ast.ClassDef) and
               any(isinstance(m,ast.FunctionDef) and m.name in ("act","__call__") for m in n.body)]
    external = sorted(imports-set(sys.stdlib_module_names))
    return dict(parses=True,entry=entry,classes=classes,imports=sorted(imports),
                external=external,sensitive_calls=sorted(calls),
                eligible=entry and not relative and not external and not calls)


def inventory():
    if (OUT/"inventory.json").exists():
        raise ValueError("preserve the frozen inventory; create a new campaign")
    refs = []
    for line in git("for-each-ref","--format=%(refname)\t%(objectname)","refs/heads","refs/remotes").decode().splitlines():
        ref,commit = line.split("\t")
        if ref.endswith("/HEAD"):
            continue
        refs.append(dict(ref=ref,commit=commit))
    trees = {commit:tree(commit) for commit in {r["commit"] for r in refs}}
    bodies = blobs(blob for rows in trees.values() for blob,path in rows)
    policies,python_sources = {},{}

    def add(body,alias,registered=None):
        digest = hashlib.sha256(body).hexdigest()
        info = inspect(body)
        python_sources.setdefault(digest,dict(sha256=digest,bytes=len(body),audit=info,aliases=[]))["aliases"].append(alias)
        if not info["eligible"]:
            return
        if digest not in policies:
            target = CORPUS/(digest+".py")
            target.parent.mkdir(parents=True,exist_ok=True)
            target.write_bytes(body)
            policies[digest] = dict(name="bot_"+digest[:12],sha256=digest,
                                  path=str(target.relative_to(ROOT)).replace("\\","/"),
                                  bytes=len(body),audit=info,aliases=[],registered_names=[])
        item = policies[digest]
        if alias not in item["aliases"]:
            item["aliases"].append(alias)
        if registered and registered not in item["registered_names"]:
            item["registered_names"].append(registered)

    for row in refs:
        for blob,path in trees[row["commit"]]:
            add(bodies[blob],dict(ref=row["ref"],commit=row["commit"],path=path))
    # Earlier class-wrapper builds and historical frozen genomes are sources,
    # not scalar scores to pool with this new comparison.
    for registry_path in (ROOT/"validation/source_registry.json",ROOT/"validation/official/source_registry.json"):
        if not registry_path.exists():
            continue
        data = json.loads(registry_path.read_text())
        entries = data["sources"] if isinstance(data,dict) else data
        for item in entries:
            path = ROOT/item["path"]
            if not path.exists():
                continue
            body = path.read_bytes()
            if hashlib.sha256(body).hexdigest() != item["sha256"]:
                raise ValueError("restored source mismatch")
            add(body,dict(archive=str(registry_path.relative_to(ROOT)),path=item["path"],
                          original_aliases=item.get("aliases",[])),item["name"])
    worktree_names = []
    for line in git("worktree","list","--porcelain").decode().splitlines():
        if not line.startswith("worktree "):
            continue
        folder = Path(line[9:])
        path = folder/"bot.py"
        if path.exists():
            # Labels disclose no absolute local directory in published evidence.
            add(path.read_bytes(),dict(worktree=folder.name,path="bot.py",mutable_source_frozen_at_inventory=True))
            worktree_names.append(folder.name)
    manifest = dict(base_commit=git("rev-parse","HEAD").decode().strip(),refs=refs,
                    remote_branch_count=sum(r["ref"].startswith("refs/remotes/origin/") for r in refs),
                    worktrees_sampled=worktree_names,unique_python_sources=len(python_sources),
                    policies=sorted(policies.values(),key=lambda p:p["name"]),
                    source_inventory=list(python_sources.values()),
                    scope="All local/remote branch tips and known archived class/genome exports; exact-byte deduplication. Working exports are frozen separately. Class-only/non-standalone development modules remain listed with their import requirements, not falsely admitted as single-file submissions.")
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/"inventory.json").write_text(json.dumps(manifest,indent=2),encoding="utf8",newline="\n")
    print(json.dumps(dict(refs=len(refs),remote_branches=manifest["remote_branch_count"],
                         unique_python_sources=len(python_sources),eligible_policies=len(policies),
                         syntax_failures=sum(not p["audit"]["parses"] for p in python_sources.values())),indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command",choices=("inventory",))
    args = parser.parse_args()
    inventory()


if __name__=="__main__":
    main()
