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

## 8. The out-of-sample test (EXT1): result and decision

`python3 lab/final_test.py --set EXT1 --out lab/results/test_ext1.json`, run once on
the frozen `zr6` exactly as pre-registered. 10,240 games, 0 faults by any focal bot,
0 games that failed to run. Full table: `lab/results/test_ext1.txt`; per-game data:
`lab/results/test_ext1.json`.

| Field (192 games each) | `zr6` | current `bot.py` | Racer | Blocker | `zr6` minus current (95%) | minus Racer | minus Blocker |
|---|---:|---:|---:|---:|---|---|---|
| `holdout_elite` | 1.76 | 1.63 | 1.75 | 1.72 | +0.14 [-0.16, +0.43] | +0.01 [-0.30, +0.35] | +0.05 [-0.26, +0.38] |
| `holdout_rest` | 2.68 | 2.49 | 2.62 | 2.63 | +0.19 [+0.06, +0.31] | +0.06 [-0.07, +0.18] | +0.05 [-0.07, +0.17] |
| `ai_pasted` | 2.93 | 2.85 | 2.85 | 2.89 | +0.08 [+0.01, +0.15] | +0.07 [+0.01, +0.15] | +0.04 [-0.03, +0.11] |
| `generated` | 2.84 | 2.28 | 2.60 | 2.51 | +0.56 [+0.42, +0.71] | +0.24 [+0.14, +0.34] | +0.33 [+0.23, +0.43] |
| `other_designs` | 2.38 | 2.31 | 2.40 | 2.39 | +0.07 [-0.08, +0.21] | -0.02 [-0.18, +0.14] | -0.02 [-0.17, +0.14] |
| `stress` | 2.81 | 2.32 | 2.61 | 2.64 | +0.49 [+0.34, +0.62] | +0.20 [+0.09, +0.31] | +0.17 [+0.07, +0.28] |
| `unseen_mixed` | 2.64 | 2.32 | 2.52 | 2.54 | +0.32 [+0.19, +0.44] | +0.12 [+0.02, +0.21] | +0.10 [-0.00, +0.20] |
| **Pooled** (1,344 games) | **2.575** | 2.313 | 2.478 | 2.472 | **+0.262 [+0.20, +0.33]** | **+0.097 [+0.04, +0.16]** | **+0.102 [+0.04, +0.16]** |
| known map families | 2.62 | 2.37 | 2.54 | 2.51 | +0.25 [+0.18, +0.34] | +0.08 [+0.01, +0.15] | +0.11 [+0.04, +0.18] |
| new map families | 2.52 | 2.24 | 2.40 | 2.42 | +0.27 [+0.17, +0.38] | +0.12 [+0.01, +0.23] | +0.09 [-0.01, +0.20] |
| `unseen_all` | 2.76 | 2.38 | 2.56 | 2.54 | +0.38 [+0.25, +0.50] | +0.19 [+0.10, +0.29] | +0.21 [+0.10, +0.31] |
| `with_candidate` | 1.95 | 1.83 | 1.93 | 1.81 | +0.13 [-0.10, +0.34] | +0.02 [-0.21, +0.24] | +0.15 [-0.08, +0.37] |

Alternative rule readings (64 games each, `unseen_mixed` opponents): `zr6` minus
current `bot.py` is +0.13, +0.23, +0.09, +0.20, +0.38; no interval is below zero.

### The shipping rule, applied as written

| # | Condition | Result |
|---|---|---|
| 1 | Pooled lead over current `bot.py`, lower bound above 0 | +0.262 [+0.20, +0.33]: **holds** |
| 2 | Pooled lead over Racer and over Blocker, lower bounds above 0 | +0.097 [+0.04, +0.16] and +0.102 [+0.04, +0.16]: **holds** |
| 3 | No field significantly below a reference | none: **holds** |
| 4 | Lead over current positive on known and on new map families | +0.25 and +0.27: **holds** |
| 5 | Zero faults, zero failed games | **holds** |
| 6 | Pooled lead at least half the development lead (+0.16) | +0.262: **holds** |

Under the alternative rule readings: zero faults, never significantly below current.
**Decision: `zr6` replaces the root `bot.py`.**

### What the test also shows (the part that matters for the next step)

1. **The lead is real but it is made against weak and mid-strength bots.** On the
   `generated` and `stress` fields `zr6` is +0.5 over the current bot. Against the
   strong unseen bots (`holdout_elite`, `other_designs`) its lead over the current
   bot is +0.14 and +0.07 with intervals spanning zero, and over Racer and Blocker
   it is zero.
2. **The development lead on strong bots did not carry over.** Development said
   +0.55 over the current bot on the elite field (+0.37 on fresh development seeds);
   unseen strong bots give +0.14. Section 7 found that 0.3 of the development elite
   lead came from the prior over how those particular bots use Shield. That part was
   fitted to the development bots, and this is the measurement of it.
3. **Against strong bots `zr6` scores fewer raw points than the references and
   places level with them anyway**: mean score 2,853 vs 2,871 to 2,879 on
   `holdout_elite`, 2,858 vs 2,903 to 2,938 on `other_designs`. It trades its own
   income for damage to rivals. Against strong bots that trade only breaks even.
4. **Every strong bot beats the pasted ChatGPT and Gemini bots almost every game**
   (2.85 to 2.93 of 3). If other teams submit one-shot AI bots, any of these four
   wins; places are decided among the teams that iterated, i.e. on the strong fields.
5. **Map families:** `zr6` leads on 10 of 13 families. It trails Racer and Blocker on
   `flat` (2.27 vs 2.41 / 2.35), `rich` (2.30 vs 2.37 / 2.42) and `edges` (2.32 vs
   2.37 / 2.39): maps where most cells are worth the same and claiming land fast
   matters more than which land. 84 games per family, so these are leads to look
   into, not established facts.
6. **The hazard change (`zr6` vs `zr5`) made no measurable difference out of
   sample:** pooled +0.012 [-0.03, +0.05]. Under the presence-catch rule reading
   `zr6` was below `zr5` (-0.20 [-0.38, -0.05], 64 games, one of five readings
   examined, so possibly chance; it is not the confirmed rule).

### Deviations from the pre-registration

- Before the test was started, one game was played with `zr6` against `x_zenith`,
  `x_hx_aggro` (EXT1) and `x_outsider_sim` (EXT2) on development map `gradient/1`, to
  time a game. The candidate was already frozen and was not changed; no decision
  used that game. It is the only contact with any EXT2 bot so far.
- **The EXT2 replication is deferred, not dropped.** The pre-registration says to
  run the identical plan on EXT2 after shipping. EXT2 is the only untouched opponent
  set left, and the work continues beyond `zr6` (finding 1 says where). EXT2 will be
  run once, on the next frozen candidate, with `zr6` among the focal bots on the same
  fixtures. That run reports the `zr6` replication whatever it shows and is the test
  of the next candidate. Its plan will be committed before it is run.
- From here on EXT1 counts as seen: it may be used for diagnosis and development.

## 9. `zr6` shipped as the root `bot.py`

`python3 lab/ship.py zr6 "..."` copies the frozen file to `bot.py` byte for byte
(SHA-256 `8b87bf82…`) and points `release_manifest.json` at it. The previous release
is now `tester_bots/guarded_transfer.py` (unchanged bytes, `e8b3682d…`); the tests
written against its internals run against that file, and its validation record sits
under `previous_release` in the manifest.

`tests/test_root_bot.py` adds nine contracts for the root bot on the repository's
independent reference engine: legal and timely answers, input never mutated, exact
own score / progress / cooldown books over 1,280 self-play callbacks, one module
playing four seats and a second game, dictionary / string / Enum / bare-tuple inputs,
and a working fallback when the planner raises. They bind to behaviour, not
coefficients, so a later candidate ships with `lab/ship.py` alone.

`python3 tools/check_release.py`: 142 tests pass, plus the six interface groups.

## 10. Why `zr6` only breaks even against strong bots: it leaks un-upgraded land

All of this uses opponents that are no longer held out (development pool, lab
hold-out, EXT1). EXT2 and the second half of the stress bots are untouched.

New tools: `lab/suite2.py` (five fields over every seen opponent and all 13 map
families), `lab/h2h_strong.py`, `lab/h2h_field.py`, `lab/prof_fam.py`,
`lab/loss_audit.py`, `lab/scratch/hazard_own.py`, `lab/scratch/raid_propensity.py`.

### Diagnosis

Against 26 strong bots (`python3 lab/prof_fam.py <all families> zr6 a_novel_b_racer
cur_e8 --maps 78`), per game:

| | `zr6` | Racer | previous release |
|---|---:|---:|---:|
| cells lost to raids | **4.3** | 1.3 | 0.8 |
| of which un-upgraded | 3.7 | 1.0 | 0.3 |
| bonus points handed to rivals | 89 | 30 | 24 |
| raids made / bonus earned | 4.0 / 110 | 2.4 / 41 | 1.2 / 25 |
| income, last third of the game | 1,279 | 1,368 | 1,395 |
| final score | 2,852 | 2,870 | 2,878 |

`python3 lab/loss_audit.py zr6 --maps 80`: three of the 4.3 lost cells are cells
`zr6` claimed and left un-upgraded; two of those three had not been stood on for more
than 20 turns; two thirds of all losses fall after turn 55. When `zr6` walked away
from them the eventual raider was usually four or more steps off. Racer and the
previous release upgrade a cell before leaving it, so they are almost never exposed.

**Cause: the risk table `zr6` plans with was measured on the wrong cells.** It came
from every bot's un-upgraded cells in development games. Most strong bots upgrade
within three turns of claiming, so those cells were short-lived and the table says
little about a cell left for 20 or 40 turns. Measured on `zr6`'s own cells
(`lab/results/hazard_own_zr6.txt`), the chance of losing an un-upgraded cell within
40 turns, nearest rival four steps away, mid-game:

| Opponents | measured | `zr6` assumed |
|---|---:|---:|
| strong | 49% | about 15% |
| mid | 24% | about 15% |
| weak | 16% | about 15% |

Two structural facts came out of that table:

- The risk is nearly a constant rate per turn once a rival has had time to walk over
  (about three turns per step of distance), with no real dependence on the phase of
  the game. One shape fits every distance: exposure `g = max(0, h - 3(d-1))`.
- The rate differs about threefold between opponent populations, and between
  individual bots by more (`lab/results/raid_propensity.txt`: rivals take an exposed
  cell they stand next to on 3% of turns for passive designs, about 20% for most
  strong bots, 40 to 50% for the aggressive ones). No single number can be right.

### What was changed (`lab/cand/_head3.py`, `lab/cand/_tail3.py`; build with `gen=3`)

1. The un-upgraded-cell risk is now `1 - product over rivals of P(survives rival)`,
   with each rival's rate taken from a **posterior over three raider types** (passive,
   ordinary, aggressive) updated from how often that rival actually takes an exposed
   cell when it stands next to one. Before any evidence the mix is 30/50/20.
2. "Claim and upgrade without leaving" is planned as one job, so a cell that is not
   worth holding un-upgraded can still be taken and fortified. In `zr6` such a claim
   was discarded before its upgrade was ever considered. That discard is why raising
   the old risk multiplier looked disastrous in section 6: the multiplier scaled
   probabilities past 100%, claims went negative and the bot stopped expanding.

### Development results (`python3 lab/suite2.py --seed 900 ...`, difference from `zr6`)

First with one rate for every rival (no per-rival typing):

| rate | strong | mid | weak | mix | self |
|---:|---:|---:|---:|---:|---:|
| 0.003 | -0.47 | -0.13 | -0.05 | -0.19 | -0.25 |
| 0.006 | +0.10 | -0.05 | -0.06 | +0.03 | +0.30 |
| 0.010 | +0.13 | +0.01 | -0.08 | +0.09 | +0.44 |
| 0.016 | +0.22 | -0.13 | -0.08 | +0.04 | +0.40 |
| 0.030 | +0.19 | -0.14 | -0.18 | -0.05 | +0.35 |
| 0.060 | +0.19 | -0.18 | -0.19 | -0.09 | +0.34 |

More caution helps against strong bots up to about 0.016 and then is flat; it costs
against mid and weak bots. Head to head (`lab/h2h_field.py`) the cost is against
passive designs and the gain against raiders, which is the case for typing rivals.

With the per-rival posterior (`zr7h`, ordinary-raider rate 0.014):

| | strong | mid | weak | mix | self |
|---|---:|---:|---:|---:|---:|
| `zr7h` minus `zr6` | **+0.22 [+0.08, +0.36]** | -0.02 [-0.13, +0.08] | -0.10 [-0.17, -0.03] | +0.04 [-0.04, +0.12] | **+0.41 [+0.21, +0.60]** |
| rate 0.008 | +0.07 | +0.02 | -0.10 | +0.08 | +0.43 |
| rate 0.022 | +0.21 | -0.14 | -0.11 | +0.01 | +0.41 |

A separate 880-game weak-field run on another seed puts the weak-field cost at
-0.04 (2.782 vs 2.822). Against strong bots `zr7h` now loses 1.6 cells per game
instead of 4.3 and hands rivals 36 bonus points instead of 89.

Tried and dropped: pricing the land taken in a raid with a lower risk than land
already held (four combinations). It changed nothing measurable, so the model keeps
one risk for both.

Not yet done, and the numbers above are development numbers on seen opponents:
more than half of the remaining losses fall in the last ten turns.

## 11. Generation 4 starts from `zr7h`; two ideas from a parallel line checked and not adopted

A parallel line of work (kept in commit 1c2f7e2, candidate `zr9old`) had three changes
on top of the `zr6` design: full upgrade value for the cell the bot is standing on,
clamped loss probabilities, and "value-aware routes" (among equally short paths to the
target, walk the one that passes the most claimable land). Before building on either
line, both were measured on the same fresh fixtures.

Seed 1200, difference from the shipped `zr6` (`python3 lab/suite2.py --seed 1200 --self zr7h zr9old zr7h`):

| | strong | mid | weak | mix | self |
|---|---:|---:|---:|---:|---:|
| `zr6` (PW) | 2.109 | 2.628 | 2.865 | 2.486 | 1.965 |
| `zr9old` | +0.072 [-0.06, +0.21] | -0.032 | -0.019 | +0.010 | +0.016 |
| `zr7h` | +0.104 [-0.06, +0.25] | +0.032 | -0.051 [-0.12, +0.01] | +0.072 | +0.122 |

`zr7h` is at least as good everywhere that matters, so generation 3 is the base.
Note the strong-field gain of `zr7h` on this seed (+0.10) is half the +0.22 seen on
seed 900 where it was developed: the usual shrinkage, and a reminder of its size.

Generation 4 (`lab/cand/_head4.py`, `_tail4.py`; `python3 lab/build.py NAME gen=4`)
is generation 3 plus optional features, each behind a setting that defaults to off.
`zr8a_r0` (gen 4, everything off) is move-for-move identical to `zr7h`
(`python3 lab/equiv.py zr7h zr8a_r0 --maps 10`: 40/40 games, 3,200 decisions).

Value-aware routes on the generation 3 base, seed 1300, difference from `zr7h`
(`python3 lab/suite2.py --ref zr7h --seed 1300 --self zr8a zr8a`):

| | strong | mid | weak | mix | self |
|---|---:|---:|---:|---:|---:|
| `zr7h` (PW) | 2.373 | 2.545 | 2.853 | 2.591 | 2.244 |
| routes on | **-0.051 [-0.09, -0.02]** | +0.045 [-0.01, +0.10] | +0.013 [-0.01, +0.04] | +0.010 [-0.02, +0.04] | -0.010 [-0.07, +0.06] |

Not adopted: slightly but clearly worse against strong bots, no clear gain elsewhere.
The setting stays in the file, off (`"routes": 0`).

Seeds used in this section: 1200, 1300.

## 12. Where `zr7h` still loses, and two changes to how land is priced

### Diagnosis (new tools: `lab/gap.py`, `lab/scratch/l2_loss.py`, `waste.py`, `opening.py`)

- `python3 lab/gap.py zr7h --field strong|mid|weak` profiles every seat in every game
  and compares the focal bot with exactly the rivals that finished ahead of it. In
  the pairings `zr7h` loses, the rival is not raiding better: it has less raid bonus
  than `zr7h`. It simply was left alone (0.4 cells lost against our 1.6, no shields
  needed) and spent those turns on claims and upgrades. `zr7h`'s bad games are the
  ones in which it is raided repeatedly (about 3 cells lost, one of them upgraded,
  4 shields cast).
- Upgraded cells (`l2_loss.py`, 0.47 lost per game against strong bots): half fall
  while the shield is recharging after catching a different raider, a fifth after
  the raider side-stepped a shield (backfire), a fifth with the shield ready and not
  used. Not pursued yet.
- Wasted turns (`waste.py`): the 2 abandoned progress points per game are almost all
  deliberate side-steps on turns the landlord did shield. Nothing to recover there.
- **Opening** (`opening.py`: each bot alone against three bots that never move; the
  position's worth at turn 27 is score + income x turns left). `zr7h` had the slowest
  opening of all the strong bots: 1,966 against Racer 2,054 and `zr6` 2,243. Two
  causes, both visible in the move traces:
  1. it upgraded its **home cell first**. The home cell cannot be taken, but the
     risk model priced it like any other un-upgraded cell, which made "upgrade home"
     look like rescuing a cell about to be lost;
  2. it walks over cheap cells near home without claiming them, because a claim is
     priced as "held un-upgraded, and exposed, for the rest of the game".

### Change 1, adopted: no risk on the home cell (`"homefix": 1`)

A modelling error, fixed. Difference from `zr7h`, fresh fixtures:

| seed | strong | mid | weak | mix | self |
|---|---:|---:|---:|---:|---:|
| 1400 | +0.040 [-0.03, +0.11] | +0.032 [-0.03, +0.10] | +0.006 [-0.03, +0.04] | +0.014 [-0.04, +0.07] | +0.115 [-0.03, +0.29] |
| 1500 | +0.104 [+0.03, +0.18] | +0.032 [-0.04, +0.12] | -0.026 [-0.07, +0.02] | +0.043 [-0.03, +0.13] | +0.090 [+0.00, +0.18] |

### Change 2, not adopted: price a claim as exposed for `lag` turns, then upgraded

Three versions were tried.

- Charging the three future upgrade turns at last turn's best rate: the price fed
  back into itself from one turn to the next and the bot dithered. Dropped before
  any real-game run.
- Exposure cut off after `lag` turns for every un-upgraded cell (seed 1400): the
  undisturbed opening jumps to 2,308, but in real games it is a disaster,
  **strong -1.11 (lag 8), -0.73 (lag 16)**, mid -0.21 / -0.12. Upgrades of cells
  already held looked less urgent, were put off, and 4.6 un-upgraded cells per game
  were raided. This is the `zr6` leak again, and a clean measurement of how hard
  the known strong bots punish exposed land.
- Exposure cut off only for a claim made inside the current plan, full urgency for
  cells already held (seed 1500, difference from the home-fixed bot): the opening
  now equals Racer's (2,050) and a first look on development seed 78 said +0.10 on
  strong, but the fresh seed says strong -0.04 / -0.03 / +0.02 (lag 6 / 10 / 16),
  mid -0.03 / -0.02 / -0.01, weak -0.05 / -0.04 / -0.01. No gain. The setting stays in
  the file, off (`"lag": 0`).

The slower opening of generation 3 is therefore the price of not exposing land, and
on the evidence it is a price worth paying against these opponents.

Seeds used in this section: 41, 42, 43 (gap), 51, 52 (audits), 77, 78 (profiles),
1400, 1500 (suite2).
