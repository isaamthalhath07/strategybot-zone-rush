"""
Tune the independent rival (probot.py) as hard as my own bot was tuned.

An untuned opponent is not evidence. If the only strong bots in the field are
snapshots of my own, then "my bot beats the field" partly means "my bot beats
itself", and both sides share whatever my planner gets wrong. Tuning a different
architecture against the same field gives the one thing the field was missing: a
strong opponent that is not me.

Same method as tune.py -- (1+lambda) with common random numbers, so every
candidate in a generation plays the identical games -- but the opponents here are
the hand-written designs and my frozen snapshots, never ProBot itself. A rival
tuned purely in self-play would converge on a weak mutual equilibrium, which is
exactly how the reinforcement-learning attempt failed.

    python tune_rival.py <gens> <games/gen> <pop> <out.json> [processes]
"""
import json
import multiprocessing
import os
import random
import sys
import time

import engine
import probot

# (low, high, integer, mutation step as a fraction of the range)
BOUNDS = {
    "w_claim":       (0.4, 2.0, False, 0.12),
    "w_upgrade":     (0.4, 2.2, False, 0.12),
    "w_raid":        (0.2, 2.2, False, 0.12),
    "w_raid_late":   (0.2, 3.5, False, 0.12),
    "bonus_mult":    (0.2, 2.0, False, 0.12),
    "compact":       (0.0, 0.45, False, 0.12),
    "centre":        (0.0, 0.45, False, 0.12),
    "cd_bonus":      (0.8, 3.0, False, 0.12),
    "cd_malus":      (0.2, 1.2, False, 0.12),
    "squat":         (0.05, 1.0, False, 0.12),
    "commit":        (1.0, 2.2, False, 0.10),
    "shield_floor":  (4.0, 90.0, False, 0.12),
    "shield_scale":  (0.0, 3.0, False, 0.12),
    "upg_pref":      (0.6, 2.0, False, 0.10),
    "home_pref":     (0.6, 2.2, False, 0.10),
}

# The field it is tuned against. Deliberately does NOT contain ProBot: a bot
# tuned only against copies of itself learns a weak mutual equilibrium.
FIELD = [
    ("v6", 3.0), ("v3", 2.0), ("spine", 2.5), ("camper", 2.0),
    ("ai_hawk", 2.0), ("ai_homefort", 2.0), ("ai_cheapraid", 1.5),
    ("cdraider", 1.2), ("turtle", 1.0), ("greedy", 1.2), ("greedyshield", 1.2),
    ("raider", 0.8), ("baiter", 0.8), ("random", 0.2),
]


def _opp(name):
    """See field.opponent. ProBot is deliberately absent from FIELD above: a bot
    tuned only against copies of itself learns a weak mutual equilibrium, which
    is exactly how the reinforcement-learning attempt failed."""
    import field as fieldmod
    return fieldmod.opponent(name)


def make_tasks(n, seed):
    rnd = random.Random(seed)
    names = [n_ for n_, _w in FIELD]
    wts = [w for _n, w in FIELD]
    tot = 0.0
    cum = []
    for w in wts:
        tot += w
        cum.append(tot)

    def pick():
        x = rnd.random() * tot
        for i, c in enumerate(cum):
            if x <= c:
                return names[i]
        return names[-1]

    return [(rnd.randrange(1 << 30), rnd.randrange(4),
             [pick() for _ in range(3)], rnd.randint(1, 4)) for _ in range(n)]


def play_task(params, task):
    map_seed, myseat, opps, token = task
    base = engine.make_map(seed=map_seed)
    bots = []
    k = 0
    for i in range(4):
        if i == myseat:
            bots.append(probot.ProBot(seed=map_seed & 0xffff, params=params))
        else:
            bots.append(_opp(opps[k])(map_seed * 4 + i))
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
    tot = sc = 0.0
    for t in tasks:
        pw, s = play_task(params, t)
        tot += pw
        sc += s
    return tot, sc, len(tasks)


def evaluate(pool, cands, tasks, chunk=12):
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


def mutate(p, rnd, sigma):
    q = dict(p)
    keys = list(BOUNDS.keys())
    for k in rnd.sample(keys, max(1, int(len(keys) * rnd.uniform(0.2, 0.55)))):
        lo, hi, isint, step = BOUNDS[k]
        v = q[k] + rnd.gauss(0.0, step * sigma) * (hi - lo)
        v = max(lo, min(hi, v))
        q[k] = int(round(v)) if isint else v
    return q


def main():
    gens = int(sys.argv[1]) if len(sys.argv) > 1 else 40
    ntasks = int(sys.argv[2]) if len(sys.argv) > 2 else 240
    lam = int(sys.argv[3]) if len(sys.argv) > 3 else 13
    out = sys.argv[4] if len(sys.argv) > 4 else "pro_params.json"
    procs = int(sys.argv[5]) if len(sys.argv) > 5 else min(24, multiprocessing.cpu_count())
    cur = dict(probot.WEIGHTS)
    if os.path.exists(out):
        cur.update(json.load(open(out)))
        print("seeding from %s" % out)
    rnd = random.Random(515)
    pool = multiprocessing.Pool(processes=procs)
    tasks = make_tasks(ntasks, 1)
    (curpw, cursc), = evaluate(pool, [cur], tasks)
    print("gen  0  incumbent PW %.4f  score %.0f" % (curpw, cursc))
    sigma = 1.0
    t0 = time.time()
    for gen in range(1, gens + 1):
        if gen % 6 == 1 and gen > 1:
            tasks = make_tasks(ntasks, 1000 + gen)
            (curpw, cursc), = evaluate(pool, [cur], tasks)
        cands = [mutate(cur, rnd, sigma) for _ in range(lam)]
        res = evaluate(pool, cands, tasks)
        bi = max(range(lam), key=lambda i: res[i][0])
        tag = "  keep"
        if res[bi][0] > curpw:
            # Confirmation stage, for the reason given in tune.py: the best of
            # `lam` candidates on one draw of games is a maximum over noisy
            # estimates and is biased upward by more than the improvements being
            # searched for. Measured on the real bot, thirteen generations
            # without this produced nothing at all.
            vt = make_tasks(max(160, ntasks), 5500000 + gen * 13)
            (vnew, _a), (vcur, _b) = evaluate(pool, [cands[bi], cur], vt)
            if vnew > vcur:
                cur, curpw, cursc = cands[bi], res[bi][0], res[bi][1]
                sigma = min(2.0, sigma * 1.18)
                tag = "accept"
            else:
                sigma = max(0.22, sigma * 0.95)
                tag = "reject"
        if tag == "  keep":
            sigma = max(0.22, sigma * 0.90)
        print("gen %2d  %s  PW %.4f  score %.0f  sigma %.2f  (%.0fs)"
              % (gen, tag, curpw, cursc, sigma, time.time() - t0))
        json.dump(cur, open(out, "w"), indent=1, sort_keys=True)
    val = make_tasks(400, 777001)
    b = evaluate(pool, [dict(probot.WEIGHTS)], val)[0]
    a = evaluate(pool, [cur], val)[0]
    print("\nheld-out validation over %d games" % len(val))
    print("  untuned ProBot : PW %.4f/3   score %.0f" % b)
    print("  tuned ProBot   : PW %.4f/3   score %.0f" % a)
    print("  delta          : %+.4f PW   %+.0f score" % (a[0] - b[0], a[1] - b[1]))
    pool.close()
    print("\nwrote %s" % out)


if __name__ == "__main__":
    main()
