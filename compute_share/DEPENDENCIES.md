# Windows GPU preparation

The environment preparation package and **public-history GPU diagnostic worker**
are ready for an initial laptop trial. The diagnostic worker has completed a
local CUDA job from an extracted ZIP and independent verification of its return.
The full two-million-game campaign and full BMCTS are separate, unfinished work.
Every helper laptop still needs its own successful hardware and job checks.

## What each helper needs

1. **64-bit Python 3.12**, including its Windows Python launcher (`py`). Use
   [python.org](https://www.python.org/downloads/windows/).
2. An installed **NVIDIA graphics driver** compatible with the laptop and the
   selected PyTorch build. The checker tests actual execution; if it fails, send
   its report before changing drivers.
3. **PyTorch 2.11.0, CUDA 12.8 build**, in the separate environment created by
   `setup_gpu.cmd`. Its normal dependencies are installed automatically by pip.
4. **Microsoft Visual C++ Redistributable x64 runtime**, if it is missing.
   Existing gaming laptops often have it already. If PyTorch reports a missing
   DLL/runtime, use the [official Microsoft runtime download](https://learn.microsoft.com/en-us/cpp/windows/latest-supported-vc-redist).
   This is a runtime package, not the Visual Studio compiler. The
   [PyTorch Windows FAQ](https://docs.pytorch.org/docs/stable/notes/windows.html)
   documents this Windows binary dependency.

The RTX 4070, RTX 5070 Ti, RTX 2060, GTX 1660 and RTX 5050 should each be checked
individually. Their installed drivers, available memory and laptop power limits
can differ. This exact PyTorch build has executed a real CUDA kernel on the
owner's RTX 5070 Ti. Other laptops remain unverified until their reports pass.
The Intel integrated alternative can contribute CPU work; it cannot run CUDA.

Only `torch` is required beyond Python's standard library for the current GPU
physics tools. There is no need for torchvision, torchaudio, the full CUDA
Toolkit, a separate cuDNN installation, Visual Studio, Docker, Git or WSL. The
[official PyTorch version instructions](https://pytorch.org/get-started/previous-versions/)
list the Windows CUDA 12.8 build for 2.11.0. PyTorch's binaries bundle their CUDA
runtime dependencies; see the [maintainer's explanation](https://discuss.pytorch.org/t/should-i-install-the-extra-cudatoolkit-and-cudnn/194528/2).

## Easy setup

Extract `gpu_setup_bundle.zip`, then double-click **setup_gpu.cmd**. This explicitly
installs packages from PyTorch's official wheel index into **.venv-worker** inside
that folder. It does not install drivers, modify global Python, open ports, or
start a campaign. Internet is needed to download packages. The window remains
open to show success or errors.

Send the resulting **hardware.json** back to the owner. It excludes names,
computer names, network addresses and GPU serial numbers. Inspect it in Notepad
if desired. A device must pass a real CUDA kernel, not just appear in a list.

For manual installation, open Command Prompt in the extracted folder:

```bat
py -3.12 -m venv .venv-worker
.venv-worker\Scripts\python.exe -m pip install torch==2.11.0 --index-url https://download.pytorch.org/whl/cu128
.venv-worker\Scripts\python.exe verify_cuda.py
```

For a read-only check before installing anything, use `check_hardware.cmd` from
the doctor bundle. To contribute to standard-library CPU game evaluation, Python
alone will be sufficient once the game worker is connected. No GPU package is
needed for that evaluator. The tensor search diagnostic's CPU mode does need
PyTorch; this differs from the standard-library game evaluator.

Laptops can remain on separate networks. Work will be allocated through disjoint
job files and returned result files. Do not open router ports or share accounts.
Keep bot-containing job packages under the participating team's control, as the
rulebook prohibits sharing bot code between competing teams.
