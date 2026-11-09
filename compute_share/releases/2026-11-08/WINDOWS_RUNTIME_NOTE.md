# Additional Windows prerequisite

The released ZIPs are immutable and already tested. One Windows dependency may
already be present on gaming laptops: **Microsoft Visual C++ Redistributable x64**.
If the setup reports a missing DLL or C++ runtime while importing PyTorch, install
the current x64 runtime from [Microsoft's official page](https://learn.microsoft.com/en-us/cpp/windows/latest-supported-vc-redist)
and retry setup. The [official PyTorch Windows FAQ](https://docs.pytorch.org/docs/stable/notes/windows.html)
describes the dependency.

The complete prerequisite list is 64-bit Python3.12, an NVIDIA driver, the C++
runtime if absent, and the package's pinned PyTorch2.11/CUDA12.8 environment.
The setup installs PyTorch's normal Python dependencies automatically. No full
CUDA toolkit or Visual Studio compiler is required.
