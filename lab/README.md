# lab: a new bot built against an independent opponent field

Work in progress. `bot.py` at the repository root is **not yet replaced**; the
candidate lives in `lab/cand/`. Nothing below has been run on the hold-out
opponents yet, so every number here is a development result.

## What is here

| Path | Purpose |
|---|---|
| `sim.py` | In-process game runner. Physics come from the pinned referee in `simulator/vendor_harness/referee.py`; each seat gets a fresh module and only the four documented inputs. |
| `arena.py`, `ev.py`, `suite.py`, `h2h.py` | Paired comparisons on shared fixtures (same map, seat, token, opponents, opponent seeds), with map-clustered bootstrap intervals. |
| `prof.py`, `diag.py`, `trace.py` | Where points and turns go; turn-by-turn game traces. |
| `check_tracker.py` | Grades the candidate's public-history tracker against the referee's hidden counters. |
| `fields.py` | Opponent fields, and the development / hold-out split (drawn once with a fixed seed before any new bot was designed). |
| `pool/`, `legacy/` | 103 standalone bots recovered from this repository's own archives and branches, plus 20 class-based opponents from the first project phase. |
| `cand/_head.py` + `cand/_tail2.py` | The candidate: tracker half and decision half. `build.py NAME key=value` assembles `cand/NAME.py`. |
| `scratch/` | One-off measurements (solo optimum, raid/shield habits, cell survival by rival distance). |

## Findings so far

1. **The strong bots in this repository are economically identical.** In a field of
   the 17 strongest, mean scores sit within about 100 points and every one of them
   plays "claim, then upgrade the same cell". An offline search puts the best
   possible score from one quadrant at about 2,780; they already reach it. Tuning
   the existing genome cannot find much, which is what the 100,000-game campaign saw.
2. **Un-upgraded cells are only at risk when a rival is close.** Measured over a mixed
   population: 23% lost within five turns at distance 1, 4% at distance 2, under 1%
   at distance 3 or more. Upgraded cells are almost never lost.
3. **Shield timing is predictable.** With a rival one stay from taking an upgraded
   cell, the strong bots shield 95-100% of the time. Stepping to a neighbouring cell
   on that turn makes the shield backfire, which freezes the landlord for two turns
   and leaves every cell it owns unprotected for four.
4. **Raiders are predictable too.** About 93% stay on the decisive turn, so a shield
   one stay early catches them just as reliably and cannot be dodged by a bot that
   only steps aside on the decisive turn.

## The candidate

- Tracker: turn, scores and token are reconstructed exactly; rival progress 99.99%
  and shield cooldowns 99.9% of seat-turns (the remainder are publicly ambiguous).
- Planner: beam search over job sequences compared at a common time horizon, with
  the value of a cell discounted by the measured chance of losing it.
- Opponent model: a posterior over five shield habits per landlord, updated from
  every stand-off anyone has with it, so one or two sightings are enough to adapt.
- Tactics: expected-value shield calls (including one stay early, at random), raids
  that stay or step aside depending on what that landlord is likely to do.

Development results, paired against the current `bot.py` (`cur_e8`), mean rivals
outscored out of 3:

| Field | Current bot | Candidate `zr3` | Paired difference (95% interval) |
|---|---:|---:|---|
| 12 strongest development bots | 1.82 | 2.30 | +0.48 [+0.31, +0.64] |
| 14 mid-strength | 2.27 | 2.51 | +0.24 [+0.06, +0.42] |
| 18 weak | 2.58 | 2.82 | +0.23 [+0.13, +0.33] |
| All development bots mixed | 2.24 | 2.58 | +0.34 [+0.23, +0.46] |
| Strong bots plus copies of the candidate | 1.53 | 1.84 | +0.30 [+0.04, +0.57] |

Head to head it outscores every development opponent more often than not (lowest
0.56 against the previous strongest bots).

## Reproduce

```bash
python3 lab/build.py zr4
python3 lab/suite.py --ref cur_e8 zr4
python3 lab/check_tracker.py lab/cand/zr4.py 300
```
