"""Operator-launched known-control representative benchmark, never training.

First reproduce the exact eight serial controls. Then one512-lane full CUDA
pipeline call uses two256 batches and64 ordered repetitions per control. Every
replica has a fresh lane identity and all320 independent replay callbacks.
"""
import argparse
from collections import Counter
import copy
from datetime import datetime,timezone
import math
from pathlib import Path
import time

from local_policy_pool import benchmark as serial_reference
from . import runner

ROOT=runner.ROOT
FORMAT='deadline-known-eight-representative-benchmark/1'
OUTPUT=ROOT/'.cache/deadline_runner/known8_001'
CONTROLS=8
REPETITIONS=64
BATCH_SIZE=256
PIPELINE_GAMES=512


def source_pins():
    pins=runner.source_pins()
    for name in ('deadline_runner/benchmark.py','local_policy_pool/benchmark.py',
                 'local_policy_pool/pool.py','local_policy_pool/__init__.py','deadline_runner/verify.py'):
        pins[name]=runner.sha((ROOT/name).read_bytes())
    return pins


def _load_known():
    # The reference reader pins the exact unchanged two qualification files.
    registration,rows,input_pins=serial_reference._load_known()
    if len(rows)!=CONTROLS or len({row['fixture'] for row in rows})!=CONTROLS:
        raise ValueError('Exactly eight unchanged known controls required')
    return registration,rows,input_pins


def _replicas(registration,controls):
    if len(controls)!=CONTROLS: raise ValueError('Eight controls required for balanced replication')
    fixtures={f['id']:f for f in registration['fixtures']}; generated=[]; mapping=[]
    if len(fixtures)!=CONTROLS or set(fixtures)!={row['fixture'] for row in controls}:
        raise ValueError('Known fixture/record coverage changed')
    for repeat in range(REPETITIONS):
        for position,control in enumerate(controls):
            original=fixtures[control['fixture']]
            lane=runner.sha(runner.canonical([FORMAT,control['fixture'],repeat]))
            cloned=copy.deepcopy(original); cloned['id']=lane
            generated.append(cloned)
            mapping.append(dict(lane_id=lane,source_fixture_id=control['fixture'],control_position=position,repetition=repeat))
    if len(generated)!=PIPELINE_GAMES or len({f['id'] for f in generated})!=PIPELINE_GAMES:
        raise ValueError('Representative benchmark must contain512 fresh lane identities')
    snapshot=dict(format=FORMAT,role='Known-control qualification replicas; never new study cases',
        rules=copy.deepcopy(registration.get('rules',{'catch_requires_stay':True})),
        candidates=copy.deepcopy(registration['candidates']),sources=copy.deepcopy(registration['sources']),
        guards=copy.deepcopy(registration['guards']),fixtures=generated,
        primary_games=0,study_games=0,completed_per_game_bmcts_audits=0,promotion_allowed=False)
    return snapshot,mapping


def _verify_result(result,mapping,controls,pipeline_output):
    expected={row['fixture']:row for row in controls}; ids=[m['lane_id'] for m in mapping]
    rows=result['rows']; audits=result['audits']; summary=result['summary']
    if [r['fixture'] for r in rows]!=ids or [a['fixture'] for a in audits]!=ids:
        raise ValueError('Ordered complete512 original/audit coverage changed')
    if (len(rows)!=PIPELINE_GAMES or len(audits)!=PIPELINE_GAMES
            or summary['original_games']!=PIPELINE_GAMES or summary['independent_full_game_audits']!=PIPELINE_GAMES
            or summary['original_callbacks']!=PIPELINE_GAMES*320 or summary['independently_regenerated_callbacks']!=PIPELINE_GAMES*320):
        raise ValueError('Representative benchmark omitted an original or independent callback')
    for row,audit,binding in zip(rows,audits,mapping):
        control=expected[binding['source_fixture_id']]
        for name in serial_reference.BEHAVIOR:
            desired=binding['lane_id'] if name=='fixture' else control[name]
            if row[name]!=desired: raise ValueError('A full representative control action tape/score differs: '+name)
        proof=row['proof']
        if (proof['callbacks_regenerated']!=320 or proof['gpu_reference_state_comparisons']!=81
                or proof['gpu_official_state_comparisons']!=81 or proof['physical_turns']!=80
                or audit['callbacks_regenerated']!=320 or audit['all_actors_regenerated'] is not True
                or audit['dual_referee_physical_turns']!=80
                or audit['row_sha256']!=runner.sha(runner.canonical(row))):
            raise ValueError('Representative original/audit proof incomplete or bound to another row')
    disk_rows=[runner.oversight.strict_loads(line) for line in (pipeline_output/'originals.jsonl').read_bytes().splitlines()]
    disk_audits=[runner.oversight.strict_loads(line) for line in (pipeline_output/'audits.jsonl').read_bytes().splitlines()]
    if disk_rows!=rows or disk_audits!=audits: raise ValueError('Published pipeline records differ from returned complete records')
    return dict(full_originals=PIPELINE_GAMES,full_actor_audits=PIPELINE_GAMES,
                original_callbacks=PIPELINE_GAMES*320,independent_replay_callbacks=PIPELINE_GAMES*320,
                both_referees=True,all_entire_known_tapes_and_scores_exact=True)


def _sealed(path):
    body=path.read_bytes()
    if runner.sha(body)!=path.with_suffix('.sha256').read_text().strip(): raise ValueError('Artifact seal mismatch: '+path.name)
    return runner.oversight.strict_loads(body)


def _lines(path):
    body=path.read_bytes()
    if body and not body.endswith(b'\n'): raise ValueError('Incomplete streamed record: '+path.name)
    return [runner.oversight.strict_loads(line) for line in body.splitlines()]


def _verify_pipeline_artifacts(path,replicas,mapping,controls):
    from .verify import verify_execution
    result=verify_execution(replicas,path)
    _verify_result(result,mapping,controls,path)
    return result


def verify_complete(output_directory):
    """Read-only verification; no actor, referee step, CUDA or game rerun."""
    from .verify import _source_archive,_zero
    output=Path(output_directory).resolve(); report=_sealed(output/'benchmark_result.json')
    if (output/'benchmark_error.json').exists() or (output/'pipeline'/'error.json').exists():
        raise ValueError('Failed benchmark evidence cannot calibrate campaign budget')
    plan=_sealed(output/'benchmark_registration.json'); pins=source_pins()
    if plan.get('format')!=FORMAT or report.get('format')!=FORMAT: raise ValueError('Benchmark format changed')
    _zero(plan); _zero(report)
    registration,controls,input_pins=_load_known(); replicas,mapping=_replicas(registration,controls)
    if (report['source_sha256']!=pins or plan['source_sha256']!=pins or report['known_input_sha256']!=input_pins
            or plan['known_input_sha256']!=input_pins or report['replica_mapping']!=mapping or plan['replica_mapping']!=mapping
            or report['known_control_order']!=[r['fixture'] for r in controls]):
        raise ValueError('Exact benchmark source/input/ordered control mapping changed')
    for key,value in (('controls',CONTROLS),('repetitions_per_control',REPETITIONS),('pipeline_games',PIPELINE_GAMES),('batch_size',BATCH_SIZE),('actor_workers',4),('audit_workers',4)):
        if type(report[key]) is not int or report[key]!=value or plan[key]!=value: raise ValueError('Fixed benchmark schedule changed')
    if any(report[k]!=plan[k] for k in plan): raise ValueError('Published benchmark plan/claim differs from final result')
    current_runtime=runner.frozen.runtime_info()
    if any(report['runtime'][k]!=current_runtime[k] for k in ('implementation','python_version','full_python_version')):
        raise ValueError('Qualified CPU Python runtime changed')
    if report['source_snapshot_sha256']!=runner.sha((output/'source_snapshot.json').read_bytes()): raise ValueError('Benchmark source archive binding changed')
    _source_archive(output,pins,replicas)
    expected_counts=dict(Counter(m['source_fixture_id'] for m in mapping))
    if report['control_replica_counts']!=expected_counts or any(v!=REPETITIONS for v in expected_counts.values()):
        raise ValueError('Known controls are not exactly balanced')
    result=_verify_pipeline_artifacts(output/'pipeline',replicas,mapping,controls)
    if (report['pipeline_summary']!=result['summary']
            or report['pipeline_summary_sha256']!=runner.sha((output/'pipeline'/'summary.json').read_bytes())):
        raise ValueError('Benchmark full pipeline summary changed')
    if report['equivalence']!=_verify_result(result,mapping,controls,output/'pipeline'):
        raise ValueError('Whole canonical equivalence result changed')
    serial_rows=runner.oversight.strict_loads((output/'serial_controls'/'serial_rows_0.json').read_bytes())
    for name,digest in report['serial_artifacts_sha256'].items():
        if name not in ('serial_rows_0.json','serial_turns_0.jsonl') or runner.sha((output/'serial_controls'/name).read_bytes())!=digest:
            raise ValueError('Serial control artifact hash changed')
    if set(report['serial_artifacts_sha256'])!={'serial_rows_0.json','serial_turns_0.jsonl'}:
        raise ValueError('Both serial control artifacts required')
    if len(serial_rows)!=CONTROLS or any(any(row[k]!=expected[k] for k in serial_reference.BEHAVIOR) for row,expected in zip(serial_rows,controls)):
        raise ValueError('Untouched serial control tapes/scores changed')
    measurements=report['measurements']
    if type(measurements) is not list or len(measurements)!=1: raise ValueError('One complete512-lane pipeline timing required')
    m=measurements[0]
    if (set(m)!={'games','wall_seconds','full_actor_audits','both_referees'} or type(m['games']) is not int or m['games']!=PIPELINE_GAMES
            or type(m['full_actor_audits']) is not int or m['full_actor_audits']!=PIPELINE_GAMES or m['both_referees'] is not True
            or type(m['wall_seconds']) not in (int,float) or not math.isfinite(m['wall_seconds']) or m['wall_seconds']<=0
            or m['wall_seconds']<report['outer_full_run_fixtures_wall_s']
            or abs(m['wall_seconds']-report['outer_full_run_fixtures_wall_s']-report['final_equivalence_and_source_checks_s'])>1e-6):
        raise ValueError('Budget measurement omits complete original/audit wall time')
    serial_reference._guards(registration)
    return report


def run(output=OUTPUT,device='cuda'):
    output=Path(output).resolve()
    if output.exists(): raise ValueError('Fresh benchmark output required; preserve failed/completed attempts')
    if type(device) is not str or not (device=='cuda' or device.startswith('cuda:')):
        raise ValueError('Representative pipeline calibration requires actual local CUDA')
    pins=source_pins(); registration,controls,input_pins=_load_known(); serial_reference._guards(registration)
    replicas,mapping=_replicas(registration,controls)
    output.mkdir(parents=True,exist_ok=False); (output/'.execution_claim').mkdir()
    archived=runner._snapshot_sources(output,pins,replicas)
    plan=dict(format=FORMAT,created_utc=datetime.now(timezone.utc).isoformat(),source_sha256=pins,
        known_input_sha256=input_pins,known_control_order=[r['fixture'] for r in controls],replica_mapping=mapping,
        controls=CONTROLS,repetitions_per_control=REPETITIONS,pipeline_games=PIPELINE_GAMES,batch_size=BATCH_SIZE,
        actor_workers=4,audit_workers=4,device=device,
        order='Eight original serial controls once; one512 replica pipeline call in two256 batches; original control order repeated64 times.',
        runtime=runner.frozen.runtime_info(),
        concurrent_context=dict(operator_reports_frozen_32k_study_running=True,verified_by_benchmark=False,
            limitation='Concurrent old-study CPU/GPU work and fixed ordering make this a loaded-system calibration, not an isolated hardware ratio.'),
        primary_games=0,study_games=0,completed_per_game_bmcts_audits=0)
    runner.frozen._seal(output/'benchmark_registration.json',plan)
    partial={}; serial_stats=None; result=None; started=time.perf_counter()
    try:
        serial_dir=output/'serial_controls'; serial_dir.mkdir()
        serial_began=time.perf_counter()
        serial_stats=serial_reference._replica(registration,controls,'serial',0,serial_dir,None,partial)
        serial_outer_s=time.perf_counter()-serial_began
        pipeline_output=output/'pipeline'; partial=dict(phase='full_pipeline')
        pipeline_started=time.perf_counter()
        result=runner.run_fixtures(replicas,[m['lane_id'] for m in mapping],pipeline_output,
                                   batch_size=BATCH_SIZE,workers=4,audit_workers=4,device=device)
        outer_run_s=time.perf_counter()-pipeline_started
        result=_verify_pipeline_artifacts(pipeline_output,replicas,mapping,controls)
        equivalence=_verify_result(result,mapping,controls,pipeline_output)
        serial_reference._guards(registration)
        if source_pins()!=pins or _load_known()[2]!=input_pins:
            raise ValueError('Benchmark source or exact known-control inputs changed')
        runner._verify_source_snapshot(output,archived)
        complete_wall=time.perf_counter()-pipeline_started
        measurements=[dict(games=PIPELINE_GAMES,wall_seconds=complete_wall,full_actor_audits=PIPELINE_GAMES,both_referees=True)]
        report=dict(plan,measurements=measurements,serial_control_measurement=serial_stats,
            serial_artifacts_sha256={name:runner.sha((serial_dir/name).read_bytes()) for name in ('serial_rows_0.json','serial_turns_0.jsonl')},
            serial_control_outer_wall_s=serial_outer_s,outer_full_run_fixtures_wall_s=outer_run_s,
            final_equivalence_and_source_checks_s=complete_wall-outer_run_s,
            measurement_definition='Full outer run_fixtures call including worker startup/shutdown, originals, all actor audits and pipeline final publication, plus all512 canonical equivalence and final input/source snapshot checks. Benchmark_result.json self-write follows the measured interval.',
            equivalence=equivalence,pipeline_summary_sha256=runner.sha((pipeline_output/'summary.json').read_bytes()),
            pipeline_summary=result['summary'],source_snapshot_sha256=runner.sha((output/'source_snapshot.json').read_bytes()),
            control_replica_counts=dict(Counter(m['source_fixture_id'] for m in mapping)),
            wall_before_benchmark_result_publication_s=time.perf_counter()-started,
            limitations=['Eight underlying known recipes are reused;512 lanes are qualification replicas, not new maps or study outcomes.',
                'Every512 original has all320 independent actor replay callbacks and both CPU referees; no sampled auditing.',
                'Serial controls and pipeline populations differ in size and overlap context; no isolated speedup ratio is reported.',
                'All primary/study/BMCTS admission remains zero. This benchmark does not modify or integrate into the active frozen study.'])
        runner.frozen._seal(output/'benchmark_result.json',report); return report
    except BaseException as error:
        payload=dict(format=FORMAT,exception_type=type(error).__name__,message=str(error),partial=partial,
            serial_control_measurement=serial_stats,pipeline_partial=getattr(error,'deadline_runner_partial',None),
            primary_games=0,study_games=0,completed_per_game_bmcts_audits=0,status='failed preserve all evidence no retry')
        try: runner.frozen._seal(output/'benchmark_error.json',runner.frozen._safe_evidence(payload))
        except BaseException as secondary: error.benchmark_evidence_failure=type(secondary).__name__
        raise


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=OUTPUT); parser.add_argument('--device',default='cuda')
    result=run(**vars(parser.parse_args()))
    print(runner.canonical(dict(measurements=result['measurements'],primary_games=0,study_games=0)).decode())


if __name__=='__main__': main()
