"""Exclusive owner coordinator for the explicitly separate ten-hour campaign.

Workers receive source registrations only. Authority, score selection, phase
reservation, receipts and release decisions remain in this root process.
"""
import argparse
from datetime import datetime,timezone
from fractions import Fraction
import json
import math
from pathlib import Path
import time
from zipfile import ZipFile,ZIP_DEFLATED

from campaign_monitor.guarded_run import CoordinatorLease
from evolution import oversight
from local_cuda_matches import runner as frozen
from deadline_runner import runner
from primary_local import recipe
from . import budget,design,evaluation
from .authority import Authority
from .awake import KeepAwake

ROOT=design.ROOT
CAMPAIGN=ROOT/'.cache/deadline/campaign_20261109_10h_001'
STUDY=ROOT/'.cache/confirmation/architectures_v2_001/registration.json'
REGISTRY=ROOT/'.cache/distributed_campaign/architecture_v2_private_001/registry.json'
DEFAULT_EXECUTION=dict(batch_size=256,workers=4,audit_workers=4)


def now(): return datetime.now(timezone.utc)


def _require(condition,message):
    if not condition: raise ValueError(message)


def _same(left,right): return design.canonical(left)==design.canonical(right)


def _read(path):
    body=Path(path).read_bytes()
    value=oversight.strict_loads(body)
    _require(body==design.canonical(value)+b'\n','Exact canonical artifact plus LF required')
    return value


def _sealed(path):
    path=Path(path);body=path.read_bytes()
    _require(path.with_suffix('.sha256').read_text().strip()==design.sha(body),'Artifact fingerprint changed')
    return _read(path)


def source_pins():
    from deadline_runner.benchmark import source_pins as qualification_pins
    pins=qualification_pins()
    pins.update(recipe.source_pins())
    from deadline_strategy.goal_space import source_pins as strategy_pins
    for name,digest in strategy_pins().items():
        _require(name not in pins or pins[name]==digest,'Strategy dependency source closure disagrees')
        pins[name]=digest
    for folder in ('deadline_campaign','deadline_strategy','evolution_templates','local_cuda_analysis'):
        for path in (ROOT/folder).glob('*.py'):
            if not path.name.startswith('test_'): pins[path.relative_to(ROOT).as_posix()]=design.sha(path.read_bytes())
    for relative in ('campaign_holdout/authority.py','campaign_monitor/guarded_run.py'):
        pins[relative]=design.sha((ROOT/relative).read_bytes())
    for relative in ('deadline_strategy/LEGACY_STAGE4_REVIEW.json','primary_campaign/evidence/accepted_stages_000_004.json'):
        pins[relative]=design.sha((ROOT/relative).read_bytes())
    for path in (ROOT/'deadline_runner').glob('*.py'):
        if not path.name.startswith('test_'): pins[path.relative_to(ROOT).as_posix()]=design.sha(path.read_bytes())
    return dict(sorted(pins.items()))


def _context(campaign):
    campaign=Path(campaign).resolve()
    _require(campaign==CAMPAIGN.resolve(),'This deadline protocol has one canonical owner output')
    authority=Authority.load(campaign);manifest=_read(campaign/'manifest.json')
    _require(manifest['source_sha256']==source_pins(),'Frozen deadline runtime changed')
    _require(manifest['catalog_sha256']==design.CATALOG_SHA256
             and design.sha(design.CATALOG.read_bytes())==design.CATALOG_SHA256,'Reserved catalog changed')
    receipt=authority.read('manifest','manifest_receipt.json')
    _require(receipt['manifest_sha256']==authority.manifest_sha256,'Manifest receipt does not bind this exact manifest')
    return campaign,authority,manifest


def prepare(benchmark_directory,scheduling_directory=None):
    from deadline_runner.benchmark import verify_complete
    proof=verify_complete(Path(benchmark_directory).resolve())
    measurements=proof['measurements']
    execution=dict(DEFAULT_EXECUTION);scheduling=None
    if scheduling_directory is not None:
        from deadline_runner.optimize import verify_complete as verify_scheduling
        optimized=verify_scheduling(Path(scheduling_directory).resolve())
        _require(optimized['baseline']['benchmark_result_sha256']==design.sha((Path(benchmark_directory)/'benchmark_result.json').read_bytes()),
            'Scheduling calibration used a different original qualification baseline')
        execution=dict(optimized['selected_configuration']);measurements=[optimized['selected_measurement']]
        scheduling=dict(path=str(Path(scheduling_directory).resolve()),
            result_sha256=design.sha((Path(scheduling_directory)/'optimization_result.json').read_bytes()))
    # This also proves that a full minimum heldout panel fits, including reserves.
    prospective=budget.heldout_budget(measurements)
    _require(now()<budget.TRAIN_CUTOFF,'Training setup is past its deadline')
    campaign=CAMPAIGN.resolve()
    with CoordinatorLease(campaign):
        _require(not campaign.exists(),'Fresh canonical deadline campaign required; no reinitialization')
        campaign.mkdir(parents=True,exist_ok=False)
        manifest=dict(format=design.FORMAT,start_utc=budget.START.isoformat(),deadline_utc=budget.DEADLINE.isoformat(),
            created_utc=now().isoformat(),catalog_sha256=design.CATALOG_SHA256,source_sha256=source_pins(),
            qualification_path=str(Path(benchmark_directory).resolve()),
            qualification_result_sha256=design.sha((Path(benchmark_directory)/'benchmark_result.json').read_bytes()),
            timing_measurements=measurements,prospective_heldout_budget=prospective,
            execution_configuration=execution,scheduling_qualification=scheduling,
            initial_candidates=[design.classify(body) for body in design.initial_population()],
            train=dict(first_map=500,maps_per_generation=16,games_per_generation=8192,population=8,
                reference_sources=list(design.REFERENCES),rule='Exact64cells/map/arm; every TRAIN rival instance and actual seed is fresh.',
                population_recipe='Gen0 e8,50d,Blocker,Feint,f5 +exact learned stage4 offspring_07 +Blocker/Feint numeric children. Gen1 three originals +f5 control +best other nonreference +e8 child +fixed persistent-goal f5 extension +Feint child. Gen2 onward3originals +2nonreference elites +one sparse child per strategy family; structural template inherited explicitly.',
                stopping='Timing-only whole-generation feasibility; no TRAIN after shortlist or any heldout outcome.'),
            development=dict(first_map=8000,map_grid=list(budget.DEVELOPMENT_MAP_GRID),
                shortlist='Exactly the last fully admitted eight-policy TRAIN population.',
                selection='Maximum mean pairwise, then worst field mean, mean raw score, source SHA; exploratory.'),
            final=dict(first_map=9000,map_grid=list(budget.FINAL_MAP_GRID),
                reference='Largest exact mean pairwise among the four arms of the complete authenticated fixed architecture study; raw score then SHA breaks ties.',
                comparison='Exactly one frozen DEV challenger versus this reference, all64cells/map with matched rival parameters/RNG and fresh distinct namespaces/instance IDs.',
                promotion='overall95% map-bootstrap lower>0 AND each of4 Bonferroni one-sided field lower>-.05PW; otherwise reference.',
                no_challenger='If DEV selects the reference itself, retain it without a redundant two-identical-source FINAL.',
                missing_or_failed_panel='Preserve evidence and retain the fully validated reference; no final-comparison superiority claim.',
                bootstrap_replicates=evaluation.BOOTSTRAP_REPLICATES,bootstrap_seed=evaluation.BOOTSTRAP_SEED),
            new_primary_campaign_credit=0,completed_bmcts_audits=0,
            scope='Deadline replacement for mandatory volume; never a completed two-million-game claim.',
            trust='Owner-local trusted source execution and independently regenerated actors/two referees; HMAC is not hostile-host or hardware attestation.')
        frozen._seal(campaign/'manifest.json',manifest)
        authority=Authority.create(campaign)
        authority.seal('manifest',dict(manifest_sha256=authority.manifest_sha256,created_utc=now().isoformat()),'manifest_receipt.json')
        with ZipFile(campaign/'runtime_sources.zip','x',compression=ZIP_DEFLATED) as archive:
            for relative in manifest['source_sha256']: archive.writestr(relative,(ROOT/relative).read_bytes())
        frozen._seal(campaign/'runtime_archive.json',dict(sha256=design.sha((campaign/'runtime_sources.zip').read_bytes()),
            files=manifest['source_sha256'],contains_private_keys=False))
        return dict(campaign=str(campaign),manifest_sha256=authority.manifest_sha256,prospective_budget=prospective)


def _materialize(directory,bodies):
    design.validate_population(bodies,len(bodies));directory.mkdir(exist_ok=False)
    entries=[]
    for body in bodies:
        path=directory/(design.sha(body)+'.py')
        with path.open('xb') as stream: stream.write(body)
        entries.append(design.source_entry(path))
    return entries


def _registration(campaign,authority,manifest,phase,generation,bodies,boards):
    directory=campaign/(('train_%03d'%generation) if phase=='train' else phase)
    _require(not directory.exists(),'One attempt per registered cohort; preserve partial failures without replay')
    directory.mkdir(exist_ok=False)
    entries=_materialize(directory/'candidates',bodies)
    guards={str(ROOT/name):digest for name,digest in manifest['source_sha256'].items()}
    registration=design.cohort(phase,generation,boards,entries,guards)
    frozen._seal(directory/'registration.json',registration)
    authority.seal('registration',dict(phase=phase,generation=generation,path=str(directory/'registration.json'),
        registration_sha256=design.sha((directory/'registration.json').read_bytes()),planned_games=len(registration['fixtures']),
        map_indices=[b['map_index'] for b in boards],candidate_sha256=[c['sha256'] for c in entries]),directory/'registration_receipt.json')
    return directory,registration


def _verify_output(registration,directory):
    """Check complete durable output bindings; actual full replay was done by runner."""
    output=directory/'execution'; summary=_sealed(output/'summary.json')
    from deadline_runner.verify import verify_execution
    verified=verify_execution(registration,output)
    expected=registration['protocol']['complete_games']
    _require(summary['source_sha256']==runner.source_pins(),'Executor runtime closure changed')
    for name,field in (('originals.jsonl','originals_sha256'),('audits.jsonl','audits_sha256')):
        _require(design.sha((output/name).read_bytes())==summary[field],'Complete original/audit bytes changed')
    for field,count in (('original_games',expected),('independent_full_game_audits',expected),
            ('original_callbacks',expected*320),('independently_regenerated_callbacks',expected*320),
            ('original_gpu_physical_turns',expected*80),('independent_dual_referee_turns',expected*80)):
        _require(type(summary.get(field)) is int and summary[field]==count,'Complete physical/actor coverage missing')
    rows=verified['rows'];audits=verified['audits']
    fixtures=registration['fixtures'];closure=design.sha(design.canonical(runner.source_pins()))
    _require(len(rows)==len(audits)==len(fixtures)==expected,'Incomplete ordered cohort')
    for fixture,row,audit in zip(fixtures,rows,audits):
        p=row.get('proof',{}); tracker=audit.get('tracker',{})
        _require(row['fixture']==fixture['id'] and audit.get('fixture')==fixture['id']
            and audit.get('candidate')==fixture['candidate'] and audit.get('ok') is True
            and audit.get('row_sha256')==design.sha(design.canonical(row))
            and audit.get('source_closure_sha256')==closure and p.get('source_closure_sha256')==closure,
            'Original/independent audit identity or exact row/source binding changed')
        for key in ('callbacks_regenerated','callbacks_returned','callbacks_completed'):
            _require(type(p.get(key)) is int and p[key]==320,'Original callback coverage missing')
        for key,count in (('physical_turns',80),('gpu_reference_state_comparisons',81),('gpu_official_state_comparisons',81)):
            _require(type(p.get(key)) is int and p[key]==count,'Original physical/referee coverage missing')
        _require(audit.get('all_actors_regenerated') is True and type(audit.get('callbacks_regenerated')) is int
            and audit['callbacks_regenerated']==320 and type(audit.get('dual_referee_physical_turns')) is int
            and audit['dual_referee_physical_turns']==80 and tracker.get('attempted')==320 and tracker.get('returned')==320
            and tracker.get('attempts_by_seat')==[80]*4 and tracker.get('returns_by_seat')==[80]*4,
            'Independent actual callback/physical coverage missing')
    aggregated=evaluation.aggregate(registration,rows)
    return summary,aggregated


def _assert_execution_configuration(directory,configuration):
    if (type(configuration) is not dict or set(configuration)!=set(DEFAULT_EXECUTION)
            or any(type(v) is not int for v in configuration.values())):
        raise ValueError('Exact qualified integer execution configuration required')
    header=_sealed(directory/'execution'/'execution_started.json')
    _require(_same({key:header[key] for key in DEFAULT_EXECUTION},configuration),
        'Actual execution scheduling differs from its qualified timing and frozen manifest')


def _cutoff(phase):
    return {'train':budget.TRAIN_CUTOFF,'development':budget.DEV_CUTOFF,'final':budget.FINAL_CUTOFF}[phase]


def _execute(campaign,authority,manifest,directory,registration):
    _require(source_pins()==manifest['source_sha256'],'Source drift before launch')
    authority.seal('start',dict(phase=registration['phase'],generation=registration['generation'],
        registration_sha256=design.sha((directory/'registration.json').read_bytes()),started_utc=now().isoformat(),
        planned_games=len(registration['fixtures'])),directory/'started.json')
    began=time.perf_counter()
    try:
        configuration=manifest.get('execution_configuration',DEFAULT_EXECUTION)
        runner.run_fixtures(registration,[f['id'] for f in registration['fixtures']],directory/'execution',
            device='cuda',**configuration)
        _assert_execution_configuration(directory,configuration)
        summary,aggregated=_verify_output(registration,directory)
        _require(source_pins()==manifest['source_sha256'],'Source drift after complete audit')
        _require(now()<=_cutoff(registration['phase']),'Completed cohort is past its eligibility deadline; preserve without selection')
        elapsed=time.perf_counter()-began
        payload=dict(phase=registration['phase'],generation=registration['generation'],completed_utc=now().isoformat(),
            registration_sha256=design.sha((directory/'registration.json').read_bytes()),
            originals_sha256=summary['originals_sha256'],audits_sha256=summary['audits_sha256'],
            original_games=aggregated['games'],independently_regenerated_callbacks=aggregated['games']*320,
            both_referees=True,aggregate=aggregated,
            execution_configuration=dict(configuration),
            execution_header_sha256=design.sha((directory/'execution'/'execution_started.json').read_bytes()),
            measurement=dict(games=aggregated['games'],wall_seconds=elapsed,full_actor_audits=aggregated['games'],both_referees=True),
            admission='Complete new deadline-protocol originals plus ALL fresh actor replays and both referees.',
            original_primary_campaign_credit=0,completed_per_game_bmcts_audits=0,promoted=False)
        authority.seal('acceptance',payload,directory/'accepted.json')
        return payload
    except BaseException as error:
        authority.seal('failure',dict(phase=registration['phase'],generation=registration['generation'],
            error_type=type(error).__name__,message=str(error),failed_utc=now().isoformat(),
            status='Preserve all partial evidence; no automatic resubmission or admission',admitted_games=0),directory/'failure_receipt.json')
        raise


def _validate_registration(campaign,authority,manifest,directory,phase,generation,bodies,boards):
    registration=_sealed(directory/'registration.json')
    entries=registration['candidates']
    _require([design.sha(Path(c['path']).read_bytes()) for c in entries]==[design.sha(b) for b in bodies],
        'Population lineage or exact candidate bytes changed')
    guards={str(ROOT/name):digest for name,digest in manifest['source_sha256'].items()}
    expected=design.cohort(phase,generation,boards,entries,guards)
    _require(_same(registration,expected),'Registration differs from exact canonical phase/map/population recipe')
    receipt=authority.read('registration',directory/'registration_receipt.json')
    _require(_same(receipt,dict(phase=phase,generation=generation,path=str(directory/'registration.json'),
        registration_sha256=design.sha((directory/'registration.json').read_bytes()),planned_games=len(registration['fixtures']),
        map_indices=[b['map_index'] for b in boards],candidate_sha256=[c['sha256'] for c in entries])),
        'Registration receipt does not match reconstructed exact cohort')
    return registration


def _validate_acceptance(campaign,authority,directory,registration,configuration=None):
    accepted=authority.read('acceptance',directory/'accepted.json')
    if configuration is not None:
        _assert_execution_configuration(directory,configuration)
        _require(_same(accepted['execution_configuration'],configuration)
            and accepted['execution_header_sha256']==design.sha((directory/'execution'/'execution_started.json').read_bytes()),
            'Admitted execution configuration/header differs from qualified timing')
    phase=registration['phase'];generation=registration['generation'];count=len(registration['fixtures'])
    started=authority.read('start',directory/'started.json')
    _require(started['phase']==phase and type(started['generation']) is int and started['generation']==generation
        and started['registration_sha256']==design.sha((directory/'registration.json').read_bytes())
        and type(started['planned_games']) is int and started['planned_games']==count,'Start receipt does not match exact cohort')
    _require(accepted['phase']==phase and type(accepted['generation']) is int and accepted['generation']==generation
        and accepted['registration_sha256']==design.sha((directory/'registration.json').read_bytes()),'Previous TRAIN receipt identity mismatch')
    start_time=datetime.fromisoformat(started['started_utc']);end_time=datetime.fromisoformat(accepted['completed_utc'])
    _require(start_time.tzinfo is not None and end_time.tzinfo is not None and budget.START<=start_time<=end_time<=_cutoff(phase),
        'Accepted cohort timestamps violate phase eligibility')
    _require(end_time<=now(),'A future receipt cannot be admitted as completed work')
    measurement=accepted['measurement'];rate=budget.conservative_rate([measurement])
    _require(measurement['games']==count and accepted['original_games']==count
        and type(accepted['independently_regenerated_callbacks']) is int and accepted['independently_regenerated_callbacks']==count*320
        and accepted['both_referees'] is True and accepted['promoted'] is False
        and abs((end_time-start_time).total_seconds()-measurement['wall_seconds'])<5,
        'Accepted coverage or measured complete-pipeline wall time is inconsistent')
    summary,aggregate=_verify_output(registration,directory)
    _require(measurement['wall_seconds']+1e-6>=summary['wall_before_final_publication_s'],
        'Accepted measurement cannot be shorter than its complete executor lifecycle')
    _require(all(type(accepted.get(k)) is int and accepted[k]==0
        for k in ('original_primary_campaign_credit','completed_per_game_bmcts_audits')),
        'Deadline acceptance cannot relabel primary or BMCTS credit')
    _require(_same(aggregate,accepted['aggregate']) and summary['originals_sha256']==accepted['originals_sha256']
        and summary['audits_sha256']==accepted['audits_sha256'],'Admitted TRAIN bytes or computed fitness changed')
    return accepted


def _train_chain(campaign,authority,manifest):
    boards=design.catalog();chain=[];generation=0;previous=None;bodies=None
    while (campaign/('train_%03d'%generation)/'accepted.json').exists():
        expected=design.initial_population() if generation==0 else design.next_population(bodies,previous['aggregate']['ranking'],generation)
        directory=campaign/('train_%03d'%generation)
        registration=_validate_registration(campaign,authority,manifest,directory,'train',generation,expected,
            boards[500+generation*16:516+generation*16])
        previous=_validate_acceptance(campaign,authority,directory,registration,manifest['execution_configuration'])
        if chain:
            started=authority.read('start',directory/'started.json')
            _require(datetime.fromisoformat(started['started_utc'])>=datetime.fromisoformat(chain[-1][0]['completed_utc']),
                'TRAIN generations overlap or reverse the accepted chronology')
        bodies=[Path(c['path']).read_bytes() for c in registration['candidates']]
        chain.append((previous,bodies));generation+=1
    _require(not any((path/'accepted.json').exists() for path in campaign.glob('train_[0-9][0-9][0-9]')
        if int(path.name[6:])>=generation),'Accepted TRAIN generation appears after a missing predecessor')
    return chain


def _heldout_absent(campaign):
    return not any((campaign/name).exists() for name in ('shortlist.json','development','dev_selection.json','final','final_decision.json'))


def _architecture():
    from local_cuda_analysis.report import analyze
    report=analyze(STUDY,REGISTRY)
    arms=sorted(report['arms'],key=lambda r:(-Fraction(r['pairwise_numerator_sum'],2*r['games']),
        -Fraction(r['raw_score_sum'],r['games']),r['sha256']))
    study=_read(STUDY)
    anchor=next(c for c in study['candidates'] if c['sha256']==arms[0]['sha256'])
    return report,dict(path=anchor['path'],sha256=anchor['sha256'])


def _shortlist_context(campaign,authority,manifest):
    short=authority.read('shortlist','shortlist.json');chain=_train_chain(campaign,authority,manifest)
    _require(chain and type(short.get('last_train_generation')) is int and short['last_train_generation']==len(chain)-1,
        'Shortlist must bind the last complete admitted TRAIN generation')
    previous,bodies=chain[-1];index=len(chain)-1
    _require(short['previous_acceptance_sha256']==design.sha((campaign/('train_%03d'%index)/'accepted.json').read_bytes())
        and short['candidate_sha256']==[design.sha(b) for b in bodies] and short['training_closed'] is True
        and short['heldout_outcomes_consumed'] is False,'Shortlist lineage or phase boundary changed')
    measurements=list(manifest['timing_measurements'])+[entry[0]['measurement'] for entry in chain]
    chosen=budget.heldout_budget(measurements)
    _require(_same(short['heldout_budget'],chosen) and _same(short['development_map_indices'],list(range(8000,8000+chosen['development_maps'])))
        and _same(short['final_map_indices'],list(range(9000,9000+chosen['final_maps']))),'Timing-only budget or reserved maps changed')
    saved=_sealed(campaign/'architecture_report.json');report,anchor=_architecture()
    _require(_same({k:v for k,v in saved.items() if k!='timings'},{k:v for k,v in report.items() if k!='timings'})
        and short['architecture_report_sha256']==design.sha((campaign/'architecture_report.json').read_bytes())
        and _same(short['anchor'],anchor),'Anchor is not the strongest complete authenticated architecture control')
    frozen_time=datetime.fromisoformat(short['frozen_utc'])
    _require(frozen_time.tzinfo is not None and datetime.fromisoformat(previous['completed_utc'])<=frozen_time<=budget.TRAIN_CUTOFF,
        'Invalid shortlist freeze timestamp')
    return short,bodies


def _development_context(campaign,authority,manifest,short,bodies):
    selection=authority.read('dev-selection','dev_selection.json')
    directory=campaign/'development';chosen=short['heldout_budget']
    registration=_validate_registration(campaign,authority,manifest,directory,'development',0,bodies,
        design.catalog()[8000:8000+chosen['development_maps']])
    accepted=_validate_acceptance(campaign,authority,directory,registration,manifest['execution_configuration'])
    started=authority.read('start',directory/'started.json')
    _require(datetime.fromisoformat(started['started_utc'])>=datetime.fromisoformat(short['frozen_utc']),
        'DEV began before its candidate population and map budget were frozen')
    winner=accepted['aggregate']['ranking'][0]['sha256']
    expected=dict(challenger=winner,anchor=short['anchor'],
        development_acceptance_sha256=design.sha((directory/'accepted.json').read_bytes()),
        challenger_path=next(c['path'] for c in registration['candidates'] if c['sha256']==winner),
        final_maps=short['final_map_indices'],final_frozen=True,final_outcomes_consumed=False,
        final_not_needed=winner==short['anchor']['sha256'])
    _require(_same({k:v for k,v in selection.items() if k!='selected_utc'},expected),'DEV selection does not match its complete admitted evidence')
    selected_time=datetime.fromisoformat(selection['selected_utc'])
    _require(selected_time.tzinfo is not None and datetime.fromisoformat(accepted['completed_utc'])<=selected_time<=budget.DEV_CUTOFF,
        'Invalid DEV selection freeze timestamp')
    return selection


def train_loop(campaign=CAMPAIGN):
    with CoordinatorLease(campaign),KeepAwake():
        campaign,authority,manifest=_context(campaign)
        _require(manifest.get('fallback_only') is not True,'Fallback-only campaign cannot execute new TRAIN games')
        _require(_heldout_absent(campaign),'TRAIN cannot continue after any heldout reservation, output or freeze')
        measurements=list(manifest['timing_measurements']);generation=0;previous=None;bodies=None
        chain=_train_chain(campaign,authority,manifest)
        for previous,bodies in chain:
            measurements.append(previous['measurement']);generation+=1
        while budget.may_start_generation(now(),measurements,games=8192,coaching_and_setup_seconds=600):
            bodies=design.initial_population() if generation==0 else design.next_population(bodies,previous['aggregate']['ranking'],generation)
            boards=design.catalog()[500+generation*16:516+generation*16]
            directory,registration=_registration(campaign,authority,manifest,'train',generation,bodies,boards)
            previous=_execute(campaign,authority,manifest,directory,registration)
            measurements.append(previous['measurement'])
            print(json.dumps(dict(completed_train_generation=generation,admitted_deadline_games=8192*(generation+1),
                current_generation=previous['aggregate']['ranking'],measurement=previous['measurement'])),flush=True)
            generation+=1
        return dict(completed_generations=generation,training_cutoff=budget.TRAIN_CUTOFF.isoformat(),
                    status='No additional complete generation fits with the frozen safety allowance')


def freeze_shortlist(campaign=CAMPAIGN):
    with CoordinatorLease(campaign):
        campaign,authority,manifest=_context(campaign)
        _require(not (campaign/'shortlist.json').exists(),'Shortlist is frozen once')
        generation=0;accepted=None;bodies=None;measurements=list(manifest['timing_measurements'])
        chain=_train_chain(campaign,authority,manifest)
        for accepted,bodies in chain:
            measurements.append(accepted['measurement']);generation+=1
        _require(accepted is not None,'At least one complete admitted TRAIN generation required')
        report,anchor=_architecture()  # rejects incomplete/unauthenticated architecture study
        chosen=budget.heldout_budget(measurements)
        _require(now()<=budget.TRAIN_CUTOFF,'Shortlist freeze is past the TRAIN boundary')
        _require(now().timestamp()+chosen['development_games']/chosen['conservative_games_per_second']+600
                 <=budget.DEV_CUTOFF.timestamp(),'Full development panel no longer fits before its deadline')
        frozen._seal(campaign/'architecture_report.json',report)
        payload=dict(frozen_utc=now().isoformat(),last_train_generation=generation-1,
            previous_acceptance_sha256=design.sha((campaign/('train_%03d'%(generation-1))/'accepted.json').read_bytes()),
            candidate_sha256=[design.sha(body) for body in bodies],anchor=anchor,
            architecture_report_sha256=design.sha((campaign/'architecture_report.json').read_bytes()),
            heldout_budget=chosen,development_map_indices=list(range(8000,8000+chosen['development_maps'])),
            final_map_indices=list(range(9000,9000+chosen['final_maps'])),
            training_closed=True,heldout_outcomes_consumed=False)
        authority.seal('shortlist',payload,'shortlist.json')
        return payload


def development(campaign=CAMPAIGN):
    with CoordinatorLease(campaign),KeepAwake():
        campaign,authority,manifest=_context(campaign);short,bodies=_shortlist_context(campaign,authority,manifest)
        chosen=short['heldout_budget']
        _require(now().timestamp()+chosen['development_games']/chosen['conservative_games_per_second']+600
                 <=budget.DEV_CUTOFF.timestamp(),'Cannot begin a complete development panel before its deadline')
        boards=design.catalog()[8000:8000+chosen['development_maps']]
        directory,registration=_registration(campaign,authority,manifest,'development',0,bodies,boards)
        accepted=_execute(campaign,authority,manifest,directory,registration)
        winner=accepted['aggregate']['ranking'][0]['sha256']
        payload=dict(selected_utc=now().isoformat(),challenger=winner,anchor=short['anchor'],
            development_acceptance_sha256=design.sha((directory/'accepted.json').read_bytes()),
            challenger_path=next(c['path'] for c in registration['candidates'] if c['sha256']==winner),
            final_maps=short['final_map_indices'],final_frozen=True,final_outcomes_consumed=False,
            final_not_needed=winner==short['anchor']['sha256'])
        authority.seal('dev-selection',payload,'dev_selection.json')
        return payload


def final(campaign=CAMPAIGN):
    with CoordinatorLease(campaign),KeepAwake():
        campaign,authority,manifest=_context(campaign);short,bodies=_shortlist_context(campaign,authority,manifest)
        selection=_development_context(campaign,authority,manifest,short,bodies);anchor=selection['anchor']
        _require(now()>=datetime.fromisoformat(selection['selected_utc']),'FINAL cannot begin before the DEV selection is frozen')
        _require(now()<=budget.FINAL_CUTOFF,'Final phase is past its reserved completion boundary')
        if selection['final_not_needed']:
            payload=dict(selected=anchor['sha256'],promoted=False,reason='DEV selected the validated anchor itself; no redundant FINAL.',
                         final_games=0,completed_utc=now().isoformat(),primary_campaign_credit=0,bmcts_credit=0)
        else:
            chosen=short['heldout_budget']
            _require(now().timestamp()+chosen['final_games']/chosen['conservative_games_per_second']+600
                <=budget.FINAL_CUTOFF.timestamp(),'Cannot begin complete untouched final before reserved packaging time')
            bodies=[Path(selection['challenger_path']).read_bytes(),Path(anchor['path']).read_bytes()]
            _require([design.sha(b) for b in bodies]==[selection['challenger'],anchor['sha256']],'Frozen final source changed')
            boards=design.catalog()[9000:9000+chosen['final_maps']]
            directory,registration=_registration(campaign,authority,manifest,'final',0,bodies,boards)
            accepted=_execute(campaign,authority,manifest,directory,registration)
            payload=evaluation.final_decision(accepted['aggregate'],selection['challenger'],anchor['sha256'])
            payload.update(completed_utc=now().isoformat(),final_acceptance_sha256=design.sha((directory/'accepted.json').read_bytes()))
        authority.seal('final-decision',payload,'final_decision.json')
        return payload


def fallback(campaign=CAMPAIGN):
    """Return the predeclared independently validated anchor, never a new winner."""
    with CoordinatorLease(campaign):
        _require(Path(campaign).resolve()==CAMPAIGN.resolve(),'Fallback uses the same canonical owner output')
        if not Path(campaign).exists():
            # The new backend may fail qualification or not fit the minimum
            # panels. An already complete authenticated architecture study is
            # sufficient for its own reference release; do not demand a new
            # campaign that could never have been initialized.
            _require(now()<=budget.DEADLINE,'Delivery deadline has expired')
            report,anchor=_architecture()
            Path(campaign).mkdir(parents=True,exist_ok=False)
            manifest=dict(format=design.FORMAT,created_utc=now().isoformat(),fallback_only=True,
                start_utc=budget.START.isoformat(),deadline_utc=budget.DEADLINE.isoformat(),
                source_sha256=source_pins(),catalog_sha256=design.CATALOG_SHA256,
                reason='New deadline pipeline qualification/budget unavailable; validated architecture reference only.',
                new_games_executed=0,original_primary_campaign_credit=0,bmcts_credit=0)
            frozen._seal(Path(campaign)/'manifest.json',manifest)
            authority=Authority.create(campaign)
            authority.seal('manifest',dict(manifest_sha256=authority.manifest_sha256,created_utc=now().isoformat()),'manifest_receipt.json')
        campaign,authority,manifest=_context(campaign)
        _require(now()<=budget.DEADLINE,'Delivery deadline has expired')
        report,anchor=_architecture()
        if (campaign/'shortlist.json').exists():
            short,bodies=_shortlist_context(campaign,authority,manifest)
            _require(short['anchor']==anchor,'Frozen anchor changed')
        payload=dict(selected=anchor['sha256'],selected_source=anchor['path'],promoted=False,
            reason='A complete eligible challenger comparison is unavailable; retain the independently validated architecture anchor.',
            final_comparison_claim=False,completed_utc=now().isoformat(),primary_campaign_credit=0,bmcts_credit=0)
        authority.seal('final-decision',payload,'final_decision.json')
        return payload


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('prepare','train','freeze','development','final','fallback'))
    parser.add_argument('--benchmark',type=Path)
    parser.add_argument('--scheduling',type=Path)
    args=parser.parse_args()
    if args.action=='prepare': result=prepare(args.benchmark,args.scheduling)
    elif args.action=='train': result=train_loop()
    elif args.action=='freeze': result=freeze_shortlist()
    elif args.action=='development': result=development()
    elif args.action=='final': result=final()
    else: result=fallback()
    print(json.dumps(result,sort_keys=True),flush=True)


if __name__=='__main__':main()
