"""(1+lambda) tuner for Apex's own planner genome and tactic weights, with a
confirmation stage on fresh games (a winner of one noisy draw must win again).

    python tune_apex.py <generations> <out.json> [seed.json] [--n1=300] [--n2=500] [--lam=5]
"""
import json
import math
import os
import random
import sys
import time

LAB = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, LAB)
import zarena  # noqa

BOT = "apex/apex_bot.py"
SPACE = {
    "g_upgrade_open": (0.45, 4.5, 1.46008), "g_upgrade_late": (0.3, 6.0, 3.3705),
    "g_raid_open": (0.2, 2.4, 0.95839), "g_raid_late": (0.25, 3.5, 1.64117),
    "g_risk_open": (0.0, 10.0, 1.97775), "g_risk_late": (0.0, 14.0, 8.0),
    "g_income_lifetime": (6.0, 60.0, 40.67114), "g_safety_slope": (0.0, 12.0, 3.52153),
    "g_fortify_premium": (0.65, 2.0, 1.11474), "g_denial_base": (0.0, 1.2, 0.66671),
    "g_denial_close": (0.0, 1.3, 0.20084), "g_cash_weight": (0.4, 2.5, 1.25275),
    "g_contest_cost": (0.0, 3.0, 0.42039), "g_breadth": (3, 12, 7),
    "g_route_weight": (0.0, 1.5, 0.61979), "g_route_delay": (0.0, 0.5, 0.02),
    "g_inertia": (0.0, 0.3, 0.0496), "g_shield_weight": (0.1, 3.0, 1.30296),
    "g_backfire_cost": (0.3, 5.0, 1.13552), "g_feint_weight": (0.0, 2.0, 1.25119),
    "g_stay_prior": (0.3, 0.95, 0.76),
    "g_home_retention": (20.0, 100.0, 100.0), "g_vexp": (0.7, 1.8, 1.0),
    "wr": (0.0, 1.5, 0.5), "hk": (4, 30, 14), "kappa": (0.3, 3.0, 1.0),
}
INTS = {"g_breadth", "hk"}


def spec(p):
    kv = ",".join("%s:%s" % (k, (int(round(v)) if k in INTS else round(v, 5))) for k, v in sorted(p.items()))
    return "file:%s+rollout:0%s" % (BOT, ("," + kv) if kv else "")


def mutate(p, rnd):
    q = dict(p)
    keys = list(SPACE)
    for k in rnd.sample(keys, rnd.choice((1, 1, 2, 2, 3))):
        lo, hi, d = SPACE[k]
        cur = q.get(k, d)
        v = cur + rnd.gauss(0, 0.18 * (hi - lo))
        v = max(lo, min(hi, v))
        if k in INTS:
            v = int(round(v))
        q[k] = v
    return q


def paired(res, a, b):
    xa, xb = res[a], res[b]
    d = [xb[i]["pw"] - xa[i]["pw"] for i in range(len(xa))]
    m, se = zarena.mean_se(d)
    return m, se, (m / se if se > 0 else 0.0)


def main(argv):
    gens = int(argv[1])
    out = argv[2]
    inc = {}
    if len(argv) > 3 and not argv[3].startswith("--") and os.path.exists(argv[3]):
        inc = json.load(open(argv[3]))
    opts = dict(a[2:].split("=") for a in argv[3:] if a.startswith("--"))
    n1, n2, lam = int(opts.get("n1", 300)), int(opts.get("n2", 500)), int(opts.get("lam", 5))
    seed0 = int(opts.get("seed", 1000))
    rnd = random.Random(seed0)
    log = open(out + ".log", "a")
    for g in range(gens):
        t0 = time.time()
        cands = [mutate(inc, rnd) for _ in range(lam)]
        tasks = zarena.make_tasks(n1, "mix", seed=seed0 + 2 * g)
        specs = [("inc", spec(inc))] + [("c%d" % k, spec(c)) for k, c in enumerate(cands)]
        res = zarena.run(specs, tasks)
        scored = []
        for k in range(lam):
            m, se, z = paired(res, "inc", "c%d" % k)
            scored.append((z, m, k))
        scored.sort(reverse=True)
        z, m, k = scored[0]
        line = "gen %d best c%d dPW %+.4f z %+.2f  %s" % (g, k, m, z, json.dumps(
            dict((kk, v) for kk, v in cands[k].items() if inc.get(kk) != v)))
        accepted = False
        if m > 0 and z > 1.0:
            tasks2 = zarena.make_tasks(n2, "mix", seed=seed0 + 2 * g + 1)
            res2 = zarena.run([("inc", spec(inc)), ("cand", spec(cands[k]))], tasks2)
            m2, se2, z2 = paired(res2, "inc", "cand")
            line += " | confirm dPW %+.4f z %+.2f" % (m2, z2)
            if m2 > 0 and z2 > 1.5:
                inc = cands[k]
                accepted = True
                json.dump(inc, open(out, "w"), indent=1, sort_keys=True)
        line += "  ACCEPT" if accepted else ""
        line += "  (%.0fs)" % (time.time() - t0)
        print(line, flush=True)
        log.write(line + "\n")
        log.flush()
    json.dump(inc, open(out, "w"), indent=1, sort_keys=True)


if __name__ == "__main__":
    main(sys.argv)
