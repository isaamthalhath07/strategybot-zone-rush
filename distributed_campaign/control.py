"""Authenticated offline architecture controls, with different-slot peer audits.

This coordinator credits EXTRA control matches only. Each accepted match has
an authenticated original creator, a different declared physical auditor, full
original actor/two-referee replay, and owner physical checks. Cooperative HMAC
authentication is not proof that a host is honest or physically independent.
"""
import argparse
from pathlib import Path

from distributed_campaign import auth, owner, protocol as p, proofs, qualification
from primary_campaign import core, run


def _unsigned(value):
    return {key:item for key,item in value.items() if key != 'authentication'}


def _sign(registry,purpose,value):
    return auth.sign_owner(registry,'distributed-control-'+purpose+'/v2',value)


def _read(registry,purpose,path):
    return auth.verify_owner(registry,'distributed-control-'+purpose+'/v2',core.read_sealed(path))


def _pins():
    paths = [path for path in (core.ROOT/'distributed_campaign').glob('*.py') if not path.name.startswith('test_')]
    paths += [core.ROOT/'confirmation_campaign/architectures.py']
    return {str(path.resolve()):p.sha(path.read_bytes()) for path in paths}


def _check_pins(pins):
    if not pins or any(p.sha(Path(path).read_bytes()) != digest for path,digest in pins.items()):
        raise ValueError('Distributed control coordinator source changed')


def _load(path):
    path = Path(path).resolve()
    envelope = core.read_sealed(path)
    # Registry location is public; authentication still uses the private owner
    # key and exact immutable plan, not an unsigned registry approval flag.
    registry = auth.load_registry(envelope['payload']['registry_path'])
    plan = auth.verify_owner(registry,'distributed-control-plan/v2',envelope)
    _check_pins(plan['controller_sources'])
    if plan['role'] != 'extra_control_assignment' or plan['primary_games_accepted'] != 0:
        raise ValueError('This controller accepts EXTRA controls only')
    registration_path = Path(plan['source_registration_path'])
    registration = core.read_sealed(registration_path)
    if p.sha(registration_path.read_bytes()) != plan['source_registration_sha256']:
        raise ValueError('Frozen control registration changed')
    binding = _read(registry,'study-binding',registration_path.parent/'distributed_control_v2/binding.json')
    if binding != _study_binding(registration_path,path.parent,plan['helpers'],plan['registry_path']):
        raise ValueError('This frozen study is assigned to another canonical controller output')
    from confirmation_campaign import architectures
    architectures.validate(registration)
    if registration['campaign_id'] != plan['campaign_id'] or registration['generation'] != plan['generation']:
        raise ValueError('Control campaign identity changed')
    if owner.qualification_context() != plan['qualification_context']:
        raise ValueError('Actual actor/referee/helper sources changed')
    if p.runtime() != plan['owner_runtime']:
        raise ValueError('Owner runtime changed; reviewed controller migration required')
    bundles = {}
    assigned = []
    for shard in plan['distribution']['shards']:
        bundle = p.verify_bundle(shard['bundle_directory'],shard['bundle_sha256'])
        if (bundle['work_role'] != 'play' or bundle['role'] != plan['role']
                or bundle['source_registration_sha256'] != plan['source_registration_sha256']):
            raise ValueError('Control play bundle role or registration changed')
        bundles[shard['id']] = bundle
        assigned += shard['fixture_ids']
    gold_ids = registration['runtime_qualification_task_ids']
    expected = {fixture['id'] for fixture in registration['fixtures']}-set(gold_ids)
    if len(assigned) != len(set(assigned)) or set(assigned) != expected:
        raise ValueError('Play assignment coverage overlaps, misses or repeats consumed gold')
    return plan,registry,registration,path.parent,bundles


def _import_gold(plan,registry,registration,directory):
    _,gold = qualification.read_control_gold(plan['source_registration_path'],registry)
    for identity,value in gold.items():
        origin = dict(kind='owner_gold',game=value['game'],creator=value['creator'],
                      gold_witness_sha256=plan['gold_witness_sha256'],source_gold_record=value)
        core.seal(directory/'origins'/(identity+'.json'),_sign(registry,'origin',origin))


def _returned_entries(result_directory,digest):
    path = Path(result_directory)/'records.jsonl'
    if path.stat().st_size > 256*1024*1024:
        raise ValueError('Returned transfer grew beyond its verified byte bound')
    body = path.read_bytes()
    if p.sha(body) != digest:
        raise ValueError('Returned transfer changed after bounded authentication')
    return {entry['record']['fixture']:entry for entry in (p.loads(line) for line in body.splitlines())}


def _study_binding(registration_path,output,helpers,registry_path):
    return dict(source_registration_path=str(Path(registration_path).resolve()),
                source_registration_sha256=p.sha(Path(registration_path).read_bytes()),
                canonical_output=str(Path(output).resolve()),helpers=list(helpers),
                registry_path=str(Path(registry_path).resolve()),role='extra_control_assignment',
                rule='One owner-issued original-game cohort per frozen study; alternate outputs cannot resubmit it.')


def prepare(registration_path,registry_path,output,helpers,approval_paths):
    """Reserve the study's one canonical controller BEFORE issuing any jobs."""
    registration_path,output = Path(registration_path).resolve(),Path(output).resolve()
    if not output.is_relative_to((core.ROOT/'.cache/distributed_campaign').resolve()):
        raise ValueError('Control plans must be generated under the ignored distributed cache')
    registry = auth.load_registry(registry_path)
    from confirmation_campaign import architectures
    architectures.validate(core.read_sealed(registration_path))
    canonical = registration_path.parent/'distributed_control_v2'
    with p.ResultLease(canonical):
        expected = _study_binding(registration_path,output,helpers,registry_path)
        binding_path = canonical/'binding.json'
        if binding_path.exists():
            if _read(registry,'study-binding',binding_path) != expected:
                raise ValueError('Frozen study already reserved another canonical output/helper request; never duplicate its jobs')
        else:
            core.seal(binding_path,_sign(registry,'study-binding',expected))
        return _prepare_locked(registration_path,registry_path,output,helpers,approval_paths)


def _prepare_locked(registration_path,registry_path,output,helpers,approval_paths):
    """Freeze real play assignments after source-specific runtime qualification."""
    registration_path,output = Path(registration_path).resolve(),Path(output).resolve()
    if not output.is_relative_to((core.ROOT/'.cache/distributed_campaign').resolve()):
        raise ValueError('Control plans must be generated under the ignored distributed cache')
    if (output/'plan.json').exists():
        plan,registry,registration,directory,_ = _load(output/'plan.json')
        if plan['source_registration_path'] != str(registration_path) or plan['helpers'] != list(helpers):
            raise ValueError('Existing immutable control plan belongs to another request')
        with p.ResultLease(output):
            _import_gold(plan,registry,registration,directory)
        return plan
    registry = auth.load_registry(registry_path)
    registration = core.read_sealed(registration_path)
    from confirmation_campaign import architectures
    architectures.validate(registration)
    witness,gold = qualification.read_control_gold(registration_path,registry)
    approvals = {slot:core.read_sealed(approval_paths[slot]) for slot in helpers}
    for slot in helpers:
        if auth.public_identity(auth.owner_slot_credentials(registry,slot))['physical_slot_id'] == witness['creator']['physical_slot_id']:
            raise ValueError('Study workers must use registered helper slots distinct from owner gold creator')
    pending = [fixture for fixture in registration['fixtures'] if fixture['id'] not in gold]
    # First assigned fixture for every (helper, focal source) is fixed before
    # any helper result. Auditor canaries are independently fixed at audit issue.
    canaries = []
    for index,_ in enumerate(helpers):
        seen = set()
        for fixture in pending[index::len(helpers)]:
            if fixture['candidate'] not in seen:
                canaries.append(fixture['id'])
                seen.add(fixture['candidate'])
    with p.ResultLease(output):
        distribution = owner.build_shards(dict(registration,fixtures=pending),output/'play',helpers,
                         role='extra_control_assignment',source_registration_sha256=p.sha(registration_path.read_bytes()),
                         registry=registry,approvals=approvals)
        plan = dict(format=p.FORMAT,role='extra_control_assignment',campaign_id=registration['campaign_id'],
                    generation=registration['generation'],source_registration_path=str(registration_path),
                    source_registration_sha256=p.sha(registration_path.read_bytes()),registry_path=str(Path(registry_path).resolve()),
                    helpers=list(helpers),runtime_approvals=approvals,distribution=distribution,
                    controller_sources=_pins(),qualification_context=owner.qualification_context(),owner_runtime=p.runtime(),
                    gold_witness_sha256=p.sha((registration_path.parent/'runtime_gold_v2/gold_witness.json').read_bytes()),
                    owner_canary_fixture_ids=sorted(set(canaries)|set(gold)),primary_games_accepted=0,bmcts_audits=0,
                    planned_extra_games=len(registration['fixtures']),production_promotion=False,
                    trust_model='Cooperative owner-assigned team; HMAC authenticates declarations, not compute or physical independence.')
        core.seal(output/'plan.json',_sign(registry,'plan',plan))
        _import_gold(plan,registry,registration,output)
    return plan


def _origin(plan,registry,registration,directory,bundles,path,maps=None):
    value = _read(registry,'origin',path)
    row,creator = value['game'],value['creator']
    candidates,fixtures = run.task_maps(registration) if maps is None else maps
    identity = row['fixture']
    if path.name != identity+'.json' or identity not in fixtures:
        raise ValueError('Foreign or renamed original game')
    run.runner.verify_row(row,candidates[fixtures[identity]['candidate']],fixtures[identity])
    if value['kind'] == 'owner_gold':
        witness,gold = qualification.read_control_gold(plan['source_registration_path'],registry)
        if (identity not in gold or value['source_gold_record'] != gold[identity] or value['game'] != gold[identity]['game']
                or creator != witness['creator'] or value['gold_witness_sha256'] != plan['gold_witness_sha256']):
            raise ValueError('Owner gold origin differs from its actual canonical row')
    elif value['kind'] == 'remote_play':
        bundle = bundles[value['shard_id']]
        header = value['play_header']
        from distributed_campaign import roles
        shard = next(item for item in plan['distribution']['shards'] if item['id'] == value['shard_id'])
        if (identity not in shard['fixture_ids'] or creator != header['slot'] or creator != bundle['target_slot']
                or header['bundle_sha256'] != shard['bundle_sha256'] or header['work_role'] != 'play'
                or header['campaign_id'] != plan['campaign_id'] or header['generation'] != plan['generation']
                or roles.runtime_fingerprint(header['runtime']) != roles.runtime_fingerprint(bundle['approved_runtime'])):
            raise ValueError('Authenticated original creator/source/runtime binding changed')
        if (auth.verify(registry,'distributed-worker-header/v2',header['authentication'],expected_slot=creator['slot_id']) != roles.header_payload(header)
                or auth.verify(registry,'distributed-result/play/v2',value['play_authentication'],expected_slot=creator['slot_id']) != roles.result_payload(bundle,header,row)):
            raise ValueError('Original PLAY evidence does not authenticate this row and creator')
    else:
        raise ValueError('Unknown original game provenance')
    return value


def _origins(plan,registry,registration,directory,bundles):
    maps = run.task_maps(registration)
    return {path.stem:_origin(plan,registry,registration,directory,bundles,path,maps)
            for path in sorted((directory/'origins').glob('*.json'))}


def ingest_play(plan_path,shard_id,result_directory):
    plan,registry,registration,directory,bundles = _load(plan_path)
    records,header,digest = owner.validate_result(plan,registration,shard_id,result_directory,registry)
    if bundles[shard_id]['work_role'] != 'play':
        raise ValueError('Only actual PLAY records create study games')
    entries = _returned_entries(result_directory,digest)
    with p.ResultLease(directory):
        _load(plan_path)
        new = 0
        for row in records:
            # The creator comes exclusively from the authenticated issued PLAY
            # header, never from helper-supplied audit labels.
            origin = dict(kind='remote_play',game=row,creator=header['slot'],shard_id=shard_id,
                          play_header=header,play_authentication=entries[row['fixture']]['authentication'])
            path = directory/'origins'/(row['fixture']+'.json')
            if path.exists():
                old = _origin(plan,registry,registration,directory,bundles,path)
                if old != origin:
                    raise ValueError('Conflicting repeated original row; exact original timing/provenance is immutable')
            else:
                core.seal(path,_sign(registry,'origin',origin))
                new += 1
        return dict(imported_actual_games=new,identical_duplicates=len(records)-new,accepted_extra_games=0,
                    primary_games_accepted=0,independent_peer_audit_pending=True,result_records_sha256=digest)


def prepare_audits(plan_path,output,helpers,approval_paths):
    """Issue actual original-row audit jobs, never qualification-row retags."""
    plan,registry,registration,directory,bundles = _load(plan_path)
    output = Path(output).resolve()
    if not output.is_relative_to(directory):
        raise ValueError('Audit assignments must stay inside their immutable owner plan')
    with p.ResultLease(directory):
        origins = _origins(plan,registry,registration,directory,bundles)
        if set(origins) != {fixture['id'] for fixture in registration['fixtures']}:
            raise ValueError('Issue peer audits only after complete original PLAY/gold coverage')
        if (output/'audit_plan.json').exists():
            existing = _read(registry,'audit-plan',output/'audit_plan.json')
            if existing['parent_plan_sha256'] != p.sha(Path(plan_path).read_bytes()) or existing['helpers'] != list(helpers):
                raise ValueError('Audit plan request changed')
            _audit_plan(plan_path,output/'audit_plan.json')
            return existing
        identities = {slot:auth.public_identity(auth.owner_slot_credentials(registry,slot)) for slot in helpers}
        if len(identities) != len(helpers) or not helpers:
            raise ValueError('Distinct registered audit helpers required')
        groups = {slot:[] for slot in helpers}
        for index,fixture in enumerate(registration['fixtures']):
            eligible = [slot for slot in helpers if identities[slot]['physical_slot_id'] != origins[fixture['id']]['creator']['physical_slot_id']]
            if not eligible:
                raise ValueError('Every original game needs a different physical helper auditor')
            groups[eligible[index%len(eligible)]].append(fixture)
        approvals = {slot:core.read_sealed(approval_paths[slot]) for slot in helpers}
        distribution,canaries = dict(shards=[],total_assigned_games=0),[]
        for index,slot in enumerate(helpers):
            tasks = groups[slot]
            if not tasks:
                continue
            seen = set()
            for fixture in tasks:
                if fixture['candidate'] not in seen:
                    canaries.append(fixture['id'])
                    seen.add(fixture['candidate'])
            issued = owner.build_shards(dict(registration,fixtures=tasks),output/('auditor_%02d'%index),[slot],
                       role='extra_control_assignment',source_registration_sha256=plan['source_registration_sha256'],
                       registry=registry,work_role='audit',approvals=approvals,
                       input_rows={identity:value['game'] for identity,value in origins.items()},
                       creators={identity:value['creator'] for identity,value in origins.items()})
            distribution['shards'] += issued['shards']
            distribution['total_assigned_games'] += len(tasks)
        audit_plan = dict(format=p.FORMAT,role=plan['role'],campaign_id=plan['campaign_id'],generation=plan['generation'],
                          registry_path=plan['registry_path'],helpers=list(helpers),distribution=distribution,
                          parent_plan_sha256=p.sha(Path(plan_path).read_bytes()),
                          origin_sha256={identity:p.sha((directory/'origins'/(identity+'.json')).read_bytes()) for identity in origins},
                          owner_canary_fixture_ids=sorted(set(canaries)),primary_games_accepted=0)
        core.seal(output/'audit_plan.json',_sign(registry,'audit-plan',audit_plan))
        return audit_plan


def _audit_plan(plan_path,audit_plan_path):
    plan,registry,registration,directory,bundles = _load(plan_path)
    audit = _read(registry,'audit-plan',audit_plan_path)
    if (audit['parent_plan_sha256'] != p.sha(Path(plan_path).read_bytes())
            or audit['campaign_id'] != plan['campaign_id'] or audit['generation'] != plan['generation']):
        raise ValueError('Peer audit belongs to another immutable control plan')
    origins = _origins(plan,registry,registration,directory,bundles)
    if set(audit['origin_sha256']) != set(origins):
        raise ValueError('Peer audit original coverage differs')
    for identity,digest in audit['origin_sha256'].items():
        if p.sha((directory/'origins'/(identity+'.json')).read_bytes()) != digest:
            raise ValueError('Original creator evidence changed after audit assignment')
    ids = []
    audit_bundles = {}
    for shard in audit['distribution']['shards']:
        bundle = p.verify_bundle(shard['bundle_directory'],shard['bundle_sha256'])
        if bundle['work_role'] != 'audit' or bundle['source_registration_sha256'] != plan['source_registration_sha256']:
            raise ValueError('Peer assignment work role/source registration changed')
        for identity in shard['fixture_ids']:
            origin = origins[identity]
            if (bundle['input_rows'][identity] != origin['game'] or bundle['creators'][identity] != origin['creator']
                    or origin['creator']['physical_slot_id'] == bundle['target_slot']['physical_slot_id']):
                raise ValueError('Audit row/original creator/different physical identity changed')
        ids += shard['fixture_ids']
        audit_bundles[shard['id']] = bundle
    if len(ids) != len(set(ids)) or set(ids) != set(origins):
        raise ValueError('Peer audit assignments have overlapping/incomplete task coverage')
    return plan,registry,registration,directory,audit,origins,audit_bundles


def ingest_audit(plan_path,audit_plan_path,shard_id,result_directory):
    plan,registry,registration,directory,audit,origins,bundles = _audit_plan(plan_path,audit_plan_path)
    records,header,digest = owner.validate_result(audit,registration,shard_id,result_directory,registry)
    entries = _returned_entries(result_directory,digest)
    with p.ResultLease(directory):
        _audit_plan(plan_path,audit_plan_path)
        new = 0
        for proof in records:
            identity = proof['fixture']
            evidence = dict(proof=proof,origin_sha256=audit['origin_sha256'][identity],auditor=header['slot'],
                            audit_plan_sha256=p.sha(Path(audit_plan_path).read_bytes()),audit_plan_path=str(Path(audit_plan_path).resolve()),
                            shard_id=shard_id,audit_header=header,audit_authentication=entries[identity]['authentication'],
                            origin='REMOTE cooperative full-actor/two-referee audit; owner physical replay plus independent canaries')
            path = directory/'peer_proofs'/(identity+'.json')
            signed = _sign(registry,'peer-proof',evidence)
            if not path.exists():
                core.seal(path,signed)
                new += 1
            elif _read(registry,'peer-proof',path) != evidence:
                raise ValueError('Conflicting immutable peer proof')
        return dict(imported_full_game_audits=new,identical_duplicates=len(records)-new,actual_actor_callbacks=new*320,
                    accepted_extra_games=0,primary_games_accepted=0,result_records_sha256=digest)


def finalize(plan_path,audit_plan_path):
    """Admit complete EXTRA coverage; never tune or deploy any policy."""
    plan,registry,registration,directory,audit,origins,bundles = _audit_plan(plan_path,audit_plan_path)
    from distributed_campaign import roles
    candidates,fixtures = run.task_maps(registration)
    audit_plan_sha = p.sha(Path(audit_plan_path).read_bytes())
    with p.ResultLease(directory):
        actual = {path.stem:path for path in (directory/'peer_proofs').glob('*.json')}
        if set(actual) != set(fixtures) or set(origins) != set(fixtures):
            raise ValueError('Every original study game must have its own actual authenticated peer proof')
        callbacks,oracles = 0,0
        for identity in fixtures:
            evidence = _read(registry,'peer-proof',actual[identity])
            bundle = bundles[evidence['shard_id']]
            header,proof = evidence['audit_header'],evidence['proof']
            creator = origins[identity]['creator']
            shard = next(item for item in audit['distribution']['shards'] if item['id'] == evidence['shard_id'])
            if (evidence['audit_plan_sha256'] != audit_plan_sha
                    or evidence['origin_sha256'] != audit['origin_sha256'][identity]
                    or evidence['auditor'] != header['slot'] or header['slot'] != bundle['target_slot']
                    or creator['physical_slot_id'] == header['slot']['physical_slot_id']
                    or identity not in shard['fixture_ids'] or header['bundle_sha256'] != shard['bundle_sha256']
                    or roles.runtime_fingerprint(header['runtime']) != roles.runtime_fingerprint(bundle['approved_runtime'])):
                raise ValueError('Full peer creator/auditor/runtime/assignment provenance changed')
            if (auth.verify(registry,'distributed-worker-header/v2',header['authentication'],expected_slot=header['slot']['slot_id']) != roles.header_payload(header)
                    or auth.verify(registry,'distributed-result/audit/v2',evidence['audit_authentication'],expected_slot=header['slot']['slot_id']) != roles.result_payload(bundle,header,proof)):
                raise ValueError('Actual independent auditor evidence failed authentication')
            proofs.validate(proof,origins[identity]['game'],candidates[fixtures[identity]['candidate']],fixtures[identity],registration['sources'])
            callbacks += proof['callbacks_regenerated']
            oracles += proof['public_memory_oracles']
        canaries = sorted(set(plan['owner_canary_fixture_ids'])|set(audit['owner_canary_fixture_ids']))
        new_canaries = 0
        for identity in canaries:
            path = directory/'owner_canaries'/(identity+'.json')
            row = origins[identity]['game']
            if path.exists():
                canary = _read(registry,'owner-canary',path)
                if canary['owner_runtime'] != plan['owner_runtime'] or canary['plan_sha256'] != p.sha(Path(plan_path).read_bytes()):
                    raise ValueError('Owner canary provenance changed')
                proofs.validate(canary['proof'],row,candidates[row['candidate']],fixtures[identity],registration['sources'])
            else:
                proof = run.audit_task(candidates[row['candidate']],fixtures[identity],registration['sources'],row)
                proofs.validate(proof,row,candidates[row['candidate']],fixtures[identity],registration['sources'])
                core.seal(path,_sign(registry,'owner-canary',dict(proof=proof,owner_runtime=plan['owner_runtime'],
                          plan_sha256=p.sha(Path(plan_path).read_bytes()))))
                new_canaries += 1
        rows = [origins[identity]['game'] for identity in fixtures]
        p.write_new(directory/'games.jsonl',b''.join(p.canonical(row)+b'\n' for row in rows))
        accepted = dict(format=p.FORMAT,role='extra_control_assignment',campaign_id=plan['campaign_id'],approved=True,
                        actual_extra_games=len(rows),primary_games_accepted=0,bmcts_audits=0,
                        study_registration_sha256=plan['source_registration_sha256'],plan_sha256=p.sha(Path(plan_path).read_bytes()),
                        audit_plan_sha256=p.sha(Path(audit_plan_path).read_bytes()),games_sha256=p.sha((directory/'games.jsonl').read_bytes()),
                        remote_full_actor_callbacks=callbacks,remote_public_memory_oracles=oracles,
                        owner_canary_games=len(canaries),owner_canary_callbacks=len(canaries)*320,
                        all_original_rows_physically_replayed=True,all_actual_original_rows_have_different_slot_peer_audit=True,
                        gold_study_cases_counted_once=8,qualification_replica_games_credited=0,
                        production_promoted=False,trust_model=plan['trust_model'])
        core.seal(directory/'acceptance.json',_sign(registry,'acceptance',accepted))
        core.seal(Path(plan['source_registration_path']).parent/'distributed_control_v2/acceptance.json',
                  _sign(registry,'study-acceptance',dict(canonical_output=str(directory),
                        acceptance_sha256=p.sha((directory/'acceptance.json').read_bytes()),
                        source_registration_sha256=plan['source_registration_sha256'],
                        actual_extra_games=len(rows),primary_games_accepted=0)))
        return dict(acceptance=accepted,new_owner_canary_jobs=new_canaries)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command',required=True)
    make = commands.add_parser('prepare')
    make.add_argument('--registration',type=Path,required=True)
    make.add_argument('--registry',type=Path,required=True)
    make.add_argument('--output',type=Path,required=True)
    make.add_argument('--helpers',nargs='+',required=True)
    make.add_argument('--approval',nargs='+',required=True,help='slot=owner approval JSON')
    for command in ('ingest-play','prepare-audits','ingest-audit','finalize'):
        sub = commands.add_parser(command)
        sub.add_argument('--plan',type=Path,required=True)
        if command in ('prepare-audits',):
            sub.add_argument('--output',type=Path,required=True)
            sub.add_argument('--helpers',nargs='+',required=True)
            sub.add_argument('--approval',nargs='+',required=True)
        if command in ('ingest-play','ingest-audit'):
            sub.add_argument('--shard',required=True)
            sub.add_argument('--results',type=Path,required=True)
        if command in ('ingest-audit','finalize'):
            sub.add_argument('--audit-plan',type=Path,required=True)
    args = parser.parse_args()
    approvals = dict(item.split('=',1) for item in args.approval) if hasattr(args,'approval') else None
    if args.command == 'prepare':
        result = prepare(args.registration,args.registry,args.output,args.helpers,approvals)
    elif args.command == 'ingest-play':
        result = ingest_play(args.plan,args.shard,args.results)
    elif args.command == 'prepare-audits':
        result = prepare_audits(args.plan,args.output,args.helpers,approvals)
    elif args.command == 'ingest-audit':
        result = ingest_audit(args.plan,args.audit_plan,args.shard,args.results)
    else:
        result = finalize(args.plan,args.audit_plan)
    print(p.canonical(result).decode(),flush=True)


if __name__ == '__main__':
    main()
