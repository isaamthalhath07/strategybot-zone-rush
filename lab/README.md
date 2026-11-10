# lab: how the released bot was built and measured

The root `bot.py` is `cand/_head.py` + `cand/_tail2.py` concatenated by
`release.py`. Everything used to design and judge it is in this folder.

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

Results, paired against the previous release (`cur_e8`), mean rivals outscored
out of 3. Development rows are fresh fixtures drawn after the last design decision;
hold-out rows are opponents never used during design, run once after the bot was
frozen (`results/dev_suite_final.json`, `results/holdout_run1.json`).

| Opponents | Previous | New | Paired difference (95% interval) |
|---|---:|---:|---|
| Development, 12 strongest | 1.80 | 2.25 | +0.45 [+0.26, +0.66] |
| Development, 14 mid-strength | 2.08 | 2.30 | +0.22 [+0.00, +0.44] |
| Development, 18 weak | 2.65 | 2.91 | +0.26 [+0.14, +0.38] |
| Development, all 44 mixed | 2.28 | 2.48 | +0.20 [+0.06, +0.33] |
| Development strong plus copies of the new bot | 1.57 | 1.99 | +0.42 [+0.12, +0.73] |
| **Hold-out, 5 strong** | 1.62 | 2.08 | **+0.46 [+0.29, +0.63]** |
| **Hold-out, 6 mid-strength** | 2.38 | 2.64 | **+0.26 [+0.13, +0.40]** |
| **Hold-out, 8 weak** | 2.73 | 2.88 | **+0.16 [+0.07, +0.25]** |
| **Hold-out, all 19 mixed** | 2.34 | 2.51 | **+0.18 [+0.07, +0.28]** |

Head to head it outscores every development opponent more often than not, and no
pool bot does better than it against a table of three copies of it.

## Choices that were tested and rejected

- **Weighting loss risk more heavily** (1.5x the measured curves): -0.36 on the
  strong field on fresh fixtures. Half weight: -0.11. The measured value stays.
- **Longer or wider plan search, higher value of time**: better alone on an empty
  board, worse in contested games (-0.2 on the strong field), so the cheap setting
  stays.
- **Claim-first variants of the previous bot**: -0.5 to -1.2; its cells get raided.

## Rule readings

The official reading (shields catch rivals whose effective action is STAY) is what
the bot is built for. Against the previous release under other readings, same
fixtures: catch by presence +0.00, legal list omits occupied cells +0.43, no
progress reset after a claim +0.31, home not upgradable +0.40, frozen stays count
+0.45, lost contest is not a stay +0.44. Under the presence reading the bot
notices the first time a successful move is caught and stops stepping onto the
same landlord's cells.

## Reproduce

```bash
python3 lab/build.py zr6                  # the released configuration
python3 lab/suite.py --ref cur_e8 zr6     # five development fields
python3 lab/check_tracker.py bot.py 300   # tracker against referee truth
python3 lab/release.py                    # rebuild bot.py and refresh its fingerprint
python3 tools/check_release.py            # 142 tests
```
