"""Adversarial checks for the independent read-only stage monitor."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

from campaign_monitor import audit
from primary_campaign import core


class CampaignMonitorTests(unittest.TestCase):
    def test_directory_index_binding_rejects_copied_and_boolean_generations(self):
        manifest = {'profile': 'full_primary'}
        for generation in (0, True, '1'):
            with self.assertRaisesRegex(ValueError, 'directory index'):
                audit.metadata_identity(dict(generation=generation, phase='train', profile='full_primary'),
                                        1, manifest, 'copied stage')
        audit.metadata_identity(dict(generation=1, phase='train', profile='full_primary'), 1, manifest, 'proper stage')

    def test_global_ids_and_seeds_must_be_disjoint(self):
        for label in ('map', 'task', 'rival', 'seed'):
            seen = {}
            audit.unique_insert(seen, 'same', 0, label)
            with self.assertRaisesRegex(ValueError, 'Global duplicate'):
                audit.unique_insert(seen, 'same', 1, label)

    def test_live_partial_tail_is_observed_without_repair_or_rewrite(self):
        cache = core.ROOT/'.cache/campaign_monitor'
        cache.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='tail-test-', dir=cache) as name:
            path = Path(name)/'live.jsonl'
            body = b'{"complete":true}\n{"partial":'
            path.write_bytes(body)
            before = path.stat().st_mtime_ns
            rows, observed, tail = audit.lines_snapshot(path)
            self.assertEqual(rows, [{'complete': True}])
            self.assertEqual(observed, body)
            self.assertGreater(tail, 0)
            self.assertEqual(path.read_bytes(), body)
            self.assertEqual(path.stat().st_mtime_ns, before)
            path.write_bytes(b'{broken complete JSON}\n')
            with self.assertRaises(ValueError):
                audit.lines_snapshot(path)

    def test_actual_record_metadata_callback_and_score_consistency(self):
        fixture = dict(candidate='candidate', id='fixture', map_id='map', seat=0,
                       field='field', opponents=[{'id': str(i)} for i in range(3)])
        row = dict(candidate='candidate', fixture='fixture', map_id='map', focal_seat=0,
                   field='field', opponent_ids=['0', '1', '2'], faults=[], actions=[['STAY']*4 for _ in range(80)],
                   scores=[100, 80, 100, 120], focal_pw=1.5, focal_score=100,
                   timing=[dict(calls=80, first_ms=1., regular_max_ms=1., max_ms=1., total_ms=80.) for _ in range(4)])
        audit.check_row(row, fixture)
        for key, value in (('focal_pw', 3), ('focal_seat', 1), ('faults', ['fallback']), ('candidate', 'changed')):
            bad = copy.deepcopy(row)
            bad[key] = value
            with self.assertRaises(ValueError):
                audit.check_row(bad, fixture)
        bad = copy.deepcopy(row)
        bad['timing'][0]['calls'] = True
        with self.assertRaises(ValueError):
            audit.check_row(bad, fixture)

    def test_real_sealed_generation_zero_cannot_be_relabelled_by_directory(self):
        source = core.ROOT/'.cache/primary/campaign_v1_20261109'
        if not (source/'train_000/registration.json').exists():
            self.skipTest('Local campaign evidence is not part of a clean checkout')
        cache = core.ROOT/'.cache/campaign_monitor'
        cache.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='copied-stage-test-', dir=cache) as name:
            directory = Path(name)
            for filename in ('manifest.json', 'manifest.sha256', 'catalog.json', 'catalog.sha256'):
                (directory/filename).write_bytes((source/filename).read_bytes())
            fake = directory/'train_001'
            fake.mkdir()
            for filename in ('registration.json', 'registration.sha256'):
                (fake/filename).write_bytes((source/'train_000'/filename).read_bytes())
            before = {path: (path.read_bytes(), path.stat().st_mtime_ns) for path in directory.rglob('*') if path.is_file()}
            with self.assertRaisesRegex(ValueError, 'directory index'):
                audit.inspect(directory)
            for path, expected in before.items():
                self.assertEqual((path.read_bytes(), path.stat().st_mtime_ns), expected)


if __name__ == '__main__':
    unittest.main()
