"""Verify the selected offline environment; this does not certify game jobs."""
import sys
from pathlib import Path

try:
    from .doctor import atomic_json, collect
except ImportError:
    from doctor import atomic_json, collect


def compatible(report):
    probe = report.get("torch", {})
    return (str(probe.get("version", "")).split("+")[0] == "2.11.0"
            and probe.get("cuda_build") == "12.8"
            and any(device.get("kernel_ok") is True for device in probe.get("devices", [])))


def main():
    report = collect(probe_torch=True)
    target = Path(__file__).resolve().parent/"hardware.json"
    atomic_json(target, report)
    if not compatible(report):
        print("GPU environment check did not pass. Send hardware.json to the campaign owner.")
        print("No game jobs were started. The full report explains missing packages or driver/kernel errors.")
        return 1
    print("GPU environment PASS. Send hardware.json to the campaign owner.")
    print("This checks the environment only; each laptop still needs its own successful job validation.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
