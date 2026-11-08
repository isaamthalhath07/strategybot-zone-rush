# Check a helper laptop

Extract this ZIP to a folder, then double-click **check_hardware.cmd**. Python
3.10 or newer must already be installed. The check does not install packages,
change drivers, open ports, or contact a server. Close the window after it finishes.

Send the resulting **hardware.json** back to the campaign owner. It contains the
Windows version, Python version, CPU thread count, GPU model/driver/memory, and
the result of a tiny CUDA calculation if PyTorch is installed. It does not collect
your name, hostname, network address, GPU serial number, or account credentials.
User home folders are redacted from diagnostic errors. You can inspect the JSON
in Notepad before sharing it.

If the window says Python is missing, tell the owner instead of installing an
unknown package. If you already have a separate Python environment, open Command
Prompt in this folder and run:

```
check_hardware.cmd "C:\path\to\environment\Scripts\python.exe"
```

Seeing `cuda_available: true` alone is insufficient: **kernel_ok must be true**.
A missing or incompatible PyTorch installation does not mean the GPU is unusable;
the owner can choose an appropriate separate environment from the report.

The RTX 4050, RTX 5070 Ti, RTX 2060, GTX 1660 Ti and RTX 5050 are candidate CUDA
workers. Actual support depends on the installed driver and PyTorch build. An
Intel integrated GPU is not a CUDA device; that laptop can contribute CPU work.
No game jobs are included in this hardware-check ZIP. Game/referee parity and
speed checks must pass before a machine receives campaign work.

Keep the package within the participating team. It contains no credentials or
other teams' bot sources. Laptops on different networks will exchange job and
result files; no shared network or router configuration is required.
