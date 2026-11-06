"""
Robustness suite. The starter kit ships no engine, so engine.py encodes my best
guess at five genuinely ambiguous rules. These tests ask: does the bot still win
if my guesses are wrong, and does it survive every malformed input I can think of?
"""
import json
import os
import random
import time

import engine
import mybot
import zoo

PARAMS = {}
if os.path.exists("best_params.json"):
    PARAMS = json.load(open("best_params.json"))

FIELD = [zoo.SpineFarmerBot, zoo.CamperBot, zoo.GreedyShieldBot,
         zoo.GreedyValueBot, zoo.PacifistBot, zoo.RaiderBot, zoo.BaiterBot]

fails = []


def pw_under(rules, games=120, seed0=4000, params=None, max_turns=80):
    tot = 0.0
    worst = 0.0
    illegal = 0
    crashes = 0
    for s in range(games):
        rnd = random.Random(seed0 + s)
        base = engine.make_map(seed=seed0 + s)
        myseat = rnd.randrange(4)
        ag = mybot.Agent(seed=s, params=params if params is not None else PARAMS)
        bots = [ag if i == myseat else FIELD[rnd.randrange(len(FIELD))](s * 4 + i)
                for i in range(4)]
        g = engine.Game(base=base, start_token=rnd.randint(1, 4), rules=rules,
                        max_turns=max_turns)
        while not g.over():
            vs = g.views()
            acts = []
            for i in range(4):
                if i == myseat:
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
                else:
                    a = bots[i](vs[i])
                    if a not in vs[i].legal_actions:
                        a = "STAY"
                acts.append(a)
            g.step(acts)
        pl = g.places()
        tot += sum(1.0 for j in range(4) if j != myseat and pl[myseat] < pl[j])
        tot += 0.5 * sum(1 for j in range(4) if j != myseat and pl[myseat] == pl[j])
    return tot / games, worst * 1000.0, illegal, crashes


print("=== A. are the ambiguous rules load-bearing? ============================")
print("Each row flips one rule I had to guess. PW is out of 3.")
base_pw, worst, ill, cr = pw_under(None)
print("  %-34s PW %.2f   (max %.0f ms, %d illegal, %d crashes)"
      % ("engine defaults", base_pw, worst, ill, cr))
if ill or cr:
    fails.append("illegal/crash under defaults")
VARIANTS = [
    ("frozen_stay_counts = True", {"frozen_stay_counts": True}),
    ("claim_resets_progress = False", {"claim_resets_progress": False}),
    ("catch_requires_stay = False", {"catch_requires_stay": False}),
    ("lost_contest_is_stay = False", {"lost_contest_is_stay": False}),
    ("home_upgradable = False", {"home_upgradable": False}),
    ("all five flipped", {"frozen_stay_counts": True, "claim_resets_progress": False,
                          "catch_requires_stay": False, "lost_contest_is_stay": False,
                          "home_upgradable": False}),
]
for name, rules in VARIANTS:
    pw, worst, ill, cr = pw_under(rules)
    flag = "" if pw > 2.0 else "   <-- WEAK"
    print("  %-34s PW %.2f   (max %.0f ms, %d illegal, %d crashes)%s"
          % (name, pw, worst, ill, cr, flag))
    if ill or cr:
        fails.append("illegal/crash under %s" % name)
    if pw < 2.0:
        fails.append("weak under %s (PW %.2f)" % (name, pw))

print("\n=== B. malformed / hostile inputs ======================================")


class FlatView(object):
    """board as a flat 64-list, which the starter kit's bot.py docstring implies."""
    __slots__ = ("board", "bot_id", "is_priority_token", "legal_actions")


def flat_game(games=12):
    bad = 0
    for s in range(games):
        base = engine.make_map(seed=9000 + s)
        g = engine.Game(base=base, start_token=1)
        ag = mybot.Agent(seed=s, params=PARAMS)
        others = [zoo.CamperBot(i) for i in range(3)]
        while not g.over():
            vs = g.views()
            fv = FlatView()
            bd = vs[0].board
            fv.board = [bd[r][c] for r in range(8) for c in range(8)]
            fv.bot_id = vs[0].bot_id
            fv.is_priority_token = vs[0].is_priority_token
            fv.legal_actions = vs[0].legal_actions
            try:
                a = ag(fv)
            except Exception:
                bad += 1
                a = "STAY"
            if a not in fv.legal_actions:
                bad += 1
                a = "STAY"
            acts = [a] + [others[i](vs[i + 1]) for i in range(3)]
            acts = [x if x in vs[i].legal_actions else "STAY"
                    for i, x in enumerate(acts)]
            g.step(acts)
    return bad


bad = flat_game()
print("  flat 64-cell board layout        : %s" % ("OK" if bad == 0 else "%d FAILURES" % bad))
if bad:
    fails.append("flat board layout")

# uniform maps, degenerate values
odd = 0
for v in (1, 3):
    b = [v] * 64
    for s in range(4):
        g = engine.Game(base=b, start_token=s % 4 + 1)
        ag = mybot.Agent(seed=s, params=PARAMS)
        bots = [ag] + [zoo.RaiderBot(i) for i in range(3)]
        while not g.over():
            vs = g.views()
            acts = []
            for i in range(4):
                try:
                    a = bots[i](vs[i])
                except Exception:
                    odd += 1
                    a = "STAY"
                if a not in vs[i].legal_actions:
                    odd += 1
                    a = "STAY"
                acts.append(a)
            g.step(acts)
print("  uniform all-1 and all-3 maps     : %s" % ("OK" if odd == 0 else "%d FAILURES" % odd))
if odd:
    fails.append("uniform maps")

# short and long games (in case the turn count is not 80)
odd = 0
for mt in (10, 40, 150):
    pw, worst, ill, cr = pw_under(None, games=8, seed0=7000, max_turns=mt)
    if ill or cr:
        odd += ill + cr
    print("  %3d-turn game                    : PW %.2f  %s"
          % (mt, pw, "OK" if not (ill or cr) else "FAILURES"))
if odd:
    fails.append("non-80-turn games")

# Every seat, to be sure nothing is hardcoded to a corner.
#
# This has to be done as SELF-PLAY. The map is four-fold mirrored, so four copies
# of one bot must average exactly 1.50 pairwise wins in each seat, and any
# deviation is that bot's own bias. Measuring against three copies of one
# opponent does NOT work: it reported this bot as 2.1/2.4/1.3/1.2 across the
# seats, which looked alarming and turned out to be SpineFarmerBot's own seat
# bias leaking in -- replacing a strong seat with my bot is a different
# experiment from replacing a weak one. See diag_seat.py.
seat_pw = []
for seat in range(4):
    tot = 0.0
    n = 0
    for s_ in range(30):
        base = engine.make_map(seed=8000 + s_)
        bots = [mybot.Agent(seed=s_ * 4 + i, params=PARAMS) for i in range(4)]
        g = engine.Game(base=base, start_token=(s_ % 4) + 1)
        while not g.over():
            vs = g.views()
            acts = []
            for i in range(4):
                a_ = bots[i](vs[i])
                if a_ not in vs[i].legal_actions:
                    a_ = "STAY"
                acts.append(a_)
            g.step(acts)
        pl = g.places()
        tot += sum(1.0 for j in range(4) if j != seat and pl[seat] < pl[j])
        tot += 0.5 * sum(1 for j in range(4) if j != seat and pl[seat] == pl[j])
        n += 1
    seat_pw.append(tot / n)
print("  PW by seat in self-play (1.50 each by symmetry) : %s" %
      "  ".join("%.2f" % x for x in seat_pw))
if max(seat_pw) - min(seat_pw) > 0.30:
    fails.append("seat-dependent strength in self-play: %s" % seat_pw)

print("\n=== C. mirror match (the convergent-field scenario) ====================")
tot = 0.0
scores = []
for s in range(40):
    base = engine.make_map(seed=6000 + s)
    bots = [mybot.Agent(seed=i * 97 + s, params=PARAMS) for i in range(4)]
    g = engine.Game(base=base, start_token=(s % 4) + 1)
    while not g.over():
        vs = g.views()
        acts = []
        for i in range(4):
            a = bots[i](vs[i])
            if a not in vs[i].legal_actions:
                a = "STAY"
            acts.append(a)
        g.step(acts)
    scores.append(sorted(g.score, reverse=True))
avg = [sum(x[k] for x in scores) / len(scores) for k in range(4)]
print("  4 identical copies, mean scores by finishing place: %s"
      % "  ".join("%.0f" % x for x in avg))
print("  spread 1st vs 4th: %.0f points (%.0f%%)"
      % (avg[0] - avg[3], 100.0 * (avg[0] - avg[3]) / avg[0]))

print("\n" + ("ALL ROBUSTNESS CHECKS PASS" if not fails else
             "PROBLEMS:\n  - " + "\n  - ".join(fails)))
