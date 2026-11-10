import json, os, hashlib
SP = os.path.dirname(os.path.abspath(__file__))
d = json.load(open(SP + "/corpus.json")); E = d["entries"]
static = json.load(open(SP + "/static.json"))
SKIP = {"2545fbad3107": "test file (act only inside a template string)", "54cc8d865d28": "build script", "7e4460d2078d": "build script",
        "a2562aacdce4": "test file", "bb0689234122": "bot checker script",
        "60cafda89559": "multi-module source of zenith_bot.py (built file ranked instead)",
        "ecbd91fb257e": "multi-module source of apex_bot.py (built file ranked instead)",
        "d33365fb6bfb": "persona core, ranked through hx_* personas"}
cands = {}
for sha, e in E.items():
    s = sha[:12]
    if s in SKIP: continue
    if s in ("437cf7ee6631", "66ed85892834"): continue   # fusion.py source, handled below with siblings
    cands[s] = dict(id=s, sha256=sha, path=SP + "/corpus/" + s + ".py", size=e["size"], git_paths=e["git_paths"],
                    zip_paths=e["zip_paths"][:3], n_zip=len(e["zip_paths"]), first_commit=e["first_commit"][:7], first_date=e["first_date"],
                    last_date=e["last_date"], branches=e["branches"], at_head_of=e["at_head_of"], imports=static[s]["imports"])
for c, s in (("d31fff2", "66ed85892834"), ("ed708f3", "437cf7ee6631")):
    e = E[[k for k in E if k.startswith(s)][0]]
    cands[s] = dict(id=s, sha256=e["sha256"], path=SP + "/multi/fusion_src_%s/fusion.py" % c, size=e["size"], git_paths=e["git_paths"], zip_paths=[], n_zip=0,
                    first_commit=e["first_commit"][:7], first_date=e["first_date"], last_date=e["last_date"], branches=e["branches"], at_head_of=e["at_head_of"],
                    imports=static[s]["imports"], note="multi-file source (needs econ.py + mybot.py of the same commit)")
hx = SP + "/multi/zenith_tree/zenith/lab/humanlike"
for fn in sorted(os.listdir(hx)):
    if not fn.startswith("hx_"): continue
    sha = hashlib.sha256(open(os.path.join(hx, fn), "rb").read()).hexdigest()
    cands[sha[:12]] = dict(id=sha[:12], sha256=sha, path=os.path.join(hx, fn), size=os.path.getsize(os.path.join(hx, fn)), git_paths=["zenith/lab/humanlike/" + fn],
                           zip_paths=[], n_zip=0, first_commit="c3dfbfd", first_date=d["meta"][[k for k in d["meta"] if k.startswith("c3dfbfd")][0]]["date"],
                           last_date="", branches=["claude/amazing-fermat-yiicr8"], at_head_of=["claude/amazing-fermat-yiicr8"], imports=["os", "random"],
                           note="persona wrapper around _hxcore.py + apex/src/evosim.py")
json.dump(dict(cands=cands, skipped=SKIP), open(SP + "/cands.json", "w"), indent=1)
print(len(cands), "candidates")
