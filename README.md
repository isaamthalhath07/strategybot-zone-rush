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

`bot.py` carries **v3** (`v3_params.json`). Five versions were produced by
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
