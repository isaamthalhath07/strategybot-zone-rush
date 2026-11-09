"""Synthetic metadata/authentication only: ZERO real outcomes or execution.

The fake32k cohort is not physically played. Real owner HMAC functions use an
explicit synthetic secret; real registries/keys/gold/CUDA/controllers are never
read or called. Source/oracle/gold metadata contexts are explicitly mocked.
"""
import copy
from contextlib import ExitStack,contextmanager
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from confirmation_campaign import architectures
from distributed_campaign import auth,protocol as p
from study_analysis.test_report import synthetic_design,synthetic_row
from . import report as r
REAL_GOLD = r._gold
REAL_BATCH_CONTEXT = r._batch_context
REAL_FINISH_BATCH = r._finish_batch


def seal(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    body = p.canonical(value)+b'\n'
    path.write_bytes(body)
    digest = p.sha(body)
    path.with_suffix('.sha256').write_text(digest+'\n',encoding='ascii')
    return digest


def first_line(path):
    with path.open('rb') as handle:
        return handle.readline()


def local_row(fixture,arm,map_index,source_closure='d'*64,snapshot='e'*64):
    row = synthetic_row(fixture,arm,map_index)
    row.update(public_memory_oracles=0,proof=dict(callbacks_regenerated=320,public_memory_oracles=0,
        oracle_calls_by_seat=[0]*4,gpu_reference_state_comparisons=81,gpu_official_state_comparisons=81,
        physical_turns=80,gpu_state_chain_sha256='a'*64,gpu_public_chain_sha256='b'*64,
        source_closure_sha256=source_closure,registration_snapshot_sha256=snapshot,
        all_inputs_gpu_public_only=True,cpu_referees_observers_only=True,actor_backend='CPython CPU',
        physics_backend='local CUDA',primary_games=0,canonical_local_admission='pending',completed_per_game_bmcts_audits=0))
    return row


class SyntheticAcceptedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(prefix='.synthetic-',dir=Path(__file__).parent)
        cls.root = Path(cls.temporary.name).resolve()
        cls.registration_path = cls.root/'.cache/confirmation/SYNTHETIC_ONLY/registration.json'
        cls.directory = cls.root/'.cache/local_cuda/SYNTHETIC_ONLY'
        cls.registry_path = cls.root/'SYNTHETIC_REGISTRY_NEVER_READ.json'
        cls.registry = auth._Registry(cls.registry_path,b'SYNTHETIC_NOT_A_REGISTRY',{'authority_id':'1'*32})
        cls.registration = synthetic_design()
        cls.ids = [item['id'] for item in cls.registration['fixtures']]
        cls.gold_ids = cls.ids[:8]
        cls.registration.update(runtime_qualification_task_ids=cls.gold_ids,guards={},sources={})
        cls.reg_sha = seal(cls.registration_path,cls.registration)
        cls.design = r.old._design(cls.registration)
        cls.pins = r._runtime_source_pins()
        cls.runner_pins = r._runner_pins()
        cls.batch_size = 256
        cls.cpu_runtime = dict(implementation='CPython',actor_backend='CPython CPU original Python actors',cuda_used_by_policy=False)
        cls.gold = {}
        cls.directory.mkdir(parents=True)
        indices = {value:index for index,value in enumerate(architectures.ARMS)}
        maps = {item['id']:index for index,item in enumerate(cls.registration['maps'])}
        fixtures = cls.design[3]
        ordered = cls.gold_ids+[identity for identity in cls.ids if identity not in set(cls.gold_ids)]
        cls.schedule = r._source_schedule(cls.registration)
        cls.batch_snapshots = {}
        for offset in range(8,len(ordered),cls.batch_size):
            selected = ordered[offset:offset+cls.batch_size]
            digest = p.sha(p.canonical(r._source_snapshot(cls.registration,fixtures,selected,cls.schedule))+b'\n')
            cls.batch_snapshots.update({identity:digest for identity in selected})
        with (cls.directory/'games.jsonl').open('wb') as games,(cls.directory/'audits.jsonl').open('wb') as audits:
            for identity in ordered:
                fixture = fixtures[identity]
                a,m = indices[fixture['candidate']],maps[fixture['map_id']]
                if identity in cls.gold_ids:
                    row = synthetic_row(fixture,a,m);cls.gold[identity] = row
                    backend = 'existing_canonical_cpu_original'
                else:
                    row = local_row(fixture,a,m,p.sha(p.canonical(cls.runner_pins)),cls.batch_snapshots[identity])
                    backend = 'local_cuda_physics_exact_cpu_python_actors'
                games.write(p.canonical(row)+b'\n')
                audits.write(p.canonical(dict(fixture=identity,candidate=fixture['candidate'],game_sha256=p.sha(p.canonical(row)),
                    original_backend=backend,callbacks_regenerated=320,public_memory_oracles=0))+b'\n')
        cls.games_sha = p.sha((cls.directory/'games.jsonl').read_bytes())
        cls.audits_sha = p.sha((cls.directory/'audits.jsonl').read_bytes())
        cls.runtime = dict(SYNTHETIC_METADATA_ONLY=True,actual_games_executed=0)
        cls.physics = dict(format='local-cuda-match-physics/1',device='cuda:0',cuda_kernel_executed=True,use_graph=True,
            max_turns=80,batch_size=8,accepted_batch_steps=80,accepted_branch_turn_events=640,
            setup_throwaway_transitions=3,setup_primary_match_credit=0,setup_completed_game_audit_credit=0,
            policy_backend='External exact CPU actors',
            source_sha256={key:cls.pins[key] for key in ('training_gpu/batch_game.py','search_coach/gpu_batch.py','local_cuda_matches/physics.py')},
            rules=dict(frozen_stay_counts=False,claim_resets_progress=True,catch_requires_stay=True,
                       lost_contest_is_stay=True,home_upgradable=True))
        cls.qual_path = cls.root/'SYNTHETIC_QUALIFICATION_NOT_EXECUTED/qualification.json'

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def setUp(self):
        self.stack = ExitStack();self.addCleanup(self.stack.close)
        for target,name,value in ((auth._Registry,'_secret',b'\x62'*32),(r,'ROOT',self.root),
                (r,'REGISTRATION_PATH',self.registration_path),(r,'REGISTRATION_SHA256',self.reg_sha)):
            self.stack.enter_context(patch.object(target,name,return_value=value) if name=='_secret' else patch.object(target,name,value))
        self.stack.enter_context(patch.object(auth,'load_registry',return_value=self.registry))
        self.stack.enter_context(patch.object(r,'_source_entries'))
        self.stack.enter_context(patch.object(r,'_oracle_counts',return_value=[0]*4))
        self.stack.enter_context(patch.object(r,'_runtime_source_pins',return_value=self.pins))
        self.stack.enter_context(patch.object(r,'_runner_pins',return_value=self.runner_pins))
        self.stack.enter_context(patch.object(r,'_gold',return_value=(self.gold,'c'*64)))
        def batch_context(registration,fixtures,directory,identities,pins,cpu_runtime,schedule):
            return dict(directory=directory,fixture_ids=identities,registration_snapshot_sha256=self.batch_snapshots[identities[0]],
                source_closure_sha256=p.sha(p.canonical(pins)),header_sha256='1'*64,summary_sha256='2'*64,
                games_sha256='3'*64,turns_sha256='4'*64)
        self.stack.enter_context(patch.object(r,'_batch_context',side_effect=batch_context))
        self.stack.enter_context(patch.object(r,'_finish_batch'))
        self.binding = dict(format=r.LOCAL_FORMAT,source_registration_path=str(self.registration_path),
            source_registration_sha256=self.reg_sha,canonical_output=str(self.directory),registry_path=str(self.registry_path),
            role='extra_control_assignment',execution_mode='owner_local_cuda_physics_exact_cpu_python_actors',helpers=[],
            user_cancelled_shared_compute=True,rule='One canonical original cohort; import8 consumed originals once and execute32760 remaining originals locally.',
            primary_games_accepted=0,bmcts_audits=0,promotion_allowed=False)
        self.write_signed(self.registration_path.parent/'distributed_control_v2/binding.json','distributed-control-study-binding/v2',self.binding)
        summary = dict(format=r.RUNNER_FORMAT,complete_games=8,callbacks=2560,gpu_physical_turns=640,
            gpu_reference_state_comparisons=648,gpu_official_state_comparisons=648,primary_games=0,
            completed_per_game_bmcts_audits=0,physics_metadata=self.physics,source_sha256=self.runner_pins)
        summary['cpu_runtime'] = self.cpu_runtime
        summary_sha = seal(self.qual_path.parent/'summary.json',summary)
        self.qualification = dict(format=r.LOCAL_FORMAT,qualified=True,source_registration_sha256=self.reg_sha,
            source_sha256=self.pins,runtime=self.runtime,fixture_ids=self.gold_ids,full_action_tapes_equal=True,
            actor_backend='CPU exact Python',physics_backend='CUDA',qualification_replicas=8,new_study_games=0,
            primary_games=0,bmcts_audits=0,original_actor_callbacks=2560,independently_regenerated_callbacks=2560,
            public_memory_oracles=0,
            physics_metadata=self.physics,backend_summary_sha256=summary_sha,canonical_gold_witness_sha256='c'*64)
        qual_sha = self.write_signed(self.qual_path,'owner-local-cuda-qualification/v1',self.qualification)
        pending = self.ids[8:]
        self.plan = dict(format=r.LOCAL_FORMAT,binding=self.binding,source_sha256=self.pins,runtime=self.runtime,
            source_registration_path=str(self.registration_path),registry_path=str(self.registry_path),promotion_allowed=False,
            statistical_plan=architectures.inference_plan(),original_backend_counts=dict(existing_cpu_gold=8,new_cuda_originals=32760),
            planned_extra_games=32768,primary_games=0,bmcts_audits=0,batch_size=self.batch_size,
            primary_games_accepted=0,
            qualification_path=str(self.qual_path),qualification_sha256=qual_sha,gold_witness_sha256='c'*64,
            pending_fixture_ids=pending,fixture_id_list_sha256=p.sha(p.canonical(pending)),canonical_gold_originals=8,new_local_cuda_originals=32760)
        plan_sha = self.write_signed(self.directory/'plan.json','owner-local-cuda-plan/v1',self.plan)
        self.accepted = dict(format=r.LOCAL_FORMAT,complete=True,promoted=False,source_sha256=self.pins,runtime=self.runtime,
            source_registration_sha256=self.reg_sha,plan_sha256=plan_sha,original_backend_counts=self.plan['original_backend_counts'],
            accepted_extra_games=32768,primary_games=0,bmcts_audits=0,original_callbacks=32768*320,
            independent_owner_regenerated_callbacks=32768*320,games_sha256=self.games_sha,audits_sha256=self.audits_sha)
        self.write_signed(self.directory/'acceptance.json','owner-local-cuda-acceptance/v1',self.accepted)

    def write_signed(self,path,purpose,payload):
        return seal(path,auth.sign_owner(self.registry,purpose,payload))

    def test_complete_synthetic_cohort_authentication_integer_cube_all_six_frozen_contrasts_and_no_runtime(self):
        import builtins
        actual = builtins.__import__
        def blocked(name,*args,**kwargs):
            if name=='torch' or name.startswith('local_cuda_study') or name.startswith('local_cuda_matches'):
                raise AssertionError('Analyzer imported an execution runtime')
            return actual(name,*args,**kwargs)
        with patch.object(builtins,'__import__',side_effect=blocked):
            result = r.analyze(self.registration_path,self.registry_path)
        self.assertEqual(result['coverage']['unique_games'],32768)
        self.assertEqual(result['coverage']['canonical_cpu_gold_originals'],8)
        self.assertEqual(result['coverage']['local_cuda_originals'],32760)
        self.assertEqual([arm['games'] for arm in result['arms']],[8192]*4)
        self.assertEqual([arm['mean_pairwise']['decimal'] for arm in result['arms']],[1.5]*4)
        self.assertEqual(len(result['comparisons']),6)
        self.assertEqual(result['inference_plan'],architectures.inference_plan())
        self.assertEqual(result['bootstrap']['replicates'],60000)
        self.assertEqual(result['bootstrap']['seed'],202611091740)
        self.assertEqual(result['bootstrap']['percentile_indices_zero_based'],[249,59749])
        self.assertEqual(len(result['architecture_assessment']['observed_mean_leaders']),4)
        self.assertIsNone(result['architecture_assessment']['descriptively_separated_arm'])
        self.assertFalse(result['promoted'])
        self.assertEqual(result['new_actor_callbacks'],0)
        self.assertEqual(result['primary_match_credit'],0)

    def test_owner_purpose_mac_incomplete_counts_sources_and_promotion_are_not_repaired(self):
        for change in (dict(complete=False),dict(accepted_extra_games=32767),dict(primary_games=1),
                       dict(independent_owner_regenerated_callbacks=32768*320-1),dict(promoted=True),dict(source_sha256={})):
            with self.subTest(change=change):
                self.write_signed(self.directory/'acceptance.json','owner-local-cuda-acceptance/v1',dict(self.accepted,**change))
                with self.assertRaises(ValueError):
                    r._context(self.registration_path,self.registry_path)
        self.write_signed(self.directory/'acceptance.json','owner-local-cuda-plan/v1',self.accepted)
        with self.assertRaises(auth.AuthUnavailable):
            r._context(self.registration_path,self.registry_path)

    def test_binding_remote_helpers_wrong_output_path_or_rehashed_plan_statistics_rejected(self):
        for change in (dict(helpers=['RETIRED_HELPER']),dict(canonical_output=str(self.root/'elsewhere')),
                       dict(user_cancelled_shared_compute=False)):
            self.write_signed(self.registration_path.parent/'distributed_control_v2/binding.json',
                              'distributed-control-study-binding/v2',dict(self.binding,**change))
            with self.assertRaises(ValueError):
                r._context(self.registration_path,self.registry_path)
        self.write_signed(self.registration_path.parent/'distributed_control_v2/binding.json','distributed-control-study-binding/v2',self.binding)
        changed = copy.deepcopy(self.plan);changed['statistical_plan']['bootstrap_seed']+=1
        digest = self.write_signed(self.directory/'plan.json','owner-local-cuda-plan/v1',changed)
        self.write_signed(self.directory/'acceptance.json','owner-local-cuda-acceptance/v1',dict(self.accepted,plan_sha256=digest))
        with self.assertRaises(ValueError):
            r._context(self.registration_path,self.registry_path)
        with self.assertRaisesRegex(ValueError,'original canonical'):
            r._context(self.root/'copy.json',self.registry_path)

    def test_missing_or_duplicate_audit_never_reaches_statistics(self):
        directory = self.root/'SYNTHETIC_PARTIAL_ONLY'
        directory.mkdir(exist_ok=True)
        first_game = first_line(self.directory/'games.jsonl')
        first_audit = first_line(self.directory/'audits.jsonl')
        for body in (b'',first_audit*2):
            (directory/'games.jsonl').write_bytes(first_game*2)
            (directory/'audits.jsonl').write_bytes(body)
            with self.assertRaises(ValueError),patch.object(r.old,'_bootstrap') as bootstrap:
                r._collect(self.registration,self.design,directory,dict(batch_size=self.batch_size,
                    games_sha256=p.sha(first_game*2),audits_sha256=p.sha(body)),self.gold)
            bootstrap.assert_not_called()

    def test_local_proof_callback_oracle_backend_and_transcript_faults_reject(self):
        fixture = self.registration['fixtures'][8]
        row = local_row(fixture,0,0)
        for mutate in (lambda x:x['proof'].update(callbacks_regenerated=319),
                       lambda x:x['proof'].update(gpu_official_state_comparisons=80),
                       lambda x:x['proof'].update(physics_backend='CPU'),
                       lambda x:x['proof'].update(primary_games=1),
                       lambda x:x.update(actions=x['actions'][:-1]),
                       lambda x:x['proof'].update(oracle_calls_by_seat=[80,0,0,0])):
            changed = copy.deepcopy(row);mutate(changed)
            with self.assertRaises(ValueError):
                r._local_row(changed,fixture,[0]*4)

    def test_exact_game_audit_hash_binding_and_backend_cannot_be_retagged(self):
        directory = self.root/'SYNTHETIC_CORRUPT_FIRST_AUDIT'
        directory.mkdir(exist_ok=True)
        first_game = first_line(self.directory/'games.jsonl')
        first_audit = p.loads(first_line(self.directory/'audits.jsonl'))
        for change in (dict(game_sha256='0'*64),dict(original_backend='local_cuda_physics_exact_cpu_python_actors'),
                       dict(callbacks_regenerated=319),dict(public_memory_oracles=80)):
            body = p.canonical(dict(first_audit,**change))+b'\n'
            (directory/'games.jsonl').write_bytes(first_game)
            (directory/'audits.jsonl').write_bytes(body)
            with self.assertRaisesRegex(ValueError,'Every exact original'):
                r._collect(self.registration,self.design,directory,dict(batch_size=self.batch_size),self.gold)

    def test_canonical_gold_hmac_records_bind_original_rows_once_without_replay(self):
        directory = self.registration_path.parent/'runtime_gold_v2'
        directory.mkdir(exist_ok=True)
        creator,context = {'slot_id':'SYNTHETIC_ONLY'},{'SYNTHETIC_METADATA_ONLY':True}
        values = [dict(game=self.gold[identity],audit={'SYNTHETIC_NOT_A_REAL_PROOF':True},
                       creator=creator,study_registration_sha256=self.reg_sha) for identity in self.gold_ids]
        def records(rows):
            body = b''.join(p.canonical(auth.sign_owner(self.registry,'distributed-control-gold-record/v2',value))+b'\n' for value in rows)
            (directory/'gold_records.jsonl').write_bytes(body)
            return p.sha(body)
        binding = dict(study_registration_sha256=self.reg_sha,task_ids=self.gold_ids,creator=creator,qualification_context=context)
        self.write_signed(directory/'gold_registration.json','distributed-control-gold-registration/v2',binding)
        witness = dict(binding,source_registration_path=str(self.registration_path),records_sha256=records(values),
                       actual_study_games=8,full_audit_callbacks=2560,primary_games_accepted=0)
        digest = self.write_signed(directory/'gold_witness.json','distributed-control-gold-witness/v2',witness)
        with patch.object(r.proofs,'validate') as validate:
            rows,sha = REAL_GOLD(self.registry,self.registration,self.registration_path,digest)
        self.assertEqual(rows,self.gold)
        self.assertEqual(sha,digest)
        self.assertEqual(validate.call_count,8)
        duplicated = values[:1]+values[:1]+values[2:]
        witness['records_sha256'] = records(duplicated)
        digest = self.write_signed(directory/'gold_witness.json','distributed-control-gold-witness/v2',witness)
        with patch.object(r.proofs,'validate'),self.assertRaisesRegex(ValueError,'duplicate original gold'):
            REAL_GOLD(self.registry,self.registration,self.registration_path,digest)

    def test_actual_runner_batch_source_snapshot_summary_and_80turn_links_bind_both_proof_hashes(self):
        directory = self.root/'SYNTHETIC_BATCH_BINDING_ONLY'
        directory.mkdir(exist_ok=True)
        identities = self.ids[8:10];fixtures = self.design[3]
        snapshot = r._source_snapshot(self.registration,fixtures,identities,self.schedule)
        snapshot_sha = seal(directory/'registration.json',snapshot)
        closure = p.sha(p.canonical(self.runner_pins))
        rows = [local_row(fixtures[identity],index,0,closure,snapshot_sha) for index,identity in enumerate(identities)]
        games_body = b''.join(p.canonical(row)+b'\n' for row in rows)
        (directory/'games.jsonl').write_bytes(games_body)
        turns = [dict(turn=turn,actions=[row['actions'][turn-1] for row in rows],
                      gpu_state_chain_sha256=['a'*64]*2,gpu_public_chain_sha256=['b'*64]*2,
                      per_lane_completed_physical_turns=[turn]*2) for turn in range(1,81)]
        turn_bytes = b''.join(p.canonical(turn)+b'\n' for turn in turns)
        (directory/'turns.jsonl').write_bytes(turn_bytes)
        header = dict(format=r.RUNNER_FORMAT,fixture_ids=identities,registration_snapshot_sha256=snapshot_sha,
            source_sha256=self.runner_pins,source_schedule=self.schedule,cpu_runtime=self.cpu_runtime,
            actor_backend='CPython CPU original Python actors',physics_backend='local CUDA',
            primary_games=0,completed_per_game_bmcts_audits=0)
        seal(directory/'execution_started.json',header)
        physics = dict(self.physics,batch_size=2,accepted_branch_turn_events=160)
        summary = dict(format=r.RUNNER_FORMAT,complete_games=2,callbacks=640,gpu_physical_turns=160,
            gpu_reference_state_comparisons=162,gpu_official_state_comparisons=162,
            primary_games=0,completed_per_game_bmcts_audits=0,source_sha256=self.runner_pins,
            source_schedule=self.schedule,cpu_runtime=self.cpu_runtime,physics_metadata=physics,
            games_sha256=p.sha(games_body),turns_sha256=p.sha(turn_bytes))
        seal(directory/'summary.json',summary)
        def context():
            return REAL_BATCH_CONTEXT(self.registration,fixtures,directory,identities,
                                      self.runner_pins,self.cpu_runtime,self.schedule)
        bound = context()
        for row in rows:
            r._local_row(row,fixtures[row['fixture']],[0]*4)
            r._row_binding(row,bound)
        REAL_FINISH_BATCH(bound,rows,p.sha(games_body))
        for field in ('source_closure_sha256','registration_snapshot_sha256'):
            changed = copy.deepcopy(rows[0]);changed['proof'][field]='0'*64
            with self.assertRaisesRegex(ValueError,'source closure or selected-batch'):
                r._row_binding(changed,bound)
        swapped = copy.deepcopy(snapshot);swapped['fixtures'].reverse()
        seal(directory/'registration.json',swapped)
        with self.assertRaisesRegex(ValueError,'exact ordered source fixtures'):
            context()
        seal(directory/'registration.json',snapshot)
        seal(directory/'summary.json',dict(summary,games_sha256='0'*64))
        with self.assertRaisesRegex(ValueError,'exact sealed CUDA batch games'):
            REAL_FINISH_BATCH(context(),rows,p.sha(games_body))
        turns[0]['actions'][0]=['SHIELD']*4
        altered = b''.join(p.canonical(turn)+b'\n' for turn in turns)
        (directory/'turns.jsonl').write_bytes(altered)
        seal(directory/'summary.json',dict(summary,turns_sha256=p.sha(altered)))
        with self.assertRaisesRegex(ValueError,'action, clock, lane count'):
            REAL_FINISH_BATCH(context(),rows,p.sha(games_body))


class AssessmentTests(unittest.TestCase):
    def test_observed_best_without_positive_interval_against_all_others_is_inconclusive(self):
        arms = [dict(sha256=arm,pairwise_numerator_sum=4-index) for index,arm in enumerate(architectures.ARMS)]
        comparisons = [dict(first=first,second=second,descriptive_bonferroni_interval=[dict(numerator=0),dict(numerator=1)])
                       for i,first in enumerate(architectures.ARMS) for second in architectures.ARMS[i+1:]]
        result = r.assessment(arms,comparisons)
        self.assertIsNone(result['descriptively_separated_arm'])
        for item in comparisons:
            item['descriptive_bonferroni_interval'][0]['numerator']=1
        result = r.assessment(arms,comparisons)
        self.assertEqual(result['descriptively_separated_arm'],architectures.ARMS[0])
        self.assertFalse(result['automatic_promotion'])


if __name__=='__main__':
    unittest.main()
