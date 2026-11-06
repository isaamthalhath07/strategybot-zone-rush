"""
Self-play weight tuning: (1+lambda) evolutionary search on the bot's PARAMS,
scored as mean pairwise wins against a field of opponent archetypes.

Common random numbers -- every candidate in a generation plays the identical set
of (map, seat, opponent-lineup) tasks -- so a generation compares policies, not
luck. The task set is refreshed periodically and the incumbent re-scored on it,
and there is a held-out validation set at the end to catch overfitting.
"""
import json
import multiprocessing
import os
import random
import sys
import time

import engine
import mybot
import rivals
import zoo

# my best guess at the real Round 1 field, by weight
FIELD = [
    ("spine", 3.5), ("camper", 3.0), ("greedy", 1.5), ("greedyshield", 1.5),
    ("pacifist", 1.0), ("raider", 0.8), ("baiter", 0.8), ("random", 0.2),
    ("stay", 0.15),
]

# param -> (low, high, is_integer, mutation step as a fraction of the range)
BOUNDS = {
    "horizon":        (8, 40, True, 0.12),
    "visits":         (5, 10, True, 0.14),
    "beam":           (40, 400, True, 0.12),
    "ncand":          (8, 26, True, 0.12),
    "reach":          (4, 10, True, 0.12),
    "stickiness":     (1.00, 1.35, False, 0.10),
    "w_claim":        (0.5, 1.8, False, 0.10),
    "w_upgrade":      (0.5, 2.0, False, 0.10),
    "w_raid":         (0.3, 2.0, False, 0.10),
    "w_raid_late":    (0.3, 3.0, False, 0.12),
    "combo":          (0.0, 1.6, False, 0.12),
    "hold":           (0.0, 1.2, False, 0.12),
    "consolidate":    (-0.8, 0.9, False, 0.12),
    "lead_caution":   (0.0, 0.8, False, 0.12),
    "combo_pri":      (0.3, 2.0, False, 0.12),
    "w_denial":       (0.0, 1.5, False, 0.12),
    "perish":         (0.0, 1.0, False, 0.12),
    "safe_discount":  (0.6, 1.15, False, 0.10),
    "zone_bonus":     (1.0, 1.7, False, 0.10),
    "squat_penalty":  (0.05, 1.0, False, 0.12),
    "contest_penalty": (0.0, 1.5, False, 0.12),
    "kappa":          (0.3, 1.4, False, 0.10),
    "def_kappa":      (0.3, 2.5, False, 0.10),
    "freeze_cost":    (0.5, 4.0, False, 0.12),
    "q_prior":        (0.2, 0.9, False, 0.10),
    "q_weight":       (1.0, 12.0, False, 0.12),
    "raid_risk":      (0.4, 1.6, False, 0.10),
    "shield_cost":    (0.4, 4.0, False, 0.12),
    "shield_bias":    (0.3, 3.0, False, 0.12),
    "shield_certain": (0.6, 1.0, False, 0.08),
    "retake_credit":  (0.0, 0.9, False, 0.12),
    "commit_prior":   (0.15, 0.9, False, 0.12),
    "free_shield_turns": (1, 5, True, 0.15),
    "tau":            (60.0, 420.0, False, 0.12),
}


def get_field(spec):
    """
    default : the zoo only (the predicted Round 1 field)
    mixed   : the zoo plus every frozen snapshot -- the real training target
    counter : only the named snapshot, for tuning a bot to beat it
    """
    if spec == "default":
        return list(FIELD)
    snaps = rivals.names()
    if spec == "mixed":
        f = list(FIELD)
        for s_ in snaps:
            f.append((s_, 2.5))
        return f
    if spec.startswith("counter:"):
        return [(spec.split(":", 1)[1], 1.0)]
    raise SystemExit("unknown field spec %r (want default|mixed|counter:NAME)" % spec)


def make_tasks(n, seed, field=None):
    rnd = random.Random(seed)
    names = [n_ for n_, w in (field or FIELD)]
    wts = [w for n_, w in (field or FIELD)]
    cum = []
    t = 0.0
    for w in wts:
        t += w
        cum.append(t)

    def pick():
        x = rnd.random() * t
        for i, c in enumerate(cum):
            if x <= c:
                return names[i]
        return names[-1]

    tasks = []
    for _ in range(n):
        tasks.append((rnd.randrange(1 << 30), rnd.randrange(4),
                      [pick() for _ in range(3)], rnd.randint(1, 4)))
    return tasks


def _factory(name):
    """Opponent by name: a zoo archetype, or a frozen snapshot of this bot."""
    if name in _ZOO:
        return _ZOO[name]
    return rivals.factory(name)


_ZOO = dict((c.name, c) for c in zoo.ZOO)


def play_task(params, task):
    map_seed, myseat, opps, token = task
    base = engine.make_map(seed=map_seed)
    ag = mybot.Agent(seed=map_seed & 0xffff, params=params)
    bots = []
    k = 0
    for i in range(4):
        if i == myseat:
            bots.append(ag)
        else:
            bots.append(_factory(opps[k])(map_seed * 4 + i))
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
    pw = 0.0
    for j in range(4):
        if j == myseat:
            continue
        if pl[myseat] < pl[j]:
            pw += 1.0
        elif pl[myseat] == pl[j]:
            pw += 0.5
    return pw, g.score[myseat]


def _worker(arg):
    params, tasks = arg
    tot = 0.0
    sc = 0.0
    for t in tasks:
        pw, s = play_task(params, t)
        tot += pw
        sc += s
    return tot, sc, len(tasks)


def evaluate(pool, cands, tasks, chunk=12):
    """Score every candidate on the same task list. Returns [(pw, score), ...]."""
    jobs = []
    owner = []
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


def mutate(p, rnd, sigma):
    q = dict(p)
    keys = list(BOUNDS.keys())
    # mutate a random subset, so steps stay informative
    k = max(1, int(len(keys) * rnd.uniform(0.18, 0.5)))
    for key in rnd.sample(keys, k):
        lo, hi, isint, step = BOUNDS[key]
        span = hi - lo
        v = q[key] + rnd.gauss(0.0, step * span * sigma)
        if v < lo:
            v = lo
        if v > hi:
            v = hi
        q[key] = int(round(v)) if isint else v
    return q


def main():
    gens = int(sys.argv[1]) if len(sys.argv) > 1 else 30
    ntasks = int(sys.argv[2]) if len(sys.argv) > 2 else 96
    lam = int(sys.argv[3]) if len(sys.argv) > 3 else 23
    fieldspec = sys.argv[4] if len(sys.argv) > 4 else "default"
    outfile = sys.argv[5] if len(sys.argv) > 5 else "best_params.json"
    seedfile = sys.argv[6] if len(sys.argv) > 6 else outfile
    field = get_field(fieldspec)
    print("field: %s" % ", ".join("%s(%.1f)" % (n_, w) for n_, w in field))
    start = dict(mybot.PARAMS)
    if os.path.exists(seedfile):
        start.update(json.load(open(seedfile)))
        print("seeding from %s" % seedfile)
    rnd = random.Random(20261106)
    pool = multiprocessing.Pool(processes=min(24, multiprocessing.cpu_count()))
    sigma = 1.0
    tasks = make_tasks(ntasks, 1, field)
    cur = start
    (curpw, cursc), = evaluate(pool, [cur], tasks)
    print("gen  0  incumbent PW %.4f  score %.0f  sigma %.2f" % (curpw, cursc, sigma))
    t0 = time.time()
    hist = []
    for gen in range(1, gens + 1):
        if gen % 6 == 1 and gen > 1:
            # refresh the task set and re-score the incumbent on it, so we never
            # keep a candidate that only won on one particular draw of games
            tasks = make_tasks(ntasks, 1000 + gen, field)
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
        hist.append(curpw)
        print("gen %2d  %s  PW %.4f  score %.0f  sigma %.2f  (%.0fs)"
              % (gen, tag, curpw, cursc, sigma, time.time() - t0))
        json.dump(cur, open(outfile, "w"), indent=1, sort_keys=True)

    # held-out validation against a task set never used during tuning
    val = make_tasks(400, 999331, field)
    base_pw, base_sc = evaluate(pool, [dict(mybot.PARAMS)], val)[0]
    new_pw, new_sc = evaluate(pool, [cur], val)[0]
    print("\nheld-out validation over %d games" % len(val))
    print("  starting params : PW %.4f/3   score %.0f" % (base_pw, base_sc))
    print("  tuned params    : PW %.4f/3   score %.0f" % (new_pw, new_sc))
    print("  delta           : %+.4f PW   %+.0f score" % (new_pw - base_pw, new_sc - base_sc))
    pool.close()
    json.dump(cur, open(outfile, "w"), indent=1, sort_keys=True)
    print("\nwrote best_params.json")


if __name__ == "__main__":
    main()
