# StrategyBot — Zone Rush

A bot for **Zone Rush**, the four-player territory game used in StrategyBot
(ARC × Coding Club, AFKAR 2026, IIT Delhi — Abu Dhabi).

`bot.py` is the submission: one self-contained file, standard library only,
exposing `act(state)` exactly as the starter kit defines it.

Everything else here is the workshop that produced it — a rules engine, an
opponent zoo, a tournament harness, an evolutionary tuner, and a GPU self-play
track that was tried and rejected.

---

## Quickstart

```bash
python ship.py
```

Rebuilds `bot.py` from the tuned weights and verifies it. It refuses to pass
unless: imports are stdlib-only, `act(state)` is unchanged, the built file plays
move-for-move identically to the development bot, `decide()` raises no internal
exceptions, four seats can share one module without sharing state, and 40 stress
games produce no crash, no illegal action and no turn close to the 200 ms limit.

```bash
python test_engine.py
```

```bash
python strategies.py 150
```

> The check that matters most is **"decide() internal exceptions"**. `__call__`
> catches exceptions and returns `STAY`, so a completely broken bot looks healthy
> and scores zero. This caught exactly that: one parameter missing from a JSON
> file made the bot play `STAY` for all 80 turns while the stress test reported
> "0 failures".

---

## Results

Measured over **1,100 games with 20 entrants**, random seats, maps and starting
token, scored the way Round 1 scores it — each four-bot game becomes three
one-on-one results, so `PW/3` is how many of the three rivals were outscored.

| bot | Elo | PW/3 | score | 1st | what it is |
|---|---|---|---|---|---|
| **v3** | **1907** | **2.41** | **2536** | **56%** | this project |
| v1 | 1701 | 2.14 | 2345 | 44% | first tuned version |
| `spine` | 1607 | 1.77 | 2033 | 29% | best farmer written by hand |
| `camper` | 1577 | 1.59 | 2010 | 15% | takes the 3-cells and squats them |
| `cdraider` | 1457 | 1.34 | 1801 | 12% | raids only inside shield cooldowns |
| `greedy` | 1391 | 1.08 | 1566 | 10% | model of the typical AI-written bot |
| `stay` | 674 | 0.08 | 160 | 0% | an unmodified or crashing skeleton |

**300 Elo over the best bot written by hand, 516 over the modal AI-written
entry.** The `stay` row matters too: a bot that crashes, times out or returns an
illegal action plays `STAY` and finishes there.

`bot.py` ships **v6**, a later version that beats v3 on six of seven matchups:

| matchup | v3 | v6 |
|---|---|---|
| mixed zoo lineups | **2.90** | 2.81 |
| held-out lineups | 2.74 | **2.84** |
| vs 3× `spine` | 1.47 | **1.81** |
| vs 3× `camper` | 2.71 | **2.89** |
| vs 3× `cdraider` | 2.52 | **2.66** |
| vs 3× `hunter` | 2.77 | **2.91** |
| mean | 2.586 | **2.704** |

### Robustness

| | |
|---|---|
| counter-bot bred specifically to beat it | 2.17 / 3 — where 1.50 is no edge |
| held-out opponents, never tuned against | 2.84 / 3 |
| transfer ratio (held-out gain ÷ training gain) | 1.8 – 1.9 |
| all five ambiguous rules flipped at once | 2.81 / 3 |
| turn time | 2.6 ms mean, 6.1 ms max (limit 200) |
| crashes / illegal actions / timeouts | 0 |
| four identical copies against each other | 5% score spread, 1st to 4th |

v6 is the strongest version *and* the most exploitable one (v3 gives up only
1.72). It ships anyway, because no competing team has this source to breed a
counter from, and v6 generalises better to opponents it was never tuned against.
`python ship.py v3_params.json` swaps the other way in one command.

---

## How the bot works

### 1. It rebuilds the state the server hides

The starter kit's `state` exposes the board, `bot_id`, `is_priority_token` and
`legal_actions`. It does **not** expose the turn number, any bot's score, take or
upgrade progress, shield cooldowns, freeze counters, or which seat holds the
token. `Tracker` reconstructs all of it from board diffs.

Every shield is observable, because it either catches somebody (that bot freezes)
or it backfires (the shielder freezes). Attribution is genuinely ambiguous when a
bot freezes while standing on rival land — it was either caught by the landlord or
backfired on its own shield. Rather than guess, the tracker searches for the set
of shielders that *exactly explains* the freezes observed, using the hard
constraint that a shielder cannot lose a cell that turn, and stays pessimistic
where two explanations tie. Guessing gave 1,406 errors; solving gave 25.

Knowing every shield gives every four-turn cooldown — and **a rival on cooldown
cannot defend anything.**

Verified against the engine's hidden state over 3,200 turns: scores, progress,
positions, freezes and the token are **exact**; cooldowns are 99.2% exact with
residual errors in the safe direction. Worth **+0.65 pairwise wins and +376
points** per game (`test_amnesia.py`).

### 2. It plans routes, not targets

A beam search over *walks* — sequences of work-cells with the real travel cost
between them — rather than ranking single targets by rate. Scoring whole walks
prices travel correctly and prefers clusters.

An earlier version ranked single targets and **paced between two neighbouring
cells for an entire game**, scoring 1,050 instead of 2,400. The cause was cell
modifiers keyed to walk distance, so whichever cell the bot stood on was
penalised relative to its neighbour.

### 3. It treats defence as the game-theory problem it is

The shield/raid stand-off is a 2×2 game with no pure equilibrium, so a
predictable defender can be baited: step onto their cell, let them shield, step
off, and they are frozen for two turns and on cooldown for four. The bot prices
the backfire branch properly and weights it by a per-opponent estimate of whether
that rival commits or bails. Against an opponent that never commits, its shield
rate falls from 12% to 4% within a single game.

### 4. It self-throttles

The grading machine may be slower or busier than the one these weights were tuned
on, and a late turn is scored as `STAY`. The search has a hard internal deadline
checked mid-iteration, and the beam shrinks when a turn runs long and grows back
when there is room. Under 24× CPU oversubscription the worst turn was 80 ms
against the 200 ms limit.

---

## The game, in numbers

Manhattan distance splits the 8×8 board cleanly into four 4×4 quadrants, one per
corner. Each is worth **28 points per turn** and holds exactly three 3-point
cells. Nothing inside your own quadrant is reachable by a rival in under five
moves, so your inner cells are safe and the centre is the only ground genuinely
worth contesting.

A cell is worth its value multiplied by the turns remaining — a 3-point cell taken
on turn 10 pays 210 points, the same cell on turn 70 pays 30. Raid bonuses
(`8 × value × level`) are one-off and therefore do **not** decay, which is why
half of all bonus income arrives in the last 20 turns.

A perfect solo farmer restricted to its own quadrant scores 2,744. Unopposed and
free to expand, the bot scores 3,404.

---

## Layout

| file | what it is |
|---|---|
| **`bot.py`** | **the submission** — generated by `ship.py`, do not hand-edit |
| `mybot.py` | the bot's source: `Tracker`, the planner, the tactics |
| `engine.py` | rules engine; the five ambiguous rules are flags in `RULES` |
| `zoo.py` | opponent archetypes used for tuning |
| `holdout.py` | opponents never used in tuning, for the overfitting check |
| `arena.py` | Elo tournament harness |
| `tune.py` | (1+λ) evolutionary weight search, multiprocess |
| `strategies.py` | macro-strategy sweep across three opponent fields |
| `rivals.py` | frozen snapshots, so the bot can face earlier versions of itself |
| `exploit.py` | exploitability matrix: every counter against every version |
| `ship.py` | build and verify the submission |
| `gpuenv.py` | Zone Rush as batched tensors, for GPU self-play |
| `rl.py` | PPO self-play training on the GPU engine |
| `nnbot.py` | pure-Python inference twin of the learned policy |
| `v*_params.json` | tuned weight snapshots |
| `nemesis*.json` | counter-bots bred to beat a given version |

Scratch diagnostics, kept for reference and not needed to build or submit:
`diag*.py`, `dbg*.py`, `probe.py`, `calib.py`, `bench.py`, `patch_combo.py`,
`agent_new.py`, `final_eval.py`, `evaluate.py`.

### Tests

```bash
python test_engine.py      # rulebook examples + 400 fuzzed games with invariants
python test_tracker.py     # the tracker's reconstruction vs the engine's hidden state
python test_robust.py      # ambiguous-rule flips, malformed input, every seat, mirror
python test_transfer.py    # tuned-on-zoo vs held-out opponents (overfitting)
python test_fields.py      # how much strength depends on the assumed field
python test_amnesia.py     # what happens if the server keeps no module state
python test_oppmodel.py    # does the opponent model actually adapt
python test_gpuenv.py cpu  # tensor engine vs reference engine, state by state
```

### Re-tuning

```bash
python tune.py <generations> <games/gen> <population> <field> <out.json> <seed.json>
```

`field` is `default`, `mixed`, or `counter:<snapshot>`. The last one tunes a bot
to *beat* a snapshot — that is how the bot's own exploitability is measured, and
how the training field was hardened.

---

## Strategy sweep

`v1`…`v6` were the *same* strategy with different weights. `strategies.py` sweeps
the distinct macro plans the game admits, against three different opponent fields
with common random numbers. PW is out of 3; 1.50 is average.

| macro plan | mean PW | vs incumbent |
|---|---|---|
| **deep search + ignore rivals** | **2.824** | **+0.112** |
| deep search alone (visits 8, beam 300) | 2.802 | +0.090 |
| ignore rivals alone | 2.753 | +0.041 |
| incumbent | 2.712 | — |
| turtle (own quadrant only, upgrade everything) | 2.598 | −0.102 |
| centre-steal opening | 2.598 | −0.102 |
| pure farmer (never raid) | 2.589 | −0.111 |
| never shield | 2.287 | −0.413 |
| berserker (raid-first) | 2.253 | −0.447 |
| expansionist (claim the whole board) | 1.804 | −0.896 |

Two results worth absorbing.

**Ignoring rivals beats targeting them.** Maximising your own score and never
weighting a rival's loss scores better than the placement-margin objective the
earlier versions used. In a four-player game, hurting one rival mostly helps the
other two, and the tempo costs you more than it costs them. Maximising absolute
score turns out to be a very good proxy for placement.

**Deeper search is the biggest single lever, but not monotonically.** `visits 8,
beam 300` is the best setting found; `beam 700` is measurably *worse*, because a
wider candidate set dilutes the beam.

---

## The GPU / reinforcement-learning track

Set up, trained, and **rejected**. Recorded so it is not repeated blindly.

`gpuenv.py` reimplements the game as batched tensor operations. `test_gpuenv.py`
replays identical action sequences through it and `engine.py` and compares the
full state after **every turn** under all five ambiguous-rule settings: 9,600
comparisons, exact. That test earned its keep immediately — it caught a bug where
progress was zeroed on every turn of a freeze rather than only when a new freeze
landed, which is invisible under the default rules.

Throughput at batch 32,768: **134,000 complete 80-turn games per second**
(10.7M game-steps/s), against roughly 500K steps/s for the Python engine on one
core. The environment is effectively free.

`rl.py` trains a 75-feature MLP by PPO self-play; `nnbot.py` is its pure-Python
inference twin, verified to match the torch feature extraction to 2.8e-08. After
**164M steps** the policy plateaus and then declines:

| matchup | learned policy | the heuristic bot |
|---|---|---|
| mixed zoo lineups | 0.52 | **2.83** |
| held-out lineups | 1.10 | **2.91** |
| vs 3× `spine` | 0.08 | **1.70** |
| vs 3× `greedy` | 2.60 | **2.99** |
| vs 3× the heuristic bot | **0.00** | — |

Inference was never the obstacle (1.3 ms/turn, well inside budget). The policy is
simply weak, for two structural reasons:

- **Pure self-play converges to a weak mutual equilibrium.** All four seats share
  one policy, so it only ever has to beat itself.
- **No search.** The shipped bot beam-searches seven work-items deep over whole
  routes. Zone Rush rewards multi-turn commitment — one stay to claim, three more
  to upgrade, plus travel — and a reactive policy cannot plan a route.

If picked up again, in order: train against a **vectorised heuristic opponent on
the GPU** rather than against itself, or **warm-start by cloning the existing
bot** before any RL. Using the network as a value function inside the beam is a
dead end for the submission — thousands of forward passes per turn will not fit
200 ms of pure Python.

The GPU work needs a separate venv (`torch 2.11+cu128`, for sm_120 Blackwell
kernels). It is gitignored, and the shipped bot has no dependency on any of it.

---

## Tested and found NOT to work

All of these were plausible, and several were confidently predicted before any
code ran. Recorded so they are not re-tried.

- **Priority-token contest avoidance** — tuned to exactly zero on a weak field, and
  back up to 0.92 on a strong one. Field-dependent, not free.
- **All-out endgame raiding** — the bot already shifts to raiding late on its own;
  forcing it harder is clearly worse (2.86 → 2.61).
- **Occupancy as deliberate defence** ("a cell I stand on cannot be entered") — no
  measurable benefit, because the planner is already parked on cells while
  upgrading them.
- **The centre-steal opening** — six turns of zero income is not recoverable.
- **Perishability bonus** and **retake credit** — both tuned to zero.
- **Equilibrium shield mixing** — the formula is correct and present, but it does
  not bind: stopping an imminent take is worth an order of magnitude more than a
  shield costs. The per-opponent commit estimate is what actually prevents
  baiting.
- **Consolidating late** and **varying risk with standing** — within noise.
- **PPO self-play**, as above.

### One cautionary result

**v5 overfitted to beating itself.** Its training field contained four of its own
ancestors plus two counter-bots. It scored best of any version on that field and
worst of the lineage against outside opponents (2.55 against v3's 2.74).
Self-play fields need outsiders to stay honest, and version selection has to run
on an external tournament rather than on each run's own training score.

---

## Caveats

Every number here is measured against opponents written for this project. The
300-Elo margin is real, but `spine` is an educated guess at a strong competitor,
not an actual one. **The highest-value remaining work is replacing the opponent
zoo with bots generated by several different AI models**, then re-tuning — the
field you tune against matters more than the algorithm.

The bot assumes an 80-turn game. It degrades gracefully if the server keeps no
module state between calls (2.67 → 2.02 pairwise wins) but is meaningfully
stronger with it.

`engine.py` encodes a guess at five rules the rulebook leaves ambiguous, listed in
`RULES`. Flipping all five costs 0.04 pairwise wins, so the guesses are not
load-bearing — but they are worth confirming with the organisers:

1. Does a frozen bot's forced `STAY` accrue take or upgrade progress?
2. After claiming a neutral cell, does progress reset?
3. Does losing a contested-cell race count as a `STAY` for progress?
4. Can a bot `SHIELD` while standing on rival land to avoid being frozen?
5. Does a home cell have `base_points`, and can its owner upgrade it?
