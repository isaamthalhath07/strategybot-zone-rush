"""Collect human-readable provenance for every candidate: registry names, families, aliases, root bot.py per commit/branch."""
import json, os, subprocess, hashlib, collections, gzip
REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SP = os.path.dirname(os.path.abspath(__file__))
def git(*a): return subprocess.run(["git", "-C", REPO, *a], capture_output=True, check=True).stdout
cands = json.load(open(SP + "/cands.json"))["cands"]
full = {c["sha256"]: k for k, c in cands.items()}
reg = collections.defaultdict(list)
def walk(x, src):
    if isinstance(x, dict):
        s = x.get("sha256")
        if isinstance(s, str) and s in full:
            info = {k: x[k] for k in ("name", "label", "role", "family", "path", "style", "kind", "description", "design", "parent_sha256", "genome", "source_commit", "commit", "ref") if k in x and isinstance(x[k], (str, int, float))}
            al = x.get("aliases")
            if isinstance(al, list): info["aliases"] = [a for a in al if isinstance(a, dict)][:6]
            if isinstance(x.get("source"), dict): info["source"] = {k: v for k, v in x["source"].items() if isinstance(v, (str, int, float))}
            info["_from"] = src
            reg[full[s]].append(info)
        for v in x.values(): walk(v, src)
    elif isinstance(x, list):
        for v in x: walk(v, src)
n = 0
for root, dirs, files in os.walk(REPO):
    if ".git" in root: continue
    for fn in files:
        if not fn.endswith(".json"): continue
        p = os.path.join(root, fn)
        if os.path.getsize(p) > 40_000_000: continue
        try: data = json.load(open(p, encoding="utf8"))
        except Exception: continue
        n += 1; walk(data, os.path.relpath(p, REPO))
print("json files scanned", n, "candidates with registry info", len(reg))
# root bot.py / mybot.py at every commit, and at every branch head
meta = {}
for line in git("log", "--all", "--pretty=format:%H|%ad|%an|%s", "--date=iso-strict").decode().splitlines():
    h, d, an, s = line.split("|", 3); meta[h] = dict(date=d, author=an, subject=s)
rootbots = collections.defaultdict(list)
for h in sorted(meta, key=lambda h: meta[h]["date"]):
    for path in ("bot.py", "mybot.py"):
        r = subprocess.run(["git", "-C", REPO, "show", "%s:%s" % (h, path)], capture_output=True)
        if r.returncode == 0:
            sha = hashlib.sha256(r.stdout).hexdigest()[:12]
            rootbots[sha].append(dict(commit=h[:7], date=meta[h]["date"][:16], path=path, subject=meta[h]["subject"], author=meta[h]["author"]))
heads = {}
for line in git("for-each-ref", "--format=%(refname:short) %(objectname)", "refs/remotes/origin").decode().splitlines():
    name, h = line.split()
    if name in ("origin/HEAD", "origin"): continue
    r = subprocess.run(["git", "-C", REPO, "show", "%s:bot.py" % h], capture_output=True)
    heads[name.replace("origin/", "")] = dict(commit=h[:7], date=meta[h]["date"][:16], subject=meta[h]["subject"], bot_sha=hashlib.sha256(r.stdout).hexdigest()[:12] if r.returncode == 0 else None)
json.dump(dict(reg=reg, rootbots=rootbots, heads=heads), open(SP + "/labels.json", "w"), indent=1)
for b, v in sorted(heads.items(), key=lambda kv: kv[1]["date"]): print(b, v["commit"], v["date"], v["bot_sha"], "|", v["subject"][:70])
print()
for sha, v in sorted(rootbots.items(), key=lambda kv: kv[1][0]["date"]):
    print(sha, v[0]["path"], "first", v[0]["commit"], v[0]["date"], "commits=%d" % len(v), "|", v[0]["subject"][:80])
