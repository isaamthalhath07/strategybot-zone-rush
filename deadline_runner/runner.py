"""Local fast immutable CPU actors, CUDA physics and complete replay audits.

Every original turn is checked against two CPU referees. A separate persistent
CPU pool regenerates all320 callbacks per completed original. At most two
completed original batches can await audits; nothing receives admission here.
"""
from collections import deque
from concurrent.futures import ProcessPoolExecutor
import copy
import hashlib
import math
import multiprocessing
import os
from pathlib import Path
import time
import types

from evolution import oversight
from local_cuda_matches import runner as frozen
from tests import reference_engine as engine

ROOT=Path(__file__).resolve().parents[1]
FORMAT='deadline-local-immutable-actors-cuda-full-audit/1'
canonical=frozen.canonical
sha=frozen.sha


class AuditFailure(RuntimeError):
    def __init__(self,evidence):
        self.evidence=evidence
        super().__init__('Independent full actor replay failed; preserve all originals and audit evidence')


def source_pins():
    from . import actors
    result=frozen.source_pins()
    for name,digest in actors.source_pins().items():
        if name in result and result[name]!=digest: raise ValueError('Fast actor/runtime source closure disagreement')
        result[name]=digest
    for name in ('deadline_runner/__init__.py','deadline_runner/runner.py','deadline_runner/actors.py'):
        result[name]=sha((ROOT/name).read_bytes())
    return dict(sorted(result.items()))


def _actors(workers):
    from .actors import FastActorPool
    return FastActorPool(worker_count=workers)


def _physics(fixtures,device):
    from local_cuda_matches.physics import CudaPhysics
    return CudaPhysics([f['base'] for f in fixtures],[f['token'] for f in fixtures],device=device,use_graph=True)


def _entry(entry):
    result=dict(path=entry['path'],sha256=entry['sha256'])
    if sha(Path(result['path']).read_bytes())!=result['sha256']: raise ValueError('Exact actor source changed')
    return result


def _audit_task(candidate,fixture,sources,row,pins,batch_index):
    fields=('id','candidate','map_id','base','seat','token','field')
    selected={name:copy.deepcopy(fixture[name]) for name in fields}
    selected['opponents']=[]
    for raw in fixture['opponents']:
        allowed={'id','seat','family','seed','genes','epsilon','commitment','pair_parameter_id'}
        if not set(raw)<=allowed: raise ValueError('Unexpected private/credential actor specification field')
        if 'pair_parameter_id' in raw:
            provenance=raw['pair_parameter_id']
            if type(provenance) is not str or len(provenance)!=64 or any(c not in '0123456789abcdef' for c in provenance):
                raise ValueError('Invalid pair provenance')
        selected['opponents'].append({k:copy.deepcopy(v) for k,v in raw.items() if k!='pair_parameter_id'})
    task=dict(candidate=_entry(candidate),fixture=selected,sources={k:_entry(v) for k,v in sources.items()},
              row=row,source_sha256=pins,batch_index=batch_index)
    canonical(task)  # Only trusted plain-data commands, no arbitrary pickle payload.
    return task


def _audit_job(task):
    """Reuse the exact frozen audit body with passive callback instrumentation."""
    tracker=dict(attempted=0,returned=0,attempts_by_seat=[0]*4,returns_by_seat=[0]*4,
        timing=[dict(calls=0,first_ms=0.0,regular_max_ms=0.0,max_ms=0.0,total_ms=0.0) for _ in range(4)],
        active_seat=None,active_callback_turn=None)
    started=time.perf_counter()
    base=dict(fixture=task['fixture']['id'],candidate=task['candidate']['sha256'],
        batch_index=task['batch_index'],row_sha256=sha(canonical(task['row'])),
        fixture_sha256=sha(canonical(task['fixture'])),source_closure_sha256=sha(canonical(task['source_sha256'])),
        audit_source_sha256=sha((ROOT/'evolution/oversight.py').read_bytes()),primary_games=0,study_games=0,
        completed_per_game_bmcts_audits=0)
    try:
        if set(task)!={'candidate','fixture','sources','row','source_sha256','batch_index'}:
            raise ValueError('Unexpected audit task/capability field')
        if source_pins()!=task['source_sha256']: raise ValueError('Audit source closure changed')
        _entry(task['candidate'])
        for source in task['sources'].values(): _entry(source)
        def tracked_make(candidate,fixture,sources):
            actors,namespaces=oversight.make_actors(candidate,fixture,sources)
            def wrap(actor,seat):
                def observed(view):
                    tracker['attempted']+=1; tracker['attempts_by_seat'][seat]+=1
                    turn=tracker['attempts_by_seat'][seat]
                    tracker.update(active_seat=seat,active_callback_turn=turn)
                    began=time.perf_counter()
                    try:
                        action=actor(view); tracker['returned']+=1; tracker['returns_by_seat'][seat]+=1
                    finally:
                        elapsed=time.perf_counter()-began
                        rec=tracker['timing'][seat]; rec['calls']+=1
                        if math.isfinite(elapsed) and elapsed>=0:
                            ms=elapsed*1000; rec['total_ms']+=ms; rec['max_ms']=max(rec['max_ms'],ms)
                            if turn==1: rec['first_ms']=ms
                            else: rec['regular_max_ms']=max(rec['regular_max_ms'],ms)
                        else: tracker['invalid_elapsed_repr']=repr(elapsed)
                    if not math.isfinite(elapsed) or elapsed<0 or elapsed>(2 if turn==1 else .2):
                        raise ValueError('Independent replay callback deadline/nonfinite duration')
                    return action
                return observed
            return [wrap(actor,seat) for seat,actor in enumerate(actors)],namespaces
        # This changes no frozen module globals or files. The audited function's
        # exact code/defaults/closure are reused; only its factory lookup in a
        # copied globals dictionary points to the passive timing wrappers.
        original=oversight.audit_game
        namespace=dict(original.__globals__); namespace['make_actors']=tracked_make
        instrumented=types.FunctionType(original.__code__,namespace,original.__name__,original.__defaults__,original.__closure__)
        result=instrumented(task['candidate'],task['fixture'],task['sources'],task['row'],True)
        if (result['callbacks_regenerated']!=320 or tracker['attempted']!=320 or tracker['returned']!=320
                or tracker['attempts_by_seat']!=[80]*4 or tracker['returns_by_seat']!=[80]*4):
            raise ValueError('Independent actual actor replay coverage incomplete')
        if source_pins()!=task['source_sha256']: raise ValueError('Audit source changed after replay')
        _entry(task['candidate'])
        for source in task['sources'].values(): _entry(source)
        return dict(base,ok=True,all_actors_regenerated=True,callbacks_regenerated=result['callbacks_regenerated'],
            public_memory_oracles=result['public_memory_oracles'],dual_referee_physical_turns=len(task['row']['actions']),
            tracker=tracker,elapsed_s=time.perf_counter()-started,
            instrumentation='Exact frozen audit code/defaults/closure; copied globals changes only make_actors to passive original-action timing wrappers')
    except BaseException as error:
        return frozen._safe_evidence(dict(base,ok=False,error_type=type(error).__name__,message=str(error),tracker=tracker,
            validated_complete_callbacks_unknown=True,elapsed_s=time.perf_counter()-started))


def _audit_executor(workers):
    return ProcessPoolExecutor(max_workers=workers,mp_context=multiprocessing.get_context('spawn'))


def _projection_truth(projection,state,lane,seat):
    if projection is None: return 0
    if (projection['progress']!=state['prog'][lane][seat] or projection['scores'][1:]!=state['score'][lane]
            or projection['inference_failures']!=0
            or any(state['cd'][lane][i] not in projection['cooldown_possible'][str(i+1)] for i in range(4))):
        raise ValueError('Inferred actor public memory disagrees with checked GPU/CPU observer truth')
    return 1


def _append(handle,value):
    handle.write(canonical(value)+b'\n'); handle.flush(); os.fsync(handle.fileno())


def _snapshot_sources(output,pins,registration):
    """Archive exact bytes once per digest; metadata never substitutes for code."""
    folder=output/'sources'; folder.mkdir(exist_ok=False); artifacts={}
    def save(path,expected):
        body=Path(path).read_bytes()
        if sha(body)!=expected: raise ValueError('Source changed while creating immutable byte snapshot')
        relative='sources/'+expected+'.py'
        if expected not in artifacts:
            with (output/relative).open('xb') as handle:
                handle.write(body); handle.flush(); os.fsync(handle.fileno())
            artifacts[expected]=relative
        return dict(sha256=expected,artifact=relative)
    runtime={name:save(ROOT/name,digest) for name,digest in pins.items()}
    actors=[]
    for entry in registration['candidates']+list(registration['sources'].values()):
        actors.append(dict(original_path=entry['path'],**save(entry['path'],entry['sha256'])))
    manifest=dict(format=FORMAT,runtime=runtime,actors=actors,artifacts=artifacts,
                  scope='Exact guarded runtime/actor source bytes, content-addressed; not executable path rewriting')
    frozen._seal(output/'source_snapshot.json',manifest)
    return manifest


def _verify_source_snapshot(output,manifest):
    for digest,relative in manifest['artifacts'].items():
        if (type(digest) is not str or len(digest)!=64 or any(c not in '0123456789abcdef' for c in digest)
                or relative!='sources/'+digest+'.py'):
            raise ValueError('Invalid content-addressed source artifact path')
        resolved=(output/relative).resolve()
        if not resolved.is_relative_to(output.resolve()): raise ValueError('Archived source artifact escaped output')
        if sha(resolved.read_bytes())!=digest: raise ValueError('Archived immutable source bytes changed')
    body=(output/'source_snapshot.json').read_bytes()
    if sha(body)!=(output/'source_snapshot.sha256').read_text().strip():
        raise ValueError('Archived source manifest seal changed')
    if canonical(oversight.strict_loads(body))!=canonical(manifest):
        raise ValueError('Archived source manifest changed')


def _generate_batch(snapshot,fixtures,candidates,actor_pool,batch_directory,device,pins,partial):
    ids=[f['id'] for f in fixtures]; began=time.perf_counter(); lanes=len(fixtures)
    timing=[[dict(calls=0,first_ms=0.0,regular_max_ms=0.0,max_ms=0.0,total_ms=0.0) for _ in range(4)] for _ in fixtures]
    proofs=[dict(callbacks_regenerated=0,callbacks_returned=0,callbacks_completed=0,public_memory_oracles=0,
                 gpu_reference_state_comparisons=0,gpu_official_state_comparisons=0,physical_turns=0) for _ in fixtures]
    totals=dict(actor_initialize_s=0.0,actor_decide_wall_s=0.0,actor_callback_sum_s=0.0,public_envelope_s=0.0,
                gpu_setup_wall_s=0.0,gpu_step_wall_s=0.0,gpu_public_download_wall_s=0.0,gpu_state_download_wall_s=0.0,
                referee_step_and_checks_s=0.0,projection_truth_s=0.0,turn_evidence_s=0.0,actor_reset_s=0.0)
    tapes=[[] for _ in fixtures]; partial.update(turn=0,actions=tapes,proofs=proofs,timing=timing,pending_actions=None)
    batch_directory.mkdir(exist_ok=False); frozen._seal(batch_directory/'registration.json',snapshot)
    actor_snapshot=dict(guards=snapshot['guards'],candidates=[_entry(c) for c in snapshot['candidates']],
                        sources={k:_entry(v) for k,v in snapshot['sources'].items()},fixtures=fixtures)
    moment=time.perf_counter(); actor_pool.initialize_batch(actor_snapshot,ids); totals['actor_initialize_s']=time.perf_counter()-moment
    moment=time.perf_counter(); physics=_physics(fixtures,device); totals['gpu_setup_wall_s']=time.perf_counter()-moment
    refs=[engine.Game(base=f['base'],start_token=f['token'],rules={'catch_requires_stay':True}) for f in fixtures]
    shadows=[oversight.referee.Referee(f['base'],start_token=f['token'],rules={'catch_requires_stay':True}) for f in fixtures]
    state_hashes=[hashlib.sha256() for _ in fixtures]; public_hashes=[hashlib.sha256() for _ in fixtures]
    public,state=frozen._snapshots(physics,totals); moment=time.perf_counter()
    frozen._compare(public,state,refs,shadows,proofs,state_hashes,public_hashes)
    totals['referee_step_and_checks_s']+=time.perf_counter()-moment
    with (batch_directory/'turns.jsonl').open('xb') as stream:
        for turn in range(1,81):
            partial['turn']=turn
            if state['turn']!=turn: raise ValueError('Skipped/repeated physical actor turn')
            moment=time.perf_counter()
            compact=dict(turn=turn,lanes=[dict(lane_id=key,board=public['board'][i],legal=public['legal'][i],
                priority=[public['tokens'][i]==seat+1 for seat in range(4)]) for i,key in enumerate(ids)])
            totals['public_envelope_s']+=time.perf_counter()-moment
            moment=time.perf_counter(); decision=actor_pool.decide_turn(compact); totals['actor_decide_wall_s']+=time.perf_counter()-moment
            if decision['turn']!=turn or [r['lane_id'] for r in decision['lanes']]!=ids:
                raise ValueError('Fast actor pool returned a foreign/reordered response')
            joint=[r['actions'] for r in decision['lanes']]; partial['pending_actions']=joint
            moment=time.perf_counter()
            for lane,response in enumerate(decision['lanes']):
                proof=response['proof']
                if any(type(proof.get(k)) is not int or proof[k]!=4 for k in ('attempted_callbacks','returned_callbacks','completed_callbacks')):
                    raise ValueError('Original callback chunk coverage incomplete')
                for key in ('attempts_total','returned_total','completed_total'):
                    if type(proof.get(key)) is not list or len(proof[key])!=4 or any(type(v) is not int or v!=turn for v in proof[key]):
                        raise ValueError('Original cumulative callback coverage inconsistent')
                if len(response['actions'])!=4 or len(proof['timing'])!=4 or len(proof['memory'])!=4:
                    raise ValueError('Missing action/timing/public memory seat')
                proofs[lane]['callbacks_regenerated']+=proof['attempted_callbacks']
                proofs[lane]['callbacks_returned']+=proof['returned_callbacks']; proofs[lane]['callbacks_completed']+=proof['completed_callbacks']
                for seat,(action,call,projection) in enumerate(zip(response['actions'],proof['timing'],proof['memory'])):
                    if (type(action) is not str or action not in refs[lane].legal(seat) or action not in shadows[lane].legal(seat)
                            or not public['legal'][lane][seat][engine.ACTIONS.index(action)]):
                        raise ValueError('Original action illegal in GPU or a CPU observer')
                    ms=call['callback_ms']
                    if (call['seat']!=seat or not all(call[k] is True for k in ('attempted','returned','completed')) or call['fallback'] is not False
                            or type(ms) not in (int,float) or not math.isfinite(ms) or ms<0 or ms>(2000 if turn==1 else 200)):
                        raise ValueError('Invalid/late/fallback original callback receipt')
                    rec=timing[lane][seat]; rec['calls']+=1; rec['total_ms']+=ms; rec['max_ms']=max(rec['max_ms'],ms)
                    if turn==1: rec['first_ms']=ms
                    else: rec['regular_max_ms']=max(rec['regular_max_ms'],ms)
                    totals['actor_callback_sum_s']+=ms/1000
                    proofs[lane]['public_memory_oracles']+=_projection_truth(projection,state,lane,seat)
            totals['projection_truth_s']+=time.perf_counter()-moment
            moment=time.perf_counter(); physics.step([[engine.ACTIONS.index(a) for a in row] for row in joint])
            totals['gpu_step_wall_s']+=time.perf_counter()-moment
            public,state=frozen._snapshots(physics,totals); moment=time.perf_counter()
            for lane,row in enumerate(joint): refs[lane].step(row); shadows[lane].step(row)
            frozen._compare(public,state,refs,shadows,proofs,state_hashes,public_hashes)
            totals['referee_step_and_checks_s']+=time.perf_counter()-moment
            for lane,row in enumerate(joint): tapes[lane].append(list(row)); proofs[lane]['physical_turns']+=1
            moment=time.perf_counter()
            _append(stream,dict(turn=turn,actions=joint,actor_proofs=[r['proof'] for r in decision['lanes']],
                gpu_state_chain_sha256=[h.hexdigest() for h in state_hashes],gpu_public_chain_sha256=[h.hexdigest() for h in public_hashes]))
            totals['turn_evidence_s']+=time.perf_counter()-moment; partial['pending_actions']=None
    if source_pins()!=pins: raise ValueError('Original runtime changed after full batch')
    frozen._registration(snapshot,ids)
    rows=[]; snapshot_sha=sha((batch_directory/'registration.json').read_bytes())
    for lane,f in enumerate(fixtures):
        p=proofs[lane]
        if (state['turn']!=81 or not refs[lane].over() or not shadows[lane].over()
                or any(p[k]!=320 for k in ('callbacks_regenerated','callbacks_returned','callbacks_completed'))
                or p['physical_turns']!=80 or p['gpu_reference_state_comparisons']!=81 or p['gpu_official_state_comparisons']!=81):
            raise ValueError('Original game terminal/callback/physical coverage incomplete')
        scores=list(state['score'][lane]); seat=f['seat']; points=sum(1 if scores[seat]>v else .5 if scores[seat]==v else 0 for i,v in enumerate(scores) if i!=seat)
        rows.append(dict(candidate=f['candidate'],fixture=f['id'],map_id=f['map_id'],focal_seat=seat,field=f['field'],
            scores=scores,focal_pw=points,focal_score=scores[seat],opponent_ids=[s['id'] for s in f['opponents']],
            actions=tapes[lane],faults=[],timing=timing[lane],elapsed_s=time.perf_counter()-began,
            proof=dict(p,source_closure_sha256=sha(canonical(pins)),registration_snapshot_sha256=snapshot_sha,
                gpu_state_chain_sha256=state_hashes[lane].hexdigest(),gpu_public_chain_sha256=public_hashes[lane].hexdigest(),
                actor_backend='Persistent local CPU exact Python actors',physics_backend='local CUDA',
                input_contract='Namedtuple Cell6/View4; nested exact builtin tuples/scalars; shared immutable board per lane',
                primary_games=0,study_games=0,completed_per_game_bmcts_audits=0)))
    moment=time.perf_counter(); actor_pool.reset(); totals['actor_reset_s']=time.perf_counter()-moment
    with (batch_directory/'originals.jsonl').open('xb') as handle:
        for row in rows: _append(handle,row)
    frozen._seal(batch_directory/'original_summary.json',dict(format=FORMAT,games=len(rows),timings=totals,
        physics_metadata=physics.metadata,physics_timings=physics.timings,source_sha256=pins,
        originals_sha256=sha((batch_directory/'originals.jsonl').read_bytes()),turns_sha256=sha((batch_directory/'turns.jsonl').read_bytes()),
        elapsed_s=time.perf_counter()-began,primary_games=0,study_games=0,independent_audits='pending'))
    return rows,dict(timings=totals,elapsed_s=time.perf_counter()-began,snapshot_sha256=snapshot_sha)


def run_fixtures(registration,fixture_ids,output,batch_size=256,workers=4,audit_workers=4,device='cuda'):
    """Generate ordered originals and ALL full audits, with zero admission."""
    started=time.perf_counter(); output=Path(output).resolve()
    if output.exists(): raise ValueError('Fresh output required; no resume, overwrite or automatic retry')
    if (type(batch_size) is not int or batch_size<1 or type(workers) is not int or not 1<=workers<=8
            or type(audit_workers) is not int or not 1<=audit_workers<=4
            or type(device) is not str or not (device=='cuda' or device.startswith('cuda:'))):
        raise ValueError('Positive batch size,1..8 local actor workers,1..4 local audit workers and CUDA required')
    pins=source_pins(); snapshot,fixtures,candidates=frozen._registration(registration,fixture_ids)
    output.mkdir(parents=True,exist_ok=False); (output/'.execution_claim').mkdir()
    actor_pool=None; audit_pool=None; pending=deque(); all_rows=[]; all_audits=[]; batch_metrics=[]
    partial=dict(batch=None,phase='setup'); max_pending=0; audit_wait_s=0.0; audit_stream=None; original_stream=None
    def drain(item,raise_failure=True):
        nonlocal audit_wait_s
        responses=[]; moment=time.perf_counter()
        for row,task,future in zip(item['rows'],item['tasks'],item['futures']):
            try: response=future.result()
            except BaseException as error:
                response=dict(ok=False,fixture=row['fixture'],row_sha256=sha(canonical(row)),
                    error_type=type(error).__name__,message=str(error),actual_attempt_counts_unknown=True)
            if type(response) is not dict or type(response.get('ok')) is not bool:
                response=dict(ok=False,fixture=row['fixture'],row_sha256=sha(canonical(row)),error_type='InvalidAuditResponse',message='Audit must return a typed plain-data outcome')
            if response.get('fixture')!=row['fixture'] or response.get('row_sha256')!=sha(canonical(row)):
                response=dict(ok=False,fixture=row['fixture'],row_sha256=sha(canonical(row)),error_type='ForeignAuditResponse',message='Audit identity/row bytes mismatch')
            if response.get('ok') is True:
                tracker=response.get('tracker',{})
                if type(tracker) is not dict: tracker={}
                valid=(response.get('candidate')==row['candidate'] and response.get('callbacks_regenerated')==320
                    and type(response.get('callbacks_regenerated')) is int
                    and response.get('all_actors_regenerated') is True and response.get('dual_referee_physical_turns')==80
                    and type(response.get('dual_referee_physical_turns')) is int
                    and response.get('source_closure_sha256')==sha(canonical(pins))
                    and response.get('audit_source_sha256')==oversight.sha((ROOT/'evolution/oversight.py').read_bytes())
                    and response.get('fixture_sha256')==sha(canonical(task['fixture']))
                    and type(response.get('batch_index')) is int and response['batch_index']==item['index']
                    and type(response.get('public_memory_oracles')) is int and 0<=response['public_memory_oracles']<=320
                    and tracker.get('attempted')==320 and tracker.get('returned')==320
                    and type(tracker.get('attempted')) is int and type(tracker.get('returned')) is int
                    and tracker.get('attempts_by_seat')==[80]*4 and tracker.get('returns_by_seat')==[80]*4)
                valid=valid and all(type(tracker.get(k)) is list and len(tracker[k])==4
                    and all(type(v) is int and v==80 for v in tracker[k]) for k in ('attempts_by_seat','returns_by_seat'))
                timings=tracker.get('timing')
                valid=valid and type(timings) is list and len(timings)==4
                if valid:
                    for timing in timings:
                        if (type(timing) is not dict or type(timing.get('calls')) is not int or timing['calls']!=80
                                or any(type(timing.get(k)) not in (int,float) or not math.isfinite(timing[k]) or timing[k]<0
                                       for k in ('first_ms','regular_max_ms','max_ms','total_ms'))):
                            valid=False; break
                        if (timing['first_ms']>2000 or timing['regular_max_ms']>200
                                or timing['max_ms']!=max(timing['first_ms'],timing['regular_max_ms'])
                                or not timing['max_ms']<=timing['total_ms']<=timing['first_ms']+79*timing['regular_max_ms']+1e-6):
                            valid=False; break
                    if any(type(response.get(k)) is not int or response[k]!=0 for k in ('primary_games','study_games','completed_per_game_bmcts_audits')):
                        valid=False
                if not valid:
                    response=dict(ok=False,fixture=row['fixture'],row_sha256=sha(canonical(row)),
                        error_type='IncompleteAuditProof',message='Full independent replay/source/callback proof missing or inconsistent',reported_response=response)
            _append(audit_stream,response); responses.append(response)
            if response['ok'] is True: all_audits.append(response)
        audit_wait_s+=time.perf_counter()-moment
        frozen._seal(item['directory']/'audit_summary.json',dict(format=FORMAT,batch=item['index'],responses=responses,
            all_passed=all(r['ok'] is True for r in responses),primary_games=0,study_games=0,completed_per_game_bmcts_audits=0))
        if raise_failure and any(r['ok'] is not True for r in responses): raise AuditFailure(responses)
    try:
        partial['phase']='source_snapshot'
        archived_sources=_snapshot_sources(output,pins,snapshot)
        frozen._seal(output/'execution_started.json',dict(format=FORMAT,fixture_ids=list(fixture_ids),source_sha256=pins,
            source_schedule=snapshot['local_cuda_source_schedule'],batch_size=batch_size,workers=workers,audit_workers=audit_workers,
            max_completed_batches_pending_audit=2,cpu_runtime=frozen.runtime_info(),primary_games=0,study_games=0,
            completed_per_game_bmcts_audits=0,admission='none; generic role only'))
        partial['phase']='setup'
        actor_pool=_actors(workers); audit_pool=_audit_executor(audit_workers)
        original_stream=(output/'originals.jsonl').open('xb'); audit_stream=(output/'audits.jsonl').open('xb')
        for start in range(0,len(fixtures),batch_size):
            while len(pending)>=2:
                partial.update(phase='audit_backpressure'); drain(pending.popleft())
            index=start//batch_size; chosen=fixtures[start:start+batch_size]; ids=[f['id'] for f in chosen]
            selected_snapshot,_,_=frozen._registration(snapshot,ids); directory=output/('batch_%05d'%index)
            partial.clear(); partial.update(batch=index,phase='original')
            rows,metrics=_generate_batch(selected_snapshot,chosen,candidates,actor_pool,directory,device,pins,partial)
            all_rows.extend(rows); batch_metrics.append(dict(batch=index,**metrics))
            for row in rows: _append(original_stream,row)
            tasks=[_audit_task(candidates[f['candidate']],f,snapshot['sources'],row,pins,index) for f,row in zip(chosen,rows)]
            futures=[audit_pool.submit(_audit_job,task) for task in tasks]
            pending.append(dict(index=index,rows=rows,tasks=tasks,futures=futures,directory=directory)); max_pending=max(max_pending,len(pending))
        while pending:
            partial.update(phase='audit_completion'); drain(pending.popleft())
        if source_pins()!=pins: raise ValueError('Runtime source changed after pipeline completion')
        frozen._registration(snapshot,fixture_ids)
        _verify_source_snapshot(output,archived_sources)
        indexed={a['fixture']:a for a in all_audits}
        if len(all_rows)!=len(fixture_ids) or len(indexed)!=len(fixture_ids) or set(indexed)!=set(fixture_ids):
            raise ValueError('Full original/independent actor audit coverage incomplete')
        ordered=[indexed[key] for key in fixture_ids]
        summary=dict(format=FORMAT,original_games=len(all_rows),independent_full_game_audits=len(ordered),
            original_callbacks=sum(r['proof']['callbacks_regenerated'] for r in all_rows),
            independently_regenerated_callbacks=sum(a['callbacks_regenerated'] for a in ordered),
            original_gpu_physical_turns=sum(r['proof']['physical_turns'] for r in all_rows),
            independent_dual_referee_turns=sum(a['dual_referee_physical_turns'] for a in ordered),
            max_completed_batches_pending_audit_observed=max_pending,audit_wait_wall_s=audit_wait_s,
            batch_metrics=batch_metrics,wall_before_final_publication_s=time.perf_counter()-started,source_sha256=pins,
            originals_sha256=sha((output/'originals.jsonl').read_bytes()),audits_sha256=sha((output/'audits.jsonl').read_bytes()),
            source_snapshot_sha256=sha((output/'source_snapshot.json').read_bytes()),
            primary_games=0,study_games=0,completed_per_game_bmcts_audits=0,admission='none; root authority must independently admit later',
            limits=['Exact original policies run on local CPUs; CUDA advances physical turns.',
                    'Every original state/clock/income/legal set is checked against both CPU referees, opening through terminal.',
                    'Every original receives all320 fresh independent actor callbacks and both CPU-referee replays; no sampling.',
                    'No speedup or CUDA integration qualification is established before a separate measured canonical-control benchmark.'])
        frozen._seal(output/'summary.json',summary)
        return dict(rows=all_rows,audits=ordered,summary=summary)
    except BaseException as error:
        # Complete and retain already dispatched audit work; never resubmit it.
        for item in list(pending):
            try: drain(item,raise_failure=False)
            except BaseException: pass
        pending.clear()
        payload=dict(format=FORMAT,exception_type=type(error).__name__,message=str(error),partial=partial,
            fast_actor_evidence=getattr(actor_pool,'evidence',None),completed_originals=len(all_rows),
            completed_successful_audits=len(all_audits),primary_games=0,study_games=0,completed_per_game_bmcts_audits=0,
            status='failed preserve all evidence no retry or admission')
        error.deadline_runner_partial=payload
        try: frozen._seal(output/'error.json',frozen._safe_evidence(payload))
        except BaseException as secondary: error.deadline_runner_evidence_failure=type(secondary).__name__
        raise
    finally:
        if original_stream is not None: original_stream.close()
        if audit_stream is not None: audit_stream.close()
        if actor_pool is not None:
            try: actor_pool.close()
            except BaseException: pass
        if audit_pool is not None: audit_pool.shutdown(wait=True,cancel_futures=False)
