"""Lab arena: field / head-to-head / trio measurement, paired across variants.

    python zarena.py <games> <mode> [--seed=N] label=spec ...
    mode: field  focus + 3 opponents sampled group-first from the whole field
          h2h    focus + evolved + 2 field opponents (seats shuffled)
          trio   focus + 3 evolved copies
          mix    half h2h, half field
    spec: file:<path>[+k:v,...] | opp:<name>
"""
import glob
import json
import math
import multiprocessing as mp
import os
import random
import sys
import time

LAB = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(LAB, "crossfield"))
sys.path.insert(0, LAB)
import engine  # noqa
import xfield  # noqa

OPP_DIR = os.path.join(LAB, "opponents")
OPP_FILES = sorted(os.path.basename(p)[:-3] for p in glob.glob(os.path.join(OPP_DIR, "opp_*.py")))
# opp_buggy_02 sleeps 150 ms per turn on purpose; the referee would play it as a
# legal-but-slow bot. Simulate it without the sleep (same decisions).
GROUPS = dict(xfield.GROUPS)
GROUPS["opp_orig"] = [n for n in OPP_FILES if not ("gpt" in n or "gemini" in n)]
GROUPS["opp_llm"] = [n for n in OPP_FILES if ("gpt" in n or "gemini" in n)]
GROUPS["shipped"] = ["main_v7", "indep_v7", "evolved", "evolved_tc", "v6", "fused"]
GROUP_WEIGHT = {"main": 1.0, "indep": 1.0, "research": 1.0, "shipped": 1.0,
                "weak": 0.5, "opp_orig": 1.0, "opp_llm": 1.0}
GROUP_OF = dict((n, g) for g, ns in GROUPS.items() for n in ns)
EVOLVED = "evolved"


class _NoSleep(object):
    def __getattr__(self, k):
        import time as _t
        return getattr(_t, k)

    def sleep(self, s):
        return None


def opponent(name):
    if name in GROUPS["opp_orig"] or name in GROUPS["opp_llm"]:
        path = os.path.join(OPP_DIR, name + ".py")
        base = xfield.file_bot(path)
        if name == "opp_buggy_02":
            code = xfield._compiled(path)

            def make(seed):
                ns = {"__name__": "opp", "__file__": path}
                exec(code, ns)
                ns["time"] = _NoSleep()
                return ns["act"]
            return make
        return base
    if name == "fused":
        return xfield.file_bot(os.path.join(LAB, "bot.py"))
    return xfield.opponent(name)


def _pick(rnd, groups):
    gw = [(g, GROUP_WEIGHT[g]) for g in groups]
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
    rnd = random.Random(seed * 7919 + hash(mode) % 1000)
    groups = groups or sorted(GROUP_WEIGHT)
    out = []
    for k in range(n):
        m = mode
        if mode == "mix":
            m = "h2h" if k % 2 == 0 else "field"
        fam = _family(rnd)
        if m == "field":
            others = [_pick(rnd, groups) for _ in range(3)]
        elif m == "h2h":
            others = [EVOLVED, _pick(rnd, groups), _pick(rnd, groups)]
        elif m == "trio":
            others = [EVOLVED] * 3
        elif m == "duo":
            others = [EVOLVED, EVOLVED, _pick(rnd, groups)]
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


def play(focus_factory, task, cache):
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
        g.step(acts)
    sc = g.score
    pairs = []
    for i in range(4):
        if i != me:
            r = 1.0 if sc[me] > sc[i] else (0.5 if sc[me] == sc[i] else 0.0)
            pairs.append((names[i], r))
    return {"pw": sum(r for _, r in pairs), "score": sc[me], "pairs": pairs, "ms": worst,
            "avg_ms": tot_ms / 80.0, "err": errors, "scores": list(sc), "me": me}


_SPECS = {}


def resolve(spec):
    kind, _, rest = spec.partition(":")
    if kind == "opp":
        return opponent(rest)
    return xfield.resolve(spec)


def _worker(arg):
    os.chdir(LAB)
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


def mean_se(xs):
    n = len(xs)
    if n == 0:
        return float("nan"), float("nan")
    m = sum(xs) / n
    if n < 2:
        return m, float("inf")
    v = sum((x - m) ** 2 for x in xs) / (n - 1)
    return m, math.sqrt(v / n)


def h2h_vs(records, name=EVOLVED):
    """Mean pairwise credit against every seat played by `name`, per game."""
    vals = []
    for r in records:
        xs = [x for nm, x in r["pairs"] if nm == name]
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
        "vsEvo", "SE"))
    a = res[ref]
    for lab in labels:
        b = res[lab]
        pw = sum(x["pw"] for x in b) / n
        sc = sum(x["score"] for x in b) / n
        ms = max(x["ms"] for x in b)
        am = sum(x["avg_ms"] for x in b) / n
        er = sum(x["err"] for x in b)
        hv, hse = mean_se(h2h_vs(b))
        if lab == ref:
            w("%-12s %6.3f %5.1f%% %6.0f %7.1f %6.2f %4d %9s %7s %6s %7.1f%% %5.1f\n" % (
                lab, pw, 100 * pw / 3, sc, ms, am, er, "(ref)", "", "", 100 * hv, 100 * hse))
            continue
        d = [b[i]["pw"] - a[i]["pw"] for i in range(n)]
        md, se = mean_se(d)
        z = md / se if se > 0 else 0.0
        mark = " **" if abs(z) >= 2.58 else (" *" if abs(z) >= 1.96 else "")
        w("%-12s %6.3f %5.1f%% %6.0f %7.1f %6.2f %4d %+9.4f %7.4f %+6.2f %7.1f%% %5.1f%s\n" % (
            lab, pw, 100 * pw / 3, sc, ms, am, er, md, se, z, 100 * hv, 100 * hse, mark))
    groups = sorted(GROUP_WEIGHT)
    w("\ncredit vs each group\n%-12s" % "variant" + "".join("%9s" % g[:9] for g in groups) + "\n")
    for lab in labels:
        acc = {}
        for r in res[lab]:
            for nm, x in r["pairs"]:
                acc.setdefault(GROUP_OF.get(nm, "?"), []).append(x)
        w("%-12s" % lab + "".join(
            ("%8.1f%%" % (100 * sum(acc[g]) / len(acc[g]))) if g in acc else "%9s" % "-"
            for g in groups) + "\n")


def per_opponent(specs, res, out=sys.stdout, top=14):
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
        out.write("  %-26s %5.1f%%  (%s %5.1f%%)  n=%d\n" % (nm, 100 * v, labels[0], 100 * sum(ref) / len(ref), n))


def main(argv):
    games = int(argv[1])
    mode = argv[2]
    seed, groups, out, specs = 1, None, None, []
    for a in argv[3:]:
        if a.startswith("--seed="):
            seed = int(a.split("=", 1)[1])
        elif a.startswith("--groups="):
            groups = a.split("=", 1)[1].split(",")
        elif a.startswith("--out="):
            out = a.split("=", 1)[1]
        elif a == "--per":
            pass
        else:
            lab, _, spec = a.partition("=")
            specs.append((lab, spec))
    tasks = make_tasks(games, mode, seed=seed, groups=groups)
    t0 = time.time()
    res = run(specs, tasks)
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
