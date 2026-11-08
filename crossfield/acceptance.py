"""
Acceptance checks for the shipped bot.py. ship.py runs these; any problem
blocks the submission.

There is no trial run against the organisers' server, so each check below
stands for one concrete way the server could differ from the local referees, or
one way the bot could fail silently. "Silently" is the important word: a bot that
raises, runs late or returns an unusable action is scored as STAY for that turn,
the game carries on, and nothing on the scoreboard says why.

    python crossfield/acceptance.py [bot.py]
"""
import ast
import io
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
import robustness  # noqa: E402
import xfield  # noqa: E402

STDLIB_OK = {"time", "collections", "math", "random", "sys", "heapq", "itertools"}
DEV_MODULES = {"engine", "zoo", "rivals", "arena", "mybot", "econ", "fusion", "xfield",
               "field", "aifield", "holdout", "probot", "newfield"}


def _say(msg):
    print("  " + msg)


def _game(bots, base, token=1, legal_filter=None, action_map=None):
    """Play one game. legal_filter / action_map model a non-standard server."""
    g = engine.Game(base=base, start_token=token)
    while not g.over():
        vs = g.views()
        acts = []
        for i in range(4):
            v = vs[i]
            if legal_filter is not None:
                v = engine.View(v.board, v.bot_id, v.is_priority_token, legal_filter(g, i))
            a = bots[i](v)
            if a not in v.legal_actions:
                a = "STAY"
            if action_map is not None:
                a = action_map(a)
            acts.append(a)
        g.step(acts)
    return g


def run(path):
    path = os.path.abspath(path)
    os.chdir(ROOT)
    problems = []
    src = open(path, "rb").read()

    # 1. the file itself ---------------------------------------------------------
    try:
        text = src.decode("ascii")
        _say("encoding: pure ASCII")
    except UnicodeDecodeError:
        text = src.decode("utf-8")
        problems.append("bot.py is not pure ASCII (a server reading it with a non-UTF-8 "
                        "default encoding would fail to import it)")
    try:
        tree = ast.parse(text, feature_version=(3, 7))
        _say("grammar: parses as Python 3.7")
    except SyntaxError as e:
        tree = ast.parse(text)
        problems.append("uses syntax newer than Python 3.7: %s" % e)
    mods = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            mods.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            mods.add(node.module.split(".")[0])
    _say("imports: %s" % sorted(mods))
    if mods - STDLIB_OK:
        problems.append("imports outside the allowed stdlib set: %s" % sorted(mods - STDLIB_OK))
    if mods & DEV_MODULES:
        problems.append("references development modules: %s" % sorted(mods & DEV_MODULES))
    acts = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "act"]
    if len(acts) != 1 or [a.arg for a in acts[0].args.args] != ["state"]:
        problems.append("there must be exactly one module-level act(state)")
    else:
        _say("entry point: one module-level act(state)")
    calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call)
             and isinstance(n.func, ast.Name) and n.func.id in ("print", "open", "input",
                                                                 "exec", "eval")]
    if calls:
        problems.append("calls print/open/input/exec/eval (%d sites): stdout may be the "
                        "server's protocol channel" % len(calls))
    else:
        _say("no print/open/input/exec/eval calls")

    # import it exactly as a server would, capturing anything it writes
    fac = xfield.file_bot(path)
    fac_live = xfield.file_bot(path, deterministic=False)
    real_out = sys.stdout
    sys.stdout = cap = io.StringIO()
    try:
        fac(0)
    finally:
        sys.stdout = real_out
    if cap.getvalue():
        problems.append("importing bot.py writes to stdout")

    # 2. identical to the development fusion, and to the research bot -----------
    dev = xfield.file_bot(os.path.join(ROOT, "fusion.py"))
    evo = xfield.file_bot(os.path.join(HERE, "bots", "evolved.py"))
    tasks = xfield.make_tasks(12, seed=4040)
    same_dev = same_evo = True
    for t in tasks:
        a, b, c = fac(0), dev(0), evo(0)
        me = t["seat"]
        opps = [xfield.opponent(n)(t["map_seed"] * 4 + i) for i, n in enumerate(t["opps"])]
        g = engine.Game(base=xfield.make_map(t["family"], t["map_seed"]), start_token=t["token"])
        while not g.over() and (same_dev or same_evo):
            vs = xfield._views(g, t["excl"])
            row = []
            k = 0
            for i in range(4):
                if i == me:
                    x, y, z = a(vs[i]), b(vs[i]), c(vs[i])
                    same_dev = same_dev and x == y
                    same_evo = same_evo and x == z
                    row.append(x)
                else:
                    row.append(opps[k](vs[i]))
                    k += 1
            g.step([r if r in vs[i].legal_actions else "STAY" for i, r in enumerate(row)])
    _say("plays identically to the development fusion.py: %s" % same_dev)
    _say("plays identically to research/evolution's bot on the documented interface: %s"
         % same_evo)
    if not same_dev:
        problems.append("the built bot.py diverges from fusion.py")
    if not same_evo:
        problems.append("a failsafe layer changed play on the documented interface")

    # 3. four seats in one process, and several games in one process -------------
    ns_act = fac(0)
    ok = True
    for s_ in range(3):
        base = engine.make_map(seed=2500 + s_)
        try:
            _game([ns_act] * 4, base, token=1 + s_)
        except Exception as e:
            ok = False
            problems.append("four seats sharing one module raised %r" % (e,))
    # game 2 in a reused module must play exactly like game 2 in a fresh one
    reused = fac(0)
    base1, base2 = engine.make_map(seed=71), engine.make_map(seed=72)
    opp = lambda: [xfield.opponent("spine")(i) for i in range(3)]
    _game([reused] + opp(), base1)
    g_reused = _game([reused] + opp(), base2)
    g_fresh = _game([fac(0)] + opp(), base2)
    leak = g_reused.score != g_fresh.score
    _say("four seats in one module: %s;  game 2 in a reused module == fresh module: %s"
         % ("OK" if ok else "BROKEN", not leak))
    if leak:
        problems.append("state leaks from one game into the next in the same process")

    # 4. the failsafe chain, by forcing each planner to fail ---------------------
    def broken(which):
        def make(seed):
            ns = {"__name__": "xfield_bot"}
            exec(compile(open(path, encoding="utf-8").read(), path, "exec"), ns)
            ns["SAFETY"]["deterministic"] = True

            def boom(*_a, **_k):
                raise RuntimeError("forced")
            if "econ" in which:
                ns["Econ"].step = boom
            if "route" in which:
                ns["Agent"].plan = boom
            if "ingest" in which:
                ns["Agent"].ingest = boom
            if "fallback" in which:
                ns["_fallback"] = boom
            return ns["act"]
        return make
    rows = [("healthy", fac), ("econ raises", broken("econ")),
            ("econ + walk planner raise", broken("econ route")),
            ("econ + tracker raise", broken("econ ingest")),
            ("everything raises", broken("econ route ingest fallback"))]
    scores = {}
    for name, f in rows:
        tot = 0
        for s_ in range(4):
            base = engine.make_map(seed=4700 + s_)
            bots = [f(0)] + [xfield.opponent("spine")(s_ * 4 + i) for i in range(1, 4)]
            tot += _game(bots, base, token=1 + s_).score[0]
        scores[name] = tot / 4.0
    _say("failsafe chain (mean score vs 3 spine): " + ", ".join(
        "%s %.0f" % (k, v) for k, v in scores.items()))
    if scores["econ raises"] < 0.85 * scores["healthy"]:
        problems.append("losing the economic planner costs more than 15%")
    if scores["econ + walk planner raise"] < 4 * 160:
        problems.append("the fallback policy is no better than STAY")

    # 5. interface variants --------------------------------------------------------
    ref, _, _ = robustness.play(path, robustness.p_documented)
    bad = []
    for name, fn in robustness.PERTURB:
        sc, er, _ = robustness.play(path, fn)
        # A missing token flag genuinely removes information, so play may differ;
        # every other variant carries the same information and must not.
        floor = 0.85 if fn is robustness.p_no_token_attr else 0.97
        if er or sc < floor * ref:
            bad.append("%s (%.0f vs %.0f, %d errors)" % (name, sc, ref, er))
    am, er, _ = robustness.play(path, robustness.p_documented, amnesia=True)
    _say("interface variants: %d of %d degrade; module memory lost every turn: %.0f "
         "(vs %.0f)" % (len(bad), len(robustness.PERTURB), am, ref))
    for b in bad:
        problems.append("interface variant degrades play: " + b)
    if am < 0.85 * ref:
        problems.append("memory loss every turn costs more than 15%% (%.0f vs %.0f)" % (am, ref))

    # 6. servers that bend the rules' interface --------------------------------------
    # 6a. SHIELD offered during cooldown and scored as STAY
    def shield_always(g, i):
        leg = g.legal(i)
        if g.frozen[i] == 0 and "SHIELD" not in leg:
            leg = leg + ["SHIELD"]
        return leg
    wasted = 0
    for s_ in range(4):
        base = engine.make_map(seed=5100 + s_)
        a = fac(0)
        sent = []

        def spy(v, a=a, sent=sent):
            x = a(v)
            sent.append(x)
            return x
        bots = [spy] + [xfield.opponent(n)(s_ * 4 + i) for i, n in
                        enumerate(("ai_cheapraid", "cdraider", "evolved"))]
        g = engine.Game(base=base, start_token=1 + s_)
        while not g.over():
            vs = g.views()
            cd0 = g.cd[0]
            row = []
            for i in range(4):
                v = engine.View(vs[i].board, i + 1, vs[i].is_priority_token, shield_always(g, i))
                x = bots[i](v)
                row.append(x if x in v.legal_actions else "STAY")
            if row[0] == "SHIELD" and cd0 > 0:
                wasted += 1
            g.step(row)
    _say("server offering SHIELD during cooldown: %d shields sent on cooldown" % wasted)
    if wasted:
        problems.append("sent SHIELD during cooldown %d times" % wasted)

    # 6b. a server whose NORTH is row + 1 (a vertically flipped frame)
    flip = {"NORTH": "SOUTH", "SOUTH": "NORTH"}

    def flipped_legal(g, i):
        return [flip.get(a, a) for a in g.legal(i)]
    tot_n = tot_f = 0
    for s_ in range(4):
        base = engine.make_map(seed=5300 + s_)
        bots = [fac(0)] + [xfield.opponent("spine")(s_ * 4 + i) for i in range(1, 4)]
        tot_n += _game(bots, base, token=1 + s_).score[0]
        bots = [fac(0)] + [xfield.opponent("spine")(s_ * 4 + i) for i in range(1, 4)]
        g = engine.Game(base=base, start_token=1 + s_)
        while not g.over():
            vs = g.views()
            row = []
            for i in range(4):
                if i == 0:
                    v = engine.View(vs[0].board, 1, vs[0].is_priority_token, flipped_legal(g, 0))
                    x = bots[0](v)
                    x = flip.get(x, x) if x in v.legal_actions else "STAY"
                else:
                    x = bots[i](vs[i])
                    x = x if x in vs[i].legal_actions else "STAY"
                row.append(x)
            g.step(row)
        tot_f += g.score[0]
    _say("server with a flipped NORTH/SOUTH convention: %.0f vs %.0f on the documented one"
         % (tot_f / 4.0, tot_n / 4.0))
    if tot_f < 0.85 * tot_n:
        problems.append("does not recover from a flipped movement convention")

    # 6c. everybody stays home for the first turns: neither planner's clock or
    #     score reconstruction may reset (main v7 read five all-home turns as
    #     turn 1 with every score zero)
    a = fac(0)
    ns = a.__globals__
    g = engine.Game(base=engine.make_map(seed=77))
    for t_ in range(6):
        a(g.views()[0])
        if t_ < 5:
            g.step(["STAY"] * 4)
    brain = ns["_F_BRAINS"][1]
    e_turn, r_turn = brain.econ.mem["turn"], brain.route.tr.turn
    e_score = brain.econ.mem["scores"][1:5]
    r_score = list(brain.route.tr.score)
    good = e_turn == 6 and r_turn == 6 and e_score == g.score and r_score == g.score
    _say("all-home opening, 6th turn: econ clock %d, tracker clock %d, scores %s / %s, "
         "true %s" % (e_turn, r_turn, e_score, r_score, g.score))
    if not good:
        problems.append("the clock or score reconstruction resets during an all-home opening")
    # 6d. a rival steps out of its home and back without capturing: the board is
    #     a starting board again, but it is still the same game (positions revert;
    #     only ownership and upgrades cannot). This is the case that slipped past
    #     6c: an earlier fix keyed on "fresh after non-fresh" and reset here.
    a = fac(0)
    ns = a.__globals__
    g = engine.Game(base=engine.make_map(seed=78))
    script = [["STAY", "WEST", "STAY", "STAY"], ["STAY", "EAST", "STAY", "STAY"],
              ["STAY", "STAY", "STAY", "STAY"]]
    for t_ in range(4):
        a(g.views()[0])
        if t_ < 3:
            g.step(script[t_])
    brain = ns["_F_BRAINS"][1]
    e_turn, r_turn = brain.econ.mem["turn"], brain.route.tr.turn
    good = (e_turn == 4 and r_turn == 4 and brain.turns == 4
            and brain.econ.mem["scores"][1:5] == g.score and list(brain.route.tr.score) == g.score)
    _say("rival steps out and back home, 4th turn: econ clock %d, tracker clock %d, "
         "brain turns %d" % (e_turn, r_turn, brain.turns))
    if not good:
        problems.append("a rival stepping out of and back into its home resets the game clock")

    # 7. time, on the real clock with the real guards on -------------------------
    worst = 0.0
    times = []
    for s_ in range(24):
        rnd = random.Random(3000 + s_)
        base = xfield.make_map(("slope", "balanced", "patchy", "edge")[s_ % 4], 3000 + s_)
        me = rnd.randrange(4)
        names = ["main_v7", "pro_tuned", "evolved", "rollout", "seq", "spine"]
        bots = []
        for i in range(4):
            if i == me:
                live = fac_live(0)

                def timed(v, live=live):
                    t0 = time.perf_counter()
                    x = live(v)
                    times.append(time.perf_counter() - t0)
                    return x
                bots.append(timed)
            else:
                bots.append(xfield.opponent(names[rnd.randrange(len(names))])(s_ * 4 + i))
        _game(bots, base, token=rnd.randint(1, 4))
    times.sort()
    worst = times[-1] * 1000
    p99 = times[int(len(times) * 0.99)] * 1000
    mean = 1000 * sum(times) / len(times)
    _say("turn time over 24 games (live clock): mean %.2f ms, p99 %.2f ms, max %.1f ms"
         % (mean, p99, worst))
    if worst > 100:
        problems.append("max turn %.0f ms leaves too little margin under 200 ms" % worst)
    return problems


if __name__ == "__main__":
    out = run(sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "bot.py"))
    print()
    if out:
        print("PROBLEMS:")
        for p in out:
            print("  - " + p)
        sys.exit(1)
    print("ALL ACCEPTANCE CHECKS PASS")
