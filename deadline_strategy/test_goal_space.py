"""Synthetic goal-score/source mechanics; no strength games or live outcomes."""
import copy
import math
import unittest
from unittest.mock import patch

from deadline_runner.actors import freeze_lane, ACTIONS
from deadline_strategy import goal_space as space
from deadline_strategy.space import PublicMemoryTemplateSpace
from deadline_strategy.test_space import masked
from evolution.oversight import referee, signature, state_equal
from strategy_candidates.test_public_memory import path
from tests import reference_engine as engine


def load(body):
    namespace={'__name__':'_synthetic_persistent_goal'}
    exec(compile(body,'<synthetic-persistent-goal>','exec'),namespace)
    return namespace


def public_view(game,seat):
    board=[[c.occupant,c.owner,c.is_upgraded,c.is_home,c.is_frozen,c.base_points]
           for row in game.board_view() for c in row]
    legal=[[a in game.legal(s) for a in ACTIONS] for s in range(4)]
    return freeze_lane(board,legal,[game.token==s+1 for s in range(4)])[seat]


def attractiveness(tracker,rival):
    values=[]
    for goal in range(64):
        owner=tracker.own[goal];base=tracker.base[goal]
        if owner==0: value=base
        elif owner==rival: value=0 if tracker.upg[goal] else .6*base
        elif tracker.home[goal]: value=0
        elif tracker.upg[goal]: value=.6*base
        else: value=2.5*base
        if tracker.occ[goal] and tracker.occ[goal]!=rival: value*=.3
        distance=abs(tracker.pos[rival]//8-goal//8)+abs(tracker.pos[rival]%8-goal%8)
        values.append(value/(distance+1))
    total=sum(values)
    if not total: values[tracker.pos[rival]]=1;total=1
    return [v/total for v in values]


class PersistentGoalTests(unittest.TestCase):
    def setUp(self):
        self.space=space.PersistentGoalTemplateSpace()
        self.namespace=load(self.space.export(self.space.defaults))
        self.tracker=self.namespace['BlockerBot'](seed=7919)

    def test_exact_default_canonical_numeric_family_and_structural_pins(self):
        body=self.space.export(self.space.defaults)
        self.assertEqual(space.sha(body),space.TEMPLATE_SHA256)
        self.assertEqual(self.space.defaults,PublicMemoryTemplateSpace().defaults)
        self.assertEqual(len(self.space.bounds),12)
        self.assertEqual(self.space.inspect_export(body),self.space.defaults)
        for seed in range(12):
            genes=self.space.mutate(self.space.defaults,seed)
            changed=self.space.export(genes)
            self.assertEqual(masked(body,self.space.bounds),masked(changed,self.space.bounds))
            self.assertEqual(self.space.inspect_export(changed),genes)
        for changed in (body+b'\n',body.replace(b'0.8 * prior[g] + 0.2 * q[g]',b'0.7 * prior[g] + 0.3 * q[g]'),
                        body.replace(b'4.0 **',b'5.0 **'),body.replace(b'seed=seat * 7919',b'seed=seat * 7920')):
            with self.assertRaises(ValueError): self.space.inspect_export(changed)
        with self.assertRaises(ValueError): self.space.inspect_export(PublicMemoryTemplateSpace().export(self.space.defaults))
        pins=space.source_pins();pins['deadline_strategy/goal_space.py']='0'*64
        with patch.object(space,'source_pins',return_value=pins):
            with self.assertRaises(ValueError): self.space.export(self.space.defaults)
        description=self.space.description()
        self.assertFalse(description['initial_panel_included'])
        self.assertTrue(description['requires_explicit_future_train_amendment'])
        self.assertFalse(description['runtime_qualified'])
        self.assertEqual(description['primary_credit'],0)

    def test_independent_formula_movement_stationarity_and_no_double_count(self):
        game=engine.Game(base=engine.make_map(seed=714),start_token=3)
        self.tracker._observe(public_view(game,0))
        for rival in self.tracker.riv:
            for actual,want in zip(self.tracker._persistent_goal_mass[rival],attractiveness(self.tracker,rival)):
                self.assertAlmostEqual(actual,want,places=14)
        old=copy.deepcopy(self.tracker._persistent_goal_mass)
        positions=game.pos[:]
        joint=['STAY','WEST','NORTH','STAY']
        self.tracker.last=joint[0];game.step(joint)
        self.tracker._observe(public_view(game,0))
        for rival in self.tracker.riv:
            q=attractiveness(self.tracker,rival)
            remaining=sum(old[rival][g] for g in range(64) if q[g]>0)
            expected=[]
            for goal in range(64):
                if q[goal]==0: expected.append(0);continue
                prior=old[rival][goal]/remaining if remaining else q[goal]
                before=abs(positions[rival-1]//8-goal//8)+abs(positions[rival-1]%8-goal%8)
                after=abs(game.pos[rival-1]//8-goal//8)+abs(game.pos[rival-1]%8-goal%8)
                likelihood=math.exp(math.log(4)*(before-after)) if positions[rival-1]!=game.pos[rival-1] else 1
                expected.append(likelihood*(.8*prior+.2*q[goal]))
            norm=sum(expected)
            for actual,want in zip(self.tracker._persistent_goal_mass[rival],expected):
                self.assertAlmostEqual(actual,want/norm,places=14)
        once=copy.deepcopy(self.tracker._persistent_goal_mass)
        self.tracker._forecast();self.tracker._forecast()
        self.assertEqual(self.tracker._persistent_goal_mass,once)
        for rival in self.tracker.riv:
            self.assertIs(self.tracker.post[rival],self.tracker._persistent_goal_mass[rival])

    def test_every_observation_updates_even_when_focal_frozen_and_blocked_rival_is_uninformative(self):
        game=engine.Game()
        self.tracker.act(public_view(game,0))
        updates=[];original=self.tracker._update_goal_mass
        def update(): updates.append(self.tracker.t);return original()
        self.tracker._update_goal_mass=update
        # Scripted own backfire creates two forced-STAY observations. Rival2
        # moves WEST at every step; its evidence must not disappear while we freeze.
        for joint in (['SHIELD','WEST','STAY','STAY'],['STAY','WEST','STAY','STAY'],['STAY','WEST','STAY','STAY']):
            self.tracker.last=joint[0]
            self.assertTrue(all(a in game.legal(s) for s,a in enumerate(joint)))
            game.step(joint)
            self.tracker.act(public_view(game,0))
            self.assertTrue(all(abs(sum(v)-1)<1e-12 for v in self.tracker._persistent_goal_mass.values()))
        self.assertEqual(updates,[2,3,4])
        # Public stationary rival2 under an occupied-start WEST attempt has L=1.
        # Compare with accepted STAY in the same public world; no rival intention
        # is supplied to the observer in either branch.
        actions=[['STAY','WEST','STAY','STAY'] for _ in range(6)]
        memories=[]
        for last in ('WEST','STAY'):
            branch=engine.Game();tracker=self.namespace['BlockerBot'](seed=1)
            for joint in actions:
                tracker._observe(public_view(branch,0));tracker.last=joint[0];branch.step(joint)
            tracker._observe(public_view(branch,0));tracker.last='STAY'
            branch.step(['STAY',last,'STAY','STAY'])
            tracker._observe(public_view(branch,0));memories.append(tracker._persistent_goal_mass)
        self.assertEqual(memories[0],memories[1])

    def test_invalid_targets_removed_and_empty_valid_prior_restarts(self):
        game=engine.Game();self.tracker._observe(public_view(game,0))
        rival=2;invalid=game.pos[rival-1]
        self.tracker._persistent_goal_mass[rival]=tuple(1.0 if g==invalid else 0.0 for g in range(64))
        # A fully legal three-STAY home upgrade removes the old sole target.
        for _ in range(3):
            self.tracker.last='STAY';game.step(['STAY']*4)
            # Keep the sole prior on the soon-invalid target to isolate reset.
            if game.turn<4:
                self.tracker._observe(public_view(game,0))
                self.tracker._persistent_goal_mass[rival]=tuple(1.0 if g==invalid else 0.0 for g in range(64))
        self.tracker._observe(public_view(game,0))
        self.assertTrue(game.upg[invalid])
        self.assertEqual(self.tracker._persistent_goal_mass[rival][invalid],0)
        q=attractiveness(self.tracker,rival)
        for actual,want in zip(self.tracker._persistent_goal_mass[rival],q):
            self.assertAlmostEqual(actual,want,places=14)

    def test_f5_mechanics_and_hidden_world_invariance_survive_goal_extension(self):
        worlds=[]
        for actions in (path(own_final='WEST'),path(own_final='WEST',defender_final='SHIELD',raider_final='STAY')):
            game=engine.Game(rules={'catch_requires_stay':True})
            official=referee.Referee(game.base,start_token=game.token,rules=game.rules)
            tracker=self.namespace['BlockerBot'](seed=7919);public=[]
            for joint in actions:
                view=public_view(game,0);before=signature(view)
                tracker._observe(view);tracker.last=joint[0]
                self.assertEqual(signature(view),before)
                self.assertEqual(tracker.prog,game.prog[0])
                self.assertEqual([tracker.score[s] for s in range(1,5)],game.score)
                self.assertTrue(all(a in game.legal(s) for s,a in enumerate(joint)))
                public.append(before);game.step(joint);official.step(joint);state_equal(game,official)
            tracker._observe(public_view(game,0));public.append(signature(public_view(game,0)))
            worlds.append((game,tracker,public))
        self.assertEqual(worlds[0][2],worlds[1][2])
        self.assertNotEqual(worlds[0][0].cd,worlds[1][0].cd)
        a,b=worlds[0][1],worlds[1][1]
        self.assertEqual(a.__dict__,b.__dict__ | {'rng':a.rng})
        self.assertEqual(a._decide(public_view(worlds[0][0],0)),b._decide(public_view(worlds[1][0],0)))


if __name__=='__main__': unittest.main()
