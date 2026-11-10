"""Development-set sensitivity sweep: one tunable moved at a time, everything else as zr4.

  python3 lab/sensitivity.py [--seed 300] [--scale 1.0]

A candidate that only works at its exact settings is overfitted to them. This prints,
for every variant, the paired difference from the unmodified candidate on each
development field. Uses development opponents only.
"""
import os, sys, json, time
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import build, suite

BASE = "zr4"
VARIANTS = [
    ("hazard", 0.5), ("hazard", 2.0),
    ("raid_exec", 0.7), ("raid_exec", 1.0),
    ("l1_delay", 0.1), ("l1_delay", 0.6),
    ("shield_margin", 0.7), ("shield_margin", 1.4),
    ("early_shield", 0.0), ("early_shield", 1.0),
    ("denial_floor", 0.0), ("denial_floor", 0.3),
    ("tail", 0.3), ("tail", 0.9),
    ("horizon", 12), ("horizon", 22),
    ("beam", 8), ("beam", 28),
    ("feints", 0), ("raids", 0), ("shields", 0),
]

if __name__ == "__main__":
    args = sys.argv[1:]
    seed = int(args[args.index("--seed") + 1]) if "--seed" in args else 300
    scale = float(args[args.index("--scale") + 1]) if "--scale" in args else 1.0
    names = []
    for key, val in VARIANTS:
        name = "sens_%s_%s" % (key, str(val).replace(".", "p"))
        build.build(name, **{key: val})
        names.append(name)
    t0 = time.time()
    table = suite.run(names, BASE, scale=scale, seed=seed, selfname=BASE)
    out = {c: {f: {k: e[k] for k in ("pw", "diff", "lo", "hi", "n") if k in e} for f, e in row.items()} for c, row in table.items()}
    json.dump(dict(base=BASE, seed=seed, scale=scale, table=out), open(os.path.join(HERE, "results", "sensitivity_dev.json"), "w"), indent=1)
    print("%.0fs" % (time.time() - t0))
