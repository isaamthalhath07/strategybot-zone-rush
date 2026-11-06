# StrategyBot / Zone Rush — bot, engine and tuning harness

`bot.py` is the submission: one self-contained file, standard library only,
`act(state)` as the starter kit defines it. Everything else is the workshop that
produced it.

## Build and check the submission

```bash
python ship.py best_params.json
```

Bakes the tuned weights into `bot.py` and refuses to pass unless: imports are
stdlib-only, `act(state)` is unchanged, the shipped file plays move-for-move
identically to the dev bot, `decide()` raises no internal exceptions, four seats
can share one module without sharing state, and 40 stress games produce no
crash, no illegal action and no turn near the 200 ms limit.

> The check that matters most is "decide() internal exceptions". `__call__`
> swallows exceptions and returns `STAY`, so a broken bot looks healthy and
> scores zero. This caught exactly that: one parameter missing from the JSON
> made the bot play `STAY` for all 80 turns while reporting "0 failures".

## Files

| file | what it is |
|---|---|
| `bot.py` | **the submission** — built, do not hand-edit |
| `mybot.py` | the bot's source: `Tracker` + planner + tactics |
| `engine.py` | Zone Rush rules engine; the five ambiguous rules are flags in `RULES` |
| `zoo.py` | opponent archetypes used for training |
| `holdout.py` | opponents never used in training, for the overfitting check |
| `arena.py` | Elo tournament harness |
| `tune.py` | (1+λ) evolutionary weight tuning, multiprocess |
| `rivals.py` | frozen snapshots, so the bot can face earlier versions of itself |
| `ship.py` | build + verify the submission |
| `evaluate.py` | full-field Elo, mirror match, exploitability |
| `strategies.py` | macro-strategy sweep across three opponent fields |
| `gpuenv.py` | Zone Rush as batched tensors, for GPU self-play |
| `rl.py` | PPO self-play training on the GPU engine |
| `nnbot.py` | pure-Python inference twin of the learned policy |
| `exploit.py` | exploitability matrix: counters vs every version |
| `test_*.py` | the suites listed below |
| `vN_params.json` | tuned weight snapshots, v1 through v5 |
| `nemesisN.json` | counter-bots tuned to beat vN, for exploitability measurement |
| `diag*.py`, `dbg*.py`, `probe.py`, `calib.py`, `bench.py`, `patch_combo.py`, `agent_new.py` | scratch / one-off diagnostics kept for reference; not needed to build or submit |

## Tests

```bash
python test_engine.py     # 50 checks: every worked example in the rulebook + 400 fuzzed games
python test_tracker.py    # the tracker's reconstruction vs the engine's hidden state
python test_robust.py     # ambiguous-rule flips, malformed input, every seat, mirror match
python test_transfer.py   # tuned-on-zoo vs held-out opponents (overfitting)
python test_fields.py     # how much strength depends on my guess about the field
python test_amnesia.py    # what happens if the server does not keep module state
```

## Which version ships, and why

`bot.py` carries **v6** (`v6_params.json`). Five versions were produced by
alternating "tune against the field" with "tune a counter-bot to beat the
result". Selection was made on a 1100-game, 20-entrant tournament rather than on
each run's own training score:

| | Elo | PW/3 | score | 1st% | beats v3 h2h | exploitability |
|---|---|---|---|---|---|---|
| **v3** | **1907** | **2.41** | **2536** | **56%** | — | 1.75-1.91 |
| v4 | 1888 | 2.39 | 2450 | 53% | 42% | 1.85-1.86 |
| v5 | 1871 | 2.35 | 2392 | 52% | 45% | — |
| v2 | 1859 | 2.32 | 2481 | 52% | 33% | 1.62-1.76 |
| v1 | 1701 | 2.14 | 2345 | 44% | 37% | 1.93-2.02 |
| best zoo bot (`spine`) | 1607 | 1.77 | 2033 | 29% | — | — |

Exploitability = what a counter-bot tuned specifically to beat that version
scores against three copies of it. **1.50 means no edge at all.** v1 was
genuinely exploitable; by v3 a dedicated counter-tuning effort gets very little.

**v5 is a cautionary result.** Its training field contained four of its own
ancestors plus both counter-bots, and it overfitted to beating itself: best
score on its own training field, worst of the lineage on held-out opponents
(2.55 vs v3's 2.74). Self-play fields need outside opponents to stay honest.

## Final measurements (v3)

| | |
|---|---|
| held-out opponents (never tuned against) | PW 2.55-2.79 / 3 |
| transfer ratio (held-out gain / training gain) | 1.78-1.90 |
| field sensitivity, 7 different assumed fields | PW 2.35-2.95, spread 0.60 |
| all five ambiguous rules flipped at once | PW 2.81 |
| turn time | 0.6 ms mean, 1.9 ms max (limit 200 ms) |
| crashes / illegal actions over all testing | 0 |
| mirror match, 1st vs 4th score spread | 5% |

## The strategy space, and what was actually tested

`v1`..`v5` were all the *same* strategy with different weights. `strategies.py`
sweeps the distinct macro plans the game admits, scoring each against three
different opponent fields with common random numbers. PW is out of 3; 1.50 is
exactly average.

| macro plan | mean PW | vs incumbent |
|---|---|---|
| **deep search + ignore rivals** | **2.824** | **+0.112** |
| deep search + hunt the leader | 2.812 | +0.100 |
| deep search alone (visits 8, beam 300) | 2.802 | +0.090 |
| deep search + claim/upgrade combo | 2.788 | +0.076 |
| ignore rivals alone | 2.753 | +0.041 |
| claim-and-upgrade combo | 2.720 | +0.008 |
| v3 incumbent | 2.712 | — |
| hunt the weakest / nearest, max denial, fortress | 2.68-2.70 | noise |
| turtle (own quadrant only, upgrade everything) | 2.598 | -0.102 |
| centre-steal opening | 2.598 | -0.102 |
| pure farmer (never raid) | 2.589 | -0.111 |
| centre-steal, aggressive | 2.538 | -0.162 |
| never shield | 2.287 | -0.413 |
| berserker (raid-first) | 2.253 | -0.447 |
| expansionist (claim the whole board) | 1.804 | -0.896 |

Two results worth absorbing:

**"Ignore rivals" beats targeting them.** Setting `care_mode: 4` and
`w_denial: 0` -- maximise your own score, never weight a rival's loss -- scores
better than the placement-margin objective the earlier versions used. In a
four-player game, hurting one rival mostly helps the other two, and the tempo
spent doing it is worth more spent on your own board. Maximising absolute score
turns out to be a very good proxy for placement.

**Deeper search is the single biggest lever, but not monotonically.** `visits 8,
beam 300` is the best setting found; `beam 700` is measurably *worse*, because a
wider candidate set dilutes the beam. Worst turn 8.2 ms against a 200 ms limit,
so depth is nearly free here.

Also tested and found to be within noise: `consolidate` (expand early, upgrade
late -- the tilt my own economics predicted would matter), and `lead_caution`
(play low-variance when ahead, gamble when behind).

## The GPU / reinforcement-learning track

Set up and tested. **It does not beat the heuristic bot**, and the result is
recorded here so nobody repeats it blindly.

`gpuenv.py` reimplements Zone Rush as batched tensor ops. `test_gpuenv.py`
proves equivalence by replaying identical action sequences through it and
`engine.py` and comparing the FULL state after every turn, under all five
ambiguous-rule settings: 9600 state comparisons, exact. That test earned its
keep immediately -- it caught a bug where progress was zeroed on every turn of a
freeze rather than only when a new freeze landed, which is invisible under the
default rules.

Throughput at batch 32768: **134,000 complete 80-turn games per second**
(10.7M game-steps/s), against roughly 500k steps/s for the pure-Python engine on
one core. The environment is effectively free.

`rl.py` trains a 75-feature MLP policy by PPO self-play. `nnbot.py` is its pure
Python twin for inference, verified to match the torch feature extraction to
2.8e-08. After **164M steps** the policy plateaus and then declines:

| matchup | learned policy | the heuristic bot |
|---|---|---|
| zoo lineups | 0.52 | **2.83** |
| held-out lineups | 1.10 | **2.91** |
| vs 3x spine | 0.08 | **1.70** |
| vs 3x greedy | 2.60 | **2.99** |
| vs 3x the heuristic bot | **0.00** | — |

Inference is not the obstacle (1.3 ms per turn, well inside budget). The policy
is simply weak. Two reasons, both structural:

- **Pure self-play converges to a weak mutual equilibrium.** All four seats share
  one policy, so it only ever has to beat itself.
- **No search.** The shipped bot beam-searches seven work-items deep over whole
  routes. Zone Rush rewards multi-turn commitment (one stay to claim, three more
  to upgrade, plus travel), and a reactive policy cannot plan a route.

If this is picked up again, the order that matters is: train against a
**vectorised heuristic opponent on the GPU** rather than against itself, or warm
start by **cloning the existing bot** before any RL. Using the network as a value
function inside the beam is a dead end for the submission -- thousands of
forwards per turn will not fit 200 ms of pure Python.

The GPU work needs `.venv-rl` (torch 2.11+cu128, for sm_120 Blackwell kernels);
the global interpreter and the shipped bot are untouched by it.

## Things that were tested and did NOT work

Recorded so they are not re-tried. All of these were my own hypotheses:

- **Priority-token contest avoidance** — tuned to exactly zero on an easy field.
  It only earns its keep against opponents that genuinely contest cells, where it
  came back at 0.92. Field-dependent, not free.
- **All-out endgame raiding** — the bot already shifts to raiding late on its own;
  forcing it harder is clearly worse (PW 2.86 -> 2.61).
- **Occupancy as deliberate defence** ("a cell I stand on cannot be entered") —
  gave no measurable benefit, because the planner is already parked on cells
  while upgrading them.
- **Perishability bonus** and **retake credit** — both tuned to zero.
- **Equilibrium shield mixing** — the formula is correct and is in the code, but
  it does not bind: the value of stopping an imminent take is an order of
  magnitude above the shield's cost, so no sane threshold suppresses it. What
  actually protects against baiting is the per-opponent `commit` estimate.

## How the bot works

**Tracker.** The starter kit's `state` exposes only the board, `bot_id`,
`is_priority_token` and `legal_actions`. It does *not* give the turn number, any
bot's score, take/upgrade progress, shield cooldowns, freeze counters, or which
seat holds the token. All of it is reconstructed from board diffs, exactly:

- every shield is observable — it either catches someone (that bot freezes) or it
  backfires (the shielder freezes). Attribution is ambiguous when a bot freezes
  while standing on rival land, so the tracker searches for the set of shielders
  that exactly explains the freezes, using the hard constraint that a shielder
  cannot lose a cell that turn, and stays pessimistic when two explanations tie.
- knowing every shield gives every 4-turn cooldown, which is what makes risk-free
  raiding possible.

Verified against the engine's hidden state: scores, progress, positions, freezes
and token are **exact**; cooldowns are 99.2% exact with residual errors mostly in
the safe direction.

**Planner.** Beam search over *walks* — a sequence of work-cells with the real
travel cost between them — rather than ranking single targets by rate. Scoring
whole walks prices travel correctly, prefers clusters, and stops the oscillation
that single-target scoring caused.

**Tactics.** The shield/raid stand-off is a 2×2 matrix game with no pure
equilibrium, so a deterministic defender is baitable. The bot mixes at the
computed equilibrium when it has no read, and best-responds once the opponent
model has one. Backfire is free in the last turns, so it shields freely there.

**Objective.** Elo pays for *placement*, not score, so the evaluation is a sum of
logistic margins against each rival, not raw points. That makes the bot target
whichever rival it is closest to and stop gambling once a lead is safe.

## Re-tuning

```bash
python tune.py <generations> <games/gen> <population> <field> <out.json> <seed.json>
# field: default | mixed | counter:<snapshot>
```

`counter:<snapshot>` tunes a bot to *beat* a snapshot — that is how the bot's own
exploitability is measured, and how the training field is hardened.
