"""Second development-only sweep: a finer look at the one sensitive setting (hazard), and
at the prior over landlords' Shield habits, which lab/sensitivity.py cannot reach.

  python3 lab/sensitivity2.py [--seed 500]
"""
import os, sys, json, re, time
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import build, suite

BASE = "zr5"
PRIORS = {"flat": "(.20, .20, .20, .20, .20)",
          "sight": "(.10, .35, .20, .30, .05)",       # on-sight shielding is what a one-shot AI bot writes
          "never": "(.40, .10, .15, .30, .05)"}

if __name__ == "__main__":
    args = sys.argv[1:]
    seed = int(args[args.index("--seed") + 1]) if "--seed" in args else 500
    names = []
    for h in (0.6, 0.75, 0.85, 1.25, 1.5):
        name = "sens_hazard_%s" % str(h).replace(".", "p")
        build.build(name, hazard=h)
        names.append(name)
    base_src = open(build.build("sens_tmp")).read()
    os.remove(os.path.join(HERE, "cand", "sens_tmp.py"))
    for key, val in PRIORS.items():
        src, n = re.subn(r"^_TYPE_PRIOR = \(.*\)$", "_TYPE_PRIOR = " + val, base_src, count=1, flags=re.M)
        assert n == 1
        name = "sens_prior_" + key
        open(os.path.join(HERE, "cand", name + ".py"), "w").write(src)
        names.append(name)
    t0 = time.time()
    table = suite.run(names, BASE, seed=seed, selfname=BASE)
    out = {c: {f: {k: e[k] for k in ("pw", "diff", "lo", "hi", "n") if k in e} for f, e in row.items()} for c, row in table.items()}
    json.dump(dict(base=BASE, seed=seed, table=out), open(os.path.join(HERE, "results", "sensitivity2_dev.json"), "w"), indent=1)
    print("%.0fs" % (time.time() - t0))
