"""Run with a PyTorch environment: python -m unittest search_coach.test_gpu_batch -v."""
import copy
import random
import unittest

import torch

from tests import reference_engine as ref
from .belief import PublicObservation
from .gpu_batch import (PublicPolicyBatch, _public_adapter, _tensor_state, public_policy,
                        scalar_public_policy, run_batch, _pairwise_numerator)
from .test_coach import setup_prefix


def job_from_actions(actions=(), *, job_id="test", focal=0, config=None):
    game = ref.Game()
    job = {"schema": 1, "kind": "public_history_gpu_coach", "job_id": job_id,
           "initial_observation": PublicObservation.from_view(game.views()[focal]).serializable(),
           "transitions": [], "search": config or dict(seed=31, horizon=2, plans_per_root=2,
                                                       rollouts_per_plan=3)}
    for joint in actions:
        game.step(joint)
        job["transitions"].append({"own_action": joint[focal],
                    "observation": PublicObservation.from_view(game.views()[focal]).serializable()})
    return job


class GpuCoachTests(unittest.TestCase):
    def test_tensor_public_policy_matches_independent_scalar_and_is_row_local(self):
        rnd = random.Random(48)
        games = []
        for i in range(24):
            g = ref.Game(base=ref.make_map(seed=i + 10), start_token=i % 4 + 1)
            for _ in range(12):
                g.step([rnd.choice(g.legal(s)) for s in range(4)])
            games.append(g)
        batch = _tensor_state(games, "cpu")
        public = _public_adapter(batch)
        before = public.board.clone()
        keys = torch.arange(len(games) * 4) * 69621
        for step in range(6):
            actual = public_policy(public, keys, step).tolist()
            expected = [scalar_public_policy(PublicObservation.from_view(v), int(keys[i * 4 + seat]), step)
                        for i, g in enumerate(games) for seat, v in enumerate(g.views())]
            self.assertEqual(actual, expected)
        self.assertTrue(torch.equal(before, public.board))
        altered = public.legal_actions.clone()
        altered[1:] = False
        altered[1:, 4] = True
        other = PublicPolicyBatch(public.board, public.bot_id, public.is_priority_token, altered)
        self.assertEqual(int(public_policy(public, keys, 2)[0]), int(public_policy(other, keys, 2)[0]))

    def test_cpu_worker_independently_verifies_every_trajectory_and_preserves_job(self):
        job = job_from_actions()
        original = copy.deepcopy(job)
        result = run_batch([job], device="cpu", max_trajectories=5)
        self.assertEqual(job, original)
        self.assertTrue(result["independent_cpu_verified"])
        self.assertEqual(result["independent_cpu_turn_checks"], result["synthetic_game_turns"])
        self.assertEqual(result["primary_campaign_games"], 0)
        self.assertFalse(result["full_bmcts"])
        self.assertGreater(result["chunks"], 1)
        for root in result["jobs"][0]["root_estimates"]:
            self.assertEqual(root["best_common_plan"]["value_denominator"], 6)

    def test_pairwise_objective_prefers_three_wins_over_one_with_larger_margin(self):
        scores = torch.tensor([[101, 100, 100, 100], [200, 201, 202, 1]])
        self.assertEqual(_pairwise_numerator(scores, torch.tensor([0, 0])).tolist(), [6, 2])

    def test_terminal_utility_has_zero_income_tail_and_legal_roots(self):
        prefix = [["STAY"] * 4 for _ in range(79)]
        zero = job_from_actions(prefix, config=dict(horizon=3, income_tail=0, rollouts_per_plan=2))
        large = copy.deepcopy(zero)
        large["search"]["income_tail"] = 80
        a = run_batch([zero])["jobs"][0]
        b = run_batch([large])["jobs"][0]
        self.assertEqual(a["effective_horizon"], 1)
        self.assertEqual(a["root_estimates"], b["root_estimates"])
        legal = zero["transitions"][-1]["observation"]["legal_actions"]
        self.assertIn(a["recommended_action"], legal)

    def test_chunk_size_does_not_change_values(self):
        job = job_from_actions()
        a = run_batch([job], max_trajectories=1)
        b = run_batch([job], max_trajectories=8192)
        self.assertEqual(a["jobs"], b["jobs"])

    def test_unknown_hidden_job_fields_and_duplicate_ids_rejected(self):
        job = job_from_actions()
        job["actual_opponent_seed"] = 0
        with self.assertRaises(ValueError):
            run_batch([job])
        with self.assertRaisesRegex(ValueError, "duplicate"):
            run_batch([job_from_actions(), job_from_actions()])

    def test_identical_public_prefix_with_different_actual_cooldown_has_same_values(self):
        prefix = setup_prefix()
        a = prefix + [["STAY", "STAY", "SHIELD", "STAY"]] + [["STAY"] * 4] * 2
        b = prefix + [["STAY", "SHIELD", "SHIELD", "STAY"]] + [["STAY"] * 4] * 2
        job_a = job_from_actions(a, job_id="a")
        job_b = job_from_actions(b, job_id="b")
        self.assertEqual(job_a["transitions"], job_b["transitions"])
        result = run_batch([job_a, job_b])
        self.assertEqual(result["jobs"][0]["root_estimates"], result["jobs"][1]["root_estimates"])
        self.assertEqual(result["jobs"][0]["belief"], result["jobs"][1]["belief"])

    @unittest.skipUnless(torch.cuda.is_available(), "CUDA is unavailable")
    def test_actual_cuda_and_cpu_values_and_actions_match_exactly(self):
        jobs = [job_from_actions(job_id="opening"),
                job_from_actions(setup_prefix(), job_id="shield_position")]
        cpu = run_batch(jobs, device="cpu", max_trajectories=31)
        cuda = run_batch(jobs, device="cuda", max_trajectories=31)
        self.assertEqual(cpu["jobs"], cuda["jobs"])
        self.assertEqual(cpu["trace_sha256"], cuda["trace_sha256"])
        self.assertEqual(cpu["independent_cpu_turn_checks"], cuda["independent_cpu_turn_checks"])


if __name__ == "__main__":
    unittest.main()
