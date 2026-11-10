"""Development suite, second generation: every opponent that is no longer held out
(development pool, lab hold-out, EXT1 and its stress half), all 13 map families.

  python3 lab/suite2.py [--ref zr6] [--scale 1.0] [--seed 900] [--only strong,mid] cand ...

Fields
  strong  26 strong designs: EXT1 strong + hold-out elite + development elite
  mid     development and hold-out mid bots + the EXT1 generated families
  weak    development and hold-out weak bots + EXT1 pasted-AI bots + EXT1 stress half
  mix     everything above
  self    strong field plus copies of the last candidate (what if others built it too)

EXT2 and the other stress half are NOT here: they stay untouched for the final test.
Seeds: explore on any seed, then confirm a decision on a seed that has not been used
for that decision. Every seed used is written in lab/PROGRESS.md.
"""
import sys, os, json, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import arena, fields, sim

HERE = os.path.dirname(os.path.abspath(__file__))
FAMS = sim.FAMILIES + sim.NEW_FAMILIES


def groups():
    split = json.load(open(os.path.join(HERE, "ext", "split.json")))
    index = json.load(open(os.path.join(HERE, "ext", "index.json")))
    ext = split["EXT1"]
    by = lambda *g: [n for n in ext if index[n]["group"] in g]
    stress = sorted(f[:-3] for f in os.listdir(os.path.join(HERE, "stress")) if f.endswith(".py"))[::2]
    strong = by("hx", "zenith", "outsider", "indep") + fields.HOLDOUT_ELITE + fields.DEV_ELITE
    mid = fields.DEV_MID + fields.HOLDOUT_MID + by("gen", "rival")
    weak = fields.DEV_WEAK + fields.HOLDOUT_WEAK + by("gpt", "gemini") + stress
    return dict(strong=strong, mid=mid, weak=weak)


def plan(selfname):
    g = groups()
    return [("strong", g["strong"], 78), ("mid", g["mid"], 39), ("weak", g["weak"], 39),
            ("mix", g["strong"] + g["mid"] + g["weak"], 52), ("self", g["strong"] + [selfname] * 8, 39)]


def run(cands, ref, scale=1.0, seed=900, selfname=None, which=None, quiet=False, workers=4):
    selfname = selfname or cands[-1]
    allc = [ref] + [c for c in cands if c != ref]
    table = {}
    names = []
    for k, (name, field, maps) in enumerate(plan(selfname)):
        if which and name not in which:
            continue
        names.append(name)
        fx = arena.fixtures(field, maps=max(13, int(maps * scale)), seed=seed + k, families=FAMS)
        per, err = arena.evaluate(allc, fx, workers=workers)
        for e in arena.summarize(per, ref=ref):
            table.setdefault(e["cand"], {})[name] = e
    if not quiet:
        print("%-22s" % "candidate" + "".join("%-25s" % n for n in names))
        for c in allc:
            row = "%-22s" % c[-22:]
            for n in names:
                e = table[c][n]
                if "diff" in e:
                    row += "%.3f %+.3f[%+.2f,%+.2f] " % (e["pw"], e["diff"], e["lo"], e["hi"])
                else:
                    row += "%.3f %-19s" % (e["pw"], "(ref %.0f)" % e["score"])
            print(row)
    return table


if __name__ == "__main__":
    args = sys.argv[1:]
    opt = {"--ref": "zr6", "--scale": "1.0", "--seed": "900", "--self": None, "--only": None}
    for k in list(opt):
        if k in args:
            i = args.index(k); opt[k] = args[i + 1]; del args[i:i + 2]
    t = time.time()
    run(args, opt["--ref"], float(opt["--scale"]), int(opt["--seed"]), opt["--self"],
        opt["--only"].split(",") if opt["--only"] else None)
    print("%.0fs" % (time.time() - t))
