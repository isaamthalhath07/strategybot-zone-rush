# Progress log

Running record of what was done, what was found and what it means. Newest entries
at the bottom. Every number here is reproducible from files in this repository.

Score used throughout: **rivals outscored per game, 0 to 3** (ties count half).
1.5 is break-even among equals.

---

## 1. Every bot in the repository's history, ranked (2026-11-10)

Files: `lab/history_ranking/` (`RANKING.md` is the readable report,
`full_ranking.csv` the full table, the `.py` files are the scripts).

- 595 distinct playable `act(state)` files recovered from all 60 commits on all 13
  branches, including 470 found only inside source archives committed in history.
- 35,616 games on the pinned referee under the confirmed STAY-only Shield rule, one
  process per seat, 200 ms per turn enforced.
- Result: **Racer** (`tester_bots/racer.py`) 2.36 and **Blocker**
  (`tester_bots/blocker.py`) 2.32 were the best existing bots; the shipped root
  `bot.py` scored 1.99 and placed 19th of 20 finalist files. Racer minus `bot.py` on
  identical games: +0.36, 95% interval [+0.22, +0.52].
- Caveat that matters for everything below: that ranking used four to six fixed
  opponent line-ups on one map generator. Which bot is "best" depends on the field.

## 2. Review of commit 5031014 (lab harness and candidate `zr4`)

What the commit contains: an in-process harness (`lab/sim.py`), a 123-bot opponent
pool with a development / hold-out split (`lab/fields.py`), and a new candidate bot
in `lab/cand/` (`zr4` = `_head.py` + `_tail2.py`). Its hold-out was never run.

Reproduced its development numbers exactly (`python3 lab/suite.py --ref cur_e8
a_novel_b_racer a_novel_b_blocker zr3 zr4`, 2,850 games):

| Focal bot | elite | mid | weak | mix | self |
|---|---:|---:|---:|---:|---:|
| current `bot.py` (`cur_e8`) | 1.82 | 2.27 | 2.58 | 2.24 | 1.48 |
| Racer | 1.77 | 2.18 | 2.85 | 2.33 | 1.41 |
| Blocker | 1.81 | 2.27 | 2.85 | 2.31 | 1.58 |
| `zr3` | 2.30 | 2.48 | 2.81 | 2.59 | 1.78 |
| **`zr4`** | **2.37** | **2.53** | **2.83** | **2.56** | **1.84** |

`zr4` minus `cur_e8`: elite +0.55 [+0.39, +0.70], mid +0.26 [+0.05, +0.47],
weak +0.25 [+0.15, +0.35], mix +0.32 [+0.19, +0.46], self +0.35 [+0.07, +0.61].

Head to head on 600 development games (`lab/h2h.py`): `zr4` outscores every
development opponent more often than not; its closest matchups are UltimateBot
(0.54), research_correctness (0.58) and Blocker (0.60).

Timing in isolated worker processes (24 games): mean 1.4 ms per call, worst
9.9 ms, no faults. The limit is 200 ms.

### Findings from the review

1. **These are all in-sample numbers.** `zr4` was designed against the development
   fields, so its lead there says nothing yet about overfitting.
2. **The lab hold-out is not independent of development.** `HOLDOUT_ELITE` contains
   Feint (same code base as Racer and Blocker, which are development bots) and
   `v2_bot_191059b37141` (byte-for-byte Blocker with one seat reseeded). A pass on
   that split alone would be weak evidence.
3. **Racer and Blocker do not dominate in the lab's fields.** In section 1 they beat
   `cur_e8` by 0.3; on the lab's development elite field they are level with it.
   Different maps and opponents, different order. This is the reason the final test
   below spans several unrelated opponent sets and map families.
4. **492 bots in the repository's history were never in the lab pool**, so the
   candidate has never met them. They include the 20 bots pasted from ChatGPT and
   Gemini, 12 procedurally generated opponent families the pool has no member of,
   the six "human-like" exploiters and Zenith from the Apex work, and independent
   challengers written from the rulebook. These form the external test.
5. **Engineering gaps in `zr4`** to close before it can ship: one module-level
   memory shared by all seats (breaks if a server runs two seats in one process),
   it returns plain strings even if the server hands it action objects, and its
   fallback on an internal error is STAY rather than a working policy.

## 3. Protocol for the rest of the work

The requirement is the best bot that does **not** overfit, in a field where every
other team also used AI. So:

- **Development set** (already used): `fields.DEV_*`. All design and tuning
  decisions use only this.
- **Test sets** (not touched until the candidate is frozen and the plan is
  committed): the lab hold-out, plus the external bots from finding 4, split once
  by seeded shuffle into a test half and an untouched reserve half.
- Test games use fresh maps, map families never used in development, all four
  seats and token starts, and the referee's alternative rule readings.
- The candidate, the current `bot.py`, Racer and Blocker all play the identical
  fixtures, so differences are paired.
- The shipping rule is written down and committed before the test is run.

## 4. Hardened candidate `zr5` (same decisions, safe to deploy)

`zr5` = `zr4` plus deployment fixes only. On the documented interface it is
**move-for-move identical** to `zr4`: 160 games, 12,800 decisions, zero differences
(`python3 lab/equiv.py zr4 zr5 --maps 40`).

What changed:

- one memory per seat instead of one per module, so a server that runs several seats
  in one process cannot mix their histories;
- it answers with the server's own action object (lower-case strings, Enum members)
  instead of always returning an upper-case string;
- cells may be bare 6-tuples; homes the server reports as unowned are attributed
  to their seat;
- an internal error no longer returns STAY: that seat's memory is dropped and
  rebuilt from the board, and a stateless greedy policy plays the turn;
- a turn that runs longer than 60 ms narrows every later search (never triggered in
  testing: mean 1.4 ms, worst 9.9 ms).

Robustness matrix (`python3 lab/robust.py zr5 zr4 cur_e8 a_novel_b_racer`, saved
in `lab/results/robust.txt`): 22 input or rule variations and 4 deployment modes,
four full games each.

| Bot | Conditions passed (of 26) | Fails on |
|---|---:|---|
| **`zr5`** | **26** | none |
| `zr4` | 21 | lower-case actions, Enum actions, bare-tuple cells, homes unowned, one module for four seats |
| current `bot.py` | 25 | bare-tuple cells |
| Racer | 16 | flat boards, dict cells, string `bot_id`, lower-case and Enum actions, missing token flag, dict state, bare tuples, **second game in the same module** |

Finding: **Racer cannot be shipped as it is.** It plays a second game in the same
process with the first game's memory and collapses, and it breaks on most input
variations. Its strength numbers in section 1 hold only on the exact documented
interface with a fresh process per game.

A development-only sensitivity sweep (`lab/sensitivity.py`) is running; results in
the next entry.

## 5. Opponents the candidate has never met

Built before freezing the candidate; no candidate game has been played against any
of them.

- `lab/ext/` (`python3 lab/make_ext.py`): **85 bots from this repository's history
  that were never in `lab/pool`**: 20 pasted from ChatGPT and Gemini, 42 generated
  challengers from 12 families the pool has no member of, 6 evolution-league rival
  types, 8 "outsider" designs, 2 independent challengers, 6 human-like exploiters
  and Zenith. Split once (seed 20261111) into EXT1, 40 bots for the test, and EXT2,
  45 bots held in reserve. Generated families were split whole.
- `lab/stress/` (`python3 lab/make_stress.py`): 14 new bots on one small economy,
  differing only in Shield habit (never, on sight, decisive, a stay early, coin
  flip, mixed) and raid habit (none, level-1 only, everything, feint, endgame only,
  grudge, cooldown sniping, swarm). They exist to break the assumptions an adaptive
  bot leans on.
- `lab/sim.py`: seven new map families reserved for the test (`flat`, `centre`,
  `edges`, `stripes`, `checker`, `sparse`, `rich`). Development fixtures are
  unchanged by the edit (checked).
- Smoke run against development bots only: all 85 external and 14 stress bots load
  and play with zero faults.
- `lab/final_test.py`: the test runner. Four focal bots (candidate, current
  `bot.py`, Racer, Blocker) on identical fixtures over nine fields, plus five
  alternative rule readings.

## 6. Development sensitivity sweep: is the candidate tuned on a knife-edge?

`python3 lab/sensitivity.py` (16,720 games, development opponents only, fresh
fixture seed 300; table in `lab/results/sensitivity_dev.txt`). One setting moved at a
time, difference from the unmodified candidate per field with 95% intervals.

On these fresh development fixtures the candidate scores elite 2.19, mid 2.46,
weak 2.87, mix 2.56, self 1.82. On the fixtures the previous session tuned on
(seed 100) the elite figure was 2.37, so about 0.18 of that headline was the
tuning fixtures; the other fields did not move.

| Setting moved | Effect |
|---|---|
| `raid_exec` 0.7 / 1.0 | flat (worst -0.25 on the self field at 1.0) |
| `l1_delay` 0.1 / 0.6 | flat, all within +/-0.03 |
| `shield_margin` 0.7 / 1.4 | flat, all within +/-0.05 |
| `early_shield` 0 / 1 | flat; 0 helps mix (+0.07) and hurts self (-0.09) |
| `denial_floor` 0 / 0.3 | 0 is as good; 0.3 costs 0.16 on elite |
| `tail` 0.3 / 0.9 | flat within noise |
| `horizon` 12 / 22 | 22 is as good; 12 costs 0.19 on elite |
| `beam` 8 / 28 | 28 is as good; 8 costs 0.35 on self |
| **`hazard` 0.5 / 2.0** | **0.5 costs 0.20 on elite; 2.0 costs 0.97 on elite, 0.37 on mid, 0.39 on mix** |

Ablations (mechanism switched off entirely):

| Off | elite | mid | weak | mix | self |
|---|---:|---:|---:|---:|---:|
| sidestep feints | -0.32 | -0.19 | -0.15 | -0.28 | -0.22 |
| raids | -0.38 | -0.23 | -0.45 | -0.48 | -0.45 |
| shields | -0.43 | -0.51 | -0.49 | -0.45 | -0.69 |

### What this says

1. **Nine of ten settings are flat.** The lead does not depend on their exact
   values, so they are not where overfitting could hide.
2. **`hazard` is the exception and it is asymmetric.** It scales the measured
   chance that an un-upgraded cell near a rival is lost. Assuming twice the real
   risk makes the bot far too timid (-0.97); assuming half costs much less (-0.20).
   That curve was measured on the development population, so it is the setting most
   likely to be wrong against bots built by other teams. The bot does rescale it per
   rival from the raiding it observes (between 0.35x and 2.2x), which is the
   protection; the stress bots and the generated families in the test set include
   both heavy raiders and bots that never raid, to check that protection works.
3. **All three mechanisms carry weight.** No single trick explains the lead; the
   feints, which depend most on how opponents use Shield, are the smallest part.

A finer sweep of `hazard` and of the prior over landlords' Shield habits is running
(`lab/sensitivity2.py`).

## 7. Finer sweep, one setting changed, candidate frozen as `zr6`

`python3 lab/sensitivity2.py` (6,840 games, development only, fresh seed 500; table
in `lab/results/sensitivity2_dev.txt`).

**Hazard.** Difference from hazard 1.0:

| hazard | elite | mid | weak | mix | self |
|---:|---:|---:|---:|---:|---:|
| 0.6 | -0.08 | -0.03 | +0.01 | -0.01 | +0.08 |
| 0.75 | -0.02 | -0.08 | 0.00 | +0.01 | +0.11 |
| 0.85 | -0.10 | -0.03 | +0.01 | +0.01 | +0.17 |
| 1.25 | **-0.22** | **-0.18** | -0.03 | -0.02 | -0.05 |
| 1.5 | **-0.41** | **-0.16** | -0.08 | -0.07 | -0.20 |

Flat from 0.6 to 1.0 (every interval spans zero), then a cliff. The previous setting
of 1.0 was the last safe value: if real opponents raid a quarter less often than
the development population, the bot would be playing as if at 1.25. **Changed to
0.8**, inside the plateau. Confirmation on a third fresh seed (700, 1,140 fixtures
per bot, `python3 lab/suite.py --ref zr5 --seed 700 --scale 1.5 --self zr5 zr6`):
elite +0.02, mid +0.01, weak +0.02, mix +0.08, self +0.11, no interval below zero.
This is a robustness change; development shows no significant gain from it.

**Prior over landlords' Shield habits.** Replacing the tuned prior:

| Prior | elite | mid | weak | mix | self |
|---|---:|---:|---:|---:|---:|
| flat (20% each habit) | **-0.32** | -0.04 | -0.02 | -0.10 | -0.23 |
| on-sight heavy | **-0.15** | -0.07 | 0.00 | -0.01 | -0.15 |
| never-shields heavy | **-0.44** | -0.10 | -0.02 | -0.10 | -0.28 |

Finding: **about 0.3 of the candidate's lead over strong development bots comes from
knowing in advance how those bots use Shield.** Against mid and weak bots the prior
hardly matters. This is the main channel through which the candidate could be
overfitted. The prior encodes "a strong bot shields when a take is imminent", which
is also the rational play, so it may well transfer to other teams' strong bots; but
that is a hypothesis, and the out-of-sample test is where it is checked. The prior
was left unchanged so the test measures the candidate as designed.

**Frozen candidate:** `lab/cand/zr6.py`, SHA-256
`8b87bf8221c5937fc3bd51562850a6ac550a0cec49681640332b19c4ea0144cb`. It passes all
27 rows of `lab/robust.py` (`lab/results/robust_zr6.txt`).
`lab/PREREGISTRATION.md` is now in force. No test game has been played.
