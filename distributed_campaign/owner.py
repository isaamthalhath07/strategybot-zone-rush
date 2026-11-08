"""Future owner planning/import for genuine offline primary game execution.

Creating a PRIMARY plan requires the old owner to have exited and an OS lease.
No helper result or unsigned progress count admits a primary game: the original
complete all-actor/two-referee owner audit remains the final admission gate.
"""
import argparse
import copy
import json
import os
from pathlib import Path
import zipfile

from campaign_monitor import audit as monitor
from campaign_monitor import guarded_run as guarded
from distributed_campaign import protocol as p, roles, proofs
from primary_campaign import core, run

ROOT = core.ROOT
CODE_FILES = (
    'distributed_campaign/__init__.py', 'distributed_campaign/protocol.py', 'distributed_campaign/worker.py',
    'distributed_campaign/roles.py',
    'evolution/__init__.py', 'evolution/runner.py', 'evolution/genomes.py', 'evolution/maps.py',
    'evolution/opponents.py', 'evolution/oversight.py', 'tests/__init__.py', 'tests/reference_engine.py',
    'simulator/vendor_harness/referee.py',
)
BEHAVIOR_FIELDS = ('candidate', 'fixture', 'map_id', 'focal_seat', 'field', 'scores', 'focal_pw',
                   'focal_score', 'opponent_ids', 'actions', 'faults')


def qualification_context():
    from evolution import oversight
    logic, _ = oversight.stripped_tree((ROOT/'bot.py').read_bytes())
    paths = [relative for relative in CODE_FILES if not relative.endswith('__init__.py')]
    paths += ['distributed_campaign/auth.py', 'campaign_holdout/authority.py']
    # Exact helper/referee/rival sources, with the evolving numerical CONFIG
    # separated from the common focal policy logic.
    paths += ['tester_bots/racer.py', 'tester_bots/blocker.py', 'tester_bots/research_alternative.py']
    return dict(policy_logic_sha256=p.sha(logic.encode()), sources={relative:p.sha((ROOT/relative).read_bytes()) for relative in paths})


def approved_runtime(registry, slot, envelope, candidate_entries=()):
    from distributed_campaign import auth
    value = auth.verify_owner(registry, 'distributed-runtime-approval/v2', envelope)
    identity = auth.public_identity(auth.owner_slot_credentials(registry, slot))
    if (value['slot'] != identity or value['qualification_context'] != qualification_context()
            or value['approved'] is not True or value['all_recorded_actions_equal'] is not True
            or value['full_audit_callbacks'] < 8*320 or value['canaries_required'] is not True
            or not roles.allowed_qualification_runtime(value['runtime'])):
        raise ValueError('Runtime approval does not cover this physical slot/source family')
    from evolution import oversight
    for candidate in candidate_entries:
        if candidate['sha256'] in value['focal_sources']:
            continue
        if value.get('numeric_policy_family_qualified') is not True:
            raise ValueError('This new focal architecture needs its own executed qualification goldens')
        body = Path(candidate['path']).read_bytes()
        from evolution.genomes import GenomeSpace
        try:
            template = GenomeSpace((ROOT/'bot.py').read_bytes())
            genes = GenomeSpace(body).genes
            if body != template.export(genes):
                raise ValueError('Not an exact numeric policy export')
        except Exception as error:
            raise ValueError('Numeric runtime qualification requires the exact validated policy export') from error
        logic, _ = oversight.stripped_tree(body)
        if p.sha(logic.encode()) != value['policy_logic_sha256']:
            raise ValueError('Numeric-only qualification does not cover this structural focal source')
    return value['runtime']


def build_shards(registration, output, helpers, role='mechanics_shadow', source_registration_sha256=None,
                 registry=None, work_role='play', approvals=None, input_rows=None, creators=None, expected_rows=None):
    """Pure packaging helper. A shadow package can NEVER be ingested as primary."""
    if role not in ('mechanics_shadow', 'primary_assignment', 'extra_control_assignment', 'runtime_qualification') or not 1 <= len(helpers) <= 32 or len(set(helpers)) != len(helpers):
        raise ValueError('Distinct helper labels and an explicit supported role are required')
    if any(type(name) is not str or not name or len(name) > 100 for name in helpers):
        raise ValueError('Invalid helper label')
    if work_role not in ('play','audit','qualify') or (role == 'runtime_qualification') != (work_role == 'qualify'):
        raise ValueError('Assignment role and work role differ')
    if role != 'mechanics_shadow' and registry is None:
        raise ValueError('Real/helper qualification assignments require registered private credentials')
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    runtime = p.runtime()
    candidates = {value['sha256']: value for value in registration['candidates']}
    tasks = registration['fixtures']
    if len({task['id'] for task in tasks}) != len(tasks):
        raise ValueError('Duplicate planned task')
    shards = []
    for index, helper in enumerate(helpers):
        assigned = tasks[index::len(helpers)]  # Interleave policies/maps across helpers.
        if not assigned:
            raise ValueError('Every helper must have real assigned tasks')
        directory = output/('helper_%02d' % index)
        directory.mkdir()
        files = {}
        code_files = list(CODE_FILES)
        if role != 'mechanics_shadow':
            code_files += ['distributed_campaign/auth.py','campaign_holdout/__init__.py','campaign_holdout/authority.py']
            from distributed_campaign import auth
            credential = auth.owner_slot_credentials(registry, helper)
            target = auth.public_identity(credential)
        else:
            target = dict(slot_id=helper, physical_slot_id='shadow_'+helper)
        for relative in code_files:
            body = (ROOT/relative).read_bytes()
            p.write_new(p.safe_path(directory, relative), body)
            files[relative] = p.sha(body)
        packaged_candidates = []
        for identity in sorted({task['candidate'] for task in assigned}):
            candidate = candidates[identity]
            body = Path(candidate['path']).read_bytes()
            if p.sha(body) != identity:
                raise ValueError('Candidate body changed during packaging')
            relative = 'candidates/'+identity+'.py'
            p.write_new(p.safe_path(directory, relative), body)
            files[relative] = identity
            packaged_candidates.append(dict(candidate, path=relative))
        sources = {}
        for family, source in registration['sources'].items():
            body = Path(source['path']).read_bytes()
            if p.sha(body) != source['sha256']:
                raise ValueError('Rival source changed during packaging')
            relative = 'sources/'+family+'_'+source['sha256']+'.py'
            p.write_new(p.safe_path(directory, relative), body)
            files[relative] = source['sha256']
            sources[family] = dict(source, path=relative)
        shard_id = p.sha(p.canonical(dict(campaign=registration['campaign_id'], generation=registration['generation'],
                                          helper_index=index, helper_label=helper, work_role=work_role,
                                          fixture_ids=[task['id'] for task in assigned], role=role)))
        bundle = dict(format=p.FORMAT, role=role, campaign_id=registration['campaign_id'],
                      generation=registration['generation'], source_registration_sha256=source_registration_sha256,
                      shard_id=shard_id, helper_label=helper, owner_runtime=runtime, files=files,
                      candidates=packaged_candidates, sources=sources, fixtures=assigned,
                      worker_primary_credit=0, bmcts_audits=0, cuda_used_by_policy=False,
                      work_role=work_role, target_slot=target,
                      owner_independent_audit_required=True)
        if work_role == 'qualify':
            bundle['expected_rows'] = {task['id']:expected_rows[task['id']] for task in assigned}
            bundle['qualification_context'] = qualification_context()
        elif role != 'mechanics_shadow':
            bundle['approved_runtime'] = approved_runtime(registry, helper, approvals[helper],
                    [candidates[identity] for identity in sorted({task['candidate'] for task in assigned})])
        if work_role == 'audit':
            bundle['input_rows'] = {task['id']:input_rows[task['id']] for task in assigned}
            bundle['creators'] = {task['id']:creators[task['id']] for task in assigned}
            if any(value['physical_slot_id'] == target['physical_slot_id'] for value in bundle['creators'].values()):
                raise ValueError('A physical helper cannot be its own independent auditor')
        if role != 'mechanics_shadow':
            bundle['authentication'] = auth.sign(credential, 'distributed-assignment/v2', roles.assignment_payload(bundle))
        p.json_new(directory/'bundle.json', bundle)
        manifest_sha = p.sha((directory/'bundle.json').read_bytes())
        p.write_new(directory/'bundle.sha256', (manifest_sha+'\n').encode('ascii'))
        heading = {'play':'ACTUAL ASSIGNED FULL MATCHES (CPU policy; owner acceptance pending)',
                   'qualify':'RUNTIME QUALIFICATION (known full matches plus independent audits; zero primary credit)',
                   'audit':'INDEPENDENT FULL-GAME AUDIT (all actors/two referees; zero additional games)'}[work_role]
        instructions = (heading+'\n\n'+
            'Verify the ZIP SHA supplied by the owner, unzip, and open a terminal in this folder.\n'
            'No torch/CUDA installation is needed for these actual Python actor tasks.\n'+
            ('This is runtime qualification: existing CPython3.12.x is tested, with no global reinstall.\n' if work_role == 'qualify'
             else 'Use your explicitly qualified existing CPython runtime; a changed runtime must qualify again.\n')+
            'Run:\npython -m distributed_campaign.worker --root . --expected-manifest-sha '+manifest_sha+
            ' --output results --workers 2'+('' if role == 'mechanics_shadow' else ' --credentials PRIVATE_FOLDER/credential.json --secure-credentials')+
            '\n\n'+('' if role == 'mechanics_shadow' else
             'First put ONLY your separately provided credential.json in a fresh dedicated PRIVATE_FOLDER.\n'
             'The explicit --secure-credentials flag restricts that folder to your account; do not use Downloads or the whole package folder.\n'
             'Never return, upload or share the private credential folder.\n')+
            'Run the same command to resume. Return only the complete results folder.\n'
            'The GPU is not used by this Python policy; these are real assigned games on your CPU.\n'
            'Do not change sources, seeds, maps, candidate files or bundle.json.\n')
        p.write_new(directory/'RUN_INSTRUCTIONS.txt', instructions.encode('utf8'))
        archive = output/('helper_%02d.zip' % index)
        with zipfile.ZipFile(archive, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zipped:
            for path in sorted(directory.rglob('*')):
                if path.is_file():
                    zipped.write(path, path.relative_to(directory).as_posix())
        shards.append(dict(id=shard_id, helper_label=helper, bundle_directory=str(directory),
                           bundle_sha256=manifest_sha, archive=str(archive), archive_sha256=p.sha(archive.read_bytes()),
                           fixture_ids=[task['id'] for task in assigned], games=len(assigned)))
    if {task for shard in shards for task in shard['fixture_ids']} != {task['id'] for task in tasks}:
        raise ValueError('Distribution omitted a task')
    return dict(shards=shards, total_assigned_games=len(tasks))


def prepare_plan(campaign, index, helpers, output, handoff, registry_path, approval_paths):
    from distributed_campaign import auth
    campaign = Path(campaign).resolve()
    output = Path(output).resolve()
    if not output.is_relative_to((ROOT/'.cache/distributed_campaign').resolve()):
        raise ValueError('Generated helper plans/packages must stay in the ignored distributed cache')
    if (output/'plan.json').exists():
        existing, existing_campaign, _, _ = load_plan(output/'plan.json')
        if (existing_campaign != campaign or existing['generation'] != index
                or [item['helper_label'] for item in existing['distribution']['shards']] != list(helpers)):
            raise ValueError('Existing immutable plan belongs to another request')
        return existing
    pins = guarded.provenance()
    registry = auth.load_registry(registry_path)
    approvals = {slot:core.read_sealed(path) for slot,path in approval_paths.items()}
    manifest, _ = core.load_catalog(campaign)
    if manifest['profile'] != 'full_primary':
        raise ValueError('Actual primary sharing requires the full immutable campaign profile')
    guarded.verify_handoff(handoff, campaign, manifest['campaign_id'])
    with guarded.CoordinatorLease(campaign):
        before = monitor.inspect(campaign)
        guarded.boundary(before, index, index+1)
        guarded.verify_handoff(handoff, campaign, manifest['campaign_id'])
        guarded.requested_registration(campaign, index, allow_missing=True)
        core.prepare_generation(campaign, index)
        registration = guarded.requested_registration(campaign, index)
        stage = campaign/('train_%03d' % index)
        if ((stage/'summary.json').exists() or (stage/'audit.json').exists()
                or ((stage/'games.jsonl').exists() and (stage/'games.jsonl').stat().st_size)):
            raise ValueError('Only a fresh unexecuted stage can be distributed by this protocol')
        sha = p.sha((stage/'registration.json').read_bytes())
        distribution = build_shards(registration, output, helpers, 'primary_assignment', sha,
                                    registry=registry, approvals=approvals)
        guarded.check_provenance(pins)
        plan = dict(format=p.FORMAT, role='primary_assignment', campaign_directory=str(campaign),
                    campaign_id=manifest['campaign_id'], generation=index, source_registration_sha256=sha,
                    owner_provenance=pins, owner_runtime=p.runtime(), distribution=distribution,
                    registry_path=str(Path(registry_path).resolve()), runtime_approvals=approvals,
                    distribution_source_pins={str(path.resolve()): p.sha(path.read_bytes())
                                              for path in (ROOT/'distributed_campaign').glob('*.py')
                                              if not path.name.startswith('test_')},
                    owner_game_execution_offloaded=True, owner_full_independent_audit_required=True,
                    cuda_used_by_policy=False, primary_games_accepted=0, bmcts_audits=0)
        plan['authentication'] = auth.sign_owner(registry, 'distributed-primary-plan/v2',
                           {key:value for key,value in plan.items() if key != 'authentication'})
        core.seal(Path(output)/'plan.json', plan)
        return plan


def load_plan(path):
    from distributed_campaign import auth
    path = Path(path)
    plan = core.read_sealed(path)
    if plan['format'] != p.FORMAT or plan['role'] != 'primary_assignment':
        raise ValueError('Shadow/unknown packages cannot supply primary results')
    registry = auth.load_registry(plan['registry_path'])
    if auth.verify_owner(registry, 'distributed-primary-plan/v2', plan['authentication']) != {key:value for key,value in plan.items() if key != 'authentication'}:
        raise ValueError('Primary distribution plan is not this owner-authorized immutable assignment')
    guarded.check_provenance(plan['owner_provenance'])
    for source, expected in plan['distribution_source_pins'].items():
        if p.sha(Path(source).read_bytes()) != expected:
            raise ValueError('Distributed controller/source version changed')
    campaign = Path(plan['campaign_directory'])
    registration = guarded.requested_registration(campaign, plan['generation'])
    stage = campaign/('train_%03d' % plan['generation'])
    if p.sha((stage/'registration.json').read_bytes()) != plan['source_registration_sha256']:
        raise ValueError('Distributed source registration changed')
    fixtures = {fixture['id']: fixture for fixture in registration['fixtures']}
    ids = [identity for shard in plan['distribution']['shards'] for identity in shard['fixture_ids']]
    if len(set(ids)) != len(ids) or set(ids) != set(fixtures):
        raise ValueError('Plan has overlapping, missing or foreign task assignments')
    return plan, campaign, registration, stage


def validate_result(plan, registration, shard_id, result_directory, registry=None):
    """Authenticate bounded complete records before any owner data is appended."""
    import hashlib
    shard = next((entry for entry in plan['distribution']['shards'] if entry['id'] == shard_id), None)
    if shard is None:
        raise ValueError('Unknown helper shard')
    bundle = p.verify_bundle(shard['bundle_directory'], shard['bundle_sha256'])
    result_directory = Path(result_directory)
    header_path = result_directory/'header.json'
    if header_path.stat().st_size > 65536:
        raise ValueError('Returned helper header exceeds protocol bound')
    header = p.loads(header_path.read_bytes())
    shadow, kind = plan['role'] == 'mechanics_shadow', bundle.get('work_role','play')
    if (header['format'] != p.FORMAT or header['shard_id'] != shard_id
            or header['bundle_sha256'] != shard['bundle_sha256'] or header['role'] != plan['role']
            or header['work_role'] != kind or header['campaign_id'] != plan['campaign_id']
            or type(header['generation']) is not int or header['generation'] != plan['generation']
            or header['worker_primary_credit'] != 0 or header['bmcts_audits'] != 0
            or header['runtime']['cuda_used_by_policy'] is not False):
        raise ValueError('Helper result identity/source package changed')
    if shadow:
        if any(header['runtime'][key] != plan['owner_runtime'][key] for key in ('implementation','version','full_version')):
            raise ValueError('Shadow runtime differs from its reference')
    else:
        from distributed_campaign import auth
        if registry is None:
            registry = auth.load_registry(plan['registry_path'])
        target = auth.public_identity(auth.owner_slot_credentials(registry, shard['helper_label']))
        if header['slot'] != target or target != bundle['target_slot']:
            raise ValueError('Foreign helper physical identity')
        signed = auth.verify(registry, 'distributed-worker-header/v2', header['authentication'], expected_slot=target['slot_id'])
        if signed != roles.header_payload(header):
            raise ValueError('Header source/runtime signature binding changed')
        if kind == 'qualify':
            if not roles.allowed_qualification_runtime(header['runtime']):
                raise ValueError('Qualification only admits explicit CPython3.12 release builds')
        elif roles.runtime_fingerprint(header['runtime']) != roles.runtime_fingerprint(bundle['approved_runtime']):
            raise ValueError('This exact runtime has not passed its signed qualification')
    candidates = {candidate['sha256']:candidate for candidate in registration['candidates']}
    fixtures = {fixture['id']:fixture for fixture in registration['fixtures']}
    assigned, seen, records = set(shard['fixture_ids']), set(), []
    path = result_directory/('games.jsonl' if shadow else 'records.jsonl')
    before = path.stat()
    if before.st_size > min(256*1024*1024, len(assigned)*131072):
        raise ValueError('Returned checkpoint exceeds its assigned task/byte bound')
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        while True:
            line = handle.readline(131073)
            if not line:
                break
            if len(line) > 131072 or not line.endswith(b'\n') or len(records) >= len(assigned):
                raise ValueError('Transfer a bounded, complete, stable result checkpoint')
            digest.update(line)
            entry = p.loads(line)
            record = entry if shadow else entry['record']
            if not shadow:
                signed = auth.verify(registry, 'distributed-result/'+kind+'/v2', entry['authentication'], expected_slot=target['slot_id'])
                if signed != roles.result_payload(bundle, header, record):
                    raise ValueError('Result MAC does not bind this exact assignment/row/runtime')
            row = record['game'] if kind == 'qualify' else record
            identity = row['fixture']
            if identity not in assigned or identity in seen or row['candidate'] != fixtures[identity]['candidate']:
                raise ValueError('Duplicate, unassigned or reassigned remote record')
            if kind in ('play','qualify'):
                run.runner.verify_row(row,candidates[row['candidate']],fixtures[identity])
            if kind == 'qualify':
                expected = bundle['expected_rows'][identity]
                if any(row[key] != expected[key] for key in BEHAVIOR_FIELDS):
                    raise ValueError('Qualified runtime did not match known canonical behavior')
                proofs.validate(record['audit'],row,candidates[row['candidate']],fixtures[identity],registration['sources'])
            elif kind == 'audit':
                creator = bundle['creators'][identity]
                if creator['physical_slot_id'] == target['physical_slot_id']:
                    raise ValueError('Creator and independent auditor are the same physical helper')
                proofs.validate(record,bundle['input_rows'][identity],candidates[record['candidate']],fixtures[identity],registration['sources'])
            seen.add(identity)
            records.append(record)
    after = path.stat()
    if (before.st_size,before.st_mtime_ns) != (after.st_size,after.st_mtime_ns):
        raise ValueError('Checkpoint changed during transfer; retry a stable snapshot')
    return records,header,digest.hexdigest()


def ingest(plan_path, shard_id, result_directory, handoff):
    plan, campaign, registration, stage = load_plan(plan_path)
    guarded.verify_handoff(handoff, campaign, plan['campaign_id'])
    rows, header, result_digest = validate_result(plan, registration, shard_id, result_directory)
    with guarded.CoordinatorLease(campaign):
        load_plan(plan_path)
        guarded.verify_handoff(handoff, campaign, plan['campaign_id'])
        existing = run.checked_rows(stage, registration)
        by_id = {row['fixture']: row for row in existing}
        pending, duplicates = [], 0
        for row in rows:
            if row['fixture'] in by_id:
                if any(row[key] != by_id[row['fixture']][key] for key in BEHAVIOR_FIELDS):
                    raise ValueError('Conflicting repeated helper result')
                duplicates += 1
            else:
                pending.append(row)
        if (stage/'audit.json').exists() or (stage/'summary.json').exists():
            if pending:
                raise ValueError('Completed/admitted stages are immutable; no new task may be appended')
            if (stage/'audit.json').exists():
                core.validated_audit(stage)
        # Validate the complete transfer before appending any row; accepted
        # timing records remain attached to the first identical actual result.
        with (stage/'games.jsonl').open('ab') as handle:
            for row in pending:
                run.append(handle, row)
        receipt = dict(format=p.FORMAT, shard_id=shard_id, result_header=header,
                       result_games_sha256=result_digest,
                       appended_games=len(pending), identical_duplicates_ignored=duplicates,
                       stage_rows=len(existing)+len(pending), primary_games_accepted=0,
                       owner_independent_audit_pending=True, bmcts_audits=0)
        receipt_id = p.sha(p.canonical(receipt))
        core.seal(Path(plan_path).parent/'ingest_receipts'/(receipt_id+'.json'), receipt)
        return receipt


def finalize(plan_path, handoff, workers=6):
    plan, campaign, registration, stage = load_plan(plan_path)
    guarded.verify_handoff(handoff, campaign, plan['campaign_id'])
    with guarded.CoordinatorLease(campaign):
        load_plan(plan_path)
        guarded.verify_handoff(handoff, campaign, plan['campaign_id'])
        rows = run.checked_rows(stage, registration)
        if {row['fixture'] for row in rows} != {fixture['id'] for fixture in registration['fixtures']}:
            raise ValueError('Cannot finalize until every original assigned game is present')
        # With complete coverage the old executor submits ZERO games; it only
        # derives its original summary. The owner still pays the full audit.
        run.execute_generation(campaign, plan['generation'], workers)
        approved = run.audit_generation(campaign, plan['generation'], workers)
        after = monitor.inspect(campaign)
        exact = next(item for item in after['stages'] if item['generation'] == plan['generation'])
        if exact.get('accepted_primary_games') != len(rows):
            raise ValueError('Original independent gate did not admit this exact stage')
        result = dict(format=p.FORMAT, generation=plan['generation'], original_audit=approved,
                      owner_game_tasks_executed=0, primary_games_accepted_by_original_gate=len(rows),
                      bmcts_audits=0, source_migration=False, promoted=False)
        core.seal(Path(plan_path).parent/'admission.json', result)
        return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    prepare = commands.add_parser('prepare')
    prepare.add_argument('--campaign', type=Path, required=True)
    prepare.add_argument('--generation', type=int, required=True)
    prepare.add_argument('--helpers', nargs='+', required=True)
    prepare.add_argument('--output', type=Path, required=True)
    prepare.add_argument('--handoff', type=Path, required=True)
    prepare.add_argument('--registry', type=Path, required=True)
    prepare.add_argument('--approval', nargs='+', required=True, help='slot=owner-approved runtime JSON')
    consume = commands.add_parser('ingest')
    consume.add_argument('--plan', type=Path, required=True)
    consume.add_argument('--shard', required=True)
    consume.add_argument('--results', type=Path, required=True)
    consume.add_argument('--handoff', type=Path, required=True)
    finish = commands.add_parser('finalize')
    finish.add_argument('--plan', type=Path, required=True)
    finish.add_argument('--handoff', type=Path, required=True)
    finish.add_argument('--workers', type=int, default=6)
    args = parser.parse_args()
    if args.command == 'prepare':
        value = prepare_plan(args.campaign, args.generation, args.helpers, args.output, args.handoff,
                             args.registry,dict(item.split('=',1) for item in args.approval))
    elif args.command == 'ingest':
        value = ingest(args.plan, args.shard, args.results, args.handoff)
    else:
        value = finalize(args.plan, args.handoff, args.workers)
    print(p.canonical(value).decode(), flush=True)


if __name__ == '__main__':
    main()
