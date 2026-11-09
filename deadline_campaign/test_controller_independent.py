"""Independent synthetic admission/phase tests: no live key, actor or CUDA call.

FakeAuthority models an authenticated owner receipt. A correct coordinator
still has to prove that its payload matches the canonical complete evidence.
"""
import copy
from datetime import timedelta
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from deadline_campaign import controller as c


class FakeAuthority:
    def __init__(self,payloads): self.payloads=payloads;self.writes=[]
    def read(self,scope,path): return copy.deepcopy(self.payloads[scope])
    def seal(self,scope,payload,path):
        self.writes.append((scope,copy.deepcopy(payload),str(path)))
        return copy.deepcopy(payload)


class NoLease:
    def __init__(self,*_): pass
    def __enter__(self): return self
    def __exit__(self,*_): pass


class CoordinatorBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='SYNTHETIC-CONTROLLER-',dir=c.ROOT/'deadline_campaign')
        self.addCleanup(self.temp.cleanup)
        self.campaign=Path(self.temp.name)
        synthetic_clock=patch.object(c,'now',return_value=c.budget.START+timedelta(hours=2))
        synthetic_clock.start();self.addCleanup(synthetic_clock.stop)
        awake_context=patch.object(c,'KeepAwake',NoLease)
        awake_context.start();self.addCleanup(awake_context.stop)

    def context(self,authority):
        return patch.object(c,'_context',return_value=(self.campaign,authority,
            {'source_sha256':{},'execution_configuration':dict(c.DEFAULT_EXECUTION),
             'timing_measurements':[dict(games=256,wall_seconds=20.,full_actor_audits=256,both_referees=True)]}))

    def test_rehashed_registration_and_signed_receipt_still_match_canonical_recipe(self):
        directory=self.campaign/'train_000';directory.mkdir()
        body=b'SYNTHETIC-NO-ACTOR-EXECUTION';source=directory/'source.py';source.write_bytes(body)
        entries=[dict(path=str(source),sha256=c.design.sha(body))]
        expected=dict(phase='train',generation=0,candidates=entries,
            fixtures=[{'id':'SYNTHETIC','map_index':500}],protocol={'complete_games':1})
        boards=[{'map_index':500}]
        def write(registration):
            # Deliberately rehash a tampered SYNTHETIC artifact; a self-reported
            # fingerprint must not replace independent recipe reconstruction.
            body=c.design.canonical(registration)+b'\n'
            (directory/'registration.json').write_bytes(body)
            (directory/'registration.sha256').write_text(c.design.sha(body)+'\n')
            return dict(phase='train',generation=0,path=str(directory/'registration.json'),
                registration_sha256=c.design.sha((directory/'registration.json').read_bytes()),planned_games=1,
                map_indices=[500],candidate_sha256=[entries[0]['sha256']])
        receipt=write(expected);authority=FakeAuthority({'registration':receipt})
        with patch.object(c.design,'cohort',return_value=copy.deepcopy(expected)) as rebuild:
            actual=c._validate_registration(self.campaign,authority,{'source_sha256':{}},directory,'train',0,[body],boards)
            self.assertEqual(actual,expected)
            self.assertEqual(rebuild.call_args.args[0:3],('train',0,boards))
            wrong=copy.deepcopy(expected);wrong['fixtures'][0]['map_index']=0
            authority.payloads['registration']=write(wrong)
            with self.assertRaises(ValueError):
                c._validate_registration(self.campaign,authority,{'source_sha256':{}},directory,'train',0,[body],boards)
            authority.payloads['registration']=write(expected)
            authority.payloads['registration']['planned_games']=2
            with self.assertRaises(ValueError):
                c._validate_registration(self.campaign,authority,{'source_sha256':{}},directory,'train',0,[body],boards)
            for key,value in (('planned_games',1.0),('planned_games',True),('generation',False)):
                with self.subTest(typed_receipt=(key,value)):
                    authority.payloads['registration']=write(expected)
                    authority.payloads['registration'][key]=value
                    with self.assertRaises(ValueError):
                        c._validate_registration(self.campaign,authority,{'source_sha256':{}},directory,'train',0,[body],boards)

    def test_train_chain_rejects_missing_predecessors_and_reversed_chronology(self):
        later=self.campaign/'train_001';later.mkdir();(later/'accepted.json').write_bytes(b'SYNTHETIC')
        with patch.object(c.design,'catalog',return_value=[]):
            with self.assertRaises(ValueError): c._train_chain(self.campaign,FakeAuthority({}),
                {'source_sha256':{},'execution_configuration':dict(c.DEFAULT_EXECUTION)})
        first=self.campaign/'train_000';first.mkdir();(first/'accepted.json').write_bytes(b'SYNTHETIC')
        source=self.campaign/'source.py';source.write_bytes(b'SYNTHETIC')
        registration={'candidates':[{'path':str(source),'sha256':c.design.sha(source.read_bytes())}]}
        previous={'completed_utc':(c.budget.START+timedelta(seconds=20)).isoformat(),'aggregate':{'ranking':['FIRST-GENERATION-ONLY']}}
        following={'completed_utc':(c.budget.START+timedelta(seconds=30)).isoformat(),'aggregate':{'ranking':[]}}
        authority=FakeAuthority({'start':{'started_utc':(c.budget.START+timedelta(seconds=10)).isoformat()}})
        with patch.object(c.design,'catalog',return_value=[None]*532),\
                patch.object(c.design,'initial_population',return_value=[b'SYNTHETIC']),\
                patch.object(c.design,'next_population',return_value=[b'SYNTHETIC']) as next_population,\
                patch.object(c,'_validate_registration',return_value=registration),\
                patch.object(c,'_validate_acceptance',side_effect=[previous,following]):
            with self.assertRaises(ValueError): c._train_chain(self.campaign,authority,
                {'source_sha256':{},'execution_configuration':dict(c.DEFAULT_EXECUTION)})
        self.assertEqual(next_population.call_args.args,([b'SYNTHETIC'],previous['aggregate']['ranking'],1))

    def test_signed_shortlist_recomputes_budget_reference_maps_and_last_population(self):
        directory=self.campaign/'train_000';directory.mkdir();(directory/'accepted.json').write_bytes(b'SYNTHETIC-ACCEPTANCE')
        bodies=[b'FIRST',b'SECOND']
        measurement=dict(games=256,wall_seconds=20.,full_actor_audits=256,both_referees=True)
        previous={'completed_utc':(c.budget.START+timedelta(seconds=1)).isoformat(),'measurement':measurement}
        manifest={'timing_measurements':[measurement]};chosen=c.budget.heldout_budget([measurement,measurement])
        anchor={'path':'SYNTHETIC-REFERENCE','sha256':'a'*64};report={'arms':['SYNTHETIC-COMPLETE-ONLY'],'timings':{'wall':1.}}
        c.frozen._seal(self.campaign/'architecture_report.json',report)
        short=dict(frozen_utc=(c.budget.START+timedelta(seconds=2)).isoformat(),last_train_generation=0,
            previous_acceptance_sha256=c.design.sha((directory/'accepted.json').read_bytes()),
            candidate_sha256=[c.design.sha(body) for body in bodies],anchor=anchor,
            architecture_report_sha256=c.design.sha((self.campaign/'architecture_report.json').read_bytes()),
            heldout_budget=chosen,development_map_indices=list(range(8000,8000+chosen['development_maps'])),
            final_map_indices=list(range(9000,9000+chosen['final_maps'])),training_closed=True,heldout_outcomes_consumed=False)
        authority=FakeAuthority({'shortlist':short})
        mutations={
            'last_stage':lambda s:s.__setitem__('last_train_generation',1),
            'population':lambda s:s['candidate_sha256'].__setitem__(0,'0'*64),
            'acceptance':lambda s:s.__setitem__('previous_acceptance_sha256','0'*64),
            'dev_map':lambda s:s['development_map_indices'].__setitem__(0,7999),
            'final_map':lambda s:s['final_map_indices'].__setitem__(0,8999),
            'rate':lambda s:s['heldout_budget'].__setitem__('conservative_games_per_second',1e12),
            'reference':lambda s:s['anchor'].__setitem__('sha256','0'*64),
            'report':lambda s:s.__setitem__('architecture_report_sha256','0'*64),
            'open_train':lambda s:s.__setitem__('training_closed',False),
            'heldout_used':lambda s:s.__setitem__('heldout_outcomes_consumed',True),
            'late_freeze':lambda s:s.__setitem__('frozen_utc',(c.budget.TRAIN_CUTOFF+timedelta(seconds=1)).isoformat()),
        }
        with patch.object(c,'_train_chain',return_value=[(previous,bodies)]),\
                patch.object(c,'_architecture',return_value=(copy.deepcopy(report),copy.deepcopy(anchor))):
            self.assertEqual(c._shortlist_context(self.campaign,authority,manifest),(short,bodies))
            for name,mutate in mutations.items():
                with self.subTest(name=name):
                    changed=copy.deepcopy(short);mutate(changed);authority.payloads['shortlist']=changed
                    with self.assertRaises(ValueError): c._shortlist_context(self.campaign,authority,manifest)

    def test_signed_dev_selection_is_derived_from_complete_dev_ranking(self):
        directory=self.campaign/'development';directory.mkdir();(directory/'accepted.json').write_bytes(b'SYNTHETIC-DEV')
        winner='b'*64;anchor={'path':'SYNTHETIC-ANCHOR','sha256':'a'*64}
        short={'anchor':anchor,'heldout_budget':{'development_maps':24},'final_map_indices':list(range(9000,9064)),
            'frozen_utc':(c.budget.START+timedelta(seconds=1)).isoformat()}
        registration={'candidates':[{'path':'SYNTHETIC-WINNER','sha256':winner}]}
        accepted={'completed_utc':(c.budget.START+timedelta(seconds=4)).isoformat(),
            'aggregate':{'ranking':[{'sha256':winner}]}}
        selection=dict(selected_utc=(c.budget.START+timedelta(seconds=5)).isoformat(),challenger=winner,anchor=anchor,
            development_acceptance_sha256=c.design.sha((directory/'accepted.json').read_bytes()),challenger_path='SYNTHETIC-WINNER',
            final_maps=short['final_map_indices'],final_frozen=True,final_outcomes_consumed=False,final_not_needed=False)
        authority=FakeAuthority({'dev-selection':selection,
            'start':{'started_utc':(c.budget.START+timedelta(seconds=2)).isoformat()}})
        mutations={
            'winner':lambda s:s.__setitem__('challenger','c'*64),
            'anchor':lambda s:s['anchor'].__setitem__('sha256','c'*64),
            'source':lambda s:s.__setitem__('challenger_path','FOREIGN-SOURCE'),
            'acceptance':lambda s:s.__setitem__('development_acceptance_sha256','0'*64),
            'maps':lambda s:s['final_maps'].__setitem__(0,8999),
            'skip_final':lambda s:s.__setitem__('final_not_needed',True),
            'not_frozen':lambda s:s.__setitem__('final_frozen',False),
            'outcomes_used':lambda s:s.__setitem__('final_outcomes_consumed',True),
            'reverse_time':lambda s:s.__setitem__('selected_utc',c.budget.START.isoformat()),
            'late':lambda s:s.__setitem__('selected_utc',(c.budget.DEV_CUTOFF+timedelta(seconds=1)).isoformat()),
        }
        with patch.object(c.design,'catalog',return_value=[None]*8024),\
                patch.object(c,'_validate_registration',return_value=registration),\
                patch.object(c,'_validate_acceptance',return_value=accepted):
            manifest={'execution_configuration':dict(c.DEFAULT_EXECUTION)}
            self.assertEqual(c._development_context(self.campaign,authority,manifest,short,[]),selection)
            for name,mutate in mutations.items():
                with self.subTest(name=name):
                    changed=copy.deepcopy(selection);mutate(changed);authority.payloads['dev-selection']=changed
                    with self.assertRaises(ValueError): c._development_context(self.campaign,authority,manifest,short,[])
            authority.payloads['dev-selection']=copy.deepcopy(selection)
            authority.payloads['start']['started_utc']=c.budget.START.isoformat()
            with self.assertRaises(ValueError): c._development_context(self.campaign,authority,manifest,short,[])

    def test_final_cannot_start_before_its_selection_timestamp(self):
        authority=FakeAuthority({})
        selection=dict(anchor={'sha256':'a'*64},final_not_needed=True,
            selected_utc=(c.budget.START+timedelta(seconds=10)).isoformat())
        with patch.object(c,'CoordinatorLease',NoLease),self.context(authority),\
                patch.object(c,'_shortlist_context',return_value=({},[])),\
                patch.object(c,'_development_context',return_value=selection),\
                patch.object(c,'now',return_value=c.budget.START+timedelta(seconds=5)):
            with self.assertRaises(ValueError): c.final(self.campaign)
        self.assertFalse(any(scope=='final-decision' for scope,_,_ in authority.writes))

    def test_fallback_can_select_only_the_validated_anchor_without_superiority(self):
        authority=FakeAuthority({});anchor={'path':'SYNTHETIC-ARCHITECTURE-SOURCE','sha256':'a'*64}
        with patch.object(c,'CoordinatorLease',NoLease),patch.object(c,'CAMPAIGN',self.campaign),self.context(authority),\
                patch.object(c,'_architecture',return_value=({'complete':True},anchor)):
            selected=c.fallback(self.campaign)
        self.assertEqual(selected['selected'],anchor['sha256'])
        self.assertIs(selected['promoted'],False)
        self.assertIs(selected['final_comparison_claim'],False)
        self.assertEqual(selected['primary_campaign_credit'],0)
        self.assertEqual(selected['bmcts_credit'],0)
        self.assertEqual([scope for scope,_,_ in authority.writes],['final-decision'])
        authority.writes=[]
        with patch.object(c,'CoordinatorLease',NoLease),patch.object(c,'CAMPAIGN',self.campaign),self.context(authority),\
                patch.object(c,'_architecture',side_effect=ValueError('SYNTHETIC incomplete architecture')):
            with self.assertRaises(ValueError): c.fallback(self.campaign)
        self.assertEqual(authority.writes,[])
        with patch.object(c,'CoordinatorLease',NoLease),patch.object(c,'CAMPAIGN',self.campaign),self.context(authority),\
                patch.object(c,'now',return_value=c.budget.DEADLINE+timedelta(seconds=1)),\
                patch.object(c,'_architecture') as architecture:
            with self.assertRaises(ValueError): c.fallback(self.campaign)
        architecture.assert_not_called()

    def test_fallback_without_prepared_campaign_creates_only_zero_game_reference_release(self):
        target=self.campaign/'fallback-only';anchor={'path':'SYNTHETIC-VALIDATED-SOURCE','sha256':'a'*64}
        authority=FakeAuthority({});authority.manifest_sha256='b'*64
        with patch.object(c,'CoordinatorLease',NoLease),patch.object(c,'CAMPAIGN',target),\
                patch.object(c.Authority,'create',return_value=authority) as create,\
                patch.object(c,'_context',return_value=(target,authority,{'fallback_only':True,'timing_measurements':[]})),\
                patch.object(c,'_architecture',return_value=({'complete':True},anchor)),\
                patch.object(c.runner,'run_fixtures') as run:
            selected=c.fallback(target)
            self.assertEqual(selected['selected'],anchor['sha256'])
            self.assertIs(selected['promoted'],False)
            self.assertIs(selected['final_comparison_claim'],False)
            with self.assertRaises(ValueError): c.train_loop(target)
        create.assert_called_once_with(target);run.assert_not_called()
        manifest=c._read(target/'manifest.json')
        self.assertIs(manifest['fallback_only'],True)
        self.assertEqual(manifest['new_games_executed'],0)
        self.assertEqual(manifest['original_primary_campaign_credit'],0)
        self.assertEqual([scope for scope,_,_ in authority.writes],['manifest','final-decision'])

    def test_signed_no_final_claim_cannot_replace_missing_development_evidence(self):
        anchor={'path':str(self.campaign/'unqualified.py'),'sha256':'a'*64}
        authority=FakeAuthority({'shortlist':{'heldout_budget':{}},'dev-selection':dict(
            anchor=anchor,challenger=anchor['sha256'],final_not_needed=True,
            development_acceptance_sha256='0'*64,final_frozen=True,final_outcomes_consumed=False)})
        with patch.object(c,'CoordinatorLease',NoLease),self.context(authority),\
                patch.object(c,'now',return_value=c.budget.START):
            with self.assertRaises((ValueError,OSError,KeyError)):
                c.final(self.campaign)
        self.assertFalse(any(scope=='final-decision' for scope,_,_ in authority.writes))

    def test_signed_challenger_selection_cannot_promote_without_development_chain(self):
        challenger=self.campaign/'challenger.py';challenger.write_bytes(b'SYNTHETIC-UNQUALIFIED-CHALLENGER')
        reference=self.campaign/'reference.py';reference.write_bytes(b'SYNTHETIC-UNQUALIFIED-REFERENCE')
        anchor={'path':str(reference),'sha256':c.design.sha(reference.read_bytes())}
        selection=dict(anchor=anchor,challenger=c.design.sha(challenger.read_bytes()),
            challenger_path=str(challenger),final_not_needed=False,development_acceptance_sha256='0'*64,
            final_maps=list(range(9000,9064)),final_frozen=True,final_outcomes_consumed=False)
        short={'heldout_budget':dict(final_games=8192,conservative_games_per_second=1000.,final_maps=64)}
        authority=FakeAuthority({'shortlist':short,'dev-selection':selection})
        directory=self.campaign/'fake-final';directory.mkdir();(directory/'accepted.json').write_bytes(b'SYNTHETIC')
        with patch.object(c,'CoordinatorLease',NoLease),self.context(authority),\
                patch.object(c,'now',return_value=c.budget.START),\
                patch.object(c.design,'catalog',return_value=[None]*9064),\
                patch.object(c,'_registration',return_value=(directory,{})),\
                patch.object(c,'_execute',return_value={'aggregate':{}}) as execute,\
                patch.object(c.evaluation,'final_decision',return_value={'selected':selection['challenger'],'promoted':True}):
            with self.assertRaises((ValueError,OSError,KeyError)):
                c.final(self.campaign)
        execute.assert_not_called()
        self.assertFalse(any(scope=='final-decision' for scope,_,_ in authority.writes))

    def test_any_heldout_artifact_closes_training_even_if_shortlist_is_missing(self):
        (self.campaign/'development').mkdir()
        authority=FakeAuthority({})
        with patch.object(c,'CoordinatorLease',NoLease),self.context(authority),\
                patch.object(c,'now',return_value=c.budget.START),\
                patch.object(c.budget,'may_start_generation',return_value=False):
            with self.assertRaises((ValueError,OSError,KeyError)):
                c.train_loop(self.campaign)

    def test_completed_after_phase_cutoff_has_failure_and_no_acceptance(self):
        for phase,cutoff in (('train',c.budget.TRAIN_CUTOFF),
                ('development',c.budget.DEV_CUTOFF),('final',c.budget.FINAL_CUTOFF)):
            with self.subTest(phase=phase):
                directory=self.campaign/phase;directory.mkdir()
                registration=dict(phase=phase,generation=0,fixtures=[{'id':'SYNTHETIC'}])
                c.frozen._seal(directory/'registration.json',registration)
                authority=FakeAuthority({});clock=[cutoff-timedelta(seconds=10)]
                def completed(*args,**kwargs):
                    output=Path(args[2]);output.mkdir()
                    c.frozen._seal(output/'execution_started.json',dict(c.DEFAULT_EXECUTION))
                    clock[0]=cutoff+timedelta(seconds=1)
                summary={'originals_sha256':'a'*64,'audits_sha256':'b'*64}
                with patch.object(c,'source_pins',return_value={}),\
                        patch.object(c,'now',side_effect=lambda:clock[0]),\
                        patch.object(c.runner,'run_fixtures',side_effect=completed),\
                        patch.object(c,'_verify_output',return_value=(summary,{'games':8192,'ranking':[]})):
                    with self.assertRaises((ValueError,OSError,KeyError)):
                        c._execute(self.campaign,authority,{'source_sha256':{}},directory,registration)
                self.assertFalse(any(scope=='acceptance' for scope,_,_ in authority.writes))
                self.assertTrue(any(scope=='failure' for scope,_,_ in authority.writes))

    def test_optimized_schedule_is_used_and_exact_header_binding_is_required(self):
        configuration=dict(batch_size=128,workers=8,audit_workers=4)
        manifest={'source_sha256':{},'execution_configuration':configuration}
        for correct_header in (True,False):
            with self.subTest(correct_header=correct_header):
                directory=self.campaign/('schedule-'+str(correct_header));directory.mkdir()
                registration={'phase':'train','generation':0,'fixtures':[{'id':'SYNTHETIC'}]}
                c.frozen._seal(directory/'registration.json',registration)
                authority=FakeAuthority({});calls=[]
                def executed(*args,**kwargs):
                    calls.append(kwargs)
                    output=Path(args[2]);output.mkdir()
                    c.frozen._seal(output/'execution_started.json',configuration if correct_header else dict(c.DEFAULT_EXECUTION))
                summary={'originals_sha256':'a'*64,'audits_sha256':'b'*64}
                with patch.object(c,'source_pins',return_value={}),\
                        patch.object(c.runner,'run_fixtures',side_effect=executed),\
                        patch.object(c,'_verify_output',return_value=(summary,{'games':1,'ranking':[]})):
                    if correct_header:
                        accepted=c._execute(self.campaign,authority,manifest,directory,registration)
                        self.assertEqual(accepted['execution_configuration'],configuration)
                        self.assertEqual(accepted['execution_header_sha256'],
                            c.design.sha((directory/'execution'/'execution_started.json').read_bytes()))
                    else:
                        with self.assertRaises(ValueError): c._execute(self.campaign,authority,manifest,directory,registration)
                        self.assertFalse(any(scope=='acceptance' for scope,_,_ in authority.writes))
                self.assertEqual(calls,[dict(device='cuda',**configuration)])

    def test_prepare_binds_verified_schedule_its_timing_and_exact_baseline(self):
        from deadline_runner import benchmark,optimize
        baseline=self.campaign/'known';baseline.mkdir();(baseline/'benchmark_result.json').write_bytes(b'SYNTHETIC-BASELINE')
        grid=self.campaign/'grid';grid.mkdir();(grid/'optimization_result.json').write_bytes(b'SYNTHETIC-OPTIMIZATION')
        target=self.campaign/'prepared';authority=FakeAuthority({})
        configuration=dict(batch_size=128,workers=8,audit_workers=4)
        old=dict(games=512,wall_seconds=60.,full_actor_audits=512,both_referees=True)
        selected=dict(old,wall_seconds=40.)
        proof=dict(baseline={'benchmark_result_sha256':c.design.sha((baseline/'benchmark_result.json').read_bytes())},
            selected_configuration=configuration,selected_measurement=selected)
        def create(path):
            authority.manifest_sha256=c.design.sha((Path(path)/'manifest.json').read_bytes())
            return authority
        with patch.object(c,'CoordinatorLease',NoLease),patch.object(c,'CAMPAIGN',target),\
                patch.object(benchmark,'verify_complete',return_value={'measurements':[old]}),\
                patch.object(optimize,'verify_complete',return_value=proof),\
                patch.object(c,'source_pins',return_value={}),\
                patch.object(c.design,'initial_population',return_value=[b'SYNTHETIC-%d'%i for i in range(8)]),\
                patch.object(c.design,'classify',side_effect=lambda body:{'source_sha256':c.design.sha(body)}),\
                patch.object(c.Authority,'create',side_effect=create) as authority_create:
            c.prepare(baseline,grid)
        authority_create.assert_called_once_with(target)
        manifest=c._read(target/'manifest.json')
        self.assertEqual(manifest['execution_configuration'],configuration)
        self.assertEqual(manifest['timing_measurements'],[selected])
        self.assertEqual(manifest['scheduling_qualification'],dict(path=str(grid),
            result_sha256=c.design.sha((grid/'optimization_result.json').read_bytes())))
        self.assertEqual(manifest['qualification_result_sha256'],proof['baseline']['benchmark_result_sha256'])
        self.assertEqual(manifest['prospective_heldout_budget'],c.budget.heldout_budget([selected]))
        bad=copy.deepcopy(proof);bad['baseline']['benchmark_result_sha256']='0'*64
        with patch.object(c,'CoordinatorLease',NoLease),patch.object(c,'CAMPAIGN',self.campaign/'wrong-baseline'),\
                patch.object(benchmark,'verify_complete',return_value={'measurements':[old]}),\
                patch.object(optimize,'verify_complete',return_value=bad),patch.object(c.Authority,'create') as create:
            with self.assertRaises(ValueError): c.prepare(baseline,grid)
        create.assert_not_called()

    def test_signed_fast_measurement_cannot_outrun_verified_wall_time(self):
        directory=self.campaign/'train_000';directory.mkdir()
        source=directory/'synthetic.py';source.write_bytes(b'SYNTHETIC-NOT-AN-ELIGIBLE-SOURCE')
        registration={'phase':'train','generation':0,'fixtures':[{'id':'SYNTHETIC'}],
            'candidates':[dict(path=str(source),sha256=c.design.sha(source.read_bytes()))]}
        c.frozen._seal(directory/'registration.json',registration)
        aggregate={'games':1,'ranking':[]}
        accepted=dict(phase='train',generation=0,registration_sha256=c.design.sha((directory/'registration.json').read_bytes()),
            aggregate=aggregate,originals_sha256='a'*64,audits_sha256='b'*64,
            original_games=1,independently_regenerated_callbacks=320,both_referees=True,promoted=False,
            original_primary_campaign_credit=0,completed_per_game_bmcts_audits=0,
            completed_utc=(c.budget.START+timedelta(seconds=1)).isoformat(),
            measurement=dict(games=1,wall_seconds=1e-20,full_actor_audits=1,both_referees=True))
        start=dict(phase='train',generation=0,registration_sha256=accepted['registration_sha256'],
            planned_games=1,started_utc=c.budget.START.isoformat())
        authority=FakeAuthority({'acceptance':accepted,'start':start})
        summary=dict(originals_sha256='a'*64,audits_sha256='b'*64,wall_before_final_publication_s=1200.)
        with patch.object(c,'_verify_output',return_value=(summary,aggregate)):
            with self.assertRaises((ValueError,OSError,KeyError)):
                c._validate_acceptance(self.campaign,authority,directory,registration)

    def test_acceptance_cannot_claim_a_future_completion(self):
        directory=self.campaign/'future';directory.mkdir()
        registration={'phase':'train','generation':0,'fixtures':[{'id':'SYNTHETIC'}]}
        c.frozen._seal(directory/'registration.json',registration)
        digest=c.design.sha((directory/'registration.json').read_bytes())
        aggregate={'games':1,'ranking':[]}
        accepted=dict(phase='train',generation=0,registration_sha256=digest,aggregate=aggregate,
            originals_sha256='a'*64,audits_sha256='b'*64,original_games=1,
            independently_regenerated_callbacks=320,both_referees=True,promoted=False,
            original_primary_campaign_credit=0,completed_per_game_bmcts_audits=0,
            completed_utc=(c.budget.START+timedelta(seconds=11)).isoformat(),
            measurement=dict(games=1,wall_seconds=10.,full_actor_audits=1,both_referees=True))
        started=dict(phase='train',generation=0,registration_sha256=digest,planned_games=1,
            started_utc=(c.budget.START+timedelta(seconds=1)).isoformat())
        authority=FakeAuthority({'acceptance':accepted,'start':started})
        summary=dict(originals_sha256='a'*64,audits_sha256='b'*64,wall_before_final_publication_s=9.)
        with patch.object(c,'_verify_output',return_value=(summary,aggregate)),\
                patch.object(c,'now',return_value=c.budget.START+timedelta(seconds=5)):
            with self.assertRaises(ValueError): c._validate_acceptance(self.campaign,authority,directory,registration)


class OutputBoundaryTests(unittest.TestCase):
    def test_highlevel_counts_and_rehashed_streams_do_not_replace_full_transcript(self):
        # Pure fabricated metadata deliberately contains no source archive,
        # execution header, batch directory, valid action tape or timing audit.
        with tempfile.TemporaryDirectory(prefix='SYNTHETIC-OUTPUT-',dir=c.ROOT/'deadline_campaign') as name:
            directory=Path(name);output=directory/'execution';output.mkdir()
            pins=c.runner.source_pins();closure=c.design.sha(c.design.canonical(pins))
            candidates=['a'*64,'b'*64];fixtures=[];rows=[];audits=[]
            for candidate in candidates:
                for field in c.design.FIELDS:
                    for seat in range(4):
                        for token in range(1,5):
                            identity='SYNTHETIC-%d'%len(fixtures)
                            fixture=dict(id=identity,candidate=candidate,map_id='SYNTHETIC-MAP',seat=seat,
                                token=token,field=field,opponents=[{'id':'RIVAL-%d'%s} for s in range(3)])
                            fixtures.append(fixture)
                            row=dict(fixture=identity,candidate=candidate,map_id=fixture['map_id'],focal_seat=seat,
                                field=field,opponent_ids=[s['id'] for s in fixture['opponents']],faults=[],
                                scores=[0]*4,focal_score=0,focal_pw=1.5,actions=[['BOGUS']*4]*80,timing=[],
                                proof=dict(source_closure_sha256=closure,callbacks_regenerated=320,callbacks_returned=320,
                                    callbacks_completed=320,physical_turns=80,gpu_reference_state_comparisons=81,
                                    gpu_official_state_comparisons=81))
                            rows.append(row)
                            audits.append(dict(fixture=identity,candidate=candidate,ok=True,
                                row_sha256=c.design.sha(c.design.canonical(row)),source_closure_sha256=closure,
                                all_actors_regenerated=True,callbacks_regenerated=320,dual_referee_physical_turns=80,
                                tracker=dict(attempted=320,returned=320,attempts_by_seat=[80]*4,returns_by_seat=[80]*4)))
            for filename,data in (('originals.jsonl',rows),('audits.jsonl',audits)):
                (output/filename).write_bytes(b''.join(c.design.canonical(row)+b'\n' for row in data))
            count=len(fixtures)
            summary=dict(source_sha256=pins,originals_sha256=c.design.sha((output/'originals.jsonl').read_bytes()),
                audits_sha256=c.design.sha((output/'audits.jsonl').read_bytes()),original_games=count,
                independent_full_game_audits=count,original_callbacks=count*320,independently_regenerated_callbacks=count*320,
                original_gpu_physical_turns=count*80,independent_dual_referee_turns=count*80)
            c.frozen._seal(output/'summary.json',summary)
            registration=dict(candidates=[{'sha256':s} for s in candidates],fixtures=fixtures,
                protocol={'complete_games':count})
            with self.assertRaises((ValueError,OSError,KeyError)):
                c._verify_output(registration,directory)


if __name__=='__main__': unittest.main()
