"""Explicit finite runtime compatibility, rather than forcing Python reinstalls."""
import argparse
from pathlib import Path
import re

from distributed_campaign import auth, owner, protocol as p, roles, proofs
from primary_campaign import core, run


def prepare(source_stage, registry_path, output, slots=None):
    stage, output = Path(source_stage).resolve(), Path(output).resolve()
    registry = auth.load_registry(registry_path)
    identities = auth.public_slots(registry)
    slots = sorted(identities) if slots is None else list(slots)
    registration = core.read_sealed(stage/'registration.json')
    match = re.fullmatch(r'train_(\d{3})', stage.name)
    if match is None or type(registration.get('generation')) is not int or registration['generation'] != int(match.group(1)):
        raise ValueError('Qualification source directory/generation identity changed')
    # Once per golden source construction, not once per helper or primary game:
    # validate real full source coverage/exports/physical replay/individual proofs.
    audit = core.validated_audit(stage)
    if (audit['approved'] is not True or audit['registration_sha256'] != p.sha((stage/'registration.json').read_bytes())
            or audit['games_sha256'] != p.sha((stage/'games.jsonl').read_bytes())
            or audit['actor_audits_sha256'] != p.sha((stage/'actor_audits.jsonl').read_bytes())):
        raise ValueError('Qualification requires an existing independently admitted source cohort')
    selected = []
    fields = list(core.FIELDS)
    for index, candidate in enumerate(registration['candidates']):
        selected.append(next(fixture for fixture in registration['fixtures']
                             if fixture['candidate'] == candidate['sha256'] and fixture['field'] == fields[index % len(fields)]))
    if len(selected) != 8 or len({fixture['candidate'] for fixture in selected}) != 8:
        raise ValueError('Qualification must cover exactly8 distinct current-policy genotypes')
    wanted, expected = {fixture['id'] for fixture in selected}, {}
    with (stage/'games.jsonl').open(encoding='utf8') as handle:
        for line in handle:
            row = p.loads(line)
            if row['fixture'] in wanted:
                expected[row['fixture']] = row
    if set(expected) != wanted:
        raise ValueError('Qualification source records are incomplete')
    candidates = {candidate['sha256']:candidate for candidate in registration['candidates']}
    for fixture in selected:
        # Establish these exact golden histories with fresh actors in the
        # reference runtime, rather than blessing an aggregate approval flag.
        run.audit_task(candidates[fixture['candidate']], fixture, registration['sources'], expected[fixture['id']])
    output.mkdir(parents=True, exist_ok=False)
    packets = []
    for slot in slots:
        if slot not in identities:
            raise ValueError('Unknown physical helper slot')
        subset = dict(registration, fixtures=selected)
        distribution = owner.build_shards(subset, output/slot, [slot], role='runtime_qualification',
                    source_registration_sha256=p.sha((stage/'registration.json').read_bytes()), registry=registry,
                    work_role='qualify', expected_rows=expected)
        shard = distribution['shards'][0]
        packet = dict(format=p.FORMAT, role='runtime_qualification', slot=identities[slot],
                      registry_path=str(Path(registry_path).resolve()), campaign_id=registration['campaign_id'],
                      generation=registration['generation'], owner_runtime=p.runtime(), distribution=distribution,
                      qualification_context=owner.qualification_context(), minimum_games=8,
                      source_registration_sha256=p.sha((stage/'registration.json').read_bytes()),
                      source_stage=str(stage), primary_games_accepted=0)
        packet['focal_sources'] = sorted({fixture['candidate'] for fixture in selected})
        packet['numeric_policy_family_qualified'] = True
        packet['policy_logic_sha256'] = owner.qualification_context()['policy_logic_sha256']
        packet['authentication'] = auth.sign_owner(registry, 'distributed-qualification-packet/v2',
                        {key:value for key,value in packet.items() if key != 'authentication'})
        core.seal(output/slot/'qualification_packet.json', packet)
        packets.append(dict(slot=slot, packet=str(output/slot/'qualification_packet.json'),
                            archive=shard['archive'], archive_sha256=shard['archive_sha256']))
    return dict(packets=packets, actual_primary_games_created=0, runtime_reinstall_required=False)


def approve(packet_path, results, registry_path, output):
    packet = core.read_sealed(packet_path)
    registry = auth.load_registry(registry_path)
    expected_packet = {key:value for key,value in packet.items() if key != 'authentication'}
    if auth.verify_owner(registry, 'distributed-qualification-packet/v2', packet['authentication']) != expected_packet:
        raise ValueError('Qualification packet was not issued by this owner')
    if packet['qualification_context'] != owner.qualification_context():
        raise ValueError('Qualification helper/policy source family changed')
    registration_path = Path(packet['source_registration_path']) if 'source_registration_path' in packet else Path(packet['source_stage'])/'registration.json'
    registration = core.read_sealed(registration_path)
    if p.sha(registration_path.read_bytes()) != packet['source_registration_sha256']:
        raise ValueError('Qualification source registration changed')
    shard = packet['distribution']['shards'][0]
    records, header, records_sha = owner.validate_result(packet, registration, shard['id'], results, registry)
    if (len(records) != 8 or {record['game']['candidate'] for record in records} != set(packet['focal_sources'])
            or not roles.allowed_qualification_runtime(header['runtime'])):
        raise ValueError('Runtime qualification is incomplete or outside CPython3.12.x')
    # The owner checks exact known canonical behavior and physical scores; the
    # helper actually repeated every actor in two referees. No universal claim.
    candidate_by_id = {candidate['sha256']:candidate for candidate in registration['candidates']}
    fixture_by_id = {fixture['id']:fixture for fixture in registration['fixtures']}
    for record in records:
        row = record['game']
        run.runner.verify_row(row, candidate_by_id[row['candidate']], fixture_by_id[row['fixture']])
        proofs.validate(record['audit'],row,candidate_by_id[row['candidate']],fixture_by_id[row['fixture']],registration['sources'])
    approval = dict(format=p.FORMAT, slot=header['slot'], runtime=header['runtime'], approved=True,
                    all_recorded_actions_equal=True, full_audit_callbacks=8*320,
                    qualification_packet_sha256=p.sha(Path(packet_path).read_bytes()),
                    result_records_sha256=records_sha, qualification_context=owner.qualification_context(),
                    canaries_required=True, finite_qualification=True, primary_games_accepted=0,
                    focal_sources=packet['focal_sources'],
                    numeric_policy_family_qualified=packet['numeric_policy_family_qualified'],
                    policy_logic_sha256=packet['policy_logic_sha256'],
                    claim='This exact CPython3.12 patch/build passed8known full games and allactor/two-referee replay; not universal cross-version equivalence.')
    envelope = auth.sign_owner(registry, 'distributed-runtime-approval/v2', approval)
    core.seal(output, envelope)
    return dict(approval_path=str(Path(output).resolve()), slot=header['slot'], runtime=header['runtime'],
                qualification_games=8, full_audit_callbacks=2560, primary_games_accepted=0,
                no_global_reinstall=True, canaries_required=True)


def prepare_control(registration_path, registry_path, output, owner_slot, slots=None):
    gold = Path(registration_path).resolve().parent/'runtime_gold_v2'
    output = Path(output).resolve()
    if output.is_relative_to(gold) or gold.is_relative_to(output):
        raise ValueError('Helper package output must be separate from canonical study gold')
    with p.ResultLease(output):
        return _prepare_control_locked(registration_path,registry_path,output,owner_slot,slots)


def _prepare_control_locked(registration_path, registry_path, output, owner_slot, slots=None):
    """Consume the eight PREREGISTERED study tasks as real owner-created goldens.

    These outcomes belong to the study once. Helper qualification/audit replicas
    never add study or primary game credit. No source/outcome adaptation occurs.
    """
    from confirmation_campaign import architectures
    registration_path, output = Path(registration_path).resolve(), Path(output).resolve()
    registry = auth.load_registry(registry_path)
    registration = core.read_sealed(registration_path)
    architectures.validate(registration)
    wanted = registration['runtime_qualification_task_ids']
    fixtures = {fixture['id']:fixture for fixture in registration['fixtures']}
    required = set(registration['required_focal_sources'])
    if len(wanted) != 8 or len(set(wanted)) != 8 or {fixtures[x]['candidate'] for x in wanted} != required:
        raise ValueError('Frozen architecture qualification IDs do not cover every required exact source')
    creator = auth.public_identity(auth.owner_slot_credentials(registry,owner_slot))
    candidates = {candidate['sha256']:candidate for candidate in registration['candidates']}
    # The STUDY owns these outcomes. A different package output cannot rerun
    # them; a missing/replaced committed row cannot silently be regenerated.
    gold = registration_path.parent/'runtime_gold_v2'
    study_sha = p.sha(registration_path.read_bytes())
    gold_binding = dict(study_registration_sha256=study_sha,task_ids=wanted,
              required_focal_sources=registration['required_focal_sources'],creator=creator,
              runtime=p.runtime(),qualification_context=owner.qualification_context(),
              rule='Exactly these eight frozen study outcomes, consumed once before adaptation.')
    new_games = 0
    with p.ResultLease(gold):
        binding_path = gold/'gold_registration.json'
        if binding_path.exists():
            binding = auth.verify_owner(registry,'distributed-control-gold-registration/v2',core.read_sealed(binding_path))
            if binding != gold_binding:
                raise ValueError('Canonical study gold source/runtime/creator changed; never rerun consumed cases')
        else:
            core.seal(binding_path,auth.sign_owner(registry,'distributed-control-gold-registration/v2',gold_binding))
        if (gold/'gold_witness.json').exists():
            # Completed consumption is irreversible. Check it BEFORE any
            # recovery/truncation or callback can reinterpret corruption as work.
            read_control_gold(registration_path,registry)
        records, expected = [], {}
        for envelope in p.complete_rows(gold/'gold_records.jsonl',recover=True):
            value = auth.verify_owner(registry,'distributed-control-gold-record/v2',envelope)
            if value['study_registration_sha256'] != study_sha or value['creator'] != creator:
                raise ValueError('Foreign gold outcome or creator')
            row,proof = value['game'],value['audit']
            identity = row['fixture']
            if identity not in wanted or identity in expected:
                raise ValueError('Duplicate or foreign committed gold outcome')
            run.runner.verify_row(row,candidates[fixtures[identity]['candidate']],fixtures[identity])
            proofs.validate(proof,row,candidates[fixtures[identity]['candidate']],fixtures[identity],registration['sources'])
            expected[identity] = row
            records.append(value)
        # A marker survives a crash between computation and fsync. Such a
        # case is deliberately fail-closed rather than observing it twice.
        for identity in wanted:
            marker = gold/'started'/(identity+'.json')
            if marker.exists() and identity not in expected:
                raise ValueError('Interrupted in-flight gold outcome requires explicit recovery review; it will not be rerun')
        with (gold/'gold_records.jsonl').open('ab') as handle:
          for identity in wanted:
            if identity in expected:
                continue
            fixture = fixtures[identity]
            candidate = candidates[fixture['candidate']]
            core.seal(gold/'started'/(identity+'.json'),auth.sign_owner(registry,'distributed-control-gold-start/v2',
                       dict(study_registration_sha256=study_sha,fixture=identity,creator=creator)))
            row = run.runner.play_game(candidate,fixture,registration['sources'])
            run.runner.verify_row(row,candidate,fixture)
            proof = run.audit_task(candidate,fixture,registration['sources'],row)
            proofs.validate(proof,row,candidate,fixture,registration['sources'])
            value = dict(game=row,audit=proof,creator=creator,study_registration_sha256=study_sha)
            run.append(handle,auth.sign_owner(registry,'distributed-control-gold-record/v2',value))
            records.append(value)
            expected[identity] = row
            new_games += 1
        witness = dict(format=p.FORMAT,role='owner_generated_control_gold',study_registration_sha256=study_sha,
                   source_registration_path=str(registration_path),task_ids=wanted,creator=creator,
                   records_sha256=p.sha((gold/'gold_records.jsonl').read_bytes()),actual_study_games=8,
                   full_audit_callbacks=2560,primary_games_accepted=0,qualification_context=owner.qualification_context(),
                   runtime=p.runtime(),different_physical_peer_audit_still_required_for_distributed_study=True)
        signed = auth.sign_owner(registry,'distributed-control-gold-witness/v2',witness)
        core.seal(gold/'gold_witness.json',signed)
    # Packaging is repeatable from authenticated, already-consumed goldens.
    # Existing complete output is checked rather than reissuing assignments.
    if (output/'packets.json').exists():
        packaged = core.read_sealed(output/'packets.json')
        payload = auth.verify_owner(registry,'distributed-control-gold-packages/v2',packaged)
        if (payload['gold_witness_sha256'] != p.sha((gold/'gold_witness.json').read_bytes())
                or payload['requested_slots'] != (sorted(auth.public_slots(registry)) if slots is None else list(slots))):
            raise ValueError('Existing package request differs from immutable gold witness')
        for item in payload['packets']:
            packet = core.read_sealed(item['packet'])
            if auth.verify_owner(registry,'distributed-qualification-packet/v2',packet['authentication']) != {k:v for k,v in packet.items() if k != 'authentication'}:
                raise ValueError('Existing qualification package changed')
            for shard in packet['distribution']['shards']:
                p.verify_bundle(shard['bundle_directory'],shard['bundle_sha256'])
                if p.sha(Path(shard['archive']).read_bytes()) != shard['archive_sha256']:
                    raise ValueError('Existing qualification archive changed')
        return dict(gold_witness=str(gold/'gold_witness.json'),actual_study_games_consumed=8,
                    newly_executed_study_games=new_games,owner_full_audit_callbacks=2560,primary_games_accepted=0,packets=payload['packets'])
    output.mkdir(parents=True,exist_ok=True)
    packets = []
    identities = auth.public_slots(registry)
    for slot in (sorted(identities) if slots is None else list(slots)):
        if slot == owner_slot:
            continue
        subset = dict(registration,fixtures=[fixtures[x] for x in wanted])
        distribution = owner.build_shards(subset,output/slot,[slot],role='runtime_qualification',
                        source_registration_sha256=p.sha(registration_path.read_bytes()),registry=registry,
                        work_role='qualify',expected_rows=expected)
        packet = dict(format=p.FORMAT,role='runtime_qualification',slot=identities[slot],registry_path=str(Path(registry_path).resolve()),
                      campaign_id=registration['campaign_id'],generation=registration['generation'],owner_runtime=p.runtime(),
                      distribution=distribution,qualification_context=owner.qualification_context(),minimum_games=8,
                      source_stage=str(registration_path.parent),source_registration_path=str(registration_path),
                      source_registration_sha256=p.sha(registration_path.read_bytes()),primary_games_accepted=0,
                      focal_sources=registration['required_focal_sources'],numeric_policy_family_qualified=False,
                      policy_logic_sha256=owner.qualification_context()['policy_logic_sha256'],
                      gold_witness_sha256=p.sha((gold/'gold_witness.json').read_bytes()),gold_witness=str(gold/'gold_witness.json'))
        packet['authentication'] = auth.sign_owner(registry,'distributed-qualification-packet/v2',packet)
        core.seal(output/slot/'qualification_packet.json',packet)
        packets.append(dict(slot=slot,packet=str(output/slot/'qualification_packet.json'),distribution=distribution))
    core.seal(output/'packets.json',auth.sign_owner(registry,'distributed-control-gold-packages/v2',
              dict(gold_witness_sha256=p.sha((gold/'gold_witness.json').read_bytes()),
                   requested_slots=sorted(identities) if slots is None else list(slots),packets=packets)))
    return dict(gold_witness=str(gold/'gold_witness.json'),actual_study_games_consumed=8,
                newly_executed_study_games=new_games,owner_full_audit_callbacks=2560,primary_games_accepted=0,packets=packets)


def read_control_gold(registration_path, registry):
    """Read original owner-created rows; never execute or re-tag a replica."""
    registration_path = Path(registration_path).resolve()
    registration = core.read_sealed(registration_path)
    gold = registration_path.parent/'runtime_gold_v2'
    witness = auth.verify_owner(registry,'distributed-control-gold-witness/v2',core.read_sealed(gold/'gold_witness.json'))
    binding = auth.verify_owner(registry,'distributed-control-gold-registration/v2',core.read_sealed(gold/'gold_registration.json'))
    study_sha = p.sha(registration_path.read_bytes())
    if (witness['study_registration_sha256'] != study_sha or binding['study_registration_sha256'] != study_sha
            or witness['task_ids'] != registration['runtime_qualification_task_ids']
            or binding['task_ids'] != witness['task_ids'] or binding['creator'] != witness['creator']
            or witness['qualification_context'] != owner.qualification_context()
            or witness['records_sha256'] != p.sha((gold/'gold_records.jsonl').read_bytes())
            or witness['actual_study_games'] != 8 or witness['full_audit_callbacks'] != 2560):
        raise ValueError('Canonical consumed study gold witness changed')
    candidates, fixtures = run.task_maps(registration)
    records = {}
    for envelope in p.complete_rows(gold/'gold_records.jsonl'):
        value = auth.verify_owner(registry,'distributed-control-gold-record/v2',envelope)
        row = value['game']
        identity = row['fixture']
        if identity not in witness['task_ids'] or identity in records or value['creator'] != witness['creator'] or value['study_registration_sha256'] != study_sha:
            raise ValueError('Foreign, duplicate or rebound gold record')
        run.runner.verify_row(row,candidates[row['candidate']],fixtures[identity])
        proofs.validate(value['audit'],row,candidates[row['candidate']],fixtures[identity],registration['sources'])
        records[identity] = value
    if set(records) != set(witness['task_ids']):
        raise ValueError('Canonical gold task coverage is incomplete')
    return witness,records


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    make = commands.add_parser('prepare')
    make.add_argument('--source-stage', type=Path, required=True)
    make.add_argument('--registry', type=Path, required=True)
    make.add_argument('--output', type=Path, required=True)
    approve_cmd = commands.add_parser('approve')
    approve_cmd.add_argument('--packet', type=Path, required=True)
    approve_cmd.add_argument('--results', type=Path, required=True)
    approve_cmd.add_argument('--registry', type=Path, required=True)
    approve_cmd.add_argument('--output', type=Path, required=True)
    controls = commands.add_parser('prepare-control')
    controls.add_argument('--registration',type=Path,required=True)
    controls.add_argument('--registry',type=Path,required=True)
    controls.add_argument('--output',type=Path,required=True)
    controls.add_argument('--owner-slot',required=True)
    controls.add_argument('--slots',nargs='+')
    args = parser.parse_args()
    if args.command == 'prepare':
        value = prepare(args.source_stage,args.registry,args.output)
    elif args.command == 'prepare-control':
        value = prepare_control(args.registration,args.registry,args.output,args.owner_slot,args.slots)
    else:
        value = approve(args.packet,args.results,args.registry,args.output)
    print(p.canonical(value).decode(), flush=True)


if __name__ == '__main__':
    main()
