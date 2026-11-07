"""
Constructed edge cases, run directly against bot.py internals (no statistics needed).

  S1   a rival standing on MY HOME is priced as an imminent capture (finding B3)
  S1c  what an L1 shield is believed to save vs what it really saves (B2)
  S8   on turn 80 the bot walks off a neutral cell instead of claiming it (B6)
  S2   stale module state + a missed turn-1 call: R pinned to 1 all game (C2)

    python audit/scenarios.py
"""
import os
import sys
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO)
os.chdir(REPO)
import engine
import edge_audit

bot = edge_audit.bot              # honours AUDIT_BOT

def fresh_agent(base, seat=1):
    a = bot.Agent(seed=1, params={"throttle": 0, "budget_ms": 10000.0})
    home_of = [0]*64
    for s, c in engine.CORNERS.items():
        home_of[c] = s
    a.tr.init_static(base, home_of)
    a.tr.turn = 1
    a.tr.income = [0, 0, 0, 0]
    return a, home_of

base = engine.make_map(canonical=True)
print("canonical home values:", [base[c] for c in engine.CORNERS.values()])

# ---------------------------------------------------------------- S1: rival on MY HOME
print("\n[S1] rival (seat 2) standing on my home cell 0; I am seat 1 elsewhere; homes can never be taken")
for commit_obs in (0, 20):
    fires = []
    for R in range(1, 81):
        a, home_of = fresh_agent(base)
        tr = a.tr
        tr.turn = 80 - R + 1
        tr.raids[1] = commit_obs
        owner = [0]*64; upg = [0]*64; occ = [0]*64; frz = [0]*64
        for s, c in engine.CORNERS.items():
            owner[c] = s
        occ[0] = 2                      # rival on my home
        occ[9] = 1                      # me, on my own cell
        owner[9] = 1
        tr.pos = [9, 0, 63, 56]; occ[63] = 3; occ[56] = 4
        care = a._care(1, R)
        dk = max(1.0, a.P["def_kappa"] * R)
        if a._should_shield(owner, upg, occ, frz, base, 1, R, dk, care):
            fires.append(R)
    print("  rival raid-commit history = %2d stays: shield fires at R in %s" % (commit_obs, fires))

# ---------------------------------------------------------------- S1b: home bug, 2-pt home
b2 = base[:]
for c in engine.CORNERS.values():
    b2[c] = 2
fires = []
for R in range(1, 81):
    a, home_of = fresh_agent(b2)
    tr = a.tr; tr.turn = 80 - R + 1; tr.raids[1] = 20
    owner = [0]*64; upg = [0]*64; occ = [0]*64; frz = [0]*64
    for s, c in engine.CORNERS.items(): owner[c] = s
    occ[0] = 2; occ[9] = 1; owner[9] = 1; tr.pos = [9, 0, 63, 56]; occ[63] = 3; occ[56] = 4
    care = a._care(1, R); dk = max(1.0, a.P["def_kappa"] * R)
    if a._should_shield(owner, upg, occ, frz, b2, 1, R, dk, care):
        fires.append(R)
print("  same, 2-point home, committed rival: shield fires at R in", fires)
fires = []
for R in range(1, 81):
    a, home_of = fresh_agent(b2)
    tr = a.tr; tr.turn = 80 - R + 1
    owner = [0]*64; upg = [0]*64; occ = [0]*64; frz = [0]*64
    for s_, c in engine.CORNERS.items(): owner[c] = s_
    occ[0] = 2; occ[9] = 1; owner[9] = 1; tr.pos = [9, 0, 63, 56]; occ[63] = 3; occ[56] = 4
    care = a._care(1, R); dk = max(1.0, a.P["def_kappa"] * R)
    a.rng = 1
    if a._should_shield(owner, upg, occ, frz, b2, 1, R, dk, care):
        fires.append(R)
print("  same, 2-point home, NO history (prior only, rng-dependent mixing): fires at R in", fires)

# ---------------------------------------------------------------- S1c: L1 valuation vs reality
print("\n[S1c] what _should_shield believes an L1 shield saves vs what it really saves")
for R in (60, 40, 20, 10):
    v = 3
    lost = v * 1 * (R - 1) * (1.0 - bot.PARAMS["retake_credit"])
    print("  R=%2d  3-pt L1 cell: modelled income saved %.0f pts; real (committed raider "
          "takes it 3 turns later) %d pts" % (R, lost, 3 * v))

# ---------------------------------------------------------------- S8: off-by-one at R=1
print("\n[S8] final turn (R=1), I stand on a NEUTRAL 3-pt cell; staying claims it and it scores this turn")
a, home_of = fresh_agent(base)
tr = a.tr; tr.turn = 80
owner = [0]*64; upg = [0]*64; occ = [0]*64; frz = [0]*64
for s, c in engine.CORNERS.items(): owner[c] = s
me = 27; occ[me] = 1; tr.pos = [me, 7, 63, 56]; occ[7] = 2; occ[63] = 3; occ[56] = 4
owner[18] = 1   # one own L1 cell elsewhere
print("  base_points here:", base[me])
import time; a._deep = 1.0; a._deadline = time.perf_counter() + 10
act = a._plan_walk(owner, upg, base, home_of, occ, frz, 1, me, 1, 1.0, a._care(1, 1))
print("  bot plays:", act, "(STAY would score +%d)" % base[me])
for R in (2, 3):
    g = a._work_gain(me, 0, base[me], 1, 0, owner, upg, occ, 1, R, 1.0, [1]*4, 0)
    print("  R=%d: claim-in-place modelled at %.2f (x w_claim); true income %d" % (R, g or 0, base[me]*R))

# ---------------------------------------------------------------- S2: stale state, first board missed
print("\n[S2] module state survives into a new game AND the turn-1 call is missed")
import zoo
g1 = engine.Game(base=base)
ag = bot.Agent(seed=1, params={"throttle": 0, "budget_ms": 10000.0})
opp = [zoo.ZOO_BY_NAME["spine"](i) for i in range(3)]
while not g1.over():
    vs = g1.views()
    g1.step([ag(vs[0])] + [opp[i](vs[i+1]) for i in range(3)])
print("  after game 1: tracker turn =", ag.tr.turn)
g2 = engine.Game(base=base)
opp = [zoo.ZOO_BY_NAME["spine"](i+10) for i in range(3)]
Rs = []
first = True
while not g2.over():
    vs = g2.views()
    if first:
        a0 = "SOUTH"; first = False          # turn 1 played by the server, not by us
    else:
        a0 = ag(vs[0]); Rs.append(bot.MAX_TURNS - ag.tr.turn + 1)
    g2.step([a0] + [opp[i](vs[i+1]) for i in range(3)])
print("  game 2: R the bot believed (first 5 turns):", Rs[:5], "... last:", Rs[-1])
print("  game 2 score:", g2.score[0], "vs rivals", g2.score[1:])
