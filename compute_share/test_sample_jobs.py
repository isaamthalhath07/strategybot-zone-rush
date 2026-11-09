"""Owner-side assignment guards; no GPU kernels or primary games are run."""
from pathlib import Path
import tempfile
import unittest

from compute_share.make_sample_jobs import ROOT, make


class SampleJobTests(unittest.TestCase):
    def setUp(self):
        self.cache = ROOT/'.cache'
        self.cache.mkdir(exist_ok=True)

    def test_invalid_library_options_create_no_partial_packages(self):
        for options in ({'laptops': 0}, {'laptops': True}, {'per_laptop': 17},
                        {'per_laptop': 1.0}, {'start_index': True}, {'start_index': -1},
                        {'horizon': 2.5}, {'horizon': True}, {'plans': False},
                        {'rollouts': 257}):
            with self.subTest(options=options), tempfile.TemporaryDirectory(dir=self.cache) as temp:
                target = Path(temp)/'jobs'
                with self.assertRaisesRegex(ValueError, 'Invalid diagnostic budget'):
                    make(target, **options)
                self.assertFalse(target.exists())

    def test_combined_resource_limit_rejects_before_packaging(self):
        # Individually legal settings can still exceed the batch worker's limit.
        with tempfile.TemporaryDirectory(dir=self.cache) as temp:
            target = Path(temp)/'jobs'
            with self.assertRaisesRegex(ValueError, '65,536 trajectories'):
                make(target, laptops=1, per_laptop=16, horizon=6, plans=32, rollouts=256)
            self.assertFalse(target.exists())

    def test_existing_directory_is_preserved(self):
        with tempfile.TemporaryDirectory(dir=self.cache) as temp:
            target = Path(temp)
            marker = target/'existing.txt'
            marker.write_text('retain', encoding='utf8')
            with self.assertRaises(FileExistsError):
                make(target, laptops=1, per_laptop=1)
            self.assertEqual(marker.read_text(encoding='utf8'), 'retain')


if __name__ == '__main__':
    unittest.main()
