"""Real packaged actor execution, checkpoint resume and strict owner validation.

Uses already-recorded fixtures as shadow controls, never as new primary work.
"""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zipfile

from distributed_campaign import owner, protocol as p
from evolution import oversight
from primary_campaign import core, run


class DistributedExecutionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = core.ROOT/'.cache/primary/campaign_v1_20261109/train_000'
        if not (cls.source/'registration.json').exists():
            raise unittest.SkipTest('Local recorded primary evidence unavailable')
        parent = core.ROOT/'.cache/distributed_campaign'
        parent.mkdir(parents=True, exist_ok=True)
        cls.temporary = tempfile.TemporaryDirectory(prefix='shadow-test-', dir=parent)
        cls.directory = Path(cls.temporary.name).resolve()
        if not cls.directory.is_relative_to(parent.resolve()):
            raise ValueError('Test path escaped workspace')
        cls.original = core.read_sealed(cls.source/'registration.json')
        selected, seen = [], set()
        for fixture in cls.original['fixtures']:
            if fixture['candidate'] not in seen:
                selected.append(fixture)
                seen.add(fixture['candidate'])
            if len(selected) == 8:
                break
        cls.registration = dict(cls.original, fixtures=selected)
        cls.distribution = owner.build_shards(cls.registration, cls.directory/'packages', ['helper_A', 'helper_B'])
        cls.plan = dict(role='mechanics_shadow', campaign_id=cls.original['campaign_id'], generation=0,
                        owner_runtime=p.runtime(), distribution=cls.distribution)
        cls.rows = []
        for shard in cls.distribution['shards']:
            root = Path(shard['bundle_directory'])
            output = root/'results'
            command = [sys.executable, '-m', 'distributed_campaign.worker', '--root', '.',
                       '--expected-manifest-sha', shard['bundle_sha256'], '--output', str(output), '--workers', '1']
            kwargs = dict(cwd=root, capture_output=True, text=True, timeout=60,
                          creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            first = subprocess.run(command+['--limit', '1'], **kwargs)
            if first.returncode:
                raise AssertionError(first.stderr)
            partial = p.loads((output/'progress.json').read_bytes())
            if partial['completed_games'] != 1 or partial['complete']:
                raise AssertionError('Worker falsely marked partial assignment complete')
            finished = subprocess.run(command, **kwargs)
            if finished.returncode:
                raise AssertionError(finished.stderr)
            second = p.loads((output/'progress.json').read_bytes())
            if second['completed_games'] != 4 or not second['complete'] or second['this_run_games'] != 3:
                raise AssertionError('Worker resume did not finish exactly the remaining assigned tasks')
            checkpoint = (output/'games.jsonl').read_bytes()
            resumed = subprocess.run(command, **kwargs)
            if resumed.returncode:
                raise AssertionError(resumed.stderr)
            if p.loads((output/'progress.json').read_bytes())['this_run_games'] != 0 or (output/'games.jsonl').read_bytes() != checkpoint:
                raise AssertionError('Completed helper checkpoint repeated work')
            rows, header, digest = owner.validate_result(cls.plan, cls.registration, shard['id'], output)
            if digest != p.sha(checkpoint):
                raise AssertionError('Owner did not bind the exact transferred checkpoint snapshot')
            cls.rows.extend(rows)
        wanted = {fixture['id'] for fixture in selected}
        cls.expected = {}
        with (cls.source/'games.jsonl').open() as handle:
            for line in handle:
                row = p.loads(line)
                if row['fixture'] in wanted:
                    cls.expected[row['fixture']] = row

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, 'temporary'):
            cls.temporary.cleanup()

    def test_eight_actual_packaged_games_match_recorded_all80_turn_actions_and_sources(self):
        self.assertEqual(len(self.rows), 8)
        self.assertEqual(len({row['fixture'] for row in self.rows}), 8)
        for row in self.rows:
            expected = self.expected[row['fixture']]
            for key in owner.BEHAVIOR_FIELDS:
                self.assertEqual(row[key], expected[key], key)
            self.assertEqual(sum(item['calls'] for item in row['timing']), 320)
        self.assertEqual(sum(len(row['actions']) for row in self.rows), 640)

    def test_independent_original_all_actor_two_referee_audit_passes_all_shadow_games(self):
        candidates = {candidate['sha256']: candidate for candidate in self.original['candidates']}
        fixtures = {fixture['id']: fixture for fixture in self.registration['fixtures']}
        total = 0
        for row in self.rows:
            outcome = oversight.audit_game(candidates[row['candidate']], fixtures[row['fixture']],
                                           self.original['sources'], row, regenerate=True)
            total += outcome['callbacks_regenerated']
        self.assertEqual(total, 2560)

    def test_bundle_has_explicit_sources_and_no_keys_authority_or_reserved_maps(self):
        ids = [identity for shard in self.distribution['shards'] for identity in shard['fixture_ids']]
        self.assertEqual(len(ids), len(set(ids)))
        for shard in self.distribution['shards']:
            with zipfile.ZipFile(shard['archive']) as zipped:
                names = zipped.namelist()
                self.assertFalse(any('.authority' in name or '.cache' in name or name.endswith('.key')
                                     or 'catalog.json' in name or 'owner.py' in name for name in names))
            bundle = p.verify_bundle(shard['bundle_directory'], shard['bundle_sha256'])
            self.assertEqual(bundle['role'], 'mechanics_shadow')
            self.assertFalse(bundle['cuda_used_by_policy'])
            self.assertEqual(bundle['worker_primary_credit'], 0)

    def test_owner_rejects_reassigned_or_score_corrupted_results_and_ignores_progress_claims(self):
        shard = self.distribution['shards'][0]
        original = Path(shard['bundle_directory'])/'results'
        target = self.directory/'tamper_result'
        target.mkdir(exist_ok=True)
        (target/'header.json').write_bytes((original/'header.json').read_bytes())
        body = (original/'games.jsonl').read_bytes()
        (target/'games.jsonl').write_bytes(body)
        (target/'progress.json').write_text('{"completed_games":2000000,"worker_primary_credit":2000000}')
        rows, _, _ = owner.validate_result(self.plan, self.registration, shard['id'], target)
        self.assertEqual(len(rows), 4)
        bad = copy.deepcopy(rows)
        bad[0]['scores'][0] += 1
        (target/'games.jsonl').write_bytes(b''.join(p.canonical(row)+b'\n' for row in bad))
        with self.assertRaises(ValueError):
            owner.validate_result(self.plan, self.registration, shard['id'], target)
        bad = copy.deepcopy(rows)
        bad[0]['fixture'] = self.distribution['shards'][1]['fixture_ids'][0]
        (target/'games.jsonl').write_bytes(b''.join(p.canonical(row)+b'\n' for row in bad))
        with self.assertRaises(ValueError):
            owner.validate_result(self.plan, self.registration, shard['id'], target)

    def test_physical_replay_alone_does_not_replace_actual_policy_regeneration(self):
        row = copy.deepcopy(self.rows[0])
        fixture = next(f for f in self.registration['fixtures'] if f['id'] == row['fixture'])
        candidate = next(c for c in self.original['candidates'] if c['sha256'] == row['candidate'])
        game = core.runner.engine.Game(base=fixture['base'], start_token=fixture['token'])
        row['actions'] = [['STAY']*4 for _ in range(80)]
        for actions in row['actions']:
            game.step(actions)
        row['scores'] = game.score
        seat = fixture['seat']
        row['focal_score'] = game.score[seat]
        row['focal_pw'] = sum(1 if game.score[seat] > score else .5 if game.score[seat] == score else 0
                              for rival, score in enumerate(game.score) if rival != seat)
        run.runner.verify_row(row, candidate, fixture)  # Physically legal can still be the wrong actor.
        with self.assertRaisesRegex(ValueError, 'does not regenerate'):
            oversight.audit_game(candidate, fixture, self.original['sources'], row, regenerate=True)


if __name__ == '__main__':
    unittest.main()
