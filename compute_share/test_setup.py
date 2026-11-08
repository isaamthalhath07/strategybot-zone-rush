"""The setup must not mistake CUDA detection for successful execution."""
import copy
from pathlib import Path
import unittest

from compute_share.verify_cuda import compatible


class SetupTests(unittest.TestCase):
    def test_requires_pinned_build_and_real_kernel(self):
        report = {"torch": {"version": "2.11.0+cu128", "cuda_build": "12.8",
                            "cuda_available": True, "devices": [{"kernel_ok": True}]}}
        self.assertTrue(compatible(report))
        for change in ({"version": "2.6.0+cu124"}, {"cuda_build": "12.4"},
                       {"devices": [{"kernel_ok": False}]}, {"devices": [{"kernel_ok": 1}]},
                       {"devices": []}):
            bad = copy.deepcopy(report)
            bad["torch"].update(change)
            self.assertFalse(compatible(bad))
        self.assertFalse(compatible({}))

    def test_setup_installs_only_into_its_separate_environment(self):
        script = (Path(__file__).parent/"setup_gpu.cmd").read_text()
        installs = [line for line in script.splitlines() if "pip install" in line]
        self.assertEqual(len(installs), 1)
        self.assertTrue(installs[0].startswith('".venv-worker\\Scripts\\python.exe"'))
        self.assertIn('verify_cuda.py', script)
        self.assertNotIn('--system-site-packages', script)


if __name__ == "__main__":
    unittest.main()
