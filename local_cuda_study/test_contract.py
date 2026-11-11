"""Local admission contracts with synthetic records and mocked execution only.

Actual owner HMAC functions use an explicitly patched synthetic secret. No real
registry, gold, reservation, qualification, policy, CUDA job or study is invoked.
"""
import copy
from contextlib import ExitStack
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from distributed_campaign import auth,protocol
from distributed_campaign import control as retired_control
from primary_campaign import core
from . import contract,controller


class LocalCudaContractTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='.synthetic-',dir=Path(__file__).parent)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.registration_path = self.root/'.cache/confirmation/SYNTHETIC_ONLY/registration.json'
        self.registry_path = self.root/'SYNTHETIC_REGISTRY_NEVER_READ.json'
        self.output = self.root/'.cache/local_cuda/SYNTHETIC_ONLY'
        self.ids = ['%064x'%index for index in range(32768)]
        self.arms = [letter*64 for letter in 'abcd']
        self.registration = dict(planned_games=32768,
            runtime_qualification_task_ids=self.ids[:8],
            candidates=[dict(sha256=arm,path='SYNTHETIC_NEVER_EXECUTED') for arm in self.arms],
            fixtures=[dict(id=identity,candidate=self.arms[index%4]) for index,identity in enumerate(self.ids)],
            sources={},protocol={'inference':{'fixed_synthetic_statistics':True}})
        self.gold = {identity:dict(game=self.row(identity)) for identity in self.ids[:8]}
        core.seal(self.registration_path,self.registration)
        self.witness_path = self.registration_path.parent/'runtime_gold_v2/gold_witness.json'
        self.witness_path.parent.mkdir(parents=True)
        self.witness_path.write_text('SYNTHETIC_WITNESS_NOT_AUTHENTIC_GOLD',encoding='utf8')
        self.registry = auth._Registry(self.registry_path,b'SYNTHETIC_ONLY',{'authority_id':'0'*32})
        stack = ExitStack();self.addCleanup(stack.close)
        stack.enter_context(patch.object(auth._Registry,'_secret',return_value=b'\x5a'*32))
        stack.enter_context(patch.object(contract,'ROOT',self.root))
        stack.enter_context(patch.object(contract,'REGISTRATION_PATH',self.registration_path))
        stack.enter_context(patch.object(contract,'REGISTRATION_SHA256',contract.sha(self.registration_path.read_bytes())))
        self.admitted = (self.registration,self.registry,{'synthetic':True},self.gold)

    def row(self,identity):
        index = int(identity,16)
        return dict(candidate=self.arms[index%4],fixture=identity,map_id='SYNTHETIC_MAP',
            focal_seat=0,field='economic',scores=[1,2,3,4],focal_pw=0,focal_score=1,
            opponent_ids=['SYNTHETIC_R1','SYNTHETIC_R2','SYNTHETIC_R3'],
            actions=[['STAY']*4 for _ in range(80)],faults=[])

    def admitted_mock(self):
        return patch.object(contract,'admitted_study',return_value=self.admitted)

    def test_exact_canonical_path_bytes_seal_and_auth_gold_are_required(self):
        with patch.object(contract.architectures,'validate') as validate, \
             patch.object(auth,'load_registry',return_value=self.registry) as load, \
             patch.object(contract.qualification,'read_control_gold',return_value=({'synthetic':True},self.gold)) as gold:
            registration,registry,_,records = contract.admitted_study(self.registration_path,self.registry_path)
            self.assertEqual(registration,self.registration);self.assertIs(registry,self.registry)
            self.assertEqual(set(records),set(self.ids[:8]))
            validate.assert_called_once_with(self.registration)
            load.assert_called_once_with(self.registry_path)
            gold.assert_called_once_with(self.registration_path,self.registry)
        copied=self.root/'copied/registration.json';core.seal(copied,self.registration)
        with patch.object(auth,'load_registry',side_effect=AssertionError('Auth must not be reached')), \
             self.assertRaisesRegex(ValueError,'Copied'):
            contract.admitted_study(copied,self.registry_path)
        with patch.object(contract,'REGISTRATION_SHA256','f'*64), \
             patch.object(auth,'load_registry',side_effect=AssertionError('Auth must not be reached')), \
             self.assertRaisesRegex(ValueError,'exact preregistered'):
            contract.admitted_study(self.registration_path,self.registry_path)

    def test_gold_partition_is_exact_ordered_and_duplicate_free(self):
        pending=contract.fixture_partition(self.registration,self.gold)
        self.assertEqual(pending,self.ids[8:])
        self.assertEqual(len(pending),32760)
        self.assertFalse(set(pending)&set(self.gold))
        for change in ('duplicate','missing_gold','foreign_gold','short_schedule'):
            registration=copy.deepcopy(self.registration);gold=dict(self.gold)
            if change=='duplicate': registration['fixtures'][-1]['id']=self.ids[0]
            elif change=='missing_gold': gold.pop(self.ids[0])
            elif change=='foreign_gold': gold['FOREIGN']=gold.pop(self.ids[0])
            else: registration['fixtures'].pop()
            with self.subTest(change=change),self.assertRaises(ValueError):
                contract.fixture_partition(registration,gold)

    def test_reservation_reuses_same_os_lease_and_never_replaces_another_binding(self):
        with self.admitted_mock():
            reservation=contract.reserve(self.registration_path,self.registry_path,self.output)
            canonical=self.registration_path.parent/'distributed_control_v2'
            path=canonical/'binding.json';original=path.read_bytes()
            self.assertEqual(reservation['binding']['helpers'],[])
            self.assertTrue(reservation['binding']['user_cancelled_shared_compute'])
            self.assertEqual(reservation['pending_fixture_ids'],self.ids[8:])
            self.assertEqual(reservation['primary_games_accepted'],0)
            self.assertEqual(reservation['bmcts_audits'],0)
            self.assertFalse(reservation['promotion_allowed'])
            contract.reserve(self.registration_path,self.registry_path,self.output)
            self.assertEqual(path.read_bytes(),original)
            with self.assertRaisesRegex(ValueError,'already reserved'):
                contract.reserve(self.registration_path,self.registry_path,self.output.with_name('DIFFERENT'))
            self.assertEqual(path.read_bytes(),original)
            with protocol.ResultLease(canonical),self.assertRaises(protocol.ResultBusy):
                contract.reserve(self.registration_path,self.registry_path,self.output)
            old_payload={key:value for key,value in reservation['binding'].items()
                         if key not in ('format','execution_mode','user_cancelled_shared_compute','primary_games_accepted','bmcts_audits','promotion_allowed')}
            self.assertNotEqual(auth.verify_owner(self.registry,'distributed-control-study-binding/v2',core.read_sealed(path)),old_payload)

    def test_same_canonical_binding_blocks_retired_helper_issuance(self):
        with self.admitted_mock():
            contract.reserve(self.registration_path,self.registry_path,self.output)
        old_output=self.root/'.cache/distributed_campaign/CANCELLED_SYNTHETIC_HELPER'
        with patch.object(core,'ROOT',self.root), \
             patch.object(auth,'load_registry',return_value=self.registry), \
             patch.object(contract.architectures,'validate'), \
             patch.object(retired_control,'_prepare_locked',side_effect=AssertionError('No old issuance may occur')), \
             self.assertRaisesRegex(ValueError,'already reserved another canonical'):
            retired_control.prepare(self.registration_path,self.registry_path,old_output,['CANCELLED_SYNTHETIC_HELPER'],{})
        self.assertFalse(old_output.exists())

    def test_owner_hmac_purpose_tampering_and_actor_capability_separation(self):
        value=dict(qualified=True,primary_games=0,bmcts_audits=0)
        path=self.root/'qualification.json';core.seal(path,controller._signed(self.registry,'qualification',value))
        self.assertEqual(controller._read(self.registry,'qualification',path),value)
        with self.assertRaises(auth.AuthUnavailable): controller._read(self.registry,'plan',path)
        bad=core.read_sealed(path);bad['payload']['primary_games']=100
        changed=self.root/'rehash_does_not_sign.json';core.seal(changed,bad)
        with self.assertRaises(auth.AuthUnavailable): controller._read(self.registry,'qualification',changed)
        with self.assertRaises(TypeError): copy.deepcopy(self.registry)

    def qualification_mocks(self,*,changed_tape=False,audit_callbacks=320):
        stack=ExitStack();self.addCleanup(stack.close)
        stack.enter_context(self.admitted_mock())
        stack.enter_context(patch.object(controller,'pins',return_value={'synthetic_source':'fixed'}))
        stack.enter_context(patch.object(controller,'_runtime',return_value={'synthetic_runtime':True}))
        def run(registration,identities,output,**kwargs):
            self.assertEqual(kwargs,dict(device='cuda',use_graph=True,primary_credit=0))
            self.assertIs(registration,self.registration)
            self.assertEqual(identities,self.ids[:8])
            Path(output).mkdir(parents=True,exist_ok=False)
            core.seal(Path(output)/'summary.json',dict(callbacks=2560,physics_metadata={'synthetic_cuda':True}))
            rows=[copy.deepcopy(self.gold[identity]['game']) for identity in identities]
            if changed_tape: rows[0]['actions'][0][0]='EAST'
            return rows
        runner=stack.enter_context(patch.object(controller.runner,'run_fixtures',side_effect=run))
        audit=stack.enter_context(patch.object(controller.oversight,'audit_game',return_value=dict(
            callbacks_regenerated=audit_callbacks,public_memory_oracles=80)))
        return runner,audit

    def test_qualification_replicas_equal_full_gold_and_grant_zero_new_credit(self):
        runner,audit=self.qualification_mocks()
        output=self.root/'SYNTHETIC_QUALIFICATION'
        value=controller.qualify(self.registration_path,self.registry_path,output)
        self.assertTrue(value['qualified']);self.assertEqual(value['qualification_replicas'],8)
        self.assertEqual(value['independently_regenerated_callbacks'],2560)
        self.assertEqual(value['new_study_games'],0);self.assertEqual(value['primary_games'],0)
        self.assertEqual(value['bmcts_audits'],0)
        self.assertEqual(audit.call_count,8)
        self.assertEqual(controller._read(self.registry,'qualification',output/'qualification.json'),value)
        # Opaque authentication capability is absent from execution/audit args.
        self.assertFalse(any(argument is self.registry for argument in runner.call_args.args))
        for call in audit.call_args_list:
            self.assertTrue(call.kwargs['regenerate'])
            self.assertFalse(any(argument is self.registry for argument in call.args))

    def test_qualification_rejects_tape_drift_and_incomplete_actor_regeneration(self):
        for changed,callbacks in ((True,320),(False,319)):
            with self.subTest(changed=changed,callbacks=callbacks):
                stack=ExitStack()
                with stack:
                    stack.enter_context(self.admitted_mock())
                    stack.enter_context(patch.object(controller,'pins',return_value={'synthetic_source':'fixed'}))
                    stack.enter_context(patch.object(controller,'_runtime',return_value={'synthetic_runtime':True}))
                    rows=[copy.deepcopy(self.gold[identity]['game']) for identity in self.ids[:8]]
                    if changed: rows[0]['actions'][0][0]='EAST'
                    stack.enter_context(patch.object(controller.runner,'run_fixtures',return_value=rows))
                    stack.enter_context(patch.object(controller.oversight,'audit_game',return_value=dict(callbacks_regenerated=callbacks,public_memory_oracles=80)))
                    destination=self.root/('FAILED_QUAL_%s_%s'%(changed,callbacks))
                    with self.assertRaises(ValueError): controller.qualify(self.registration_path,self.registry_path,destination)
                    self.assertFalse((destination/'qualification.json').exists())

    def test_partial_execution_interrupt_preserves_claim_zero_credit_and_no_retry(self):
        self.output.mkdir(parents=True)
        plan_path=self.output/'plan.json';plan_path.write_text('SYNTHETIC_ONLY',encoding='utf8')
        canonical=self.registration_path.parent/'distributed_control_v2'
        plan=dict(pending_fixture_ids=self.ids[8:],batch_size=64,source_sha256={'synthetic':'fixed'})
        interruption=KeyboardInterrupt('SYNTHETIC_PARTIAL_INTERRUPT')
        interruption.local_cuda_partial={'synthetic_partial':True,'physical_turns':2}
        with patch.object(controller,'_load',return_value=(plan,self.registry,self.registration,self.gold,canonical)), \
             patch.object(controller.oversight,'audit_game',return_value=dict(callbacks_regenerated=320,public_memory_oracles=80)) as audit, \
             patch.object(controller.runner,'run_fixtures',side_effect=interruption) as run:
            with self.assertRaises(KeyboardInterrupt) as caught: controller.execute(plan_path)
            self.assertIs(caught.exception,interruption)
            self.assertEqual(audit.call_count,8);self.assertEqual(run.call_count,1)
            error=controller._read(self.registry,'error',self.output/'error.json')
            self.assertEqual(error['completed_original_rows'],8)
            self.assertEqual(error['callbacks_regenerated'],2560)
            self.assertEqual(error['primary_games'],0);self.assertEqual(error['bmcts_audits'],0)
            self.assertEqual(error['failed_batch_partial'],interruption.local_cuda_partial)
            self.assertTrue((self.output/'.execution_claim').is_dir())
            self.assertFalse((self.output/'acceptance.json').exists())
            self.assertEqual(len((self.output/'games.jsonl').read_bytes().splitlines()),8)
            for row in (self.output/'audits.jsonl').read_bytes().splitlines():
                self.assertIn(b'existing_canonical_cpu_original',row)
            with self.assertRaises(ValueError): controller.execute(plan_path)
            self.assertEqual(run.call_count,1)

    def prepared_mock(self,*,qualification_change=None):
        stack=ExitStack();self.addCleanup(stack.close)
        stack.enter_context(self.admitted_mock())
        stack.enter_context(patch.object(controller,'pins',return_value={'synthetic_source':'fixed'}))
        stack.enter_context(patch.object(controller,'_runtime',return_value={'synthetic_runtime':True}))
        stack.enter_context(patch.object(auth,'load_registry',return_value=self.registry))
        receipt=dict(source_registration_sha256=contract.REGISTRATION_SHA256,
            source_sha256={'synthetic_source':'fixed'},runtime={'synthetic_runtime':True},
            qualified=True,qualification_replicas=8,full_action_tapes_equal=True,
            independently_regenerated_callbacks=2560,fixture_ids=self.ids[:8],
            new_study_games=0,primary_games=0,bmcts_audits=0)
        if qualification_change: receipt.update(qualification_change)
        qpath=self.root/'SYNTHETIC_BOUND_QUALIFICATION.json'
        core.seal(qpath,controller._signed(self.registry,'qualification',receipt))
        return qpath

    def test_prepared_plan_has_exact_residual_scope_statistics_and_no_friend_gate(self):
        qualification=self.prepared_mock()
        with patch.object(contract.qualification,'read_control_gold',side_effect=AssertionError('Admitted mock supplies gold; no other path')), \
             patch.object(controller.runner,'run_fixtures',side_effect=AssertionError('Preparation must not execute actors')):
            plan=controller.prepare(self.registration_path,self.registry_path,qualification,self.output,batch_size=64)
            loaded=controller._load(self.output/'plan.json')[0]
        self.assertEqual(plan,loaded)
        self.assertEqual(plan['pending_fixture_ids'],self.ids[8:])
        self.assertEqual(plan['binding']['helpers'],[])
        self.assertEqual(plan['original_backend_counts'],dict(existing_cpu_gold=8,new_cuda_originals=32760))
        self.assertEqual(plan['statistical_plan'],self.registration['protocol']['inference'])
        self.assertEqual(plan['planned_extra_games'],32768)
        self.assertEqual(plan['primary_games'],0);self.assertEqual(plan['bmcts_audits'],0)
        self.assertFalse(plan['promotion_allowed'])
        self.assertNotIn('runtime_approvals',plan)

    def test_signed_plan_schedule_statistics_source_runtime_and_receipt_drift_rejected(self):
        qualification=self.prepared_mock()
        plan=controller.prepare(self.registration_path,self.registry_path,qualification,self.output)
        for change in ('schedule','statistics'):
            bad=copy.deepcopy(plan)
            if change=='schedule': bad['pending_fixture_ids'][0],bad['pending_fixture_ids'][1]=bad['pending_fixture_ids'][1],bad['pending_fixture_ids'][0]
            else: bad['statistical_plan']={'CHANGED':True}
            path=self.output/(change+'.json');core.seal(path,controller._signed(self.registry,'plan',bad))
            with self.subTest(change=change),self.assertRaises(ValueError): controller._load(path)
        with patch.object(controller,'pins',return_value={'synthetic_source':'changed'}),self.assertRaises(ValueError):
            controller._load(self.output/'plan.json')
        with patch.object(controller,'_runtime',return_value={'synthetic_runtime':'changed'}),self.assertRaises(ValueError):
            controller._load(self.output/'plan.json')
        qualification.write_bytes(qualification.read_bytes()+b' ')
        with self.assertRaisesRegex(ValueError,'qualification receipt changed'):
            controller._load(self.output/'plan.json')

    def test_stale_qualification_cannot_reserve_or_prepare_originals(self):
        qualification=self.prepared_mock(qualification_change={'independently_regenerated_callbacks':2559})
        with patch.object(contract,'reserve',side_effect=AssertionError('Invalid qualification must not reserve')), \
             self.assertRaisesRegex(ValueError,'qualification is missing or stale'):
            controller.prepare(self.registration_path,self.registry_path,qualification,self.output)
        self.assertFalse(self.output.exists())

    def test_partial_coverage_and_wrong_fixture_arm_never_publish_acceptance(self):
        for wrong_arm in (False,True):
            output=self.root/'.cache/local_cuda'/('PARTIAL_'+str(wrong_arm));output.mkdir(parents=True)
            plan_path=output/'plan.json';plan_path.write_text('SYNTHETIC_ONLY',encoding='utf8')
            gold=copy.deepcopy(self.gold)
            if wrong_arm: gold[self.ids[0]]['game']['candidate']=self.arms[1]
            plan=dict(pending_fixture_ids=[],batch_size=64,source_sha256={'synthetic':'fixed'})
            canonical=self.registration_path.parent/'distributed_control_v2'
            with patch.object(controller,'_load',return_value=(plan,self.registry,self.registration,gold,canonical)), \
                 patch.object(controller.oversight,'audit_game',return_value=dict(callbacks_regenerated=320,public_memory_oracles=80)) as audit, \
                 patch.object(controller.runner,'run_fixtures',side_effect=AssertionError('No residual fixtures')):
                with self.subTest(wrong_arm=wrong_arm),self.assertRaises(ValueError): controller.execute(plan_path)
                self.assertEqual(audit.call_count,0 if wrong_arm else 8)
                self.assertFalse((output/'acceptance.json').exists())
                error=controller._read(self.registry,'error',output/'error.json')
                self.assertEqual(error['primary_games'],0);self.assertEqual(error['bmcts_audits'],0)

    def test_runtime_torchversion_is_plain_json_before_owner_signing(self):
        import torch
        from torch.torch_version import TorchVersion
        version=TorchVersion('2.11.0+cu128')
        self.assertIsNot(type(version),str)
        with patch.object(torch,'__version__',version), \
             patch.object(torch.cuda,'is_available',return_value=True), \
             patch.object(torch.cuda,'get_device_name',return_value='SYNTHETIC_DEVICE_NO_KERNELS'), \
             patch.object(torch.cuda,'get_device_capability',return_value=(12,0)), \
             patch.object(controller.transport,'runtime',return_value={'synthetic_cpu_runtime':True}):
            runtime=controller._runtime()
        self.assertIs(type(runtime['torch']),str)
        auth._canonical(runtime)
        envelope=controller._signed(self.registry,'qualification',dict(runtime=runtime,primary_games=0))
        self.assertEqual(auth.verify_owner(self.registry,'owner-local-cuda-qualification/v1',envelope)['runtime'],runtime)

    def test_local_source_pins_include_admission_auth_and_full_cuda_dependencies(self):
        pins=controller.pins()
        required={'distributed_campaign/auth.py','distributed_campaign/protocol.py',
            'distributed_campaign/qualification.py','distributed_campaign/owner.py',
            'distributed_campaign/proofs.py','confirmation_campaign/architectures.py',
            'primary_campaign/core.py','campaign_holdout/authority.py',
            'local_cuda_matches/runner.py','local_cuda_matches/physics.py',
            'local_cuda_study/controller.py','local_cuda_study/contract.py',
            'training_gpu/batch_game.py','search_coach/gpu_batch.py',
            'tests/reference_engine.py','simulator/vendor_harness/referee.py'}
        self.assertTrue(required<=set(pins))
        self.assertFalse(any(Path(name).name.startswith('test_') for name in pins))
        for name in required:
            self.assertEqual(pins[name],contract.sha((controller.ROOT/name).read_bytes()))


if __name__=='__main__': unittest.main()
