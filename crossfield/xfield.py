"""
Cross-branch evaluation field.

Each of the four branches in this repository measured its bot against opponents
written by the same author that wrote the bot, and each branch's headline number
is largest exactly where the field was its own family:

  hardened-field-and-fixes  v7 gains +0.251 on `peer` (six of eleven entrants are
                            its own snapshots) but +0.024 on `strangers`
  v7-independent-field      v7 was *selected* on newfield, then reported on it
  research/evolution        the evolved bot's audit field is dominated by
                            `economic_*` descendants of the evolved bot itself
  visual-harness            no strategy; its referee agrees with engine.py

This module puts every bot from every branch on one field, grouped by author, so
a bot's strength can be read separately against each author's opponents. A bot
that only beats its own author's opponents is overfitted, whatever its headline.

Design, and the bias each choice removes:

  * Opponents come in author groups, sampled group-first so no author dominates
    the field by having written more bots.
  * Every game yields three one-on-one results, so pairwise credit is attributed
    per opponent: "PW vs research" is the share of pairings won against research
    bots, measured inside mixed lineups rather than in three-copy trios.
  * Six map families from both generators (main's centre slope, the research
    branch's balanced / patchy / edge / flat, and the rulebook example).
  * Both legal_actions conventions: the research referee drops moves into
    occupied cells, main's engine and the visual harness keep them.
  * Round 1 scoring: equal scores are half credit. engine.Game.places() breaks
    score ties on cell count, which is the Round 2 rule.
  * Paired tasks: every variant plays the identical (map, seat, lineup, token,
    interface) list, and differences are reported with a paired standard error.
  * File bots get a fresh module namespace per game, like a server that loads
    bot.py once per match, so module-level memory cannot leak between games.
  * Every bot gets its own copy of the board, so a bot that mutates its input
    cannot corrupt another seat's view.

Wall-clock dependence is neutralised for measurement (throttle 0, no deadline)
so results are reproducible; real-time behaviour is tested separately.

    python crossfield/xfield.py <games> ref=<spec> cand=<spec> [...]
    spec:  file:<path>[+key:val,...]   a single-file bot (PARAMS overrides)
           opp:<name>                  any registered opponent
"""
import json
import math
import multiprocessing as mp
import os
import random
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
for _p in (ROOT, HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import engine  # noqa: E402

# ----------------------------------------------------------------- loading bots
_CODE = {}


def _compiled(path):
    c = _CODE.get(path)
    if c is None:
        with open(path, encoding="utf-8-sig") as f:
            c = compile(f.read(), path, "exec")
        _CODE[path] = c
    return c


def file_bot(path, params=None, config=None, attrs=None, policy=None,
             deterministic=True):
    """Factory for a single-file bot: a fresh module namespace per game."""
    if not os.path.isabs(path):
        cand = os.path.join(HERE, path)
        path = cand if os.path.exists(cand) else os.path.join(ROOT, path)

    def make(seed):
        ns = {"__name__": "xfield_bot", "__file__": path}
        exec(_compiled(path), ns)
        if deterministic and isinstance(ns.get("PARAMS"), dict):
            ns["PARAMS"]["throttle"] = 0
            ns["PARAMS"]["budget_ms"] = 1e6
        if deterministic and isinstance(ns.get("SAFETY"), dict):
            ns["SAFETY"]["deterministic"] = True
        if params:
            for k, v in params.items():
                for table in ("FLAGS", "ECON_GENOME", "ROUTE_PARAMS", "PARAMS"):
                    if isinstance(ns.get(table), dict) and k in ns[table]:
                        ns[table][k] = v
                        break
                else:
                    raise KeyError("no FLAGS/ROUTE_PARAMS/PARAMS key %r in %s" % (k, path))
        if config is not None:
            ns["CONFIG"] = dict(config)
        # research/user_family.py ports main's walk planner, wall-clock budget
        # and all, and builds its parameters as DEFAULT_CONFIG + CONFIG: pin both
        # clocks there too, or that opponent varies with machine load
        if (deterministic and isinstance(ns.get("CONFIG"), dict)
                and "budget_ms" in ns.get("DEFAULT_CONFIG", {})):
            ns["CONFIG"]["throttle"] = 0
            ns["CONFIG"]["budget_ms"] = 1e6
        if attrs:
            ns.update(attrs)
        if policy:
            return ns["POLICIES"][policy]
        return ns["act"]
    return make


def _research(name):
    with open(os.path.join(HERE, "research", "configs.json"), encoding="utf-8") as f:
        spec = json.load(f)[name]
    path = os.path.join(HERE, "research", spec["path"])
    if spec.get("config_style") == "dict":
        return file_bot(path, config=spec["config"])
    if "name" in spec:
        return file_bot(path, policy=spec["name"])
    return file_bot(path, attrs=spec.get("config"))


# ----------------------------------------------------------------- the field
SHIPPED = {
    "main_v7": "bots/main_v7.py",            # hardened-field-and-fixes / main
    "indep_v7": "bots/indep_v7.py",          # v7-independent-field
    "evolved": "bots/evolved.py",            # research/evolution (recommended)
    "evolved_tc": "bots/evolved_transfer.py",  # research/evolution (finalist)
}

GROUPS = {
    # hardened-field author: hand-written designs and the independent rival
    "main": ["spine", "camper", "cdraider", "turtle", "hunter", "centre",
             "ai_marginal", "ai_hawk", "ai_homefort", "ai_cheapraid", "ai_route",
             "ai_elo", "ai_centre", "pro", "pro_tuned"],
    # v7-independent-field author
    "indep": ["rate", "route", "vulture", "guard", "grab", "harass", "rollout", "seq"],
    # research/evolution author
    "research": ["fortress", "lure", "macro", "incumbent", "reserved_adversary",
                 "tactical_9d8c8555d2a9", "action_beam_1ea33eef3561",
                 "economic_b9fdc45f4957", "economic_f04298fe614d",
                 "economic_11c655468adf", "user_route_5a9c915442d7"],
    # public code anyone can submit unchanged: every branch's shipped bot
    "shipped": ["main_v7", "indep_v7", "evolved", "evolved_tc", "v6"],
    # a field of twenty-odd teams always contains entries that barely work
    "weak": ["greedy", "greedyshield", "raider", "baiter", "pacifist", "random",
             "stay"],
}
GROUP_WEIGHT = {"main": 1.0, "indep": 1.0, "research": 1.0, "shipped": 1.0,
                "weak": 0.5}
GROUP_OF = dict((n, g) for g, ns in GROUPS.items() for n in ns)

MAP_FAMILIES = (("slope", 0.35), ("balanced", 0.30), ("patchy", 0.15),
                ("edge", 0.10), ("example", 0.05), ("flat", 0.05))


def opponent(name):
    """name -> factory(seed) returning a callable act(view)."""
    if name in SHIPPED:
        return file_bot(SHIPPED[name])
    if name.startswith(("economic_", "tactical_", "action_beam_", "user_route_")) \
            or name in ("fortress", "lure", "macro", "incumbent", "reserved_adversary"):
        return _research(name)
    import newfield
    if name in newfield.NEW_BY_NAME:
        return newfield.NEW_BY_NAME[name]
    import field as fieldmod
    return fieldmod.opponent(name)


_EXAMPLE_Q = ((1, 1, 1, 2), (1, 1, 2, 2), (1, 2, 2, 3), (2, 2, 3, 3))


def research_map(seed, family):
    """The research referee's generator (crossfield/research/arena.py), inlined:
    the repository root already has an unrelated arena.py that would shadow it."""
    rng = random.Random(seed)
    q = []
    for r in range(4):
        row = []
        for c in range(4):
            b = _EXAMPLE_Q[r][c]
            if family == "balanced":
                v = b + rng.choice((-1, 0, 0, 0, 1))
            elif family == "patchy":
                v = rng.randint(1, 3)
            elif family == "flat":
                v = 1 + seed % 3
            elif family == "edge":
                v = 4 - b + rng.choice((-1, 0, 0, 1))
            else:
                raise ValueError("unknown map family %r" % family)
            row.append(min(3, max(1, v)))
        q.append(row)
    return [q[min(r, 7 - r)][min(c, 7 - c)] for r in range(8) for c in range(8)]


def make_map(family, seed):
    if family == "slope":
        return engine.make_map(seed=seed)
    if family == "example":
        return engine.make_map(canonical=True)
    return research_map(seed, family)


def make_tasks(n, seed=1, groups=None):
    """Identical task list for every variant. groups restricts the field."""
    rnd = random.Random(seed)
    gw = [(g, GROUP_WEIGHT[g]) for g in (groups or sorted(GROUPS))]
    tot_g = sum(w for _, w in gw)
    tot_m = sum(w for _, w in MAP_FAMILIES)
    out = []
    for _ in range(n):
        x = rnd.random() * tot_m
        fam = MAP_FAMILIES[-1][0]
        for f, w in MAP_FAMILIES:
            if x < w:
                fam = f
                break
            x -= w
        opps = []
        for _k in range(3):
            y = rnd.random() * tot_g
            grp = gw[-1][0]
            for g, w in gw:
                if y < w:
                    grp = g
                    break
                y -= w
            opps.append(GROUPS[grp][rnd.randrange(len(GROUPS[grp]))])
        out.append({"family": fam, "map_seed": rnd.randrange(1 << 30),
                    "seat": rnd.randrange(4), "opps": opps,
                    "token": rnd.randint(1, 4), "excl": rnd.random() < 0.5})
    return out


# ----------------------------------------------------------------- one game
def _views(g, excl):
    occ = set(g.pos)
    out = []
    for i in range(4):
        legal = g.legal(i)
        if excl:
            legal = [a for a in legal
                     if a not in engine.MOVES or g.pos[i] + engine.MOVES[a] not in occ]
        out.append(engine.View(g.board_view(), i + 1, g.token == i + 1, legal))
    return out


def play(focus_factory, task, opp_cache=None):
    """Returns per-game record for the focus seat."""
    base = make_map(task["family"], task["map_seed"])
    me = task["seat"]
    bots = []
    names = []
    k = 0
    for i in range(4):
        if i == me:
            bots.append(focus_factory(task["map_seed"] & 0xffff))
            names.append("*")
        else:
            nm = task["opps"][k]
            k += 1
            fac = opp_cache.get(nm) if opp_cache is not None else None
            if fac is None:
                fac = opponent(nm)
                if opp_cache is not None:
                    opp_cache[nm] = fac
            bots.append(fac(task["map_seed"] * 4 + i))
            names.append(nm)
    g = engine.Game(base=base, start_token=task["token"])
    worst_ms = 0.0
    errors = 0
    while not g.over():
        vs = _views(g, task["excl"])
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
                if dt > worst_ms:
                    worst_ms = dt
            if a not in vs[i].legal_actions:
                if i == me and a is not None:
                    errors += 1
                a = "STAY"
            acts.append(a)
        g.step(acts)
    sc = g.score
    res = []                                 # (opponent name, 1 / 0.5 / 0)
    for i in range(4):
        if i == me:
            continue
        r = 1.0 if sc[me] > sc[i] else (0.5 if sc[me] == sc[i] else 0.0)
        res.append((names[i], r))
    return {"pw": sum(r for _, r in res), "score": sc[me], "pairs": res,
            "ms": worst_ms, "err": errors}


# ----------------------------------------------------------------- batches
_SPECS = {}


def resolve(spec):
    """'file:path[+k:v,...]' or 'opp:name' -> factory."""
    kind, _, rest = spec.partition(":")
    if kind == "opp":
        return opponent(rest)
    if kind == "file":
        path, _, ov = rest.partition("+")
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
        return file_bot(path, params=params or None)
    raise ValueError("bad spec %r" % spec)


def _worker(arg):
    os.chdir(ROOT)                    # field.opponent reads pro_params_v1.json
    spec, tasks = arg
    fac = _SPECS.get(spec)
    if fac is None:
        fac = resolve(spec)
        _SPECS[spec] = fac
    cache = {}
    return [play(fac, t, cache) for t in tasks]


def run(specs, tasks, procs=None, chunk=6):
    """specs: [(label, spec)] -> label -> list of per-task records."""
    jobs, owner = [], []
    for vi, (_lab, spec) in enumerate(specs):
        for i in range(0, len(tasks), chunk):
            jobs.append((spec, tasks[i:i + chunk]))
            owner.append(vi)
    pool = mp.Pool(procs or max(1, mp.cpu_count()))
    try:
        res = pool.map(_worker, jobs, chunksize=1)
    finally:
        pool.close()
        pool.join()
    out = [[] for _ in specs]
    for o, r in zip(owner, res):
        out[o].extend(r)
    return dict((specs[i][0], out[i]) for i in range(len(specs)))


def _mean_se(xs):
    n = len(xs)
    if n == 0:
        return 0.0, 0.0
    m = sum(xs) / n
    if n < 2:
        return m, float("inf")
    v = sum((x - m) ** 2 for x in xs) / (n - 1)
    return m, math.sqrt(v / n)


def by_group(records):
    """Pairwise credit (0..1) against each author group, from per-opponent results."""
    acc = {}
    for r in records:
        for nm, x in r["pairs"]:
            g = GROUP_OF.get(nm, "?")
            acc.setdefault(g, []).append(x)
    return dict((g, (sum(v) / len(v), len(v))) for g, v in acc.items())


def report(specs, res, tasks, out=sys.stdout):
    labels = [lab for lab, _ in specs]
    ref = labels[0]
    a = res[ref]
    n = len(a)
    w = out.write
    w("\n%d paired games, reference = %s\n" % (n, ref))
    w("%-14s %7s %7s %6s %7s %7s  %9s %7s %6s\n"
      % ("variant", "PW/3", "credit", "score", "max_ms", "errors", "dPW", "SE", "z"))
    w("-" * 84 + "\n")
    for lab in labels:
        b = res[lab]
        pw = sum(x["pw"] for x in b) / n
        sc = sum(x["score"] for x in b) / n
        ms = max(x["ms"] for x in b)
        er = sum(x["err"] for x in b)
        if lab == ref:
            w("%-14s %7.3f %6.1f%% %6.0f %7.1f %7d   (reference)\n"
              % (lab, pw, 100 * pw / 3, sc, ms, er))
            continue
        d = [b[i]["pw"] - a[i]["pw"] for i in range(n)]
        md, se = _mean_se(d)
        z = md / se if se > 0 else 0.0
        mark = "  **" if abs(z) >= 2.58 else ("  *" if abs(z) >= 1.96 else "")
        w("%-14s %7.3f %6.1f%% %6.0f %7.1f %7d  %+9.4f %7.4f %+6.2f%s\n"
          % (lab, pw, 100 * pw / 3, sc, ms, er, md, se, z, mark))
    # credit against each author's bots, and by map family / interface
    groups = sorted(GROUPS)
    w("\npairwise credit vs each author group (share of one-on-one pairings won)\n")
    w("%-14s" % "variant" + "".join("%10s" % g for g in groups) + "%10s\n" % "worst")
    for lab in labels:
        bg = by_group(res[lab])
        vals = [bg.get(g, (float("nan"), 0))[0] for g in groups]
        real = [v for v in vals if v == v]
        w("%-14s" % lab + "".join("%9.1f%%" % (100 * v) for v in vals)
          + "%9.1f%%\n" % (100 * min(real) if real else float("nan")))
    w("\nPW/3 by seat (the map is four-fold mirrored, so a gap is the bot's own asymmetry)\n")
    w("%-14s" % "variant" + "".join("%9s" % ("seat %d" % (s + 1)) for s in range(4)) + "\n")
    for lab in labels:
        b = res[lab]
        row = []
        for s in range(4):
            idx = [i for i, t in enumerate(tasks) if t["seat"] == s]
            row.append(sum(b[i]["pw"] for i in idx) / max(1, len(idx)))
        w("%-14s" % lab + "".join("%9.3f" % v for v in row) + "\n")
    fams = sorted(set(t["family"] for t in tasks))
    w("\nPW/3 by map family and interface\n")
    cols = fams + ["incl", "excl"]
    w("%-14s" % "variant" + "".join("%9s" % c for c in cols) + "\n")
    for lab in labels:
        b = res[lab]
        row = []
        for c in cols:
            if c in ("incl", "excl"):
                idx = [i for i, t in enumerate(tasks) if t["excl"] == (c == "excl")]
            else:
                idx = [i for i, t in enumerate(tasks) if t["family"] == c]
            row.append(sum(b[i]["pw"] for i in idx) / max(1, len(idx)))
        w("%-14s" % lab + "".join("%9.3f" % v for v in row) + "\n")


def main(argv):
    if len(argv) < 3:
        raise SystemExit(__doc__)
    games = int(argv[1])
    seed = 1
    groups = None
    out = None
    specs = []
    for a in argv[2:]:
        if a.startswith("--out="):
            out = a.split("=", 1)[1]
        elif a.startswith("--seed="):
            seed = int(a.split("=", 1)[1])
        elif a.startswith("--groups="):
            groups = a.split("=", 1)[1].split(",")
        else:
            lab, _, spec = a.partition("=")
            specs.append((lab, spec))
    tasks = make_tasks(games, seed=seed, groups=groups)
    t0 = time.time()
    res = run(specs, tasks)
    report(specs, res, tasks)
    if out:
        with open(out, "w", encoding="utf-8") as f:
            json.dump({"specs": specs, "tasks": tasks, "results": res}, f)
    print("\n%.0f s" % (time.time() - t0))
    return res


if __name__ == "__main__":
    main(sys.argv)
