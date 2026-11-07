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


def build(src="mybot.py", params_file="best_params.json", out="bot.py"):
    import mybot
    s = open(src, encoding="utf-8").read()
    # Start from the dev defaults so a key added after the last tuning run cannot
    # go missing -- a missing key raises inside decide(), gets swallowed by the
    # try/except, and the bot silently plays STAY for the whole game.
    params = dict(mybot.PARAMS)
    params.update(json.load(open(params_file)))
    missing = set(mybot.PARAMS) - set(json.load(open(params_file)))
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
    open(out, "w", encoding="utf-8").write(s)
    return out


def verify(out="bot.py", params_file="best_params.json"):
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


if __name__ == "__main__":
    pf = sys.argv[1] if len(sys.argv) > 1 else "best_params.json"
    out = build(params_file=pf)
    print("built %s from %s" % (out, pf))
    probs = verify(out, pf)
    print()
    if probs:
        print("NOT READY TO SUBMIT:")
        for p in probs:
            print("  - %s" % p)
        sys.exit(1)
    print("bot.py PASSES ALL SUBMISSION CHECKS")
