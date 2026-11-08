# Shared GPU pilot status

Snapshot: **9 November 2026**. These are public-history search diagnostics,
separate from actual primary campaign games and full BMCTS.

| Helper | GPU | Returned diagnostics independently reproduced | State |
|---|---|---:|---|
| 1 | RTX 4050 | 4 | Verified; second batch assigned |
| 2 | RTX 5070 Ti | 4 | Verified; second batch assigned |
| 3 | RTX 2060 | 4 | Verified; second batch assigned |
| 4 | GTX 1660 Ti | 4 | Verified; second batch assigned |
| 5 | RTX 5050 Laptop | 4 | Verified; second batch assigned |

The owner's separately tested RTX 5070 Ti is not counted as helper 2.
The five remote returns contain **20 unique diagnostics**, **14,720 synthetic
trajectories** and **44,160 synthetic turns**. Every numerical result was
recomputed on the owner's CPU against its original pinned public input and
source files. Counts and result fingerprints are in
[the receipt registry](verified_returns/registry.json). They contribute **zero
primary campaign games** and **zero full BMCTS audits**. They do not establish
that a different bot is stronger.

Diagnostic uniqueness here means across remote returns. The owner's earlier
calibration already computed the RTX 4050's assigned positions; its return is an
additional hardware/protocol check, not newly discovered strategy evidence.

The RTX 2060 and RTX 5050 hardware reports both show a successful actual CUDA
kernel with PyTorch 2.11.0+cu128. Their `ready_for_games: false` field describes
the hardware checker alone; it does not override a separately verified job.
The missing-NumPy warning in those reports did not invalidate either return.
Updated setup installs NumPy 2.5.4 in the existing private environment.

## Next assigned work

Batch 2 returns from slots 1, 2, 3 and 5 have now passed full owner-side CPU
reproduction: **32 positions, 184,320 synthetic paths and 1,105,920 future
turns**. Slot 4's return is pending. Receipts are in
`verified_returns/batch02/registry.json`. These are six-turn searches, so their
complete-match and primary-game counts remain zero. They are separate from the
first hardware/protocol pilot totals above.

The short runtimes do not establish useful primary workload sharing. Most pilot
time was CPU validation, and the owner repeated that work. Real complete-match
distribution and independent peer auditing now have a reviewed extra-study
implementation; remote primary admission is still unfinished. The current
Python policy is a CPU policy. CUDA teacher work needs a validated
usefulness experiment and a sustained queue before substantial allocation.

Five new source-specific full-match compatibility packages are ready in
`releases/2026-11-09-runtime-checks/`. Each helper needs its own private credential
file, delivered separately. Eight canonical study reference matches were created
once and fully audited on the owner; helper qualification replays grant no new
study or primary credit. The larger four-policy study remains unplayed apart
from those eight originals, and no full workload has yet been assigned remotely.

Full-match compatibility returns from **RTX4050 / CPython3.12.0** and
**RTX5050 / CPython3.12.7** have passed authenticated owner verification. Each
contains eight reference matches and 2,560 full actor-audit callbacks, covering
all four exact frozen policies. Qualification replicas create no new study or
primary credit. The other three runtime returns are pending. The intended
five-laptop original-play allocation is 6,552 matches per helper, followed by
different-laptop full audits. Its fixed task-list fingerprints are recorded in
`distributed_campaign/evidence/architecture_v2_allocation_preview.json`; this is
a non-executing preview and no actual PLAY assignment has been issued yet.

The second batches contain eight different public positions per helper, with a
six-turn horizon, 32 plans per root action and 32 sampled rollouts per plan.
Their 40 diagnostic IDs are disjoint from the accepted first returns and the
owner's local calibration. These jobs were not already computed on the owner
before dispatch. Source, archive and assignment fingerprints are in
[the assignment list](releases/2026-11-08-v2/fresh_batch02_assignments.json).
They remain assigned work until a return passes independent verification.

1. Keep the previous `result.json` outside the worker folder.
2. Extract the matching second-batch ZIP into the existing worker folder and
   replace its package files. Reuse `compute_share/.venv-worker`.
3. Run `compute_share/setup_gpu.cmd` to add NumPy if needed, then run
   `run_gpu_job.cmd` and return the new `result.json`.

The dependencies remain 64-bit Python 3.12, a working NVIDIA driver, the pinned
PyTorch CUDA build and its normal dependencies. See
[the installation guide](DEPENDENCIES.md). Reinstalling the GPU driver or the
full CUDA toolkit is not needed for these successful reports.

Manual ZIP transfer works across separate networks. The optional
`compute_queue/` implementation is a local prototype: its persistent-worker
protocol still needs a reviewed HTTPS route and a real remote connection test
before automatic Internet sharing is ready.
