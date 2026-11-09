"""Transport must reject hidden inputs and changed source/data bundles."""
import copy
from pathlib import Path
import tempfile
import unittest

from compute_share import gpu_jobs
from search_coach.belief import PublicObservation
from tests import reference_engine as engine


def job():
    game = engine.Game(base=[2]*64)
    return dict(schema=1, kind='public_history_gpu_coach', job_id='transport-test',
                initial_observation=PublicObservation.from_view(game.views()[0]).serializable(),
                transitions=[], search=dict(seed=17, horizon=2, plans_per_root=1, rollouts_per_plan=2))


class TransportTests(unittest.TestCase):
    def test_hidden_joint_actions_private_fields_and_duplicate_ids_are_rejected(self):
        original = job()
        self.assertEqual(gpu_jobs.validate_public_job(original), [original])
        for bad in (dict(original, opponent_seed=17), dict(original, true_cooldowns=[0]*4),
                    dict(original, transitions=[{'joint_actions': ['STAY']*4, 'observation': original['initial_observation']}])):
            with self.assertRaises(ValueError):
                gpu_jobs.validate_public_job(bad)
        with self.assertRaises(ValueError):
            gpu_jobs.validate_public_job(dict(schema=1, kind='public_history_gpu_coach_batch', jobs=[original, original]))

    def test_worker_integer_limits_are_checked_before_packaging(self):
        for key, value in (('seed', 202611082601), ('seed', True), ('horizon', 0),
                           ('support_cap', 1025), ('rollouts_per_plan', 257), ('unknown', 1)):
            bad = job()
            bad['search'][key] = value
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                gpu_jobs.validate_public_job(bad)

    def test_portable_bundle_pins_all_sources_and_public_data(self):
        cache = gpu_jobs.ROOT/'.cache'
        cache.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=cache) as directory:
            output = Path(directory)/'bundle'
            archive = gpu_jobs.prepare(job(), output)
            self.assertTrue(archive.exists())
            manifest, payload, jobs = gpu_jobs.verify_bundle(output)
            self.assertEqual(payload, job())
            self.assertEqual(len(jobs), 1)
            self.assertEqual(manifest['primary_campaign_games'], 0)
            source = output/'search_coach/gpu_batch.py'
            body = source.read_bytes()
            source.write_bytes(body+b'\n')
            with self.assertRaisesRegex(ValueError, 'hash mismatch'):
                gpu_jobs.verify_bundle(output)


if __name__ == '__main__':
    unittest.main()
