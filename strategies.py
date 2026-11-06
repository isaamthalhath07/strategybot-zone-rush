"""
Macro-strategy sweep.

v1..v5 were all the SAME strategy with different weights. This file writes out the
distinct macro plans the game actually admits and scores each one against the same
opponents with common random numbers, so the comparison is between plans rather
than between lucky draws.
"""
import json
import multiprocessing
import random
import sys

import engine
import holdout
import mybot
import zoo

BASE = json.load(open("v3_params.json"))

# Each entry is an overlay on the tuned v3 weights. The point of a named strategy
# is that it changes WHAT the bot tries to do, not just how hard it tries.
STRATEGIES = {
    # --- the incumbent ---------------------------------------------------------
    "v3 (incumbent)":        {},
    "ignore rivals":         {"care_mode": 4, "w_denial": 0.0},
    # --- consolidation and search --------------------------------------------
    "claim+upgrade combo":   {"combo": 0.5},
    "deep search":           {"visits": 8, "horizon": 40, "beam": 300},
    # --- combinations of what won round one ----------------------------------
    "deep + ignore":         {"visits": 8, "horizon": 40, "beam": 300,
                              "care_mode": 4, "w_denial": 0.0},
    "deep + combo":          {"visits": 8, "horizon": 40, "beam": 300, "combo": 0.5},
    "deep + ignore + combo": {"visits": 8, "horizon": 40, "beam": 300,
                              "care_mode": 4, "w_denial": 0.0, "combo": 0.5},
    "deep + leader":         {"visits": 8, "horizon": 40, "beam": 300,
                              "care_mode": 1},
    "deeper beam 700":       {"visits": 8, "horizon": 40, "beam": 700, "ncand": 14},
    "deeper + ignore":       {"visits": 8, "horizon": 40, "beam": 700, "ncand": 14,
                              "care_mode": 4, "w_denial": 0.0},
    "widest":                {"visits": 8, "horizon": 40, "beam": 900, "ncand": 18,
                              "reach": 7, "care_mode": 4, "w_denial": 0.0,
                              "combo": 0.5},
}

ZOO = dict((c.name, c) for c in zoo.ZOO)
ZOO.update(dict((c.name, c) for c in holdout.HOLDOUT))

FIELDS = {
    "predicted field": [("greedy", 3.0), ("greedyshield", 3.0), ("pacifist", 2.0),
                        ("spine", 2.0), ("camper", 2.0), ("raider", 1.5),
                        ("baiter", 1.0), ("random", 0.5), ("stay", 0.3)],
    "strong farmers":  [("spine", 3.0), ("camper", 2.0), ("turtle", 2.0),
                        ("pacifist", 1.0)],
    "held-out field":  [("turtle", 1.0), ("hunter", 1.0), ("centre", 1.0),
                        ("cdraider", 1.0)],
}


def make_tasks(n, seed, field):
    rnd = random.Random(seed)
    names = [a for a, w in field]
    cum, t = [], 0.0
    for a, w in field:
        t += w
        cum.append(t)

    def pick():
        x = rnd.random() * t
        for i, c in enumerate(cum):
            if x <= c:
                return names[i]
        return names[-1]
    return [(rnd.randrange(1 << 30), rnd.randrange(4),
             [pick() for _ in range(3)], rnd.randint(1, 4)) for _ in range(n)]


def _worker(arg):
    overlay, tasks = arg
    params = dict(mybot.PARAMS)
    params.update(BASE)
    params.update(overlay)
    pw = 0.0
    sc = 0.0
    for map_seed, myseat, opps, token in tasks:
        base = engine.make_map(seed=map_seed)
        ag = mybot.Agent(seed=map_seed & 0xffff, params=params)
        bots = []
        k = 0
        for i in range(4):
            if i == myseat:
                bots.append(ag)
            else:
                bots.append(ZOO[opps[k]](map_seed * 4 + i))
                k += 1
        g = engine.Game(base=base, start_token=token)
        while not g.over():
            vs = g.views()
            acts = []
            for i in range(4):
                try:
                    a = bots[i](vs[i])
                except Exception:
                    a = "STAY"
                if a not in vs[i].legal_actions:
                    a = "STAY"
                acts.append(a)
            g.step(acts)
        pl = g.places()
        pw += sum(1.0 for j in range(4) if j != myseat and pl[myseat] < pl[j])
        pw += 0.5 * sum(1 for j in range(4) if j != myseat and pl[myseat] == pl[j])
        sc += g.score[myseat]
    return pw, sc, len(tasks)


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 150
    pool = multiprocessing.Pool(processes=min(24, multiprocessing.cpu_count()))
    names = list(STRATEGIES.keys())
    results = {}
    for fname, field in FIELDS.items():
        tasks = make_tasks(n, 4242, field)         # identical tasks for every strategy
        jobs, owner = [], []
        for si, sname in enumerate(names):
            for i in range(0, len(tasks), 10):
                jobs.append((STRATEGIES[sname], tasks[i:i + 10]))
                owner.append(si)
        res = pool.map(_worker, jobs, chunksize=1)
        acc = [[0.0, 0.0, 0] for _ in names]
        for o, (pw, sc, c) in zip(owner, res):
            acc[o][0] += pw
            acc[o][1] += sc
            acc[o][2] += c
        results[fname] = dict((names[i], (acc[i][0] / acc[i][2], acc[i][1] / acc[i][2]))
                              for i in range(len(names)))
        print("  done: %s" % fname)
    pool.close()

    fnames = list(FIELDS.keys())
    print("\nPW out of 3, same %d games per cell. 1.50 = exactly average." % n)
    hdr = "%-22s" % "strategy"
    for f in fnames:
        hdr += "%17s" % f
    print(hdr + "%9s" % "mean")
    print("-" * (22 + 17 * len(fnames) + 9))
    rows = []
    for sname in names:
        vals = [results[f][sname][0] for f in fnames]
        rows.append((sum(vals) / len(vals), sname, vals,
                     [results[f][sname][1] for f in fnames]))
    rows.sort(reverse=True)
    for mean, sname, vals, scs in rows:
        line = "%-22s" % sname
        for v, sc in zip(vals, scs):
            line += "%11.2f %5.0f" % (v, sc)
        print(line + "%9.3f" % mean)
    base_mean = [r[0] for r in rows if r[1] == "v3 (incumbent)"][0]
    print("\nversus the incumbent (v3 = %.3f):" % base_mean)
    for mean, sname, vals, scs in rows:
        if sname == "v3 (incumbent)":
            continue
        d = mean - base_mean
        if abs(d) > 0.02:
            print("  %-22s %+.3f %s" % (sname, d, "better" if d > 0 else "worse"))


if __name__ == "__main__":
    main()
