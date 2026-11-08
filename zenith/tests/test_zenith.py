"""Acceptance tests for zenith/zenith_bot.py. Self-contained: needs only this branch.

    python zenith/tests/test_zenith.py          # everything (a few minutes)
    python zenith/tests/test_zenith.py quick    # skip the slow timing section

Sections
  A  the in-bot rules engine (used for rollouts) against engine.py, state by state
  B  the in-bot simulator of the evolved planner against the evolved bot itself,
     move for move, for all four genomes in the bank
  C  the tracker against the engine's hidden state
  D  eleven server-interface variants, and a module reloaded every turn
  E  module reuse: four seats in one module, several games in one process
  F  the safety net: the main agent forced to raise every turn
  G  wall-clock timing with every expensive mode active
  H  static checks: stdlib-only imports, act(state), ASCII, no print/open/exec
  I  the Apex simulator inside Zenith against apex/apex_bot.py, move for move,
     turns 1-60 (Apex's endgame search reads the clock, so prediction stops there)
"""
import ast
import collections
import os
import random
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ZEN = os.path.dirname(HERE)
ROOT = os.path.dirname(ZEN)
sys.path.insert(0, ROOT)

import engine  # noqa: E402

BOT = os.path.join(ZEN, "zenith_bot.py")
FIXTURE = os.path.join(ROOT, "apex", "tests", "fixtures", "evolved_bot.py")
_CODE = {}
FAILS = []


def load(path, extra=None):
    code = _CODE.get(path)
    if code is None:
        with open(path, encoding="utf-8") as f:
            code = compile(f.read(), path, "exec")
        _CODE[path] = code
    ns = {"__name__": "bot_under_test"}
    exec(code, ns)
    if extra:
        ns.update(extra)
    return ns


def check(name, ok, detail=""):
    print("  %-62s %s %s" % (name, "ok" if ok else "FAIL", detail))
    if not ok:
        FAILS.append(name)


def opponent(name, seed=0):
    """A fresh opponent callable: the evolved fixture or one of field.py's bots."""
    if name.startswith("evolved"):
        cfg = None
        if name != "evolved":
            ns0 = load(BOT)
            cfg = dict(ns0["EVO_GENOMES"][int(name[-1])])
        ns = load(FIXTURE)
        if cfg is not None:
            ns["CONFIG"] = cfg
        return ns["act"]
    import field
    return field.opponent(name)(seed)


def play(bots, base, token=1, excl=False, rules=None, hook=None):
    g = engine.Game(base=base, start_token=token, rules=rules)
    while not g.over():
        vs = g.views()
        acts = []
        for i in range(4):
            v = vs[i]
            if excl:
                occ = set(g.pos)
                legal = [a for a in v.legal_actions
                         if a not in engine.MOVES or g.pos[i] + engine.MOVES[a] not in occ]
                v = engine.View(v.board, v.bot_id, v.is_priority_token, legal)
            try:
                a = bots[i](v)
            except Exception:
                a = "STAY"
            if a not in v.legal_actions:
                a = "STAY"
            acts.append(a)
        if hook:
            hook(g, vs, acts)
        g.step(acts)
    return g


# --------------------------------------------------------------------------- A
def section_a(games=300):
    print("A  in-bot rules engine vs engine.py")
    ns = load(BOT)
    SimState, sim_step, sim_legal = ns["SimState"], ns["sim_step"], ns["sim_legal"]
    rnd = random.Random(1)
    bad = 0
    for gi in range(games):
        base = engine.make_map(seed=rnd.randrange(1 << 20))
        g = engine.Game(base=base, start_token=rnd.randint(1, 4))
        st = SimState()
        st.base = list(base)
        st.home = [0] * 64
        for s, c in engine.CORNERS.items():
            st.home[c] = s
        st.owner, st.up = list(g.owner), [0] * 64
        st.pos = [0] + list(g.pos)
        st.fl, st.cd, st.prog, st.score = [0] * 5, [0] * 5, [0] * 5, [0] * 5
        st.turn, st.token, st.resets = 1, g.token, True
        while not g.over():
            acts = [rnd.choices(engine.ACTIONS, weights=(1, 1, 1, 1, 4, 0.4))[0] for _ in range(4)]
            if sorted(sim_legal(st, 1)) != sorted(g.legal(0)):
                bad += 1
                break
            g.step(acts)
            sim_step(st, [None] + acts)
            if (st.owner != g.owner or st.up != g.upg or st.pos[1:] != g.pos or st.fl[1:] != g.frozen
                    or st.cd[1:] != g.cd or st.prog[1:] != g.prog or st.score[1:] != g.score
                    or st.token != g.token):
                bad += 1
                break
    check("%d random games with shields, state identical every turn" % games, bad == 0,
          "(%d diverged)" % bad)


# --------------------------------------------------------------------------- B
def section_b(games=40):
    print("B  simulator bank vs the evolved bot itself (move for move)")
    ns = load(BOT)
    EvoSim, GEN = ns["EvoSim"], ns["EVO_GENOMES"]
    rnd = random.Random(5)
    pool = ["spine", "raider", "camper", "greedyshield", "baiter", "ai_cheapraid", "ai_hawk", "random"]
    for k in range(len(GEN)):
        name = "evolved" if k == 0 else "evolved%d" % k
        turns = mism = 0
        for gi in range(games):
            names = [rnd.choice([name, name] + pool) for _ in range(4)]
            names[rnd.randrange(4)] = name
            bots = [opponent(n, gi * 4 + i) for i, n in enumerate(names)]
            sims = [EvoSim(GEN[k]) if n == name else None for n in names]
            counts = [0, 0]

            def hook(g, vs, acts, sims=sims, counts=counts):
                for i in range(4):
                    if sims[i] is None:
                        continue
                    cells = [c for row in vs[i].board for c in row]
                    b = sims[i].act(cells, i + 1, list(vs[i].legal_actions), vs[i].is_priority_token)
                    counts[0] += 1
                    counts[1] += b != acts[i]
            random.seed(gi)
            play(bots, engine.make_map(seed=rnd.randrange(1 << 20)), token=rnd.randint(1, 4),
                 excl=rnd.random() < 0.5, hook=hook)
            turns += counts[0]
            mism += counts[1]
        check("genome %d: %d decisions compared" % (k, turns), mism == 0, "(%d mismatches)" % mism)


# --------------------------------------------------------------------------- C
def section_c(games=40):
    print("C  tracker vs the engine's hidden state")
    ns = load(BOT)
    Tracker, Obs = ns["Tracker"], ns["Obs"]
    rnd = random.Random(11)
    pool = ["evolved", "spine", "raider", "camper", "greedyshield", "baiter", "cdraider",
            "ai_hawk", "ai_cheapraid", "random", "hunter"]
    err = collections.Counter()
    n = 0
    for gi in range(games):
        names = [rnd.choice(pool) for _ in range(4)]
        bots = [opponent(nm, gi * 4 + i) for i, nm in enumerate(names)]
        trs = [Tracker() for _ in range(4)]
        last = [None] * 4

        def hook(g, vs, acts, trs=trs, last=last):
            pass
        g = engine.Game(base=engine.make_map(seed=rnd.randrange(1 << 20)), start_token=rnd.randint(1, 4))
        random.seed(gi)
        while not g.over():
            vs = g.views()
            for i in range(4):
                cells = [c for row in vs[i].board for c in row]
                trs[i].update(Obs(cells), i + 1, vs[i].is_priority_token, list(vs[i].legal_actions), last[i])
                n += 1
                tr = trs[i]
                err["turn"] += tr.turn != g.turn
                for s in range(4):
                    err["score"] += tr.score[s + 1] != g.score[s]
                    err["freeze"] += tr.fl[s + 1] != g.frozen[s]
                    err["progress"] += tr.prog[s + 1] != min(g.prog[s], 2)
                    if s == i:
                        err["own cooldown"] += tr.cd[s + 1] != g.cd[s]
                    else:
                        err["rival cooldown"] += tr.cd[s + 1] != g.cd[s]
                h = tr.holder()
                err["token"] += h is not None and h != g.token
            acts = []
            for i in range(4):
                try:
                    a = bots[i](vs[i])
                except Exception:
                    a = "STAY"
                a = a if a in vs[i].legal_actions else "STAY"
                acts.append(a)
                last[i] = a
            g.step(acts)
    for k in ("turn", "score", "freeze", "own cooldown", "token"):
        check("%s exact over %d observations" % (k, n), err[k] == 0, "(%d wrong)" % err[k])
    check("progress >= 99.5% exact", err["progress"] <= 0.005 * n * 4, "(%d wrong)" % err["progress"])
    check("rival cooldowns >= 99% exact", err["rival cooldown"] <= 0.01 * n * 3,
          "(%d wrong of %d)" % (err["rival cooldown"], n * 3))


# --------------------------------------------------------------------------- D
NT = collections.namedtuple("Cell", "occupant owner is_upgraded is_home is_frozen base_points")


class S(object):
    pass


class Enumish(object):
    def __init__(self, name):
        self.name = name

    def __eq__(self, other):
        return isinstance(other, Enumish) and other.name == self.name

    def __hash__(self):
        return hash(self.name)


def _mk(board, bot_id, tok, legal, token_attr=True):
    s = S()
    s.board, s.bot_id, s.legal_actions = board, bot_id, legal
    if token_attr:
        s.is_priority_token = tok
    return s


def _nt(c, ints=False):
    f = int if ints else (lambda x: x)
    return NT(c.occupant, c.owner, f(c.is_upgraded), f(c.is_home), f(c.is_frozen), c.base_points)


VARIANTS = [
    ("documented 8x8 Cell objects", lambda v: (v, None)),
    ("flat 64-list of Cell objects", lambda v: (_mk([c for r in v.board for c in r], v.bot_id,
                                                    v.is_priority_token, list(v.legal_actions)), None)),
    ("flat 64-list of namedtuples", lambda v: (_mk([_nt(c) for r in v.board for c in r], v.bot_id,
                                                   v.is_priority_token, list(v.legal_actions)), None)),
    ("8x8 rows of namedtuples", lambda v: (_mk([[_nt(c) for c in r] for r in v.board], v.bot_id,
                                               v.is_priority_token, list(v.legal_actions)), None)),
    ("tuple board, tuple legal", lambda v: (_mk(tuple(tuple(r) for r in v.board), v.bot_id,
                                                v.is_priority_token, tuple(v.legal_actions)), None)),
    ("cells are dicts", lambda v: (_mk([[dict(zip(NT._fields, _nt(c))) for c in r] for r in v.board],
                                       v.bot_id, v.is_priority_token, list(v.legal_actions)), None)),
    ("bools as 0/1 ints", lambda v: (_mk([[_nt(c, True) for c in r] for r in v.board], v.bot_id,
                                         int(v.is_priority_token), list(v.legal_actions)), None)),
    ("bot_id as a string", lambda v: (_mk(v.board, str(v.bot_id), v.is_priority_token,
                                          list(v.legal_actions)), None)),
    ("lower-case action strings", lambda v: (_mk(v.board, v.bot_id, v.is_priority_token,
                                                 [a.lower() for a in v.legal_actions]),
                                             lambda a: a.upper() if isinstance(a, str) else a)),
    ("Enum-like action objects", lambda v: (_mk(v.board, v.bot_id, v.is_priority_token,
                                                [Enumish(a) for a in v.legal_actions]),
                                            lambda a: a.name if isinstance(a, Enumish) else a)),
    ("is_priority_token missing", lambda v: (_mk(v.board, v.bot_id, None, list(v.legal_actions),
                                                 token_attr=False), None)),
]


def interface_game(perturb, amnesia=False, seed=5):
    ns = load(BOT)
    act = ns["act"]
    g = engine.Game(base=engine.make_map(seed=seed), start_token=1)
    opp = [opponent("spine", seed * 4 + i) for i in range(3)]
    errors = 0
    while not g.over():
        vs = g.views()
        if amnesia:
            act = load(BOT)["act"]
        v0, back = perturb(vs[0])
        try:
            a = act(v0)
            ok = a in list(v0.legal_actions)
        except Exception:
            a, ok = None, False
        if ok and back is not None:
            a = back(a)
        if not ok or a not in vs[0].legal_actions:
            errors += 1
            a = "STAY"
        acts = [a]
        for i in range(3):
            b = opp[i](vs[i + 1])
            acts.append(b if b in vs[i + 1].legal_actions else "STAY")
        g.step(acts)
    return g.score[0], errors


def section_d():
    print("D  server-interface variants (one game vs 3 x spine each)")
    ref, _ = interface_game(VARIANTS[0][1])
    for name, fn in VARIANTS:
        sc, er = interface_game(fn)
        check("%-34s score %4d" % (name, sc), er == 0 and sc >= 0.9 * ref, "(%d bad turns)" % er)
    sc, er = interface_game(VARIANTS[0][1], amnesia=True)
    check("%-34s score %4d" % ("module reloaded every turn", sc), er == 0 and sc >= 0.6 * ref,
          "(%d bad turns; the organisers allow memory)" % er)


# --------------------------------------------------------------------------- E
def section_e():
    print("E  module reuse (wall clock pinned, so only state can make a difference)")

    def det():
        ns = load(BOT)
        ns["FLAGS"]["wall"] = 0
        return ns["act"]
    # four seats sharing one module must play exactly like four separate modules
    base = engine.make_map(seed=9)
    shared = det()
    g1 = play([shared] * 4, base)
    g2 = play([det() for _ in range(4)], base)
    check("four seats in one module == four modules", g1.score == g2.score, str(g1.score))
    # game 2 in a reused module must equal game 2 in a fresh module
    act = det()
    opp = lambda: [opponent("evolved")] + [opponent("spine", i) for i in range(2)]  # noqa: E731
    play([act] + opp(), engine.make_map(seed=3))
    ga = play([act] + opp(), engine.make_map(seed=4), token=2)
    gb = play([det()] + opp(), engine.make_map(seed=4), token=2)
    check("game 2 in a reused module == game 2 in a fresh module", ga.score == gb.score,
          "%s vs %s" % (ga.score, gb.score))


# --------------------------------------------------------------------------- F
def section_f():
    print("F  safety net")
    ns = load(BOT)

    def boom(*a, **k):
        raise RuntimeError("forced")
    ns["Agent"].decide = boom
    g = play([ns["act"]] + [opponent("spine", i) for i in range(3)], engine.make_map(seed=5))
    check("agent raising every turn still scores (backup planner): %d" % g.score[0], g.score[0] > 1500)
    ns2 = load(BOT)
    ns2["Agent"].decide = boom
    ns2["EvoSim"].step = boom
    g = play([ns2["act"]] + [opponent("spine", i) for i in range(3)], engine.make_map(seed=5))
    check("agent and backup both raising: stateless fallback scores %d" % g.score[0], g.score[0] > 600)


# --------------------------------------------------------------------------- G
def section_g(games=6):
    print("G  wall-clock timing, every expensive mode active (exact world + endgame)")
    worst = 0.0
    first = 0.0
    total, n = 0.0, 0
    rnd = random.Random(2)
    for gi in range(games):
        ns = load(BOT)
        act = ns["act"]
        seat = gi % 4
        bots = [opponent("evolved") for _ in range(4)] if gi % 2 == 0 else \
            [opponent(rnd.choice(["spine", "raider", "ai_hawk", "evolved"]), i) for i in range(4)]
        timed = []

        def wrapped(v, act=act, timed=timed):
            t0 = time.perf_counter()
            a = act(v)
            timed.append((time.perf_counter() - t0) * 1000.0)
            return a
        bots[seat] = wrapped
        play(bots, engine.make_map(seed=rnd.randrange(1 << 20)), token=rnd.randint(1, 4))
        first = max(first, timed[0])
        worst = max(worst, max(timed[1:]))
        total += sum(timed)
        n += len(timed)
    check("worst turn %.1f ms (limit 200)" % worst, worst < 150.0)
    check("worst first turn %.1f ms (limit 2000)" % first, first < 1200.0)
    print("  mean %.1f ms per turn" % (total / max(1, n)))


# --------------------------------------------------------------------------- H
def section_h():
    print("H  static checks")
    with open(BOT, "rb") as f:
        raw = f.read()
    check("pure ASCII", all(b < 128 for b in raw))
    tree = ast.parse(raw.decode("ascii", "replace"))
    allowed = {"collections", "math", "time"}
    mods = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            mods.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            mods.add((node.module or "").split(".")[0])
    check("imports only %s" % sorted(allowed), mods <= allowed, str(sorted(mods)))
    acts = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "act"]
    check("one top-level act(state)", len(acts) == 1 and [a.arg for a in acts[0].args.args] == ["state"])
    calls = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            calls.add(node.func.id)
    check("no print / open / exec / eval / input", not (calls & {"print", "open", "exec", "eval", "input"}))


# --------------------------------------------------------------------------- I
def section_i(games=6):
    print("I  Zenith's Apex simulator against apex/apex_bot.py, turns 1-60")
    os.chdir(ROOT)
    zn = load(BOT)
    rnd = random.Random(11)
    bad = tot = 0
    pool = ["spine", "camper", "ai_hawk", "pro_tuned", "cdraider", "turtle", "ai_marginal"]
    for gi in range(games):
        apex = load(os.path.join(ROOT, "apex", "apex_bot.py"))
        seat = rnd.randint(1, 4)
        bots = [apex["act"] if s == seat else opponent(rnd.choice(pool), seed=gi * 4 + s)
                for s in (1, 2, 3, 4)]
        sim = zn["Agent"](zn["APEX_SIM"])
        g = engine.Game(base=engine.make_map(seed=rnd.randrange(1 << 20)),
                        start_token=rnd.randint(1, 4))
        while not g.over() and g.turn <= 60:
            vs = g.views()
            acts = []
            for i in range(4):
                try:
                    a = bots[i](vs[i])
                except Exception:
                    a = "STAY"
                acts.append(a if a in vs[i].legal_actions else "STAY")
            cells, me, token, names, _lk = zn["normalise"](vs[seat - 1])
            pa = sim.decide(cells, me, token, names, 0.0)
            sim.last = pa
            tot += 1
            bad += pa != acts[seat - 1]
            g.step(acts)
    check("Apex simulator matches Apex on %d decisions" % tot, bad == 0, "%d mismatches" % bad)


if __name__ == "__main__":
    quick = len(sys.argv) > 1 and sys.argv[1] == "quick"
    t0 = time.time()
    section_h()
    section_a(120 if quick else 300)
    section_b(12 if quick else 40)
    section_c(12 if quick else 40)
    section_d()
    section_e()
    section_f()
    section_i(3 if quick else 8)
    if not quick:
        section_g()
    print("\n%s in %.0f s" % ("ALL PASSED" if not FAILS else "FAILED: %s" % ", ".join(FAILS),
                             time.time() - t0))
    sys.exit(1 if FAILS else 0)
