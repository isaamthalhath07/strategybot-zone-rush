# Shared GPU pilot status

Snapshot: **9 November 2026**. These are public-history search diagnostics,
separate from actual primary campaign games and full BMCTS.

| Helper | GPU | Returned diagnostics independently reproduced | State |
|---|---|---:|---|
| 1 | RTX 4050 | 4 | Verified; second batch assigned |
| 2 | RTX 5070 Ti | 0 | Awaiting return |
| 3 | RTX 2060 | 4 | Verified; second batch assigned |
| 4 | GTX 1660 Ti | 4 | Verified; second batch assigned |
| 5 | RTX 5050 Laptop | 4 | Verified; second batch assigned |

The owner's separately tested RTX 5070 Ti is not counted as helper 2.
The four remote returns contain **16 unique diagnostics**, **11,904 synthetic
trajectories** and **35,712 synthetic turns**. Every numerical result was
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

The second batches contain eight different public positions per helper, with a
six-turn horizon, 32 plans per root action and 32 sampled rollouts per plan.
Their 32 diagnostic IDs are disjoint from the accepted first returns and the
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
