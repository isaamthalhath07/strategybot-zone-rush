# Persistent local CPU policy pool

This prototype is unused by the active frozen CUDA study. It imports no Torch,
CUDA, transport, credential or owner-registry module. Original Python policies
still execute on local CPUs. No speedup, GPU-policy execution, qualification,
primary match, BMCTS audit or study admission is claimed.

`ActorPool(max_workers=4, evidence_directory=None)` owns up to eight local spawn
workers. Each shard uses its own persistent one-worker `ProcessPoolExecutor`.
This explicit affinity keeps a game's four source namespaces on the same
process for all eighty turns; an ordinary shared executor queue would not.
Only immutable compiled code may be cached across games. Reset destroys every
actor/controller instance and namespace before another batch is initialized.

Call `initialize_batch(registrationSubset, fixture_ids)` with guarded exact
candidate/source entries and selected fixtures. Only the minimum actor setup
specifications are sent to workers. Registration headers, maps, observer truth
and credentials are not sent. Initialization checks source bytes again inside
each worker. Setup is trusted-source execution, not an OS security sandbox.

`decide_turn(publicviews)` accepts exactly this plain-data envelope:

```text
{"turn":1,"lanes":[{"lane_id":"registered-id","views":[VIEW1,VIEW2,VIEW3,VIEW4]}, ...]}
```

Lane order must equal the initialized fixture order. Each view has exactly
`board`, `bot_id`, `is_priority_token`, and `legal_actions`; cells have the six
documented public fields. Supply the admitted engine legal-action order
`STAY,NORTH,SOUTH,WEST,EAST,SHIELD`, filtered by the public legal set. Every
lane's four boards and priority flags must describe the same preturn state.
All inputs are validated and copied to immutable views before callbacks.
The turn envelope is protocol bookkeeping and is not passed to an actor.

The response contains ordered joint actions, per-seat actual attempt/completion
counts (attempted, returned and contract-complete separately), callback wall
times, immutable-input/fallback checks, and only the
supported public-memory projections: inferred progress, scores, cooldown
possibilities and inference-failure status. No truth value is supplied to an
actor or used to correct its memory. A future physics driver must independently
check those projections against observer truth after each decision.

Worker errors are encoded as plain bounded error data, never returned exception
objects or arbitrary pickled commands. The parent waits for every dispatched
chunk, preserves successful and failed chunk evidence, marks the whole batch
failed and raises `PoolExecutionError`. It never substitutes STAY or retries a
callback. A hard worker/process failure explicitly reports unknown attempt
counts rather than inventing zero. Zero-attempt host schema errors occur before
dispatch. `reset()` and `close()` preserve evidence; an optional fresh evidence
directory durably records operations in `events.jsonl`. In-memory `.evidence`
remains available after close.

Limits: no current CUDA integration, canonical admission, benchmark, process
sandbox, hard preemptive callback timeout, crash recovery, automatic retry or
resumable actor state exists. A hung trusted callback can block a worker; timing
deadlines are checked after it returns. A broken executor requires closing and
constructing a new pool. Worker count is fixed by the first batch. Fresh source
namespaces do not isolate arbitrary mutable third-party module globals; exact
existing policy sources require their own parity qualification before use.
A future
benchmark must include serialization, public-view construction, CPU work,
audit/transfer costs and end-to-end time. Integration requires a new reviewed
source freeze after the active study, never a mid-run source change.

Run the CPU-only tests with `python -m unittest local_policy_pool.test_pool -v`.
They use synthetic maps/actors and a short exact-source e8 reference comparison;
they do not consume gold or current study outcomes or execute a GPU probe.

## Known-eight CPU qualification benchmark

`benchmark.py` is a separate, unlaunched operator task. It accepts only the
exact pinned registration and eight existing records in
`.cache/local_cuda/qualification_gold_002/`. It runs two predetermined repeats,
serial then four-worker pool, reproducing every original eighty-turn joint
action tape and terminal result through both CPU referees. All actors start
with fresh namespaces; workers persist across reset for the warm repeat.
Public-memory truth checks occur only in the parent after decisions.

The fresh output defaults to `.cache/local_policy_pool/known8_001`. It reports
source/input/runtime/profile pins, cold startup, warm reset and initialization,
wire validation, full dispatch/serialization wall time, actor callback sums,
parent truth checks, both CPU observers, evidence writes and full lifecycle
costs. Ratios are computed only from a completed actual run. Replica counts
grant zero new original games or study/primary/BMCTS credit. A CPU-only result
does not qualify integration into the active CUDA pipeline.

The root operator must review and launch it once; agents have run only the
synthetic benchmark tests. The launch command is
`python -m local_policy_pool.benchmark` from this checkout. No registry,
credential, network service, CUDA or Torch module is used by the benchmark.
