"""Independent checks of the model counterexamples, not strength evidence."""
from fractions import Fraction
import unittest

from evolution.mathematical_probes import anticipatory_shield_counterexample, outcome, terminal_contest_counterexample
from simulator.vendor_harness.referee import Referee


class MathematicalProofTests(unittest.TestCase):
    def test_average_score_margin_can_reverse_the_official_objective(self):
        a, b = outcome([101, 100, 100, 100]), outcome([200, 201, 202, 1])
        self.assertGreater(a["pairwise_wins"], b["pairwise_wins"])
        self.assertLess(a["own_score"], b["own_score"])
        self.assertLess(a["mean_rival_margin"], b["mean_rival_margin"])

    def test_local_surrogate_mix_makes_both_sides_indifferent(self):
        gain, freeze, backfire = map(Fraction, (48, 18, 12))
        denominator = gain+freeze+backfire
        p, q, value = backfire/denominator, gain/denominator, gain*backfire/denominator
        self.assertEqual((1-q)*gain-q*freeze, q*backfire)
        self.assertEqual(p*gain, -p*freeze+(1-p)*backfire)
        self.assertEqual(q*backfire, value)

    def test_identical_marginals_allow_different_backfire_probabilities(self):
        distributions = (
            {(True, True): .6, (False, False): .4},
            {(True, True): .36, (True, False): .24, (False, True): .24, (False, False): .16},
            {(True, True): .2, (True, False): .4, (False, True): .4},
        )
        misses = []
        for distribution in distributions:
            self.assertAlmostEqual(sum(distribution.values()), 1)
            for index in range(2):
                self.assertAlmostEqual(sum(probability for joint, probability in distribution.items() if joint[index]), .6)
            misses.append(distribution.get((False, False), 0))
        self.assertEqual(misses, [.4, .16, 0])

    def test_terminal_contest_rank_effect_matches_the_second_referee(self):
        proof = terminal_contest_counterexample()
        for expected in proof["outcomes"]:
            game = Referee([3]*64, rules={"catch_requires_stay": True}, start_token=1)
            game.turn = 80
            game.pos = [27, 29, 63, 56]
            game.owner[27] = game.owner[28] = 1
            game.upg[27] = 1
            game.owner[29], game.upg[29] = 3, 1
            game.prog[1] = 2
            game.score = [1000, 2000, 1005, 500]
            game.step(expected["joint"])
            self.assertEqual(game.score, expected["scores"])
            self.assertEqual(game.pos, expected["positions"])
            self.assertEqual(game.owner[29], expected["owner_of_cell29"])
        self.assertEqual([item["pairwise_wins"] for item in proof["outcomes"]], [1, 2, 1])

    def test_waiting_to_shield_can_lose_the_future_defense_option(self):
        proof = anticipatory_shield_counterexample()
        self.assertEqual(proof["turn"], 17)
        self.assertEqual(proof["raider_progress"], 1)
        self.assertEqual(proof["observer_enemy_progress"], 1)
        self.assertEqual(proof["incumbent_action"], "STAY")
        for expected in proof["outcomes"]:
            game = Referee(proof["base"], rules={"catch_requires_stay": True}, start_token=proof["initial_token"])
            for joint in proof["prefix"]:
                game.step(joint)
            self.assertEqual(game.pos, proof["positions"])
            game.step(expected["first_joint"])
            self.assertEqual(game.frozen, expected["after_first"]["frozen"])
            self.assertEqual(game.prog, expected["after_first"]["progress"])
            self.assertEqual(game.cd, expected["after_first"]["cooldown"])
            game.step(["STAY"]*4)
            self.assertEqual(game.score, expected["after_second"]["score"])
            self.assertEqual(game.owner[18], expected["after_second"]["owner18"])


if __name__ == "__main__":
    unittest.main()
