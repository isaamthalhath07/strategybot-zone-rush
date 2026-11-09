"""Four-arm preregistration corruption tests; no games are executed."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from confirmation_campaign import architectures, prepare
from evolution import runner
from primary_campaign import core


class ArchitectureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='architecture-plan-unit-', dir=core.ROOT/'.cache')
        cls.base = Path(cls.temp.name)
        cls.space, _ = core.sources_space()
        genes = dict(cls.space.genes, backfire_cost=1.674416, feint_weight=1.167526,
                     shield_prior=.333592, shield_weight=1.227437, stay_prior=.771476)
        candidate = cls.base/'mock_unpromoted_50d.py'
        candidate.write_bytes(cls.space.export(genes))
        if core.digest(candidate.read_bytes()) != prepare.CHALLENGER:
            raise AssertionError('Test must use the exact frozen 50d source')
        cls.parent = dict(campaign_id='mock-primary-no-games', catalog_sha256='mock-catalog',
                          guards=core.guard_sources(), sources={name: runner.source_entry(core.ROOT/path) for name, path in {
                              'planner': 'bot.py', 'research': 'tester_bots/research_alternative.py',
                              'racer': 'tester_bots/racer.py', 'blocker': 'tester_bots/blocker.py'}.items()})
        original = dict(sha256=prepare.CHALLENGER, path=str(candidate), genes=genes, name='mock-audited-discovery-source')
        real_read = core.read_sealed
        def prior(path):
            path = Path(path)
            if path.parent.name.startswith('train_'):
                if path.name == 'summary.json':
                    return dict(candidates=[dict(sha256=prepare.CHALLENGER)])
                if path.name == 'registration.json':
                    return dict(candidates=[original])
                raise ValueError('Unexpected mocked admission')
            return real_read(path)
        cls.patches = [
            patch.object(core, 'load_catalog', return_value=(cls.parent, [])),
            patch.object(core, 'validated_audit', side_effect=lambda path: dict(generation=int(Path(path).name[-3:]),
                         games_sha256='mock-no-games-executed', registration_sha256='mock-prior-admission')),
            patch.object(core, 'read_sealed', side_effect=prior),
            patch.object(core, 'historical_map_ids', return_value=set()),
            patch.object(architectures, 'distribution_roots', return_value=[]),
        ]
        for item in cls.patches:
            item.start()
        try:
            cls.v1 = cls.base/'v1'
            prepare.make(cls.base/'mock-campaign', cls.v1, map_count=4)
            cls.before = {p.name: p.read_bytes() for p in cls.v1.iterdir()}
            cls.registration = architectures.make(cls.v1, cls.base/'v2')
        except BaseException:
            for item in reversed(cls.patches):
                item.stop()
            cls.temp.cleanup()
            raise

    @classmethod
    def tearDownClass(cls):
        for item in reversed(cls.patches):
            item.stop()
        cls.temp.cleanup()

    def test_exact_four_arm_balance_sources_instances_and_unmodified_v1(self):
        result = architectures.validate(self.registration)
        self.assertEqual(result, dict(games=1024, matched_conditions=256, arms=4, maps=4,
                                     unique_actor_instances=4096, comparisons=6, primary_credit=0, bmcts_audits=0,
                                     runtime_qualification_tasks=8, executed_games=0, promotion_allowed=False))
        self.assertEqual({p.name: p.read_bytes() for p in self.v1.iterdir()}, self.before)
        self.assertEqual([c['sha256'] for c in self.registration['candidates']], list(architectures.ARMS))
        self.assertTrue((self.base/'v2/v1_unused_superseded.json').exists())
        runtime = [f for f in self.registration['fixtures'] if f['id'] in self.registration['runtime_qualification_task_ids']]
        self.assertEqual(len(runtime), 8)
        self.assertEqual({f['candidate'] for f in runtime}, set(architectures.ARMS))
        self.assertFalse(self.registration['protocol']['existing_numeric_only_qualification_sufficient'])

    def test_all_four_policies_share_params_but_no_actor_or_task_ids(self):
        groups = {}
        for fixture in self.registration['fixtures']:
            groups.setdefault(fixture['pair_key'], []).append(fixture)
        for group in groups.values():
            params = [[{k: v for k, v in spec.items() if k != 'id'} for spec in f['opponents']] for f in group]
            self.assertTrue(all(value == params[0] for value in params))
            self.assertEqual(len({f['id'] for f in group}), 4)
            self.assertEqual(len({f['focal_actor_id'] for f in group}), 4)
            self.assertEqual(len({s['id'] for f in group for s in f['opponents']}), 12)

    def test_missing_duplicate_changed_or_reordered_arms_rejected(self):
        for mode in ('missing', 'duplicate', 'source', 'reordered', 'genes'):
            value = copy.deepcopy(self.registration)
            if mode == 'missing':
                value['candidates'].pop()
            elif mode == 'duplicate':
                value['candidates'][3] = copy.deepcopy(value['candidates'][2])
            elif mode == 'source':
                value['candidates'][2]['path'] = value['candidates'][0]['path']
            elif mode == 'reordered':
                value['candidates'].reverse()
            else:
                value['candidates'][1]['genes']['backfire_cost'] += .1
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                architectures.validate(value)

    def test_rehashed_unmatched_opponents_or_reused_id_rejected(self):
        for mode in ('parameters', 'rival', 'focal', 'condition', 'missing'):
            value = copy.deepcopy(self.registration)
            fixture = value['fixtures'][1]
            if mode == 'parameters':
                fixture['opponents'][0]['epsilon'] += .01
            elif mode == 'rival':
                fixture['opponents'][0]['id'] = value['fixtures'][0]['opponents'][0]['id']
            elif mode == 'focal':
                fixture['focal_actor_id'] = value['fixtures'][0]['focal_actor_id']
            elif mode == 'condition':
                fixture['token'] = fixture['token'] % 4+1
            else:
                value['fixtures'].pop()
            fixture['id'] = core.digest(core.canonical({k: v for k, v in fixture.items() if k != 'id'}))
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                architectures.validate(value)

    def test_map_leak_mutation_and_new_unregistered_seed_rejected(self):
        orbit = self.registration['maps'][0]['rotation_orbit']
        with self.assertRaises(ValueError):
            architectures.validate(self.registration, excluded={orbit})
        for mode in ('map', 'seed'):
            value = copy.deepcopy(self.registration)
            if mode == 'map':
                value['maps'][0]['base'] = [1]*64
            else:
                value['protocol']['seed'] += 1
                value['campaign_id'] = core.digest(core.canonical(value['protocol']))
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                architectures.validate(value)

    def test_a_played_or_distributed_v1_cannot_be_relabelled_unused(self):
        marker = self.v1/'games.jsonl'
        marker.write_text('{}\n')
        try:
            with self.assertRaises(ValueError):
                architectures.validate(self.registration)
        finally:
            marker.unlink()
        outside = self.base/'outside-return'
        outside.mkdir()
        header = outside/'header.json'
        header.write_text(json.dumps({'campaign_id': self.registration['protocol']['parent_v1_control_id']}))
        with self.assertRaises(ValueError):
            architectures.validate(self.registration, distribution_roots=[outside])
        header.unlink()
        row = outside/'records.jsonl'
        v1 = core.read_sealed(self.v1/'registration.json')
        row.write_text(json.dumps({'record': {'fixture': v1['fixtures'][0]['id']}})+'\n')
        with self.assertRaises(ValueError):
            architectures.validate(self.registration, distribution_roots=[outside])
        row.unlink()

    def test_mode_primary_search_promotion_and_qualification_drift_rejected(self):
        for key, replacement in (('role', 'primary_assignment'), ('phase', 'train'), ('generation', 1),
                                 ('executed_games', 1), ('primary_games_accepted', 1024), ('worker_primary_credit', 1),
                                 ('bmcts_audits', 1), ('promotion_allowed', True), ('planned_games', 1025)):
            value = copy.deepcopy(self.registration)
            value[key] = replacement
            with self.subTest(key=key), self.assertRaises(ValueError):
                architectures.validate(value)
        value = copy.deepcopy(self.registration)
        value['runtime_qualification_task_ids'].pop()
        with self.assertRaises(ValueError):
            architectures.validate(value)

    def test_six_simultaneous_comparisons_are_fixed_before_outcomes(self):
        plan = self.registration['protocol']['inference']
        self.assertEqual(len(plan['paired_comparisons']), 6)
        self.assertEqual(len({(p['first'], p['second']) for p in plan['paired_comparisons']}), 6)
        self.assertAlmostEqual(plan['per_comparison_alpha'], .05/6)
        self.assertEqual(plan['bootstrap_replicates'], 60000)
        self.assertAlmostEqual(plan['percentile_probabilities'][0], .05/12)
        value = copy.deepcopy(self.registration)
        value['protocol']['inference']['bootstrap_seed'] += 1
        value['campaign_id'] = core.digest(core.canonical(value['protocol']))
        with self.assertRaises(ValueError):
            architectures.validate(value)


if __name__ == '__main__':
    unittest.main()
