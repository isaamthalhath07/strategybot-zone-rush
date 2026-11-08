"""Actual full-size catalog/registration mechanics; no20k-game execution here."""
from collections import Counter, defaultdict
import copy
import json
from pathlib import Path
import tempfile
import unittest

from evolution import oversight, runner
from evolution.genomes import GenomeSpace, digest
from primary_campaign import core, run


class PrimaryCampaignTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cache = core.ROOT/'.cache'
        cache.mkdir(exist_ok=True)
        cls.temporary = tempfile.TemporaryDirectory(prefix='primary-core-test-', dir=cache)
        cls.directory = Path(cls.temporary.name).resolve()
        if not cls.directory.is_relative_to(cache.resolve()):
            raise ValueError('Test temporary path escaped workspace')
        cls.manifest = core.create_catalog(cls.directory, 202611090041)
        cls.manifest, cls.catalog = core.load_catalog(cls.directory)
        cls.registration = core.prepare_generation(cls.directory, 0)

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def test_full_two_million_plan_and_split_disjoint_rotational_maps(self):
        self.assertEqual(self.manifest['profile'], 'full_primary')
        self.assertEqual(self.manifest['scheduled_games'], 2000000)
        self.assertEqual(self.manifest['requested_primary_games'], 2000000)
        self.assertEqual(self.manifest['training_generations'], 80)
        self.assertEqual(len(self.catalog), 10000)
        self.assertEqual(Counter(board['phase'] for board in self.catalog),
                         {'train': 8000, 'development': 1000, 'final': 1000})
        self.assertEqual(len({board['id'] for board in self.catalog}), 10000)
        self.assertEqual(len({board['seed'] for board in self.catalog}), 10000)
        self.assertEqual(len({board['rotation_orbit'] for board in self.catalog}), 10000)
        self.assertFalse({board['rotation_orbit'] for board in self.catalog} & core.historical_map_ids())

    def test_registration_has20k_single_assignments60k_new_rivals_and_balanced_candidates(self):
        checks = core.validate_registration(self.registration, self.manifest, self.catalog)
        self.assertEqual(checks['games'], 20000)
        self.assertEqual(checks['new_rivals'], 60000)
        self.assertEqual(set(checks['candidate_games'].values()), {2500})
        self.assertEqual((checks['pair_min'], checks['pair_max']), (156, 157))
        by_map, field_pairs, candidate_strata = defaultdict(Counter), Counter(), defaultdict(Counter)
        candidate_switches = 0
        prior = None
        for fixture in self.registration['fixtures']:
            by_map[fixture['map_index']][fixture['seat'], fixture['token']] += 1
            field_pairs[fixture['field'], fixture['seat'], fixture['token']] += 1
            candidate_strata[fixture['candidate']][fixture['seat'], fixture['token'], fixture['field']] += 1
            candidate_switches += fixture['candidate'] != prior
            prior = fixture['candidate']
        self.assertEqual(len(by_map), 100)
        for crossings in by_map.values():
            self.assertEqual(sum(crossings.values()), 200)
            self.assertEqual(set(crossings.values()), {12, 13})
        self.assertEqual(len(field_pairs), 64)
        self.assertEqual(set(field_pairs.values()), {312, 313})
        for strata in candidate_strata.values():
            self.assertEqual(len(strata), 64)
            self.assertEqual(set(strata.values()), {39, 40})
        self.assertGreater(candidate_switches, 10000)

    def test_unchanged_policy_logic_exact_incumbent_and_no_paired_crossproduct(self):
        space = GenomeSpace((core.ROOT/'bot.py').read_bytes())
        self.assertEqual(self.registration['candidates'][0]['sha256'], core.INCUMBENT)
        for candidate in self.registration['candidates']:
            self.assertEqual(Path(candidate['path']).read_bytes(), space.export(candidate['genes']))
        task_ids = {(fixture['map_index'], fixture['episode']) for fixture in self.registration['fixtures']}
        self.assertEqual(len(task_ids), 20000)
        self.assertFalse(self.registration['paired_controls'])
        self.assertEqual(self.registration['bmcts_audits'], 0)
        self.assertFalse(self.registration['promotion_allowed'])

    def test_next_generation_and_reserved_holdouts_cannot_run_before_audit(self):
        with self.assertRaises((ValueError, FileNotFoundError)):
            core.prepare_generation(self.directory, 1)
        self.assertFalse((self.directory/'train_001/registration.json').exists())
        with self.assertRaises(ValueError):
            core.prepare_generation(self.directory, 80)
        self.assertEqual({board['phase'] for board in self.catalog if board['map_index'] >= 8000},
                         {'development', 'final'})

    def test_reordered_or_reassigned_tasks_fail_registration_audit(self):
        changed = copy.deepcopy(self.registration)
        first = changed['fixtures'][0]
        first['candidate'] = changed['candidates'][1]['sha256']
        first['id'] = digest(core.canonical({key: value for key, value in first.items() if key != 'id'}))
        with self.assertRaises(ValueError):
            core.validate_registration(changed, self.manifest, self.catalog)
        # An opponent cannot be copied into another game, even with the right
        # family and perfectly legal decisions.
        changed = copy.deepcopy(self.registration)
        changed['fixtures'][1]['opponents'][0] = copy.deepcopy(changed['fixtures'][0]['opponents'][0])
        fixture = changed['fixtures'][1]
        fixture['id'] = digest(core.canonical({key: value for key, value in fixture.items() if key != 'id'}))
        with self.assertRaises(ValueError):
            core.validate_registration(changed, self.manifest, self.catalog)

    def test_one_actual_primary_fixture_regenerates_all_actions_in_two_referees(self):
        fixture = self.registration['fixtures'][0]
        candidate = next(c for c in self.registration['candidates'] if c['sha256'] == fixture['candidate'])
        row = runner.play_game(candidate, fixture, self.registration['sources'])
        runner.verify_row(row, candidate, fixture)
        proof = run.audit_task(candidate, fixture, self.registration['sources'], row)
        self.assertEqual(proof['callbacks_regenerated'], 320)
        self.assertGreaterEqual(proof['public_memory_oracles'], 80)
        self.assertEqual(proof['row_sha256'], digest(core.canonical(row)))
        self.assertEqual(len(row['actions']), 80)
        self.assertEqual(sum(rec['calls'] for rec in row['timing']), 320)
        # This isolated test is never admitted as a completed20k primary stage.
        self.assertFalse((self.directory/'train_000/audit.json').exists())

    def test_checkpoints_recover_only_an_incomplete_tail(self):
        directory = self.directory/'checkpoint_test'
        directory.mkdir(exist_ok=True)
        path = directory/'rows.jsonl'
        valid = core.canonical(dict(fixture='one'))+b'\n'
        tail = b'{"fixture":"interrupted'
        path.write_bytes(valid+tail)
        self.assertEqual(run.completed_lines(path), [dict(fixture='one')])
        self.assertEqual(path.read_bytes(), valid)
        backups = list(directory.glob('*.bin'))
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_bytes(), tail)
        path.write_bytes(valid+b'{broken\n')
        with self.assertRaises(ValueError):
            run.completed_lines(path)

    def test_rotational_orbit_dedup_is_stricter_than_content_hash(self):
        base = self.catalog[0]['base']
        rotated = [base[(7-c)*8+r] for r in range(8) for c in range(8)]
        self.assertEqual(core.rotation_orbit(base), core.rotation_orbit(rotated))
        asymmetric = next(board['base'] for board in self.catalog
                          if board['base'] != [board['base'][(7-c)*8+r] for r in range(8) for c in range(8)])
        rotated = [asymmetric[(7-c)*8+r] for r in range(8) for c in range(8)]
        self.assertNotEqual(digest(bytes(asymmetric)), digest(bytes(rotated)))
        self.assertEqual(core.rotation_orbit(asymmetric), core.rotation_orbit(rotated))


if __name__ == '__main__':
    unittest.main()
