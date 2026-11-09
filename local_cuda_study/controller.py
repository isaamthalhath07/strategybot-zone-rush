"""Canonical owner-local CUDA study, with complete owner actor regeneration."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import time

from distributed_campaign import auth, protocol as transport
from evolution import oversight
from local_cuda_matches import runner
from primary_campaign import core
from . import contract

ROOT = contract.ROOT
BEHAVIOR = ('candidate','fixture','map_id','focal_seat','field','scores','focal_pw',
            'focal_score','opponent_ids','actions','faults')


def pins():
    result = dict(runner.source_pins())
    packages = ('distributed_campaign','confirmation_campaign','primary_campaign','evolution',
                'campaign_holdout','training_gpu','search_coach','simulator/vendor_harness',
                'local_cuda_matches','local_cuda_study')
    for package in packages:
        result.update({p.relative_to(ROOT).as_posix():contract.sha(p.read_bytes())
                       for p in (ROOT/package).glob('*.py') if not p.name.startswith('test_')})
    for name in ('simulator/__init__.py','tests/__init__.py'):
        result[name] = contract.sha((ROOT/name).read_bytes())
    return result


def check_pins(expected):
    if pins() != expected:
        raise ValueError('Frozen local controller/actor/physics sources changed')


def _signed(registry, purpose, value):
    return auth.sign_owner(registry, 'owner-local-cuda-'+purpose+'/v1', value)


def _read(registry, purpose, path):
    return auth.verify_owner(registry, 'owner-local-cuda-'+purpose+'/v1', core.read_sealed(path))


def _runtime():
    import torch
    if not torch.cuda.is_available():
        raise ValueError('Actual local CUDA is required; no CPU fallback')
    return dict(python=transport.runtime(),torch=str(torch.__version__),cuda_build=torch.version.cuda,
                device_name=torch.cuda.get_device_name(0),capability=list(torch.cuda.get_device_capability(0)))


def qualify(registration_path, registry_path, output):
    output = Path(output).resolve()
    registration, registry, witness, gold = contract.admitted_study(registration_path, registry_path)
    expected = pins()
    identities = list(registration['runtime_qualification_task_ids'])
    rows = runner.run_fixtures(registration,identities,output,device='cuda',use_graph=True,primary_credit=0)
    candidates = {c['sha256']:c for c in registration['candidates']}
    fixtures = {f['id']:f for f in registration['fixtures']}
    callbacks, oracles = 0, 0
    for row in rows:
        original = gold[row['fixture']]['game']
        if any(row[key] != original[key] for key in BEHAVIOR):
            raise ValueError('CUDA qualification did not reproduce the exact canonical original game')
        proof = oversight.audit_game(candidates[row['candidate']],fixtures[row['fixture']],registration['sources'],row,regenerate=True)
        callbacks += proof['callbacks_regenerated']
        oracles += proof['public_memory_oracles']
    if len(rows) != 8 or {r['fixture'] for r in rows} != set(identities) or callbacks != 2560:
        raise ValueError('Incomplete exact-policy CUDA qualification')
    check_pins(expected)
    summary = core.read_sealed(output/'summary.json')
    receipt = dict(format=contract.FORMAT,source_registration_sha256=contract.REGISTRATION_SHA256,
        source_sha256=expected,qualified=True,runtime=_runtime(),fixture_ids=identities,
        canonical_gold_witness_sha256=contract.sha((Path(registration_path).parent/'runtime_gold_v2/gold_witness.json').read_bytes()),
        backend_summary_sha256=contract.sha((output/'summary.json').read_bytes()),
        qualification_replicas=8,new_study_games=0,primary_games=0,bmcts_audits=0,
        full_action_tapes_equal=True,original_actor_callbacks=summary['callbacks'],
        independently_regenerated_callbacks=callbacks,public_memory_oracles=oracles,
        physics_metadata=summary['physics_metadata'],actor_backend='CPU exact Python',physics_backend='CUDA',
        limitation='Finite eight-case qualification; all original fixtures still require full local admission.')
    core.seal(output/'qualification.json',_signed(registry,'qualification',receipt))
    return receipt


def prepare(registration_path, registry_path, qualification_path, output, batch_size=64):
    output = Path(output).resolve()
    if output.exists() or type(batch_size) is not int or not 1 <= batch_size <= 256:
        raise ValueError('Fresh local output and fixed batch size1..256 required')
    registration, registry, witness, gold = contract.admitted_study(registration_path,registry_path)
    qualified = _read(registry,'qualification',qualification_path)
    if (qualified['source_registration_sha256'] != contract.REGISTRATION_SHA256
            or qualified['source_sha256'] != pins() or qualified['runtime'] != _runtime()
            or qualified['qualified'] is not True or qualified['qualification_replicas'] != 8
            or qualified['full_action_tapes_equal'] is not True
            or qualified['independently_regenerated_callbacks'] != 2560
            or qualified['fixture_ids'] != registration['runtime_qualification_task_ids']):
        raise ValueError('Exact-source/runtime local CUDA qualification is missing or stale')
    reservation = contract.reserve(registration_path,registry_path,output)
    output.mkdir(parents=True,exist_ok=False)
    plan = dict(reservation)
    plan.update(dict(format=contract.FORMAT,source_sha256=pins(),
        runtime=qualified['runtime'],qualification_path=str(Path(qualification_path).resolve()),
        qualification_sha256=contract.sha(Path(qualification_path).read_bytes()),batch_size=batch_size,
        source_registration_path=str(Path(registration_path).resolve()),registry_path=str(Path(registry_path).resolve()),
        planned_extra_games=32768,primary_games=0,bmcts_audits=0,
        original_backend_counts=dict(existing_cpu_gold=8,new_cuda_originals=32760),
        independent_actor_audit='Every original row, including imported gold, regenerated on this owner in both CPU referees.',
        statistical_plan=registration['protocol']['inference'],promotion_allowed=False,
        failure_policy='Preserve all original/partial evidence; no automatic outcome retry, source replacement or fixture omission.',
        execution_gate='Publish exact local amendment and runtime source pins before new original fixtures execute.'))
    core.seal(output/'plan.json',_signed(registry,'plan',plan))
    return plan


def _load(plan_path):
    envelope = core.read_sealed(plan_path)
    registry = auth.load_registry(envelope['payload']['registry_path'])
    plan = auth.verify_owner(registry,'owner-local-cuda-plan/v1',envelope)
    check_pins(plan['source_sha256'])
    registration, same_registry, witness, gold = contract.admitted_study(plan['source_registration_path'],plan['registry_path'])
    if plan['runtime'] != _runtime() or plan['statistical_plan'] != registration['protocol']['inference']:
        raise ValueError('Qualified local runtime or preregistered statistics changed')
    if contract.sha(Path(plan['qualification_path']).read_bytes()) != plan['qualification_sha256']:
        raise ValueError('Bound CUDA qualification receipt changed')
    _read(registry,'qualification',plan['qualification_path'])
    if (plan['pending_fixture_ids'] != contract.fixture_partition(registration,gold)
            or plan['binding'] != contract.binding_payload(plan['source_registration_path'],plan['registry_path'],Path(plan_path).parent)):
        raise ValueError('Local source schedule or canonical output changed')
    canonical = Path(plan['source_registration_path']).parent/'distributed_control_v2'
    binding = auth.verify_owner(registry,'distributed-control-study-binding/v2',core.read_sealed(canonical/'binding.json'))
    if binding != plan['binding']:
        raise ValueError('Study canonical reservation changed')
    return plan,registry,registration,gold,canonical


def execute(plan_path):
    started = time.perf_counter()
    plan,registry,registration,gold,canonical = _load(plan_path)
    output = Path(plan_path).resolve().parent
    with transport.ResultLease(canonical), transport.ResultLease(output):
        claim=output/'.execution_claim'
        if claim.exists() or (output/'acceptance.json').exists():
            raise ValueError('Preserve original execution evidence; no automatic outcome rerun')
        claim.mkdir(exist_ok=False)
        core.seal(output/'execution_started.json',_signed(registry,'started',dict(
            plan_sha256=contract.sha(Path(plan_path).read_bytes()),primary_games=0,bmcts_audits=0)))
        candidates={c['sha256']:c for c in registration['candidates']}
        fixtures={f['id']:f for f in registration['fixtures']}
        count,callbacks,active=0,0,dict(phase='import_original_gold',batch=None,fixture=None)
        seen=set()
        try:
            with (output/'games.jsonl').open('xb') as games, (output/'audits.jsonl').open('xb') as audits:
                def admit(row,backend):
                    nonlocal count,callbacks
                    identity=row['fixture']; active['fixture']=identity
                    if identity in seen or identity not in fixtures:
                        raise ValueError('Duplicate or foreign original study row')
                    f=fixtures[identity]
                    if row['candidate'] != f['candidate']:
                        raise ValueError('Original row candidate differs from the frozen fixture arm')
                    proof=oversight.audit_game(candidates[row['candidate']],f,registration['sources'],row,regenerate=True)
                    if proof['callbacks_regenerated'] != 320:
                        raise ValueError('Independent complete original actor regeneration missing')
                    body=core.canonical(row)
                    games.write(body+b'\n'); games.flush()
                    audits.write(core.canonical(dict(fixture=identity,candidate=row['candidate'],
                        game_sha256=contract.sha(body),original_backend=backend,**proof))+b'\n'); audits.flush()
                    seen.add(identity); count+=1; callbacks+=proof['callbacks_regenerated']
                for identity in registration['runtime_qualification_task_ids']:
                    admit(gold[identity]['game'],'existing_canonical_cpu_original')
                todo=plan['pending_fixture_ids']
                for offset in range(0,len(todo),plan['batch_size']):
                    index=offset//plan['batch_size']; active.update(phase='cuda_original_batch',batch=index,fixture=None)
                    ids=todo[offset:offset+plan['batch_size']]
                    batch_dir=output/'batches'/('%05d'%index)
                    rows=runner.run_fixtures(registration,ids,batch_dir,device='cuda',use_graph=True,primary_credit=0)
                    if [row['fixture'] for row in rows] != ids:
                        raise ValueError('CUDA original batch changed ordered fixture coverage')
                    active['phase']='independent_owner_actor_regeneration'
                    for row in rows:
                        admit(row,'local_cuda_physics_exact_cpu_python_actors')
                    games.flush(); audits.flush()
                    os.fsync(games.fileno()); os.fsync(audits.fileno())
                    print(json.dumps(dict(completed_extra_originals=count,planned=32768,
                        independently_regenerated_callbacks=callbacks,primary_games=0,bmcts_audits=0,
                        elapsed_s=time.perf_counter()-started)),flush=True)
            if seen != set(fixtures) or count != 32768 or callbacks != 32768*320:
                raise ValueError('Complete frozen study/actor-audit coverage is missing')
            check_pins(plan['source_sha256'])
            acceptance=dict(format=contract.FORMAT,complete=True,accepted_extra_games=32768,
                original_backend_counts=plan['original_backend_counts'],primary_games=0,bmcts_audits=0,
                original_callbacks=32768*320,independent_owner_regenerated_callbacks=callbacks,
                games_sha256=contract.sha((output/'games.jsonl').read_bytes()),
                audits_sha256=contract.sha((output/'audits.jsonl').read_bytes()),
                source_registration_sha256=contract.REGISTRATION_SHA256,
                plan_sha256=contract.sha(Path(plan_path).read_bytes()),runtime=plan['runtime'],
                source_sha256=plan['source_sha256'],wall_seconds=time.perf_counter()-started,promoted=False,
                limitation='Local CUDA physics with exact CPU policies and complete owner CPU actor/two-referee regeneration; no remote auditor or GPU-policy claim.')
            core.seal(output/'acceptance.json',_signed(registry,'acceptance',acceptance))
            return acceptance
        except BaseException as error:
            core.seal(output/'error.json',_signed(registry,'error',dict(format=contract.FORMAT,
                active=active,completed_original_rows=count,callbacks_regenerated=callbacks,
                exception_type=type(error).__name__,message=str(error),primary_games=0,bmcts_audits=0,
                failed_batch_partial=getattr(error,'local_cuda_partial',None),
                status='Preserve all original/partial evidence; no automatic outcome rerun.')))
            raise


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='command',required=True)
    for name in ('qualify','prepare'):
        command=sub.add_parser(name)
        command.add_argument('--registration',type=Path,required=True)
        command.add_argument('--registry',type=Path,required=True)
        command.add_argument('--output',type=Path,required=True)
        if name=='prepare':
            command.add_argument('--qualification',type=Path,required=True)
            command.add_argument('--batch-size',type=int,default=64)
    command=sub.add_parser('execute'); command.add_argument('--plan',type=Path,required=True)
    args=parser.parse_args()
    if args.command=='qualify':
        value=qualify(args.registration,args.registry,args.output)
    elif args.command=='prepare':
        value=prepare(args.registration,args.registry,args.qualification,args.output,args.batch_size)
    else:
        value=execute(args.plan)
    print(json.dumps({key:value[key] for key in ('format','qualified','qualification_replicas','accepted_extra_games','primary_games','bmcts_audits') if key in value}),flush=True)


if __name__=='__main__':
    main()
