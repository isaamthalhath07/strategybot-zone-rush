"""
Self-play weight tuning: (1+lambda) evolutionary search on the bot's PARAMS,
scored as mean pairwise wins against a field of opponent archetypes.

Common random numbers -- every candidate in a generation plays the identical set
of (map, seat, opponent-lineup) tasks -- so a generation compares policies, not
luck. The task set is refreshed periodically and the incumbent re-scored on it,
and there is a held-out validation set at the end to catch overfitting.

Selection also has a CONFIRMATION STAGE, which turned out to matter more than
anything else here. Taking the best of `lam` candidates on one draw of games is a
maximum over noisy estimates: with a few hundred games the standard error is
around 0.06 pairwise wins, and the best of thirteen draws is biased upward by
roughly 1.5 of those -- more than the improvements being searched for. Without
confirmation the search spends most of its generations accepting luck, and the
tell is that the incumbent drops by about that much every time the task set is
refreshed. A candidate now has to win twice: once on its own draw, then again
against the incumbent on games it was not selected on.
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

# The field that should actually drive decisions. Near-peers are weighted up
# because they are what decides Elo: beating a bot that barely works is worth
# the same single pairwise win as beating the best team in the room, but there
# are far more games in which the close calls are against serious entries.
REALISTIC = [
    ("v6", 3.0), ("v3", 2.0), ("nemesis2", 1.6), ("nemesis3", 1.6),
    ("pro_tuned", 3.0), ("pro", 0.8),
    ("ai_hawk", 2.2), ("ai_homefort", 2.2), ("ai_marginal", 1.8),
    ("ai_cheapraid", 1.8), ("ai_elo", 1.2), ("ai_centre", 1.0),
    ("ai_route", 1.0), ("spine", 2.5), ("camper", 2.0),
    ("cdraider", 1.2), ("turtle", 1.0), ("centre", 1.0), ("hunter", 1.0),
    ("greedy", 1.2), ("greedyshield", 1.2), ("raider", 0.8), ("baiter", 0.8),
    ("random", 0.2), ("stay", 0.15),
]
PEER = [
    ("v6", 3.0), ("v3", 2.0), ("nemesis1", 1.5), ("nemesis2", 1.5),
    ("nemesis3", 1.5), ("ai_hawk", 2.0), ("ai_homefort", 2.0), ("spine", 2.0),
    ("pro_tuned", 3.0),
]

# param -> (low, high, is_integer, mutation step as a fraction of the range)
BOUNDS = {
    "horizon":        (8, 50, True, 0.12),
    "visits":         (5, 10, True, 0.14),
    "beam":           (40, 400, True, 0.12),
    "ncand":          (6, 26, True, 0.12),
    "reach":          (3, 10, True, 0.12),
    "stickiness":     (1.00, 1.80, False, 0.10),
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
    "raid_risk":      (0.3, 2.5, False, 0.10),
    "shield_cost":    (0.4, 4.0, False, 0.12),
    "shield_bias":    (0.15, 6.0, False, 0.12),
    "shield_certain": (0.40, 1.0, False, 0.08),
    "retake_credit":  (0.0, 0.9, False, 0.12),
    "commit_prior":   (0.10, 0.98, False, 0.12),
    "free_shield_turns": (1, 5, True, 0.15),
    "tau":            (60.0, 420.0, False, 0.12),
    # added once the ruleset was confirmed
    "care_mode":      (0, 4, True, 0.30),
    "proj_care":      (0.0, 1.0, False, 0.20),
    "home_bonus":     (0.70, 1.60, False, 0.10),
    "upg_risk":       (0.0, 1.5, False, 0.12),
    "own_prog":       (0.0, 2.0, False, 0.12),
    "intent":         (0.0, 0.8, False, 0.12),
    "intent_turns":   (1, 4, True, 0.30),
    "endgame_care":   (0, 30, True, 0.18),
    "endgame_denial": (0.5, 4.0, False, 0.12),
    "tie_home":       (-1, 1, True, 0.40),
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
    if spec in ("realistic", "peer"):
        return list(REALISTIC if spec == "realistic" else PEER)
    raise SystemExit("unknown field spec %r "
                     "(want default|mixed|realistic|peer|counter:NAME)" % spec)


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
    """Opponent by name -- see field.opponent for the single resolver."""
    import field as fieldmod
    return fieldmod.opponent(name)


def play_task(params, task):
    map_seed, myseat, opps, token = task
    base = engine.make_map(seed=map_seed)
    # Determinism for measurement. Two things make play depend on wall-clock
    # time: the adaptive beam (throttle) and the hard deadline inside the beam
    # search, which truncates it when a turn runs long. Switching off only the
    # first is not enough -- under load the deadline still bites, and two
    # identical parameter sets then differ by as much as 0.06 pairwise wins,
    # which is the size of a real improvement. Both are shipping insurance
    # against a slow grader, not part of the policy, so evaluation runs with the
    # search always completing and bot.py keeps the guards.
    params = dict(params)
    params["throttle"] = 0
    params["budget_ms"] = 10000.0
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
    nverify = int(sys.argv[7]) if len(sys.argv) > 7 else max(160, ntasks)
    nproc = (int(sys.argv[8]) if len(sys.argv) > 8
             else min(24, multiprocessing.cpu_count()))
    field = get_field(fieldspec)
    print("field: %s" % ", ".join("%s(%.1f)" % (n_, w) for n_, w in field))
    start = dict(mybot.PARAMS)
    if os.path.exists(seedfile):
        start.update(json.load(open(seedfile)))
        print("seeding from %s" % seedfile)
    rnd = random.Random(20261106)
    pool = multiprocessing.Pool(processes=nproc)
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
        tag = "  keep"
        if bpw > curpw:
            # CONFIRMATION STAGE. Taking the best of `lam` candidates on one draw
            # of games is a maximum over noisy estimates, so the winner's score is
            # biased upward by roughly 1.5 standard errors -- with 264 games that
            # is about +0.09 pairwise wins of pure luck, which is larger than the
            # improvements being searched for. The symptom is unmistakable: every
            # time the task set was refreshed, the incumbent dropped by about that
            # much. So a candidate now has to beat the incumbent AGAIN on games it
            # was not selected on, with both re-scored on the same fresh draw.
            vt = make_tasks(nverify, 7700000 + gen * 17, field)
            (vnew, _vs), (vcur, _cs) = evaluate(pool, [cands[bi], cur], vt)
            if vnew > vcur:
                cur, curpw, cursc = cands[bi], bpw, bsc
                sigma = min(2.0, sigma * 1.18)
                tag = "accept"
            else:
                sigma = max(0.22, sigma * 0.95)
                tag = "reject"          # won its own draw, lost the confirmation
        if tag == "  keep":
            sigma = max(0.22, sigma * 0.90)
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
    print("\nwrote %s" % outfile)


if __name__ == "__main__":
    main()
