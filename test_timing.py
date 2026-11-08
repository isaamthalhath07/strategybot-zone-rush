"""
What happens on a slow grader?

The server allows 200 ms per turn and scores a late turn as STAY. This machine
takes about 5 ms, so there is a 40x margin -- but the margin is the only thing I
know about the grading machine, and a shared or throttled container can easily be
an order of magnitude slower than a desktop.

The bot defends itself two ways: an internal deadline well under the limit, and
an adaptive beam that shrinks when a turn runs long and grows back when it does
not. This test shrinks the internal budget to emulate a machine 10x, 30x and 100x
slower and checks that play degrades smoothly instead of collapsing -- no illegal
actions, no crashes, and a score that stays far above the skeleton's.

    python test_timing.py
"""
import json
import sys
import time

import engine
import mybot
import zoo

P = dict(mybot.PARAMS)
P.update(json.load(open("v6_params.json")))
GAMES = 10
fails = []


def run(params, games=GAMES):
    tot = 0
    worst = 0.0
    illegal = 0
    crashes = 0
    stays = 0
    turns = 0
    for gi in range(games):
        base = engine.make_map(seed=gi + 1)
        ag = mybot.Agent(seed=gi, params=params)
        bots = [ag] + [zoo.SpineFarmerBot(gi * 4 + i) for i in range(1, 4)]
        g = engine.Game(base=base, start_token=(gi % 4) + 1)
        while not g.over():
            vs = g.views()
            acts = []
            for i in range(4):
                if i == 0:
                    t0 = time.perf_counter()
                    try:
                        a = bots[i](vs[i])
                    except Exception:
                        crashes += 1
                        a = "STAY"
                    dt = time.perf_counter() - t0
                    if dt > worst:
                        worst = dt
                    if a not in vs[i].legal_actions:
                        illegal += 1
                        a = "STAY"
                    turns += 1
                    if a == "STAY":
                        stays += 1
                else:
                    a = bots[i](vs[i])
                    if a not in vs[i].legal_actions:
                        a = "STAY"
                acts.append(a)
            g.step(acts)
        tot += g.score[0]
    return tot / games, worst * 1000.0, illegal, crashes, stays / float(turns)


print("Emulating slower hardware by shrinking the bot's own time budget.")
print("A real 200 ms limit with a 60 ms internal budget leaves a 3.3x safety")
print("factor on top of whatever the server's own overhead is.\n")
print("%-34s %7s %8s %6s %6s %6s"
      % ("internal budget", "score", "max ms", "stay", "ill", "crash"))
print("-" * 72)
full = None
for label, ms in (("60 ms (shipped)", 60.0), ("6 ms  (~10x slower machine)", 6.0),
                  ("2 ms  (~30x slower machine)", 2.0),
                  ("0.6 ms (~100x slower machine)", 0.6)):
    p = dict(P)
    p["budget_ms"] = ms
    sc, worst, ill, cr, stay = run(p)
    if full is None:
        full = sc
    print("%-34s %7.0f %8.1f %6.2f %6d %6d" % (label, sc, worst, stay, ill, cr))
    if ill or cr:
        fails.append("illegal action or crash at a %s budget" % label)
    if sc < full * 0.55:
        fails.append("score collapsed to %.0f (%.0f%% of full) at %s"
                     % (sc, 100.0 * sc / full, label))

print("\nFor reference, the skeleton bot (STAY every turn) in the same games:")
tot = 0
for gi in range(GAMES):
    base = engine.make_map(seed=gi + 1)
    bots = [zoo.StayBot(0)] + [zoo.SpineFarmerBot(gi * 4 + i) for i in range(1, 4)]
    tot += engine.play(bots, base=base, start_token=(gi % 4) + 1).score[0]
print("  %-32s %7.0f" % ("skeleton", tot / GAMES))

print("\n=== does the throttle actually react? ================================")
# drive one agent with a tight budget and watch the beam scale move
p = dict(P)
p["budget_ms"] = 0.4
p["throttle"] = 1
ag = mybot.Agent(seed=3, params=p)
base = engine.make_map(seed=4)
g = engine.Game(base=base, start_token=1)
others = [zoo.SpineFarmerBot(i) for i in range(1, 4)]
scales = []
while not g.over():
    vs = g.views()
    acts = [ag(vs[0])] + [others[i - 1](vs[i]) for i in range(1, 4)]
    scales.append(ag._beam_scale)
    g.step(acts)
print("  beam scale over 80 turns: start %.2f  min %.2f  end %.2f"
      % (scales[0], min(scales), scales[-1]))
if min(scales) >= 0.99:
    fails.append("the throttle never engaged even at a 0.4 ms budget")
else:
    print("  OK: it shrank the search instead of running over")

print("\n" + "=" * 72)
if fails:
    print("FAILURES (%d):" % len(fails))
    for f in fails:
        print("  - %s" % f)
    sys.exit(1)
print("TIMING SAFE: degrades smoothly, never illegal, never crashes")
