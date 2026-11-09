"""Independent synthetic mechanics checks. No CUDA, gold or study execution.

The scalar physics test double is deliberately identified as such. These tests
exercise exact actor loaders and CPU replay auditors, and confer zero credit.
"""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from deadline_runner import actors, runner
from tests import reference_engine as engine


RANDOM_ACTOR = b'''import random
CONFIG={}
RNG=random.Random(72931)
CALLS=0
SEEN=[]
def act(view):
    global CALLS
    CALLS+=1
    SEEN.append(tuple(tuple(tuple(c) if isinstance(c,tuple) else
        (c.occupant,c.owner,c.is_upgraded,c.is_home,c.is_frozen,c.base_points)
        for c in row) for row in view.board))
    legal=tuple(view.legal_actions)
    return legal[(CALLS+RNG.randrange(len(legal)))%len(legal)]
'''


def compact(game, identity='INDEPENDENT-0'):
    return dict(lane_id=identity,board=[
        [c.occupant,c.owner,c.is_upgraded,c.is_home,c.is_frozen,c.base_points]
        for row in game.board_view() for c in row],
        legal=[[a in game.legal(seat) for a in engine.ACTIONS] for seat in range(4)],
        priority=[game.token==seat+1 for seat in range(4)])


class ScalarPhysics:
    """Independent CPU test double; its metadata explicitly denies CUDA use."""
    instances=[]
    corrupt_terminal=False

    def __init__(self, fixtures, device):
        self.games=[engine.Game(base=f['base'],start_token=f['token'],
            rules={'catch_requires_stay':True}) for f in fixtures]
        self.steps=self.public_reads=self.state_reads=0
        self.metadata={'SYNTHETIC_CPU_TEST_DOUBLE':True,'cuda_kernel_executed':False}
        self.timings={'synthetic_s':0.0}
        self.instances.append(self)

    def public_snapshot(self):
        self.public_reads+=1
        rows=[compact(game) for game in self.games]
        return dict(board=[r['board'] for r in rows],legal=[r['legal'] for r in rows],
                    tokens=[game.token for game in self.games])

    def state_snapshot(self):
        self.state_reads+=1
        state=dict(turn=self.games[0].turn,**{name:[copy.deepcopy(getattr(g,name))
            for g in self.games] for name in runner.frozen.STATE_FIELDS})
        if self.corrupt_terminal and self.steps==80:
            state['income'][0][0]+=1
        return state

    def step(self, codes):
        self.steps+=1
        for game,row in zip(self.games,codes):
            game.step([engine.ACTIONS[code] for code in row])


class SyntheticCase(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='INDEPENDENT-SYNTHETIC-',
            dir=runner.ROOT/'deadline_runner')
        self.addCleanup(self.temp.cleanup)
        self.directory=Path(self.temp.name)
        self.source=self.directory/'actor.py'
        self.registration=self.register(RANDOM_ACTOR)
        ScalarPhysics.instances=[]
        actors._dispatch({'operation':'reset'})
        self.addCleanup(actors._dispatch,{'operation':'reset'})

    def register(self, body, count=3):
        self.source.write_bytes(body)
        entry=dict(path=str(self.source),sha256=runner.sha(body))
        fixtures=[]
        for index in range(count):
            base=engine.make_map(seed=600+index)
            seat=index%4
            fixtures.append(dict(id='INDEPENDENT-%d'%index,candidate=entry['sha256'],
                map_id=runner.sha(bytes(base)),base=base,token=index%4+1,seat=seat,
                field='SYNTHETIC-ONLY',opponents=[dict(id='RIVAL-%d'%s,seat=s,
                    family='planner',seed=(1<<90)+s,genes={},pair_parameter_id='b'*64)
                    for s in range(4) if s!=seat]))
        return dict(guards={str(self.source):entry['sha256']},candidates=[entry],
            sources={'planner':entry},fixtures=fixtures,rules={'catch_requires_stay':True},
            observer_private_header='NEVER-PASS-THIS-TO-AN-ACTOR')

    def initialize(self, identities=None):
        ids=identities or [self.registration['fixtures'][0]['id']]
        lanes,sources=actors.constructor_messages(self.registration,ids)
        reply=actors._dispatch(dict(operation='initialize',batch='synthetic',lanes=lanes,sources=sources))
        self.assertTrue(reply['ok'],reply)
        return lanes,sources

    def decide(self, game, turn):
        return actors._dispatch(dict(operation='decide',batch='synthetic',turn=turn,lanes=[compact(game)]))

    def row(self, index=0):
        f=self.registration['fixtures'][index]
        game=engine.Game(base=f['base'],start_token=f['token'],rules={'catch_requires_stay':True})
        policies,_=runner.oversight.make_actors(self.registration['candidates'][0],f,self.registration['sources'])
        tape=[]
        for _ in range(80):
            views=game.views()
            joint=[policy(view) for policy,view in zip(policies,views)]
            tape.append(joint);game.step(joint)
        seat=f['seat'];scores=game.score
        return dict(candidate=f['candidate'],fixture=f['id'],map_id=f['map_id'],
            focal_seat=seat,field=f['field'],scores=scores,focal_score=scores[seat],
            focal_pw=sum(1 if scores[seat]>s else .5 if scores[seat]==s else 0
                for i,s in enumerate(scores) if i!=seat),
            opponent_ids=[r['id'] for r in f['opponents']],actions=tape,faults=[],
            timing=[dict(calls=80,first_ms=.1,regular_max_ms=.1,max_ms=.1,total_ms=8.) for _ in range(4)])

    def task(self, row=None):
        return runner._audit_task(self.registration['candidates'][0],self.registration['fixtures'][0],
            self.registration['sources'],self.row() if row is None else row,runner.source_pins(),0)


class PublicBoundaryTests(SyntheticCase):
    def test_deep_immutable_exact_schema_and_same_board(self):
        raw=compact(engine.Game())
        views=actors.freeze_lane(raw['board'],raw['legal'],raw['priority'])
        self.assertEqual(views[0]._fields,('board','bot_id','is_priority_token','legal_actions'))
        self.assertEqual(views[0].board[0][0]._fields,
            ('occupant','owner','is_upgraded','is_home','is_frozen','base_points'))
        self.assertTrue(all(view.board is views[0].board for view in views))
        self.assertIs(type(views[0].board),tuple)
        for view in views:
            self.assertFalse(hasattr(view,'__dict__'))
            self.assertEqual(view.legal_actions,tuple(engine.Game().legal(view.bot_id-1)))
            self.assertIs(type(view.bot_id),int)
            self.assertIs(type(view.is_priority_token),bool)
        original=runner.oversight.signature(views[0])
        for target,name,value in ((views[0],'board',()),(views[0],'secret',1),
                (views[0].board[0][0],'owner',4)):
            with self.subTest(field=name),self.assertRaises((AttributeError,TypeError)):
                object.__setattr__(target,name,value)
        with self.assertRaises((AttributeError,TypeError)):
            object.__delattr__(views[0].board[0][0],'owner')
        with self.assertRaises(TypeError): views[0].board[0][0][1]=4
        with self.assertRaises(TypeError): views[0].board[0][0]=None
        altered=views[0].board[0][0]._replace(owner=4)
        self.assertEqual(altered.owner,4)
        raw['board'][0][1]=4;raw['legal'][0][0]=not raw['legal'][0][0]
        self.assertEqual(runner.oversight.signature(views[0]),original)

    def test_strict_builtin_leaves_and_public_only_constructor(self):
        class IntChild(int): pass
        raw=compact(engine.Game())
        mutations=[lambda r:r['board'][0].append('private'),
            lambda r:r['board'][0].__setitem__(0,True),
            lambda r:r['board'][0].__setitem__(1,IntChild(1)),
            lambda r:r['board'][0].__setitem__(2,0),
            lambda r:r['legal'][0].__setitem__(4,1),
            lambda r:r['priority'].__setitem__(1,True)]
        for mutation in mutations:
            changed=copy.deepcopy(raw);mutation(changed)
            with self.subTest(mutation=mutation),self.assertRaises(ValueError):
                actors.freeze_lane(changed['board'],changed['legal'],changed['priority'])
        lanes,sources=actors.constructor_messages(self.registration,['INDEPENDENT-0'])
        wire=runner.canonical(dict(lanes=lanes,sources=sources))
        for secret in ('NEVER-PASS','map_id','base','guards','pair_parameter_id','score','cooldown'):
            self.assertNotIn(secret.encode(),wire)
        self.assertEqual(set(lanes[0]),{'lane_id','candidate','fixture'})
        self.assertEqual(set(lanes[0]['fixture']),{'id','seat','opponents'})
        self.assertEqual(lanes[0]['fixture']['opponents'][0]['seed'],(1<<90)+1)
        for bad in ('private_key','state','registration'):
            reg=copy.deepcopy(self.registration);reg['fixtures'][0]['opponents'][0][bad]='NO'
            with self.subTest(bad=bad),self.assertRaises(ValueError):
                actors.constructor_messages(reg,['INDEPENDENT-0'])
        self.source.write_bytes(self.source.read_bytes()+b'\n# drift\n')
        with self.assertRaises(ValueError): actors.constructor_messages(self.registration,['INDEPENDENT-0'])

    def test_fresh_namespaces_rng_and_all_preturn_observations_for80(self):
        lanes,sources=self.initialize(['INDEPENDENT-0','INDEPENDENT-1'])
        fixtures=self.registration['fixtures'][:2]
        games=[engine.Game(base=f['base'],start_token=f['token']) for f in fixtures]
        serial=[runner.oversight.make_actors(lane['candidate'],lane['fixture'],sources)
            for lane in lanes]
        namespaces=[ns for lane in actors._LANES.values() for ns in lane['namespaces']]
        self.assertEqual(len({id(ns) for ns in namespaces}),8)
        self.assertEqual(len({id(ns['RNG']) for ns in namespaces}),8)
        for turn in range(1,81):
            before=[compact(g,f['id']) for g,f in zip(games,fixtures)]
            expected=[[policy(view) for policy,view in zip(policies,g.views())]
                for (policies,_),g in zip(serial,games)]
            result=actors._dispatch(dict(operation='decide',batch='synthetic',turn=turn,lanes=before))
            self.assertTrue(result['ok'],result)
            self.assertEqual([r['actions'] for r in result['lanes']],expected)
            for i,(game,row) in enumerate(zip(games,result['lanes'])):
                self.assertEqual(row['proof']['completed_total'],[turn]*4)
                same_board=tuple(tuple(tuple(c) for c in before[i]['board'][r*8:(r+1)*8]) for r in range(8))
                for ns in actors._LANES[fixtures[i]['id']]['namespaces']:
                    self.assertEqual(ns['SEEN'][-1],same_board)
                game.step(row['actions'])
        self.assertTrue(all(game.over() and game.turn==81 for game in games))
        self.assertFalse(self.decide(games[0],81)['ok'])
        actors._dispatch({'operation':'reset'})
        self.initialize()
        self.assertTrue(all(ns['CALLS']==0 for ns in actors._LANES['INDEPENDENT-0']['namespaces']))


class FailureBoundaryTests(SyntheticCase):
    def test_callback_faults_have_exact_partial_counts_and_poison_batch(self):
        cases=[('return "BOGUS"',1,False),
            ('object.__setattr__(view,"bot_id",4)\n    return "STAY"',0,False),
            ('global _policy_failures\n    _policy_failures=1\n    return "STAY"',1,True),
            ('raise KeyboardInterrupt("synthetic interruption")',0,False)]
        for body,returned,fallback in cases:
            with self.subTest(body=body):
                actors._dispatch({'operation':'reset'})
                self.registration=self.register(('CONFIG={}\ndef act(view):\n    '+body+'\n').encode())
                self.initialize();reply=self.decide(engine.Game(),1)
                self.assertFalse(reply['ok'])
                proof=reply['active_partial_lane']['proof']
                self.assertEqual([proof[k] for k in ('attempted_callbacks','returned_callbacks','completed_callbacks')],
                    [1,returned,0])
                self.assertIs(proof['timing'][0]['fallback'],fallback)
                self.assertEqual(reply['lane_counters']['INDEPENDENT-0']['attempts_total'],[1,0,0,0])
                self.assertFalse(self.decide(engine.Game(),1)['ok'])

    def test_deadline_and_nonfinite_elapsed_fail_without_substitution(self):
        self.registration=self.register(b'CONFIG={}\ndef act(view): return "STAY"\n')
        for elapsed in (2.001,-.01,float('nan')):
            with self.subTest(elapsed=elapsed):
                actors._dispatch({'operation':'reset'});self.initialize()
                with patch.object(actors.time,'perf_counter',side_effect=[0.,elapsed]):
                    reply=self.decide(engine.Game(),1)
                self.assertFalse(reply['ok'])
                self.assertEqual(reply['active_partial_lane']['actions'],[])
                self.assertEqual(reply['active_partial_lane']['proof']['returned_callbacks'],1)
        actors._dispatch({'operation':'reset'});self.initialize()
        game=engine.Game();self.assertTrue(self.decide(game,1)['ok']);game.step(['STAY']*4)
        with patch.object(actors.time,'perf_counter',side_effect=[0.,.201]): reply=self.decide(game,2)
        self.assertFalse(reply['ok'])
        self.assertEqual(reply['lane_counters']['INDEPENDENT-0']['completed_total'],[1]*4)

    def test_end_source_drift_keeps_all320_observed_calls_but_fails(self):
        self.registration=self.register(b'CONFIG={}\ndef act(view): return "STAY"\n')
        self.initialize();game=engine.Game()
        for turn in range(1,80):
            self.assertTrue(self.decide(game,turn)['ok']);game.step(['STAY']*4)
        self.source.write_bytes(self.source.read_bytes()+b'# changed during batch\n')
        result=self.decide(game,80)
        self.assertFalse(result['ok'])
        self.assertEqual(result['lane_counters']['INDEPENDENT-0']['completed_total'],[80]*4)
        self.assertEqual(len(result['completed_lanes']),1)
        self.assertIn('changed',result['error']['message'])


class PipelineTests(SyntheticCase):
    def test_forged_audit_proof_matrix_is_rejected_before_publication(self):
        # Admission-boundary unit test: mock original generation, but start each
        # forgery from one genuine, full synthetic CPU replay receipt.
        row=self.row();valid=runner._audit_job(self.task(row))
        self.assertTrue(valid['ok'],valid)
        mutations={
            'coverage319':lambda p:p.__setitem__('callbacks_regenerated',319),
            'coverage_float':lambda p:p.__setitem__('callbacks_regenerated',320.0),
            'source_closure':lambda p:p.__setitem__('source_closure_sha256','0'*64),
            'auditor_source':lambda p:p.__setitem__('audit_source_sha256','0'*64),
            'candidate':lambda p:p.__setitem__('candidate','0'*64),
            'fixture_bytes':lambda p:p.__setitem__('fixture_sha256','0'*64),
            'row_bytes':lambda p:p.__setitem__('row_sha256','0'*64),
            'fixture_identity':lambda p:p.__setitem__('fixture','FOREIGN'),
            'batch_bool':lambda p:p.__setitem__('batch_index',False),
            'oracle_bool':lambda p:p.__setitem__('public_memory_oracles',False),
            'oracle_negative':lambda p:p.__setitem__('public_memory_oracles',-1),
            'tracker_float':lambda p:p['tracker'].__setitem__('attempted',320.0),
            'seat_float':lambda p:p['tracker']['returns_by_seat'].__setitem__(0,80.0),
            'timing_calls':lambda p:p['tracker']['timing'][0].__setitem__('calls',79),
            'late':lambda p:p['tracker']['timing'][0].__setitem__('regular_max_ms',201),
            'credit_bool':lambda p:p.__setitem__('primary_games',False),
            'credit_one':lambda p:p.__setitem__('study_games',1),
            'ok_int':lambda p:p.__setitem__('ok',1),
            'malformed_tracker':lambda p:p.__setitem__('tracker',[]),
        }
        class NoOriginalActors:
            evidence=[]
            def close(self): pass
        class Future:
            def __init__(self,proof): self.proof=proof
            def result(self): return self.proof
        class Executor:
            def __init__(self,proof): self.proof=proof;self.submissions=0
            def submit(self,_,task): self.submissions+=1;return Future(self.proof)
            def shutdown(self,**_): pass
        def generation(snapshot,fixtures,candidates,actor_pool,directory,device,pins,partial):
            directory.mkdir();partial.update(phase='mock-original-only',turn=0)
            return [copy.deepcopy(row)],{'SYNTHETIC_MOCK_NO_ORIGINAL_CALLBACKS':True}
        for label,mutate in mutations.items():
            with self.subTest(label=label):
                proof=copy.deepcopy(valid);mutate(proof)
                executor=Executor(proof);output=self.directory/('forged-'+label)
                with patch.object(runner,'_actors',return_value=NoOriginalActors()),\
                        patch.object(runner,'_generate_batch',side_effect=generation),\
                        patch.object(runner,'_audit_executor',return_value=executor):
                    with self.assertRaises(runner.AuditFailure):
                        runner.run_fixtures(self.registration,['INDEPENDENT-0'],output,
                            batch_size=1,workers=1,audit_workers=1)
                self.assertEqual(executor.submissions,1)
                self.assertFalse((output/'summary.json').exists())
                rejected=json.loads((output/'audits.jsonl').read_bytes().splitlines()[0])
                self.assertIs(rejected['ok'],False)
                error=json.loads((output/'error.json').read_bytes())
                self.assertEqual(error['completed_successful_audits'],0)
                self.assertEqual(error['primary_games'],0)
                self.assertEqual(len((output/'originals.jsonl').read_bytes().splitlines()),1)

    def test_spawned_full_pipeline_and_sealed_row_audit_bindings(self):
        output=self.directory/'complete'
        with patch.object(runner,'_physics',side_effect=ScalarPhysics):
            result=runner.run_fixtures(self.registration,['INDEPENDENT-0','INDEPENDENT-1'],
                output,batch_size=1,workers=2,audit_workers=2)
        summary=result['summary']
        for key in ('primary_games','study_games','completed_per_game_bmcts_audits'):
            self.assertIs(type(summary[key]),int);self.assertEqual(summary[key],0)
        self.assertEqual(summary['original_callbacks'],640)
        self.assertEqual(summary['independently_regenerated_callbacks'],640)
        self.assertEqual(summary['max_completed_batches_pending_audit_observed'],2)
        self.assertEqual([(p.steps,p.public_reads,p.state_reads) for p in ScalarPhysics.instances],[(80,81,81)]*2)
        self.assertEqual(summary['originals_sha256'],runner.sha((output/'originals.jsonl').read_bytes()))
        self.assertEqual(summary['audits_sha256'],runner.sha((output/'audits.jsonl').read_bytes()))
        pins=summary['source_sha256']
        archive_path=output/'source_snapshot.json'
        archive=json.loads(archive_path.read_bytes())
        self.assertEqual(summary['source_snapshot_sha256'],runner.sha(archive_path.read_bytes()))
        self.assertEqual(set(archive['runtime']),set(pins))
        self.assertNotIn(b'NEVER-PASS-THIS-TO-AN-ACTOR',archive_path.read_bytes())
        self.assertEqual(set(archive['artifacts']),set(pins.values())|{self.registration['candidates'][0]['sha256']})
        for digest,relative in archive['artifacts'].items():
            self.assertEqual(relative,'sources/'+digest+'.py')
            self.assertEqual(runner.sha((output/relative).read_bytes()),digest)
        for name,entry in archive['runtime'].items():
            self.assertEqual(entry['sha256'],pins[name])
            self.assertEqual((output/entry['artifact']).read_bytes(),(runner.ROOT/name).read_bytes())
        self.assertEqual(len(archive['actors']),2)
        self.assertEqual({entry['artifact'] for entry in archive['actors']},
            {'sources/'+self.registration['candidates'][0]['sha256']+'.py'})
        for index,(row,audit) in enumerate(zip(result['rows'],result['audits'])):
            proof=row['proof'];directory=output/('batch_%05d'%index)
            self.assertEqual(row['actions'],self.row(index)['actions'])
            self.assertEqual(proof['gpu_reference_state_comparisons'],81)
            self.assertEqual(proof['gpu_official_state_comparisons'],81)
            self.assertEqual(proof['physical_turns'],80)
            self.assertEqual(proof['registration_snapshot_sha256'],runner.sha((directory/'registration.json').read_bytes()))
            self.assertEqual(audit['row_sha256'],runner.sha(runner.canonical(row)))
            self.assertEqual(audit['source_closure_sha256'],runner.sha(runner.canonical(pins)))
            self.assertEqual(audit['tracker']['attempts_by_seat'],[80]*4)
            self.assertEqual(audit['tracker']['returns_by_seat'],[80]*4)
            self.assertEqual(audit['public_memory_oracles'],0)  # toy declares no supported oracle
            turns=[json.loads(line) for line in (directory/'turns.jsonl').read_bytes().splitlines()]
            self.assertEqual([t['turn'] for t in turns],list(range(1,81)))
            self.assertEqual(turns[-1]['gpu_state_chain_sha256'][0],proof['gpu_state_chain_sha256'])
            self.assertEqual(turns[-1]['gpu_public_chain_sha256'][0],proof['gpu_public_chain_sha256'])
        with self.assertRaises(ValueError): runner.run_fixtures(self.registration,['INDEPENDENT-0'],output)

    def test_terminal_only_physical_corruption_cannot_publish_completed_row(self):
        output=self.directory/'terminal-corruption'
        with patch.object(ScalarPhysics,'corrupt_terminal',True),patch.object(runner,'_physics',side_effect=ScalarPhysics):
            with self.assertRaises(ValueError) as caught:
                runner.run_fixtures(self.registration,['INDEPENDENT-0'],output,batch_size=1,workers=1,audit_workers=1)
        self.assertFalse((output/'summary.json').exists())
        error=json.loads((output/'error.json').read_bytes())
        self.assertEqual(error['completed_originals'],0)
        self.assertEqual(error['primary_games'],0)
        self.assertEqual(error['partial']['turn'],80)
        self.assertEqual(len(error['partial']['actions'][0]),79)
        self.assertEqual(error['partial']['proofs'][0]['callbacks_completed'],320)
        self.assertEqual(caught.exception.deadline_runner_partial['completed_originals'],0)
        self.assertEqual((output/'originals.jsonl').read_bytes(),b'')

    def test_later_original_failure_drains_prior_full_audit_without_retry(self):
        output=self.directory/'later-failure'
        submissions=[]
        real_executor=runner._audit_executor
        class RecordingExecutor:
            def __init__(self,workers): self.inner=real_executor(workers)
            def submit(self,fn,task):
                submissions.append(task['fixture']['id'])
                return self.inner.submit(fn,task)
            def shutdown(self,**kwargs): self.inner.shutdown(**kwargs)
        def physics(fixtures,device):
            instance=ScalarPhysics(fixtures,device)
            instance.corrupt_terminal=len(ScalarPhysics.instances)==2
            return instance
        with patch.object(runner,'_physics',side_effect=physics),\
                patch.object(runner,'_audit_executor',side_effect=RecordingExecutor):
            with self.assertRaises(ValueError):
                runner.run_fixtures(self.registration,['INDEPENDENT-0','INDEPENDENT-1'],
                    output,batch_size=1,workers=1,audit_workers=1)
        self.assertEqual(submissions,['INDEPENDENT-0'])
        error=json.loads((output/'error.json').read_bytes())
        self.assertEqual(error['completed_originals'],1)
        self.assertEqual(error['completed_successful_audits'],1)
        self.assertEqual(error['primary_games'],0)
        self.assertFalse((output/'summary.json').exists())
        audit=json.loads((output/'audits.jsonl').read_bytes().splitlines()[0])
        self.assertTrue(audit['ok']);self.assertEqual(audit['callbacks_regenerated'],320)
        self.assertEqual(audit['tracker']['attempts_by_seat'],[80]*4)
        self.assertTrue((output/'batch_00000'/'audit_summary.json').exists())
        self.assertEqual(len((output/'originals.jsonl').read_bytes().splitlines()),1)
        self.assertEqual(len((output/'batch_00001'/'turns.jsonl').read_bytes().splitlines()),79)

    def test_auditor_uses_fresh_callbacks_and_preserves_frozen_globals_on_failure(self):
        audit=runner.oversight.audit_game
        factory=audit.__globals__['make_actors']
        result=runner._audit_job(self.task())
        self.assertTrue(result['ok'],result)
        self.assertEqual(result['tracker']['attempted'],320)
        self.assertEqual(result['callbacks_regenerated'],320)
        self.assertEqual(result['dual_referee_physical_turns'],80)
        self.assertIs(audit.__globals__['make_actors'],factory)
        self.assertIs(runner.oversight.audit_game,audit)
        row=self.row();row['actions'][0][0]='STAY' if row['actions'][0][0]!='STAY' else 'SOUTH'
        failed=runner._audit_job(self.task(row))
        self.assertFalse(failed['ok'])
        self.assertEqual(failed['tracker']['attempted'],1)
        self.assertEqual(failed['tracker']['returned'],1)
        self.assertTrue(failed['validated_complete_callbacks_unknown'])
        self.assertIs(audit.__globals__['make_actors'],factory)


if __name__=='__main__': unittest.main()
