"""Regressions for discovered evaluation-order and bootstrap reproducibility risks."""
from collections import Counter
import copy
import unittest

from tools import benchmark


class BenchmarkDesignTests(unittest.TestCase):
    def test_candidates_are_interleaved_within_reproducible_fixture_blocks(self):
        names = ['a', 'b', 'c', 'd']
        fixtures = [dict(id='fixture-%d' % i) for i in range(12)]
        before = copy.deepcopy(fixtures)
        jobs = benchmark.ordered_jobs(names, fixtures, 9181)
        self.assertEqual(jobs, benchmark.ordered_jobs(names, fixtures, 9181))
        self.assertNotEqual(jobs, benchmark.ordered_jobs(names, fixtures, 9182))
        self.assertEqual(fixtures, before)
        self.assertEqual(Counter(name for name, _ in jobs), dict.fromkeys(names, 12))
        for start in range(0, len(jobs), len(names)):
            block = jobs[start:start+len(names)]
            self.assertEqual({name for name, _ in block}, set(names))
            self.assertEqual(len({fixture['id'] for _, fixture in block}), 1)
        with self.assertRaises(ValueError):
            benchmark.ordered_jobs(names, fixtures, True)

    def test_bootstrap_is_independent_of_completed_result_order(self):
        rows = []
        for i in range(32):
            for name in ('a', 'b'):
                rows.append(dict(candidate=name, fixture='fixture-%02d' % i,
                                 map_group='map-%02d' % (i//4),
                                 focal_pw=(i*7 % 4)/2 if name == 'a' else (i*11 % 7)/3))
        forward = benchmark.paired(rows, ['a', 'b'])
        self.assertEqual(forward, benchmark.paired(list(reversed(rows)), ['a', 'b']))


if __name__ == '__main__':
    unittest.main()
