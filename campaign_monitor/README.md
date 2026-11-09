# Read-only stage and global-coverage monitor

The monitor binds every `train_NNN` directory to the same integer generation in
its registration, summary and audit. It independently checks the scheduled catalog
slice and global uniqueness of registered maps, tasks, rival IDs and rival seeds.
Actual game and individual actor-audit records must cover the registered tasks;
accepted totals derive from that disjoint coverage, not repeated aggregate flags.

This addresses a limitation of the frozen validator: its individual-stage checks
interpret `registration.generation` but do not additionally bind that value to the
caller's directory suffix. A copied generation-zero stage must not count again
under a generation-one directory. A targeted test reproduces that case using
real sealed registration/catalog files and confirms rejection without edits.

The monitor never executes actors, truncates partial files, reseals metadata or
changes the campaign. Active uncommitted tails are observed and left intact.
An in-progress stage receives zero accepted credit. Its report references
existing independently audited receipts; it is not a new deep physics/actor audit
or a substitute for the heldout evaluator's authenticated authority.

```powershell
python -m campaign_monitor.audit --directory .cache/primary/campaign_v1_20261109 --out .cache/campaign_monitor/live_snapshot.json
python -m unittest campaign_monitor.test_audit -v
```

Output must be outside the live campaign. A snapshot may conservatively omit an
approval created while the scan is running. No new primary or BMCTS credit is
created by the monitor.

## Future guarded driver v1

`guarded_run.py` implements a separately versioned wrapper. Keep the current
bounded owner unchanged. After that owner has exited and an explicit exclusive
ownership handoff is confirmed, the controller wraps the original frozen executor
without changing its source:

1. Record controller, interpreter, original source hashes, campaign identity and
   requested bounded stage range. Acquire one coordinator ownership lease.
2. Scan existing stages. Reject any directory/generation/profile mismatch,
   duplicate coverage, noncontiguous admission or unexpected pending owner.
3. Before each requested generation, call the original `prepare_generation`, then
   explicitly assert that its returned registration is for that requested index
   and exact catalog slice. Existing stages may be resumed only under this check.
4. Call the original game executor and independent auditor. Recheck directory,
   registration, summary and audit identities and global coverage afterward.
5. On any mismatch, stop and retain all evidence. Advance only after that exact
   stage's full independent admission. Release ownership when the bounded range
   finishes; never create a second owner or automatically replace one.

The default command only produces a read-only plan:

```powershell
python -m campaign_monitor.guarded_run --directory .cache/primary/campaign_v1_20261109 --start-index 5 --stop-before 6 --workers 6
python -m unittest campaign_monitor.test_guarded_run -v
```

Planning still rejects an invalid requested boundary. Execution additionally
requires `--execute --handoff PATH`. The handoff is a trusted local operator record
created after observing the prior owner terminate; its format is
`zone-rush-controller-handoff/1`, with campaign directory/identity,
`observed_terminal: true`, integer observed exit code and the previous owner's
actual OS PID. A tool session identifier is not an OS PID. The wrapper independently
checks that process is no longer running and checks again after acquiring its
OS-held coordinator lease. A claimed terminal flag cannot bypass a live PID.

The lease uses a Windows byte-range lock or POSIX flock on a persistent file
outside the campaign. Process death releases ownership; existence or stale PID
text does not grant ownership. The file is never deleted, avoiding a second-inode
race. This coordinates participating new controllers. The old executor does not
use this lease, which is why a real owner handoff is separately mandatory.

Original bot/core/runner hashes and the reviewed CPython3.12.10 executable are
pinned. Driver and monitor source hashes and interpreter metadata are recorded
before execution and checked throughout. A different runtime requires review of
a new controller version. Controller receipts live outside the campaign under
the ignored cache; existing game, summary, audit and source bindings remain intact.

Full global scans intentionally repeat at boundaries. The first real scan of
three registrations/60,000 complete rows took30.9 seconds while another owner was
active. Repeated scans grow with campaign size and can produce quadratic total
monitoring work across many stages. This cost is accepted here; unsigned cached
counts must not replace the checks. A separately authenticated future optimization
would require its own design and review.

No live campaign owner was replaced and the execution path has not been used on
the live campaign. Five targeted tests pass, including simultaneous competing
processes for one lease and a copied real stage rejected before either original
executor or auditor is called. Root review remains required before handoff.
