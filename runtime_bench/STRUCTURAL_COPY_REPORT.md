# Structural public-copy v1: measured game-generation improvement

The experimental copy backend preserved the recorded game behavior and improved
measured throughput in these bounded tests. The frozen runner, bot and live
campaign were not changed or monkeypatched. No migration was performed.

| Matched condition | Frozen generic copy | Structural v1 | Observed ratio |
|---|---:|---:|---:|
| 1 worker, 128 timed game repetitions each | 6.475 games/s | 10.105 games/s | 1.56× |
| 2 workers, 64 timed game repetitions each | 8.933 games/s | 22.612 games/s | 2.53× |

Each condition used eight warm-up games per worker and two timed blocks. Task
IDs, interpreter executable, source hashes and the benchmark helper match within
each comparison. One-worker comparisons used 64 distinct recorded fixtures; the
two-worker comparisons used 32. They cover all eight registered candidates and
all four opponent fields. The original callback code, game physics, score replay,
time limits and referee-only public-memory/cooldown checks remained intact.

All 384 timed repetitions matched their existing 80-turn action histories and final
scores: 30,720 four-player action vectors and 122,880 callbacks. No behavioral,
legality, input-mutation, deadline or public-memory mismatch was observed. Warm-up
games also checked equivalence. These are repeated controls with zero new primary
games, zero BMCTS audits and no additional strength evidence.

The measured region includes real policy calls, full game generation and score
verification. It excludes dataset loading, disk append and the separate independent
audit. Consequently, these ratios are not claims about total campaign speedup.
The machine had concurrent workloads. Callback timings varied across conditions,
so longer interleaved measurements are necessary before treating a ratio as a
reliable production forecast. Block times and per-game metrics are retained.

## Exactly what changed

`structural_runner_v1.py` contains exact copies of six functions from the frozen
runner: namespace loading, initialization, opponent construction, public signatures,
game execution and result replay. The only copied-function edit replaces
`view = copy.deepcopy(view)` with `view = clone_public(view)`. A provenance test
reverses that one replacement and compares every copied function byte for byte.
The frozen base runner hash is
`bae5c92c51efa83eaef90db0ede9940be72201d2bb78e9d0527e3f6139d7503b`.

The structural clone accepts the exact canonical CPU reference-engine schema:
an eight-by-eight list board of 64 independent six-field Cell objects, a valid
bot identity, boolean priority flag and canonical action list. It validates field
types and ranges, then creates new View, board, rows, Cells and legal-action list.
Primitive field values and classes remain identical to generic deepcopy.

Each actor receives an independent snapshot. Retaining a previous snapshot and
later changing its cells, rows, identity or legal-action list does not affect any
future or rival view or the referee. Changing the current input still triggers
the unchanged input-mutation guard. These cases were exercised through both
actual runners, including an 80-turn actor that deliberately modifies retained
old snapshots. Malformed boards, unexpected classes, out-of-domain scalar fields,
aliased row/cell graphs and invalid action containers fail closed.

## Benefits and limits

The main benefit is less generic object-graph machinery for a precisely known,
small public schema. The actor algorithm, input information and game rules remain
the same. It does not improve the bot's decisions by supplying private state or
opponent future actions, and it does not waive any existing validation step.

The narrower schema is a compatibility risk. Other valid organizer interfaces,
flat/dictionary boards, enum action containers, NumPy scalars, GPU-worker view
classes or future extra public fields are not supported by this copy function.
The submission bot's existing broad parser remains unchanged. Shared mutable
row/cell graphs accepted by generic deepcopy are rejected here; the canonical
reference engine never creates those graphs. This is not a drop-in replacement
for every possible object that Python's deepcopy can accept.

Remaining work before migration: independent review of the copy boundary;
broader shadow replay across more maps, generations and actor families; recorded
runtime/backend hashes; compatibility checks for every worker input producer;
and a versioned campaign migration that preserves all earlier source bindings.
Keep the current live campaign frozen until those checks pass. The independent
auditor should continue using its separately maintained reference copying and
referees, so it can detect any optimization error.

## Reproduce

From the repository root, choose fresh output folders:

```powershell
python -m runtime_bench.build_structural_runner
python -m unittest runtime_bench.test_structural -v
python -m runtime_bench.compare_copy --stage .cache/primary/campaign_v1_20261109/train_000 --out .cache/runtime_bench/new_frozen --backend frozen --tasks 64 --warmup 8 --repeats 2 --workers 1
python -m runtime_bench.compare_copy --stage .cache/primary/campaign_v1_20261109/train_000 --out .cache/runtime_bench/new_structural --backend structural-v1 --tasks 64 --warmup 8 --repeats 2 --workers 1
```

Replace workers with 2 for the bounded parallel test.
Raw reports, individual game metrics, source snapshots and experiment hashes are
in `evidence/structural_v1/`; source-build provenance is
`evidence/structural_v1_source.json`. Five targeted safety/provenance tests pass.
