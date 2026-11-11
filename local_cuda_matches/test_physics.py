"""Actual-CUDA synthetic physics tests; zero policy/match campaign credit."""
import copy
import random
import unittest

import torch

from simulator.vendor_harness.referee import Referee
from tests import reference_engine as ref
from .physics import CudaPhysics,FIELDS,RULES


def codes(actions):
    return [[ref.ACTIONS.index(action) for action in row] for row in actions]


class CudaPhysicsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not torch.cuda.is_available():
            raise AssertionError('These tests require actual working CUDA, not a CPU skip/fallback')

    def load_constructed(self,games,*,use_graph=True):
        physics = CudaPhysics([g.base for g in games],[g.token for g in games],use_graph=use_graph)
        for field in FIELDS:
            buffer = getattr(physics.batch,field)
            buffer.copy_(torch.tensor([getattr(g,field) for g in games],dtype=buffer.dtype,device='cuda'))
        return physics

    def shadow(self,game):
        other = Referee(game.base,start_token=game.token,rules=dict(RULES))
        for field in ('owner','upg','home','pos','frozen','cd','prog','score'):
            setattr(other,field,list(getattr(game,field)))
        other.turn = game.turn
        return other

    def compare(self,physics,games,shadows):
        state = physics.state_snapshot()
        self.assertEqual(set(state),set(FIELDS)|{'turn'})
        self.assertEqual(state['turn'],games[0].turn)
        for field in FIELDS:
            self.assertEqual(state[field],[getattr(g,field) for g in games],field)
        for game,shadow in zip(games,shadows):
            for field in FIELDS:
                expected = shadow.income() if field=='income' else getattr(shadow,field)
                self.assertEqual(getattr(game,field),expected,field)
            self.assertEqual(game.turn,shadow.turn)
        public = physics.public_snapshot()
        self.assertEqual(set(public),{'board','legal','tokens'})
        self.assertEqual(public['tokens'],[g.token for g in games])
        for lane,(game,shadow) in enumerate(zip(games,shadows)):
            cells = [cell for row in game.board_view() for cell in row]
            self.assertEqual(public['board'][lane],[[c.occupant,c.owner,c.is_upgraded,c.is_home,c.is_frozen,c.base_points] for c in cells])
            expected = [[action in game.legal(seat) for action in ref.ACTIONS] for seat in range(4)]
            self.assertEqual(public['legal'][lane],expected)
            self.assertEqual(expected,[[action in shadow.legal(seat) for action in ref.ACTIONS] for seat in range(4)])
        return state

    def advance(self,physics,games,shadows,actions):
        for game,shadow,joint in zip(games,shadows,actions):
            self.assertTrue(all(action in game.legal(seat) and action in shadow.legal(seat) for seat,action in enumerate(joint)))
            game.step(joint);shadow.step(joint)
        physics.step(codes(actions))
        return self.compare(physics,games,shadows)

    def test_capture_restores_every_buffer_and80_replays_match_both_referees(self):
        rng = random.Random(2026110917)
        for use_graph in (True,False):
            with self.subTest(use_graph=use_graph):
                games = [ref.Game(base=ref.make_map(seed=700+i),start_token=i+1,rules=dict(RULES)) for i in range(4)]
                shadows = [self.shadow(g) for g in games]
                physics = CudaPhysics([g.base for g in games],[g.token for g in games],use_graph=use_graph)
                pointers = {field:getattr(physics.batch,field).data_ptr() for field in FIELDS}
                self.compare(physics,games,shadows)
                self.assertEqual(physics.metadata['accepted_batch_steps'],0)
                self.assertEqual(physics.metadata['setup_throwaway_transitions'],3 if use_graph else 0)
                for _ in range(80):
                    actions = [[rng.choice(game.legal(seat)) for seat in range(4)] for game in games]
                    self.advance(physics,games,shadows,actions)
                    self.assertEqual(pointers,{field:getattr(physics.batch,field).data_ptr() for field in FIELDS})
                self.assertEqual(physics.batch.turn,81)
                self.assertEqual(physics.metadata['accepted_batch_steps'],80)
                self.assertEqual(physics.metadata['accepted_branch_turn_events'],320)
                final = physics.state_snapshot()
                with self.assertRaises(ValueError):
                    physics.step([[4]*4 for _ in games])
                self.assertEqual(physics.state_snapshot(),final)
                self.assertTrue(physics.metadata['cuda_kernel_executed'])
                self.assertTrue(all(value>=0 for value in physics.timings.values()))

    def test_shield_moving_escape_blocked_catch_and_mutual_backfires(self):
        games = []
        for positions,ownership in (([0,27,63,56],{27:1,26:1}),
                                     ([0,27,26,56],{27:1,26:1}),
                                     ([18,27,63,56],{18:2,27:1})):
            game = ref.Game(rules=dict(RULES));game.pos=list(positions)
            for point,owner in ownership.items(): game.owner[point]=owner
            game.income=[sum(game.base[p]*(1+game.upg[p]) for p in range(64) if game.owner[p]==seat) for seat in range(1,5)]
            games.append(game)
        shadows = [self.shadow(g) for g in games]
        physics = self.load_constructed(games)
        actions = [['SHIELD','WEST','STAY','STAY'],['SHIELD','WEST','NORTH','STAY'],['SHIELD','SHIELD','STAY','STAY']]
        state = self.advance(physics,games,shadows,actions)
        self.assertEqual(state['frozen'],[[2,0,0,0],[0,2,0,0],[2,2,0,0]])
        self.assertEqual(state['pos'][0][1],26)
        self.assertEqual(state['pos'][1][1],27)

    def test_backfire_two_future_turns_and_four_turn_cooldown(self):
        games = [ref.Game(rules=dict(RULES))]
        shadows = [self.shadow(games[0])]
        physics = self.load_constructed(games)
        self.advance(physics,games,shadows,[['SHIELD','STAY','STAY','STAY']])
        for frozen,cooldown in ((2,4),(1,3),(0,2),(0,1),(0,0)):
            state = self.compare(physics,games,shadows)
            self.assertEqual((state['frozen'][0][0],state['cd'][0][0]),(frozen,cooldown))
            if cooldown:
                before=physics.state_snapshot()
                with self.assertRaises(ValueError): physics.step([[5,4,4,4]])
                self.assertEqual(physics.state_snapshot(),before)
                self.advance(physics,games,shadows,[['STAY']*4])
        self.assertTrue(physics.public_snapshot()['legal'][0][0][5])

    def test_contested_destination_owner_then_priority_wins(self):
        games=[]
        for owner,token in ((0,1),(0,2),(0,3),(0,4),(1,2),(2,1)):
            game=ref.Game(start_token=token,rules=dict(RULES));game.pos=[17,19,63,56]
            game.owner[18]=owner
            game.income=[sum(game.base[p] for p in range(64) if game.owner[p]==seat) for seat in range(1,5)]
            games.append(game)
        shadows=[self.shadow(g) for g in games]
        physics=self.load_constructed(games)
        state=self.advance(physics,games,shadows,[['EAST','WEST','STAY','STAY'] for _ in games])
        self.assertEqual([row[:2] for row in state['pos']],[[18,19],[17,18],[18,19],[18,19],[18,19],[17,18]])

    def test_upgraded_capture_bonus_progress_reset_and_three_stay_upgrade(self):
        game=ref.Game(rules=dict(RULES));game.pos[0]=18;game.owner[18]=2;game.upg[18]=1;game.prog[0]=2
        game.income=[sum(game.base[p]*(1+game.upg[p]) for p in range(64) if game.owner[p]==seat) for seat in range(1,5)]
        games=[game];shadows=[self.shadow(game)];physics=self.load_constructed(games)
        value=game.base[18]
        state=self.advance(physics,games,shadows,[['STAY']*4])
        self.assertEqual(state['owner'][0][18],1);self.assertFalse(state['upg'][0][18])
        self.assertEqual(state['prog'][0][0],0)
        self.assertEqual(state['score'][0][0],16*value+game.base[0]+value)
        for expected in (1,2,0):
            state=self.advance(physics,games,shadows,[['STAY']*4])
            self.assertEqual(state['prog'][0][0],expected)
        self.assertTrue(state['upg'][0][18])

    def test_strict_bad_actions_never_normalize_and_snapshots_are_isolated(self):
        physics=CudaPhysics([[1]*64],[1])
        initial=physics.state_snapshot()
        invalid=([],[[4]*3],[[4]*5],[[4]*4,[4]*4],[[True,4,4,4]],[[4.0]*4],
                 [[float('nan'),4,4,4]],[[-1,4,4,4]],[[6,4,4,4]],[[0,4,4,4]],
                 torch.ones((1,4),dtype=torch.bool),torch.ones((1,4),dtype=torch.float32),
                 torch.ones((1,4),dtype=torch.long,device='cuda'))
        for actions in invalid:
            with self.subTest(actions=str(actions)),self.assertRaises(ValueError): physics.step(actions)
            self.assertEqual(physics.state_snapshot(),initial)
        public=physics.public_snapshot();public['board'][0][0][0]=4;public['legal'][0][0][4]=False;public['tokens'][0]=4
        self.assertEqual(physics.state_snapshot(),initial)
        self.assertTrue(physics.public_snapshot()['legal'][0][0][4])
        initial['owner'][0][0]=4
        self.assertEqual(physics.state_snapshot()['owner'][0][0],1)
        physics.step(torch.full((1,4),4,dtype=torch.int32))
        self.assertEqual(physics.batch.turn,2)

    def test_cpu_fallback_bad_maps_tokens_rules_and_clock_are_rejected(self):
        with self.assertRaises(ValueError): CudaPhysics([[1]*64],[1],device='cpu')
        for maps,tokens in (([],[]),([[True]*64],[1]),([[float('inf')]*64],[1]),([[1]*63],[1]),
                            ([[1]*64],[True]),([[1]*64],[0]),([[1]*64],[])):
            with self.subTest(maps=str(maps)[:20],tokens=tokens),self.assertRaises(ValueError): CudaPhysics(maps,tokens)
        physics=CudaPhysics([[1]*64],[1]);physics.batch.R['catch_requires_stay']=False
        with self.assertRaises(ValueError): physics.step([[4]*4])
        physics.batch.R['catch_requires_stay']=True;physics.batch.turn=2
        with self.assertRaises(ValueError): physics.step([[4]*4])


if __name__=='__main__': unittest.main()
