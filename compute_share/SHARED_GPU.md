# First shared GPU jobs

The first portable GPU diagnostic jobs are ready for helpers to run on Windows,
including at separate locations. They analyze public game positions from the
current champion's recorded games. They are **search diagnostics**, not primary
campaign games, full BMCTS, or an improved bot submission.

## Install once

Each helper needs 64-bit **Python 3.12** with its Python launcher, an appropriate
**NVIDIA graphics driver**, and **PyTorch 2.11.0 with CUDA 12.8**. The included
`compute_share/setup_gpu.cmd` installs PyTorch into that package's private
`.venv-worker` and tests a real CUDA calculation. See [DEPENDENCIES.md](DEPENDENCIES.md)
for exact commands and primary documentation.

The full CUDA Toolkit, cuDNN, Git, Docker and Visual Studio are unnecessary.
Do not replace a working global Python environment. CUDA support is checked on
each laptop rather than inferred from a GPU model name.

## Run the assigned package

1. Extract the assigned ZIP completely.
2. Open its `compute_share` folder and double-click **setup_gpu.cmd**.
3. Return to the ZIP's main folder and double-click **run_gpu_job.cmd**.
4. Return **result.json** and **compute_share/hardware.json** to the owner.

Each laptop gets a different package and disjoint diagnostic IDs. Do not send the
same assigned package to multiple laptops. No same-Wi-Fi connection, account
sharing, firewall changes or router ports are needed. Keep bot-related code under
the participating team's control; sharing code between competing teams is forbidden.

The RTX 4050, RTX 5070 Ti, RTX 2060, GTX 1660 Ti and RTX 5050 are NVIDIA worker
candidates, subject to actual kernel/parity checks. If person3 has only Intel
integrated graphics, it cannot run CUDA; use CPU work instead. CPU tensor
diagnostics still need PyTorch, while pure Python game evaluation does not.

## What has been verified

The local RTX 5070 Ti executed four public-prefix jobs from an extracted portable
ZIP. The return's action values, recommendations and complete rollout trace
matched a separate CPU replay. A deliberately altered recommendation was rejected.
Hardware-check success alone never credits games or certifies a result.

The numerical worker independently tested 28,416 trajectories / 85,248 turns on
CPU and CUDA. All actions and values matched exactly. Its measured complete batch
took 10.77 seconds on CPU and 9.73 on CUDA, including full independent verification.
CUDA computation itself was faster, but verification dominates total time. These
numbers are specific to the local machine and do not predict other laptops.

The transport verifies source/data hashes before and after work. Its numerical
worker reconstructs hidden-state possibilities from public history, uses common
focal continuations across those possibilities, and gives rivals only their own
public counterfactual views. It cannot see real rival controller identities,
private counters, actual random seeds or future recorded actions.

Terminal utility is the official sum of pairwise wins/ties. Nonterminal utility
is an explicitly limited projected ranking estimate. Returned diagnostics are
cases to investigate; they cannot certify that a move was optimal.

## Owner commands

Generate a new set of disjoint diagnostic packages:

```powershell
python -m compute_share.make_sample_jobs .cache/shared_gpu/new_pilot --laptops 5 --jobs-per-laptop 4
```

Recompute a returned result using the matching environment and pinned source version:

```powershell
python -m compute_share.gpu_jobs receive --root .cache/shared_gpu/new_pilot/laptop_01 incoming/result.json
```

Use a PyTorch environment for receipt. The verifier compares exact numerical
results and traces while permitting legitimate device/timing differences. A
repeated identical return is idempotent; a different accepted return for the same
job is rejected. Diagnostic counts remain separate from primary-game and BMCTS
audit counts, both of which remain zero for these packages.
