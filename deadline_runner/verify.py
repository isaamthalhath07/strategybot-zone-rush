"""Read-only durable execution verification; no actors, physics or CUDA run."""
from collections import Counter
import math
from pathlib import Path

from . import runner


def read_sealed(path):
    path=Path(path); body=path.read_bytes()
    if runner.sha(body)!=path.with_suffix('.sha256').read_text().strip(): raise ValueError('Artifact seal mismatch: '+path.name)
    return runner.oversight.strict_loads(body)


def read_lines(path):
    body=Path(path).read_bytes()
    if body and not body.endswith(b'\n'): raise ValueError('Incomplete streamed record: '+Path(path).name)
    return [runner.oversight.strict_loads(line) for line in body.splitlines()]


def _zero(record):
    if any(type(record.get(k)) is not int or record[k]!=0 for k in ('primary_games','study_games','completed_per_game_bmcts_audits')):
        raise ValueError('Generic execution cannot award admission credit')


def _timing(record):
    if (type(record) is not dict or type(record.get('calls')) is not int or record['calls']!=80
            or any(type(record.get(k)) not in (int,float) or not math.isfinite(record[k]) or record[k]<0
                   for k in ('first_ms','regular_max_ms','max_ms','total_ms'))
            or record['first_ms']>2000 or record['regular_max_ms']>200
            or record['max_ms']!=max(record['first_ms'],record['regular_max_ms'])
            or not record['max_ms']<=record['total_ms']<=record['first_ms']+79*record['regular_max_ms']+1e-6):
        raise ValueError('Invalid complete callback timing receipt')


def _cuda_metadata(metadata,lanes,pins):
    rules=dict(frozen_stay_counts=False,claim_resets_progress=True,catch_requires_stay=True,
               lost_contest_is_stay=True,home_upgradable=True)
    expected_counts=dict(batch_size=lanes,accepted_batch_steps=80,accepted_branch_turn_events=80*lanes,
        max_turns=80,setup_throwaway_transitions=3,setup_primary_match_credit=0,setup_completed_game_audit_credit=0)
    required={'training_gpu/batch_game.py','search_coach/gpu_batch.py','training_gpu/__init__.py',
              'search_coach/__init__.py','search_coach/belief.py','tests/reference_engine.py','local_cuda_matches/physics.py'}
    if (type(metadata) is not dict or metadata.get('format')!='local-cuda-match-physics/1'
            or metadata.get('cuda_kernel_executed') is not True or type(metadata.get('device')) is not str
            or not metadata['device'].startswith('cuda') or metadata.get('policy_backend')!='External exact CPU actors'
            or any(type(metadata.get(k)) is not int or metadata[k]!=v for k,v in expected_counts.items())
            or metadata.get('rules')!=rules or any(type(v) is not bool for v in metadata['rules'].values())
            or metadata.get('use_graph') is not True
            or type(metadata.get('source_sha256')) is not dict or set(metadata['source_sha256'])!=required
            or any(pins.get(name)!=digest for name,digest in metadata['source_sha256'].items())):
        raise ValueError('Complete canonical CUDA physics proof missing')


def _source_archive(path,pins,registration):
    manifest=read_sealed(path/'source_snapshot.json'); runner._verify_source_snapshot(path,manifest)
    if {name:entry['sha256'] for name,entry in manifest['runtime'].items()}!=pins:
        raise ValueError('Archived runtime source closure changed')
    expected=Counter((entry['path'],entry['sha256']) for entry in registration['candidates']+list(registration['sources'].values()))
    actual=Counter((entry['original_path'],entry['sha256']) for entry in manifest['actors'])
    if actual!=expected: raise ValueError('Archived exact actor sources changed')
    for entry in list(manifest['runtime'].values())+manifest['actors']:
        if manifest['artifacts'].get(entry['sha256'])!=entry['artifact']: raise ValueError('Source manifest reference changed')
    return manifest


def _memory(projection):
    if projection is None: return 0
    if (type(projection) is not dict or set(projection)!={'progress','scores','cooldown_possible','inference_failures'}
            or type(projection['progress']) is not int or projection['progress']<0
            or type(projection['scores']) is not list or len(projection['scores'])!=5
            or any(type(v) is not int or v<0 for v in projection['scores'])
            or type(projection['inference_failures']) is not int or projection['inference_failures']!=0
            or type(projection['cooldown_possible']) is not dict or set(projection['cooldown_possible'])!={'1','2','3','4'}):
        raise ValueError('Malformed supported inferred public-memory projection')
    for values in projection['cooldown_possible'].values():
        if type(values) is not list or not values or values!=sorted(set(values)) or any(type(v) is not int or v not in range(5) for v in values):
            raise ValueError('Malformed inferred cooldown domain')
    return 1


def verify_execution(registration,output_directory):
    """Verify the exact intended cohort and return summary/rows/audits.

    The caller supplies the complete intended registration subset, in execution
    order. This checks durable receipts and bindings without regenerating a
    policy callback or physical state. It is not an admission authority.
    """
    path=Path(output_directory).resolve()
    if (path/'error.json').exists(): raise ValueError('Failed execution cannot be verified complete')
    header=read_sealed(path/'execution_started.json'); summary=read_sealed(path/'summary.json')
    if header.get('format')!=runner.FORMAT or summary.get('format')!=runner.FORMAT:
        raise ValueError('Execution format/role changed')
    ids=[f['id'] for f in registration['fixtures']]
    if header['fixture_ids']!=ids or len(ids)!=len(set(ids)) or not ids:
        raise ValueError('Execution does not cover the exact ordered intended cohort')
    snapshot,fixtures,candidates=runner.frozen._registration(registration,ids)
    pins=runner.source_pins()
    if header['source_sha256']!=pins or summary['source_sha256']!=pins: raise ValueError('Current execution source pins changed')
    if header['source_schedule']!=snapshot['local_cuda_source_schedule']: raise ValueError('Original source schedule provenance changed')
    if (type(header['batch_size']) is not int or header['batch_size']<1 or type(header['workers']) is not int or not 1<=header['workers']<=8
            or type(header['audit_workers']) is not int or not 1<=header['audit_workers']<=4
            or type(header['max_completed_batches_pending_audit']) is not int
            or header['max_completed_batches_pending_audit']!=2): raise ValueError('Execution worker/batch protocol changed')
    current=runner.frozen.runtime_info()
    if any(header['cpu_runtime'][k]!=current[k] for k in ('implementation','python_version','full_python_version')):
        raise ValueError('Qualified CPU Python runtime changed')
    _zero(header); _zero(summary); _source_archive(path,pins,snapshot)
    for key,name in (('originals_sha256','originals.jsonl'),('audits_sha256','audits.jsonl'),('source_snapshot_sha256','source_snapshot.json')):
        if summary[key]!=runner.sha((path/name).read_bytes()): raise ValueError('Root artifact hash mismatch: '+name)
    rows=read_lines(path/'originals.jsonl'); audits=read_lines(path/'audits.jsonl')
    if [r['fixture'] for r in rows]!=ids or [r['fixture'] for r in audits]!=ids: raise ValueError('Incomplete or reordered original/audit records')
    count=len(ids); batch_size=header['batch_size']; expected_batches=(count+batch_size-1)//batch_size
    if {p.name for p in path.glob('batch_*') if p.is_dir()}!={'batch_%05d'%i for i in range(expected_batches)}:
        raise ValueError('Unexpected or omitted batch directory')
    oracle_total=0
    for index,start in enumerate(range(0,count,batch_size)):
        batch_rows=rows[start:start+batch_size]; batch_audits=audits[start:start+batch_size]; chosen=fixtures[start:start+batch_size]
        size=len(chosen); directory=path/('batch_%05d'%index); batch_ids=ids[start:start+batch_size]
        selected,_,_=runner.frozen._registration(snapshot,batch_ids)
        if read_sealed(directory/'registration.json')!=selected: raise ValueError('Exact selected registration snapshot changed')
        original=read_sealed(directory/'original_summary.json'); audited=read_sealed(directory/'audit_summary.json')
        if original.get('format')!=runner.FORMAT or audited.get('format')!=runner.FORMAT:
            raise ValueError('Batch execution format changed')
        if original['source_sha256']!=pins or original['games']!=size: raise ValueError('Original batch source/count mismatch')
        for key,name in (('originals_sha256','originals.jsonl'),('turns_sha256','turns.jsonl')):
            if original[key]!=runner.sha((directory/name).read_bytes()): raise ValueError('Batch artifact hash mismatch: '+name)
        if read_lines(directory/'originals.jsonl')!=batch_rows: raise ValueError('Batch originals differ from root stream')
        if audited['batch']!=index or audited['all_passed'] is not True or audited['responses']!=batch_audits:
            raise ValueError('Complete batch audit responses changed')
        _zero(audited); _cuda_metadata(original['physics_metadata'],size,pins)
        turns=read_lines(directory/'turns.jsonl')
        if [t['turn'] for t in turns]!=list(range(1,81)) or any(type(t['turn']) is not int for t in turns):
            raise ValueError('All eighty ordered physical turns required')
        timing=[[dict(calls=0,total_ms=0.0,max_ms=0.0,first_ms=0.0,regular_max_ms=0.0) for _ in range(4)] for _ in chosen]
        oracles=[0]*size
        for turn,record in enumerate(turns,1):
            if any(len(record[k])!=size for k in ('actions','actor_proofs','gpu_state_chain_sha256','gpu_public_chain_sha256')):
                raise ValueError('Per-turn lane/callback/state coverage changed')
            for lane,(joint,proof) in enumerate(zip(record['actions'],record['actor_proofs'])):
                if joint!=batch_rows[lane]['actions'][turn-1] or len(joint)!=4 or any(type(a) is not str or a not in runner.engine.ACTIONS for a in joint):
                    raise ValueError('Actual streamed action tape changed')
                if any(type(proof.get(k)) is not int or proof[k]!=4 for k in ('attempted_callbacks','returned_callbacks','completed_callbacks')):
                    raise ValueError('Original per-turn actual callback count changed')
                for key in ('attempts_total','returned_total','completed_total'):
                    if type(proof.get(key)) is not list or proof[key]!=[turn]*4 or any(type(v) is not int for v in proof[key]):
                        raise ValueError('Cumulative original callback coverage changed')
                if len(proof['timing'])!=4 or len(proof['memory'])!=4: raise ValueError('Missing callback/public-memory seat')
                for seat,call in enumerate(proof['timing']):
                    ms=call['callback_ms']
                    if (call['seat']!=seat or any(call.get(k) is not True for k in ('attempted','returned','completed'))
                            or call.get('fallback') is not False
                            or type(ms) not in (int,float) or not math.isfinite(ms) or not 0<=ms<=(2000 if turn==1 else 200)):
                        raise ValueError('Original callback deadline/fallback/immutable receipt changed')
                    t=timing[lane][seat]; t['calls']+=1; t['total_ms']+=ms; t['max_ms']=max(t['max_ms'],ms)
                    if turn==1: t['first_ms']=ms
                    else: t['regular_max_ms']=max(t['regular_max_ms'],ms)
                    oracles[lane]+=_memory(proof['memory'][seat])
        for lane,(row,audit,fixture) in enumerate(zip(batch_rows,batch_audits,chosen)):
            if row['timing']!=timing[lane] or len(row['actions'])!=80 or row['faults']!=[]: raise ValueError('Original timing/tape/fault coverage changed')
            for t in row['timing']: _timing(t)
            if (row['candidate']!=fixture['candidate'] or row['map_id']!=fixture['map_id'] or row['focal_seat']!=fixture['seat']
                    or row['field']!=fixture['field'] or row['opponent_ids']!=[s['id'] for s in fixture['opponents']]
                    or type(row['scores']) is not list or len(row['scores'])!=4 or any(type(v) is not int for v in row['scores'])):
                raise ValueError('Original recipe/score identity changed')
            seat=fixture['seat']; scores=row['scores']; points=sum(1 if scores[seat]>v else .5 if scores[seat]==v else 0 for s,v in enumerate(scores) if s!=seat)
            if row['focal_score']!=scores[seat] or row['focal_pw']!=points: raise ValueError('Official terminal pairwise arithmetic changed')
            p=row['proof']; final=turns[-1]; _zero(p)
            if (any(type(p[k]) is not int or p[k]!=320 for k in ('callbacks_regenerated','callbacks_returned','callbacks_completed'))
                    or any(type(p[k]) is not int for k in ('physical_turns','gpu_reference_state_comparisons','gpu_official_state_comparisons','public_memory_oracles'))
                    or p['physical_turns']!=80 or p['gpu_reference_state_comparisons']!=81 or p['gpu_official_state_comparisons']!=81
                    or p['public_memory_oracles']!=oracles[lane] or p['gpu_state_chain_sha256']!=final['gpu_state_chain_sha256'][lane]
                    or p['gpu_public_chain_sha256']!=final['gpu_public_chain_sha256'][lane]
                    or p['registration_snapshot_sha256']!=runner.sha((directory/'registration.json').read_bytes())
                    or p['source_closure_sha256']!=runner.sha(runner.canonical(pins))
                    or p.get('input_contract')!='Namedtuple Cell6/View4; nested exact builtin tuples/scalars; shared immutable board per lane'):
                raise ValueError('Original complete state/callback/source binding changed')
            task=runner._audit_task(candidates[row['candidate']],fixture,snapshot['sources'],row,pins,index)
            tracker=audit['tracker']; _zero(audit)
            if (audit.get('ok') is not True or audit.get('all_actors_regenerated') is not True
                    or audit['candidate']!=row['candidate'] or type(audit['batch_index']) is not int or audit['batch_index']!=index
                    or type(audit['callbacks_regenerated']) is not int or audit['callbacks_regenerated']!=320
                    or type(audit['dual_referee_physical_turns']) is not int
                    or audit['dual_referee_physical_turns']!=80 or audit['row_sha256']!=runner.sha(runner.canonical(row))
                    or audit['fixture_sha256']!=runner.sha(runner.canonical(task['fixture']))
                    or audit['source_closure_sha256']!=runner.sha(runner.canonical(pins))
                    or audit['audit_source_sha256']!=runner.sha((runner.ROOT/'evolution/oversight.py').read_bytes())
                    or type(tracker['attempted']) is not int or tracker['attempted']!=320
                    or type(tracker['returned']) is not int or tracker['returned']!=320
                    or any(tracker[k]!=[80]*4 or any(type(v) is not int for v in tracker[k]) for k in ('attempts_by_seat','returns_by_seat'))
                    or type(audit['public_memory_oracles']) is not int or audit['public_memory_oracles']!=oracles[lane]):
                raise ValueError('Full independent audit source/callback binding changed')
            if len(tracker['timing'])!=4: raise ValueError('Missing independent timing seat')
            for t in tracker['timing']: _timing(t)
            oracle_total+=oracles[lane]
    if (any(type(summary[k]) is not int for k in ('original_games','independent_full_game_audits','original_callbacks',
             'independently_regenerated_callbacks','original_gpu_physical_turns','independent_dual_referee_turns'))
            or summary['original_games']!=count or summary['independent_full_game_audits']!=count
            or summary['original_callbacks']!=count*320 or summary['independently_regenerated_callbacks']!=count*320
            or summary['original_gpu_physical_turns']!=count*80 or summary['independent_dual_referee_turns']!=count*80
            or type(summary['max_completed_batches_pending_audit_observed']) is not int
            or not 1<=summary['max_completed_batches_pending_audit_observed']<=2):
        raise ValueError('Complete pipeline aggregate coverage changed')
    return dict(summary=summary,rows=rows,audits=audits,
                verification=dict(source_sha256=pins,verifier_sha256=runner.sha(Path(__file__).read_bytes()),
                    original_games=count,full_actor_audits=count,public_memory_projections_checked=oracle_total,
                    callback_or_physics_reruns=0,admission='none; read-only durable verification'))
