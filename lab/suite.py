"""Development suite: every candidate on the same fixtures across several fields.
  python3 lab/suite.py [--ref cur_e8] [--scale 1.0] [--seed 100] cand1 cand2 ...
Fields: elite / mid / weak / mix (all development opponents) / self (2 copies of the
reference candidate + development elite), so a change that only helps against one kind of
opponent is visible immediately.
"""
import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import arena, fields

def run(cands, ref, scale=1.0, seed=100, selfname=None, which=None, quiet=False):
    selfname = selfname or cands[-1]
    plan = [("elite", fields.DEV_ELITE, 60), ("mid", fields.DEV_MID, 30), ("weak", fields.DEV_WEAK, 30),
            ("mix", fields.DEV_ALL, 40), ("self", fields.DEV_ELITE + [selfname] * 6, 30)]
    if which:
        plan = [p for p in plan if p[0] in which]
    allc = [ref] + [c for c in cands if c != ref]
    table = {}
    for k, (name, field, maps) in enumerate(plan):
        fx = arena.fixtures(field, maps=max(4, int(maps * scale)), seed=seed + k)
        per, err = arena.evaluate(allc, fx)
        for e in arena.summarize(per, ref=ref):
            table.setdefault(e["cand"], {})[name] = e
    names = [p[0] for p in plan]
    if not quiet:
        print("%-26s" % "candidate" + "".join("%-24s" % n for n in names))
        for c in allc:
            row = "%-26s" % c[-26:]
            for n in names:
                e = table[c][n]
                if "diff" in e:
                    row += "%.3f %+.3f[%+.2f,%+.2f] " % (e["pw"], e["diff"], e["lo"], e["hi"])
                else:
                    row += "%.3f %-18s" % (e["pw"], "(ref)")
            print(row)
    return table

if __name__ == "__main__":
    args = sys.argv[1:]
    opt = {"--ref": "cur_e8", "--scale": "1.0", "--seed": "100", "--self": None, "--only": None}
    for k in list(opt):
        if k in args:
            i = args.index(k); opt[k] = args[i + 1]; del args[i:i + 2]
    t = time.time()
    run(args, opt["--ref"], float(opt["--scale"]), int(opt["--seed"]), opt["--self"],
        opt["--only"].split(",") if opt["--only"] else None)
    print("%.0fs" % (time.time() - t))
