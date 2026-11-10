"""Head-to-head against the strong opponents that are no longer held out (EXT1 strong
designs + the lab hold-out elite + development elite), on all 13 map families.
  python3 lab/h2h_strong.py focal1 focal2 ... [--maps 120] [--seed 11]
"""
import sys, os, json, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import arena, fields, sim, h2h

HERE = os.path.dirname(os.path.abspath(__file__))


def ext1_strong():
    split = json.load(open(os.path.join(HERE, "ext", "split.json")))
    index = json.load(open(os.path.join(HERE, "ext", "index.json")))
    return [n for n in split["EXT1"] if index[n]["group"] in ("hx", "zenith", "outsider", "indep")]


def strong_field():
    return ext1_strong() + fields.HOLDOUT_ELITE + fields.DEV_ELITE


if __name__ == "__main__":
    args = sys.argv[1:]
    opt = {"--maps": "120", "--seed": "11"}
    for k in list(opt):
        if k in args:
            i = args.index(k); opt[k] = args[i + 1]; del args[i:i + 2]
    field = strong_field()
    fx = arena.fixtures(field, maps=int(opt["--maps"]), seed=int(opt["--seed"]), families=sim.FAMILIES + sim.NEW_FAMILIES)
    tasks = []
    for f in fx:
        for c in args:
            names = list(f["opponents"]); names.insert(f["seat"], c)
            tasks.append(dict(names=names, family=f["family"], mapseed=f["mapseed"], token=f["token"], seed=f["seed"],
                              cand=c, seat=f["seat"]))
    res = arena.run_tasks(tasks)
    agg = {c: collections.defaultdict(lambda: [0, 0.0, 0.0]) for c in args}
    fam = {c: collections.defaultdict(lambda: [0, 0.0, 0.0]) for c in args}
    tot = {c: [0, 0.0, 0.0] for c in args}
    for r in res:
        if "error" in r: continue
        t = r["task"]; s = r["scores"]; i = t["seat"]
        tot[t["cand"]][0] += 1; tot[t["cand"]][1] += r["pw"][i]; tot[t["cand"]][2] += s[i]
        fa = fam[t["cand"]][t["family"]]; fa[0] += 1; fa[1] += r["pw"][i]; fa[2] += s[i]
        for j, name in enumerate(t["names"]):
            if j == i: continue
            a = agg[t["cand"]][name]
            a[0] += 1; a[1] += 1.0 if s[i] > s[j] else 0.5 if s[i] == s[j] else 0.0; a[2] += s[i] - s[j]
    names = sorted(set(n for c in args for n in agg[c]), key=lambda n: agg[args[0]][n][1] / max(1, agg[args[0]][n][0]))
    print("%-34s" % "opponent" + "".join("%-22s" % c[-20:] for c in args))
    for n in names:
        row = "%-34s" % n[:33]
        for c in args:
            a = agg[c][n]
            row += "%.2f (%+5.0f) n=%-5d " % (a[1] / max(1, a[0]), a[2] / max(1, a[0]), a[0])
        print(row)
    print("\n%-34s" % "map family" + "".join("%-22s" % c[-20:] for c in args))
    for f in sim.FAMILIES[:1] + tuple(sorted(set(sim.FAMILIES[1:]))) + sim.NEW_FAMILIES:
        row = "%-34s" % f
        for c in args:
            a = fam[c][f]
            row += "%.2f (%5.0f) n=%-5d " % (a[1] / max(1, a[0]), a[2] / max(1, a[0]), a[0])
        print(row)
    print("%-34s" % "TOTAL PW (score)" + "".join("%-22s" % ("%.3f (%.0f) n=%d" % (tot[c][1] / max(1, tot[c][0]), tot[c][2] / max(1, tot[c][0]), tot[c][0])) for c in args))
