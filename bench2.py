"""
Benchmark one or more candidate bots against many opponent fields, in parallel,
with common random numbers: every candidate plays the identical (map, seat,
opponents, token, seed) tasks, so differences are between bots, not luck.

    python bench2.py <games per scenario> <candidate> [<candidate> ...]

A candidate is one of
    bot.py                       a shipped single-file bot (uses its baked weights)
    some_file.py:params.json     any file exposing Agent(seed, params)
    snap:v3                      a frozen snapshot from snapshots.json

PW is pairwise wins out of 3 (how many of the three rivals were outscored),
which is how Round 1 scores a four-bot game. 1.50 is exactly average.
"""
import importlib.util
import json
import math
import multiprocessing
import os
import random
import sys
import time

import engine
import holdout
import newfield
import zoo

HERE = os.path.dirname(os.path.abspath(__file__))

OPP = {}
for _c in zoo.ZOO + holdout.HOLDOUT + newfield.NEWFIELD:
    OPP[_c.name] = _c

_MOD_CACHE = {}


def _load(path):
    m = _MOD_CACHE.get(path)
    if m is None:
        name = "cand_%d" % len(_MOD_CACHE)
        spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, path))
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        _MOD_CACHE[path] = m
    return m


_FACT = {}


def factory(spec):
    """spec -> function(seed) returning a fresh act(view) callable for one game."""
    f = _FACT.get(spec)
    if f is None:
        f = _FACT[spec] = _factory(spec)
    return f


def _factory(spec):
    if spec in OPP:
        cls = OPP[spec]
        return lambda seed: cls(seed)
    if spec.startswith("snap:"):
        snaps = json.load(open(os.path.join(HERE, "snapshots.json")))
        params = dict(snaps[spec[5:]])
        m = _load("mybot.py")
        return lambda seed: m.Agent(seed=seed, params=params)
    if ".py:" in spec:
        path, pf = spec.split(".py:", 1)
        path += ".py"
        params = json.load(open(os.path.join(HERE, pf)))
        m = _load(path)
        return lambda seed: m.Agent(seed=seed, params=params)
    m = _load(spec)
    return lambda seed: m.Agent(seed=seed)


NEW = [c.name for c in newfield.NEWFIELD]
OLD = [c.name for c in zoo.ZOO if c.name not in ("stay", "random")]
HELD = [c.name for c in holdout.HOLDOUT]


def scenarios():
    sc = [("new field, mixed", NEW)]
    for n in NEW:
        sc.append(("new: 3x %s" % n, [n]))
    sc += [
        ("old zoo, mixed", OLD),
        ("old holdout, mixed", HELD),
        ("strong mix", ["route", "seq", "spine", "camper", "snap:v3", "snap:v6"]),
        ("3x shipped v6", ["snap:v6"]),
        ("everything", NEW + OLD + HELD + ["snap:v3", "snap:v6"]),
    ]
    return sc


def make_tasks(n, seed, pool):
    rnd = random.Random(seed)
    return [(rnd.randrange(1 << 30), rnd.randrange(4),
             [pool[rnd.randrange(len(pool))] for _ in range(3)], rnd.randint(1, 4))
            for _ in range(n)]


def play(cand, task, rules=None):
    map_seed, myseat, opps, token = task
    base = engine.make_map(seed=map_seed)
    bots = []
    k = 0
    for i in range(4):
        if i == myseat:
            bots.append(factory(cand)(map_seed & 0xffff))
        else:
            bots.append(factory(opps[k])(map_seed * 4 + i))
            k += 1
    g = engine.Game(base=base, start_token=token, rules=rules)
    worst = 0.0
    while not g.over():
        vs = g.views()
        acts = []
        for i in range(4):
            t0 = time.perf_counter()
            try:
                a = bots[i](vs[i])
            except Exception:
                a = "STAY"
            if i == myseat:
                dt = time.perf_counter() - t0
                if dt > worst:
                    worst = dt
            if a not in vs[i].legal_actions:
                a = "STAY"
            acts.append(a)
        g.step(acts)
    pl = g.places()
    pw = sum(1.0 for j in range(4) if j != myseat and pl[myseat] < pl[j])
    pw += 0.5 * sum(1 for j in range(4) if j != myseat and pl[myseat] == pl[j])
    return pw, g.score[myseat], 1 if pl[myseat] == 1 else 0, worst


def _job(arg):
    cand, tasks, rules = arg
    out = []
    for t in tasks:
        out.append(play(cand, t, rules))
    return out


def run(cands, n, seed=777, rules=None, which=None, pool=None):
    """Returns {scenario: {cand: (pw, se, score, first%, worst_ms)}}."""
    own_pool = pool is None
    if own_pool:
        pool = multiprocessing.Pool(processes=min(20, multiprocessing.cpu_count()))
    res = {}
    jobs, owner = [], []
    scs = [s for s in scenarios() if which is None or s[0] in which]
    for si, (sname, field) in enumerate(scs):
        tasks = make_tasks(n, seed + 1000 * si, field)
        for c in cands:
            for i in range(0, n, 8):
                jobs.append((c, tasks[i:i + 8], rules))
                owner.append((sname, c))
    out = pool.map(_job, jobs, chunksize=1)
    acc = {}
    for key, rows in zip(owner, out):
        acc.setdefault(key, []).extend(rows)
    for (sname, c), rows in acc.items():
        pws = [r[0] for r in rows]
        m = sum(pws) / len(pws)
        var = sum((x - m) ** 2 for x in pws) / max(1, len(pws) - 1)
        res.setdefault(sname, {})[c] = (
            m, math.sqrt(var / len(pws)), sum(r[1] for r in rows) / len(rows),
            100.0 * sum(r[2] for r in rows) / len(rows), 1000 * max(r[3] for r in rows))
    if own_pool:
        pool.close()
    return res, [s[0] for s in scs]


def report(res, order, cands, labels=None):
    labels = labels or cands
    w = max(12, max(len(x) for x in labels) + 2)
    print("%-22s" % "scenario" + "".join("%*s" % (w + 8, l) for l in labels))
    print("-" * (22 + (w + 8) * len(cands)))
    means = [0.0] * len(cands)
    for sname in order:
        line = "%-22s" % sname
        for k, c in enumerate(cands):
            m, se, sc, fp, wm = res[sname][c]
            means[k] += m
            line += "%*s" % (w + 8, "%.2f +-%.2f %5.0f" % (m, se, sc))
        print(line)
    print("-" * (22 + (w + 8) * len(cands)))
    print("%-22s" % "mean PW" + "".join("%*s" % (w + 8, "%.3f" % (x / len(order)))
                                         for x in means))
    worst = [max(res[s][c][4] for s in order) for c in cands]
    print("%-22s" % "slowest turn (ms)" + "".join("%*s" % (w + 8, "%.0f" % x) for x in worst))


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 120
    cands = sys.argv[2:] or ["bot.py"]
    t0 = time.time()
    res, order = run(cands, n)
    print("%d games per scenario per candidate, %.0fs\n" % (n, time.time() - t0))
    report(res, order, cands)
