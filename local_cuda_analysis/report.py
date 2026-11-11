"""Authenticate complete local admission before frozen descriptive arithmetic.

No controller, actor, referee replay, CUDA import/probe or partial ranking runs.
Owner HMAC authenticates declarations, not host honesty or physical execution.
"""
import argparse
import ast
from collections import Counter
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import time

from confirmation_campaign import architectures
from distributed_campaign import auth, proofs, protocol as p
from primary_campaign import core
from study_analysis import report as old

CODE_ROOT = Path(__file__).resolve().parents[1]
ROOT = CODE_ROOT
REGISTRATION_PATH = ROOT/'.cache/confirmation/architectures_v2_001/registration.json'
REGISTRATION_SHA256 = 'b5ffb74f5c8ad1c7a984a54d41d86efb26cb99ae2318a8b7d5a631d23ad24eb9'
FORMAT = 'zone-rush-owner-local-cuda-architecture-report/1'
LOCAL_FORMAT = 'zone-rush-owner-local-cuda-study/1'
RUNNER_FORMAT = 'local-cuda-physics-cpu-policy-matches/1'
PACKAGES = ('distributed_campaign','confirmation_campaign','primary_campaign','evolution',
            'campaign_holdout','training_gpu','search_coach','simulator/vendor_harness',
            'local_cuda_matches','local_cuda_study')
BASE_ROW = frozenset(('candidate','fixture','map_id','focal_seat','field','scores','focal_pw',
    'focal_score','opponent_ids','actions','timing','faults','elapsed_s'))
BACKENDS = {'existing_canonical_cpu_original':8,'local_cuda_physics_exact_cpu_python_actors':32760}
FROZEN_ARITHMETIC_SHA = 'ca76221c83bd2c13af9368487e6e79c6faa82c0d215b9b4261221db03580e733'


def require(condition,message):
    if not condition:
        raise ValueError(message)


def integer(value,low,high):
    return type(value) is int and low <= value <= high


def signed(registry,purpose,path):
    envelope,digest = old._sealed(path,128*1024*1024)
    return auth.verify_owner(registry,purpose,envelope),digest,envelope['authority_id']


def _runner_pins():
    runner = CODE_ROOT/'local_cuda_matches/runner.py'
    tree = ast.parse(runner.read_bytes())
    assignments = [node.value for node in tree.body if isinstance(node,ast.Assign)
                   and any(isinstance(target,ast.Name) and target.id=='FROZEN' for target in node.targets)]
    require(len(assignments)==1,'Ambiguous frozen local runner dependency closure')
    frozen = ast.literal_eval(assignments[0])
    pins = {}
    for name,expected in frozen.items():
        actual = p.sha((CODE_ROOT/name).read_bytes())
        require(actual==expected,'Frozen local runtime dependency source changed')
        pins[name] = actual
    for name in ('local_cuda_matches/__init__.py','local_cuda_matches/runner.py','local_cuda_matches/physics.py'):
        pins[name] = p.sha((CODE_ROOT/name).read_bytes())
    return dict(sorted(pins.items()))


def _runtime_source_pins():
    """Reproduce the controller pin recipe by reading bytes, never importing it."""
    pins = _runner_pins()
    for name in PACKAGES:
        for path in (CODE_ROOT/name).glob('*.py'):
            if not path.name.startswith('test_'):
                pins[path.relative_to(CODE_ROOT).as_posix()] = p.sha(path.read_bytes())
    for name in ('simulator/__init__.py','tests/__init__.py'):
        pins[name] = p.sha((CODE_ROOT/name).read_bytes())
    return dict(sorted(pins.items()))


def _reporter_pins():
    require(p.sha(Path(old.__file__).read_bytes())==FROZEN_ARITHMETIC_SHA,'Frozen study arithmetic source changed')
    paths = [Path(__file__),Path(__file__).with_name('__init__.py'),Path(old.__file__),
             Path(auth.__file__),Path(p.__file__),Path(proofs.__file__),Path(architectures.__file__)]
    return {path.relative_to(CODE_ROOT).as_posix():p.sha(path.read_bytes()) for path in paths}


def _source_entries(registration):
    for path,expected in registration['guards'].items():
        require(p.sha(Path(path).read_bytes())==expected,'Registered source guard changed')
    for entry in registration['candidates']+list(registration['sources'].values()):
        require(p.sha(Path(entry['path']).read_bytes())==entry['sha256'],'Exact registered actor source changed')


def _oracle_counts(registration,fixture):
    candidates = {row['sha256']:row for row in registration['candidates']}
    result = [0]*4
    own = candidates[fixture['candidate']]
    result[fixture['seat']] = 80*int(proofs.legacy_tracker(own['path'],own['sha256']))
    for spec in fixture['opponents']:
        if spec['family'] in ('planner','research','racer','blocker'):
            source = registration['sources'][spec['family']]
            result[spec['seat']] = 80*int(proofs.legacy_tracker(source['path'],source['sha256']))
    return result


def _physics_metadata(metadata,pins,lanes):
    require(type(metadata) is dict and metadata['format']=='local-cuda-match-physics/1'
        and type(metadata['device']) is str and metadata['device'].startswith('cuda')
        and metadata['cuda_kernel_executed'] is True and metadata['use_graph'] is True
        and integer(metadata['max_turns'],80,80) and integer(metadata['batch_size'],lanes,lanes)
        and integer(metadata['accepted_batch_steps'],80,80)
        and integer(metadata['accepted_branch_turn_events'],80*lanes,80*lanes)
        and integer(metadata['setup_throwaway_transitions'],3,3)
        and integer(metadata['setup_primary_match_credit'],0,0)
        and integer(metadata['setup_completed_game_audit_credit'],0,0)
        and metadata['policy_backend']=='External exact CPU actors',
        'Local qualification lacks actual declared complete CUDA physics provenance')
    required = {'training_gpu/batch_game.py','search_coach/gpu_batch.py','local_cuda_matches/physics.py'}
    require(required<=set(metadata['source_sha256']) and all(pins.get(name)==value
        for name,value in metadata['source_sha256'].items()),'Qualified physics source closure changed')
    require(metadata['rules']==dict(frozen_stay_counts=False,claim_resets_progress=True,
        catch_requires_stay=True,lost_contest_is_stay=True,home_upgradable=True)
        and all(type(value) is bool for value in metadata['rules'].values()),'Qualified canonical physics rules changed')


def _gold(registry,registration,registration_path,expected_witness):
    directory = registration_path.parent/'runtime_gold_v2'
    witness,witness_sha,_ = signed(registry,'distributed-control-gold-witness/v2',directory/'gold_witness.json')
    binding,_,_ = signed(registry,'distributed-control-gold-registration/v2',directory/'gold_registration.json')
    identities = registration['runtime_qualification_task_ids']
    require(witness_sha==expected_witness and len(identities)==len(set(identities))==8
        and witness['task_ids']==binding['task_ids']==identities
        and witness['study_registration_sha256']==binding['study_registration_sha256']==REGISTRATION_SHA256
        and witness['creator']==binding['creator'] and witness['qualification_context']==binding['qualification_context']
        and witness['source_registration_path']==str(registration_path)
        and integer(witness['actual_study_games'],8,8) and integer(witness['full_audit_callbacks'],2560,2560)
        and integer(witness['primary_games_accepted'],0,0),'Canonical consumed eight-gold witness changed')
    fixtures = {row['id']:row for row in registration['fixtures']}
    candidates = {row['sha256']:row for row in registration['candidates']}
    records,digest = {},hashlib.sha256()
    records_path = directory/'gold_records.jsonl'
    require(records_path.stat().st_size<=8*1024*1024,'Canonical eight-record gold evidence exceeds its bound')
    with records_path.open('rb') as stream:
        while True:
            line = stream.readline(1024*1024+1)
            if not line:
                break
            require(line.endswith(b'\n') and len(line)<=1024*1024,'Malformed canonical gold record')
            digest.update(line)
            record = auth.verify_owner(registry,'distributed-control-gold-record/v2',p.loads(line))
            row = record['game']; identity = row['fixture']
            require(identity in identities and identity not in records and record['creator']==witness['creator']
                and record['study_registration_sha256']==REGISTRATION_SHA256,'Foreign or duplicate original gold row')
            old._row(row,fixtures[identity])
            proofs.validate(record['audit'],row,candidates[row['candidate']],fixtures[identity],registration['sources'])
            records[identity] = row
    require(set(records)==set(identities) and digest.hexdigest()==witness['records_sha256'],
            'Complete exact canonical original gold records required')
    return records,witness_sha


def _context(registration_path,registry_path):
    registration_path,registry_path = Path(registration_path).resolve(),Path(registry_path).resolve()
    require(registration_path==REGISTRATION_PATH.resolve(),'Only the original canonical study registration path is reportable')
    registration,registration_sha = old._sealed(registration_path,100*1024*1024)
    require(registration_sha==REGISTRATION_SHA256,'Exact frozen four-arm registration required')
    # Exact published bytes plus the frozen pure structural crossing validator;
    # do not call architectures.validate/controller._load or active runtimes.
    design = old._design(registration)
    _source_entries(registration)
    registry = auth.load_registry(registry_path)
    binding,binding_sha,authority = signed(registry,'distributed-control-study-binding/v2',
        registration_path.parent/'distributed_control_v2/binding.json')
    directory = Path(binding['canonical_output']).resolve()
    expected_binding = dict(format=LOCAL_FORMAT,source_registration_path=str(registration_path),
        source_registration_sha256=REGISTRATION_SHA256,canonical_output=str(directory),registry_path=str(registry_path),
        role='extra_control_assignment',execution_mode='owner_local_cuda_physics_exact_cpu_python_actors',helpers=[],
        user_cancelled_shared_compute=True,
        rule='One canonical original cohort; import8 consumed originals once and execute32760 remaining originals locally.',
        primary_games_accepted=0,bmcts_audits=0,promotion_allowed=False)
    require(binding==expected_binding and directory.is_relative_to((ROOT/'.cache/local_cuda').resolve())
        and directory!=(ROOT/'.cache/local_cuda').resolve()
        and integer(binding['primary_games_accepted'],0,0) and integer(binding['bmcts_audits'],0,0)
        and binding['promotion_allowed'] is False and binding['user_cancelled_shared_compute'] is True,
        'Foreign canonical owner-local binding/output')
    plan,plan_sha,plan_authority = signed(registry,'owner-local-cuda-plan/v1',directory/'plan.json')
    accepted,acceptance_sha,accept_authority = signed(registry,'owner-local-cuda-acceptance/v1',directory/'acceptance.json')
    require(authority==plan_authority==accept_authority,'Local admission authority changed')
    pins = _runtime_source_pins()
    require(plan['format']==accepted['format']==LOCAL_FORMAT and accepted['complete'] is True
        and accepted['promoted'] is False and plan['promotion_allowed'] is False
        and plan['source_sha256']==accepted['source_sha256']==pins
        and plan['runtime']==accepted['runtime'] and type(plan['runtime']) is dict
        and plan['binding']==binding and plan['source_registration_path']==str(registration_path)
        and plan['registry_path']==str(registry_path) and accepted['source_registration_sha256']==REGISTRATION_SHA256
        and accepted['plan_sha256']==plan_sha and plan['statistical_plan']==registration['protocol']['inference']
        and plan['original_backend_counts']==accepted['original_backend_counts']==dict(existing_cpu_gold=8,new_cuda_originals=32760)
        and integer(plan['planned_extra_games'],32768,32768) and integer(accepted['accepted_extra_games'],32768,32768)
        and all(integer(item[key],0,0) for item in (plan,accepted) for key in ('primary_games','bmcts_audits'))
        and integer(accepted['original_callbacks'],32768*320,32768*320)
        and integer(accepted['independent_owner_regenerated_callbacks'],32768*320,32768*320)
        and integer(plan['primary_games_accepted'],0,0)
        and integer(plan['batch_size'],1,256),'Incomplete, changed-source or credit-altered local admission')
    qualified,qualification_sha,_ = signed(registry,'owner-local-cuda-qualification/v1',Path(plan['qualification_path']))
    require(qualification_sha==plan['qualification_sha256'] and qualified['qualified'] is True
        and qualified['format']==LOCAL_FORMAT and qualified['source_registration_sha256']==REGISTRATION_SHA256
        and qualified['source_sha256']==pins and qualified['runtime']==plan['runtime']
        and qualified['fixture_ids']==registration['runtime_qualification_task_ids']
        and qualified['full_action_tapes_equal'] is True
        and qualified['actor_backend']=='CPU exact Python' and qualified['physics_backend']=='CUDA'
        and all(integer(qualified[key],value,value) for key,value in
            (('qualification_replicas',8),('new_study_games',0),('primary_games',0),('bmcts_audits',0),
             ('original_actor_callbacks',2560),('independently_regenerated_callbacks',2560))),
        'Complete exact-source zero-credit CUDA qualification missing')
    _physics_metadata(qualified['physics_metadata'],pins,8)
    expected_qualification_oracles = sum(sum(_oracle_counts(registration,design[3][identity]))
                                         for identity in registration['runtime_qualification_task_ids'])
    require(integer(qualified['public_memory_oracles'],expected_qualification_oracles,expected_qualification_oracles),
            'Qualification source-specific memory oracle coverage changed')
    summary,summary_sha = old._sealed(Path(plan['qualification_path']).parent/'summary.json',16*1024*1024)
    require(summary_sha==qualified['backend_summary_sha256'] and summary['format']==RUNNER_FORMAT
        and all(integer(summary[key],value,value) for key,value in (('complete_games',8),('callbacks',2560),
            ('gpu_physical_turns',640),('gpu_reference_state_comparisons',648),('gpu_official_state_comparisons',648),
            ('primary_games',0),('completed_per_game_bmcts_audits',0)))
        and summary['physics_metadata']==qualified['physics_metadata']
        and summary['source_sha256']==_runner_pins(),
        'Bound complete CUDA qualification backend summary changed')
    gold,witness_sha = _gold(registry,registration,registration_path,plan['gold_witness_sha256'])
    require(qualified['canonical_gold_witness_sha256']==witness_sha,'Qualification uses different canonical originals')
    pending = [fixture['id'] for fixture in registration['fixtures'] if fixture['id'] not in gold]
    require(plan['pending_fixture_ids']==pending and len(pending)==32760
        and plan['fixture_id_list_sha256']==p.sha(p.canonical(pending))
        and integer(plan['canonical_gold_originals'],8,8) and integer(plan['new_local_cuda_originals'],32760,32760)
        and all(type(accepted[name]) is str and old.HEX.fullmatch(accepted[name]) for name in ('games_sha256','audits_sha256')),
        'Frozen original fixture partition or accepted file hashes changed')
    return registration,design,directory,dict(authority_id=authority,registration_sha256=registration_sha,
        study_binding_sha256=binding_sha,plan_sha256=plan_sha,acceptance_sha256=acceptance_sha,
        qualification_sha256=qualification_sha,gold_witness_sha256=witness_sha,
        games_sha256=accepted['games_sha256'],audits_sha256=accepted['audits_sha256'],
        canonical_output=str(directory),runtime=plan['runtime'],runtime_source_sha256=pins,
        batch_size=plan['batch_size'],qualified_cpu_runtime=summary['cpu_runtime'],
        original_backend_counts=accepted['original_backend_counts'],helpers=[],
        trust_model='Trusted owner HMAC authenticates admission declarations; not proof of host honesty, independent hardware or CUDA execution.'),gold


def _local_row(row,fixture,oracles):
    require(set(row)==BASE_ROW|{'proof','public_memory_oracles'},'Malformed local CUDA original row')
    pw2 = old._row({name:row[name] for name in BASE_ROW},fixture)
    proof = row['proof']
    require(type(proof) is dict and set(proof)=={'callbacks_regenerated','public_memory_oracles','oracle_calls_by_seat',
        'gpu_reference_state_comparisons','gpu_official_state_comparisons','physical_turns',
        'gpu_state_chain_sha256','gpu_public_chain_sha256','all_inputs_gpu_public_only',
        'source_closure_sha256','registration_snapshot_sha256',
        'cpu_referees_observers_only','actor_backend','physics_backend','primary_games',
        'canonical_local_admission','completed_per_game_bmcts_audits'}
        and all(integer(proof[key],value,value) for key,value in
        (('callbacks_regenerated',320),('physical_turns',80),('gpu_reference_state_comparisons',81),
         ('gpu_official_state_comparisons',81),('public_memory_oracles',sum(oracles)),('primary_games',0),
         ('completed_per_game_bmcts_audits',0))) and type(proof['oracle_calls_by_seat']) is list
        and len(proof['oracle_calls_by_seat'])==4 and all(type(value) is int for value in proof['oracle_calls_by_seat'])
        and proof['oracle_calls_by_seat']==oracles
        and integer(row['public_memory_oracles'],sum(oracles),sum(oracles))
        and proof['all_inputs_gpu_public_only'] is True and proof['cpu_referees_observers_only'] is True
        and proof['actor_backend']=='CPython CPU' and proof['physics_backend']=='local CUDA'
        and proof['canonical_local_admission']=='pending'
        and all(type(proof[name]) is str and old.HEX.fullmatch(proof[name])
                for name in ('gpu_state_chain_sha256','gpu_public_chain_sha256','source_closure_sha256',
                             'registration_snapshot_sha256')),
        'Local original lacks complete source-specific actor/CUDA/two-referee proof')
    return pw2


def _source_schedule(registration):
    return dict(snapshot_scope='selected fixtures only; not the complete original registration bytes',
        original_fixture_count=len(registration['fixtures']),
        ordered_original_fixture_ids_sha256=p.sha(p.canonical([fixture['id'] for fixture in registration['fixtures']])))


def _source_snapshot(registration,fixtures,identities,schedule):
    result = {key:value for key,value in registration.items() if key!='fixtures'}
    result.update(fixtures=[fixtures[identity] for identity in identities],local_cuda_source_schedule=schedule)
    return result


def _batch_context(registration,fixtures,directory,identities,runner_pins,cpu_runtime,schedule):
    """Bind the row hashes to this exact selected-source snapshot and summary."""
    snapshot,snapshot_sha = old._sealed(directory/'registration.json',100*1024*1024)
    expected = _source_snapshot(registration,fixtures,identities,schedule)
    require(p.canonical(snapshot)==p.canonical(expected),'CUDA batch snapshot differs from exact ordered source fixtures')
    header,header_sha = old._sealed(directory/'execution_started.json',16*1024*1024)
    summary,summary_sha = old._sealed(directory/'summary.json',16*1024*1024)
    lanes = len(identities)
    require(header['format']==summary['format']==RUNNER_FORMAT and header['fixture_ids']==identities
        and header['registration_snapshot_sha256']==snapshot_sha
        and header['source_sha256']==summary['source_sha256']==runner_pins
        and header['source_schedule']==summary['source_schedule']==schedule
        and header['cpu_runtime']==summary['cpu_runtime']==cpu_runtime
        and cpu_runtime['implementation']=='CPython' and cpu_runtime['cuda_used_by_policy'] is False
        and cpu_runtime['actor_backend']=='CPython CPU original Python actors'
        and header['actor_backend']=='CPython CPU original Python actors' and header['physics_backend']=='local CUDA'
        and all(integer(item[key],0,0) for item in (header,summary)
                for key in ('primary_games','completed_per_game_bmcts_audits'))
        and all(integer(summary[key],value,value) for key,value in (('complete_games',lanes),
            ('callbacks',lanes*320),('gpu_physical_turns',lanes*80),('gpu_reference_state_comparisons',lanes*81),
            ('gpu_official_state_comparisons',lanes*81)))
        and all(type(summary[name]) is str and old.HEX.fullmatch(summary[name]) for name in ('games_sha256','turns_sha256')),
        'CUDA batch header/summary source, runtime, credit or coverage changed')
    _physics_metadata(summary['physics_metadata'],runner_pins,lanes)
    return dict(directory=directory,fixture_ids=identities,registration_snapshot_sha256=snapshot_sha,
        source_closure_sha256=p.sha(p.canonical(runner_pins)),header_sha256=header_sha,summary_sha256=summary_sha,
        games_sha256=summary['games_sha256'],turns_sha256=summary['turns_sha256'])


def _file_hash(path,maximum):
    require(path.stat().st_size<=maximum,'CUDA batch file exceeds its explicit bound')
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''):
            digest.update(chunk)
    return digest.hexdigest()


def _row_binding(row,context):
    require(row['proof']['source_closure_sha256']==context['source_closure_sha256']
        and row['proof']['registration_snapshot_sha256']==context['registration_snapshot_sha256'],
        'Accepted row source closure or selected-batch registration hash changed')


def _finish_batch(context,rows,accepted_digest):
    """Tie raw batch files and all80 public action/hash links to accepted rows."""
    directory = context['directory']; lanes = len(rows)
    require([row['fixture'] for row in rows]==context['fixture_ids']
        and accepted_digest==context['games_sha256']==_file_hash(directory/'games.jsonl',1024**3),
        'Accepted original rows do not match the exact sealed CUDA batch games file')
    path = directory/'turns.jsonl'
    require(path.stat().st_size<=128*1024*1024,'CUDA batch turn evidence exceeds its bound')
    digest,last = hashlib.sha256(),None
    with path.open('rb') as stream:
        for turn in range(1,81):
            line = stream.readline(1024*1024+1)
            require(line.endswith(b'\n') and len(line)<=1024*1024,'Complete80-turn CUDA batch transcript required')
            digest.update(line); entry = p.loads(line)
            require(set(entry)=={'turn','actions','gpu_state_chain_sha256','gpu_public_chain_sha256',
                    'per_lane_completed_physical_turns'} and integer(entry['turn'],turn,turn)
                and entry['actions']==[row['actions'][turn-1] for row in rows]
                and entry['per_lane_completed_physical_turns']==[turn]*lanes
                and all(type(value) is int for value in entry['per_lane_completed_physical_turns'])
                and all(type(entry[name]) is list and len(entry[name])==lanes
                        and all(type(value) is str and old.HEX.fullmatch(value) for value in entry[name])
                        for name in ('gpu_state_chain_sha256','gpu_public_chain_sha256')),
                'CUDA batch action, clock, lane count or public-state hash transcript changed')
            last = entry
        require(not stream.read(1),'Excess CUDA batch turn evidence forbidden')
    require(digest.hexdigest()==context['turns_sha256']
        and last['gpu_state_chain_sha256']==[row['proof']['gpu_state_chain_sha256'] for row in rows]
        and last['gpu_public_chain_sha256']==[row['proof']['gpu_public_chain_sha256'] for row in rows],
        'Sealed CUDA batch turn evidence does not bind accepted final state/public chains')


def _collect(registration,design,directory,provenance,gold):
    arms,fields,maps,fixtures = design
    mi,ai,fi = ({value:index for index,value in enumerate(values)} for values in (maps,arms,fields))
    cube = [[[0]*4 for _ in arms] for _ in maps]
    overall,by_field = [old.Bucket() for _ in arms],[[old.Bucket() for _ in fields] for _ in arms]
    expected_order = registration['runtime_qualification_task_ids']+[identity for identity in fixtures if identity not in gold]
    seen,backends,digests = set(),Counter(),[hashlib.sha256(),hashlib.sha256()]
    paths = [directory/'games.jsonl',directory/'audits.jsonl']
    batch_size = provenance.get('batch_size'); runner_pins = _runner_pins()
    require(integer(batch_size,1,256),'Authenticated CUDA batch size changed')
    pending = expected_order[8:]; schedule = _source_schedule(registration)
    batch_context,batch_rows,batch_digest = None,[],None
    batch_provenance = []
    require(all(path.stat().st_size<=1024**3 for path in paths),'Complete local evidence exceeds explicit one-GiB/file bound')
    with paths[0].open('rb') as games,paths[1].open('rb') as audits:
        for index in range(32768):
            lines = [games.readline(256*1024+1),audits.readline(256*1024+1)]
            require(all(line.endswith(b'\n') and len(line)<=256*1024 and line.strip() for line in lines),
                    'Complete untorn local game/audit rows required before analysis')
            for digest,line in zip(digests,lines):
                digest.update(line)
            row,audit = map(p.loads,lines)
            identity = row.get('fixture') if type(row) is dict else None
            require(identity==expected_order[index] and identity not in seen,'Duplicate, foreign or reordered original fixture')
            fixture = fixtures[identity]; oracles = _oracle_counts(registration,fixture)
            backend = 'existing_canonical_cpu_original' if identity in gold else 'local_cuda_physics_exact_cpu_python_actors'
            if identity in gold:
                require(row==gold[identity],'Imported gold is not the exact consumed original row')
                pw2 = old._row(row,fixture)
            else:
                offset = index-8
                if offset%batch_size==0:
                    batch_context = _batch_context(registration,fixtures,directory/'batches'/('%05d'%(offset//batch_size)),
                        pending[offset:offset+batch_size],runner_pins,provenance['qualified_cpu_runtime'],schedule)
                    batch_rows,batch_digest = [],hashlib.sha256()
                pw2 = _local_row(row,fixture,oracles)
                _row_binding(row,batch_context)
                batch_rows.append(row);batch_digest.update(lines[0])
                if len(batch_rows)==len(batch_context['fixture_ids']):
                    _finish_batch(batch_context,batch_rows,batch_digest.hexdigest())
                    batch_provenance.append({key:value for key,value in batch_context.items() if key not in ('directory','fixture_ids')})
            require(type(audit) is dict and set(audit)=={'fixture','candidate','game_sha256','original_backend',
                'callbacks_regenerated','public_memory_oracles'} and audit['fixture']==identity
                and audit['candidate']==fixture['candidate'] and audit['original_backend']==backend
                and audit['game_sha256']==p.sha(p.canonical(row))
                and integer(audit['callbacks_regenerated'],320,320)
                and integer(audit['public_memory_oracles'],sum(oracles),sum(oracles)),
                'Every exact original game requires its complete source-specific owner actor audit')
            seen.add(identity); backends[backend]+=1
            m,a,f = mi[fixture['map_id']],ai[fixture['candidate']],fi[fixture['field']]
            cube[m][a][f]+=pw2; overall[a].add(row,pw2); by_field[a][f].add(row,pw2)
        require(not games.read(1) and not audits.read(1),'Excess original games or audits forbidden')
    require(seen==set(fixtures) and backends==BACKENDS and digests[0].hexdigest()==provenance['games_sha256']
        and digests[1].hexdigest()==provenance['audits_sha256'],'Complete exact accepted local files/backend coverage required')
    provenance['cuda_batch_evidence'] = batch_provenance
    return cube,overall,by_field


def assessment(arms,comparisons):
    maximum = max(arm['pairwise_numerator_sum'] for arm in arms)
    leaders = [arm['sha256'] for arm in arms if arm['pairwise_numerator_sum']==maximum]
    separated = None
    if len(leaders)==1:
        leader = leaders[0]
        relevant = [item for item in comparisons if leader in (item['first'],item['second'])]
        if len(relevant)==3 and all((item['descriptive_bonferroni_interval'][0]['numerator']>0
            if item['first']==leader else item['descriptive_bonferroni_interval'][1]['numerator']<0) for item in relevant):
            separated = leader
    return dict(observed_mean_leaders=leaders,descriptively_separated_arm=separated,
        conclusion='One arm is descriptively separated within this registered study.' if separated else
                   'Inconclusive: no unique arm is descriptively separated from every alternative.',
        automatic_promotion=False,scope='Finite selected architecture cohort; not universal strength or an automatic release decision.')


def analyze(registration_path,registry_path):
    started,guards = time.perf_counter(),_reporter_pins()
    registration,design,directory,provenance,gold = _context(registration_path,registry_path)
    cube,overall,fields = _collect(registration,design,directory,provenance,gold)
    statistical_start = time.perf_counter()
    comparisons,bootstrap = old._bootstrap(cube,registration['protocol']['inference'])
    arms = []
    for index,candidate in enumerate(registration['candidates']):
        result = dict(name=candidate['name'],sha256=candidate['sha256'],**overall[index].summary())
        result['fields'] = {field:bucket.summary() for field,bucket in zip(design[1],fields[index])}
        minimum = min(Fraction(bucket.pw2,2*bucket.games) for bucket in fields[index])
        result['worst_field_mean_pairwise'] = old._fraction(minimum.numerator,minimum.denominator)
        result['worst_fields'] = [field for field,bucket in zip(design[1],fields[index]) if Fraction(bucket.pw2,2*bucket.games)==minimum]
        arms.append(result)
    require(guards==_reporter_pins() and provenance['runtime_source_sha256']==_runtime_source_pins(),
            'Reporting or admitted runtime source changed during analysis')
    return dict(format=FORMAT,role='report_only_owner_local_extra_study',provenance=provenance,
        inference_plan=registration['protocol']['inference'],
        inference_plan_sha256=p.sha(p.canonical(registration['protocol']['inference'])),
        coverage=dict(complete=True,unique_games=32768,maps=128,arms=4,fields=4,seat_token_crosses=16,
            games_per_arm=8192,games_per_arm_field=2048,canonical_cpu_gold_originals=8,
            local_cuda_originals=32760,qualification_replicas_credited=0,independently_regenerated_callbacks=32768*320,
            all_registered_fixtures_once=True,faults=0),arms=arms,comparisons=comparisons,bootstrap=bootstrap,
        architecture_assessment=assessment(arms,comparisons),source_sha256=guards,
        validation_scope='Complete authenticated evidence/schema/hash/source validation and frozen arithmetic; no execution replay by this analyzer.',
        timings=dict(validation_and_collection_s=statistical_start-started,
                     statistics_s=time.perf_counter()-statistical_start,total_report_s=time.perf_counter()-started),
        timing_caveat='Exact Python actors run on CPU; CUDA advances physics. Recorded callback/transfer/observer timings are descriptive, not a GPU-policy or normalized speed ranking.',
        field_inference='Field means/contrasts are descriptive; no additional simultaneous field intervals.',
        new_games_executed=0,new_actor_callbacks=0,primary_match_credit=0,completed_game_audit_credit=0,
        full_bmcts_audit_credit=0,promoted=False,tuning_performed=False,
        caveat='All six unchanged preregistered map-bootstrap contrasts reported only after complete owner-authenticated local admission. HMAC authenticates trusted-owner declarations, not host honesty or physical independence. No universal superiority, exact familywise guarantee or automatic release.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--registration',type=Path,required=True)
    parser.add_argument('--registry',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args = parser.parse_args(); output = args.output.resolve()
    require(not output.exists() and not output.with_suffix('.sha256').exists(),'Fresh report output required')
    result = analyze(args.registration,args.registry)
    core.seal(output,result)
    print(json.dumps(dict(output=str(output),accepted_games=32768,comparisons=6,
                          new_games_executed=0,primary_match_credit=0,promoted=False)),flush=True)


if __name__=='__main__':
    main()
