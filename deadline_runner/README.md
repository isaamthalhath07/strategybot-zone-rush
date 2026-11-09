# Local deadline pipeline

This new pipeline is separate from the active frozen study. It runs the exact
original Python policies on persistent local CPU workers and all physical
transitions on the frozen CUDA referee. It changes no policy, rule, old pool or
active runtime source. Generic output always grants zero primary games, zero
study admission and zero BMCTS audit credit. Root authority is a separate step.

`run_fixtures(registration, fixture_ids, output, batch_size=256, workers=4,
audit_workers=4, device='cuda')` returns ordered `rows`, ordered independent
`audits`, and a `summary`. Use a fresh output directory and call under the usual
`if __name__ == '__main__'` guard on Windows. There is no automatic resume,
overwrite, source substitution, STAY fallback or retry.

Each local actor shard owns persistent source instances for its assigned games.
One board per lane is constructed from GPU public cells as namedtuple `Cell`
objects with six fields. Four namedtuple `View` objects share that immutable
tuple board and contain only four public fields. All leaves are exact builtin
ints, bools and strings. Ordinary assignment, nested assignment and
`object.__setattr__` cannot mutate this representation. All four same-preturn
views exist before callbacks. This construction replaces repeated full-board
before/after signatures in the original path; it does not weaken the input
contract to mutable cells. The compact worker envelope never carries observer
scores, cooldowns, progress or actual rival identity/RNG as actor inputs.

Every actual callback has attempted/returned/completed counters, first2s and
regular200ms limits, legal-action and fallback checks. Supported inferred
public-memory projections return to the parent for truth checks after the
decision; no truth corrections enter the actors. Exact source bytes and runtime
guards are checked at setup and completion. Reset creates fresh per-game
namespaces/RNG while retaining only immutable compiled code caches.

The parent compares every full GPU state, income, legal set and true clock to
both independent CPU referees, including opening and terminal states. All
eighty turns and 320 original callbacks remain. Independent audit work uses a
separate persistent local spawn pool, default four workers. Every completed
original receives all320 fresh actor replay callbacks and both full CPU referee
replays through the exact frozen `oversight.audit_game` function body.

Audit instrumentation copies that function's globals and changes only its
`make_actors` lookup to passive wrappers around the original source factory.
The original function code/defaults/closure and existing module globals/files
remain unchanged. Wrappers call each original action once, return it unchanged,
and measure actual attempted/returned calls and deadlines. The frozen auditor
continues validating every input, action, fallback, supported memory oracle,
physical transition, final score and pairwise result. On success the wrapper's
320calls must equal the frozen auditor's independently counted320; on failure,
actual attempted/returned counts are retained and the validated-completion
count is explicitly unknown.

At most two completed original batches can await audit completion. Backpressure
drains the oldest audit batch before another original batch starts. Originals,
per-turn action/counter/state digests, audit records and immutable selected
registration snapshots are streamed to disk. Final summary publication requires
every original and every complete matching audit, unchanged source guards and
exact row/source bindings. Failure preserves partial originals and worker/audit
evidence and never grants admission. Already dispatched audits are retained;
they are not silently omitted or resubmitted.

No speedup is claimed before an operator-run end-to-end canonical-control
benchmark. Timing reports include actor setup/IPC/decisions, callback sums,
CUDA setup/transfers/physics, public conversion, parent truth checks, both CPU
referees, evidence writes and audit backpressure. This is CPU policy execution
with CUDA physics, not a CUDA policy or 200ms GPU-actor qualification. No
current study or known-eight benchmark is launched by the tests. Synthetic CPU
test doubles demonstrate orchestration only; any real-CUDA synthetic probe
must be separately coordinated and small. Trusted source execution is not a
hostile-code operating-system sandbox.

## Operator calibration and read-only verification

`python -m deadline_runner.benchmark` is root-launchable only. It first reproduces
the unchanged eight serial controls, then runs exactly512 fresh lane identities
in two256 batches: the original eight control recipes in order, repeated64
times. Each replica retains all320 independent callbacks. These are known
qualification replicas, with zero new study/primary credit. Concurrent old-study
work is explicitly recorded as operator-declared context, so no isolated
hardware speed ratio is inferred.

The default output is `.cache/deadline_runner/known8_001`. Its sealed
`benchmark_result.json` exposes `measurements` with one exact object containing
`games`, `wall_seconds`, `full_actor_audits`, and `both_referees`. Timing covers
the complete outer pipeline, including child startup/shutdown, original and
audit work, pipeline final publication, canonical equivalence and final source
checks. The benchmark result's own final write follows that interval.

`deadline_runner.verify.verify_execution(registration, output_directory)` checks
the exact intended ordered cohort, current source/CPU-runtime pins, immutable
source bytes, selected batch registrations, all80 streamed turns and callback
receipts, state-chain/source/row bindings, complete320-callback audit proofs,
deadlines/fallbacks and aggregate counts. It returns `summary`, ordered `rows`,
ordered `audits` and a verification receipt. It never calls actors or advances
CPU/GPU physics. The caller must supply the complete intended registration
subset; this function is read-only verification, not admission authority.
`deadline_runner.benchmark.verify_complete(output_directory)` uses that shared
validator and additionally verifies all512 known-control tapes/scores and the
fixed benchmark schedule and budget measurement.
