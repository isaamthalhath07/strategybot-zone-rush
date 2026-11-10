"""Head-to-head table: how often does the focal bot outscore each opponent it meets?
  python3 lab/h2h.py focal [--field DEV_ALL] [--maps 150] [--seed 7]
"""
import sys, os, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import arena, fields

def run(focals, field, maps=150, seed=7):
    fx = arena.fixtures(field, maps=maps, seed=seed)
    tasks = []
    for fi, f in enumerate(fx):
        for c in focals:
            names = list(f["opponents"]); names.insert(f["seat"], c)
            tasks.append(dict(names=names, family=f["family"], mapseed=f["mapseed"], token=f["token"], seed=f["seed"],
                              cand=c, seat=f["seat"]))
    res = arena.run_tasks(tasks)
    agg = {c: collections.defaultdict(lambda: [0, 0.0, 0.0]) for c in focals}
    tot = {c: [0, 0.0] for c in focals}
    for r in res:
        if "error" in r: continue
        t = r["task"]; s = r["scores"]; i = t["seat"]
        tot[t["cand"]][0] += 1; tot[t["cand"]][1] += r["pw"][i]
        for j, name in enumerate(t["names"]):
            if j == i: continue
            a = agg[t["cand"]][name]
            a[0] += 1; a[1] += 1.0 if s[i] > s[j] else 0.5 if s[i] == s[j] else 0.0; a[2] += s[i] - s[j]
    return agg, tot

if __name__ == "__main__":
    args = sys.argv[1:]
    opt = {"--field": "DEV_ALL", "--maps": "150", "--seed": "7"}
    for k in list(opt):
        if k in args:
            i = args.index(k); opt[k] = args[i + 1]; del args[i:i + 2]
    field = []
    for part in opt["--field"].split("+"):
        field += getattr(fields, part)
    agg, tot = run(args, field, int(opt["--maps"]), int(opt["--seed"]))
    names = sorted(set(n for c in args for n in agg[c]), key=lambda n: sum(agg[c][n][1] / max(1, agg[c][n][0]) for c in args))
    print("%-36s" % "opponent" + "".join("%-22s" % c[-20:] for c in args))
    for n in names:
        row = "%-36s" % n[:35]
        for c in args:
            a = agg[c][n]
            row += "%.2f (%+5.0f) n=%-5d " % (a[1] / max(1, a[0]), a[2] / max(1, a[0]), a[0])
        print(row)
    print("%-36s" % "TOTAL PW" + "".join("%-22s" % ("%.3f n=%d" % (tot[c][1] / max(1, tot[c][0]), tot[c][0])) for c in args))
