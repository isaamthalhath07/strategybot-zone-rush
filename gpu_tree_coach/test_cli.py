"""The bounded CLI publishes a receipt only after all inputs pass."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from .test_tree import job


class CLITests(unittest.TestCase):
    def call(self, source, output):
        return subprocess.run([sys.executable, '-m', 'gpu_tree_coach', str(source), str(output),
                               '--roots-per-chunk', '1', '--verify-reference'],
                              cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True, timeout=60)

    def test_success_fresh_output_and_late_failure_never_publish_partial_receipt(self):
        private_temp = Path(__file__).resolve().parent/'.cache'
        private_temp.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=private_temp) as directory:
            root = Path(directory)
            source, output = root/'roots.jsonl', root/'receipt.jsonl'
            source.write_text(json.dumps(job(horizon=1, simulations=12)[1])+'\n', encoding='utf8')
            success = self.call(source, output)
            self.assertEqual(success.returncode, 0, success.stderr)
            rows = [json.loads(line) for line in output.read_text(encoding='utf8').splitlines()]
            self.assertEqual([row['kind'] for row in rows], ['root_result', 'summary'])
            self.assertTrue(rows[1]['result']['exact_reference_verified'])
            self.assertTrue(rows[1]['result']['results_streamed'])
            original = output.read_bytes()
            self.assertNotEqual(self.call(source, output).returncode, 0)
            self.assertEqual(original, output.read_bytes())
            first = job(root_id='first', horizon=1, simulations=12)[1]
            second = job(root_id='second', horizon=1, simulations=12)[1]
            bad = job(root_id='third')[1]; bad['actual_private_game'] = {}
            source.write_text('\n'.join(json.dumps(row) for row in (first, second, bad))+'\n', encoding='utf8')
            failure_output = root/'must-not-exist.jsonl'
            failure = self.call(source, failure_output)
            self.assertNotEqual(failure.returncode, 0)
            self.assertFalse(failure_output.exists())
            self.assertEqual(list(root.glob('.tree-unpublished-*')), [])


if __name__ == '__main__':
    unittest.main()
