"""Independent scripted goal-memory tests; zero strength/qualification credit."""
import copy
import math
import unittest

from deadline_strategy.goal_space import PersistentGoalTemplateSpace,TEMPLATE_SHA256,sha
from deadline_strategy.test_independent import public
from evolution.oversight import signature
from strategy_candidates.test_public_memory import path
from tests import reference_engine as engine


def load(body):
    namespace={'__name__':'_independent_synthetic_goal'}
    exec(compile(body,'<independent-synthetic-goal>','exec'),namespace)
    return namespace


class IndependentGoalTests(unittest.TestCase):
    def test_exact_structure_and_fixed_unsearched_transition_constants(self):
        space=PersistentGoalTemplateSpace();body=space.export(space.defaults)
        self.assertEqual(sha(body),TEMPLATE_SHA256)
        self.assertEqual(len(space.bounds),12)
        self.assertEqual(body.count(b'        self._update_goal_mass()\n'),1)
        for changed in (body.replace(b'0.8 * prior[g] + 0.2 * q[g]',b'0.9 * prior[g] + 0.1 * q[g]'),
                body.replace(b'4.0 **',b'3.0 **'),body.replace(b'        self._update_goal_mass()\n',b''),
                body.replace(b'seed=seat * 7919',b'seed=seat * 7920')):
            with self.assertRaises(ValueError): space.inspect_export(changed)
        genes=space.mutate(space.defaults,590)
        self.assertEqual(space.inspect_export(space.export(genes)),genes)

    def test_mutated_goal_state_uses_only_identical_public_prefixes_in_fresh_namespaces(self):
        space=PersistentGoalTemplateSpace();body=space.export(space.mutate(space.defaults,591))
        worlds=[]
        for script in (path(own_final='WEST'),path(own_final='WEST',defender_final='SHIELD',raider_final='STAY')):
            namespace=load(body);tracker=namespace['BlockerBot'](seed=7919);game=engine.Game()
            prefix=[]
            for joint in script:
                view=public(game,0);before=signature(view);tracker._observe(view)
                tracker.last=joint[0];prefix.append((before,joint[0]))
                self.assertEqual(signature(view),before)
                self.assertEqual(tracker.prog,game.prog[0])
                self.assertTrue(all(action in game.legal(seat) for seat,action in enumerate(joint)))
                game.step(joint)
            tracker._observe(public(game,0));prefix.append(signature(public(game,0)))
            for values in tracker._persistent_goal_mass.values():
                self.assertIs(type(values),tuple)
                self.assertEqual(len(values),64)
                self.assertTrue(all(math.isfinite(v) and v>=0 for v in values))
                self.assertAlmostEqual(sum(values),1.,places=13)
            worlds.append((game,tracker,prefix))
        left,right=worlds[0][1],worlds[1][1]
        self.assertEqual(worlds[0][2],worlds[1][2])
        self.assertNotEqual(worlds[0][0].cd,worlds[1][0].cd)
        self.assertEqual(left._persistent_goal_mass,right._persistent_goal_mass)
        self.assertEqual(left.rng.getstate(),right.rng.getstate())
        self.assertEqual(left._decide(public(worlds[0][0],0)),right._decide(public(worlds[1][0],0)))
        saved=copy.deepcopy(right._persistent_goal_mass)
        left._persistent_goal_mass[2]=tuple([1.]+[0.]*63)
        self.assertEqual(right._persistent_goal_mass,saved)

    def test_observation_updates_once_including_frozen_returns_and_forecast_is_read_only(self):
        space=PersistentGoalTemplateSpace();namespace=load(space.export(space.defaults))
        tracker=namespace['BlockerBot'](seed=7919);game=engine.Game();calls=[]
        original=tracker._update_goal_mass
        def observed(): calls.append(tracker.t);return original()
        tracker._update_goal_mass=observed
        tracker.act(public(game,0))
        # These accepted scripted actions isolate observation mechanics; the
        # intervened own planner state is not labelled unchanged-policy play.
        for joint in (['SHIELD','WEST','STAY','STAY'],['STAY','WEST','STAY','STAY'],['STAY']*4):
            tracker.last=joint[0];game.step(joint);proposal=tracker.act(public(game,0))
            self.assertIn(proposal,game.legal(0))
            if game.frozen[0]: self.assertEqual(proposal,'STAY')
            before=copy.deepcopy(tracker._persistent_goal_mass)
            tracker._forecast();tracker._forecast()
            self.assertEqual(tracker._persistent_goal_mass,before)
            for rival in tracker.riv:
                self.assertIs(tracker.post[rival],tracker._persistent_goal_mass[rival])
                with self.assertRaises(TypeError): tracker.post[rival][0]=0.
        self.assertEqual(calls,[1,2,3,4])


if __name__=='__main__': unittest.main()
