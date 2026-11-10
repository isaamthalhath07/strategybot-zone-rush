"""One-off preparation between build_corpus.py and make_cands.py.

1. static.json: imports, sensitive call sites and the act() signature of every source.
2. multi/: the bots that need sibling files from their own commit (two fusion.py
   sources, and the six human-like personas that exec _hxcore.py and apex/src/evosim.py).
"""
import ast, json, os, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
CORPUS = os.path.join(HERE, "corpus")
WATCH = ("open", "exec", "eval", "compile", "__import__", "system", "popen", "Popen", "urlopen", "socket",
         "remove", "unlink", "rmtree", "mkdir", "makedirs", "write_text", "write_bytes", "dump", "load", "getenv")
info = {}
for fn in sorted(os.listdir(CORPUS)):
    tree = ast.parse(open(os.path.join(CORPUS, fn), "rb").read())
    mods, calls, args, top = set(), set(), None, False
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            mods.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            mods.add((node.module or ".").split(".")[0] if node.level == 0 else "." + (node.module or ""))
        elif isinstance(node, ast.Call):
            f = node.func
            name = f.id if isinstance(f, ast.Name) else (f.attr if isinstance(f, ast.Attribute) else None)
            if name in WATCH:
                calls.add(name)
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == "act":
            top, args = True, [a.arg for a in node.args.args]
    info[fn[:12]] = dict(imports=sorted(mods), calls=sorted(calls), act_args=args, real_toplevel_act=top)
json.dump(info, open(os.path.join(HERE, "static.json"), "w"))


def show(commit, path, dest):
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    data = subprocess.run(["git", "-C", REPO, "show", "%s:%s" % (commit, path)], capture_output=True, check=True).stdout
    open(dest, "wb").write(data)


for commit in ("d31fff2", "ed708f3"):
    for f in ("fusion.py", "econ.py", "mybot.py"):
        show(commit, f, os.path.join(HERE, "multi", "fusion_src_" + commit, f))
tree = os.path.join(HERE, "multi", "zenith_tree")
listing = subprocess.run(["git", "-C", REPO, "ls-tree", "-r", "--name-only", "a5b462f", "zenith/lab/humanlike/"],
                         capture_output=True, check=True, text=True).stdout.split()
for f in listing:
    show("a5b462f", f, os.path.join(tree, f))
show("a5b462f", "apex/src/evosim.py", os.path.join(tree, "apex", "src", "evosim.py"))
print("static.json: %d sources; multi/ ready" % len(info))
