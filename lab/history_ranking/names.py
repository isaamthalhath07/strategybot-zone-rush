"""Readable name + family for every candidate, from git paths, commit history and the repo's own registries."""
import json, os, re
SP = os.path.dirname(os.path.abspath(__file__))
CANDS = json.load(open(SP + "/cands.json"))["cands"]
L = json.load(open(SP + "/labels.json"))
REG, ROOT, HEADS = L["reg"], L["rootbots"], L["heads"]
TESTER = {"fe03b8164ed3": "Transfer (previous release)", "5457b5fdf4ca": "Transfer (original)", "720e5a3daf7b": "Fusion (fused economic planner)",
          "641c909b7ef1": "Apex (counter-player)", "a35c2c481164": "Racer (novel-b)", "1bb70109a75e": "Blocker (novel-b)",
          "6f2ac1487cd0": "Guarded research alternative", "a8f7a74e7ed3": "UltimateBot", "f95dc9fc2266": "Feint (novel-b)",
          "e8b3682d8b39": "CURRENT main bot.py (guarded Transfer, STAY-only)", "5f1bb9f70aac": "Zenith", "50d82d7ac581": "Defense-tuned Transfer (50d, evolved from main bot)",
          "191059b37141": "Evolved league genome 191059 (Blocker-core)", "92f38af1a559": "Evolved league genome 92f38a"}
CLONES = json.load(open(SP + "/clones.json")) if os.path.exists(SP + "/clones.json") else {}
for _c, _v in CLONES.items():
    if _v["seeded"] and not _v["other_changed"]:
        TESTER[_c] = "%s seed-only clone (seat %s reseeded)" % (_v["cls"].replace("Bot", ""), _v["seeded"][0][0])
TESTER["f5e870cd8bb5"] = "Blocker + public-memory patch (strategy_candidates/)"
TESTER["8e84ff655452"] = "main-bot CONFIG variant fa9d68 (evolution league)"
TESTER["def6a8585f26"] = "main-bot CONFIG variant mutation_01 (evolution league)"
TESTER["4737b8184da3"] = "main-bot CONFIG variant mutation_03 (evolution league)"
TESTER["18c0316f3250"] = "hx_steady persona (zenith/lab/humanlike)"
TESTER["d75575389253"] = "novel_d_shieldmaster (PR10 novel-d)"
def policy(cid):
    v = CLONES.get(cid)
    if v and not v["other_changed"]: return v["cls"].replace("Bot", "")
    return None
def reg_names(cid):
    out = []
    for r in REG.get(cid, []):
        n = r.get("name") or r.get("label")
        if n and n not in out and not re.fullmatch(r"(bot_)?[0-9a-f]{12}", n): out.append(n)
    return out
def family(cid):
    c = CANDS[cid]; gp = c["git_paths"]
    fams = [r.get("family") for r in REG.get(cid, []) if r.get("family")]
    names = reg_names(cid)
    if any(p.startswith("opponents/") for p in gp): return "opponent-field"
    if any(p.startswith("harness/bots/") for p in gp): return "starter/skeleton"
    if fams: return fams[0]
    if any(n.startswith("novel_") for n in names): return "novel-opponent"
    zp = " ".join(c["zip_paths"])
    if "offspring" in zp or "elite" in " ".join(names) or "train_0" in zp: return "evolved-genome"
    if ".cache/evolution" in json.dumps(REG.get(cid, [])): return "evolved-genome"
    if gp: return "own-lineage"
    return "archived-variant"
def name(cid):
    c = CANDS[cid]; gp = c["git_paths"]
    if cid in TESTER: base = TESTER[cid]
    else:
        names = reg_names(cid)
        if cid in ROOT and ROOT[cid][0]["path"] == "bot.py": base = "root bot.py"
        elif cid in ROOT: base = "root mybot.py (dev source)"
        elif gp: base = sorted(gp, key=len)[0]
        elif names: base = names[0]
        else: base = c["zip_paths"][0].split("!")[-1].split("/")[-1]
        if names and names[0] not in base and not gp: pass
        elif names and gp and names[0] not in base: base += " [%s]" % names[0]
    return base
def where(cid):
    c = CANDS[cid]
    bits = []
    if cid in ROOT:
        r = ROOT[cid]
        bits.append("%s @ %s (%s)%s" % (r[0]["path"], r[0]["commit"], r[0]["date"][:10], " … %d commits" % len(r) if len(r) > 1 else ""))
    heads = [b for b, h in HEADS.items() if h["bot_sha"] == cid]
    if heads: bits.append("root bot.py at head of: " + ", ".join(sorted(heads)))
    if c["git_paths"] and cid not in ROOT: bits.append("%s @ %s" % (", ".join(sorted(c["git_paths"])[:3]), c["first_commit"]))
    if not c["git_paths"]: bits.append("archive: " + c["zip_paths"][0].split("!")[0].split("/")[-2] + "/…/" + c["zip_paths"][0].split("!")[-1].split("/")[-1][:24])
    return "; ".join(bits)
if __name__ == "__main__":
    import collections
    print(collections.Counter(family(c) for c in CANDS))
    for cid in ["e8b3682d8b39", "1bb70109a75e", "191059b37141", "50d82d7ac581", "31965e1412c6", "ef5d88a22a3d", "0b826e99381a"]:
        print(cid, "|", name(cid), "|", family(cid), "|", where(cid))
