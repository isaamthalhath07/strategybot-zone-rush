"""
Paired A/B measurement.

Unpaired tournament means are far too noisy to judge a change worth 0.02 PW: the
per-game standard deviation of pairwise wins is about 1.0, so 400 unpaired games
give a standard error near 0.05 and most real improvements vanish into it.

So every variant here plays the *identical* list of (map, seat, opponents, token)
tasks, and variants are compared by their per-task difference. The paired standard
error is what gets printed, and it is typically 3-5x smaller than the unpaired one
because map and lineup luck cancels exactly.

    python measure.py <games> <tier> <name>=<file.json> [<name>=<file.json> ...]
    python measure.py 600 realistic base=v6_params.json cand=cand.json

`base` (or the first variant given) is the reference; every other variant is
reported as a difference from it with a paired standard error and a z score.
"""
import json
import math
import multiprocessing as mp
import os
import random
import sys

import engine
import field as fieldmod
import maps
import mybot


def _default_procs():
    """PROCS caps the pool, so a measurement can share the machine with a
    tuner instead of oversubscribing it. Results do not depend on it: both
    clock-reading paths are pinned off, which is the whole point of that
    pinning."""
    n = int(os.environ.get("PROCS", "0"))
    return n if n > 0 else min(24, mp.cpu_count())


def _make(name, seed):
    import field as fieldmod
    return fieldmod.opponent(name)(seed)


def make_tasks(n, tier, seed=1):
    rnd = random.Random(seed)
    pool = fieldmod.tier(tier)
    out = []
    for _ in range(n):
        out.append((rnd.randrange(1 << 30), rnd.randrange(4),
                    [pool[rnd.randrange(len(pool))] for _ in range(3)],
                    rnd.randint(1, 4)))
    return out


def play(params, task):
    map_seed, myseat, opps, token = task
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
    base = maps.make(map_seed)      # MAPS picks the family; default unchanged
    bots = []
    k = 0
    for i in range(4):
        if i == myseat:
            bots.append(mybot.Agent(seed=map_seed & 0xffff, params=params))
        else:
            bots.append(_make(opps[k], map_seed * 4 + i))
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
    return pw, g.score[myseat], pl[myseat]


def _worker(arg):
    params, tasks = arg
    return [play(params, t) for t in tasks]


def run(variants, tasks, procs=None, chunk=10):
    """variants: [(name, params)]. Returns name -> per-task [(pw, score, place)]."""
    pool = mp.Pool(procs or _default_procs())
    jobs = []
    owner = []
    for vi, (_n, p) in enumerate(variants):
        for i in range(0, len(tasks), chunk):
            jobs.append((p, tasks[i:i + chunk]))
            owner.append(vi)
    res = pool.map(_worker, jobs, chunksize=1)
    pool.close()
    pool.join()
    out = [[] for _ in variants]
    for o, r in zip(owner, res):
        out[o].extend(r)
    return dict((variants[i][0], out[i]) for i in range(len(variants)))


def report(variants, res, label=""):
    names = [n for n, _ in variants]
    ref = names[0]
    a = res[ref]
    n = len(a)
    print("\n%s%d paired games, reference = %s" % (label and label + "  ", n, ref))
    print("%-12s %7s %8s %7s   %9s %8s %7s"
          % ("variant", "PW/3", "score", "place", "dPW", "+/- SE", "z"))
    print("-" * 68)
    for nm in names:
        b = res[nm]
        pw = sum(x[0] for x in b) / n
        sc = sum(x[1] for x in b) / n
        pc = sum(x[2] for x in b) / n
        if nm == ref:
            print("%-12s %7.3f %8.0f %7.2f %s" % (nm, pw, sc, pc, "   (reference)"))
            continue
        d = [b[i][0] - a[i][0] for i in range(n)]
        md = sum(d) / n
        if n > 1:
            var = sum((x - md) ** 2 for x in d) / (n - 1)
            se = math.sqrt(var / n)
        else:
            se = float("inf")
        z = md / se if se > 0 else 0.0
        mark = ""
        if abs(z) >= 2.58:
            mark = "  **"
        elif abs(z) >= 1.96:
            mark = "  *"
        print("%-12s %7.3f %8.0f %7.2f   %+9.4f %8.4f %+7.2f%s"
              % (nm, pw, sc, pc, md, se, z, mark))
    print("  * paired difference significant at 5%, ** at 1%")


def load(spec):
    """name=file.json[+key:val,key:val]  -- inline overrides save writing files."""
    name, _, rest = spec.partition("=")
    if not rest:
        raise SystemExit("want name=file.json[+key:val], got %r" % spec)
    path, _, overrides = rest.partition("+")
    p = dict(mybot.PARAMS)
    if path not in ("current", ""):
        p.update(json.load(open(path)))
    for kv in overrides.split(","):
        if not kv:
            continue
        k, _, v = kv.partition(":")
        if k not in p:
            raise SystemExit("unknown param %r" % k)
        p[k] = int(v) if isinstance(p[k], int) and "." not in v else float(v)
    return name, p


if __name__ == "__main__":
    if len(sys.argv) < 4:
        raise SystemExit(__doc__)
    games = int(sys.argv[1])
    tier = sys.argv[2]
    variants = [load(s) for s in sys.argv[3:]]
    # SEED draws a fresh set of games, for confirming a result on games it was
    # not discovered on. Reusing the discovery set would re-measure the same luck.
    tasks = make_tasks(games, tier, seed=int(os.environ.get("SEED", "1")))
    res = run(variants, tasks)
    report(variants, res, label="[%s]" % tier)
