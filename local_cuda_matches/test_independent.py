"""Independent synthetic-only local CUDA boundary and full-state checks.

These tests consume no study/gold fixture or outcome and grant no match credit.
The actual CUDA checks require the owner's existing CUDA-enabled interpreter.
"""
import copy
import hashlib
import json
from pathlib import Path
import random
import tempfile
import unittest
from unittest.mock import patch

from evolution import oversight
from search_coach.belief import PublicObservation
from tests import reference_engine as engine

try:
    import torch
    CUDA_AVAILABLE = torch.cuda.is_available()
except ImportError:
    torch = None
    CUDA_AVAILABLE = False


def expected_state(games):
    result = {name:[copy.deepcopy(getattr(game,name)) for game in games]
              for name in ('base','owner','upg','home','pos','frozen','cd','prog','score','income')}
    result['token'] = [game.token for game in games]
    result['turn'] = games[0].turn
    return result


def expected_public(games):
    return dict(board=[[list(cell) for cell in PublicObservation.from_view(game.views()[0]).cells] for game in games],
                legal=[[[action in game.legal(seat) for action in engine.ACTIONS] for seat in range(4)] for game in games],
                tokens=[game.token for game in games])


@unittest.skipUnless(CUDA_AVAILABLE,'Requires the existing CUDA-enabled .venv-rl interpreter')
class IndependentCudaPhysicsTests(unittest.TestCase):
    def make(self,graph):
        from local_cuda_matches.physics import CudaPhysics
        bases = [engine.make_map(canonical=True),engine.make_map(seed=7801),engine.make_map(seed=7802)]
        tokens = [1,2,4]
        physics = CudaPhysics(bases,tokens,device='cuda',use_graph=graph)
        games = [engine.Game(base=base,start_token=token,rules={'catch_requires_stay':True})
                 for base,token in zip(bases,tokens)]
        shadows = [oversight.referee.Referee(base,start_token=token,rules={'catch_requires_stay':True})
                   for base,token in zip(bases,tokens)]
        return physics,games,shadows

    def assert_full(self,physics,games,shadows):
        self.assertEqual(physics.state_snapshot(),expected_state(games))
        self.assertEqual(physics.public_snapshot(),expected_public(games))
        for game,shadow in zip(games,shadows):
            oversight.state_equal(game,shadow)

    def test_real_cuda_eager_and_graph_restore_and_all80_turns_match_two_refs(self):
        for graph in (False,True):
            with self.subTest(graph=graph):
                physics,games,shadows = self.make(graph)
                self.assert_full(physics,games,shadows)
                rng = random.Random(202611102117)
                for _ in range(80):
                    joints = [[rng.choice(game.legal(seat)) for seat in range(4)] for game in games]
                    codes = [[engine.ACTIONS.index(action) for action in joint] for joint in joints]
                    physics.step(codes)
                    for game,shadow,joint in zip(games,shadows,joints):
                        game.step(joint)
                        shadow.step(joint)
                    self.assert_full(physics,games,shadows)
                self.assertEqual(physics.state_snapshot()['turn'],81)
                before = physics.state_snapshot()
                with self.assertRaises(ValueError):
                    physics.step([[4]*4 for _ in games])
                self.assertEqual(physics.state_snapshot(),before)

    def test_real_cuda_bad_actions_reject_transactionally_and_snapshots_are_isolated(self):
        physics,games,shadows = self.make(True)
        original = physics.state_snapshot()
        bad = ([[4]*4],[[4]*5 for _ in games],[[True,4,4,4] for _ in games],
               [[4.0,4,4,4] for _ in games],[[-1,4,4,4] for _ in games],
               [[6,4,4,4] for _ in games],[[0,4,4,4] for _ in games])
        for actions in bad:
            with self.subTest(actions=actions),self.assertRaises((ValueError,TypeError)):
                physics.step(actions)
            self.assertEqual(physics.state_snapshot(),original)
        if torch is not None:
            for actions in (torch.ones((3,4),dtype=torch.float32),torch.full((3,4),4,device='cuda')):
                with self.assertRaises((ValueError,TypeError)):
                    physics.step(actions)
                self.assertEqual(physics.state_snapshot(),original)
        exposed = physics.public_snapshot()
        self.assertEqual(set(exposed),{'board','legal','tokens'})
        exposed['board'][0][0][1] = 4
        exposed['legal'][0][0][0] = True
        state = physics.state_snapshot()
        state['cd'][0][0] = 999
        self.assert_full(physics,games,shadows)


SYNTHETIC_ACTOR = '''
ARM = %r
CALLS = 0
INPUTS = []
CONFIG = {}
_input_failures = 0
_policy_failures = 0
def act(view):
    global CALLS
    CALLS += 1
    assert set(view.__slots__) == {'board','bot_id','is_priority_token','legal_actions'}
    assert type(view.board) is tuple and type(view.legal_actions) is tuple
    assert not any(hasattr(view,key) for key in ('score','cd','prog','turn','seed','opponents','referee'))
    cells = [cell for row in view.board for cell in row]
    assert all(set(cell.__slots__) == {'occupant','owner','is_upgraded','is_home','is_frozen','base_points'} for cell in cells)
    try:
        view.board[0][0].owner = 4
    except AttributeError:
        pass
    else:
        raise AssertionError('mutable cell')
    positions = tuple(next(p for p,c in enumerate(cells) if c.occupant == who) for who in range(1,5))
    INPUTS.append((positions,view.bot_id,view.is_priority_token,view.legal_actions))
    if view.bot_id == 1 and CALLS == 1 and 'EAST' in view.legal_actions:
        return 'EAST'
    if view.bot_id == 2 and positions[0] != 0 and positions[1] == 7 and 'WEST' in view.legal_actions:
        return 'WEST'
    return 'STAY'
'''


class SpyPhysics:
    """Deliberately CPU test double; never passed off as real CUDA evidence."""
    def __init__(self,bases,tokens,device,use_graph):
        self.games = [engine.Game(base=base,start_token=token,rules={'catch_requires_stay':True})
                      for base,token in zip(bases,tokens)]
        self.steps = 0
        self.public_calls = 0
        self.state_calls = 0
        self.timings = {'synthetic_only':0.0}
        self.metadata = dict(device='SYNTHETIC_CPU_TEST_DOUBLE',cuda_kernel_executed=False,
                             setup_primary_match_credit=0,setup_completed_game_audit_credit=0)
        self.state_fault = None
        self.public_fault = None

    def public_snapshot(self):
        self.public_calls += 1
        result = expected_public(self.games)
        if self.public_fault:
            self.public_fault(result,self.steps)
        return result

    def state_snapshot(self):
        self.state_calls += 1
        result = expected_state(self.games)
        if self.state_fault:
            self.state_fault(result,self.steps)
        return result

    def step(self,codes):
        self.steps += 1
        for game,row in zip(self.games,codes):
            game.step([engine.ACTIONS[code] for code in row])


class IndependentRunnerTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='.independent-',dir=Path(__file__).parent)
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.entries = []
        for arm in range(4):
            path = self.directory/('synthetic_arm%d.py'%arm)
            body = (SYNTHETIC_ACTOR%('synthetic%d'%arm)).encode('utf8')
            path.write_bytes(body)
            self.entries.append(dict(path=str(path),sha256=hashlib.sha256(body).hexdigest()))
        base = engine.make_map(canonical=True)
        map_id = hashlib.sha256(bytes(base)).hexdigest()
        self.fixtures = [dict(id='SYNTHETIC_LANE_%d'%arm,candidate=entry['sha256'],base=base,
            map_id=map_id,seat=0,token=1,field='economic',opponents=[dict(seat=seat,family='planner',genes={},
                id='SYNTHETIC_RIVAL_%d_%d'%(arm,seat),seed=9000+10*arm+seat) for seat in (1,2,3)])
                         for arm,entry in enumerate(self.entries)]
        self.registration = dict(guards={entry['path']:entry['sha256'] for entry in self.entries},
            candidates=self.entries,sources={'planner':self.entries[0]},fixtures=self.fixtures,
            rules={'catch_requires_stay':True})
        self.created = []
        self.physics = []

    def factory(self,bases,tokens,device,use_graph):
        instance = SpyPhysics(bases,tokens,device,use_graph)
        self.physics.append(instance)
        return instance

    def run_synthetic(self,identities=None,**options):
        from local_cuda_matches import runner
        actual = oversight.make_actors
        def record(*args):
            result = actual(*args)
            self.created.append(result)
            return result
        with patch.object(runner,'_physics',side_effect=self.factory),patch.object(oversight,'make_actors',side_effect=record):
            return runner.run_fixtures(self.registration,
                identities or [fixture['id'] for fixture in self.fixtures],self.directory/'output',**options)

    def error(self,output=None):
        path = (self.directory/'output' if output is None else output)/'error.json'
        self.assertTrue(path.exists())
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),path.with_suffix('.sha256').read_text().strip())
        return json.loads(path.read_text())

    def test_exact_source_dispatch_fresh_lane_globals_public_simultaneity_and_measured_coverage(self):
        identities = [self.fixtures[index]['id'] for index in (3,1,0,2)]
        rows = self.run_synthetic(identities)
        self.assertEqual([row['fixture'] for row in rows],identities)
        self.assertEqual(len(self.created),4)
        all_globals = [actor.__globals__ for actors,_ in self.created for actor in actors]
        self.assertEqual(len({id(namespace) for namespace in all_globals}),16)
        for row,(actors,namespaces),arm in zip(rows,self.created,(3,1,0,2)):
            self.assertEqual(namespaces[0]['ARM'],'synthetic%d'%arm)
            self.assertTrue(all(namespace['CALLS']==80 for namespace in namespaces))
            self.assertEqual(row['actions'][0],['EAST','STAY','STAY','STAY'])
            self.assertEqual(row['actions'][1][1],'WEST')
            for seat,namespace in enumerate(namespaces):
                self.assertEqual(namespace['INPUTS'][0][0],(0,7,63,56))
                self.assertEqual(namespace['INPUTS'][0][1],seat+1)
            self.assertEqual(row['proof']['callbacks_regenerated'],320)
            self.assertEqual([value['calls'] for value in row['timing']],[80]*4)
            self.assertEqual(row['proof']['physical_turns'],80)
            self.assertEqual(row['proof']['gpu_reference_state_comparisons'],81)
            self.assertEqual(row['proof']['gpu_official_state_comparisons'],81)
            self.assertEqual(row['proof']['primary_games'],0)
            self.assertEqual(row['proof']['completed_per_game_bmcts_audits'],0)
        physics = self.physics[0]
        self.assertEqual((physics.steps,physics.public_calls,physics.state_calls),(80,81,81))
        summary = json.loads((self.directory/'output/summary.json').read_text())
        self.assertEqual(summary['callbacks'],1280)
        self.assertEqual(summary['gpu_physical_turns'],320)
        self.assertEqual(summary['primary_games'],0)
        self.assertEqual(len((self.directory/'output/turns.jsonl').read_text().splitlines()),80)

    def test_checked_gpu_public_adapter_cannot_disagree_with_full_state_before_callbacks(self):
        original = self.factory
        def corrupt(*args):
            instance = original(*args)
            instance.public_fault = lambda public,steps:public['board'][0][1].__setitem__(1,4)
            return instance
        self.factory = corrupt
        with self.assertRaisesRegex(ValueError,'public board disagrees'):
            self.run_synthetic([self.fixtures[0]['id']])
        self.assertEqual(sum(namespace['CALLS'] for _,namespaces in self.created for namespace in namespaces),0)
        self.assertEqual(self.error()['partial']['proofs'][0]['callbacks_regenerated'],0)
        self.assertEqual(self.physics[0].steps,0)

    def test_full_gpu_state_corruption_aborts_whole_batch_with_pending_actions_and_no_complete_game(self):
        original = self.factory
        def corrupt(*args):
            instance = original(*args)
            def fault(state,steps):
                if steps == 2:
                    state['cd'][1][3] = 999
            instance.state_fault = fault
            return instance
        self.factory = corrupt
        with self.assertRaisesRegex(ValueError,'state disagreement'):
            self.run_synthetic([fixture['id'] for fixture in self.fixtures[:2]])
        error = self.error()
        self.assertEqual(error['partial']['active']['turn'],2)
        self.assertEqual([len(tape) for tape in error['partial']['accepted_actions']],[1,1])
        self.assertEqual([proof['callbacks_regenerated'] for proof in error['partial']['proofs']],[8,8])
        self.assertEqual(len(error['partial']['pending_actions']),2)
        self.assertEqual(error['primary_games'],0)
        self.assertFalse((self.directory/'output/games.jsonl').exists())

    def test_keyboard_interrupt_seals_exact_attempted_callback_counts_and_rethrows_same_stop(self):
        from local_cuda_matches import runner
        actual = oversight.make_actors
        stopped = KeyboardInterrupt('synthetic stop only')
        def interrupt(*args):
            actors,namespaces = actual(*args)
            def fail(view):
                raise stopped
            actors[1] = fail
            return actors,namespaces
        with patch.object(runner,'_physics',side_effect=self.factory),patch.object(oversight,'make_actors',side_effect=interrupt):
            with self.assertRaises(KeyboardInterrupt) as caught:
                runner.run_fixtures(self.registration,[self.fixtures[0]['id']],self.directory/'output')
        self.assertIs(caught.exception,stopped)
        error = self.error()
        self.assertEqual(error['exception_type'],'KeyboardInterrupt')
        self.assertEqual(error['partial']['active'],dict(turn=1,lane=0,seat=1,phase='actors'))
        self.assertEqual(error['partial']['proofs'][0]['callbacks_regenerated'],2)
        self.assertEqual([value['calls'] for value in error['partial']['timing'][0]],[1,1,0,0])
        self.assertEqual(error['partial']['pending_actions'],[['EAST']])
        self.assertEqual(self.physics[0].steps,0)
        self.assertFalse((self.directory/'output/games.jsonl').exists())
        with self.assertRaisesRegex(ValueError,'Fresh output'):
            runner.run_fixtures(self.registration,[self.fixtures[0]['id']],self.directory/'output')

    def test_invalid_credit_cpu_device_duplicate_ids_and_rehashed_source_drift_reject_before_cuda(self):
        from local_cuda_matches import runner
        for options,identities in (({'primary_credit':1},[self.fixtures[0]['id']]),
                                   ({'device':'cpu'},[self.fixtures[0]['id']]),
                                   ({},[self.fixtures[0]['id']]*2)):
            with patch.object(runner,'_physics') as factory,self.assertRaises(ValueError):
                runner.run_fixtures(self.registration,identities,self.directory/'output',**options)
            factory.assert_not_called()
        Path(self.entries[3]['path']).write_text('changed synthetic source',encoding='utf8')
        with patch.object(runner,'_physics') as factory,self.assertRaisesRegex(ValueError,'source guard changed'):
            runner.run_fixtures(self.registration,[self.fixtures[0]['id']],self.directory/'output')
        factory.assert_not_called()

    def test_illegal_mutation_fallback_and_public_memory_faults_reject_before_physics(self):
        from local_cuda_matches import runner
        actual = oversight.make_actors
        for mode in ('illegal','mutation','fallback','oracle'):
            with self.subTest(mode=mode):
                output = self.directory/('fault_'+mode)
                def make(*args):
                    actors,namespaces = actual(*args)
                    namespace = namespaces[0]
                    def fault(view):
                        if mode == 'illegal':
                            return 'NORTH'
                        if mode == 'mutation':
                            object.__setattr__(view.board[0][0],'owner',4)
                        elif mode == 'fallback':
                            namespace['_policy_failures'] = 1
                        else:
                            namespace['_history'] = {1:dict(cooldown_possible={seat:{0} for seat in range(1,5)},
                                                          progress=999,scores=[0]*5)}
                        return 'STAY'
                    actors[0] = fault
                    return actors,namespaces
                with patch.object(runner,'_physics',side_effect=self.factory),patch.object(oversight,'make_actors',side_effect=make):
                    with self.assertRaises(ValueError):
                        runner.run_fixtures(self.registration,[self.fixtures[0]['id']],output)
                error = self.error(output)
                self.assertEqual(error['partial']['proofs'][0]['callbacks_regenerated'],1)
                self.assertEqual(error['partial']['accepted_actions'],[[]])
                self.assertEqual(self.physics[-1].steps,0)
                self.assertFalse((output/'games.jsonl').exists())

    def test_first_and_regular_deadlines_are_checked_and_actual_late_call_remains_in_partial_counts(self):
        from local_cuda_matches import runner
        actual = oversight.make_actors
        for late_turn,seconds in ((1,2.001),(2,.201)):
            with self.subTest(late_turn=late_turn):
                output = self.directory/('late_%d'%late_turn)
                clock = [0.0]
                def make(*args):
                    actors,namespaces = actual(*args)
                    first = actors[0]
                    namespace = namespaces[0]
                    def late(view):
                        if namespace['CALLS'] == late_turn-1:
                            clock[0] += seconds
                        return first(view)
                    actors[0] = late
                    return actors,namespaces
                with patch.object(runner,'_physics',side_effect=self.factory),patch.object(oversight,'make_actors',side_effect=make),\
                        patch.object(runner.time,'perf_counter',side_effect=lambda:clock[0]):
                    with self.assertRaisesRegex(ValueError,'deadline'):
                        runner.run_fixtures(self.registration,[self.fixtures[0]['id']],output)
                error = self.error(output)
                self.assertEqual(error['partial']['active']['turn'],late_turn)
                self.assertEqual(error['partial']['proofs'][0]['callbacks_regenerated'],4*(late_turn-1)+1)
                self.assertEqual([rec['calls'] for rec in error['partial']['timing'][0]],
                                 [late_turn]+[late_turn-1]*3)
                self.assertEqual(len(error['partial']['accepted_actions'][0]),late_turn-1)
                self.assertEqual(self.physics[-1].steps,late_turn-1)

    def test_postgame_runtime_source_drift_preserves_all_partial_tapes_without_publishing_games(self):
        from local_cuda_matches import runner
        with patch.object(runner,'_physics',side_effect=self.factory),\
                patch.object(runner,'source_pins',side_effect=[{'runtime':'before'},{'runtime':'after'}]):
            with self.assertRaisesRegex(ValueError,'source changed during'):
                runner.run_fixtures(self.registration,[self.fixtures[0]['id']],self.directory/'output')
        error = self.error()
        self.assertEqual(error['partial']['active']['phase'],'final_source_and_coverage_checks')
        self.assertEqual(len(error['partial']['accepted_actions'][0]),80)
        self.assertEqual(error['partial']['proofs'][0]['callbacks_regenerated'],320)
        self.assertFalse((self.directory/'output/games.jsonl').exists())


if __name__ == '__main__':
    unittest.main()
