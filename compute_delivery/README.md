# Outer delivery for real play and independent replay

This package wraps an **already issued, authenticated** architecture-study
assignment. It does not create a canonical control plan, choose opponents,
approve a runtime, handle raw key material, execute a policy itself, or grant
game credit. Owner plan verification stays inside the existing private authority.
The frozen worker and its signed ZIP stay byte-identical.

The owner must obtain all five runtime approvals and create the one canonical
study plan using the fixed reviewed helper order before building real PLAY
deliveries. Those actions are outside this builder. Creating peer-audit plans
also remains the existing controller's job, after original play coverage.

## Owner use

For a PLAY shard already present in the authenticated canonical plan:

```text
python -m compute_delivery.builder --plan CANONICAL_PLAN_JSON --shard SHARD_ID --output DEDICATED_WRAPPER_FOLDER
```

For an independent audit shard already present in its authenticated audit plan:

```text
python -m compute_delivery.builder --plan CANONICAL_PLAN_JSON --audit-plan AUDIT_PLAN_JSON --shard SHARD_ID --output DEDICATED_WRAPPER_FOLDER
```

`builder.build` calls the frozen `control._load` or `control._audit_plan` first.
It checks the selected work role, context, fixture list, bundle manifest and
the owner-bound inner ZIP hash, then verifies every archived source. The outer
ZIP contains only that unchanged inner ZIP, generated launcher files and public
delivery metadata. It never sweeps a plan folder, credential directory, old
results, environment, or repository into an archive. Its public receipt contains
hashes and task metadata, not registry paths or keys.

A rejected owner admission, foreign shard, changed ZIP, wrong role or invalid
archive produces no delivery. Existing identical outputs are reusable; different
bytes are never overwritten. A partial wrapper build can be preserved and
recreated in a fresh wrapper output for the SAME issued assignment. Do not
create another study plan or dispatch the same assignment as additional work.

## Helper use

Extract the entire source ZIP to a short local folder and double-click
`START_HERE.cmd`. The launcher first tries the previous
`compute_share/.venv-worker`, a saved path from this same job, or a normal Python
on PATH. It skips Windows Store aliases. Every candidate executable must match
the approved executable hash before it is invoked, and the Python probe must
then match all five approved fingerprint fields: implementation, exact version,
full build string, executable SHA and platform. A similar Python version is
insufficient. If needed, select the exact previously qualified interpreter.
Nothing installs Python, PyTorch, CUDA or another environment.

The cached credential is reused from
`%LOCALAPPDATA%/ZoneRushPrivate/architecture-v2-SLOT/credential.json`. Only if it
is missing does the launcher ask for that helper's separately supplied file.
The first import creates a dedicated private folder and restricts its Windows
access before writing the key. Wrong identity or assignment authentication
stops before any actor process. No credential object is passed to worker jobs.

The default is half the logical CPU count, bounded to one through four workers.
The initial count and exact job context are saved in `job_settings.json`.
Rerunning the SAME folder preserves that count even if CPU availability changes,
because the frozen signed worker header binds it. Missing settings beside an
existing result, altered context or a different requested count fails closed.
The outer launcher holds an OS lock for setup, execution and return export;
the unchanged worker also holds its own result-directory lock. Copying a job to
another folder is not a supported resume and may waste duplicate compute.

The child runs in the selected inner checkout with inherited `PYTHONPATH`,
`PYTHONHOME`, inspect and safe-path overrides removed. Its flushed progress is
streamed as it arrives, rather than captured until the whole shard finishes.
The unchanged worker reports every 50 completions and at the end:

- PLAY: completed original full matches; owner acceptance pending.
- AUDIT: completed independent full-game replays; zero new games.

Both roles run the actual Python policy on CPU and report zero worker primary
credit. No GPU policy or accepted result count is claimed. Stream failures and
interrupts stop/reap the owned worker process group; completed records remain.

At successful completion, return only the content-addressed `RETURN_TO_OWNER`
ZIP. It contains exactly `header.json`, `records.jsonl` and `progress.json`.
Header context, actual signed record coverage and the records hash are checked
before export. Source trees, credentials, environments and extra files are
excluded. Publication is atomic and exclusive; an existing unrelated file or
linked target is never truncated. A new progress snapshot may produce another
return ZIP while preserving the earlier one. This export is pending the owner's
complete ingestion and independent evidence gate, not an admission decision.

## Boundaries and tests

The outer ZIP SHA supplied by the owner is the delivery identity. Inner ZIP
checks reject traversal, Windows path aliases/reserved names, duplicate entries,
links, unexpected files and excessive expansion. Extraction stages a complete
source tree before making it visible. Activation uses exclusive Windows rename,
never replace. Only native access/sharing/lock errors 5, 32 and 33 receive up to
four waits of 0.05, 0.15, 0.3 and 0.5 seconds, for at most five attempts. Every
attempt rechecks archive bytes, the exact fresh source tree and auxiliary files,
links and destination absence. A destination that appears, changed source,
unrelated error or exhausted retry stops and preserves staging for review. No
permissions are changed, and the precise cause of an OS error is not inferred.
Production activation fails closed outside the approved Windows platform rather
than treating POSIX overwrite-capable rename as exclusive. Existing extracted
sources are checked again on resume. Reparse points and hard links in relevant
paths fail closed.

`--runtime-probe` executes no actors. `--check-package` verifies package and exact
runtime only, and reports zero actors, matches and credit. The test suite uses
explicitly mocked owner admission, comment-only fake worker files and fake
export authentication. It creates no real study plan, key, runtime, qualification
replica, actor execution or campaign credit. Native Windows controls cover
spaces, `%`, `!`, inherited delayed expansion and failure status propagation.
Those mechanics checks are not proof that real owner authentication was repeated;
the unchanged canonical controller provides that production boundary.

```text
python -m unittest compute_delivery.test_extract_retry compute_delivery.test_runner compute_delivery.test_independent -v
```

Root review and final source hashes are required before any real wrapper is
published. This new directory changes no frozen distributed/primary/holdout
module, qualification packet, canonical reference outcome or approval.

The earlier 26-check green receipt is historical. Subsequent owner runs exposed
an intermittent directory-activation error both under restricted and normal
Windows permissions. The exact original source, tests, review and receipt are
preserved in `evidence/history/outer_delivery_v1_before_rename_retry.zip`, with
the two observed failures in `evidence/history/root_v1_failures.json`. The cause
of the Windows error was not established; earlier passing tests did not prove
reliable startup.

The revised source passed three bounded 42-check Windows runs with zero skips:
10.114 and 10.454 seconds locally, and 10.321 seconds in independent review.
Injected access/sharing/lock failures, actual native promotion, permanent and
unrelated errors, racing destinations, source/auxiliary changes, hard links and
cross-directory attempts are covered. The old receipt is not overwritten; the
current record is `evidence/validation_v2.json`. Every test uses synthetic/mock
admission and reports zero actual actor/game execution.
