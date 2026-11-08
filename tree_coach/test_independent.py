"""Independent observer checks; private state never enters a coach input."""
from collections import defaultdict
import random
import unittest
from unittest.mock import patch

from evolution.oversight import referee, state_equal
from search_coach.belief import PublicObservation
from tests import reference_engine as engine
from tree_coach import mcts


def terminal_job():
    """A legal public prefix whose final action changes pairwise rank."""
    game = engine.Game()
    shadow = referee.Referee(game.base, start_token=1)
    focal, rng = 2, random.Random(5)
    initial = PublicObservation.from_view(game.views()[focal]).serializable()
    transitions = []
    for _ in range(79):
        joint = []
        for seat in range(4):
            choices = [action for action in game.legal(seat) if action != 'SHIELD'] + ['STAY']*3
            joint.append(rng.choice(choices))
        game.step(joint)
        shadow.step(joint)
        state_equal(game, shadow)
        transitions.append(dict(own_action=joint[focal],
                                observation=PublicObservation.from_view(game.views()[focal]).serializable()))
    return dict(schema=1, kind='public_history_tree_coach', job_id='independent-terminal-rank',
                initial_observation=initial, transitions=transitions,
                search=dict(seed=53, horizon=12, simulations=64, beam_width=6, income_tail=80))


class IndependentTreeTests(unittest.TestCase):
    def test_asymmetric_opening_is_rejected_even_when_other_fields_are_valid(self):
        actual = engine.Game()
        public = PublicObservation.from_view(actual.views()[0]).serializable()
        public['board'][0][1][5] = 3
        raw = dict(schema=1, kind='public_history_tree_coach', job_id='asymmetric-map',
                   initial_observation=public, transitions=[], search=dict(simulations=16))
        with self.assertRaisesRegex(ValueError, 'four-way mirror symmetry'):
            mcts.recommend(raw)

    def test_final_return_backups_match_observed_dual_referee_outcomes(self):
        job = terminal_job()
        totals, visits, outcomes = defaultdict(int), defaultdict(int), set()
        original_step, physical_step = mcts.step, engine.Game.step

        def observe(game, focal, action, *args):
            # Only this test observer sees a sampled hypothetical state.
            other = referee.Referee(game.base, rules=game.rules, start_token=game.token,
                                     max_turns=game.max_turns)
            for name in ('owner', 'upg', 'home', 'pos', 'frozen', 'cd', 'prog', 'score'):
                setattr(other, name, list(getattr(game, name)))
            other.turn = game.turn
            state_equal(game, other)
            joint = []

            def capture(target, actions):
                self.assertIs(target, game)
                joint.extend(actions)
                return physical_step(target, actions)

            with patch.object(engine.Game, 'step', capture):
                original_step(game, focal, action, *args)
            self.assertEqual(len(joint), 4)
            other.step(joint)
            state_equal(game, other)
            self.assertTrue(game.over() and other.over())
            own = other.score[focal]
            result = sum((2 if own > score else 1 if own == score else 0)
                         for seat, score in enumerate(other.score) if seat != focal)
            visits[action] += 1
            totals[action] += result
            outcomes.add(result)

        with patch.object(mcts, 'step', observe):
            report = mcts.recommend(job)
        self.assertEqual(report['effective_horizon'], 1)
        self.assertEqual(report['terminal_evaluations'], 64)
        self.assertEqual(report['heuristic_cutoffs'], 0)
        self.assertGreater(len(outcomes), 1)  # This is not an all-actions-tie check.
        for row in report['root_estimates']:
            action = row['action']
            self.assertEqual(row['visits'], visits[action])
            self.assertEqual(row['value_numerator_sum'], totals[action])
            self.assertEqual(row['mean_pairwise_points'], totals[action]/(2*visits[action]))
        self.assertEqual(sum(visits.values()), 64)

    def test_unknown_initial_token_is_not_supplied_by_the_actual_game(self):
        reports = []
        public_inputs = []
        for true_holder in (2, 4):
            actual = engine.Game(start_token=true_holder)
            public = PublicObservation.from_view(actual.views()[0]).serializable()
            raw = dict(schema=1, kind='public_history_tree_coach', job_id='independent-token',
                       initial_observation=public, transitions=[],
                       search=dict(seed=14, horizon=3, simulations=48))
            public_inputs.append(raw)
            reports.append(mcts.recommend(raw))
        self.assertEqual(public_inputs[0], public_inputs[1])
        self.assertEqual(reports[0], reports[1])
        self.assertFalse(reports[0]['private_state_node_keys'])


if __name__ == '__main__':
    unittest.main()
