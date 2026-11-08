"""Full-size assignment mathematics and OS-held crash recovery; no game runs."""
from collections import Counter, defaultdict
from fractions import Fraction
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from evolution.maps import generate
from campaign_holdout import core, run


class ScheduleAndOwnershipTests(unittest.TestCase):
    def test_exact_metric_is_invariant_to_completion_order_and_ties_use_score_hash(self):
        cells = {(seat, token, field): [float((seat+token+field)%7)/2, 39+(field%2)]
                 for seat in range(4) for token in range(1, 5) for field in range(4)}
        self.assertEqual(core._exact_metric(cells), core._exact_metric(dict(reversed(list(cells.items())))))
        value = core._exact_metric(cells)
        entries = [dict(sha256=sha, standardized_pw_fraction=[value.numerator, value.denominator],
                        score_sum=score, games=25000) for sha, score in (("c", 1000), ("b", 1001), ("a", 1001))]
        self.assertEqual([r["sha256"] for r in core._rank(entries)], ["a", "b", "c"])

    def test_1000_map_assignment_covers200k_once_and_balances_all64_cells(self):
        boards = generate(1000, 202611090823)
        candidates = [dict(sha256=str(i)) for i in range(8)]
        manifest = {"campaign_id": "assignment-mathematics-only"}
        for phase, start, choices in (("development", 8000, candidates), ("final", 9000, candidates[:1])):
            catalog = [dict(board, phase=phase, map_index=start+i) for i, board in enumerate(boards)]
            counts, cells, tasks = Counter(), defaultdict(Counter), set()
            # Rival recipe has separate real tests; isolate assignment counts
            # without constructing1.2m rival objects. These are NOT runnable jobs.
            with patch.object(core.primary, "expected_opponents", return_value=[]):
                for block in range(10):
                    fixtures = core._fixtures(manifest, catalog, phase, block, choices)
                    self.assertEqual(len(fixtures), 20000)
                    for fixture in fixtures:
                        key = fixture["map_index"], fixture["episode"]
                        self.assertNotIn(key, tasks)
                        tasks.add(key)
                        sha = fixture["candidate"]
                        counts[sha] += 1
                        cells[sha][fixture["seat"], fixture["token"], fixture["field"]] += 1
            self.assertEqual(len(tasks), 200000)
            self.assertEqual(set(counts.values()), {25000 if phase == "development" else 200000})
            for strata in cells.values():
                self.assertEqual(len(strata), 64)
                self.assertEqual(set(strata.values()), {390, 391} if phase == "development" else {3125})

    def test_os_lock_rejects_another_owner_and_recovers_after_process_death(self):
        cache = (core.ROOT/".cache").resolve()
        with tempfile.TemporaryDirectory(prefix="heldout-lock-", dir=cache) as name:
            stage = Path(name).resolve(); self.assertTrue(stage.is_relative_to(cache))
            code = "from campaign_holdout.run import owner\nfrom pathlib import Path\nimport sys\nwith owner(Path(sys.argv[1])):\n print('LOCKED',flush=True)\n sys.stdin.read(1)\n"
            process = subprocess.Popen([sys.executable, "-c", code, str(stage)], cwd=core.ROOT,
                                       stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            try:
                self.assertEqual(process.stdout.readline().strip(), b"LOCKED")
                with self.assertRaises(ValueError):
                    with run.owner(stage):
                        self.fail("Concurrent ownership accepted")
                process.kill()
                process.wait(timeout=5)
                with run.owner(stage):
                    self.assertTrue((stage/".executor.lock").exists())
            finally:
                if process.poll() is None:
                    process.kill(); process.wait(timeout=5)
                process.stdin.close(); process.stdout.close(); process.stderr.close()


if __name__ == "__main__":
    unittest.main()
