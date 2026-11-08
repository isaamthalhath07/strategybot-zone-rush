"""Information-boundary and canonical-rule tests for the offline diagnostic."""
import copy
import unittest

from tests import reference_engine as ref
from .belief import PublicBelief, PublicObservation, InconsistentObservation, state_key
from .beam import recommend


def setup_prefix():
    """Reach A on C's cell5, B on C's cell6 and C at13, from the real opening."""
    c_actions = ["NORTH"] * 6 + ["WEST", "NORTH", "STAY", "WEST", "STAY", "SOUTH"]
    prefix = [["STAY", "STAY", action, "STAY"] for action in c_actions]
    for b_action in ("WEST", "SOUTH", "NORTH", "SOUTH", "NORTH"):
        prefix.append(["EAST", b_action, "STAY", "STAY"])
    return prefix


def replay_prefix(focal, actions, *, token=1, cap=512):
    game = ref.Game(start_token=token)
    belief = PublicBelief(game.views()[focal], cap=cap)
    for joint in actions:
        game.step(joint)
        belief.advance(joint[focal], game.views()[focal])
        if belief.exact_support:
            assert state_key(game) in {state_key(g) for g in belief._states}
    return game, belief


class PublicCoachTests(unittest.TestCase):
    def test_initial_priority_uncertainty_and_eventual_resolution(self):
        game = ref.Game(start_token=3)
        belief = PublicBelief(game.views()[0])
        self.assertEqual(belief.summary()["possible_tokens"], [2, 3, 4])
        for _ in range(4):
            game.step(["STAY"] * 4)
            belief.advance("STAY", game.views()[0])
        self.assertEqual(belief.summary()["possible_tokens"], [3])
        self.assertIn(state_key(game), [state_key(g) for g in belief._states])

    def test_cold_start_and_hidden_dictionary_fields_rejected(self):
        game = ref.Game()
        raw = PublicObservation.from_view(game.views()[0]).serializable()
        raw["private_cooldowns"] = [0] * 4
        with self.assertRaisesRegex(ValueError, "exactly the four"):
            PublicBelief(raw)
        game.step(["EAST", "STAY", "STAY", "STAY"])
        with self.assertRaises(InconsistentObservation):
            PublicBelief(game.views()[0])

    def test_successful_owned_to_owned_move_escapes(self):
        prefix = setup_prefix()[:12]
        prefix += [["STAY", "WEST", "STAY", "STAY"],
                   ["STAY", "WEST", "SHIELD", "STAY"]]
        game, belief = replay_prefix(1, prefix)
        self.assertEqual(game.pos[1], 5)
        self.assertEqual(game.frozen, [0, 0, 2, 0])
        self.assertEqual(belief.summary()["cooldown_domains"][2], [4])

    def test_blocked_move_is_stay_and_freezes(self):
        prefix = setup_prefix() + [["STAY", "WEST", "SHIELD", "STAY"]]
        game, belief = replay_prefix(1, prefix)
        self.assertEqual(game.pos[:2], [5, 6])
        self.assertEqual(game.frozen[:3], [2, 2, 0])
        self.assertIn(state_key(game), [state_key(g) for g in belief._states])

    def test_catch_backfire_ambiguity_preserves_cooldowns_and_invariance(self):
        # B can shield on C's land while C catches A. Public B-freeze can be
        # either C's catch or B's backfire, and B's private cooldown differs.
        prefix = setup_prefix()
        game_a, belief_a = replay_prefix(0, prefix)
        game_b, belief_b = replay_prefix(0, prefix)
        action_a = ["STAY", "STAY", "SHIELD", "STAY"]
        action_b = ["STAY", "SHIELD", "SHIELD", "STAY"]
        game_a.step(action_a)
        game_b.step(action_b)
        view_a = game_a.views()[0]
        view_b = game_b.views()[0]
        self.assertEqual(PublicObservation.from_view(view_a), PublicObservation.from_view(view_b))
        self.assertEqual(game_a.frozen[:2], [2, 2])
        self.assertNotEqual(game_a.cd[1], game_b.cd[1])
        belief_a.advance("STAY", view_a)
        belief_b.advance("STAY", view_b)
        self.assertEqual(belief_a.summary()["cooldown_domains"][1], [0, 4])
        self.assertEqual(belief_a.summary(), belief_b.summary())
        for _ in range(2):
            game_a.step(["STAY"] * 4)
            game_b.step(["STAY"] * 4)
            belief_a.advance("STAY", game_a.views()[0])
            belief_b.advance("STAY", game_b.views()[0])
        self.assertGreater(len(belief_a.observation.legal_actions), 1)
        report_a = recommend(belief_a, horizon=2, beam_width=2, rollouts=4, seed=91)
        report_b = recommend(belief_b, horizon=2, beam_width=2, rollouts=4, seed=91)
        self.assertEqual(report_a, report_b)
        self.assertFalse(report_a["used_per_particle_focal_optimization"])

    def test_two_shielders_on_each_others_land_both_backfire(self):
        prefix = setup_prefix() + [
            ["WEST", "SOUTH", "STAY", "STAY"],
            ["STAY", "STAY", "STAY", "STAY"],
            ["STAY", "NORTH", "EAST", "STAY"],
            ["STAY", "SHIELD", "SHIELD", "STAY"],
        ]
        game, belief = replay_prefix(1, prefix)
        self.assertEqual(game.frozen, [0, 2, 2, 0])
        self.assertEqual(belief.summary()["cooldown_domains"][1:3], [[4], [4]])

    def test_capped_support_is_reported_and_cannot_silently_invent_a_repair(self):
        game = ref.Game(start_token=3)
        belief = PublicBelief(game.views()[1], cap=1)
        self.assertFalse(belief.exact_support)
        self.assertEqual(belief.dropped_states, 2)
        before = copy.deepcopy(belief.summary())
        game.step(["STAY"] * 4)
        with self.assertRaisesRegex(InconsistentObservation, "capped approximation"):
            belief.advance("STAY", game.views()[1])
        self.assertEqual(before, belief.summary())

    def test_diagnostic_is_deterministic_and_does_not_mutate_public_history(self):
        game, belief = replay_prefix(0, [["EAST", "WEST", "NORTH", "NORTH"]])
        before = (belief.summary(), [state_key(g) for g in belief._states])
        a = recommend(belief, horizon=2, beam_width=2, rollouts=3, seed=41,
                      incumbent_action="STAY")
        b = recommend(belief, horizon=2, beam_width=2, rollouts=3, seed=41,
                      incumbent_action="STAY")
        self.assertEqual(a, b)
        self.assertEqual(before, (belief.summary(), [state_key(g) for g in belief._states]))
        self.assertIn(a["recommended_action"], game.legal(0))
        self.assertFalse(a["certifies_optimality"])
        self.assertFalse(a["full_bmcts"])


if __name__ == "__main__":
    unittest.main()
