"""Author runner checks: toy source actors and mocked physics, no real study."""
import copy
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from local_cuda_matches import runner
from tests import reference_engine as engine


class FakePhysics:
    """Explicit synthetic CPU test double; never CUDA qualification evidence."""
    def __init__(self,bases,tokens,device,use_graph):
        self.games=[engine.Game(base=b,start_token=t,rules={'catch_requires_stay':True}) for b,t in zip(bases,tokens)]
        self.metadata={'SYNTHETIC_TEST_DOUBLE':True,'device':'cuda:synthetic','cuda_kernel_executed':False}
        self.timings={'SYNTHETIC_ONLY':0.0}
    def public_snapshot(self):
        boards=[]; masks=[]; tokens=[]
        for g in self.games:
            boards.append([[c.occupant,c.owner,c.is_upgraded,c.is_home,c.is_frozen,c.base_points] for row in g.board_view() for c in row])
            masks.append([[a in g.legal(seat) for a in engine.ACTIONS] for seat in range(4)]); tokens.append(g.token)
        return dict(board=boards,legal=masks,tokens=tokens)
    def state_snapshot(self):
        return dict(turn=self.games[0].turn,**{name:[copy.deepcopy(getattr(g,name)) for g in self.games] for name in runner.STATE_FIELDS})
    def step(self,codes):
        for g,joint in zip(self.games,codes): g.step([engine.ACTIONS[a] for a in joint])


class RunnerTests(unittest.TestCase):
    def setUp(self):
        parent=Path(runner.__file__).parent/'.cache'; parent.mkdir(exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(prefix='SYNTHETIC-runner-',dir=parent); self.addCleanup(self.temp.cleanup)
        self.directory=Path(self.temp.name)
        self.source=self.directory/'toy.py'; self.source.write_text('CONFIG={}\nCALLS=0\ndef act(view):\n global CALLS\n CALLS+=1\n return "STAY"\n',encoding='utf8')
        self.registration=self.registration_for(self.source)

    def registration_for(self,path):
        digest=runner.sha(path.read_bytes()); entry={'path':str(path),'sha256':digest}; fixtures=[]
        for i in range(3):
            base=engine.make_map(canonical=True)
            fixtures.append(dict(id='SYNTHETIC-'+str(i),candidate=digest,map_id=runner.sha(bytes(base)),
                base=base,token=i+1,seat=i,field='SYNTHETIC',
                opponents=[dict(id='SYNTHETIC-%d-%d'%(i,s),seat=s,family='planner',genes={},seed=1) for s in range(4) if s!=i]))
        return dict(format='SYNTHETIC_ONLY',rules={'catch_requires_stay':True},guards={str(path):digest},
                    candidates=[entry],sources={'planner':entry},fixtures=fixtures)

    def run_fake(self,registration=None,ids=('SYNTHETIC-0','SYNTHETIC-1'),output='output',factory=FakePhysics):
        with patch.object(runner,'_physics',side_effect=factory),patch.object(runner,'source_pins',return_value={'SYNTHETIC_ONLY':'a'*64}):
            return runner.run_fixtures(registration or self.registration,list(ids),self.directory/output)

    def test_compact_selected_snapshot_preserves_original_schedule_provenance_without_mutation(self):
        original=copy.deepcopy(self.registration)
        snapshot,selected,_=runner._registration(self.registration,['SYNTHETIC-2'])
        self.assertEqual(self.registration,original)
        self.assertEqual([f['id'] for f in snapshot['fixtures']],['SYNTHETIC-2'])
        self.assertEqual(snapshot['fixtures'],selected)
        expected=runner.sha(runner.canonical([f['id'] for f in original['fixtures']]))
        self.assertEqual(snapshot['local_cuda_source_schedule']['original_fixture_count'],3)
        self.assertEqual(snapshot['local_cuda_source_schedule']['ordered_original_fixture_ids_sha256'],expected)
        again,_,_=runner._registration(snapshot,['SYNTHETIC-2'])
        self.assertEqual(again['local_cuda_source_schedule'],snapshot['local_cuda_source_schedule'])

    def test_synthetic_full_games_have_measured_320_calls_80_turns_and81_comparisons(self):
        rows=self.run_fake(); self.assertEqual(len(rows),2)
        for row in rows:
            self.assertTrue(set(runner.BEHAVIOR)<=set(row)); self.assertEqual(len(row['actions']),80)
            self.assertEqual(row['proof']['callbacks_regenerated'],320)
            self.assertEqual(row['proof']['physical_turns'],80)
            self.assertEqual(row['proof']['gpu_reference_state_comparisons'],81)
            self.assertEqual(row['proof']['gpu_official_state_comparisons'],81)
            self.assertEqual(row['proof']['public_memory_oracles'],0)
            self.assertEqual(row['proof']['primary_games'],0)
            self.assertEqual([r['calls'] for r in row['timing']],[80]*4)
            self.assertEqual(row['faults'],[])
        output=self.directory/'output'
        self.assertEqual(len((output/'turns.jsonl').read_bytes().splitlines()),80)
        self.assertEqual(len((output/'games.jsonl').read_bytes().splitlines()),2)
        snapshot=runner.oversight.strict_loads((output/'registration.json').read_bytes())
        self.assertEqual(len(snapshot['fixtures']),2)
        self.assertEqual(snapshot['local_cuda_source_schedule']['original_fixture_count'],3)
        self.assertTrue((output/'.execution_claim').is_dir())

    def test_unknown_duplicate_ids_nonzero_credit_and_existing_output_fail_before_physics(self):
        with patch.object(runner,'source_pins',return_value={}),patch.object(runner,'_physics',side_effect=AssertionError('Physics called')):
            for ids in (['SYNTHETIC-0','SYNTHETIC-0'],['UNKNOWN'],[]):
                with self.subTest(ids=ids),self.assertRaises(ValueError):
                    runner.run_fixtures(self.registration,ids,self.directory/'rejected')
            for credit in (1,False):
                with self.subTest(credit=credit),self.assertRaises(ValueError):
                    runner.run_fixtures(self.registration,['SYNTHETIC-0'],self.directory/'rejected',primary_credit=credit)
            existing=self.directory/'existing'; existing.mkdir(); (existing/'preserve').write_bytes(b'KEEP')
            with self.assertRaises(ValueError): runner.run_fixtures(self.registration,['SYNTHETIC-0'],existing)
            self.assertEqual((existing/'preserve').read_bytes(),b'KEEP')

    def test_changed_source_rejected_before_claim_and_no_cpu_fallback_option(self):
        self.source.write_bytes(self.source.read_bytes()+b'\n# CHANGED\n')
        with patch.object(runner,'source_pins',return_value={}),patch.object(runner,'_physics',side_effect=AssertionError('Physics called')):
            with self.assertRaises(ValueError): runner.run_fixtures(self.registration,['SYNTHETIC-0'],self.directory/'changed')
            with self.assertRaises(ValueError): runner.run_fixtures(self.registration,['SYNTHETIC-0'],self.directory/'cpu',device='cpu')
        self.assertFalse((self.directory/'changed').exists())

    def test_corrupt_gpu_public_adapter_is_rejected_before_first_actor_call(self):
        class Corrupt(FakePhysics):
            def public_snapshot(self):
                result=super().public_snapshot(); result['board'][0][0][5]=3; return result
        with patch.object(runner.oversight,'make_actors',return_value=([lambda _:self.fail('Actor called')]*4,[None]*4)):
            with self.assertRaisesRegex(ValueError,'public board'):
                self.run_fake(factory=Corrupt)
        error=runner.oversight.strict_loads((self.directory/'output'/'error.json').read_bytes())
        self.assertEqual(error['partial']['proofs'][0]['callbacks_regenerated'],0)
        self.assertFalse((self.directory/'output'/'games.jsonl').exists())

    def test_base_exception_retains_partial_evidence_and_reraises_same_object(self):
        interruption=KeyboardInterrupt('SYNTHETIC_INTERRUPT')
        def stop(_): raise interruption
        with patch.object(runner.oversight,'make_actors',return_value=([stop]*4,[None]*4)):
            with self.assertRaises(KeyboardInterrupt) as raised: self.run_fake()
        self.assertIs(raised.exception,interruption)
        error=runner.oversight.strict_loads((self.directory/'output'/'error.json').read_bytes())
        self.assertEqual(error['exception_type'],'KeyboardInterrupt')
        self.assertEqual(error['partial']['proofs'][0]['callbacks_regenerated'],1)
        self.assertEqual(error['partial']['accepted_actions'],[[],[]])
        self.assertEqual(error['primary_games'],0)
        self.assertTrue((self.directory/'output'/'.execution_claim').exists())

    @unittest.skipUnless(os.environ.get('LOCAL_CUDA_SYNTHETIC_INTEGRATION')=='1',
                         'Explicit opt-in real-CUDA toy-actor integration only')
    def test_actual_cuda_two_synthetic_toy_actor_lanes_complete_80_turns(self):
        rows=runner.run_fixtures(self.registration,['SYNTHETIC-0','SYNTHETIC-1'],self.directory/'real-cuda-synthetic')
        self.assertEqual(len(rows),2)
        for row in rows:
            self.assertEqual(row['scores'],[158]*4)
            self.assertEqual(row['focal_pw'],1.5)
            self.assertEqual(row['proof']['callbacks_regenerated'],320)
            self.assertEqual(row['proof']['physical_turns'],80)
            self.assertEqual(row['proof']['gpu_reference_state_comparisons'],81)
            self.assertEqual(row['proof']['gpu_official_state_comparisons'],81)
            self.assertEqual(row['proof']['primary_games'],0)
        summary=runner.oversight.strict_loads((self.directory/'real-cuda-synthetic'/'summary.json').read_bytes())
        self.assertTrue(summary['physics_metadata']['cuda_kernel_executed'])
        self.assertEqual(summary['physics_metadata']['accepted_batch_steps'],80)
        self.assertEqual(summary['physics_metadata']['accepted_branch_turn_events'],160)
        self.assertEqual(summary['physics_metadata']['setup_throwaway_transitions'],3)
        self.assertFalse(summary['cpu_runtime']['cuda_used_by_policy'])
        self.assertEqual(summary['callbacks'],640)
        self.assertEqual(summary['primary_games'],0)


if __name__=='__main__': unittest.main()
