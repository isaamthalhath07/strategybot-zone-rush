"""Synthetic CPU orchestration and full replay tests; no gold/study launch."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from deadline_runner import runner
from tests import reference_engine as engine


class FakePhysics:
    """CPU test double, explicitly not CUDA qualification evidence."""
    def __init__(self,fixtures,device):
        self.games=[engine.Game(base=f['base'],start_token=f['token'],rules={'catch_requires_stay':True}) for f in fixtures]
        self.metadata={'SYNTHETIC_TEST_DOUBLE':True}; self.timings={'synthetic_s':0.0}
    def public_snapshot(self):
        boards=[]; legal=[]; tokens=[]
        for game in self.games:
            boards.append([[c.occupant,c.owner,c.is_upgraded,c.is_home,c.is_frozen,c.base_points] for row in game.board_view() for c in row])
            legal.append([[a in game.legal(s) for a in engine.ACTIONS] for s in range(4)]); tokens.append(game.token)
        return dict(board=boards,legal=legal,tokens=tokens)
    def state_snapshot(self):
        return dict(turn=self.games[0].turn,**{name:[copy.deepcopy(getattr(g,name)) for g in self.games] for name in runner.frozen.STATE_FIELDS})
    def step(self,codes):
        for game,row in zip(self.games,codes): game.step([engine.ACTIONS[a] for a in row])


class RunnerTests(unittest.TestCase):
    def setUp(self):
        parent=runner.ROOT/'deadline_runner'/'.cache'; parent.mkdir(exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(prefix='SYNTHETIC-',dir=parent); self.addCleanup(self.temp.cleanup)
        self.directory=Path(self.temp.name); self.source=self.directory/'toy.py'
        self.source.write_text('CONFIG={}\ndef act(view): return "STAY"\n',encoding='utf8')
        entry=dict(path=str(self.source),sha256=runner.sha(self.source.read_bytes())); fixtures=[]
        for i in range(3):
            base=engine.make_map(canonical=True)
            fixtures.append(dict(id='SYNTHETIC-%d'%i,candidate=entry['sha256'],map_id=runner.sha(bytes(base)),base=base,
                token=i+1,seat=i,field='SYNTHETIC',opponents=[dict(id='SYNTHETIC-R%d'%s,seat=s,family='planner',seed=1,
                    genes={},pair_parameter_id='a'*64) for s in range(4) if s!=i]))
        self.reg=dict(candidates=[entry],sources={'planner':entry},guards={str(self.source):entry['sha256']},
                      rules={'catch_requires_stay':True},fixtures=fixtures)

    def synthetic_row(self,index=0):
        f=self.reg['fixtures'][index]; game=engine.Game(base=f['base'],start_token=f['token']); tape=[['STAY']*4 for _ in range(80)]
        for joint in tape: game.step(joint)
        return dict(candidate=f['candidate'],fixture=f['id'],map_id=f['map_id'],focal_seat=f['seat'],field=f['field'],
            scores=game.score,focal_pw=1.5,focal_score=game.score[f['seat']],opponent_ids=[s['id'] for s in f['opponents']],
            actions=tape,faults=[],timing=[dict(calls=80,first_ms=.001,regular_max_ms=.001,max_ms=.001,total_ms=.08) for _ in range(4)])

    def task(self,row=None):
        return runner._audit_task(self.reg['candidates'][0],self.reg['fixtures'][0],self.reg['sources'],
                                  row or self.synthetic_row(),runner.source_pins(),0)

    def test_exact_frozen_audit_body_regenerates320_without_mutating_global_factory(self):
        original=runner.oversight.audit_game; factory=original.__globals__['make_actors']
        proof=runner._audit_job(self.task())
        self.assertTrue(proof['ok']); self.assertEqual(proof['callbacks_regenerated'],320)
        self.assertEqual(proof['tracker']['attempts_by_seat'],[80]*4)
        self.assertEqual(proof['tracker']['returns_by_seat'],[80]*4)
        self.assertEqual(proof['dual_referee_physical_turns'],80)
        self.assertIs(runner.oversight.audit_game,original)
        self.assertIs(original.__globals__['make_actors'],factory)

    def test_audit_wrong_tape_preserves_actual_attempts_and_returns_safe_error(self):
        row=self.synthetic_row(); row['actions'][0][0]='EAST'
        proof=runner._audit_job(self.task(row))
        self.assertFalse(proof['ok']); self.assertEqual(proof['tracker']['attempted'],1)
        self.assertEqual(proof['tracker']['returned'],1)
        self.assertTrue(proof['validated_complete_callbacks_unknown'])
        self.assertEqual(proof['primary_games'],0)

    def test_full_fake_physics_pipeline_has_all_original_and_independent_callbacks(self):
        output=self.directory/'pipeline'
        with patch.object(runner,'_physics',side_effect=FakePhysics):
            result=runner.run_fixtures(self.reg,['SYNTHETIC-0','SYNTHETIC-1'],output,batch_size=1,workers=2,audit_workers=2)
        self.assertEqual([r['fixture'] for r in result['rows']],['SYNTHETIC-0','SYNTHETIC-1'])
        self.assertEqual([r['fixture'] for r in result['audits']],['SYNTHETIC-0','SYNTHETIC-1'])
        self.assertEqual(result['summary']['original_callbacks'],640)
        self.assertEqual(result['summary']['independently_regenerated_callbacks'],640)
        self.assertEqual(result['summary']['original_gpu_physical_turns'],160)
        self.assertEqual(result['summary']['independent_dual_referee_turns'],160)
        self.assertEqual(result['summary']['primary_games'],0)
        for row in result['rows']:
            self.assertEqual(row['proof']['gpu_reference_state_comparisons'],81)
            self.assertEqual(row['proof']['gpu_official_state_comparisons'],81)
            self.assertEqual(row['scores'],[158]*4)
        self.assertEqual(len((output/'originals.jsonl').read_bytes().splitlines()),2)
        self.assertEqual(len((output/'audits.jsonl').read_bytes().splitlines()),2)
        self.assertEqual(len((output/'batch_00000'/'turns.jsonl').read_bytes().splitlines()),80)
        self.assertTrue((output/'.execution_claim').exists())
        manifest=json.loads((output/'source_snapshot.json').read_bytes())
        for digest,path in manifest['artifacts'].items():
            self.assertEqual(runner.sha((output/path).read_bytes()),digest)
        self.assertEqual(result['summary']['source_snapshot_sha256'],runner.sha((output/'source_snapshot.json').read_bytes()))
        with self.assertRaises(ValueError): runner.run_fixtures(self.reg,['SYNTHETIC-0'],output)

    def test_backpressure_starts_no_third_completed_batch_before_draining_first(self):
        events=[]
        class Future:
            def __init__(self,fn,task): self.fn=fn; self.task=task
            def result(self):
                events.append('drain%d'%self.task['batch_index']); return self.fn(self.task)
        class Executor:
            def submit(self,fn,task):
                events.append('submit%d'%task['batch_index']); return Future(fn,task)
            def shutdown(self,**_): pass
        def physics(fixtures,device):
            events.append('original'+fixtures[0]['id'].rsplit('-',1)[1]); return FakePhysics(fixtures,device)
        with patch.object(runner,'_physics',side_effect=physics),patch.object(runner,'_audit_executor',return_value=Executor()):
            result=runner.run_fixtures(self.reg,[f['id'] for f in self.reg['fixtures']],self.directory/'bounded',batch_size=1,workers=1,audit_workers=1)
        self.assertLess(events.index('submit1'),events.index('drain0'))
        self.assertLess(events.index('drain0'),events.index('original2'))
        self.assertEqual(result['summary']['max_completed_batches_pending_audit_observed'],2)

    def test_forged_incomplete_audit_response_cannot_complete_pipeline(self):
        class Future:
            def __init__(self,task): self.task=task
            def result(self):
                row=self.task['row']; return dict(ok=True,fixture=row['fixture'],row_sha256=runner.sha(runner.canonical(row)),
                    candidate=row['candidate'],callbacks_regenerated=1)
        class Executor:
            def submit(self,_,task): return Future(task)
            def shutdown(self,**_): pass
        output=self.directory/'forged'
        with patch.object(runner,'_physics',side_effect=FakePhysics),patch.object(runner,'_audit_executor',return_value=Executor()):
            with self.assertRaises(runner.AuditFailure):
                runner.run_fixtures(self.reg,['SYNTHETIC-0'],output,batch_size=1,workers=1,audit_workers=1)
        self.assertFalse((output/'summary.json').exists()); self.assertTrue((output/'error.json').exists())
        audit=json.loads((output/'audits.jsonl').read_bytes().splitlines()[0])
        self.assertFalse(audit['ok']); self.assertEqual(audit['error_type'],'IncompleteAuditProof')

    def test_source_snapshot_deduplicates_bytes_and_rejects_tampering_or_path_escape(self):
        output=self.directory/'snapshot'; output.mkdir()
        registration=copy.deepcopy(self.reg); registration['owner_key']='SYNTHETIC_PRIVATE_HEADER'
        manifest=runner._snapshot_sources(output,runner.source_pins(),registration)
        self.assertNotIn('SYNTHETIC_PRIVATE_HEADER',(output/'source_snapshot.json').read_text())
        self.assertEqual(len(list((output/'sources').iterdir())),len(manifest['artifacts']))
        self.assertEqual(len(manifest['actors']),2)  # same guarded body, one stored artifact
        runner._verify_source_snapshot(output,manifest)
        digest,path=next(iter(manifest['artifacts'].items())); original=(output/path).read_bytes()
        (output/path).write_bytes(original+b'\n# SYNTHETIC_TAMPER')
        with self.assertRaisesRegex(ValueError,'source bytes changed'): runner._verify_source_snapshot(output,manifest)
        (output/path).write_bytes(original)
        escaped=copy.deepcopy(manifest); escaped['artifacts'][digest]='../outside.py'
        with self.assertRaisesRegex(ValueError,'artifact path'): runner._verify_source_snapshot(output,escaped)
        (output/'source_snapshot.sha256').write_text('0'*64+'\n')
        with self.assertRaisesRegex(ValueError,'manifest seal changed'): runner._verify_source_snapshot(output,manifest)


if __name__=='__main__': unittest.main()
