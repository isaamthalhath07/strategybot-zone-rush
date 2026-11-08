"""Validate engine.py against every worked example and invariant in the rulebook."""
import random
import engine
from engine import Game, N


def mk(positions=None, rules=None, token=1):
    g = Game(rules=rules, start_token=token)
    if positions:
        for i, p in enumerate(positions):
            g.pos[i] = p
    return g


def rc(r, c):
    return r * N + c


ok = 0
fail = []


def check(name, cond, extra=""):
    global ok
    if cond:
        ok += 1
    else:
        fail.append("%s %s" % (name, extra))


# ---------------------------------------------------------------- 2.4 the raid
# Red (seat 1) attacks Blue's (seat 2) upgraded 3-point cell.
g = mk([rc(3, 2), rc(3, 4), engine.CORNERS[3], engine.CORNERS[4]])
tgt = rc(3, 3)
g.base[tgt] = 3
g.owner[tgt] = 2
g.upg[tgt] = 1
g.income[1] = 6
s0 = g.score[0]
g.step(["EAST", "STAY", "STAY", "STAY"])          # turn 1: Red arrives
check("raid.arrive_pos", g.pos[0] == tgt)
check("raid.arrive_no_progress", g.prog[0] == 0, "arriving must not count")
check("raid.not_taken_yet", g.owner[tgt] == 2)
g.step(["STAY", "STAY", "STAY", "STAY"])          # turn 2: progress 1 of 3
check("raid.prog1", g.prog[0] == 1, g.prog[0])
g.step(["STAY", "STAY", "STAY", "STAY"])          # turn 3: progress 2 of 3
check("raid.prog2", g.prog[0] == 2, g.prog[0])
check("raid.still_blue", g.owner[tgt] == 2)
g.step(["STAY", "STAY", "STAY", "STAY"])          # turn 4: take + bonus 8*3*2 = 48
check("raid.taken", g.owner[tgt] == 1, g.owner[tgt])
check("raid.dropped_to_L1", g.upg[tgt] == 0)
gained = g.score[0] - s0
check("raid.bonus_48", gained >= 48, "total gained %d (48 bonus + income)" % gained)

# ------------------------------------------------- 2.6 shield cancels the raid
g = mk([rc(3, 2), rc(3, 4), engine.CORNERS[3], engine.CORNERS[4]])
g.base[tgt] = 3
g.owner[tgt] = 2
g.upg[tgt] = 1
g.step(["EAST", "STAY", "STAY", "STAY"])          # Red arrives
g.step(["STAY", "STAY", "STAY", "STAY"])          # progress 1
check("shield.prog_before", g.prog[0] == 1)
g.step(["STAY", "SHIELD", "STAY", "STAY"])        # Blue shields
check("shield.progress_wiped", g.prog[0] == 0, g.prog[0])
check("shield.raider_frozen_2", g.frozen[0] == 2, g.frozen[0])
check("shield.cell_held", g.owner[tgt] == 2)
check("shield.cooldown_4", g.cd[1] == 4, g.cd[1])
check("shield.shielder_free", g.frozen[1] == 0)
check("shield.no_shield_in_legal", "SHIELD" not in g.legal(1))
# the raider can only STAY for exactly two turns
g.step(["NORTH", "STAY", "STAY", "STAY"])
check("shield.frozen_cannot_move", g.pos[0] == tgt, "frozen bot must stay put")
g.step(["NORTH", "STAY", "STAY", "STAY"])
check("shield.frozen_still", g.pos[0] == tgt)
g.step(["NORTH", "STAY", "STAY", "STAY"])
check("shield.thaws_after_2", g.pos[0] == rc(2, 3), "should move on the 3rd turn")
# cooldown: shielded on turn 3, so legal again on turn 8
check("shield.cd_counts_down", g.cd[1] == 1, g.cd[1])
g.step(["STAY", "STAY", "STAY", "STAY"])
check("shield.cd_expired", g.cd[1] == 0 and "SHIELD" in g.legal(1))

# ------------------------------------------------------ 2.6 backfire + frozen
g = mk([rc(0, 2), rc(4, 4), engine.CORNERS[3], engine.CORNERS[4]])
g.step(["STAY", "SHIELD", "STAY", "STAY"])        # nobody on seat 2's land
check("backfire.frozen_2", g.frozen[1] == 2, g.frozen[1])
check("backfire.cooldown", g.cd[1] == 4)

# a shield that only reaches an already-frozen rival also backfires
g = mk([rc(3, 3), rc(3, 4), engine.CORNERS[3], engine.CORNERS[4]])
g.owner[rc(3, 3)] = 2
g.frozen[0] = 2
g.step(["STAY", "SHIELD", "STAY", "STAY"])
check("backfire.frozen_rival_doesnt_count", g.frozen[1] == 2, g.frozen[1])

# ------------------------------------------------------------ 2.3 no swapping
g = mk([rc(3, 3), rc(3, 4), engine.CORNERS[3], engine.CORNERS[4]])
g.step(["EAST", "WEST", "STAY", "STAY"])
check("noswap.both_held", g.pos[0] == rc(3, 3) and g.pos[1] == rc(3, 4))

# a cell is closed even when its occupant is leaving
g = mk([rc(3, 2), rc(3, 3), engine.CORNERS[3], engine.CORNERS[4]])
g.step(["EAST", "EAST", "STAY", "STAY"])
check("closed.vacating_still_closed", g.pos[0] == rc(3, 2), "must not follow")
check("closed.occupant_moved", g.pos[1] == rc(3, 4))

# ------------------------------------------- 2.3 contested cell: owner wins
g = mk([rc(3, 2), rc(3, 4), engine.CORNERS[3], engine.CORNERS[4]], token=2)
mid = rc(3, 3)
g.owner[mid] = 1                                  # seat 1 owns it
g.step(["EAST", "WEST", "STAY", "STAY"])
check("contest.owner_wins", g.pos[0] == mid and g.pos[1] == rc(3, 4))

# ------------------------------- 2.3 contested cell: token order 3->4->1->2
g = mk([rc(3, 2), engine.CORNERS[2], engine.CORNERS[3], rc(3, 4)], token=3)
g.step(["EAST", "STAY", "STAY", "WEST"])          # seats 1 and 4 both want mid
check("contest.token_order", g.pos[3] == mid and g.pos[0] == rc(3, 2),
      "seat4 should win from token seat 3; got p1=%s p4=%s" % (g.pos[0], g.pos[3]))
# and with the token on seat 1, seat 1 should win the same race
g = mk([rc(3, 2), engine.CORNERS[2], engine.CORNERS[3], rc(3, 4)], token=1)
g.step(["EAST", "STAY", "STAY", "WEST"])
check("contest.token_order2", g.pos[0] == mid and g.pos[3] == rc(3, 4))

# a lost contest still counts as a STAY, so it accrues progress
g = mk([rc(3, 2), engine.CORNERS[2], engine.CORNERS[3], rc(3, 4)], token=4)
g.owner[rc(3, 2)] = 1
g.step(["EAST", "STAY", "STAY", "WEST"])
check("contest.loser_gets_stay", g.prog[0] == 1, "lost contest -> STAY -> progress")

# ------------------------------------------------------------- 2.4 / 2.5 basics
g = mk([rc(3, 2), engine.CORNERS[2], engine.CORNERS[3], engine.CORNERS[4]])
g.step(["STAY", "STAY", "STAY", "STAY"])          # neutral: 1 stay
check("neutral.one_stay", g.owner[rc(3, 2)] == 1)
check("neutral.level1", g.upg[rc(3, 2)] == 0)
for _ in range(3):                                # upgrade: 3 more stays
    g.step(["STAY", "STAY", "STAY", "STAY"])
check("upgrade.three_stays", g.upg[rc(3, 2)] == 1, "upg=%d" % g.upg[rc(3, 2)])
check("upgrade.doubles_income", g.income[0] == g.base[engine.CORNERS[1]] + 2 * g.base[rc(3, 2)],
      g.income[0])

# rival level-1 cell: a single stay takes it, with a bonus of 8*v*1
g = mk([rc(3, 3), engine.CORNERS[2], engine.CORNERS[3], engine.CORNERS[4]])
g.owner[rc(3, 3)] = 2
g.base[rc(3, 3)] = 3
g.income[1] = 3
s0 = g.score[0]
g.step(["STAY", "STAY", "STAY", "STAY"])
check("raidL1.one_stay", g.owner[rc(3, 3)] == 1)
check("raidL1.bonus_24", g.score[0] - s0 >= 24, g.score[0] - s0)

# homes can never be taken
g = mk([engine.CORNERS[2], rc(1, 7), engine.CORNERS[3], engine.CORNERS[4]])
for _ in range(6):
    g.step(["STAY", "STAY", "STAY", "STAY"])
check("home.never_taken", g.owner[engine.CORNERS[2]] == 2)

# ------------------------------------------------- 2.7 scoring every turn
g = Game()
g.step(["STAY"] * 4)
check("score.homes_pay_each_turn", all(g.score[i] == g.base[engine.CORNERS[i + 1]] for i in range(4)),
      g.score)
g2 = Game()
for _ in range(80):
    g2.step(["STAY"] * 4)
check("score.80_turns", g2.turn == 81 and g2.over())
# 2 turns at v, then the home upgrades on turn 3 and pays 2v for the remaining 78
hv = g.base[engine.CORNERS[1]]
check("score.home_upgrades_itself", g2.score[0] == 2 * hv + 78 * 2 * hv, g2.score[0])
g3 = Game(rules={"home_upgradable": False})
for _ in range(80):
    g3.step(["STAY"] * 4)
check("score.home_not_upgradable_flag", g3.score[0] == 80 * hv, g3.score[0])

# -------------------------------------- 3.2 / 5.3 ranking is round-specific
# The page-9 example has equal 380 scores but 14 vs 11 cells. That breaks
# the Round 2 tie; Round 1 explicitly scores the same pair as a draw.
from arena import pairwise_wins
g = Game()
g.score = [412, 380, 380, 201]
g.owner = [1] * 10 + [2] * 14 + [3] * 11 + [4] * 9 + [0] * 20
check("ranking.round1_ignores_cell_tiebreak", g.places() == [1, 2.5, 2.5, 4],
      g.places())
check("ranking.round1_equal_score_is_pairwise_draw",
      pairwise_wins(g.places()) == [(3, 0, 0), (1, 1, 1), (1, 1, 1), (0, 0, 3)])
check("ranking.round2_cells_break_score_tie", g.places(round_number=2) == [1, 2, 3, 4])
check("ranking.round2_legacy_keyword", g.places(round2=True) == [1, 2, 3, 4])
check("ranking.round2_legacy_positional_bool", g.places(True) == [1, 2, 3, 4])
check("ranking.round1_legacy_keyword", g.places(round2=False) == [1, 2.5, 2.5, 4])
check("ranking.round1_legacy_positional_bool", g.places(False) == [1, 2.5, 2.5, 4])

g.owner = [1] * 10 + [2] * 11 + [3] * 11 + [4] * 9 + [0] * 23
pool_places = g.places(round_number=2)
check("ranking.round2_pool_exact_ties_share", pool_places == [1, 2.5, 2.5, 4])
check("ranking.round2_shared_pool_points",
      [4 - p for p in pool_places] == [3, 1.5, 1.5, 0])
check("ranking.round2_knockout_uses_round1_rank_last",
      g.places(round_number=2, round1_ranks=[4, 3, 1, 2]) == [1, 3, 2, 4])
check("ranking.round2_legacy_alias_keeps_knockout_tiebreak",
      g.places(round2=True, round1_ranks=[4, 3, 1, 2]) == [1, 3, 2, 4])

g.score = [100] * 4
check("ranking.round1_four_way_tie", g.places() == [2.5] * 4)
g.owner = [1] * 4 + [2] * 4 + [3] * 4 + [4] * 4 + [0] * 48
check("ranking.round2_pool_four_way_tie", g.places(round_number=2) == [2.5] * 4)
check("ranking.round2_knockout_four_way_tie",
      g.places(round_number=2, round1_ranks=[3, 1, 4, 2]) == [3, 1, 4, 2])
for bad_args in ({"round_number": 0}, {"round_number": 3},
                 {"round2": 1}, {"round_number": 2, "round2": False},
                 {"round1_ranks": [1, 2, 3, 4]},
                 {"round_number": 2, "round1_ranks": [1, 2, 3]}):
    try:
        g.places(**bad_args)
    except ValueError:
        ok += 1
    else:
        fail.append("ranking.invalid_format_accepted %r" % bad_args)

# ------------------------------------------- token rotation 1->2->3->4->1
g = Game(start_token=1)
seen = []
for _ in range(5):
    seen.append(g.token)
    g.step(["STAY"] * 4)
check("token.rotation", seen == [1, 2, 3, 4, 1], seen)

# ------------------------------------------------------------- shield catches many
g = Game()
g.pos[0] = rc(3, 3)
g.pos[1] = rc(3, 4)
g.pos[2] = rc(4, 4)
g.owner[rc(3, 4)] = 1
g.owner[rc(4, 4)] = 1
g.step(["SHIELD", "STAY", "STAY", "STAY"])
check("shield.catches_multiple", g.frozen[1] == 2 and g.frozen[2] == 2,
      (g.frozen[1], g.frozen[2]))

# a rival camped on your HOME is catchable too
g = Game()
g.pos[1] = rc(1, 0)
g.step(["SHIELD", "SOUTH", "STAY", "STAY"])       # seat2 moves off, so this backfires
check("shield.backfire_when_target_leaves", g.frozen[0] == 2, g.frozen[0])
g = Game()
g.pos[1] = rc(1, 0)
g.owner[rc(1, 0)] = 1
g.step(["SHIELD", "STAY", "STAY", "STAY"])
check("shield.catch_on_own_land", g.frozen[1] == 2 and g.frozen[0] == 0)

# ------------------------------------------------- illegal / frozen handling
g = Game()
g.step(["NORTH", "STAY", "STAY", "STAY"])         # seat 1 at (0,0) cannot go north
check("illegal.offboard_is_stay", g.pos[0] == engine.CORNERS[1])
g = Game()
g.cd[0] = 2
g.step(["SHIELD", "STAY", "STAY", "STAY"])
check("illegal.shield_on_cd_is_stay", g.frozen[0] == 0 and g.cd[0] == 1)

# ------------------------------------------------------------------- fuzzing
rnd = random.Random(7)
for trial in range(400):
    base = engine.make_map(seed=trial)
    g = Game(base=base, start_token=rnd.randint(1, 4))
    prev = g.score[:]
    while not g.over():
        acts = []
        for i in range(4):
            la = g.legal(i)
            acts.append(rnd.choice(la) if rnd.random() < 0.9 else "GARBAGE")
        g.step(acts)
        # invariants
        if len(set(g.pos)) != 4:
            fail.append("fuzz.two_bots_same_cell trial %d turn %d" % (trial, g.turn))
            break
        if any(not (0 <= p < 64) for p in g.pos):
            fail.append("fuzz.offboard trial %d" % trial)
            break
        if any(g.score[i] < prev[i] for i in range(4)):
            fail.append("fuzz.score_decreased trial %d" % trial)
            break
        if any(g.owner[c] != s for s, c in engine.CORNERS.items()):
            fail.append("fuzz.home_changed_owner trial %d" % trial)
            break
        inc = [0, 0, 0, 0]
        for p in range(64):
            if g.owner[p]:
                inc[g.owner[p] - 1] += g.base[p] * (2 if g.upg[p] else 1)
        if inc != g.income:
            fail.append("fuzz.income_desync trial %d turn %d %s vs %s"
                        % (trial, g.turn, inc, g.income))
            break
        if any(f < 0 or f > 2 for f in g.frozen) or any(c < 0 or c > 4 for c in g.cd):
            fail.append("fuzz.counter_range trial %d" % trial)
            break
        if any(pr < 0 or pr > 3 for pr in g.prog):
            fail.append("fuzz.progress_range trial %d %s" % (trial, g.prog))
            break
        prev = g.score[:]
check("fuzz.400_games", True)

# -------------------------------------------------------- mirrored-map property
for seed in range(60):
    b = engine.make_map(seed=seed)
    good = all(b[r * 8 + c] == b[r * 8 + 7 - c] == b[(7 - r) * 8 + c] == b[(7 - r) * 8 + 7 - c]
               for r in range(8) for c in range(8))
    if not good:
        fail.append("map.not_mirrored seed %d" % seed)
        break
    if not all(1 <= v <= 3 for v in b):
        fail.append("map.value_range seed %d" % seed)
        break
check("map.mirrored_and_in_range", True)

print("passed: %d" % ok)
if fail:
    print("FAILED %d:" % len(fail))
    for f in fail:
        print("  -", f)
else:
    print("ALL CHECKS PASS")
if fail:
    raise SystemExit(1)
