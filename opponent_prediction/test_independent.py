"""Independent likelihood/alias/correlation checks; zero study/game credit."""
import copy
import itertools
import math
import unittest
from unittest.mock import patch

from evolution.oversight import referee, state_equal
from opponent_prediction import intent_filter as model
from search_coach.belief import PublicObservation
from tests import reference_engine as engine


def view(game, focal=0):
    return PublicObservation.from_view(game.views()[focal]).serializable()


def uniform_public_policy(observation, hypothesis):
    legal = observation.legal_actions
    return tuple(1/len(legal) if name in legal else 0.0 for name in engine.ACTIONS)


def advance_observed(game, shadow, belief, joint):
    for seat, action in enumerate(joint):
        if action not in game.legal(seat) or action not in shadow.legal(seat):
            raise AssertionError('Test witness requests an illegal action')
    game.step(joint)
    shadow.step(joint)
    state_equal(game, shadow)
    return belief.advance(joint[belief.focal], view(game, belief.focal))


def old_ambiguity_prefix():
    c_actions = ['NORTH']*6 + ['WEST','NORTH','STAY','WEST','STAY','SOUTH']
    result = [['STAY','STAY',action,'STAY'] for action in c_actions]
    result += [['EAST',action,'STAY','STAY']
               for action in ('WEST','SOUTH','NORTH','SOUTH','NORTH')]
    return result


def correlation_prefix():
    """B owns6&13; B7,C6,D13 with zero raid progress after twelve legal turns."""
    a = ['STAY']*12
    b = ['WEST','STAY','SOUTH','WEST','STAY','EAST','EAST','NORTH']+['STAY']*4
    c = ['STAY']*4+['NORTH']*6+['WEST','NORTH']
    d = ['STAY']+['NORTH']*6+['EAST']*5
    return [list(actions) for actions in zip(a,b,c,d)]


def log_snapshot(belief):
    return (belief.observation, belief.transitions, belief.log_evidence,
            {key:tuple(value) for key,value in belief.weights.items()},
            tuple(sorted(belief.states)))


def posterior_mass(belief, predicate):
    return sum(math.exp(weight) for key, game in belief.states.items() if predicate(game)
               for weight in belief.weights[key])


class IndependentIntentTests(unittest.TestCase):
    def test_nested_hidden_objects_or_extra_cell_fields_cannot_enter(self):
        game = engine.Game()
        bad_values = []
        for cell in (game.views()[0].board[0][0],
                     dict(occupant=1,owner=1,is_upgraded=False,is_home=True,
                          is_frozen=False,base_points=1,actual_cooldown=0)):
            raw = view(game)
            raw['board'][0][0] = cell
            bad_values.append(raw)
        raw = view(game)
        raw['legal_actions'] = tuple(raw['legal_actions'])
        bad_values.append(raw)
        for raw in bad_values:
            with self.subTest(type=str(type(raw['board'][0][0]))), self.assertRaises(ValueError):
                model.IntentFilter(raw)

    def test_catch_backfire_and_blocked_move_mass_have_hand_computed_posterior(self):
        def specified_public_policy(observation, hypothesis):
            if observation.positions == (5,6,13,56):
                if observation.bot_id == 2:
                    # NORTH is geometrically illegal; all five legal intentions
                    # have positive probability. WEST is blocked by focal A.
                    return (0.0,.3,.1,.3,.2,.1)
                if observation.bot_id == 3:
                    return (.1,.1,.1,.1,.1,.5)
            return uniform_public_policy(observation,hypothesis)
        game = engine.Game()
        shadow = referee.Referee(game.base,start_token=1)
        belief = model.IntentFilter(view(game))
        with patch.object(model,'policy',specified_public_policy):
            for joint in old_ambiguity_prefix():
                advance_observed(game,shadow,belief,joint)
            self.assertEqual(game.pos,[5,6,13,56])
            self.assertEqual(len(belief.states),1)
            report = advance_observed(game,shadow,belief,['STAY','STAY','SHIELD','STAY'])
        # Public C-shield is required by A's newly frozen status. D must STAY.
        # B's STAY(.2), blocked WEST(.3), and SHIELD backfire(.1) all match.
        self.assertAlmostEqual(math.exp(report['log_predictive_probability']),.5*.25*.6,places=13)
        self.assertEqual(report['compatible_joint_intents'],3)
        self.assertEqual(len(belief.states),2)
        self.assertAlmostEqual(posterior_mass(belief,lambda g:g.cd[1]==4),1/6,places=13)
        self.assertAlmostEqual(posterior_mass(belief,lambda g:g.cd[1]==0),5/6,places=13)
        self.assertNotAlmostEqual(posterior_mass(belief,lambda g:g.cd[1]==4),1/3)
        self.assertTrue(all(g.frozen[:3]==[2,2,0] for g in belief.states.values()))

    def test_joint_shield_outcome_preserves_type_correlations_and_all_aliases(self):
        q = (.1,.3,.6,.85)
        site = (0,7,6,13)
        def specified_public_policy(observation,hypothesis):
            if observation.positions != site or observation.cells[6][1] != 2 or observation.cells[13][1] != 2:
                return uniform_public_policy(observation,hypothesis)
            shield = q[model.HYPOTHESES.index(hypothesis)]
            legal = observation.legal_actions
            return tuple(shield if action=='SHIELD' else (1-shield)/(len(legal)-1) if action in legal else 0.0
                         for action in engine.ACTIONS)
        game = engine.Game()
        shadow = referee.Referee(game.base,start_token=1)
        belief = model.IntentFilter(view(game))
        with patch.object(model,'policy',specified_public_policy):
            for joint in correlation_prefix():
                advance_observed(game,shadow,belief,joint)
            self.assertEqual(game.pos,list(site))
            self.assertEqual((game.owner[6],game.owner[13]),(2,2))
            self.assertEqual(len(belief.states),1)
            self.assertEqual(game.prog[2:], [0,0])
            prior = next(iter(belief.weights.values()))
            self.assertTrue(all(abs(math.exp(weight)-1/64)<1e-12 for weight in prior))
            report = advance_observed(game,shadow,belief,['STAY','SHIELD','STAY','STAY'])
        # B must either Shield and catch at least one non-shielding intruder,
        # or use STAY/blocked WEST while C and D independently backfire.
        # All-three-SHIELD would freeze B too and is incompatible.
        expected=[]
        for b,c,d in belief.types:
            qb,qc,qd=q[b],q[c],q[d]
            b_stay=2*(1-qb)/3  # B STAY or WEST into occupied C6.
            c_stay=(1-qc)/2    # C STAY or EAST into occupied B7.
            d_stay=(1-qd)/5    # D has four empty neighboring cells.
            likelihood=qb*(c_stay*d_stay+c_stay*qd+qc*d_stay)+b_stay*qc*qd
            expected.append(likelihood/64)
        evidence=sum(expected)
        expected=[weight/evidence for weight in expected]
        self.assertAlmostEqual(math.exp(report['log_predictive_probability']),evidence,places=13)
        actual=[sum(math.exp(vector[index]) for vector in belief.weights.values())
                for index in range(64)]
        for got,want in zip(actual,expected):
            self.assertAlmostEqual(got,want,places=13)
        self.assertEqual(len(belief.states),4)
        marginals=[[sum(actual[index] for index,assignment in enumerate(belief.types) if assignment[rival]==hypothesis)
                    for hypothesis in range(4)] for rival in range(3)]
        factorized=[math.prod(marginals[rival][assignment[rival]] for rival in range(3))
                    for assignment in belief.types]
        self.assertGreater(sum(abs(a-b) for a,b in zip(actual,factorized)),.01)
        self.assertTrue(all(g.frozen==[0,0,2,2] for g in belief.states.values()))

    def test_state_and_particle_budget_rejection_preserves_complete_prior(self):
        for options in ({'max_states':1},{'max_particles':64}):
            game = engine.Game()
            shadow = referee.Referee(game.base,start_token=1)
            belief = model.IntentFilter(view(game),**options)
            with patch.object(model,'policy',uniform_public_policy):
                for joint in old_ambiguity_prefix():
                    advance_observed(game,shadow,belief,joint)
                before=log_snapshot(belief)
                states_object, weights_object = belief.states, belief.weights
                game.step(['STAY','STAY','SHIELD','STAY'])
                with self.subTest(options=options), self.assertRaises(model.InferenceBudgetExceeded):
                    belief.advance('STAY',view(game))
            self.assertEqual(log_snapshot(belief),before)
            self.assertIs(belief.states,states_object)
            self.assertIs(belief.weights,weights_object)

    def test_physics_kernel_is_enumerated_once_per_physical_state_not_per_type(self):
        game = engine.Game()
        belief = model.IntentFilter(view(game))
        game.step(['STAY']*4)
        original, calls = engine.Game.step, []
        def counted(game,joint):
            calls.append(tuple(joint))
            return original(game,joint)
        with patch.object(engine.Game,'step',counted):
            report=belief.advance('STAY',view(game))
        self.assertEqual(len(belief.types),64)
        self.assertEqual(len(calls),4**3)
        self.assertEqual(len(calls),report['legal_joint_intents_tested'])
        self.assertEqual(len(set(calls)),len(calls))

    def test_current_own_action_and_next_board_do_not_enter_rival_policy(self):
        start=engine.Game()
        left,right=model.IntentFilter(view(start)),model.IntentFilter(view(start))
        observed=[]
        original=model.policy
        def capture(observation,hypothesis):
            observed.append((observation,hypothesis))
            return original(observation,hypothesis)
        logs=[]
        for action,belief in (('STAY',left),('EAST',right)):
            actual=start.clone()
            actual.step([action,'STAY','STAY','STAY'])
            observed.clear()
            with patch.object(model,'policy',capture):
                belief.advance(action,view(actual))
            logs.append(copy.deepcopy(observed))
        self.assertEqual(logs[0],logs[1])
        self.assertEqual(len(logs[0]),12)
        self.assertTrue(all(item[0].cells==PublicObservation.from_view(start.views()[0]).cells for item in logs[0]))

    def test_declared_policies_normalize_and_assign_only_legal_positive_mass(self):
        game=engine.Game()
        snapshots=[game.clone()]
        for joint in correlation_prefix():
            game.step(joint)
            snapshots.append(game.clone())
        game.step(['STAY','SHIELD','STAY','STAY'])
        snapshots.append(game.clone())
        for hypothetical in snapshots:
            for raw in hypothetical.views():
                observation=PublicObservation.from_view(raw)
                for hypothesis in model.HYPOTHESES:
                    probabilities=model.policy(observation,hypothesis)
                    self.assertAlmostEqual(sum(probabilities),1,places=13)
                    self.assertTrue(all(math.isfinite(p) for p in probabilities))
                    for action,p in zip(engine.ACTIONS,probabilities):
                        self.assertGreater(p,0) if action in observation.legal_actions else self.assertEqual(p,0)


if __name__ == '__main__':
    unittest.main()
