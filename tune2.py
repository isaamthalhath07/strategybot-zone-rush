"""
Re-tune the bot against a broader field than tune.py used.

The original tuning field was nine archetypes written alongside the bot. This one
adds five independently written agents from newfield.py and two frozen copies of
the bot itself. Three newfield agents (grab, seq, rollout) and all of holdout.py
are deliberately kept OUT of training, so bench2.py can measure whether the new
weights generalise or merely fit this field.

    python tune2.py <generations> <games/gen> <population> <out.json> <seed.json>

Same (1+lambda) evolutionary search as tune.py, with common random numbers.
"""
import json
import multiprocessing
import os
import random
import sys
import time

import engine
import mybot
import tune
from bench2 import factory

FIELD = [
    # original zoo
    ("spine", 2.0), ("camper", 1.5), ("greedy", 1.0), ("greedyshield", 1.0),
    ("pacifist", 0.6), ("raider", 0.6), ("baiter", 0.6), ("random", 0.15),
    ("stay", 0.1),
    # independently written agents (grab, seq, rollout are held out)
    ("route", 2.5), ("rate", 1.5), ("vulture", 1.5), ("guard", 1.0), ("harass", 1.0),
    # the bot itself, as the strongest opponents available
    ("snap:v6", 1.0), ("snap:v3", 1.0),
]

BOUNDS = dict(tune.BOUNDS)
BOUNDS.update({
    "q_weight2": (0.5, 10.0, False, 0.12),
    "tail": (0.0, 0.8, False, 0.10),
    "qmode": (0, 1, True, 0.6),
})
CATEGORICAL = {"care_mode": [0, 4]}


def mutate(p, rnd, sigma):
    q = dict(p)
    keys = list(BOUNDS.keys()) + list(CATEGORICAL.keys())
    k = max(1, int(len(keys) * rnd.uniform(0.18, 0.5)))
    for key in rnd.sample(keys, k):
        if key in CATEGORICAL:
            if rnd.random() < 0.3:
                q[key] = rnd.choice(CATEGORICAL[key])
            continue
        lo, hi, isint, step = BOUNDS[key]
        v = q[key] + rnd.gauss(0.0, step * (hi - lo) * sigma)
        v = min(hi, max(lo, v))
        q[key] = int(round(v)) if isint else v
    return q


def play_task(params, task):
    map_seed, myseat, opps, token = task
    base = engine.make_map(seed=map_seed)
    bots = []
    k = 0
    for i in range(4):
        if i == myseat:
            bots.append(mybot.Agent(seed=map_seed & 0xffff, params=params))
        else:
            bots.append(factory(opps[k])(map_seed * 4 + i))
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
    pw = sum(1.0 for j in range(4) if j != myseat and pl[myseat] < pl[j])
    pw += 0.5 * sum(1 for j in range(4) if j != myseat and pl[myseat] == pl[j])
    return pw, g.score[myseat]


def _worker(arg):
    params, tasks = arg
    tot = sc = 0.0
    for t in tasks:
        pw, s = play_task(params, t)
        tot += pw
        sc += s
    return tot, sc, len(tasks)


def evaluate(pool, cands, tasks, chunk=10):
    jobs, owner = [], []
    for ci, p in enumerate(cands):
        for i in range(0, len(tasks), chunk):
            jobs.append((p, tasks[i:i + chunk]))
            owner.append(ci)
    res = pool.map(_worker, jobs, chunksize=1)
    out = [[0.0, 0.0, 0] for _ in cands]
    for o, (tot, sc, n) in zip(owner, res):
        out[o][0] += tot
        out[o][1] += sc
        out[o][2] += n
    return [(r[0] / max(1, r[2]), r[1] / max(1, r[2])) for r in out]


def main():
    gens = int(sys.argv[1]) if len(sys.argv) > 1 else 20
    ntasks = int(sys.argv[2]) if len(sys.argv) > 2 else 150
    lam = int(sys.argv[3]) if len(sys.argv) > 3 else 12
    outfile = sys.argv[4] if len(sys.argv) > 4 else "v7_params.json"
    seedfile = sys.argv[5] if len(sys.argv) > 5 else outfile
    start = dict(mybot.PARAMS)
    start.update(json.load(open(seedfile)))
    print("field: %s" % ", ".join("%s(%.1f)" % f for f in FIELD))
    print("seeding from %s" % seedfile, flush=True)
    rnd = random.Random(20261107)
    pool = multiprocessing.Pool(processes=min(20, multiprocessing.cpu_count()))
    sigma = 1.0
    tasks = tune.make_tasks(ntasks, 1, FIELD)
    cur = start
    (curpw, cursc), = evaluate(pool, [cur], tasks)
    print("gen  0  incumbent PW %.4f  score %.0f" % (curpw, cursc), flush=True)
    t0 = time.time()
    for gen in range(1, gens + 1):
        if gen % 5 == 1 and gen > 1:
            # fresh games, and re-score the incumbent on them, so a lucky draw
            # cannot keep a candidate in place
            tasks = tune.make_tasks(ntasks, 1000 + gen, FIELD)
            (curpw, cursc), = evaluate(pool, [cur], tasks)
        cands = [mutate(cur, rnd, sigma) for _ in range(lam)]
        res = evaluate(pool, cands, tasks)
        bi = max(range(lam), key=lambda i: res[i][0])
        bpw, bsc = res[bi]
        if bpw > curpw:
            cur, curpw, cursc = cands[bi], bpw, bsc
            sigma = min(2.0, sigma * 1.18)
            tag = "accept"
        else:
            sigma = max(0.22, sigma * 0.90)
            tag = "  keep"
        print("gen %2d  %s  PW %.4f  score %.0f  sigma %.2f  (%.0fs)"
              % (gen, tag, curpw, cursc, sigma, time.time() - t0), flush=True)
        json.dump(cur, open(outfile, "w"), indent=1, sort_keys=True)
    pool.close()
    print("wrote %s" % outfile)


if __name__ == "__main__":
    main()
