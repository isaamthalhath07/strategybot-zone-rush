"""CPU-only closed-loop replicas of eight already known canonical controls.

Two fixed repeats, serial then four-worker pool. Never opens a registry or key,
uses CUDA, creates fresh study cases or changes the active frozen CUDA driver.
Only the root operator may launch the real known-eight run after review.
"""
import argparse
from collections import Counter
import copy
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import sys
import time

from evolution import oversight
from tests import reference_engine as engine
from .pool import ActorPool,canonical,immutable,wire_view,_projection,source_pins as pool_pins

ROOT=Path(__file__).resolve().parents[1]
KNOWN=ROOT/'.cache/local_cuda/qualification_gold_002'
OUTPUT=ROOT/'.cache/local_policy_pool/known8_001'
FORMAT='known-eight-cpu-policy-pool-qualification-benchmark/1'
REPEATS=2
PINNED_KNOWN={'registration.json':'8dce44596dd69a2958ead21030febd09ae485bf2f45069ec80f17d03ec319977',
              'games.jsonl':'feeb27b8585d73ed3cd3d4c3c0634025d024a941c3aec237491816fbf4f574d4'}
BEHAVIOR=('candidate','fixture','map_id','focal_seat','field','scores','focal_pw','focal_score','opponent_ids','actions','faults')


def sha(body): return hashlib.sha256(body).hexdigest()


def _json_new(path,value):
    body=canonical(value)+b'\n'
    with Path(path).open('xb') as handle:
        handle.write(body); handle.flush(); os.fsync(handle.fileno())
    return sha(body)


def source_pins():
    pins=pool_pins()
    for relative in ('local_policy_pool/benchmark.py','tests/reference_engine.py','simulator/vendor_harness/referee.py'):
        pins[relative]=sha((ROOT/relative).read_bytes())
    if pins['tests/reference_engine.py']!=oversight.ENGINE_SHA or pins['simulator/vendor_harness/referee.py']!=oversight.REFEREE_SHA:
        raise ValueError('Frozen independent CPU referee source changed')
    return pins


def _load_known():
    bodies={name:(KNOWN/name).read_bytes() for name in PINNED_KNOWN}
    if any(sha(bodies[name])!=digest for name,digest in PINNED_KNOWN.items()):
        raise ValueError('Exact known-eight canonical input bytes changed')
    registration=oversight.strict_loads(bodies['registration.json'])
    rows=[oversight.strict_loads(line) for line in bodies['games.jsonl'].splitlines()]
    if len(rows)!=8 or len(registration['fixtures'])!=8 or len({r['fixture'] for r in rows})!=8:
        raise ValueError('Exactly the eight fixed canonical controls are required')
    if {r['fixture'] for r in rows}!={f['id'] for f in registration['fixtures']}:
        raise ValueError('Known control rows and source fixture IDs disagree')
    return registration,rows,dict(PINNED_KNOWN)


def _guards(registration):
    for path,digest in registration['guards'].items():
        if sha(Path(path).read_bytes())!=digest: raise ValueError('Registered runtime source changed')
    for entry in registration['candidates']+list(registration['sources'].values()):
        if sha(Path(entry['path']).read_bytes())!=entry['sha256']: raise ValueError('Exact actor source changed')


def _wire(view):
    return dict(board=[[[c.occupant,c.owner,c.is_upgraded,c.is_home,c.is_frozen,c.base_points] for c in row] for row in view.board],
                bot_id=view.bot_id,is_priority_token=view.is_priority_token,legal_actions=list(view.legal_actions))


def _truth(projection,game,seat):
    if projection is None: return 0
    if (projection['progress']!=game.prog[seat] or projection['scores'][1:]!=game.score
            or projection['inference_failures']!=0
            or any(game.cd[i] not in projection['cooldown_possible'][str(i+1)] for i in range(4))):
        raise ValueError('Inferred actor public-memory projection lost observer-consistent truth')
    return 1


def _serial_decide(actors,namespaces,envelope,counters):
    views=[[immutable(wire_view(v,s)) for s,v in enumerate(row['views'])] for row in envelope['lanes']]
    joints=[]; proofs=[]
    for lane,row in enumerate(views):
        joint=[]; items=[]
        for seat,view in enumerate(row):
            counters[lane]['attempts'][seat]+=1; before=oversight.signature(view); began=time.perf_counter()
            action=actors[lane][seat](view); elapsed=time.perf_counter()-began
            counters[lane]['returned'][seat]+=1
            if not math.isfinite(elapsed) or elapsed<0 or elapsed>(2 if envelope['turn']==1 else .2):
                raise ValueError('Serial actor callback deadline/nonfinite duration')
            if oversight.signature(view)!=before or type(action) is not str or action not in view.legal_actions:
                raise ValueError('Serial actor mutation/illegal decision')
            projection=_projection(namespaces[lane][seat],seat)
            counters[lane]['completed'][seat]+=1; joint.append(action)
            items.append(dict(seat=seat,callback_ms=elapsed*1000,input_unchanged=True,fallback=False,
                              public_memory_projection=projection))
        joints.append(joint); proofs.append(dict(lane_id=envelope['lanes'][lane]['lane_id'],seats=items))
    return dict(actions=joints,proofs=proofs)


def _replica(registration,expected,arm,repeat,output,pool,partial):
    began=time.perf_counter(); ids=[row['fixture'] for row in expected]
    fixtures_by_id={f['id']:f for f in registration['fixtures']}; fixtures=[fixtures_by_id[key] for key in ids]
    candidates={c['sha256']:c for c in registration['candidates']}
    stats=dict(arm=arm,repeat=repeat,phase='cold' if repeat==0 else 'warm-reset',
        initialize_batch_s=0.0,wire_conversion_public_checks_s=0.0,decide_wall_s=0.0,
        actor_callback_sum_s=0.0,parent_projection_truth_checks_s=0.0,referee_step_checks_s=0.0,
        canonical_comparison_s=0.0,turn_evidence_write_s=0.0,final_row_evidence_write_s=0.0,
        observer_state_comparisons=0,public_memory_oracles=0)
    counters=[dict(attempts=[0]*4,returned=[0]*4,completed=[0]*4) for _ in ids]
    partial.update(arm=arm,repeat=repeat,turn=0,counters=counters,actions=[[] for _ in ids])
    started=time.perf_counter()
    if arm=='pool':
        setup=pool.initialize_batch(registration,ids); actors=namespaces=None
        stats['worker_pids']=[r['pid'] for r in setup['responses']]
    else:
        made=[oversight.make_actors(candidates[f['candidate']],f,registration['sources']) for f in fixtures]
        actors=[m[0] for m in made]; namespaces=[m[1] for m in made]
    stats['initialize_batch_s']=time.perf_counter()-started
    games=[engine.Game(base=f['base'],start_token=f['token'],rules={'catch_requires_stay':True}) for f in fixtures]
    shadows=[oversight.referee.Referee(f['base'],start_token=f['token'],rules={'catch_requires_stay':True}) for f in fixtures]
    state_hashes=[hashlib.sha256() for _ in ids]
    started=time.perf_counter()
    for game,shadow in zip(games,shadows): oversight.state_equal(game,shadow); stats['observer_state_comparisons']+=1
    stats['referee_step_checks_s']+=time.perf_counter()-started
    work_started=time.perf_counter()
    with (output/('%s_turns_%d.jsonl'%(arm,repeat))).open('xb') as journal:
        for turn in range(1,81):
            partial['turn']=turn; started=time.perf_counter()
            envelope=dict(turn=turn,lanes=[dict(lane_id=key,views=[_wire(v) for v in game.views()]) for key,game in zip(ids,games)])
            # Both arms pay the same parent wire validation; pooled dispatch
            # additionally measures its complete IPC/worker validation path.
            for lane in envelope['lanes']:
                for seat,view in enumerate(lane['views']): wire_view(view,seat)
            stats['wire_conversion_public_checks_s']+=time.perf_counter()-started
            started=time.perf_counter()
            decision=pool.decide_turn(envelope) if arm=='pool' else _serial_decide(actors,namespaces,envelope,counters)
            stats['decide_wall_s']+=time.perf_counter()-started
            if arm=='pool':
                for lane,proof in enumerate(decision['proofs']):
                    counters[lane].update(attempts=proof['attempts_total'],returned=proof['returned_total'],completed=proof['completed_total'])
            partial['pending_actions']=decision['actions']
            started=time.perf_counter()
            for lane,(joint,proof,game,shadow) in enumerate(zip(decision['actions'],decision['proofs'],games,shadows)):
                if len(joint)!=4 or any(a not in game.legal(seat) or a not in shadow.legal(seat) for seat,a in enumerate(joint)):
                    raise ValueError('Decision illegal in an independent CPU observer')
                for seat,item in enumerate(proof['seats']):
                    stats['public_memory_oracles']+=_truth(item['public_memory_projection'],game,seat)
                    stats['actor_callback_sum_s']+=item['callback_ms']/1000
            stats['parent_projection_truth_checks_s']+=time.perf_counter()-started
            started=time.perf_counter()
            for lane,joint in enumerate(decision['actions']):
                if joint!=expected[lane]['actions'][turn-1]: raise ValueError('Entire canonical known control action tape differs')
            stats['canonical_comparison_s']+=time.perf_counter()-started
            started=time.perf_counter()
            for lane,(joint,game,shadow) in enumerate(zip(decision['actions'],games,shadows)):
                game.step(joint); shadow.step(joint); oversight.state_equal(game,shadow)
                stats['observer_state_comparisons']+=1; partial['actions'][lane].append(list(joint))
                state_hashes[lane].update(canonical(dict(turn=game.turn,**{name:getattr(game,name) for name in
                    ('base','owner','upg','home','pos','frozen','cd','prog','score','income','token')})))
            stats['referee_step_checks_s']+=time.perf_counter()-started
            started=time.perf_counter()
            journal.write(canonical(dict(turn=turn,actions=decision['actions'],proofs=decision['proofs'],
                                         observer_state_chain_sha256=[h.hexdigest() for h in state_hashes]))+b'\n')
            journal.flush(); os.fsync(journal.fileno()); stats['turn_evidence_write_s']+=time.perf_counter()-started
            partial['pending_actions']=None
    rows=[]; started=time.perf_counter()
    for lane,(fixture,game,canonical_row) in enumerate(zip(fixtures,games,expected)):
        seat=fixture['seat']; scores=list(game.score)
        points=sum(1 if scores[seat]>v else .5 if scores[seat]==v else 0 for i,v in enumerate(scores) if i!=seat)
        row=dict(candidate=fixture['candidate'],fixture=fixture['id'],map_id=fixture['map_id'],focal_seat=seat,
            field=fixture['field'],scores=scores,focal_pw=points,focal_score=scores[seat],
            opponent_ids=[s['id'] for s in fixture['opponents']],actions=partial['actions'][lane],faults=[])
        if any(row[key]!=canonical_row[key] for key in BEHAVIOR): raise ValueError('Canonical full behavior/score mismatch')
        if any(counters[lane][kind]!=[80]*4 for kind in ('attempts','returned','completed')):
            raise ValueError('Not all320actual callbacks completed in every known control')
        rows.append(dict(row,callback_counts=counters[lane],observer_state_comparisons=81,
                         observer_state_chain_sha256=state_hashes[lane].hexdigest(),new_game_credit=0))
    stats['canonical_comparison_s']+=time.perf_counter()-started
    stats['work_end_to_end_s']=time.perf_counter()-work_started
    started=time.perf_counter(); _json_new(output/('%s_rows_%d.json'%(arm,repeat)),rows)
    stats['final_row_evidence_write_s']=time.perf_counter()-started
    stats['replica_end_to_end_s']=time.perf_counter()-began
    stats['actual_callbacks']=sum(sum(c['attempts']) for c in counters); stats['known_control_replicas']=len(rows)
    stats['new_primary_games']=stats['new_study_games']=0
    return stats


def run(output_directory=OUTPUT):
    output=Path(output_directory).resolve()
    if output.exists(): raise ValueError('Fresh benchmark output required; no resume or replacement')
    if 'torch' in sys.modules: raise ValueError('This qualification benchmark must remain CPU-only without Torch')
    pins=source_pins(); registration,expected,input_pins=_load_known(); _guards(registration)
    output.mkdir(parents=True,exist_ok=False); (output/'.execution_claim').mkdir()
    plan=dict(format=FORMAT,source_sha256=pins,known_input_sha256=input_pins,
        fixture_ids=[r['fixture'] for r in expected],repeats=REPEATS,workers=4,
        order='For each repeat: serial then pool. Two predetermined repeats; first cold workers, second warm reset with fresh actors.',
        counts='Canonical-control replicas only; no new source fixture or study/primary admission.',
        runtime=dict(python_version=platform.python_version(),full_version=sys.version,implementation=platform.python_implementation(),
                     executable=sys.executable,platform=platform.platform(),logical_cores=os.cpu_count()),
        actor_profiles=dict(candidate_sources=[dict(name=c.get('name'),sha256=c['sha256']) for c in registration['candidates']],
                            opponent_family_counts=dict(Counter(s['family'] for f in registration['fixtures'] for s in f['opponents']))),
        primary_games=0,study_games=0,completed_per_game_bmcts_audits=0)
    _json_new(output/'registration.json',plan)
    began=time.perf_counter(); measurements=[]; partial={}; pool=None; resets=[]; original_error=None
    try:
        started=time.perf_counter(); pool=ActorPool(4,evidence_directory=output/'pool_events')
        constructor_s=time.perf_counter()-started
        for repeat in range(REPEATS):
            measurements.append(_replica(registration,expected,'serial',repeat,output,pool,partial))
            measurements.append(_replica(registration,expected,'pool',repeat,output,pool,partial))
            started=time.perf_counter(); evidence=pool.reset(); elapsed=time.perf_counter()-started
            resets.append(dict(after_repeat=repeat,wall_s=elapsed,evidence=evidence))
        started=time.perf_counter(); pool.close(); close_s=time.perf_counter()-started
        _guards(registration)
        if source_pins()!=pins or _load_known()[2]!=input_pins or 'torch' in sys.modules:
            raise ValueError('Source/input/runtime changed or Torch imported during CPU benchmark')
        ratios=[dict(repeat=i,
            serial_over_pool_replica_wall=measurements[2*i]['replica_end_to_end_s']/measurements[2*i+1]['replica_end_to_end_s'],
            serial_over_pool_including_reset_and_lifecycle_wall=measurements[2*i]['replica_end_to_end_s']/(
                measurements[2*i+1]['replica_end_to_end_s']+resets[i]['wall_s']+(constructor_s if i==0 else 0)+(close_s if i==REPEATS-1 else 0))) for i in range(REPEATS)]
        report=dict(plan,measurements=measurements,pool_constructor_s=constructor_s,pool_reset_measurements=resets,
            pool_close_s=close_s,measured_ratios=ratios,wall_before_report_write_s=time.perf_counter()-began,
            all_entire_canonical_action_tapes_scores_exact=True,all_actual_callbacks=sum(m['actual_callbacks'] for m in measurements),
            all_two_cpu_referee_state_comparisons=sum(m['observer_state_comparisons'] for m in measurements),
            limitation='Measured CPU-only known-control qualification replicas, including public conversion/checks, IPC, actors, two CPU referees and evidence writes. Background load/order/cold compilation can affect ratios. No CUDA integration or fresh-policy qualification, no active-study source change, no primary/study credit.')
        _json_new(output/'results.json',report); return report
    except BaseException as error:
        original_error=error
        try:
            _json_new(output/'error.json',dict(format=FORMAT,exception_type=type(error).__name__,message=str(error),
                partial=partial,measurements=measurements,pool_evidence=pool.evidence if pool is not None else [],
                primary_games=0,study_games=0,status='failed preserve all partial evidence no retry'))
        except BaseException as evidence_error:
            error.benchmark_evidence_failure=type(evidence_error).__name__
        raise
    finally:
        if pool is not None:
            try: pool.close()
            except BaseException as close_error:
                if original_error is None: raise
                original_error.benchmark_close_failure=type(close_error).__name__


def main():
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument('--output',type=Path,default=OUTPUT)
    result=run(parser.parse_args().output)
    print(json.dumps(dict(replicas=len(result['fixture_ids'])*REPEATS*2,actual_callbacks=result['all_actual_callbacks'],
                          measured_ratios=result['measured_ratios'],primary_games=0,study_games=0)))


if __name__=='__main__': main()
