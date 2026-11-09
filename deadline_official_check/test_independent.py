"""Independent metadata/synthetic witnesses: no actors, CUDA or real authority."""
import copy
from collections import Counter
from datetime import timedelta
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from . import experiment as e, maps

TEMP_ROOT=e.ROOT/'deadline_official_check/.t'


def digest(body):
    return hashlib.sha256(body).hexdigest()


def orbit(base):
    # Independent coordinate rotation, rather than the imported orbit helper.
    boards=[]
    for turns in range(4):
        rotated=[]
        for row in range(8):
            for col in range(8):
                r,c=row,col
                for _ in range(turns): r,c=7-c,r
                rotated.append(base[8*r+c])
        boards.append(bytes(rotated))
    return min(boards).hex()


def metadata_bases(value):
    if type(value) is dict:
        if 'base' in value:
            base=value['base']
            if type(base) is list and len(base)==64:
                yield base
        for child in value.values(): yield from metadata_bases(child)
    elif type(value) is list:
        for child in value: yield from metadata_bases(child)


class SyntheticAuthority:
    """A deliberately non-authenticating temporary test record store."""
    def __init__(self,campaign):
        self.campaign=campaign
        self.manifest_sha256='f'*64

    def seal(self,scope,payload,path):
        Path(path).write_bytes(e.canonical(dict(scope=scope,payload=payload))+b'\n')

    def read(self,scope,path):
        value=json.loads(Path(path).read_bytes())
        if value['scope']!=scope: raise ValueError('Synthetic scope mismatch')
        return copy.deepcopy(value['payload'])


def synthetic_rows(reg):
    rows=[]
    for fixture in reg['fixtures']:
        # Vary both arms by whole map and field; no constant-contrast shortcut.
        index=fixture['map_index'];field=e.design.FIELDS.index(fixture['field'])
        pw2=(index+2*field+fixture['seat']+fixture['token']+fixture['candidate_slot']*3)%7
        rivals=[0]*(pw2//2)+([10] if pw2%2 else [])+[20]*(3-pw2//2-pw2%2)
        iterator=iter(rivals)
        scores=[10 if s==fixture['seat'] else next(iterator) for s in range(4)]
        rows.append(dict(fixture=fixture['id'],candidate=fixture['candidate'],map_id=fixture['map_id'],
            focal_seat=fixture['seat'],field=fixture['field'],opponent_ids=[r['id'] for r in fixture['opponents']],
            faults=[],scores=scores,focal_score=10,focal_pw=pw2/2))
    return rows


class IndependentOfficialTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.panel=maps.validate(e.MAPS)
        TEMP_ROOT.mkdir(exist_ok=True)
        cls.temp=tempfile.TemporaryDirectory(prefix='official-independent-',dir=TEMP_ROOT)
        cls.addClassCleanup(cls.temp.cleanup)
        cls.root=Path(cls.temp.name)
        candidate=cls.root/'synthetic.py';candidate.write_bytes(b'def act(view):\n    return "STAY"\n')
        cls.selected=dict(path=str(candidate),sha256=digest(candidate.read_bytes()))
        cls.reg=e.registration(cls.panel['maps'],[cls.selected,dict(path=str(e.ROOT/'bot.py'),sha256=e.E8)],{})

    def test_entire_exclusion_union_and_first64_acceptance_ledger(self):
        excluded=set()
        generate=maps.generator()
        for relative,expected in maps.INPUTS.items():
            body=(maps.ROOT/relative).read_bytes()
            self.assertEqual(digest(body),expected)
            if relative.endswith('reference_e8.zip'):
                # Do not read the archived smoke history/outcomes.
                excluded.add(orbit(generate(maps.SMOKE_SEED)))
            elif relative.endswith('.zip'):
                with zipfile.ZipFile(maps.ROOT/relative) as archive:
                    names=archive.namelist();self.assertEqual(len(names),11)
                    for name in names:
                        self.assertTrue(name.endswith('_spec.json'))
                        excluded.update(orbit(b) for b in metadata_bases(json.loads(archive.read(name))))
            else:
                excluded.update(orbit(b) for b in metadata_bases(json.loads(body)))
        self.assertEqual(len(excluded),10218)
        self.assertEqual(digest(e.canonical(sorted(excluded))),self.panel['exclusions']['sorted_rotation_orbits_sha256'])
        accepted=[];used=set(excluded)
        for ordinal,record in enumerate(self.panel['selection_ledger']):
            seed=int.from_bytes(hashlib.sha256(e.canonical([maps.FORMAT,'fresh-official-map',ordinal])).digest()[:8],'big')
            base=generate(seed);identity=digest(bytes(base));rotation=orbit(base)
            keep=rotation not in used
            self.assertEqual(record,dict(ordinal=ordinal,seed=seed,map_id=identity,rotation_orbit=rotation,accepted=keep))
            if keep: accepted.append(base);used.add(rotation)
        self.assertEqual(len(accepted),64)
        self.assertEqual(accepted,[b['base'] for b in self.panel['maps']])
        self.assertEqual(len(self.panel['selection_ledger']),113)
        self.assertEqual([v['accepted'] for v in self.panel['selection_ledger']].count(True),64)

    def test_exact_crossing_matched_parameters_fresh_ids_and_seed_namespace(self):
        counts=Counter((f['map_index'],f['field'],f['seat'],f['token'],f['candidate_slot']) for f in self.reg['fixtures'])
        self.assertEqual(len(counts),8192);self.assertEqual(set(counts.values()),{1})
        rivals=[r for f in self.reg['fixtures'] for r in f['opponents']]
        self.assertEqual(len({r['id'] for r in rivals}),24576)
        for left,right in zip(self.reg['fixtures'][::2],self.reg['fixtures'][1::2]):
            self.assertEqual(left['rival_map_coordinate'],12000+left['map_index'])
            self.assertEqual([{k:v for k,v in r.items() if k!='id'} for r in left['opponents']],
                             [{k:v for k,v in r.items() if k!='id'} for r in right['opponents']])
            for rival in left['opponents']:
                self.assertIs(type(rival['seed']),int)
                self.assertTrue(2**96<rival['seed']<2**128)
            self.assertNotEqual(left['focal_actor_id'],right['focal_actor_id'])
        self.assertEqual(self.reg['protocol']['primary_campaign_credit'],0)
        self.assertEqual(self.reg['protocol']['bmcts_credit'],0)
        self.assertFalse(self.reg['protocol']['promoted'])

    def test_variable64_map_endpoint_matches_independent_integer_multiplicities(self):
        import numpy as np
        result,aggregate=e.endpoint(self.reg,synthetic_rows(self.reg))
        arms={r['sha256']:r for r in aggregate['ranking']}
        delta=np.asarray(arms[self.selected['sha256']]['map_field_pw2'],dtype=np.int64)-np.asarray(arms[e.E8]['map_field_pw2'],dtype=np.int64)
        self.assertGreater(len({tuple(row) for row in delta.tolist()}),1)
        draws=np.random.default_rng(20261109114339).integers(0,64,size=(20000,64))
        multiplicities=np.zeros((20000,64),dtype=np.int64)
        np.add.at(multiplicities,(np.repeat(np.arange(20000),64),draws.ravel()),1)
        boot=multiplicities@delta/2048.0
        overall=np.sort(boot.sum(axis=1)/4)
        self.assertEqual(result['overall_two_sided_95_percentile_interval'],[float(overall[499]),float(overall[19499])])
        for index,field in enumerate(e.design.FIELDS):
            self.assertEqual(result['fields'][field]['lower_one_sided_bonferroni'],float(np.sort(boot[:,index])[249]))
        self.assertEqual(result['maps'],64);self.assertEqual(result['games'],8192)
        self.assertFalse(result['final_used_for_tuning'])
        with self.assertRaises(ValueError): e.endpoint(self.reg,synthetic_rows(self.reg)[:-1])

    def test_availability_uses_slowest_complete_phase_and_exact_fixed_volume(self):
        measurements=[dict(games=512,wall_seconds=s,full_actor_audits=512,both_referees=True) for s in (10,100,20)]
        duration=8192/(512/100*.8)+600+900
        boundary=e.CUTOFF-timedelta(seconds=duration)
        available=e.availability(boundary,self.selected['sha256'],measurements)
        self.assertEqual(available['status'],'available')
        self.assertEqual([available[k] for k in ('headroom_seconds','primary_proof_headroom_seconds','total_reserved_seconds')],[600,900,1500])
        protocol=e.protocol(e.MAPS)
        self.assertEqual([protocol[k] for k in ('headroom_seconds','primary_proof_headroom_seconds','total_reserved_seconds')],[600,900,1500])
        self.assertEqual(e.availability(boundary+timedelta(microseconds=1),self.selected['sha256'],measurements)['status'],'unavailable')
        for key,value in [('games',512.0),('full_actor_audits',True),('wall_seconds',float('nan')),('both_referees',1)]:
            bad=copy.deepcopy(measurements);bad[0][key]=value
            with self.assertRaises(ValueError): e.availability(boundary,self.selected['sha256'],bad)

    def test_rehashed_map_semantic_or_ledger_tamper_rejected(self):
        with tempfile.TemporaryDirectory(prefix='official-map-tamper-',dir=TEMP_ROOT) as temporary:
            path=Path(temporary)/'maps.json'
            for mutation in ('seed','ledger','excluded'):
                value=copy.deepcopy(self.panel)
                if mutation=='seed': value['maps'][0]['seed']+=1
                elif mutation=='ledger': value['selection_ledger'][0]['accepted']=not value['selection_ledger'][0]['accepted']
                else: value['exclusions']['unique_rotation_orbits']-=1
                body=e.canonical(value)+b'\n';path.write_bytes(body);path.with_suffix('.sha256').write_text(digest(body)+'\n')
                with self.subTest(mutation=mutation),self.assertRaises(ValueError): maps.validate(path)

    def test_publication_role_and_exact_source_map_bindings(self):
        with tempfile.TemporaryDirectory(prefix='official-publication-',dir=TEMP_ROOT) as temporary:
            campaign=Path(temporary);authority=SyntheticAuthority(campaign)
            guards={'synthetic/module.py':'a'*64}
            with patch.object(e,'_owner',return_value=campaign),patch.object(e,'source_pins',return_value=guards):
                e.amend(campaign,authority)
                e.authorize_publication(campaign,authority,'a'*40)
                directory=campaign/e.DIRECTORY
                self.assertEqual(e._context(campaign,authority)[2]['role'],e.ROLE)
                path=directory/'published_receipt.json';good=authority.read('manifest',path)
                for key,value in [('role','primary'),('approved_after_review',1),('published_commit','A'*40),('maps_sha256','0'*64),('source_sha256',{})]:
                    bad=dict(good);bad[key]=value;authority.seal('manifest',bad,path)
                    with self.subTest(key=key),self.assertRaises(ValueError): e._context(campaign,authority)
                authority.seal('manifest',good,path)
                with patch.object(e,'source_pins',return_value={'synthetic/module.py':'b'*64}):
                    with self.assertRaises(ValueError): e._context(campaign,authority)

    def test_synthetic_signed_unavailable_cannot_claim_promotion_or_foreign_role(self):
        with tempfile.TemporaryDirectory(prefix='official-zero-game-',dir=TEMP_ROOT) as temporary:
            directory=Path(temporary);authority=SyntheticAuthority(directory)
            e.frozen._seal(directory/'plan.json',{})
            prepared=dict(selected_source=self.selected,measurements=[])
            e.frozen._seal(directory/'prepared.json',prepared)
            primary=dict(selected=e.E8,completed_utc=(e.CUTOFF-timedelta(hours=2)).isoformat())
            final=dict(role=e.ROLE,status='already_e8',selected=e.E8,official_games=0,promoted=False,
                official_panel_completed=False,
                primary_decision_unchanged=True,primary_final_decision_sha256='c'*64,
                plan_sha256=digest((directory/'plan.json').read_bytes()),prepared_sha256=digest((directory/'prepared.json').read_bytes()),
                official_generator_confirmed=False,primary_campaign_credit=0,completed_per_game_bmcts_audits=0)
            with patch.object(e,'_context',return_value=(directory,directory,{})),patch.object(e,'_primary',return_value=(primary,'c'*64)):
                authority.seal('final-decision',final,directory/'release_decision.json')
                self.assertEqual(e.verify_complete(directory,authority)['selected'],e.E8)
                for key,value in [('promoted',True),('role','ordinary-primary'),('primary_campaign_credit',True)]:
                    bad=dict(final);bad[key]=value;authority.seal('final-decision',bad,directory/'release_decision.json')
                    with self.subTest(key=key),self.assertRaises(ValueError): e.verify_complete(directory,authority)

    def test_complete_start_exact_coverage_configuration_and_chronology(self):
        """Exercise receipt logic while replacing only expensive NEW aliases."""
        from types import SimpleNamespace
        with tempfile.TemporaryDirectory(prefix='official-start-',dir=TEMP_ROOT) as temporary:
            directory=Path(temporary);authority=SyntheticAuthority(directory)
            configuration=dict(batch_size=128,workers=8,audit_workers=4)
            measurements=[dict(games=512,wall_seconds=1,full_actor_audits=512,both_referees=True)]
            start_time=e.CUTOFF-timedelta(hours=1)
            primary=dict(selected=self.selected['sha256'],completed_utc=(start_time-timedelta(hours=1)).isoformat())
            authority.seal('final-decision',primary,directory/'final_decision.json')
            primary_sha=digest((directory/'final_decision.json').read_bytes())
            prepared=dict(selected_source=self.selected,measurements=measurements,execution_configuration=configuration)
            plan=dict(source_sha256={'synthetic':'a'*64})
            e.frozen._seal(directory/'plan.json',plan);e.frozen._seal(directory/'prepared.json',prepared)
            e.frozen._seal(directory/'registration.json',{})
            started=dict(role=e.ROLE,registration_sha256=digest((directory/'registration.json').read_bytes()),
                started_utc=start_time.isoformat(),planned_games=8192,execution_configuration=configuration,
                availability=e.availability(start_time,self.selected['sha256'],measurements))
            aggregate={'synthetic':'complete'}
            result=dict(selected=self.selected['sha256'],promoted=True)
            accepted=dict(role=e.ROLE,registration_sha256=started['registration_sha256'],
                completed_utc=(start_time+timedelta(minutes=30)).isoformat(),original_games=8192,
                independently_regenerated_callbacks=8192*320,both_referees=True,
                old_primary_campaign_credit=0,completed_per_game_bmcts_audits=0,
                measurement=dict(games=8192,wall_seconds=10,full_actor_audits=8192,both_referees=True),
                aggregate=aggregate,source_sha256=plan['source_sha256'],primary_final_decision_sha256=primary_sha,
                originals_sha256='d'*64,audits_sha256='e'*64)
            authority.seal('acceptance',accepted,directory/'accepted.json')
            final=dict(role=e.ROLE,status='complete',selected=self.selected['sha256'],official_games=8192,promoted=True,
                official_panel_completed=True,
                primary_decision_unchanged=True,primary_final_decision_sha256=primary_sha,
                plan_sha256=digest((directory/'plan.json').read_bytes()),prepared_sha256=digest((directory/'prepared.json').read_bytes()),
                official_generator_confirmed=True,primary_campaign_credit=0,completed_per_game_bmcts_audits=0,
                endpoint=result,acceptance_sha256=digest((directory/'accepted.json').read_bytes()),
                completed_utc=(start_time+timedelta(minutes=31)).isoformat())
            verified=dict(rows=[],summary=dict(wall_before_final_publication_s=1,originals_sha256='d'*64,audits_sha256='e'*64))
            context=(directory,directory,plan,prepared,self.reg,primary_sha)
            with patch.object(e,'_context',return_value=context[:3]),patch.object(e,'_primary',return_value=(primary,primary_sha)),\
                 patch.object(e,'_registered',return_value=context),patch.object(e,'verify_execution',return_value=verified),\
                 patch.object(e,'endpoint',return_value=(result,aggregate)),\
                 patch.object(e,'controller',SimpleNamespace(_sealed=e.controller._sealed,_assert_execution_configuration=lambda *args:None)),\
                 patch.object(e,'now',return_value=e.CUTOFF-timedelta(minutes=1)):
                authority.seal('start',started,directory/'started.json');authority.seal('final-decision',final,directory/'release_decision.json')
                self.assertEqual(e.verify_complete(directory,authority)['official_games'],8192)
                mutations=[dict(started,planned_games=8191),dict(started,execution_configuration=dict(configuration,workers=4)),
                    dict(started,started_utc=(start_time-timedelta(hours=2)).isoformat()),
                    dict(started,availability=e.availability(start_time+timedelta(seconds=1),self.selected['sha256'],measurements))]
                for index,bad in enumerate(mutations):
                    authority.seal('start',bad,directory/'started.json')
                    with self.subTest(mutation=index),self.assertRaises(ValueError): e.verify_complete(directory,authority)

    def test_primary_requires_exact_complete_normal_payload_and_tested_source(self):
        with tempfile.TemporaryDirectory(prefix='official-primary-',dir=TEMP_ROOT) as temporary:
            campaign=Path(temporary);authority=SyntheticAuthority(campaign)
            anchor=dict(path=str(e.ROOT/'bot.py'),sha256=e.E8)
            completed=(e.budget.FINAL_CUTOFF-timedelta(minutes=30)).isoformat()
            aggregate=dict(maps=['map-%02d'%i for i in range(64)],games=8192,ranking=[
                dict(sha256=self.selected['sha256'],map_field_pw2=[[64]*4 for _ in range(64)]),
                dict(sha256=e.E8,map_field_pw2=[[32]*4 for _ in range(64)])])
            context=dict(kind='comparison',anchor=anchor,selection=dict(challenger=self.selected['sha256']),
                accepted=dict(aggregate=aggregate),acceptance_sha256='a'*64,source_entries=[self.selected,anchor],
                earliest=(e.budget.FINAL_CUTOFF-timedelta(hours=1)).isoformat(),latest=e.budget.FINAL_CUTOFF.isoformat())
            # Independently use the unchanged primary recipe itself, not the new
            # primary_expected helper being checked.
            expected=e.evaluation.final_decision(aggregate,self.selected['sha256'],e.E8)
            expected.update(completed_utc=completed,final_acceptance_sha256='a'*64)
            self.assertEqual(e.primary_expected(context,completed),expected)
            path=campaign/'final_decision.json'
            with patch.object(e,'primary_context',return_value=context),patch.object(e,'now',return_value=e.CUTOFF):
                authority.seal('final-decision',expected,path)
                self.assertEqual(e._primary(campaign,authority,self.selected)[0],expected)
                invalid=[dict(selected=self.selected['sha256'],completed_utc=completed),
                    dict(expected,final_acceptance_sha256='b'*64),dict(expected,maps=63),
                    dict(expected,promoted=False),dict(expected,primary_campaign_credit=1),
                    dict(expected,completed_utc=(e.budget.FINAL_CUTOFF+timedelta(seconds=1)).isoformat())]
                for index,bad in enumerate(invalid):
                    authority.seal('final-decision',bad,path)
                    with self.subTest(mutation=index),self.assertRaises(ValueError): e._primary(campaign,authority,self.selected)
                authority.seal('final-decision',expected,path)
                foreign=dict(context,source_entries=[anchor])
                with patch.object(e,'primary_context',return_value=foreign),self.assertRaises(ValueError):
                    e._primary(campaign,authority,self.selected)

    def test_no_final_needed_and_emergency_fallback_exact_semantics(self):
        anchor=dict(path=str(e.ROOT/'bot.py'),sha256=e.E8)
        completed=(e.budget.FINAL_CUTOFF-timedelta(minutes=30)).isoformat()
        context=dict(kind='no_final_needed',anchor=anchor)
        self.assertEqual(e.primary_expected(context,completed),dict(selected=e.E8,promoted=False,
            reason='DEV selected the validated anchor itself; no redundant FINAL.',final_games=0,
            completed_utc=completed,primary_campaign_credit=0,bmcts_credit=0))
        context['kind']='fallback'
        fallback=e.primary_expected(context,completed)
        self.assertFalse(fallback['final_comparison_claim']);self.assertFalse(fallback['promoted'])
        with tempfile.TemporaryDirectory(prefix='official-fallback-',dir=TEMP_ROOT) as temporary:
            campaign=Path(temporary);directory=campaign/e.DIRECTORY;directory.mkdir();authority=SyntheticAuthority(campaign)
            e.frozen._seal(campaign/'manifest.json',dict(execution_configuration={}))
            e.frozen._seal(directory/'plan.json',{})
            with patch.object(e,'_context',return_value=(campaign,directory,{})),\
                 patch.object(e,'_primary',return_value=(fallback,'f'*64)),\
                 patch.object(e,'_timings',side_effect=AssertionError('Emergency fallback must not budget new games')):
                result=e.prepare(campaign,authority,anchor)
            self.assertEqual(result['status'],'primary_fallback_unconfirmed');self.assertEqual(result['official_games'],0)
            self.assertFalse(result['promoted']);self.assertFalse(result['official_panel_completed'])
            self.assertFalse((directory/'registration.json').exists());self.assertFalse((directory/'execution').exists())

    def test_postclaim_metadata_fault_records_e8_failure_and_never_calls_runner(self):
        from types import SimpleNamespace
        with tempfile.TemporaryDirectory(prefix='official-claim-fault-',dir=TEMP_ROOT) as temporary:
            directory=Path(temporary);authority=SyntheticAuthority(directory)
            e.frozen._seal(directory/'plan.json',{});e.frozen._seal(directory/'prepared.json',{})
            fault=ValueError('Synthetic authenticated timing record changed')
            context=(directory,directory,{}, {},self.reg,'f'*64)
            with patch.object(e,'_registered',return_value=context),patch.object(e,'_timings',side_effect=fault),\
                 patch.object(e,'runner',SimpleNamespace(run_fixtures=lambda *a,**k:self.fail('No callback execution allowed'))):
                with self.assertRaises(ValueError) as caught: e.execute(directory,authority)
                self.assertIs(caught.exception,fault)
                with self.assertRaises((ValueError,FileExistsError)): e.execute(directory,authority)
            self.assertTrue((directory/'.execution_claim').is_dir())
            failure=authority.read('failure',directory/'failure_receipt.json')
            decision=authority.read('final-decision',directory/'release_decision.json')
            self.assertEqual(failure['error_type'],'ValueError');self.assertEqual(failure['official_admitted_games'],0)
            self.assertEqual(decision['selected'],e.E8);self.assertEqual(decision['status'],'failed_or_incomplete')
            self.assertFalse(decision['promoted']);self.assertEqual(decision['official_games'],0)


if __name__=='__main__': unittest.main()
