"""Cross-process exclusivity and crash release before any checkpoint repair."""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from distributed_campaign import protocol as p, worker


ROOT = Path(__file__).resolve().parents[1]


class ResultLockTests(unittest.TestCase):
    def test_second_worker_rejected_before_partial_tail_recovery_and_crash_releases(self):
        parent = ROOT/'.cache/distributed_campaign'
        parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='lock-test-', dir=parent) as name:
            output = Path(name)
            checkpoint = output/'games.jsonl'
            body = b'{"active_partial":'
            checkpoint.write_bytes(body)
            code = """import sys,time
from distributed_campaign.protocol import ResultLease
with ResultLease(sys.argv[1]):
    print('LOCKED', flush=True)
    time.sleep(20)
"""
            process = subprocess.Popen([sys.executable, '-c', code, str(output)], cwd=ROOT,
                                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                                       creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            try:
                self.assertEqual(process.stdout.readline().strip(), 'LOCKED')
                before = checkpoint.stat().st_mtime_ns
                with self.assertRaises(p.ResultBusy):
                    worker.execute(output/'does-not-need-to-exist', 'invalid', output, workers=1)
                self.assertEqual(checkpoint.read_bytes(), body)
                self.assertEqual(checkpoint.stat().st_mtime_ns, before)
                process.terminate()  # Only this test's own child; emulate a crash.
                process.communicate(timeout=10)
                with p.ResultLease(output):
                    self.assertTrue((output/'.worker.lock').exists())
                self.assertEqual(checkpoint.read_bytes(), body)
            finally:
                if process.poll() is None:
                    process.kill()
                    process.communicate(timeout=10)


if __name__ == '__main__':
    unittest.main()
