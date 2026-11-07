# Opponent field for Zone Rush

25 standalone opponent bots, each a single stdlib-only file exposing `act(state)`, named `opp_<style>_<nn>.py`
(`nn` counts within a style). They are meant to be a field that is **independent of our own bot**.

## Provenance

Written only from two sources: the rulebook text (Section 2, Zone Rush) and the starter-kit README
(`work/official_README.md` inside `outputs/Evolution_TestKit.zip` on `research/evolution-2026-11-07`).
No bot in this repo or its branches (`bot.py`, `mybot.py`, `harness/bots/*`, branch bots, the kit's bots) was
read, copied or imported, and no file imports a sibling. Each file carries its own copy of any helper it needs,
so the bots differ in structure as well as in strategy.

## Conventions every bot follows

- **Board layout:** accepts `state.board` as either a flat list of 64 cells or an 8x8 nested list (lists or tuples).
- **Cell fields used:** only the documented ones: `occupant`, `owner`, `is_upgraded`, `is_home`, `is_frozen`, `base_points`.
- **No turn number:** none reads or counts the game turn (the server does not provide one).
  - The "late" raider decides lateness from how crowded the board is.
  - The shield bots count only their own calls since their last `SHIELD`, for the 4-turn cooldown.
  - They also check `"SHIELD" in state.legal_actions`.
- **Output:** always one string from `state.legal_actions`, falling back to `"STAY"`. The one exception is `opp_buggy_01`, on purpose.
- **Homes:** no bot tries to capture a home. No bot deliberately spends turns upgrading its home, because the rules don't say it is possible.
  The turtle just sits on it.
- **Closed cells:** most bots avoid stepping into a cell that is occupied at the start of the turn (blocked moves count as `STAY`).
  The five naive bots and `opp_buggy_01` don't check the next cell.
- **Memory:** bots marked *stateful* keep a module-level dict. They reset it when the number of owned cells on the board drops,
  which cannot happen inside one game, so a fresh game in the same process starts clean.
  **If a harness runs the same file for two seats of one game in one process, load a separate module instance per seat.**
  Otherwise the two seats share memory.

## The 25 bots

| # | File | Style | What it does | Stateful |
|---|------|-------|--------------|----------|
| 1 | `opp_naive_01.py` | naive | Walks to the nearest cell it doesn't own (reading-order tie-break), STAYs on any non-home cell it doesn't own. Vertical-first steps, ignores closed cells. No shield, no upgrades. | no |
| 2 | `opp_naive_02.py` | naive | Random walker: STAYs on non-home cells it doesn't own, otherwise a random move; 30% chance to linger on its own level-1 cell. Never shields. | no (random) |
| 3 | `opp_naive_03.py` | naive | Always heads for the highest-point cell it doesn't own (ties: nearest), column-first, STAYs to capture. Never upgrades. | no |
| 4 | `opp_naive_04.py` | naive | Sweeper: targets the first cell in reading order (row 0 left to right, then row 1...) it doesn't own. Seats starting low walk a long way. | no |
| 5 | `opp_naive_05.py` | naive | Marches to the nearest of the four centre cells and STAYs there for the rest of the game (captures and upgrades that one cell). | no |
| 6 | `opp_farmer_01.py` | farmer | Quadrant farmer: claims its home's 4x4 quadrant best-value-first, then upgrades all of it, then spills into neutral cells outside (nearest first). BFS around closed cells. | no |
| 7 | `opp_farmer_02.py` | farmer | Spine farmer: central columns 3-4 first, then 2 and 5, then the rest. Upgrades only prime spine cells (base >= 2) once it owns 6+ cells, everything else only when nothing neutral is left. | no |
| 8 | `opp_farmer_03.py` | farmer | Centre-first, ring by ring outwards. Upgrade-heavy: upgrades every 2+ point cell the moment it owns it; 1-point cells only after the neutrals run out. | no |
| 9 | `opp_farmer_04.py` | farmer | Efficiency farmer: ranks claims as `base / (distance + 1)` and upgrades as `base / (distance + 3)` and always takes the best ratio (it will walk past a 1-point cell for a nearby 3). | no |
| 10 | `opp_raider_01.py` | raider (early) | Skips farming and rushes rival land: picks the rival cell with the best `8*base*level / (distance + stays)`. With no rival land yet it drifts toward the nearest rival corner, claiming neutral cells that are valuable or near that corner. Never upgrades. | no |
| 11 | `opp_raider_02.py` | raider (late) | Farms and upgrades until the board is crowded (<= 20 neutral cells or >= 14 rival-owned non-home cells), then hunts rival upgraded cells (biggest bonus minus distance), level-1 cells if none. | no |
| 12 | `opp_raider_03.py` | raider (opportunistic) | Farms by default; raids a rival cell only when its payoff per turn is >= 4.0 (>= 2.5 if the owner is currently frozen and so cannot shield). Upgrades 3-point cells it owns (any cell once nothing neutral is left). | no |
| 13 | `opp_raider_04.py` | raider (level-1 only) | Raids only rival non-upgraded cells (one STAY, hit and run), prefers high base value; claims neutral land otherwise; never touches level-2 cells, never upgrades. | no |
| 14 | `opp_shield_01.py` | shield (spammer) | Raises SHIELD the instant it is allowed, with or without anyone on its land (so it often backfires, including on its first turn), and farms the nearest neutral cell in between. | cooldown |
| 15 | `opp_shield_02.py` | shield (turtle) | Never strays more than 2 steps from home: claims and upgrades the nearby cells, then sits on its home. Shields at the first unfrozen rival on any of its land (home included). | cooldown |
| 16 | `opp_shield_03.py` | shield (on sight) | Farms the whole board (neutral first, upgrades 2+ point cells) but shields the moment any unfrozen rival stands on one of its cells (home included), whether or not that rival is actually staying. | cooldown |
| 17 | `opp_bait_01.py` | bait/squat | Patient squatter: goes to the nearest rival upgraded cell, STAYs two of the three turns a take needs, steps off, farms/upgrades for a few turns, repeats. Never sits on level-1 rival cells. | dwell, away |
| 18 | `opp_bait_02.py` | bait/squat | Twitchy squatter: BFS to the nearest rival cell, sits 1-2 turns (random) on upgraded ones and 0 on level-1 ones, then hops to the next rival cell or any free neighbour. Only farms when there is no rival land. | dwell, limit |
| 19 | `opp_bait_03.py` | bait/squat | Leader squatter: targets the rival with the most land, sits two turns on its nearest upgraded cell, steps off toward home, farms for ~6 turns (neutral near home first, then upgrades), repeats. | dwell, rest |
| 20 | `opp_adaptive_01.py` | adaptive | Grudge keeper: +1 grudge per cell a rival takes from it (+2 if upgraded), reduced when it takes one back. Shields known offenders (or anyone on an upgraded cell) and raids the worst offender; farms in peace. | grudges, cooldown, board snapshot |
| 21 | `opp_adaptive_02.py` | adaptive | Threat tracker: times how long each rival lingers on its land and shields on the last turn that still stops the take (1st sighting on a level-1 cell, 3rd on a level-2 cell). Builds an aggro score per rival, raids the worst once it is high enough. | streaks, aggro, cooldown |
| 22 | `opp_adaptive_03.py` | adaptive | Ledger enforcer: keeps a points ledger of what rivals have taken (`8*base*level`), repaid when it takes cells back and slowly forgiven. Answers with proportional raids on its biggest debtor, never shields. | ledger, board snapshot |
| 23 | `opp_buggy_01.py` | buggy | **Illegal action.** Greedy neutral grabber whose step helper sometimes tries a diagonal move, so it returns e.g. `"SOUTHEAST"` on about 12% of the turns where it still needs to move along both axes. The server counts that as `STAY`. | no (random) |
| 24 | `opp_buggy_02.py` | buggy | **Slow.** Sound nearest-neutral farmer that on about 12% of turns sleeps 140-160 ms before answering (legal, but close to the 200 ms limit). | no (random) |
| 25 | `opp_buggy_03.py` | buggy | **Oscillator.** Walks to the central pair (3,3)/(3,4) (or (4,3)/(4,4) for bottom-row seats) and shuttles between the two cells forever, never staying, so it never claims anything. STAYs if its partner cell is occupied. | no |

Counts by style: naive 5, farmer 4, raider 4, shield 3, bait 3, adaptive 3, buggy 3.

## How they were checked

A throwaway script (not committed) imported every file and called `act` on one fake state, once with a nested board and once with a flat one.
The state object exposed only the four documented attributes, so reading anything else (such as a turn counter) would have raised.
Results:

- All 25 import and return a legal action for both layouts.
- None raised, mutated the board or `legal_actions`, or imported anything outside the standard library.
- Every docstring is one line.
- Every call took under 1 ms. `opp_buggy_02`'s stall is random and did not trigger in that run (see the forced check below).

Beyond that single call, a few extra static snapshots were used, with no game loop and no simulation:

- Scenarios included standing on a rival level-2 cell, an unfrozen rival parked on our land, and a frozen bot with `STAY` as the only legal action.
- A 12-start-cell position sweep covered edges and corners.
- Two-board sequences checked raid detection in the adaptive bots.

The three buggy bots were additionally checked with their flaw forced on, because it is probabilistic:

- `opp_buggy_01` returned the illegal `NORTHEAST`.
- `opp_buggy_02` took about 142 ms.
- `opp_buggy_03` shuttled EAST/WEST between (3,3) and (3,4).

**Not done:** no full games and no tournament runs, so how strong or weak each bot is in play is untested.
