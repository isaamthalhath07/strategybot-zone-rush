"""Independent bounded source/schema/arithmetic checks, without real outcomes."""
import ast
import builtins
import copy
from fractions import Fraction
import importlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from confirmation_campaign import architectures
from distributed_campaign import protocol as p
from . import report as model


ROOT=Path(__file__).resolve().parents[1]


def fixture_and_row():
    fixture=dict(id='a'*64,candidate=architectures.ARMS[0],map_id='b'*64,seat=0,
        token=1,field='economic',opponents=[dict(id='SYNTHETIC_%d'%seat,seat=seat,family='unit_stub') for seat in (1,2,3)])
    row=dict(candidate=fixture['candidate'],fixture=fixture['id'],map_id=fixture['map_id'],
        focal_seat=0,field='economic',scores=[40,10,20,30],focal_pw=3,focal_score=40,
        opponent_ids=[spec['id'] for spec in fixture['opponents']],actions=[['STAY']*4 for _ in range(80)],
        timing=[dict(calls=80,total_ms=80.0,max_ms=1.0,first_ms=1.0,regular_max_ms=1.0) for _ in range(4)],
        faults=[],elapsed_s=1.0)
    return fixture,row


def current_runner_row():
    fixture,row=fixture_and_row()
    proof=dict(callbacks_regenerated=320,public_memory_oracles=0,oracle_calls_by_seat=[0]*4,
        gpu_reference_state_comparisons=81,gpu_official_state_comparisons=81,physical_turns=80,
        gpu_state_chain_sha256='c'*64,gpu_public_chain_sha256='d'*64,
        source_closure_sha256='e'*64,registration_snapshot_sha256='f'*64,
        all_inputs_gpu_public_only=True,cpu_referees_observers_only=True,
        actor_backend='CPython CPU',physics_backend='local CUDA',primary_games=0,
        canonical_local_admission='pending',completed_per_game_bmcts_audits=0)
    row.update(proof=proof,public_memory_oracles=0)
    return fixture,row


class IndependentAnalysisTests(unittest.TestCase):
    def test_actual_256_plan_metadata_partitions_all_registered_ids_skipping_noncontiguous_gold(self):
        # Metadata only: never open acceptance, qualification, games, audits,
        # batches, private registry or any partial outcome file.
        path=ROOT/'.cache/local_cuda/architecture_v2_001/plan.json'
        if not path.exists():
            self.skipTest('Optional local plan metadata is absent; no runtime is invoked')
        envelope,_=model.old._sealed(path,128*1024*1024)
        plan=envelope['payload']
        self.assertEqual(plan['batch_size'],256)
        self.assertEqual(plan['binding']['source_registration_sha256'],model.REGISTRATION_SHA256)
        registration,digest=model.old._sealed(Path(plan['source_registration_path']),100*1024*1024)
        self.assertEqual(digest,model.REGISTRATION_SHA256)
        identities=[fixture['id'] for fixture in registration['fixtures']]
        gold=registration['runtime_qualification_task_ids'];gold_set=set(gold)
        self.assertEqual(len(identities),32768);self.assertEqual(len(set(identities)),32768)
        self.assertEqual(len(gold),8);self.assertEqual(len(gold_set),8)
        self.assertNotEqual(gold,identities[:8],'Exercise noncontiguous canonical gold')
        pending=[identity for identity in identities if identity not in gold_set]
        self.assertEqual(plan['pending_fixture_ids'],pending)
        self.assertEqual(len(pending),32760);self.assertFalse(set(pending)&gold_set)
        self.assertEqual(plan['fixture_id_list_sha256'],p.sha(p.canonical(pending)))
        self.assertEqual(pending[0],next(identity for identity in identities if identity not in gold_set))
        chunks=[pending[offset:offset+256] for offset in range(0,len(pending),256)]
        self.assertEqual(len(chunks),128)
        self.assertEqual([len(chunk) for chunk in chunks],[256]*127+[248])
        self.assertEqual([identity for chunk in chunks for identity in chunk],pending)

    def test_actual_frozen_runner_proof_schema_is_accepted_without_dropping_fields(self):
        # Read source bytes only: importing the CUDA runner is prohibited.
        tree=ast.parse((ROOT/'local_cuda_matches/runner.py').read_bytes())
        keywords=[]
        for call in ast.walk(tree):
            if isinstance(call,ast.Call) and isinstance(call.func,ast.Name) and call.func.id=='dict':
                names={keyword.arg for keyword in call.keywords if keyword.arg}
                if {'callbacks_regenerated','oracle_calls_by_seat','physical_turns'}<=names:
                    keywords.append(names)
                if {'source_closure_sha256','registration_snapshot_sha256'}<=names:
                    keywords.append(names)
        self.assertEqual(len(keywords),2)
        fixture,row=current_runner_row()
        self.assertEqual(set(row['proof']),set.union(*keywords))
        self.assertEqual(model._local_row(row,fixture,[0]*4),6)

    def test_consumed_qualification_and_acceptance_fields_exist_in_frozen_controller_schema(self):
        source=ast.parse((ROOT/'local_cuda_study/controller.py').read_bytes())
        produced={}
        for assignment in ast.walk(source):
            if isinstance(assignment,ast.Assign) and isinstance(assignment.value,ast.Call):
                call=assignment.value
                if isinstance(call.func,ast.Name) and call.func.id=='dict':
                    for target in assignment.targets:
                        if isinstance(target,ast.Name) and target.id in ('receipt','acceptance'):
                            produced[target.id]={keyword.arg for keyword in call.keywords if keyword.arg}
        function=next(node for node in ast.parse(Path(model.__file__).read_bytes()).body
                      if isinstance(node,ast.FunctionDef) and node.name=='_context')
        consumed={key:set() for key in ('qualified','accepted')}
        for node in ast.walk(function):
            if (isinstance(node,ast.Subscript) and isinstance(node.value,ast.Name)
                    and node.value.id in consumed and isinstance(node.slice,ast.Constant)
                    and type(node.slice.value) is str):
                consumed[node.value.id].add(node.slice.value)
        self.assertTrue(consumed['qualified']<=produced['receipt'])
        self.assertTrue(consumed['accepted']<=produced['acceptance'])

    def test_private_execution_imports_are_not_needed_for_analysis_source_checks(self):
        original=builtins.__import__
        def guard(name,*args,**kwargs):
            if name=='torch' or name.startswith(('local_cuda_study','local_cuda_matches')):
                raise AssertionError('Analysis imported an execution/CUDA runtime')
            return original(name,*args,**kwargs)
        with patch.object(builtins,'__import__',side_effect=guard):
            reloaded=importlib.reload(model)
            pins=reloaded._runtime_source_pins()
        self.assertEqual(len(pins),49)
        self.assertIn('local_cuda_study/controller.py',pins)
        self.assertIn('distributed_campaign/auth.py',pins)
        self.assertEqual(pins['local_cuda_matches/runner.py'],p.sha((ROOT/'local_cuda_matches/runner.py').read_bytes()))

    def test_wrong_fixture_arm_boolean_coverage_and_malformed_proof_hashes_reject(self):
        fixture,row=current_runner_row()
        changes=(lambda r:r.update(candidate=architectures.ARMS[1]),
                 lambda r:r['proof'].update(callbacks_regenerated=True),
                 lambda r:r['proof'].update(gpu_reference_state_comparisons=81.0),
                 lambda r:r['proof'].update(source_closure_sha256='bad'),
                 lambda r:r['proof'].update(registration_snapshot_sha256='bad'))
        for change in changes:
            bad=copy.deepcopy(row);change(bad)
            with self.subTest(change=change),self.assertRaises(ValueError): model._local_row(bad,fixture,[0]*4)

    def test_partial_files_cannot_reach_bootstrap_even_with_mocked_owner_context(self):
        fixture,row=fixture_and_row()
        with tempfile.TemporaryDirectory(prefix='.independent-',dir=Path(__file__).parent) as temp:
            directory=Path(temp)
            body=p.canonical(row)+b'\n'
            audit=p.canonical(dict(fixture=fixture['id'],candidate=fixture['candidate'],
                game_sha256=p.sha(p.canonical(row)),original_backend='existing_canonical_cpu_original',
                callbacks_regenerated=320,public_memory_oracles=0))+b'\n'
            (directory/'games.jsonl').write_bytes(body);(directory/'audits.jsonl').write_bytes(audit)
            registration=dict(runtime_qualification_task_ids=[fixture['id']],
                fixtures=[fixture],protocol={'inference':architectures.inference_plan()})
            design=(list(architectures.ARMS),list(model.core.FIELDS),[fixture['map_id']],{fixture['id']:fixture})
            context=(registration,design,directory,dict(games_sha256=p.sha(body),audits_sha256=p.sha(audit),
                batch_size=64,qualified_cpu_runtime={'synthetic':True}),{fixture['id']:row})
            with patch.object(model,'_context',return_value=context),patch.object(model,'_reporter_pins',return_value={}), \
                 patch.object(model,'_oracle_counts',return_value=[0]*4), \
                 patch.object(model.old,'_bootstrap',side_effect=AssertionError('Partial statistics are forbidden')) as boot:
                with self.assertRaises(ValueError): model.analyze('SYNTHETIC_ONLY','SYNTHETIC_ONLY')
            boot.assert_not_called()

    def test_all_six_frozen_bootstrap_contrasts_have_analytic_constant_offset_endpoints(self):
        cube=[[[16*value]*4 for value in values] for values in ((5,4,3,2),(6,5,4,3))]
        contrasts,bootstrap=model.old._bootstrap(cube,architectures.inference_plan())
        self.assertEqual(len(contrasts),6)
        self.assertEqual(bootstrap['replicates'],60000)
        self.assertEqual(bootstrap['percentile_indices_zero_based'],[249,59749])
        self.assertTrue(bootstrap['shared_map_draws_for_all_six'])
        for contrast in contrasts:
            i,j=architectures.ARMS.index(contrast['first']),architectures.ARMS.index(contrast['second'])
            expected=Fraction(j-i,2)
            for result in [contrast['mean_pairwise_difference']]+contrast['descriptive_bonferroni_interval']:
                self.assertEqual(Fraction(result['numerator'],result['denominator']),expected)
            for result in contrast['field_mean_differences'].values():
                self.assertEqual(Fraction(result['numerator'],result['denominator']),expected)


if __name__=='__main__': unittest.main()
