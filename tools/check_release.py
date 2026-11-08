"""Run the compact release's automated validation without Git or network access."""
from pathlib import Path
import os
import shutil
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]


def main():
    os.chdir(ROOT)
    sys.path.insert(0, str(ROOT))
    suite = unittest.defaultTestLoader.discover(str(ROOT/"tests"), top_level_dir=str(ROOT))
    result = unittest.TextTestRunner(verbosity=1).run(suite)
    if not result.wasSuccessful():
        return 1
    node = shutil.which("node")
    if node:
        return subprocess.run([node, str(ROOT/"tests/test_ui.js")], cwd=ROOT).returncode
    print("Python checks passed. Optional interface logic checks need Node.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
