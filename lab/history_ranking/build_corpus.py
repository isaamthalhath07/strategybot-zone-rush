"""Build the full corpus of distinct bot sources: every .py blob in every commit of every ref,
plus every .py member of every zip blob in history (read in memory, recursing into nested zips).
Dedupe by sha256 of content. Keep files with a top-level `def act(`."""
import subprocess, re, json, os, sys, collections, hashlib, io, zipfile
REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SP = os.path.dirname(os.path.abspath(__file__))
CORPUS = os.path.join(SP, "corpus")
os.makedirs(CORPUS, exist_ok=True)
def git(*a):
    return subprocess.run(["git", "-C", REPO, *a], capture_output=True, check=True).stdout
meta = {}
for line in git("log", "--all", "--pretty=format:%H|%ad|%an|%s", "--date=iso-strict").decode().splitlines():
    h, d, an, s = line.split("|", 3)
    meta[h] = dict(date=d, author=an, subject=s)
commits = sorted(meta, key=lambda h: meta[h]["date"])
refs = {}
for line in git("for-each-ref", "--format=%(refname:short) %(objectname)", "refs/remotes/origin").decode().splitlines():
    name, h = line.split()
    if name.endswith("/HEAD") or name == "origin": continue
    refs[name.replace("origin/", "")] = h
# which refs contain each commit
ref_commits = {r: set(git("rev-list", h).decode().split()) for r, h in refs.items()}
ACT = re.compile(rb"^def act\s*\(", re.M)
entries = {}   # sha256 -> record
blob_seen = {}
def add(data, origin_kind, path, commit, container=None):
    if not ACT.search(data): return
    sha = hashlib.sha256(data).hexdigest()
    e = entries.setdefault(sha, dict(sha256=sha, size=len(data), git_paths=[], zip_paths=[], commits=[], first_commit=None))
    if origin_kind == "git":
        if path not in e["git_paths"]: e["git_paths"].append(path)
    else:
        tag = "%s!%s" % (container, path)
        if tag not in e["zip_paths"]: e["zip_paths"].append(tag)
    if commit not in e["commits"]: e["commits"].append(commit)
    out = os.path.join(CORPUS, sha[:12] + ".py")
    if not os.path.exists(out):
        with open(out, "wb") as f: f.write(data)
def walk_zip(data, container, commit, depth=0):
    try:
        z = zipfile.ZipFile(io.BytesIO(data))
    except Exception as ex:
        print("bad zip", container, ex, file=sys.stderr); return
    for info in z.infolist():
        if info.is_dir(): continue
        if info.file_size > 50_000_000: continue
        name = info.filename
        low = name.lower()
        if low.endswith(".py"):
            add(z.read(info), "zip", name, commit, container)
        elif low.endswith(".zip") and depth < 3:
            walk_zip(z.read(info), container + "!" + name, commit, depth + 1)
zip_done = set()
for c in commits:
    for line in git("ls-tree", "-r", c).decode().splitlines():
        info, path = line.split("\t", 1)
        mode, typ, bsha = info.split()
        if typ != "blob": continue
        if path.endswith(".py"):
            key = (bsha, path)
            if key in blob_seen:
                sha = blob_seen[key]
                if sha and c not in entries[sha]["commits"]: entries[sha]["commits"].append(c)
                continue
            data = git("cat-file", "blob", bsha)
            if ACT.search(data):
                add(data, "git", path, c)
                blob_seen[key] = hashlib.sha256(data).hexdigest()
            else:
                blob_seen[key] = None
        elif path.endswith(".zip"):
            if bsha in zip_done: continue
            zip_done.add(bsha)
            walk_zip(git("cat-file", "blob", bsha), path, c)
for e in entries.values():
    cs = sorted(e["commits"], key=lambda h: meta[h]["date"])
    e["first_commit"] = cs[0]; e["first_date"] = meta[cs[0]]["date"]; e["first_subject"] = meta[cs[0]]["subject"]
    e["last_commit"] = cs[-1]; e["last_date"] = meta[cs[-1]]["date"]
    e["n_commits"] = len(cs)
    e["branches"] = sorted(r for r, s in ref_commits.items() if any(c in s for c in cs))
    e["at_head_of"] = sorted(r for r, h in refs.items() if h in cs)
    del e["commits"]
json.dump(dict(entries=entries, meta=meta, refs=refs), open(os.path.join(SP, "corpus.json"), "w"), indent=1)
print("distinct act() sources:", len(entries))
print("  from git paths:", sum(1 for e in entries.values() if e["git_paths"]))
print("  zip-only:", sum(1 for e in entries.values() if not e["git_paths"]))
