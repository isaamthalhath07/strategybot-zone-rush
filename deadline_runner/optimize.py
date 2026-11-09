"""Root-launched fixed scheduling grid on known controls; never training.

Published baseline plus exactly three variants. Selection uses complete elapsed
seconds/game only; all512 canonical originals and independent audits are kept.
No benchmark, pipeline, actor, verifier or active-study source is modified.
"""
import argparse
import copy
from datetime import datetime,timezone
import math
from pathlib import Path
import time

from . import benchmark,runner,verify

FORMAT='deadline-fixed-scheduling-qualification-grid/1'
OUTPUT=runner.ROOT/'.cache/deadline_runner/known8_grid_001'
BASELINE=runner.ROOT/'.cache/deadline_runner/known8_001'
BASELINE_SHA256='8ae5efc113e72961eebf465cdd5a9dc7ff95cb4e686679ec378f19aad75f9a84'
BASELINE_CONFIGURATION=dict(batch_size=256,workers=4,audit_workers=4)
CONFIGURATIONS=(dict(batch_size=128,workers=4,audit_workers=4),
                dict(batch_size=128,workers=8,audit_workers=4),
                dict(batch_size=256,workers=8,audit_workers=4))


def source_pins():
    pins=benchmark.source_pins()
    pins['deadline_runner/optimize.py']=runner.sha(Path(__file__).read_bytes())
    return pins


def label(configuration):
    if (type(configuration) is not dict or set(configuration)!={'batch_size','workers','audit_workers'}
            or any(type(v) is not int for v in configuration.values())
            or configuration not in (BASELINE_CONFIGURATION,*CONFIGURATIONS)):
        raise ValueError('Exact integer scheduling configuration required')
    return 'b%d_a%d_r%d'%(configuration['batch_size'],configuration['workers'],configuration['audit_workers'])


def _measurement(value):
    if (type(value) is not dict or set(value)!={'games','wall_seconds','full_actor_audits','both_referees'}
            or type(value['games']) is not int or value['games']!=512
            or type(value['full_actor_audits']) is not int or value['full_actor_audits']!=512
            or value['both_referees'] is not True or type(value['wall_seconds']) not in (int,float)
            or not math.isfinite(value['wall_seconds']) or value['wall_seconds']<=0):
        raise ValueError('One complete512-original/full-audit timing is required')
    return copy.deepcopy(value)


def _baseline():
    body=(BASELINE/'benchmark_result.json').read_bytes()
    if runner.sha(body)!=BASELINE_SHA256: raise ValueError('Published original baseline result bytes changed')
    result=benchmark.verify_complete(BASELINE)
    if result['batch_size']!=256 or result['actor_workers']!=4 or result['audit_workers']!=4:
        raise ValueError('Original baseline configuration changed')
    _complete_lifecycle(result['outer_full_run_fixtures_wall_s'],result['pipeline_summary'])
    return dict(relative_path=str(BASELINE.relative_to(runner.ROOT)).replace('\\','/'),
        benchmark_result_sha256=BASELINE_SHA256,configuration=dict(BASELINE_CONFIGURATION),
        measurement=_measurement(result['measurements'][0]),source_sha256=result['source_sha256'])


def _replicas(registration,controls,configuration):
    replicas,mapping=benchmark._replicas(registration,controls)
    name=label(configuration)
    for fixture,binding in zip(replicas['fixtures'],mapping):
        identity=runner.sha(runner.canonical([FORMAT,name,binding['source_fixture_id'],binding['repetition']]))
        fixture['id']=identity; binding['lane_id']=identity
    replicas.update(format=FORMAT,role='Scheduling qualification replicas; never new study cases')
    return replicas,mapping


def select(measurements):
    if len(measurements)!=4: raise ValueError('Published baseline and all three variants are required for selection')
    expected=[BASELINE_CONFIGURATION,*CONFIGURATIONS]
    if runner.canonical([m['configuration'] for m in measurements])!=runner.canonical(expected): raise ValueError('Fixed scheduling grid/order changed')
    for m in measurements:
        label(m['configuration']); _measurement({k:m[k] for k in ('games','wall_seconds','full_actor_audits','both_referees')})
    chosen=min(measurements,key=lambda m:(m['wall_seconds']/m['games'],m['configuration']['batch_size'],
                                         m['configuration']['workers'],m['configuration']['audit_workers']))
    return dict(configuration=copy.deepcopy(chosen['configuration']),
                measurement={k:chosen[k] for k in ('games','wall_seconds','full_actor_audits','both_referees')},origin=chosen['origin'])


def _complete_lifecycle(outer,summary):
    lower=summary['wall_before_final_publication_s']
    if (type(outer) not in (int,float) or not math.isfinite(outer) or outer<=0
            or type(lower) not in (int,float) or not math.isfinite(lower) or lower<0 or outer+1e-6<lower):
        raise ValueError('Outer elapsed time understates the durable complete pipeline lifecycle')


def _protocol(configuration,mapping,baseline,input_pins,pins,device):
    return dict(format=FORMAT,variant=label(configuration),configuration=dict(configuration),replica_mapping=mapping,
        baseline=baseline,known_input_sha256=input_pins,source_sha256=pins,device=device,
        work='512 known-control replicas, all80 original turns and320 independent replay callbacks per original, both CPU referees.',
        primary_games=0,study_games=0,completed_per_game_bmcts_audits=0)


def _verify_variant(directory,configuration,baseline,registration,controls,input_pins,pins,device):
    replicas,mapping=_replicas(registration,controls,configuration)
    expected=_protocol(configuration,mapping,baseline,input_pins,pins,device)
    plan=verify.read_sealed(directory/'variant_registration.json'); report=verify.read_sealed(directory/'variant_result.json')
    if runner.canonical(plan)!=runner.canonical(expected) or any(runner.canonical(report[k])!=runner.canonical(v) for k,v in expected.items()):
        raise ValueError('Fixed variant protocol/source/baseline changed')
    verify._zero(report)
    durable=benchmark._verify_pipeline_artifacts(directory/'pipeline',replicas,mapping,controls)
    equivalence=benchmark._verify_result(durable,mapping,controls,directory/'pipeline')
    if (runner.canonical(report['equivalence'])!=runner.canonical(equivalence)
            or runner.canonical(report['pipeline_summary'])!=runner.canonical(durable['summary'])
            or report['pipeline_summary_sha256']!=runner.sha((directory/'pipeline'/'summary.json').read_bytes())):
        raise ValueError('Complete variant pipeline proof changed')
    if (durable['summary']['original_games']!=512 or durable['summary']['independent_full_game_audits']!=512
            or verify.read_sealed(directory/'pipeline'/'execution_started.json')['batch_size']!=configuration['batch_size']
            or verify.read_sealed(directory/'pipeline'/'execution_started.json')['workers']!=configuration['workers']
            or verify.read_sealed(directory/'pipeline'/'execution_started.json')['audit_workers']!=configuration['audit_workers']):
        raise ValueError('Qualified variant scheduling/coverage differs from declared configuration')
    m=_measurement(report['measurement'])
    outer=report['outer_run_fixtures_wall_s']; checking=report['final_verification_s']
    _complete_lifecycle(outer,durable['summary'])
    if (type(outer) not in (int,float) or not math.isfinite(outer) or outer<=0
            or type(checking) not in (int,float) or not math.isfinite(checking) or checking<0
            or m['wall_seconds']<outer or abs(m['wall_seconds']-outer-checking)>1e-6):
        raise ValueError('Variant timing omits complete execution/final verification')
    return report


def run(output=OUTPUT,device='cuda'):
    output=Path(output).resolve()
    if output.exists(): raise ValueError('Fresh grid output required; preserve failed/completed attempts')
    if type(device) is not str or not (device=='cuda' or device.startswith('cuda:')): raise ValueError('Local CUDA required')
    pins=source_pins(); baseline=_baseline(); registration,controls,input_pins=benchmark._load_known()
    benchmark.serial_reference._guards(registration)
    output.mkdir(parents=True,exist_ok=False); (output/'.execution_claim').mkdir()
    archive=runner._snapshot_sources(output,pins,registration)
    plan=dict(format=FORMAT,created_utc=datetime.now(timezone.utc).isoformat(),source_sha256=pins,baseline=baseline,
        configurations=[dict(c) for c in CONFIGURATIONS],known_input_sha256=input_pins,device=device,
        order='Exactly three listed variants, each one fresh512-lane complete run. No tuning rounds or retries.',
        selection='Minimum complete wall_seconds/games across published baseline and all3 variants; ties(batch_size,workers,audit_workers).',
        safety_factor='Unchanged: selection changes scheduling only; campaign authority retains its existing safety-factor policy.',
        context='Fixed order on the loaded local machine while old-study work may continue; no isolated hardware ratio or strength claim.',
        primary_games=0,study_games=0,completed_per_game_bmcts_audits=0)
    runner.frozen._seal(output/'optimization_registration.json',plan)
    completed=[]; active=None
    try:
        for configuration in CONFIGURATIONS:
            active=label(configuration); directory=output/active; directory.mkdir()
            replicas,mapping=_replicas(registration,controls,configuration)
            protocol=_protocol(configuration,mapping,baseline,input_pins,pins,device)
            runner.frozen._seal(directory/'variant_registration.json',protocol)
            started=time.perf_counter()
            runner.run_fixtures(replicas,[m['lane_id'] for m in mapping],directory/'pipeline',device=device,**configuration)
            outer=time.perf_counter()-started
            durable=benchmark._verify_pipeline_artifacts(directory/'pipeline',replicas,mapping,controls)
            equivalence=benchmark._verify_result(durable,mapping,controls,directory/'pipeline')
            benchmark.serial_reference._guards(registration)
            if source_pins()!=pins or benchmark._load_known()[2]!=input_pins: raise ValueError('Grid sources/known inputs changed')
            runner._verify_source_snapshot(output,archive)
            elapsed=time.perf_counter()-started
            report=dict(protocol,measurement=dict(games=512,wall_seconds=elapsed,full_actor_audits=512,both_referees=True),
                outer_run_fixtures_wall_s=outer,final_verification_s=elapsed-outer,equivalence=equivalence,
                pipeline_summary=durable['summary'],pipeline_summary_sha256=runner.sha((directory/'pipeline'/'summary.json').read_bytes()))
            runner.frozen._seal(directory/'variant_result.json',report)
            completed.append(dict(variant=active,path=active,sha256=runner.sha((directory/'variant_result.json').read_bytes())))
        measurements=[dict(configuration=baseline['configuration'],origin='published_baseline',**baseline['measurement'])]
        for configuration in CONFIGURATIONS:
            report=verify.read_sealed(output/label(configuration)/'variant_result.json')
            measurements.append(dict(configuration=dict(configuration),origin=label(configuration),**report['measurement']))
        chosen=select(measurements)
        if _baseline()!=baseline or source_pins()!=pins: raise ValueError('Original baseline/source binding changed after grid')
        report=dict(plan,variants=completed,measurements=measurements,selected_configuration=chosen['configuration'],
            selected_measurement=chosen['measurement'],selected_origin=chosen['origin'],
            source_snapshot_sha256=runner.sha((output/'source_snapshot.json').read_bytes()),
            qualification='Known-control scheduling only; all3 variants required; no novel cases, policy strength or admission credit.')
        runner.frozen._seal(output/'optimization_result.json',report); return report
    except BaseException as error:
        payload=dict(format=FORMAT,active_variant=active,completed_variants=completed,exception_type=type(error).__name__,
            message=str(error),pipeline_partial=getattr(error,'deadline_runner_partial',None),
            primary_games=0,study_games=0,completed_per_game_bmcts_audits=0,status='failed preserve every result/error; no retries or selection')
        try: runner.frozen._seal(output/'optimization_error.json',runner.frozen._safe_evidence(payload))
        except BaseException as secondary: error.optimization_evidence_failure=type(secondary).__name__
        raise


def verify_complete(output_directory):
    """Read-only whole-grid proof; no callbacks, physics or GPU execution."""
    output=Path(output_directory).resolve()
    if (output/'optimization_error.json').exists(): raise ValueError('Failed or partial grid cannot select a schedule')
    plan=verify.read_sealed(output/'optimization_registration.json'); report=verify.read_sealed(output/'optimization_result.json')
    pins=source_pins(); baseline=_baseline(); registration,controls,input_pins=benchmark._load_known()
    if (plan.get('format')!=FORMAT or report.get('format')!=FORMAT or plan['source_sha256']!=pins
            or report['source_sha256']!=pins or runner.canonical(plan['baseline'])!=runner.canonical(baseline)
            or runner.canonical(report['baseline'])!=runner.canonical(baseline)
            or runner.canonical(plan['configurations'])!=runner.canonical([dict(c) for c in CONFIGURATIONS])
            or report['known_input_sha256']!=input_pins
            or any(runner.canonical(report[k])!=runner.canonical(v) for k,v in plan.items())):
        raise ValueError('Fixed complete grid source/baseline/protocol changed')
    verify._zero(plan); verify._zero(report)
    if report['source_snapshot_sha256']!=runner.sha((output/'source_snapshot.json').read_bytes()): raise ValueError('Optimizer source archive binding changed')
    verify._source_archive(output,pins,registration)
    variants=report['variants']
    if [v['variant'] for v in variants]!=[label(c) for c in CONFIGURATIONS] or len(variants)!=3:
        raise ValueError('All three fixed scheduling variants required; no omissions or replacements')
    expected_directories={'sources','.execution_claim',*(label(c) for c in CONFIGURATIONS)}
    if {p.name for p in output.iterdir() if p.is_dir()}!=expected_directories:
        raise ValueError('Unexpected scheduling round or omitted variant directory')
    measurements=[dict(configuration=baseline['configuration'],origin='published_baseline',**baseline['measurement'])]
    for configuration,binding in zip(CONFIGURATIONS,variants):
        name=label(configuration)
        if binding['path']!=name or binding['sha256']!=runner.sha((output/name/'variant_result.json').read_bytes()):
            raise ValueError('Variant result byte binding changed')
        if (output/name/'pipeline'/'error.json').exists(): raise ValueError('A variant pipeline failed')
        variant=_verify_variant(output/name,configuration,baseline,registration,controls,input_pins,pins,plan['device'])
        measurements.append(dict(configuration=dict(configuration),origin=name,**variant['measurement']))
    chosen=select(measurements)
    if (runner.canonical(report['measurements'])!=runner.canonical(measurements)
            or runner.canonical(report['selected_configuration'])!=runner.canonical(chosen['configuration'])
            or runner.canonical(report['selected_measurement'])!=runner.canonical(chosen['measurement']) or report['selected_origin']!=chosen['origin']):
        raise ValueError('Scheduling selection is not the deterministic minimum complete elapsed time')
    benchmark.serial_reference._guards(registration)
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument('--output',type=Path,default=OUTPUT); parser.add_argument('--device',default='cuda')
    result=run(**vars(parser.parse_args()))
    print(runner.canonical(dict(selected_configuration=result['selected_configuration'],selected_measurement=result['selected_measurement'],primary_games=0,study_games=0)).decode())


if __name__=='__main__': main()
