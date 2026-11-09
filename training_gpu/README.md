# Offline GPU physics probe

This directory restores the tensor referee from `d385e00:gpuenv.py` and checks
it against the independently maintained `tests/reference_engine.py`. It is an
experimental accelerator, not the submitted policy or a campaign game runner.
`bot.py` does not import it. PyTorch is required only for these offline tools.

Changes from the historical tensor referee:

- Shield catch tests are vectorized without GPU-to-host Boolean checks.
- Unknown integer actions normalize to STAY.
- Round 1 rankings compare score alone. Round 2 adds cells owned and can apply
  the supplied Round 1 ranks for knockout ties.
- Three-way and four-way ties receive an equal average rank. The historical
  repeated averaging algorithm gave inconsistent ranks for these ties.

Run from the repository root in an environment with a working PyTorch build:

```powershell
python -m training_gpu.probe --device cpu --output training_gpu/probe_cpu.json
python -m training_gpu.probe --device cuda --output training_gpu/probe_cuda.json
```

The probe first executes an actual CUDA kernel when CUDA is selected. Device
detection alone is insufficient: the default local PyTorch 2.6/CUDA 12.4 build
detects the RTX 5070 Ti but cannot run its kernels. The existing `.venv-rl`
environment has a working PyTorch 2.11/CUDA 12.8 build. No global package or
driver changes were made.

The checked-in CPU and CUDA results each cover six rule configurations, two
initial-state regimes, 24 games per regime, and all 80 turns: 23,040 game-turn
transitions plus the initial states. Every checkpoint compares base values,
owners, upgrades, homes, positions, freeze counters, cooldowns, progress, scores,
incomes and priority token, as well as legal action masks and rankings for both
rounds and the knockout tiebreak. One regime starts at the normal opening;
the other starts from diverse constructed states to exercise more collisions,
landlord catches, raids and upgrades. Explicit cases cover successful movement
between the same owner's cells, initially occupied destinations, contested
destinations, simultaneous shields, freeze/cooldown timing, unknown actions and
three/four-way ties. These are differential checks and are not a mathematical
proof of equivalence for every state.

Measured on the local RTX 5070 Ti Laptop GPU (12 GB), with 80 synthetic turns:

| Batch | CPU, one PyTorch thread | CUDA |
| --- | ---: | ---: |
| 64 | 1,721 games/s | 411 games/s |
| 1,024 | 9,673 games/s | 6,629 games/s |
| 8,192 | 10,541 games/s | 51,456 games/s |

These are the best of two timed replays after warm-up. CUDA synchronization is
included at timing boundaries. The largest measured batch allocated about
63 MiB of PyTorch memory; driver/display allocations are separate. Small batches
are slower on this GPU than on the CPU. Results depend on batch size, hardware,
power limits and current load.

The timing uses prebuilt uniform random action tensors. It excludes real bot
decisions, opponent generation, information-state reconstruction, BMCTS search,
data transfers, result storage and process-isolation checks. **None of these
synthetic games count toward the requested two-million-game campaign.** An
end-to-end policy/search measurement is needed before allocating campaign work
to the GPU or predicting completion time.

Private tensor fields are the referee state. Future actors and search coaches
must receive only the four documented public inputs and deductions from their
own public history. Physics parity does not establish that a future planner
respects this information boundary.
