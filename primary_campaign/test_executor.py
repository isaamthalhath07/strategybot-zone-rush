"""Opt-in800-game mechanics test of actual multiprocessing, audit and resume.

These games are explicitly a mechanics_test profile and admit ZERO primary
games. Evidence stays in .cache for independent inspection after this test.
"""
import json
import os
from pathlib import Path
import shutil
import tempfile
import time
import unittest
from unittest import mock

from primary_campaign import core, run


class PrimaryExecutorIntegrationTests(unittest.TestCase):
    def test_small_profile_real_games_all_actor_audit_resume_and_next_generation(self):
        cache = core.ROOT/'.cache'
        cache.mkdir(exist_ok=True)
        directory = Path(tempfile.mkdtemp(prefix='primary-executor-mechanics-', dir=cache)).resolve()
        self.assertTrue(directory.is_relative_to(cache.resolve()))
        before = (core.ROOT/'bot.py').read_bytes()
        shape = dict(core.DEFAULT_SHAPE, train_maps=8, development_maps=4,
                     final_maps=4, maps_per_generation=4)
        manifest = core.create_catalog(directory, 202611090042, shape)
        self.assertEqual(manifest['profile'], 'mechanics_test')
        self.assertEqual(manifest['requested_primary_games'], 2000000)
        self.assertEqual(manifest['scheduled_games'], 3200)
        with self.assertRaises((ValueError, FileNotFoundError)):
            core.prepare_generation(directory, 1)
        started = time.perf_counter()
        summary = run.execute_generation(directory, 0, workers=4)
        games_wall_s = time.perf_counter()-started
        self.assertEqual(summary['games_completed'], 800)
        self.assertEqual(summary['actual_callbacks'], 256000)
        self.assertEqual({row['games'] for row in summary['candidates']}, {100})
        self.assertFalse((directory/'train_000/audit.json').exists())
        with self.assertRaises((ValueError, FileNotFoundError)):
            core.prepare_generation(directory, 1)
        started = time.perf_counter()
        audit = run.audit_generation(directory, 0, workers=4)
        audit_wall_s = time.perf_counter()-started
        self.assertTrue(audit['approved'])
        self.assertTrue(audit['all_actors_regenerated'])
        self.assertEqual(audit['games_audited'], 800)
        self.assertEqual(audit['callbacks_regenerated'], 256000)
        self.assertEqual(audit['primary_games_accepted'], 0)
        self.assertEqual(audit['bmcts_audits'], 0)
        self.assertFalse(audit['promoted'])
        evidence_before = {path: (path.read_bytes(), path.stat().st_mtime_ns)
                           for path in (directory/'train_000').glob('*') if path.is_file()}
        with mock.patch.object(run, 'ProcessPoolExecutor', side_effect=AssertionError('Completed work resubmitted')):
            self.assertEqual(run.execute_generation(directory, 0, 4), summary)
            self.assertEqual(run.audit_generation(directory, 0, 4), audit)
        for path, expected in evidence_before.items():
            self.assertEqual((path.read_bytes(), path.stat().st_mtime_ns), expected)
        next_registration = core.prepare_generation(directory, 1)
        self.assertEqual(len(next_registration['fixtures']), 800)
        self.assertEqual(next_registration['candidates'][0]['sha256'], core.INCUMBENT)
        self.assertFalse((directory/'train_001/games.jsonl').exists())
        self.assertEqual((core.ROOT/'bot.py').read_bytes(), before)
        files = [path for path in (directory/'train_000').rglob('*') if path.is_file()]
        evidence_bytes = sum(path.stat().st_size for path in files)
        proof = dict(profile='mechanics_test', primary_games_accepted=0,
                     requested_primary_games=2000000, actual_mechanics_games=800,
                     mechanics_audit_replays=800, games_wall_s=games_wall_s,
                     audit_wall_s=audit_wall_s, workers=4, cpu_logical_cores=os.cpu_count(),
                     observed_game_throughput=800/games_wall_s,
                     observed_audit_throughput=800/audit_wall_s,
                     observed_stage_bytes=evidence_bytes,
                     projected_2m_stage_bytes=evidence_bytes*2500,
                     projected_2m_combined_wall_s=(games_wall_s+audit_wall_s)*2500,
                     projection_caveat='Linear extrapolation from this800-game CPU mechanics load; excludes heldout execution, process-isolated promotion, BMCTS and machine variability. No GPU proxy games.',
                     disk_free_bytes=shutil.disk_usage(directory).free,
                     all_actors_regenerated=True, resume_submissions=0,
                     next_generation_prepared_only=True, production_unchanged=True,
                     evidence_directory=str(directory))
        core.seal(directory/'mechanics_result.json', proof)
        print(json.dumps(proof, indent=2), flush=True)


if __name__ == '__main__':
    unittest.main()
