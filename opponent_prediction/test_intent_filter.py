import copy
import itertools
import math
import unittest
from unittest.mock import patch

from evolution.oversight import referee, state_equal
from opponent_prediction import intent_filter as model
from search_coach.belief import PublicObservation
from tests import reference_engine as engine


def public(game, focal=0):
    return PublicObservation.from_view(game.views()[focal]).serializable()


def advance_world(game, shadow, joint):
    for seat,action in enumerate(joint):
        if action not in game.legal(seat):
            raise AssertionError('Illegal test script')
    game.step(joint)
    shadow.step(joint)
    state_equal(game,shadow)


class IntentFilterTests(unittest.TestCase):
    def test_actual_hidden_holder_does_not_enter_input_or_prediction(self):
        a, b = engine.Game(start_token=2), engine.Game(start_token=4)
        self.assertEqual(public(a),public(b))
        left, right = model.IntentFilter(public(a)),model.IntentFilter(public(b))
        self.assertEqual(left.action_marginals(),right.action_marginals())
        self.assertEqual(len(left.states),3)
        self.assertEqual(sum(len(v) for v in left.weights.values()),192)

    def test_private_fields_objects_and_asymmetric_maps_are_rejected(self):
        game = engine.Game()
        with self.assertRaisesRegex(ValueError,'serialized'):
            model.IntentFilter(game)
        raw = public(game)
        raw['opponent_seed'] = 3
        with self.assertRaises(ValueError):
            model.IntentFilter(raw)
        raw = public(game)
        raw['board'][0][1][5] = 3
        with self.assertRaisesRegex(ValueError,'mirrored'):
            model.IntentFilter(raw)

    def test_persistent_type_posterior_matches_independent_one_turn_bayes(self):
        game = engine.Game()
        shadow = referee.Referee(game.base,start_token=1)
        start = public(game)
        views = [PublicObservation.from_view(v) for v in game.views()]
        probabilities = [[model.policy(views[seat],h)[4] for h in model.HYPOTHESES]
                         for seat in (1,2,3)]
        belief = model.IntentFilter(start)
        advance_world(game,shadow,['STAY']*4)
        report = belief.advance('STAY',public(game))
        expected = math.prod(sum(p)/4 for p in probabilities)
        self.assertAlmostEqual(math.exp(report['log_predictive_probability']),expected,places=13)
        self.assertEqual(report['compatible_joint_intents'],1)
        for rival, values in enumerate(probabilities,2):
            marginal = belief.type_marginals()[str(rival)]
            for h,p in zip(model.HYPOTHESES,values):
                self.assertAlmostEqual(marginal[h],p/sum(values),places=13)

    def test_blocked_west_mass_is_added_to_stay_instead_of_lost(self):
        game = engine.Game()
        shadow = referee.Referee(game.base,start_token=1)
        belief = model.IntentFilter(public(game),mode='uniform')
        for _ in range(3):
            advance_world(game,shadow,['EAST','WEST','STAY','STAY'])
            belief.advance('EAST',public(game))
        self.assertEqual(game.pos[:2],[3,4])
        advance_world(game,shadow,['STAY','WEST','STAY','STAY'])
        report = belief.advance('STAY',public(game))
        self.assertEqual(game.pos[:2],[3,4])
        self.assertEqual(report['compatible_alias_intents'],1)
        self.assertEqual(report['compatible_joint_intents'],2)
        self.assertAlmostEqual(math.exp(report['log_predictive_probability']),2/5/4/4,places=14)
        self.assertNotAlmostEqual(math.exp(report['log_predictive_probability']),1/5/4/4)

    def test_all_possible_first_public_outcomes_sum_to_one(self):
        opening = engine.Game()
        outcomes = {}
        # The focal owns the opening token, so there is one inferred holder.
        for rival_actions in itertools.product(*[opening.legal(s) for s in (1,2,3)]):
            game = opening.clone()
            game.step(['STAY',*rival_actions])
            view = PublicObservation.from_view(game.views()[0])
            outcomes[view] = view.serializable()
        for mode in model.MODES:
            probability = 0.0
            for view in outcomes.values():
                belief = model.IntentFilter(public(opening),mode=mode)
                probability += math.exp(belief.advance('STAY',view)['log_predictive_probability'])
            self.assertAlmostEqual(probability,1.0,places=12, msg=mode)

    def test_impossible_observation_and_budget_failure_are_transactional(self):
        game = engine.Game()
        belief = model.IntentFilter(public(game),max_joint_intents=1)
        before = copy.deepcopy((belief.states,belief.weights,belief.observation,belief.transitions,belief.log_evidence))
        game.step(['STAY']*4)
        with self.assertRaises(model.InferenceBudgetExceeded):
            belief.advance('STAY',public(game))
        self.assertEqual(before[1:],(belief.weights,belief.observation,belief.transitions,belief.log_evidence))
        self.assertEqual(set(before[0]),set(belief.states))
        belief = model.IntentFilter(public(engine.Game()))
        raw = public(engine.Game())
        raw['board'][0][0][2] = True  # An upgrade cannot finish on the first turn.
        with self.assertRaisesRegex(ValueError,'no positive'):
            belief.advance('STAY',raw)
        self.assertEqual(belief.transitions,0)
        self.assertEqual(belief.log_evidence,0)

    def test_policy_receives_public_views_not_own_intervention_or_private_state(self):
        game = engine.Game()
        belief = model.IntentFilter(public(game))
        original = model.policy
        supplied = []
        def observe(view,hypothesis):
            self.assertIsInstance(view,PublicObservation)
            supplied.append((view,hypothesis))
            return original(view,hypothesis)
        game.step(['EAST','STAY','STAY','STAY'])
        with patch.object(model,'policy',observe):
            belief.advance('EAST',public(game))
        self.assertEqual(len(supplied),12)
        self.assertTrue(all(view.bot_id != 1 for view,_ in supplied))

    def test_rare_explanations_remain_in_log_space_after_update(self):
        game = engine.Game()
        belief = model.IntentFilter(public(game))
        vector = next(iter(belief.weights.values()))
        vector[0] = -2000.0
        normalizer = model.logsum(vector)
        vector[:] = [p-normalizer for p in vector]
        game.step(['STAY']*4)
        belief.advance('STAY',public(game))
        self.assertTrue(all(math.isfinite(p) for vector in belief.weights.values() for p in vector))
        self.assertLess(next(iter(belief.weights.values()))[0],-1900)
        self.assertAlmostEqual(model.logsum(p for row in belief.weights.values() for p in row),0,places=12)


if __name__ == '__main__':
    unittest.main()
