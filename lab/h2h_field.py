"""Head-to-head by opponent on one suite2 field.
  python3 lab/h2h_field.py weak|mid|strong focal1 focal2 ... [--maps 100] [--seed 17]
"""
import sys, os, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import arena, suite2

if __name__ == "__main__":
    args = sys.argv[1:]
    opt = {"--maps": "100", "--seed": "17"}
    for k in list(opt):
        if k in args:
            i = args.index(k); opt[k] = args[i + 1]; del args[i:i + 2]
    field = suite2.groups()[args[0]]; cands = args[1:]
    fx = arena.fixtures(field, maps=int(opt["--maps"]), seed=int(opt["--seed"]), families=suite2.FAMS)
    tasks = []
    for f in fx:
        for c in cands:
            names = list(f["opponents"]); names.insert(f["seat"], c)
            tasks.append(dict(names=names, family=f["family"], mapseed=f["mapseed"], token=f["token"], seed=f["seed"],
                              cand=c, seat=f["seat"]))
    res = arena.run_tasks(tasks)
    agg = {c: collections.defaultdict(lambda: [0, 0.0, 0.0]) for c in cands}
    tot = {c: [0, 0.0, 0.0] for c in cands}
    for r in res:
        if "error" in r: continue
        t = r["task"]; s = r["scores"]; i = t["seat"]
        tot[t["cand"]][0] += 1; tot[t["cand"]][1] += r["pw"][i]; tot[t["cand"]][2] += s[i]
        for j, name in enumerate(t["names"]):
            if j == i: continue
            a = agg[t["cand"]][name]
            a[0] += 1; a[1] += 1.0 if s[i] > s[j] else 0.5 if s[i] == s[j] else 0.0; a[2] += s[i] - s[j]
    names = sorted(set(n for c in cands for n in agg[c]), key=lambda n: agg[cands[0]][n][1] / max(1, agg[cands[0]][n][0]))
    print("%-30s" % "opponent" + "".join("%-22s" % c[-20:] for c in cands))
    for n in names:
        row = "%-30s" % n[:29]
        for c in cands:
            a = agg[c][n]
            row += "%.2f (%+5.0f) n=%-5d " % (a[1] / max(1, a[0]), a[2] / max(1, a[0]), a[0])
        print(row)
    print("%-30s" % "TOTAL PW (score)" + "".join("%-22s" % ("%.3f (%.0f) n=%d" % (tot[c][1] / max(1, tot[c][0]), tot[c][2] / max(1, tot[c][0]), tot[c][0])) for c in cands))
