# Offline compute sharing

This package supports helper laptops on **different networks**. Exchange ZIP/JSON
files through a channel you already use. No coordinator, open port, shared GPU
memory or network discovery is required. Each GPU will eventually run independent
games/search batches, with faster laptops receiving more batches.

**Current state:** the hardware checker, deterministic scheduling/inventory,
public-history GPU diagnostic worker, portable job bundles and independent return
verification are implemented. The GPU diagnostic passed an extracted-ZIP CUDA
run and a separate CPU reproduction of its return. It is sampled open-loop search,
not full BMCTS or the primary two-million-game campaign. Primary game scheduling
is still separate from the diagnostic job transport; no primary games are counted.

For first laptop jobs and dependencies, see [SHARED_GPU.md](SHARED_GPU.md) and
[DEPENDENCIES.md](DEPENDENCIES.md). Every job contains only the focal player's
past public observations and past own actions, with pinned worker code. Returned
recommendations are independently recomputed before acceptance. Tampered returns,
changed source files, duplicate job IDs and private-field inputs are rejected.

## Hardware check

Give each helper `doctor_bundle.zip` and follow [HARDWARE_CHECK.md](HARDWARE_CHECK.md).
No automatic installation is performed. A CUDA device is eligible only after a
real kernel succeeds in the selected Python environment. All five listed NVIDIA
GPU models can be assessed this way; the Intel integrated alternative uses CPU.
Actual game/referee parity and throughput must then be measured independently.

The default system Python and a training environment can have different PyTorch
builds. In particular, detecting a GPU does not guarantee that its architecture is
included in the installed build. Preserve working environments; do not replace
the system installation merely to run this check.

## Deterministic work allocation

The owner can prepare an immutable schedule, pinning the actual bot and evaluator
files. From the repository root, for example:

```
python -m compute_share.offline plan --root . --policy bot.py --evaluator tools/benchmark.py --pin release_manifest.json --maps 10000 --games-per-map 200 --episodes-per-task 25 --workers 6 --seed 20261108 --output .cache/share-plan
python -m compute_share.offline inspect .cache/share-plan/manifest.json --root .
```

This schedules **2,000,000 games**, not executions or rollouts. It writes one
manifest and six disjoint allocation files. A task owns one seeded map and a
half-open episode range. Campaign identity includes every pinned source hash;
editing a pin creates a different campaign. Seeds and identities depend on the
campaign/map/episode, never the worker's GPU. Each primary game receives three
unique opponent instance IDs. Controller diversity, rule-valid maps and the actual
opponent behavior remain the worker adapter's responsibility.

Seat/token assignment is balanced: each 200-game map uses each focal seat and
token 50 times; each of the 16 pairs occurs 12 or 13 times. Rotating the extra
counts across maps makes the full 10,000-map campaign exactly balanced.

Keep the full manifest, assigned allocation, and all pinned files together in each
job bundle. Workers must verify the file hashes before execution. Send tasks only
to one laptop at a time; repartition only uncompleted tasks after retrieving or
cancelling the earlier assignment. Static allocation is intentional: it avoids
cross-network leases and accidental concurrent claims. Interrupted tasks keep
their original identities on retry.

The example pins the existing benchmark as an input **only**. That does not make
it a compatible distributed/BMCTS worker. The manifest explicitly records its
pending-execution status and cannot certify it.

## Results and validation boundary

Future worker results must use the `zone-rush-offline-result-v1` contract checked
by `inventory()`: campaign and manifest hashes, task ID, bot/evaluator hashes and
the exact ordered episodes, with transcript hashes and unique expected opponent
IDs. No Python objects or executable job commands are accepted. JSON duplicate
keys, non-finite numbers, overlapping results, unknown task IDs, missing episodes,
changed source hashes, invalid counters and foreign opponent IDs are rejected.

```
python -m compute_share.offline inventory .cache/share-plan/manifest.json incoming/result-001.json --output .cache/claims.json
```

This is **structural validation**, not evidence that games actually happened or
that BMCTS used legal information. The inventory deliberately reports
`verified_games: 0` and `verified_bmcts_audits: 0`. A separate trusted pipeline must
replay transcripts against the pinned referee, verify scores/timings, and audit
the public-input boundary before granting credit. Keep completed-game counts and
BMCTS-audited-game counts separate. A claimed `bmcts_audited` Boolean is not proof.

Run infrastructure checks with:

```
python -m unittest compute_share.test_compute_share -v
```

No simulator or submitted-bot code is imported by the hardware checker or scheduler.
