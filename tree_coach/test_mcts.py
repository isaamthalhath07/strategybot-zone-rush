"""Adversarial information-boundary tests; no primary games are credited."""
import copy
import unittest
from unittest.mock import patch

from search_coach.belief import PublicObservation
from tests import reference_engine as ref
from tree_coach import mcts


def job(actions=(), *, focal=0, token=1, **search):
    game = ref.Game(start_token=token)
    initial = PublicObservation.from_view(game.views()[focal]).serializable()
    transitions = []
    for joint in actions:
        game.step(joint)
        transitions.append(dict(own_action=joint[focal],
                                observation=PublicObservation.from_view(game.views()[focal]).serializable()))
    return game, dict(schema=1, kind="public_history_tree_coach", job_id="tree-test",
                      initial_observation=initial, transitions=transitions,
                      search=dict(simulations=32, horizon=4, **search))


def ambiguous_prefix():
    c_actions = ["NORTH"] * 6 + ["WEST", "NORTH", "STAY", "WEST", "STAY", "SOUTH"]
    result = [["STAY", "STAY", action, "STAY"] for action in c_actions]
    result += [["EAST", action, "STAY", "STAY"]
               for action in ("WEST", "SOUTH", "NORTH", "SOUTH", "NORTH")]
    return result


class TreeCoachTests(unittest.TestCase):
    def test_hidden_distinct_actual_games_with_identical_public_histories_are_invariant(self):
        prefix = ambiguous_prefix()
        left = prefix + [["STAY", "STAY", "SHIELD", "STAY"]] + [["STAY"] * 4] * 2
        right = prefix + [["STAY", "SHIELD", "SHIELD", "STAY"]] + [["STAY"] * 4] * 2
        game_a, job_a = job(left, seed=91, beam_width=2)
        game_b, job_b = job(right, seed=91, beam_width=2)
        self.assertNotEqual(game_a.cd[1], game_b.cd[1])
        self.assertEqual(job_a, job_b)
        a, b = mcts.recommend(job_a), mcts.recommend(job_b)
        self.assertEqual(a, b)
        self.assertEqual(a["belief"]["cooldown_domains"][1], [0, 2])
        self.assertFalse(a["private_state_node_keys"])
        self.assertFalse(a["per_particle_focal_optimization"])

    def test_tree_revisits_public_histories_and_branches_on_observed_outcomes(self):
        _, raw = job(seed=42)
        raw["search"]["simulations"] = 128
        report = mcts.recommend(raw)
        self.assertGreater(report["observation_branching_edges"], 0)
        self.assertGreater(report["tree_action_decisions"], report["simulations"])
        self.assertTrue(any(row["depth"] > 0 and row["visits"] > 0 for row in report["nodes"]))
        patterns = {tuple(row["legal_actions"]) for row in report["nodes"] if row["visits"]}
        self.assertGreater(len(patterns), 1)
        self.assertTrue(report["information_set_tree"])

    def test_every_legal_action_receives_samples_before_beam_pruning(self):
        game = ref.Game()
        view = PublicObservation.from_view(game.views()[0])
        node = mcts.Node("public-history", view, 0)
        selected = []
        for _ in range(len(view.legal_actions) * mcts.MIN_ACTION_VISITS):
            action = mcts.choose_action(node, 1)
            selected.append(action)
            node.actions[action].visits += 1
            node.actions[action].total += 6 if action == "EAST" else 0
            node.visits += 1
        self.assertEqual(set(selected), set(view.legal_actions))
        self.assertTrue(all(item.visits == mcts.MIN_ACTION_VISITS for item in node.actions.values()))
        self.assertEqual(node.pruning_events, 0)
        self.assertEqual(mcts.choose_action(node, 1), "EAST")
        self.assertEqual(node.pruned, set(view.legal_actions) - {"EAST"})

    def test_dynamic_pruning_can_readmit_an_action_when_means_change(self):
        node = mcts.Node("public-history", PublicObservation.from_view(ref.Game().views()[0]), 0)
        for item in node.actions.values():
            item.visits = 2
        node.actions["EAST"].total = 12
        node.actions["SOUTH"].total = 10
        node.visits = sum(item.visits for item in node.actions.values())
        self.assertEqual(mcts.choose_action(node, 1), "EAST")
        self.assertIn("SOUTH", node.pruned)
        # Low subsequent returns on the retained action lower its average.
        node.actions["EAST"].visits = 4
        node.visits += 2
        self.assertEqual(mcts.choose_action(node, 1), "SOUTH")

    def test_root_choice_uses_empirical_mean_even_for_a_sparsely_sampled_arm(self):
        node = mcts.Node("public-history", PublicObservation.from_view(ref.Game().views()[0]), 0)
        for item in node.actions.values():
            item.visits, item.total = 2, 0
        node.actions["EAST"].visits, node.actions["EAST"].total = 100, 400
        node.actions["SOUTH"].visits, node.actions["SOUTH"].total = 2, 10
        self.assertEqual(mcts.choose_root_recommendation(node), "SOUTH")
        # There is deliberately no claim that two lucky outcomes certify it.
        self.assertEqual(node.actions["SOUTH"].mean, 5)

    def test_simultaneous_rivals_cannot_observe_the_focal_current_action(self):
        original = ref.Game()
        public = [PublicObservation.from_view(view) for view in original.views()]
        snapshots, seen_views = [], []
        original_step = ref.Game.step
        original_policy = mcts.rival_action
        def capture_step(game, actions):
            snapshots.append(tuple(actions))
            return original_step(game, actions)
        def public_only_policy(view, family, rng):
            self.assertIsInstance(view, PublicObservation)
            self.assertEqual(view.cells, public[0].cells)
            self.assertFalse(hasattr(view, "cd"))
            self.assertFalse(hasattr(view, "score"))
            seen_views.append(view.bot_id)
            return original_policy(view, family, rng)
        with patch.object(ref.Game, "step", capture_step), patch.object(mcts, "rival_action", public_only_policy):
            for action in ("EAST", "STAY"):
                mcts.step(original.clone(), 0, action, "same-public-prefix", 43, 7, 0, public)
        self.assertEqual(seen_views, [2, 3, 4, 2, 3, 4])
        self.assertEqual(snapshots[0][1:], snapshots[1][1:])
        self.assertEqual((snapshots[0][0], snapshots[1][0]), ("EAST", "STAY"))

    def test_all_counterfactual_transitions_match_the_separate_referee(self):
        from evolution.oversight import referee, state_equal
        _, raw = job(focal=1, token=3, seed=67)
        original_step, audited = ref.Game.step, []
        def checked_step(game, actions):
            independent = referee.Referee(game.base, start_token=game.token,
                                           rules={"catch_requires_stay": True})
            for name in ("owner", "upg", "home", "pos", "frozen", "cd", "prog", "score"):
                setattr(independent, name, list(getattr(game, name)))
            independent.turn = game.turn
            state_equal(game, independent)
            for seat, action in enumerate(actions):
                self.assertIn(action, game.legal(seat))
                self.assertIn(action, independent.legal(seat))
            outcome = original_step(game, actions)
            independent.step(actions)
            state_equal(game, independent)
            audited.append(1)
            return outcome
        # Referee truth is consumed only by this test wrapper, after policies
        # choose public actions. It is never passed into a tree decision.
        with patch.object(ref.Game, "step", checked_step):
            report = mcts.recommend(raw)
        self.assertEqual(len(audited), report["synthetic_turns"])
        self.assertEqual(len(audited), 128)

    def test_exact_terminal_pairwise_objective_differs_from_score_margin(self):
        a, b = [101, 100, 100, 100], [200, 201, 202, 1]
        self.assertGreater(b[0] - sum(b[1:]) / 3, a[0] - sum(a[1:]) / 3)
        self.assertEqual(mcts.pairwise_numerator(a, 0), 6)
        self.assertEqual(mcts.pairwise_numerator(b, 0), 2)
        self.assertEqual(mcts.pairwise_numerator([100] * 4, 0), 3)
        game = ref.Game()
        game.turn, game.score = 81, b
        self.assertEqual(mcts.value(game, 0, 80), (2, True))

    def test_real_terminal_prefix_clips_horizon_and_counts_exact_evaluations(self):
        _, raw = job([["STAY"] * 4] * 79, seed=5)
        raw["search"]["horizon"] = 6
        report = mcts.recommend(raw)
        self.assertEqual(report["effective_horizon"], 1)
        self.assertEqual(report["synthetic_turns"], report["simulations"])
        self.assertEqual(report["terminal_evaluations"], report["simulations"])
        self.assertEqual(report["heuristic_cutoffs"], 0)
        self.assertTrue(all(row["mean_pairwise_points"] == 1.5 for row in report["root_estimates"]))

    def test_support_and_tree_caps_are_explicit_and_grant_no_game_credit(self):
        _, raw = job(focal=1, token=3, support_cap=1, max_nodes=1, beam_width=1)
        report = mcts.recommend(raw)
        self.assertFalse(report["belief"]["exact_support"])
        self.assertEqual(report["belief"]["dropped_states"], 2)
        self.assertEqual(report["tree_nodes"], 1)
        self.assertGreater(report["node_cap_events"], 0)
        self.assertEqual(report["primary_campaign_games"], 0)
        self.assertEqual(report["completed_per_game_bmcts_audits"], 0)
        self.assertFalse(report["certifies_optimality"])
        self.assertFalse(report["deployed_policy_changed"])

    def test_input_immutability_determinism_and_legality(self):
        game, raw = job([["EAST", "WEST", "NORTH", "NORTH"]], seed=17)
        before = copy.deepcopy(raw)
        a, b = mcts.recommend(raw), mcts.recommend(raw)
        self.assertEqual(raw, before)
        self.assertEqual(a, b)
        self.assertEqual(len(a["trace_sha256"]), 64)
        self.assertIn(a["recommended_action"], game.legal(0))
        for row in a["root_estimates"]:
            self.assertGreaterEqual(row["visits"], mcts.MIN_ACTION_VISITS)
        self.assertEqual(sum(row["visits"] for row in a["root_estimates"]), a["simulations"])

    def test_hidden_objects_private_fields_and_invalid_budgets_are_rejected(self):
        _, raw = job()
        alterations = [dict(raw, actual_referee=ref.Game()), dict(raw, opponent_seed=17),
                       dict(raw, initial_observation=ref.Game()),
                       dict(raw, transitions=[dict(joint_actions=["STAY"] * 4, observation=raw["initial_observation"])])]
        private_view = copy.deepcopy(raw)
        private_view["initial_observation"]["private_cooldowns"] = [0] * 4
        alterations.append(private_view)
        for cell in (ref.Game().views()[0].board[0][0],
                     dict(occupant=1, owner=1, is_upgraded=False, is_home=True,
                          is_frozen=False, base_points=1, private_cooldown=0)):
            private_cell = copy.deepcopy(raw)
            private_cell["initial_observation"]["board"][0][0] = cell
            alterations.append(private_cell)
        for search in ({"horizon": True}, {"seed": 1.0}, {"simulations": 1},
                       {"opponent_model_seed": 17}, {"support_cap": 0}, {"max_nodes": 8193}):
            alterations.append(dict(raw, search=search))
        for value in alterations:
            with self.subTest(keys=list(value)), self.assertRaises(ValueError):
                mcts.recommend(value)


if __name__ == "__main__":
    unittest.main()
