# Optional continuous diagnostic queue: local prototype

This adds a reusable worker process and an owner-side coordinator for the existing
public-history GPU diagnostic. It does **not** distribute primary campaign games,
run full BMCTS, evolve the champion, or count synthetic rollouts as actual games.
The current CPU campaign and its pinned source files are unchanged.

The coordinator listens only on `127.0.0.1`. There is currently **no tested public
HTTPS address**, tunnel, cloud host, automatic remote installation, or connection
to any friend's computer. Laptops on separate networks cannot use the owner's
localhost address. A separately reviewed HTTPS route and a real remote test are
still required before calling remote automatic sharing ready.

## Local owner use

Run from the package root with the existing verified PyTorch environment. Commands
below use `python` to mean that environment's Python executable, not an unverified
system Python.

```powershell
python -m compute_queue.queue add-worker
python -m compute_queue.queue enqueue --input public-batch.json
python -m compute_queue.queue serve
python -m compute_queue.queue status
```

`add-worker` writes a unique private configuration to the ignored
`.cache/compute_queue/` folder and prints only its path. Keep that file private:
it contains a bearer credential. SQLite stores only a hash of the credential.
Each worker gets its own credential. To prepare a future verified HTTPS worker,
the owner can supply `--url https://approved-host.example` when generating its
configuration; doing so does not create or expose that host.

The input is the fixed batch envelope documented in
`search_coach/GPU_GUIDE.md`: exactly `schema: 1`,
`kind: "public_history_gpu_coach_batch"`, and `jobs: [...]`. Only complete opening
public prefixes, own accepted actions, and bounded search settings are allowed.
Each diagnostic ID must be globally unique in this queue. Re-enqueuing an
identical batch is idempotent; reusing a job ID in a different batch is rejected.
Batch size is capped at 4 MiB and 65,536 synthetic trajectories.

One coordinator process owns one database. It launches exactly one CPU verifier
thread. Every returned result remains `verifying` until the owner recomputes it
with `run_batch(device="cpu", verify_all=True)`. All numerical job values,
source hashes, counts, policy metadata and trace digest must match. Timing,
device and GPU descriptions may differ. Owner CPU verification may become the
throughput bottleneck; no speedup is claimed from these tiny functional tests.

## Reusable Windows worker package

The future distribution should contain the exact files listed in
`compute_queue.queue.SOURCE_PATHS`, this README and launcher, and the existing
`compute_share` setup/dependency files. Do not bundle the owner database or any
other worker's configuration. No source code update is downloaded by the worker;
changed code requires an explicitly reviewed replacement package and new queue.

Reuse the working `compute_share/.venv-worker` already installed for the offline
GPU pilot. There is no extra Python package for queue transport. Existing setup
instructions install the compatible PyTorch/CUDA wheel; a separate CUDA toolkit,
Git, Docker and new environment per task are unnecessary. A missing-NumPy warning
alone is not a failed CUDA kernel or an invalid result; the existing setup can
install NumPy to remove that warning.

After a public HTTPS path is approved and tested, the owner will privately supply
one configuration. Save it as `.cache/compute_queue/worker.json` and run
`compute_queue/run_worker.cmd`. The process imports PyTorch once, keeps the CUDA
context warm, fetches one public batch at a time, renews its lease while computing,
and waits for owner verification. It reuses the same environment across jobs.
Transient connection failures reconnect; expired assignments can be safely
reassigned. Stop with Ctrl+C. Reusing a token on several laptops is unsupported.

## Boundaries and failure handling

* Tokens travel in authorization headers, never URLs or normal output. Redirects
  are refused so credentials are not forwarded to a different host. External
  connections require HTTPS with standard certificate validation.
* HTTP JSON is bounded to 8 MiB. Duplicate keys, nonfinite values, unexpected
  fields, private state, executable commands, modules, filenames and paths are
  not part of the protocol. The coordinator has no remote enqueue/admin API.
* Project source hashes are pinned when the database is created and checked
  before claims, before and after execution, and before and after verification.
  Source drift stops acceptance. SQLite WAL transactions serialize claims.
* Lease nonces prevent stale returns after reassignment. Worker credentials can
  access only their own assignment and status. Pending verification does not
  expire with the worker lease. Retries with the same deterministic content are
  idempotent; conflicting duplicates fail and corrupt results are quarantined.
  Retrying a lost claim response returns and renews that worker's current live
  lease instead of allocating another task. Heartbeats cover public-prefix
  validation as well as GPU execution.
* A rejected result requires owner investigation. No accepted diagnostic result
  is automatically ingested into training or promoted to the deployed bot.
  Do not run multiple coordinator processes against the same database.

Run the focused tests in the verified CUDA environment:

```powershell
python -m unittest compute_queue.test_queue -v
```

The integration test uses four tiny public opening jobs, two persistent worker
processes (CPU and CUDA), and independent owner CPU verification. It writes a
credential-free receipt to `.cache/compute_queue/local_e2e.json`. These are local
functional checks, not a WAN test, benchmark, full-game evaluation or primary
campaign credit.
