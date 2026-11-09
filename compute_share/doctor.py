"""Read-only, portable hardware check. No installation or configuration changes."""

import argparse
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import sys
import tempfile
import time


TORCH_PROBE = r'''
import json
try:
    import torch
    result = {"installed": True, "version": torch.__version__,
              "cuda_build": torch.version.cuda,
              "cuda_available": torch.cuda.is_available(), "devices": []}
    if torch.cuda.is_available():
        result["compiled_arches"] = torch.cuda.get_arch_list()
        for index in range(torch.cuda.device_count()):
            item = {"index": index, "name": torch.cuda.get_device_name(index),
                    "capability": list(torch.cuda.get_device_capability(index)),
                    "total_memory_bytes": torch.cuda.get_device_properties(index).total_memory,
                    "kernel_ok": False}
            try:
                with torch.cuda.device(index):
                    tensor = torch.ones(1024, device=f"cuda:{index}")
                    value = tensor.sum().item()
                    torch.cuda.synchronize(index)
                    item["kernel_ok"] = value == 1024.0
                    del tensor
            except Exception as exc:
                item["error"] = f"{type(exc).__name__}: {exc}"[:2000]
            result["devices"].append(item)
    print(json.dumps(result))
except ImportError:
    print(json.dumps({"installed": False, "devices": []}))
except Exception as exc:
    print(json.dumps({"installed": True, "error": f"{type(exc).__name__}: {exc}"[:2000], "devices": []}))
'''


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(value, stream, indent=2, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def command(args, timeout=15):
    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=timeout,
                                check=False, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        return {"exit_code": result.returncode, "stdout": result.stdout.strip()[:16000],
                "stderr": result.stderr.strip()[:4000]}
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"error": f"{type(exc).__name__}: {exc}"[:2000]}


def collect(probe_torch=False):
    report = {
        "schema": "zone-rush-hardware-v1",
        "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "os": {"system": platform.system(), "release": platform.release(),
               "machine": platform.machine()},
        "python": {"version": platform.python_version(), "implementation": platform.python_implementation()},
        "logical_cpus": os.cpu_count(),
        "nvidia_smi": command(["nvidia-smi", "--query-gpu=name,driver_version,memory.total,compute_cap",
                               "--format=csv,noheader,nounits"]),
        "torch": {"probed": False},
        "ready_for_games": False,
    }
    if probe_torch:
        probe = command([sys.executable, "-c", TORCH_PROBE], timeout=45)
        report["torch"] = {"probed": True, "process": probe}
        if probe.get("exit_code") == 0:
            try:
                report["torch"].update(json.loads(probe["stdout"]))
            except (ValueError, TypeError):
                report["torch"]["error"] = "CUDA probe did not return valid JSON"
    devices = report["torch"].get("devices", [])
    report["suggested_backend"] = "cuda" if any(d.get("kernel_ok") is True for d in devices) else "cpu"
    report["note"] = ("Hardware check only. A working CUDA kernel is required before GPU scheduling; "
                      "game/referee parity and throughput checks are still required.")
    def redact(value):
        if isinstance(value, dict):
            return {key: redact(item) for key, item in value.items()}
        if isinstance(value, list):
            return [redact(item) for item in value]
        if isinstance(value, str):
            value = value.replace(str(Path.home()), "<user-home>")
            value = re.sub(r"(?i)[a-z]:[\\/]users[\\/][^\\/\s]+", "<user-home>", value)
            return re.sub(r"/(?:home|Users)/[^/\s]+", "<user-home>", value)
        return value
    return redact(report)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--torch", action="store_true", help="Import PyTorch in an isolated child process and run a small CUDA kernel")
    parser.add_argument("--output", default="hardware.json")
    args = parser.parse_args()
    report = collect(args.torch)
    atomic_json(args.output, report)
    print(f"Saved {Path(args.output).resolve()}")
    print(f"Hardware recommendation: {report['suggested_backend']}; game execution is not yet certified.")
    for device in report["torch"].get("devices", []):
        print(f"GPU {device['index']}: {device['name']}; CUDA kernel {'PASS' if device['kernel_ok'] else 'FAIL'}")


if __name__ == "__main__":
    main()
