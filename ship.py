"""
Build the submission: a single self-contained bot.py with the tuned weights
baked in, then verify it hard.

Checks: stdlib-only imports, the act(state) signature is untouched, no dev-module
references, byte-for-byte identical play to the dev bot, no crash / illegal action
/ timeout across a battery of games, and that four copies in one process do not
share state.
"""
import ast
import json
import os
import random
import sys
import time

ALLOWED_IMPORTS = {"time", "collections", "math", "random", "sys"}
# bot.py is built from fusion.py by default; `python ship.py route <params>`
# still builds the walk planner alone. The old default, best_params.json, had
# been renamed to v7_seed.json, so `python ship.py` with no argument crashed.
HEADER = '''"""
StrategyBot / Zone Rush competition bot.

Plan: reconstruct everything the state object hides (turn number, all four
scores, take and upgrade progress, shield cooldowns, freeze counters, the
priority-token holder) from board diffs; plan a whole walk of work rather than
chasing one target at a time; and estimate shield/raid payoffs using learned
opponent tendencies. The planner and defensive mixing are heuristics, not a
proof of optimality or an equilibrium strategy.

Entry point: act(state) -> one of NORTH, EAST, SOUTH, WEST, STAY, SHIELD.
Standard library only.
"""
'''


def build(src="mybot.py", params_file="v8_fresh_params.json", out="bot.py"):
    import mybot
    with open(src, encoding="utf-8") as source:
        s = source.read()
    # Start from the dev defaults so a key added after the last tuning run cannot
    # go missing -- a missing key raises inside decide(), gets swallowed by the
    # try/except, and the bot silently plays STAY for the whole game.
    params = dict(mybot.PARAMS)
    with open(params_file, encoding="utf-8") as weights:
        tuned = json.load(weights)
    params.update(tuned)
    missing = set(mybot.PARAMS) - set(tuned)
    if missing:
        print("  note: %d param(s) not in %s, using dev defaults: %s"
              % (len(missing), params_file, sorted(missing)))

    # bake the tuned weights in as literals
    start = s.index("PARAMS = {")
    end = s.index("\n}\n", start) + 3
    lines = ["PARAMS = {"]
    for k in sorted(params):
        v = params[k]
        lines.append("    %r: %r," % (k, v))
    lines.append("}\n")
    s = s[:start] + "\n".join(lines) + s[end:]

    # strip the module docstring and put the submission header on
    tree = ast.parse(s)
    if (tree.body and isinstance(tree.body[0], ast.Expr)
            and isinstance(tree.body[0].value, ast.Constant)):
        doc_end = tree.body[0].end_lineno
        s = "\n".join(s.splitlines()[doc_end:]).lstrip("\n")
    s = HEADER + "\n" + s
    # Byte-identical output on Windows and Linux: provenance and replay hashes
    # must not change merely because Git checks out LF on another machine.
    with open(out, "w", encoding="utf-8", newline="\n") as submission:
        submission.write(s)
    return out


def verify(out="bot.py", params_file="v8_fresh_params.json"):
    import engine
    import mybot
    import zoo

    problems = []
    src = open(out, encoding="utf-8").read()
    tree = ast.parse(src)

    # 1. stdlib-only imports
    mods = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                mods.add(a.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                mods.add(node.module.split(".")[0])
    bad = mods - ALLOWED_IMPORTS
    print("  imports: %s%s" % (sorted(mods), "  <-- NON-STDLIB" if bad else ""))
    if bad:
        problems.append("non-stdlib imports: %s" % sorted(bad))
    for dev in ("engine", "zoo", "rivals", "arena", "mybot"):
        if dev in mods:
            problems.append("references dev module %s" % dev)

    # 2. act(state) signature preserved exactly
    fn = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "act"]
    if not fn:
        problems.append("no module-level act()")
    else:
        args = [a.arg for a in fn[0].args.args]
        print("  signature: act(%s)" % ", ".join(args))
        if args != ["state"]:
            problems.append("act signature is %s, must be act(state)" % args)

    # 3. import it in isolation and check it plays identically to the dev bot
    sys.path.insert(0, os.getcwd())
    import importlib.util
    spec = importlib.util.spec_from_file_location("shipped_bot", out)
    shipped = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(shipped)
    P = json.load(open(params_file))

    same = True
    for s_ in range(12):
        base = engine.make_map(seed=1500 + s_)
        g = engine.Game(base=base, start_token=(s_ % 4) + 1)
        Pd = dict(P)
        Pd["throttle"] = 0           # wall-clock-dependent throttling would make
                                     # this comparison flaky, not the bot wrong
        dev = mybot.Agent(seed=4242, params=Pd)
        shipped._AGENTS.clear()
        ships = shipped.Agent(seed=4242)
        ships.P["throttle"] = 0
        opp = [zoo.CamperBot(i) for i in range(3)]
        while not g.over():
            vs = g.views()
            a1 = dev(vs[0])
            a2 = ships(vs[0])
            if a1 != a2:
                same = False
                break
            acts = [a1] + [opp[i](vs[i + 1]) for i in range(3)]
            acts = [x if x in vs[i].legal_actions else "STAY"
                    for i, x in enumerate(acts)]
            g.step(acts)
        if not same:
            break
    print("  identical play to dev bot: %s" % same)
    if not same:
        problems.append("shipped bot diverges from dev bot")

    # 4. four copies in one process must not share state
    shipped._AGENTS.clear()
    ok4 = True
    for s_ in range(6):
        base = engine.make_map(seed=2500 + s_)
        g = engine.Game(base=base, start_token=(s_ % 4) + 1)
        while not g.over():
            vs = g.views()
            acts = []
            for i in range(4):
                try:
                    a = shipped.act(vs[i])
                except Exception as e:
                    ok4 = False
                    problems.append("act() raised: %r" % (e,))
                    a = "STAY"
                if a not in vs[i].legal_actions:
                    ok4 = False
                    problems.append("act() returned illegal %r" % a)
                    a = "STAY"
                acts.append(a)
            g.step(acts)
        shipped._AGENTS.clear()
    print("  four seats sharing one module: %s" % ("OK" if ok4 else "BROKEN"))

    # 4b. decide() must not be raising internally -- __call__ swallows exceptions
    #     and returns STAY, which looks like a working bot and scores zero.
    shipped._AGENTS.clear()
    raised = []
    probe = shipped.Agent(seed=1)
    for s_ in range(4):
        base = engine.make_map(seed=4100 + s_)
        g = engine.Game(base=base, start_token=(s_ % 4) + 1)
        opp = [zoo.RaiderBot(i) for i in range(3)]
        while not g.over():
            vs = g.views()
            try:
                a = probe.decide(vs[0])          # NOT through __call__
            except Exception as e:
                raised.append(repr(e))
                a = "STAY"
            if a not in vs[0].legal_actions:
                a = "STAY"
            acts = [a] + [opp[i](vs[i + 1]) for i in range(3)]
            acts = [x if x in vs[i].legal_actions else "STAY"
                    for i, x in enumerate(acts)]
            g.step(acts)
    print("  decide() internal exceptions: %d%s"
          % (len(raised), "" if not raised else "  <-- " + raised[0]))
    if raised:
        problems.append("decide() raises internally (%d times): %s"
                        % (len(raised), raised[0]))

    # 4c. the fallback policy has to survive into the shipped file. If decide()
    #     ever raises on the real server, this is the whole difference between a
    #     mediocre bot and 80 turns of STAY.
    if not hasattr(shipped, "_fallback"):
        problems.append("the shipped file has no _fallback policy")
        print("  fallback policy: MISSING")
    else:
        fb_score = stay_score = 0
        for s_ in range(6):
            base = engine.make_map(seed=4700 + s_)
            for which in ("fallback", "stay"):
                g = engine.Game(base=base, start_token=(s_ % 4) + 1)
                opp = [zoo.SpineFarmerBot(s_ * 4 + i) for i in range(1, 4)]
                while not g.over():
                    vs = g.views()
                    if which == "fallback":
                        try:
                            a = shipped._fallback(vs[0])
                        except Exception as e:
                            problems.append("_fallback raised: %r" % (e,))
                            a = "STAY"
                    else:
                        a = "STAY"
                    if a not in vs[0].legal_actions:
                        problems.append("_fallback returned illegal %r" % a)
                        a = "STAY"
                    acts = [a] + [opp[i](vs[i + 1]) for i in range(3)]
                    acts = [x if x in vs[i].legal_actions else "STAY"
                            for i, x in enumerate(acts)]
                    g.step(acts)
                if which == "fallback":
                    fb_score += g.score[0]
                else:
                    stay_score += g.score[0]
        ratio = fb_score / float(max(1, stay_score))
        print("  fallback policy: scores %.1fx the skeleton (%.0f vs %.0f)"
              % (ratio, fb_score / 6.0, stay_score / 6.0))
        if ratio < 2.0:
            problems.append("fallback policy is no better than STAY (%.1fx)" % ratio)

    # 5. stress: never crash, never illegal, never slow
    worst = 0.0
    bad_n = 0
    t_all = []
    acted = []
    for s_ in range(40):
        rnd = random.Random(3000 + s_)
        base = engine.make_map(seed=3000 + s_)
        myseat = rnd.randrange(4)
        shipped._AGENTS.clear()
        field = [zoo.SpineFarmerBot, zoo.CamperBot, zoo.RaiderBot, zoo.BaiterBot,
                 zoo.GreedyShieldBot, zoo.RandomBot]
        bots = [None if i == myseat else field[rnd.randrange(len(field))](s_ * 4 + i)
                for i in range(4)]
        g = engine.Game(base=base, start_token=rnd.randint(1, 4))
        while not g.over():
            vs = g.views()
            acts = []
            for i in range(4):
                if i == myseat:
                    t0 = time.perf_counter()
                    try:
                        a = shipped.act(vs[i])
                    except Exception:
                        bad_n += 1
                        a = "STAY"
                    dt = time.perf_counter() - t0
                    t_all.append(dt)
                    if dt > worst:
                        worst = dt
                    if a not in vs[i].legal_actions:
                        bad_n += 1
                        a = "STAY"
                    acted.append(a)
                else:
                    a = bots[i](vs[i])
                    if a not in vs[i].legal_actions:
                        a = "STAY"
                acts.append(a)
            g.step(acts)
    t_all.sort()
    stay_frac = acted.count("STAY") / float(max(1, len(acted)))
    print("  action mix: %.0f%% STAY, %.0f%% move, %.0f%% shield%s"
          % (100 * stay_frac,
             100 * sum(1 for a in acted if a in ("NORTH", "SOUTH", "EAST", "WEST"))
             / float(max(1, len(acted))),
             100 * acted.count("SHIELD") / float(max(1, len(acted))),
             "   <-- DEGENERATE" if stay_frac > 0.85 else ""))
    if stay_frac > 0.85:
        problems.append("policy is %.0f%% STAY -- it is almost certainly crashing"
                        % (100 * stay_frac))
    print("  stress 40 games: %d failures, max %.1f ms, p99 %.1f ms, mean %.1f ms"
          % (bad_n, worst * 1000, t_all[int(len(t_all) * 0.99)] * 1000,
             1000 * sum(t_all) / len(t_all)))
    if bad_n:
        problems.append("%d crashes/illegal actions under stress" % bad_n)
    if worst > 0.10:
        problems.append("max turn time %.0f ms leaves too little margin under the "
                        "200 ms limit on a loaded server" % (worst * 1000))

    print("  file size: %.1f KB, %d lines"
          % (len(src) / 1024.0, len(src.splitlines())))
    return problems


# ---------------------------------------------------------------------------
# The fusion submission: fusion.py + econ.py + mybot.py inlined into one file.
# ---------------------------------------------------------------------------
DEV_BEGIN = "# --- dev imports: ship.py inlines econ.py and mybot.py and deletes this block ---"
DEV_END = "# --- end dev imports ---"


def _body(path):
    """A module's source without its docstring and without its import lines."""
    s = open(path, encoding="utf-8").read()
    tree = ast.parse(s)
    lines = s.splitlines()
    drop = set()
    if (tree.body and isinstance(tree.body[0], ast.Expr)
            and isinstance(tree.body[0].value, ast.Constant)
            and isinstance(tree.body[0].value.value, str)):
        drop.update(range(tree.body[0].lineno - 1, tree.body[0].end_lineno))
    imports = []
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            drop.update(range(node.lineno - 1, node.end_lineno))
            imports.append(ast.get_source_segment(s, node))
    doc = ast.get_docstring(tree, clean=False) if tree.body else None
    return "\n".join(l for i, l in enumerate(lines) if i not in drop), imports, doc


def _strip_act(src):
    """Remove mybot's own module-level act(): the fusion's is the entry point."""
    i = src.index("\ndef act(state):")
    j = src.find("\n\n\n", i + 1)
    return src[:i] + ("\n" if j < 0 else src[j:])


def build_fusion(out="bot.py"):
    fsrc = open("fusion.py", encoding="utf-8").read()
    a = fsrc.index(DEV_BEGIN)
    b = fsrc.index(DEV_END) + len(DEV_END)
    open("_fusion_shipped.tmp", "w", encoding="utf-8").write(fsrc[:a] + fsrc[b:])
    try:
        fbody, fimp, fdoc = _body("_fusion_shipped.tmp")
    finally:
        os.remove("_fusion_shipped.tmp")
    ebody, eimp, _ = _body("econ.py")
    rbody, rimp, _ = _body("mybot.py")
    rbody = _strip_act(rbody)
    imports = []
    for line in eimp + rimp + fimp:
        if line not in imports:
            imports.append(line)
    parts = ['"""' + fdoc + '"""', "\n".join(sorted(imports)),
             "\n# " + "=" * 74 + "\n# econ.py -- research/evolution's economic planner (primary)\n# "
             + "=" * 74 + "\n" + ebody.strip("\n"),
             "\n# " + "=" * 74 + "\n# mybot.py -- hardened-field-and-fixes' tracker and walk planner"
             " (warm standby)\n# " + "=" * 74 + "\n" + rbody.strip("\n"),
             "\n# " + "=" * 74 + "\n# fusion.py -- normalisation, failsafes and the controller\n# "
             + "=" * 74 + "\n" + fbody.strip("\n")]
    src = "\n\n".join(parts) + "\n"
    open(out, "w", encoding="utf-8", newline="\n").write(src)
    return out


def usage():
    raise SystemExit("python ship.py                      build + verify the fusion bot.py\n"
                     "python ship.py route <params.json>  legacy: walk planner alone, to "
                     "bot_route.py")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "route":
        if len(sys.argv) < 3:
            usage()
        pf = sys.argv[2]
        out = build(params_file=pf, out="bot_route.py")
        print("built %s from %s" % (out, pf))
        probs = verify(out, pf)
    elif len(sys.argv) == 1:
        out = build_fusion("bot.py")
        print("built %s from fusion.py + econ.py + mybot.py" % out)
        sys.path.insert(0, os.path.join(os.getcwd(), "crossfield"))
        import acceptance
        probs = acceptance.run(out)
    else:
        usage()
    print()
    if probs:
        print("NOT READY TO SUBMIT:")
        for p in probs:
            print("  - %s" % p)
        sys.exit(1)
    print("%s PASSES ALL SUBMISSION CHECKS" % out)
