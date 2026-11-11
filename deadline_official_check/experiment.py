"""Owner-launched official-generator release check; never tune a policy here.

No function is called on import. Metadata freeze/amendment precedes DEV; actual
execution is available only after a separate published owner authorization and
the original primary final decision. Workers receive no authority capability.
"""
import copy
import argparse
from datetime import datetime,timedelta,timezone
from fractions import Fraction
from pathlib import Path
import re
import time

from deadline_campaign import budget,controller,design,evaluation
from deadline_runner import runner
from deadline_runner.verify import verify_execution
from local_cuda_matches import runner as frozen
from . import maps

ROOT=maps.ROOT
FORMAT='deadline-official-generator-final-release-check/1'
ROLE='separate_official_generator_final_release_check'
DIRECTORY='official_release_check'
MAPS=ROOT/'deadline_official_check/evidence/maps_001.json'
CUTOFF=datetime(2026,11,9,10,58,tzinfo=timezone.utc)
HEADROOM=600
PRIMARY_PROOF_HEADROOM=900
GAMES=8192
E8='e8b3682d8b39d3fc4d22cdcd8927161290a90cd472d3ede4132ae716f8c6f8f5'
PUBLIC_QUAD_REPORT='local_cuda_analysis/evidence/architecture_v2_001/report.json'
PUBLIC_QUAD_SHA256='6a76e981432d13638a873ba4b45db6c3259707a45a8d26b6b8b0bf5ece915147'
RIVALS={'planner':E8,'research':'6f2ac1487cd0a66793db3f2fab01f621d9c945a4f71a78cc92d176ef1de321f4',
    'racer':'a35c2c4811645091adef6cbd263f1573bf2b184d5dd5741a070234a422ce54c8',
    'blocker':'1bb70109a75e2880bfdf3ac9b6fd8e368b0f3d02b9a3e65de53cef0defa505e5'}
canonical=maps.canonical
sha=maps.sha


def now(): return datetime.now(timezone.utc)
def require(condition,message):
    if not condition: raise ValueError(message)
def same(left,right): return canonical(left)==canonical(right)
def read(path): return frozen.oversight.strict_loads(Path(path).read_bytes())
def sealed(path): return controller._sealed(Path(path))


def source_pins():
    pins=controller.source_pins()
    from deadline_finalization import cache
    pins.update(cache.source_pins())
    require(sha((ROOT/PUBLIC_QUAD_REPORT).read_bytes())==PUBLIC_QUAD_SHA256,'Published historical architecture proof changed')
    pins[PUBLIC_QUAD_REPORT]=PUBLIC_QUAD_SHA256
    for name in ('__init__.py','maps.py','experiment.py','METHOD.md'):
        relative='deadline_official_check/'+name;pins[relative]=sha((ROOT/relative).read_bytes())
    pins['primary_migration/contract.py']=sha((ROOT/'primary_migration/contract.py').read_bytes())
    return dict(sorted(pins.items()))


def protocol(map_artifact):
    return dict(format=FORMAT,role=ROLE,maps_sha256=sha(Path(map_artifact).read_bytes()),
        maps=64,arms=2,fields=list(design.FIELDS),seat_token_crosses=16,complete_games=GAMES,
        rounds=1,extension_allowed=False,retry_allowed=False,parameters_fixed=True,
        rival_recipe='design._rivals(final,0,12000+official_map_index,field_index,seat,token,slot); matched parameters/RNG, fresh namespaces/IDs.',
        rival_coordinate_start=12000,qualified_rival_sources=dict(RIVALS),old_e8=E8,
        endpoint='Matched final pairwise points0..3, equal map/field/seat/token weights; whole64-map blocks.',
        bootstrap=dict(replicates=evaluation.BOOTSTRAP_REPLICATES,seed=evaluation.BOOTSTRAP_SEED,
            shared_map_draws=True,overall_order_statistics=[499,19499],field_lower_order_statistic=249),
        release_rule='Use primary-selected body only if overall95% paired-map bootstrap lower>0 AND every4 Bonferroni one-sided field lower>-.05PW; otherwise oldE8.',
        availability_rule='Before execution only: if selected==E8 skip redundant games; otherwise launch only if all8192/full audits fit conservative measured rate plus600s setup/admission headroom and900s primary-proof reserve before10:58:00UTC. If unavailable retain primary validated decision with official-generator-unconfirmed scope.',
        after_start_failure='Any failed/incomplete/late full panel retains oldE8; no partial-result release selection.',
        completion_cutoff_utc=CUTOFF.isoformat(),headroom_seconds=HEADROOM,primary_proof_headroom_seconds=PRIMARY_PROOF_HEADROOM,
        total_reserved_seconds=HEADROOM+PRIMARY_PROOF_HEADROOM,safety_factor=budget.SAFETY_FACTOR,
        primary_decision_preserved=True,old_primary_campaign_credit=0,completed_per_game_bmcts_audits=0,
        scope='Separate conditional fresh-official-orbit domain check, not a rewritten primary decision, unconditional official-distribution estimate, universal optimum or unknown-rival claim.')


def _check_authority(campaign,authority):
    require(type(authority) is controller.Authority and campaign==controller.CAMPAIGN.resolve()
        and Path(authority.campaign).resolve()==campaign,'Exact existing canonical owner authority required')


def _owner(campaign,authority):
    campaign=Path(campaign).resolve()
    _check_authority(campaign,authority)
    require(campaign==Path(authority.campaign).resolve(),'Owner campaign mismatch')
    require(sha((campaign/'manifest.json').read_bytes())==authority.manifest_sha256,'Owner primary manifest changed')
    require(same(read(campaign/'manifest.json')['source_sha256'],controller.source_pins()),'Frozen primary runtime changed')
    return campaign


def amend(campaign,authority,map_artifact=MAPS):
    """Root only: seal the prospective method/maps BEFORE any DEV directory."""
    campaign=_owner(campaign,authority)
    require(not (campaign/'development').exists() and not (campaign/'dev_selection.json').exists()
        and not (campaign/'final_decision.json').exists(),'Official check amendment must precede DEV/final')
    value=maps.validate(map_artifact);directory=campaign/DIRECTORY;directory.mkdir(exist_ok=False)
    frozen._seal(directory/'maps.json',value)
    plan=dict(protocol=protocol(directory/'maps.json'),source_sha256=source_pins(),
        frozen_maps_created_utc=value['created_utc'],amended_utc=now().isoformat(),
        primary_manifest_sha256=authority.manifest_sha256,role=ROLE)
    frozen._seal(directory/'plan.json',plan)
    receipt=dict(role=ROLE,plan_sha256=sha((directory/'plan.json').read_bytes()),
        maps_sha256=sha((directory/'maps.json').read_bytes()),source_sha256=plan['source_sha256'],
        method_before_dev=True,primary_manifest_sha256=authority.manifest_sha256)
    authority.seal('manifest',receipt,directory/'amendment_receipt.json')
    return plan


def authorize_publication(campaign,authority,published_commit):
    """Root calls only after reviewing and publishing this exact source/plan."""
    campaign, directory,plan=_context(campaign,authority,published=False)
    require(type(published_commit) is str and re.fullmatch('[0-9a-f]{40}',published_commit) is not None,'Exact published Git commit required')
    require(not (campaign/'development').exists(),'Publication authorization must precede DEV')
    payload=dict(role=ROLE,published_commit=published_commit,plan_sha256=sha((directory/'plan.json').read_bytes()),
        maps_sha256=plan['protocol']['maps_sha256'],source_sha256=plan['source_sha256'],approved_after_review=True,
        published_utc=now().isoformat())
    authority.seal('manifest',payload,directory/'published_receipt.json')
    return payload


def _context(campaign,authority,published=True):
    campaign=_owner(campaign,authority);directory=campaign/DIRECTORY;plan=sealed(directory/'plan.json')
    require(plan.get('role')==ROLE and plan['primary_manifest_sha256']==authority.manifest_sha256,'Foreign official-check plan')
    require(same(plan['source_sha256'],source_pins()),'Official-check runtime source changed')
    map_value=maps.validate(directory/'maps.json')
    map_time=_utc(map_value['created_utc']);amended_time=_utc(plan['amended_utc'])
    require(map_time<=amended_time<=now() and plan['frozen_maps_created_utc']==map_value['created_utc'],
        'Official map freeze/amendment UTC chronology invalid')
    require(same(plan['protocol'],protocol(directory/'maps.json')),'Official-check semantic protocol changed')
    receipt=authority.read('manifest',directory/'amendment_receipt.json')
    expected=dict(role=ROLE,plan_sha256=sha((directory/'plan.json').read_bytes()),
        maps_sha256=sha((directory/'maps.json').read_bytes()),source_sha256=plan['source_sha256'],
        method_before_dev=True,primary_manifest_sha256=authority.manifest_sha256)
    require(same(receipt,expected),'Owner amendment/source/map binding changed')
    if published:
        approval=authority.read('manifest',directory/'published_receipt.json')
        require(approval.get('role')==ROLE and approval.get('approved_after_review') is True
            and re.fullmatch('[0-9a-f]{40}',approval.get('published_commit','')) is not None
            and approval.get('plan_sha256')==expected['plan_sha256'] and approval.get('maps_sha256')==expected['maps_sha256']
            and same(approval.get('source_sha256'),plan['source_sha256']),'Published root approval missing or changed')
        published_time=_utc(approval['published_utc'])
        require(amended_time<=published_time<=now(),'Official publication UTC chronology invalid')
        if (campaign/'development/started.json').exists():
            development_start=authority.read('start',campaign/'development/started.json')
            require(published_time<=_utc(development_start['started_utc']),'Official method/maps were not published before DEV')
    return campaign,directory,plan


def availability(timestamp,selected,measurements):
    require(isinstance(timestamp,datetime) and timestamp.tzinfo is not None and timestamp.utcoffset()==timedelta(0),'Explicit UTC availability time required')
    if selected==E8:
        return dict(status='already_e8',selected=E8,planned_games=0,checked_utc=timestamp.isoformat(),official_generator_confirmed=False)
    rate=budget.conservative_rate(measurements);seconds=GAMES/rate+HEADROOM+PRIMARY_PROOF_HEADROOM
    return dict(status='available' if timestamp+timedelta(seconds=seconds)<=CUTOFF else 'unavailable',
        selected=selected,planned_games=GAMES,checked_utc=timestamp.isoformat(),conservative_games_per_second=rate,
        complete_panel_estimated_seconds=GAMES/rate,headroom_seconds=HEADROOM,
        primary_proof_headroom_seconds=PRIMARY_PROOF_HEADROOM,total_reserved_seconds=HEADROOM+PRIMARY_PROOF_HEADROOM,
        cutoff_utc=CUTOFF.isoformat(),
        latest_start_utc=(CUTOFF-timedelta(seconds=seconds)).isoformat(),official_generator_confirmed=False)


def _timings(campaign,authority):
    header=read(campaign/'manifest.json');measurements=copy.deepcopy(header['timing_measurements']);proof=[]
    paths=sorted(campaign.glob('train_*/accepted.json'))
    paths += [p for p in (campaign/'development/accepted.json',campaign/'final/accepted.json') if p.exists()]
    for path in paths:
        receipt=authority.read('acceptance',path)
        require(receipt.get('both_referees') is True and type(receipt.get('original_games')) is int
            and receipt['original_games']==receipt['measurement']['games']
            and type(receipt.get('independently_regenerated_callbacks')) is int
            and receipt['independently_regenerated_callbacks']==receipt['original_games']*320,
            'Timing must come from a complete authenticated original/full-audit phase')
        budget.conservative_rate([receipt['measurement']]);measurements.append(receipt['measurement'])
        proof.append(dict(path=path.relative_to(campaign).as_posix(),sha256=sha(path.read_bytes()),measurement=receipt['measurement']))
    budget.conservative_rate(measurements)
    return measurements,proof,copy.deepcopy(header['execution_configuration'])


def registration(map_records,candidates,guards):
    require(type(map_records) is list and len(map_records)==64 and len({b['rotation_orbit'] for b in map_records})==64,'Exactly64 frozen unique official map orbits required')
    require(type(candidates) is list and len(candidates)==2 and candidates[1]['sha256']==E8 and candidates[0]['sha256']!=E8,'Two distinct exact arms, primary selected then oldE8, required')
    for entry in candidates:
        require(type(entry) is dict and set(entry)=={'path','sha256'} and sha(Path(entry['path']).read_bytes())==entry['sha256'],'Exact candidate bytes changed')
    sources=design.original_sources()
    require({name:entry['sha256'] for name,entry in sources.items()}==RIVALS,'Fixed qualified rival source family changed')
    fixtures=[]
    for index,board in enumerate(map_records):
        require(board['map_index']==index and board['id']==sha(bytes(board['base'])) and board['rotation_orbit']==maps.rotation_orbit(board['base']),'Frozen official map identity changed')
        for fi,field in enumerate(design.FIELDS):
            for seat in range(4):
                for token in range(1,5):
                    for slot,candidate in enumerate(candidates):
                        fixture=dict(map_id=board['id'],map_index=index,base=list(board['base']),map_family=board['family'],
                            map_origin='fresh_official_generator_not_primary_catalog',rival_map_coordinate=12000+index,
                            seat=seat,token=token,field=field,candidate_slot=slot,candidate=candidate['sha256'],
                            opponents=design._rivals('final',0,12000+index,fi,seat,token,slot),
                            phase='official-release-check',generation=0)
                        fixture['focal_actor_id']=sha(canonical([FORMAT,'focal',fixture]));fixture['id']=sha(canonical(fixture));fixtures.append(fixture)
    require(len(fixtures)==GAMES and len({f['id'] for f in fixtures})==GAMES,'Complete official crossing identity failure')
    require(len({r['id'] for f in fixtures for r in f['opponents']})==GAMES*3,'Rival instance identity reused')
    return dict(format=FORMAT,role=ROLE,phase='official-release-check',generation=0,rules={'catch_requires_stay':True},
        candidates=copy.deepcopy(candidates),sources=sources,guards=copy.deepcopy(guards),fixtures=fixtures,
        protocol=dict(complete_games=GAMES,maps=64,candidates=2,fields=list(design.FIELDS),seat_token_crosses=16,
            matched_rival_streams=True,primary_campaign_credit=0,bmcts_credit=0,promoted=False))


def _public_architecture():
    """Reuse the exact published, fully reviewed quad report without a registry."""
    report_path=ROOT/PUBLIC_QUAD_REPORT
    require(sha(report_path.read_bytes())==PUBLIC_QUAD_SHA256,'Published complete architecture report changed')
    report=read(report_path)
    study_path=ROOT/'.cache/confirmation/architectures_v2_001/registration.json'
    require(sha(study_path.read_bytes())==maps.INPUTS[study_path.relative_to(ROOT).as_posix()],'Pinned quad metadata changed')
    study=read(study_path);entries={c['sha256']:dict(path=c['path'],sha256=c['sha256']) for c in study['candidates']}
    expected={E8,'50d82d7ac58162e9cf651136afcedac5586db9a060f153854b00875f13efef37',
        RIVALS['blocker'],'f95dc9fc22660331b1368a876d907f111fd3cb21aef6e3e34315b41e6af94e94'}
    require(report.get('format')=='zone-rush-owner-local-cuda-architecture-report/1'
        and report['coverage']['complete'] is True and report['coverage']['unique_games']==32768
        and report['coverage']['maps']==128 and set(entries)==expected
        and {a['sha256'] for a in report['arms']}==expected,'Exact published four-arm anchor proof required')
    arms=sorted(report['arms'],key=lambda r:(-Fraction(r['pairwise_numerator_sum'],2*r['games']),
        -Fraction(r['raw_score_sum'],r['games']),r['sha256']))
    anchor=entries[arms[0]['sha256']]
    require(sha(Path(anchor['path']).read_bytes())==anchor['sha256'],'Published validated anchor source changed')
    return report,anchor


def primary_context(campaign,authority):
    """Read-only reconstruction of the original primary phase semantics/proofs.

    Existing exact-source integrity certificates are read when present. Otherwise
    the unchanged full durable verifier runs; no certificate is minted and no
    callback/physics/private quad registry is used. The original function globals
    remain untouched. The historical anchor comes from pinned public evidence.
    """
    from deadline_finalization import cache
    _,anchor=_public_architecture();manifest=read(campaign/'manifest.json')
    primary=authority.read('final-decision',campaign/'final_decision.json')
    if primary.get('final_comparison_claim') is False:
        return dict(kind='fallback',anchor=anchor,earliest=manifest['created_utc'],latest=budget.DEADLINE.isoformat(),
            source_entries=[anchor])
    require((campaign/'shortlist.json').exists(),'Normal primary final requires a frozen authenticated shortlist')
    integrity=cache.IntegrityCache(campaign,authority)
    namespace=cache.cloned_phase_namespace(integrity)
    def old_output(reg,directory):
        certificate=integrity.folder/(directory.name+'.json')
        return integrity.read(reg,directory) if certificate.exists() else controller._verify_output(reg,directory)
    namespace['_verify_output']=old_output;namespace['_architecture']=_public_architecture
    short,bodies=namespace['_shortlist_context'](campaign,authority,manifest)
    selection=namespace['_development_context'](campaign,authority,manifest,short,bodies)
    if selection['final_not_needed']:
        return dict(kind='no_final_needed',anchor=anchor,selection=selection,earliest=selection['selected_utc'],
            latest=budget.FINAL_CUTOFF.isoformat(),source_entries=[anchor])
    directory=campaign/'final'
    entries=[dict(path=selection['challenger_path'],sha256=selection['challenger']),anchor]
    candidate_bodies=[Path(c['path']).read_bytes() for c in entries]
    catalog=design.catalog();boards=[catalog[index] for index in short['final_map_indices']]
    registration=namespace['_validate_registration'](campaign,authority,manifest,directory,'final',0,candidate_bodies,boards)
    accepted=namespace['_validate_acceptance'](campaign,authority,directory,registration,manifest['execution_configuration'])
    started=authority.read('start',directory/'started.json')
    require(datetime.fromisoformat(started['started_utc'])>=datetime.fromisoformat(selection['selected_utc']),
        'Primary FINAL began before its frozen DEV source choice')
    return dict(kind='comparison',anchor=anchor,selection=selection,accepted=accepted,
        acceptance_sha256=sha((directory/'accepted.json').read_bytes()),source_entries=registration['candidates'],
        earliest=accepted['completed_utc'],latest=budget.FINAL_CUTOFF.isoformat())


def primary_expected(context,completed_utc):
    """Exact primary payload recipe, separately testable without old proof I/O."""
    anchor=context['anchor']
    if context['kind']=='comparison':
        expected=evaluation.final_decision(context['accepted']['aggregate'],context['selection']['challenger'],anchor['sha256'])
        expected.update(completed_utc=completed_utc,final_acceptance_sha256=context['acceptance_sha256'])
    elif context['kind']=='no_final_needed':
        expected=dict(selected=anchor['sha256'],promoted=False,reason='DEV selected the validated anchor itself; no redundant FINAL.',
            final_games=0,completed_utc=completed_utc,primary_campaign_credit=0,bmcts_credit=0)
    elif context['kind']=='fallback':
        expected=dict(selected=anchor['sha256'],selected_source=anchor['path'],promoted=False,
            reason='A complete eligible challenger comparison is unavailable; retain the independently validated architecture anchor.',
            final_comparison_claim=False,completed_utc=completed_utc,primary_campaign_credit=0,bmcts_credit=0)
    else: raise ValueError('Unknown validated primary decision context')
    return expected


def _primary(campaign,authority,selected_entry):
    require(type(selected_entry) is dict and set(selected_entry)=={'path','sha256'} and type(selected_entry['path']) is str,
        'Exact selected source path/SHA only; no authority or private spec fields')
    decision=authority.read('final-decision',campaign/'final_decision.json')
    require(decision.get('role')!=ROLE and decision.get('selected')==selected_entry['sha256'],'Official arm must equal the unchanged primary final decision')
    require(sha(Path(selected_entry['path']).read_bytes())==selected_entry['sha256'],'Primary-selected source changed')
    context=primary_context(campaign,authority)
    completed=_utc(decision['completed_utc']);earliest=_utc(context['earliest']);latest=_utc(context['latest'])
    require(budget.START<=earliest<=completed<=latest and completed<=now(),'Primary final decision chronology invalid')
    require(same(decision,primary_expected(context,decision['completed_utc'])),'Primary decision does not match its validated frozen phase semantics')
    allowed={c['sha256']:c for c in context['source_entries']}
    require(decision['selected'] in allowed and sha(Path(allowed[decision['selected']]['path']).read_bytes())==decision['selected'],
        'Primary selection is not an exact tested final arm or validated architecture anchor')
    return decision,sha((campaign/'final_decision.json').read_bytes())


def _utc(value):
    parsed=datetime.fromisoformat(value)
    require(parsed.tzinfo is not None and parsed.utcoffset()==timedelta(0),'Exact UTC timestamp required')
    return parsed


def _release(directory,authority,selected,primary_sha,status,**extra):
    payload=dict(format=FORMAT,role=ROLE,status=status,selected=selected,primary_final_decision_sha256=primary_sha,
        plan_sha256=sha((directory/'plan.json').read_bytes()),prepared_sha256=sha((directory/'prepared.json').read_bytes()),
        official_panel_completed=status=='complete',primary_decision_unchanged=True,completed_utc=now().isoformat(),primary_campaign_credit=0,
        completed_per_game_bmcts_audits=0,**extra)
    authority.seal('final-decision',payload,directory/'release_decision.json');return payload


def prepare(campaign,authority,selected_entry):
    """Root only, AFTER primary FINAL. No callback; one immutable registration."""
    campaign,directory,plan=_context(campaign,authority);decision,primary_sha=_primary(campaign,authority,selected_entry)
    require(not (directory/'prepared.json').exists() and not (directory/'release_decision.json').exists(),'One preparation/decision only')
    emergency=decision.get('final_comparison_claim') is False
    if decision['selected']==E8 or emergency:
        measurements,timing_proof,configuration=[],[],read(campaign/'manifest.json').get('execution_configuration',{})
    else: measurements,timing_proof,configuration=_timings(campaign,authority)
    available=(dict(status='primary_fallback_unconfirmed',selected=decision['selected'],planned_games=0,
        checked_utc=now().isoformat(),official_generator_confirmed=False) if emergency
        else availability(now(),decision['selected'],measurements))
    prepared=dict(role=ROLE,selected_source=dict(selected_entry),primary_final_decision_sha256=primary_sha,
        availability=available,timing_receipts=timing_proof,measurements=measurements,execution_configuration=configuration)
    frozen._seal(directory/'prepared.json',prepared)
    if available['status']!='available':
        return _release(directory,authority,decision['selected'],primary_sha,available['status'],
            official_generator_confirmed=False,official_games=0,promoted=False,
            scope='Primary validated decision retained; official-generator confirmation unavailable or redundant.',availability=available)
    candidates=[];candidate_dir=directory/'candidates';candidate_dir.mkdir(exist_ok=False)
    for source in (selected_entry,dict(path=str(ROOT/'bot.py'),sha256=E8)):
        body=Path(source['path']).read_bytes();require(sha(body)==source['sha256'],'Frozen arm source changed')
        path=candidate_dir/(source['sha256']+'.py')
        with path.open('xb') as stream: stream.write(body)
        candidates.append(dict(path=str(path),sha256=source['sha256']))
    reg=registration(sealed(directory/'maps.json')['maps'],candidates,{str(ROOT/p):h for p,h in plan['source_sha256'].items()})
    frozen._seal(directory/'registration.json',reg)
    authority.seal('registration',dict(role=ROLE,registration_sha256=sha((directory/'registration.json').read_bytes()),
        prepared_sha256=sha((directory/'prepared.json').read_bytes()),
        plan_sha256=sha((directory/'plan.json').read_bytes()),selected_source_sha256=decision['selected'],old_e8_sha256=E8,
        primary_final_decision_sha256=primary_sha,complete_games=GAMES),directory/'registration_receipt.json')
    return prepared


def _registered(campaign,authority):
    campaign,directory,plan=_context(campaign,authority);prepared=sealed(directory/'prepared.json')
    primary,primary_sha=_primary(campaign,authority,prepared['selected_source'])
    require(prepared.get('role')==ROLE and prepared['primary_final_decision_sha256']==primary_sha,'Prepared primary binding changed')
    require(primary.get('final_comparison_claim') is not False and prepared['availability']['status']=='available',
        'Only normal authenticated primary DEV/FINAL permits the official execution extension')
    reg=sealed(directory/'registration.json')
    expected=registration(sealed(directory/'maps.json')['maps'],reg['candidates'],{str(ROOT/p):h for p,h in plan['source_sha256'].items()})
    require(same(reg,expected),'Official registration semantic/source/map drift')
    receipt=authority.read('registration',directory/'registration_receipt.json')
    expected_receipt=dict(role=ROLE,registration_sha256=sha((directory/'registration.json').read_bytes()),
        prepared_sha256=sha((directory/'prepared.json').read_bytes()),
        plan_sha256=sha((directory/'plan.json').read_bytes()),selected_source_sha256=primary['selected'],old_e8_sha256=E8,
        primary_final_decision_sha256=primary_sha,complete_games=GAMES)
    require(same(receipt,expected_receipt),'Official owner registration receipt changed')
    require([c['sha256'] for c in reg['candidates']]==[primary['selected'],E8],'Primary/E8 arm binding changed')
    return campaign,directory,plan,prepared,reg,primary_sha


def endpoint(reg,rows):
    require(reg.get('role')==ROLE and len(reg['fixtures'])==GAMES,'Exact complete official cohort required')
    aggregated=evaluation.aggregate(reg,rows)
    require(len(aggregated['maps'])==64 and aggregated['games']==GAMES,'No partial or extended official endpoint')
    result=evaluation.final_decision(aggregated,reg['candidates'][0]['sha256'],E8)
    result.update(role=ROLE,official_generator_confirmed=True,policy_parameters_tuned=False,
        primary_decision_unchanged=True,original_primary_campaign_credit=0)
    return result,aggregated


def _execute_claimed(campaign,authority,directory,plan,prepared,reg,primary_sha):
    began=time.perf_counter()
    # Time-only recheck occurs before the start seal/callbacks. No outcome input.
    measurements,timing_proof,configuration=_timings(campaign,authority)
    require(same(configuration,prepared['execution_configuration']),'Qualified execution scheduling changed')
    require(same(measurements,prepared['measurements']) and same(timing_proof,prepared['timing_receipts']),
        'Timing inputs changed after preparation; no outcome-dependent availability replacement')
    available=availability(now(),reg['candidates'][0]['sha256'],measurements)
    if available['status']!='available':
        return _release(directory,authority,reg['candidates'][0]['sha256'],primary_sha,'unavailable_before_execution',
            official_generator_confirmed=False,official_games=0,promoted=False,availability=available)
    started=dict(role=ROLE,started_utc=now().isoformat(),registration_sha256=sha((directory/'registration.json').read_bytes()),
        planned_games=GAMES,availability=available,execution_configuration=configuration)
    authority.seal('start',started,directory/'started.json')
    runner.run_fixtures(reg,[f['id'] for f in reg['fixtures']],directory/'execution',device='cuda',**configuration)
    controller._assert_execution_configuration(directory,configuration)
    verified=verify_execution(reg,directory/'execution')
    result,aggregate=endpoint(reg,verified['rows'])
    _registered(campaign,authority)
    require(now()<=CUTOFF,'Full official panel completed after fixed deadline')
    elapsed=time.perf_counter()-began
    require(elapsed>=verified['summary']['wall_before_final_publication_s'],'Outer timing shorter than complete pipeline')
    accepted=dict(role=ROLE,registration_sha256=started['registration_sha256'],source_sha256=plan['source_sha256'],
        primary_final_decision_sha256=primary_sha,completed_utc=now().isoformat(),original_games=GAMES,
        independently_regenerated_callbacks=GAMES*320,both_referees=True,aggregate=aggregate,
        originals_sha256=verified['summary']['originals_sha256'],audits_sha256=verified['summary']['audits_sha256'],
        measurement=dict(games=GAMES,wall_seconds=elapsed,full_actor_audits=GAMES,both_referees=True),
        old_primary_campaign_credit=0,completed_per_game_bmcts_audits=0)
    authority.seal('acceptance',accepted,directory/'accepted.json')
    return _release(directory,authority,result['selected'],primary_sha,'complete',official_generator_confirmed=True,
        official_games=GAMES,promoted=result['promoted'],endpoint=result,acceptance_sha256=sha((directory/'accepted.json').read_bytes()))


def execute(campaign,authority):
    """Root explicitly launches ONCE after published approval. Actual CUDA here."""
    campaign,directory,plan,prepared,reg,primary_sha=_registered(campaign,authority)
    require(not (directory/'release_decision.json').exists(),'Official check already has a final decision')
    (directory/'.execution_claim').mkdir(exist_ok=False)
    try:
        return _execute_claimed(campaign,authority,directory,plan,prepared,reg,primary_sha)
    except BaseException as error:
        failure=dict(role=ROLE,error_type=type(error).__name__,message=str(error),failed_utc=now().isoformat(),
            selected_fallback=E8,official_admitted_games=0,primary_campaign_credit=0,completed_per_game_bmcts_audits=0)
        try:
            authority.seal('failure',failure,directory/'failure_receipt.json')
            _release(directory,authority,E8,primary_sha,'failed_or_incomplete',official_generator_confirmed=False,
                official_games=0,promoted=False,failure_receipt_sha256=sha((directory/'failure_receipt.json').read_bytes()))
        except BaseException as receipt_error:
            frozen._seal(directory/'unsealed_failure.json',dict(failure,receipt_error_type=type(receipt_error).__name__,receipt_error=str(receipt_error)))
        raise


def verify_complete(campaign,authority):
    """Read-only final check; no callbacks, CUDA or new games."""
    campaign,directory,plan=_context(campaign,authority)
    final=authority.read('final-decision',directory/'release_decision.json')
    require(final.get('role')==ROLE and final.get('primary_decision_unchanged') is True,'Foreign release-check decision')
    require(type(final.get('official_games')) is int and type(final.get('promoted')) is bool,'Exact official coverage/promotion types required')
    require(final.get('official_panel_completed') is (final.get('status')=='complete'),'Official panel completion differs from release superiority gate')
    if final['status']=='complete':
        campaign,directory,plan,prepared,reg,primary_sha=_registered(campaign,authority)
        primary=authority.read('final-decision',campaign/'final_decision.json')
        require(sha((campaign/'final_decision.json').read_bytes())==primary_sha,'Primary changed during read-only admission')
    else:
        prepared=sealed(directory/'prepared.json');primary,primary_sha=_primary(campaign,authority,prepared['selected_source'])
    require(final['primary_final_decision_sha256']==primary_sha,'Primary decision changed after official check')
    require(final.get('prepared_sha256')==sha((directory/'prepared.json').read_bytes())
        and final.get('plan_sha256')==sha((directory/'plan.json').read_bytes()),'Final decision plan/preparation binding changed')
    if final['status']=='complete':
        require(not (directory/'failure_receipt.json').exists(),'Failed execution cannot be admitted')
        started=authority.read('start',directory/'started.json');accepted=authority.read('acceptance',directory/'accepted.json')
        require(set(started)=={'role','started_utc','registration_sha256','planned_games','availability','execution_configuration'}
            and type(started.get('planned_games')) is int and started['planned_games']==GAMES
            and same(started.get('execution_configuration'),prepared['execution_configuration']),
            'Exact official start coverage/scheduling fields changed')
        require(started.get('role')==accepted.get('role')==ROLE and started['registration_sha256']==accepted['registration_sha256']==sha((directory/'registration.json').read_bytes()),'Start/acceptance registration binding changed')
        require(_utc(primary['completed_utc'])<=_utc(started['started_utc'])<=_utc(accepted['completed_utc'])<=CUTOFF
            and _utc(started['availability']['checked_utc'])<=_utc(started['started_utc'])
            and _utc(accepted['completed_utc'])<=now(),'Official admission timestamps invalid')
        require(same(started['availability'],availability(_utc(started['availability']['checked_utc']),primary['selected'],prepared['measurements']))
            and started['availability']['status']=='available','Start did not satisfy the fixed time-only availability bound')
        controller._assert_execution_configuration(directory,prepared['execution_configuration'])
        verified=verify_execution(reg,directory/'execution');result,aggregate=endpoint(reg,verified['rows'])
        require(type(accepted.get('original_games')) is int and accepted['original_games']==GAMES
            and type(accepted.get('independently_regenerated_callbacks')) is int and accepted['independently_regenerated_callbacks']==GAMES*320
            and accepted.get('both_referees') is True
            and all(type(accepted.get(k)) is int and accepted[k]==0 for k in ('old_primary_campaign_credit','completed_per_game_bmcts_audits')),
            'Official complete admission counts/zero-credit proof changed')
        budget.conservative_rate([accepted['measurement']])
        require(accepted['measurement']['games']==GAMES and accepted['measurement']['wall_seconds']>=verified['summary']['wall_before_final_publication_s'],
            'Official admitted timing is shorter than complete pipeline or uses wrong coverage')
        require(same(aggregate,accepted['aggregate']) and same(result,final['endpoint']) and final['selected']==result['selected']
            and final['promoted'] is result['promoted'] and final['official_games']==GAMES
            and final['official_generator_confirmed'] is True,'Official endpoint/selection drift')
        require(accepted['source_sha256']==plan['source_sha256'] and accepted['primary_final_decision_sha256']==primary_sha
            and accepted['originals_sha256']==verified['summary']['originals_sha256'] and accepted['audits_sha256']==verified['summary']['audits_sha256']
            and final['acceptance_sha256']==sha((directory/'accepted.json').read_bytes()),'Official acceptance proof drift')
    elif final['status'] in ('already_e8','unavailable','unavailable_before_execution','primary_fallback_unconfirmed'):
        require(final['promoted'] is False,'Zero-game official checks cannot promote')
        require(final['selected']==primary['selected'] and final['official_games']==0 and final['official_generator_confirmed'] is False,'Unavailable check cannot alter the primary decision')
        if final['status']=='primary_fallback_unconfirmed':
            require(primary.get('final_comparison_claim') is False,'Only the validated emergency primary fallback skips this extension')
        elif final['status']=='already_e8': require(primary['selected']==E8,'Only identical E8 can skip as redundant')
        else:
            check=final['availability'];require(availability(datetime.fromisoformat(check['checked_utc']),primary['selected'],prepared['measurements'])['status']=='unavailable','Unavailable decision must use fixed time-only bound')
        require(not (directory/'execution').exists(),'Unavailable pre-execution decision has actual execution evidence')
    elif final['status']=='failed_or_incomplete':
        require(final['promoted'] is False,'Failed official check cannot promote')
        require(final['selected']==E8 and final['official_generator_confirmed'] is False and final['official_games']==0,'Failed/incomplete panel must retain E8')
        failure=authority.read('failure',directory/'failure_receipt.json')
        require(failure.get('role')==ROLE and final['failure_receipt_sha256']==sha((directory/'failure_receipt.json').read_bytes()),'Failed release receipt changed')
    else: raise ValueError('Unknown official release-check terminal status')
    require(type(final['primary_campaign_credit']) is int and final['primary_campaign_credit']==0
        and type(final['completed_per_game_bmcts_audits']) is int and final['completed_per_game_bmcts_audits']==0,'Official check grants no old primary/BMCTS credit')
    return final


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('amend','authorize-publication','prepare','execute','verify'))
    parser.add_argument('--campaign',type=Path,default=controller.CAMPAIGN)
    parser.add_argument('--published-commit');parser.add_argument('--selected-path');parser.add_argument('--selected-sha256')
    args=parser.parse_args()
    # Root-local only. This capability is never passed to any actor/audit worker.
    from deadline_campaign.authority import Authority
    authority=Authority.load(args.campaign)
    if args.action=='amend': result=amend(args.campaign,authority)
    elif args.action=='authorize-publication': result=authorize_publication(args.campaign,authority,args.published_commit)
    elif args.action=='prepare': result=prepare(args.campaign,authority,dict(path=args.selected_path,sha256=args.selected_sha256))
    elif args.action=='execute': result=execute(args.campaign,authority)
    else: result=verify_complete(args.campaign,authority)
    print(canonical(result).decode(),flush=True)


if __name__=='__main__':main()
