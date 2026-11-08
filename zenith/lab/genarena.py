"""Generations arena: any bot against any line-up, paired across variants.

    python zenith/lab/genarena.py <games> <mode> [--seed=N] [--procs=N] [--out=F] label=spec ...

The first label is the reference; every variant plays the identical task list
(map, seats, line-up, token, legal_actions convention, RNG seed), so differences
come with a paired standard error.

modes
    gens          focus + 3 bots drawn from the previous generations
    field         focus + 3 drawn group-first from the whole field (every author
                  group, the previous generations and the human-like exploiters)
    humans        focus + 3 drawn from the human-like exploiters (zenith/lab/humanlike)
    trio:NAME     focus + 3 copies of NAME
    duo:NAME      focus + 2 copies of NAME + 1 from the field
    h2h:NAME      focus + 1 NAME + 2 from the field
    mix           a quarter each of gens, field, humans and trio:<random gen>

spec
    gen:NAME                one of GENS below
    opp:NAME                any registered opponent (xfield, opponents/, humanlike)
    file:PATH[+k:v,...]     a single-file bot, optionally with FLAGS/PARAMS overrides
"""
import glob
import json
import math
import multiprocessing as mp
import os
import random
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
for _p in (ROOT, os.path.join(ROOT, "crossfield"), HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import engine  # noqa: E402
import xfield  # noqa: E402

# Every generation this repository has shipped or built, oldest first.
GENS = {
    "v6": "xf:v6",                          # walk planner, first tuned ship
    "v7": "xf:main_v7",                     # main's v7 walk planner
    "indep_v7": "xf:indep_v7",              # the independent branch's v7
    "evolved": "xf:evolved",                # research/evolution economic planner
    "fused": "file:bot.py",                  # the shipped bot.py (evolved + failsafes)
    "apex": "file:apex/apex_bot.py",         # Apex: predicts the evolved planner
    "zenith": "file:zenith/zenith_bot.py",   # this generation
}
PREVIOUS = ["v7", "indep_v7", "evolved", "fused", "apex"]

OPP_DIR = os.path.join(ROOT, "opponents")
SOFT_TAU = 60.0          # soft pairwise wins: the grader's smoothing of the score margin
HUMAN_DIR = os.path.join(HERE, "humanlike")


def _names(d, prefix):
    return sorted(os.path.basename(p)[:-3] for p in glob.glob(os.path.join(d, prefix + "*.py")))


OPP_FILES = _names(OPP_DIR, "opp_")
HUMAN_FILES = _names(HUMAN_DIR, "hx_")

GROUPS = dict(xfield.GROUPS)
GROUPS["shipped"] = [n for n in GROUPS["shipped"] if n not in ("main_v7", "indep_v7", "evolved")]
GROUPS["opp_orig"] = list(OPP_FILES)
GROUPS["gens"] = list(PREVIOUS)
GROUPS["human"] = list(HUMAN_FILES)
GROUP_WEIGHT = {"main": 1.0, "indep": 1.0, "research": 1.0, "shipped": 0.5, "weak": 0.5,
                "opp_orig": 1.0, "gens": 1.5, "human": 1.5}
GROUP_OF = {}
for _g, _ns in GROUPS.items():
    for _n in _ns:
        GROUP_OF.setdefault(_n, _g)


class _NoSleep(object):
    def __getattr__(self, k):
        return getattr(time, k)

    def sleep(self, s):
        return None


def opponent(name):
    """name -> factory(seed) -> act(view)."""
    if name in GENS:
        return resolve(GENS[name])
    if name in OPP_FILES:
        path = os.path.join(OPP_DIR, name + ".py")
        if name == "opp_buggy_02":           # sleeps on purpose; same decisions without it
            code = xfield._compiled(path)

            def make(seed):
                ns = {"__name__": "opp", "__file__": path}
                exec(code, ns)
                ns["time"] = _NoSleep()
                return ns["act"]
            return make
        return xfield.file_bot(path)
    if name in HUMAN_FILES:
        return xfield.file_bot(os.path.join(HUMAN_DIR, name + ".py"))
    return xfield.opponent(name)


def resolve(spec):
    kind, _, rest = spec.partition(":")
    if kind == "gen":
        return resolve(GENS[rest])
    if kind == "opp":
        return opponent(rest)
    if kind == "xf":
        return xfield.opponent(rest)
    if kind == "file":
        path, _, ov = rest.partition("+")
        if not os.path.isabs(path):
            path = os.path.join(ROOT, path)
        params = {}
        for kv in ov.split(","):
            if not kv:
                continue
            k, _, v = kv.partition(":")
            try:
                params[k] = int(v)
            except ValueError:
                try:
                    params[k] = float(v)
                except ValueError:
                    params[k] = v
        return xfield.file_bot(path, params=params or None)
    raise ValueError("bad spec %r" % spec)


# ---------------------------------------------------------------- tasks
def _pick(rnd, groups):
    gw = [(g, GROUP_WEIGHT[g]) for g in groups if GROUPS.get(g)]
    tot = sum(w for _, w in gw)
    y = rnd.random() * tot
    grp = gw[-1][0]
    for g, w in gw:
        if y < w:
            grp = g
            break
        y -= w
    return GROUPS[grp][rnd.randrange(len(GROUPS[grp]))]


def _family(rnd):
    tot = sum(w for _, w in xfield.MAP_FAMILIES)
    x = rnd.random() * tot
    for f, w in xfield.MAP_FAMILIES:
        if x < w:
            return f
        x -= w
    return xfield.MAP_FAMILIES[-1][0]


def make_tasks(n, mode, seed=1, groups=None):
    rnd = random.Random(seed * 7919 + sum(map(ord, mode)))
    groups = groups or sorted(GROUP_WEIGHT)
    out = []
    for k in range(n):
        m = mode
        if mode == "mix":
            m = ("gens", "field", "humans", "trio:" + PREVIOUS[k // 4 % len(PREVIOUS)])[k % 4]
        kind, _, arg = m.partition(":")
        fam = _family(rnd)
        if kind == "field":
            others = [_pick(rnd, groups) for _ in range(3)]
        elif kind == "gens":
            others = [PREVIOUS[rnd.randrange(len(PREVIOUS))] for _ in range(3)]
        elif kind == "humans":
            others = [HUMAN_FILES[rnd.randrange(len(HUMAN_FILES))] for _ in range(3)]
        elif kind == "trio":
            others = [arg] * 3
        elif kind == "duo":
            others = [arg, arg, _pick(rnd, groups)]
        elif kind == "h2h":
            others = [arg, _pick(rnd, groups), _pick(rnd, groups)]
        else:
            raise ValueError(m)
        seats = list(range(4))
        rnd.shuffle(seats)
        lineup = [None] * 4
        lineup[seats[0]] = "*"
        for i, nm in enumerate(others):
            lineup[seats[i + 1]] = nm
        out.append({"family": fam, "map_seed": rnd.randrange(1 << 30), "lineup": lineup,
                    "token": rnd.randint(1, 4), "excl": rnd.random() < 0.5, "mode": m,
                    "rseed": rnd.randrange(1 << 30)})
    return out


# ---------------------------------------------------------------- one game
def play(focus_factory, task, cache, record=False):
    base = xfield.make_map(task["family"], task["map_seed"])
    random.seed(task["rseed"])
    bots, names = [], []
    me = task["lineup"].index("*")
    for i, nm in enumerate(task["lineup"]):
        if nm == "*":
            bots.append(focus_factory(task["map_seed"] & 0xffff))
        else:
            fac = cache.get(nm)
            if fac is None:
                fac = opponent(nm)
                cache[nm] = fac
            bots.append(fac(task["map_seed"] * 4 + i))
        names.append(nm)
    g = engine.Game(base=base, start_token=task["token"])
    worst, errors, tot_ms = 0.0, 0, 0.0
    hist = []
    while not g.over():
        vs = xfield._views(g, task["excl"])
        acts = []
        for i in range(4):
            t0 = time.perf_counter()
            try:
                a = bots[i](vs[i])
            except Exception:
                a = None
                if i == me:
                    errors += 1
            if i == me:
                dt = (time.perf_counter() - t0) * 1000.0
                tot_ms += dt
                worst = max(worst, dt)
            if a not in vs[i].legal_actions:
                if i == me and a is not None:
                    errors += 1
                a = "STAY"
            acts.append(a)
        if record:
            hist.append(list(acts))
        g.step(acts)
    sc = g.score
    pairs = []
    for i in range(4):
        if i != me:
            r = 1.0 if sc[me] > sc[i] else (0.5 if sc[me] == sc[i] else 0.0)
            pairs.append((names[i], r))
    soft = sum(1.0 / (1.0 + math.exp(-max(-60.0, min(60.0, (sc[me] - sc[i]) / SOFT_TAU))))
               for i in range(4) if i != me)
    out = {"pw": sum(r for _, r in pairs), "soft": soft, "score": sc[me], "pairs": pairs, "ms": worst,
           "avg_ms": tot_ms / 80.0, "err": errors, "scores": list(sc), "me": me}
    if record:
        out["actions"] = hist
    return out


_SPECS = {}


def _worker(arg):
    os.chdir(ROOT)
    spec, tasks = arg
    fac = _SPECS.get(spec)
    if fac is None:
        fac = resolve(spec)
        _SPECS[spec] = fac
    cache = {}
    return [play(fac, t, cache) for t in tasks]


def run(specs, tasks, procs=None, chunk=4):
    jobs, owner = [], []
    for vi, (_lab, spec) in enumerate(specs):
        for i in range(0, len(tasks), chunk):
            jobs.append((spec, tasks[i:i + chunk]))
            owner.append((vi, i))
    pool = mp.Pool(procs or mp.cpu_count())
    try:
        res = pool.map(_worker, jobs, chunksize=1)
    finally:
        pool.close()
        pool.join()
    out = [[None] * len(tasks) for _ in specs]
    for (vi, i), r in zip(owner, res):
        for k, x in enumerate(r):
            out[vi][i + k] = x
    return dict((specs[i][0], out[i]) for i in range(len(specs)))


# ---------------------------------------------------------------- report
def mean_se(xs):
    n = len(xs)
    if n == 0:
        return float("nan"), float("nan")
    m = sum(xs) / n
    if n < 2:
        return m, float("inf")
    v = sum((x - m) ** 2 for x in xs) / (n - 1)
    return m, math.sqrt(v / n)


def credit_vs(records, names):
    """Per-game mean credit against every seat played by any of `names`."""
    vals = []
    for r in records:
        xs = [x for nm, x in r["pairs"] if nm in names]
        if xs:
            vals.append(sum(xs) / len(xs))
    return vals


def report(specs, res, tasks, out=sys.stdout):
    labels = [lab for lab, _ in specs]
    ref = labels[0]
    n = len(tasks)
    w = out.write
    w("\n%d paired games, reference = %s\n" % (n, ref))
    w("%-12s %6s %6s %6s %7s %6s %4s %9s %7s %6s %8s %6s\n" % (
        "variant", "PW/3", "credit", "score", "max_ms", "avg_ms", "err", "dPW", "SE", "z",
        "dsoft", "z"))
    a = res[ref]
    for lab in labels:
        b = res[lab]
        pw = sum(x["pw"] for x in b) / n
        sc = sum(x["score"] for x in b) / n
        ms = max(x["ms"] for x in b)
        am = sum(x["avg_ms"] for x in b) / n
        er = sum(x["err"] for x in b)
        if lab == ref:
            w("%-12s %6.3f %5.1f%% %6.0f %7.1f %6.2f %4d %9s\n" % (
                lab, pw, 100 * pw / 3, sc, ms, am, er, "(ref)"))
            continue
        d = [b[i]["pw"] - a[i]["pw"] for i in range(n)]
        md, se = mean_se(d)
        z = md / se if se > 0 else 0.0
        ds = [b[i].get("soft", 0) - a[i].get("soft", 0) for i in range(n)]
        mds, ses = mean_se(ds)
        zs = mds / ses if ses > 0 else 0.0
        mark = " **" if abs(z) >= 2.58 else (" *" if abs(z) >= 1.96 else "")
        w("%-12s %6.3f %5.1f%% %6.0f %7.1f %6.2f %4d %+9.4f %7.4f %+6.2f %+8.4f %+6.2f%s\n" % (
            lab, pw, 100 * pw / 3, sc, ms, am, er, md, se, z, mds, zs, mark))
    seen = set(nm for r in a for nm, _ in r["pairs"])
    gens = [g for g in PREVIOUS + ["zenith"] if g in seen]
    if gens:
        w("\nhead-to-head credit vs each generation (share of one-on-one pairings won)\n")
        w("%-12s" % "variant" + "".join("%10s" % g for g in gens) + "\n")
        for lab in labels:
            row = []
            for g in gens:
                m, se = mean_se(credit_vs(res[lab], [g]))
                row.append("%5.1f%%±%-3.0f" % (100 * m, 100 * se) if m == m else "%10s" % "-")
            w("%-12s" % lab + "".join("%10s" % x for x in row) + "\n")
    groups = sorted(set(GROUP_OF.get(nm, "?") for nm in seen))
    w("\ncredit vs each group\n%-12s" % "variant" + "".join("%9s" % g[:9] for g in groups) + "\n")
    for lab in labels:
        acc = {}
        for r in res[lab]:
            for nm, x in r["pairs"]:
                acc.setdefault(GROUP_OF.get(nm, "?"), []).append(x)
        w("%-12s" % lab + "".join(
            ("%8.1f%%" % (100 * sum(acc[g]) / len(acc[g]))) if g in acc else "%9s" % "-"
            for g in groups) + "\n")


def per_opponent(specs, res, out=sys.stdout, top=16):
    labels = [lab for lab, _ in specs]
    acc = {}
    for lab in labels:
        for r in res[lab]:
            for nm, x in r["pairs"]:
                acc.setdefault(nm, {}).setdefault(lab, []).append(x)
    rows = []
    for nm, d in acc.items():
        n = len(d[labels[-1]])
        rows.append((sum(d[labels[-1]]) / n, nm, n))
    rows.sort()
    out.write("\nweakest pairings for %s (credit, n) vs %s\n" % (labels[-1], labels[0]))
    for v, nm, n in rows[:top]:
        ref = acc[nm][labels[0]]
        out.write("  %-26s %5.1f%%  (%s %5.1f%%)  n=%d\n" % (
            nm, 100 * v, labels[0], 100 * sum(ref) / len(ref), n))


def main(argv):
    games = int(argv[1])
    mode = argv[2]
    seed, groups, out, specs, procs = 1, None, None, [], None
    for a in argv[3:]:
        if a.startswith("--seed="):
            seed = int(a.split("=", 1)[1])
        elif a.startswith("--groups="):
            groups = a.split("=", 1)[1].split(",")
        elif a.startswith("--out="):
            out = a.split("=", 1)[1]
        elif a.startswith("--procs="):
            procs = int(a.split("=", 1)[1])
        elif a == "--per":
            pass
        else:
            lab, _, spec = a.partition("=")
            specs.append((lab, spec))
    tasks = make_tasks(games, mode, seed=seed, groups=groups)
    t0 = time.time()
    res = run(specs, tasks, procs=procs)
    report(specs, res, tasks)
    if "--per" in argv:
        per_opponent(specs, res)
    if out:
        with open(out, "w") as f:
            json.dump({"specs": specs, "tasks": tasks, "res": res}, f)
    print("\n%.0f s" % (time.time() - t0))
    return res


if __name__ == "__main__":
    main(sys.argv)
