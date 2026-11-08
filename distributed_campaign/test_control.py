"""Local logical-slot integration on OLD maps: zero actual V2/primary credit."""
import copy
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from distributed_campaign import auth, control, owner, protocol as p, qualification
from primary_campaign import core


class ControlPipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        required = [core.ROOT/'.cache/primary/campaign_v1_20261109/train_000/registration.json',
                    core.ROOT/'.cache/primary/campaign_v1_20261109/train_002/registration.json',
                    core.ROOT/'confirmation_campaign/evidence/architectures_v2/feint_original.py']
        if any(not path.exists() for path in required):
            raise unittest.SkipTest('Local ignored old-map evidence or frozen architecture source unavailable')
        cache = core.ROOT/'.cache/distributed_campaign'
        cache.mkdir(parents=True,exist_ok=True)
        cls.temporary = tempfile.TemporaryDirectory(prefix='ct-',dir=cache)
        cls.directory = Path(cls.temporary.name)
        cls.meta = auth.provision(cls.directory/'private',{'owner':'LOCAL_LOGICAL_OWNER','a':'LOCAL_LOGICAL_A','b':'LOCAL_LOGICAL_B'})
        original = core.read_sealed(core.ROOT/'.cache/primary/campaign_v1_20261109/train_000/registration.json')
        sources = [core.ROOT/'bot.py',core.ROOT/'tester_bots/blocker.py',
                   core.ROOT/'confirmation_campaign/evidence/architectures_v2/feint_original.py']
        train2 = core.read_sealed(core.ROOT/'.cache/primary/campaign_v1_20261109/train_002/registration.json')
        challenger = next(item for item in train2['candidates'] if item['sha256'].startswith('50d82d7a'))
        sources.insert(1,Path(challenger['path']))
        candidates = [dict(id='synthetic_'+str(i),path=str(path),sha256=p.sha(path.read_bytes())) for i,path in enumerate(sources)]
        fixtures = []
        # Eight known cases followed by four genuinely executed local controls.
        for episode in range(3):
            for index,candidate in enumerate(candidates):
                field = 'economic' if episode == 0 else 'independent'
                fixture = copy.deepcopy(next(item for item in original['fixtures'] if item['field'] == field))
                fixture.update(id=p.sha(p.canonical(['SYNTHETIC_OLD_MAP_CONTROL',episode,index])),
                               candidate=candidate['sha256'])
                fixtures.append(fixture)
        registration = dict(original,format='SYNTHETIC_CONTROLLER_MECHANICS_ONLY',
                            campaign_id=p.sha(b'ZERO_REAL_V2_PRIMARY_CREDIT'),candidates=candidates,fixtures=fixtures,
                            required_focal_sources=[item['sha256'] for item in candidates],
                            runtime_qualification_task_ids=[item['id'] for item in fixtures[:8]])
        cls.registration_path = cls.directory/'study/registration.json'
        core.seal(cls.registration_path,registration)
        # The real study validator is deliberately NOT used on this synthetic
        # old-map registration. No actual V2 fixture is read/executed here.
        cls.patcher = mock.patch('confirmation_campaign.architectures.validate',return_value=True)
        cls.patcher.start()
        cls.gold = qualification.prepare_control(cls.registration_path,cls.meta['registry_path'],cls.directory/'qual','owner',['a','b'])
        approvals = {}
        for packet in cls.gold['packets']:
            value = core.read_sealed(packet['packet'])
            shard = value['distribution']['shards'][0]
            results = cls._worker(shard,packet['slot'])
            approval = cls.directory/(packet['slot']+'_approval.json')
            qualification.approve(packet['packet'],results,cls.meta['registry_path'],approval)
            approvals[packet['slot']] = approval
        cls.plan_path = cls.directory/'plan/plan.json'
        cls.plan = control.prepare(cls.registration_path,cls.meta['registry_path'],cls.plan_path.parent,['a','b'],approvals)
        cls.play_results = {}
        for shard in cls.plan['distribution']['shards']:
            results = cls._worker(shard,shard['helper_label'])
            cls.play_results[shard['id']] = results
            imported = control.ingest_play(cls.plan_path,shard['id'],results)
            if imported['imported_actual_games'] != len(shard['fixture_ids']):
                raise AssertionError('PLAY import did not create exact assigned controls')
        cls.audit_path = cls.plan_path.parent/'audits/audit_plan.json'
        cls.audit = control.prepare_audits(cls.plan_path,cls.audit_path.parent,['a','b'],approvals)
        cls.audit_results = {}
        for shard in cls.audit['distribution']['shards']:
            results = cls._worker(shard,shard['helper_label'])
            cls.audit_results[shard['id']] = results
            control.ingest_audit(cls.plan_path,cls.audit_path,shard['id'],results)
        cls.first = control.finalize(cls.plan_path,cls.audit_path)

    @classmethod
    def _worker(cls,shard,slot):
        root = Path(shard['bundle_directory'])
        results = root/'results'
        command = [sys.executable,'-m','distributed_campaign.worker','--root','.',
                   '--expected-manifest-sha',shard['bundle_sha256'],'--output',str(results),
                   '--workers','1','--credentials',cls.meta['credentials'][slot]]
        result = subprocess.run(command,cwd=root,capture_output=True,text=True,timeout=60,
                                creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        if result.returncode:
            raise AssertionError(result.stderr)
        return results

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls,'patcher'):
            cls.patcher.stop()
        if hasattr(cls,'temporary'):
            cls.temporary.cleanup()

    def test_full_actual_control_chain_is_distinct_declared_slot_and_zero_primary(self):
        accepted = self.first['acceptance']
        self.assertEqual(accepted['actual_extra_games'],12)
        self.assertEqual(accepted['remote_full_actor_callbacks'],12*320)
        self.assertEqual(accepted['primary_games_accepted'],0)
        self.assertFalse(accepted['production_promoted'])
        self.assertEqual(accepted['qualification_replica_games_credited'],0)
        for shard in self.audit['distribution']['shards']:
            bundle = p.verify_bundle(shard['bundle_directory'],shard['bundle_sha256'])
            for creator in bundle['creators'].values():
                self.assertNotEqual(creator['physical_slot_id'],bundle['target_slot']['physical_slot_id'])

    def test_repeat_import_and_finalization_submit_zero_new_jobs(self):
        for shard in self.plan['distribution']['shards']:
            result = control.ingest_play(self.plan_path,shard['id'],self.play_results[shard['id']])
            self.assertEqual(result['imported_actual_games'],0)
        for shard in self.audit['distribution']['shards']:
            result = control.ingest_audit(self.plan_path,self.audit_path,shard['id'],self.audit_results[shard['id']])
            self.assertEqual(result['imported_full_game_audits'],0)
        with mock.patch('distributed_campaign.control.run.audit_task',side_effect=AssertionError('Repeated callback')):
            repeated = control.finalize(self.plan_path,self.audit_path)
        self.assertEqual(repeated['new_owner_canary_jobs'],0)
        self.assertEqual(repeated['acceptance'],self.first['acceptance'])

    def test_study_cannot_issue_another_original_cohort_from_a_second_output(self):
        with mock.patch('distributed_campaign.owner.build_shards',side_effect=AssertionError('Duplicate original jobs issued')):
            with self.assertRaisesRegex(ValueError,'already reserved another canonical'):
                control.prepare(self.registration_path,self.meta['registry_path'],self.directory/'duplicate',
                                ['a','b'],{})
        registry = auth.load_registry(self.meta['registry_path'])
        accepted = control._read(registry,'study-acceptance',self.registration_path.parent/'distributed_control_v2/acceptance.json')
        self.assertEqual(accepted['actual_extra_games'],12)
        self.assertEqual(accepted['primary_games_accepted'],0)

    def test_removing_peer_proof_blocks_acceptance_without_running_canaries(self):
        path = next((self.plan_path.parent/'peer_proofs').glob('*.json'))
        body = path.read_bytes()
        path.unlink()
        try:
            with mock.patch('distributed_campaign.control.run.audit_task',side_effect=AssertionError('No callbacks before coverage')):
                with self.assertRaisesRegex(ValueError,'Every original'):
                    control.finalize(self.plan_path,self.audit_path)
        finally:
            path.write_bytes(body)


if __name__ == '__main__':
    unittest.main()
