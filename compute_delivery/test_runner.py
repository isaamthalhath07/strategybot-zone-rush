"""Outer-wrapper mechanics only: mock owner admission, zero actors/matches."""
import copy
import io
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import types
import unittest
import warnings
from unittest import mock
import zipfile

from compute_delivery import builder,runner
from distributed_campaign import protocol,roles


ROOT = Path(__file__).resolve().parents[1]


class RunnerMechanicsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='cd-',dir=ROOT/'.cache')
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.plan_path = self.base/'SYNTHETIC_OWNER_GATE_NOT_A_REAL_PLAN.json'
        self.plan_path.write_bytes(b'MOCK ADMISSION ONLY; ZERO ACTORS\n')

    def fixture(self,kind='play'):
        source = self.base/('input-'+kind)
        source.mkdir()
        body = b'# SYNTHETIC COMMENT ONLY; NO POLICY OR ACTOR EXECUTION\n'
        path = source/'distributed_campaign/worker.py'
        path.parent.mkdir()
        path.write_bytes(body)
        runtime = runner.runtime_metadata()
        runtime.update(actor_backend='CPython CPU',cuda_used_by_policy=False,logical_cores=8)
        bundle = dict(format=protocol.FORMAT,role='extra_control_assignment',work_role=kind,
                      campaign_id='a'*64,generation=0,shard_id=('b' if kind=='play' else 'c')*64,
                      source_registration_sha256='d'*64,target_slot=dict(slot_id='UNIT-ONLY',physical_slot_id='LOCAL-LOGICAL-UNIT'),
                      approved_runtime=runtime,worker_primary_credit=0,cuda_used_by_policy=False,bmcts_audits=0,
                      files={'distributed_campaign/worker.py':runner.sha(body)},
                      fixtures=[dict(id='e'*64,candidate=runner.sha(body))],sources={},candidates=[],authentication={'MOCK_ONLY':True})
        if kind=='audit':
            bundle['input_rows']={'e'*64:dict(fixture='e'*64)}
            bundle['creators']={'e'*64:dict(slot_id='OTHER-UNIT',physical_slot_id='OTHER-LOGICAL-UNIT')}
        manifest = runner.canonical(bundle)+b'\n'
        (source/'bundle.json').write_bytes(manifest)
        (source/'bundle.sha256').write_bytes((runner.sha(manifest)+'\n').encode())
        (source/'RUN_INSTRUCTIONS.txt').write_bytes(b'SYNTHETIC WRAPPER CHECK ONLY\n')
        inner = source.with_suffix('.zip')
        with zipfile.ZipFile(inner,'w',compression=zipfile.ZIP_DEFLATED) as zipped:
            for path in source.rglob('*'):
                if path.is_file():zipped.write(path,path.relative_to(source).as_posix())
        shard = dict(id=bundle['shard_id'],bundle_directory=str(source),bundle_sha256=runner.sha(manifest),
                     archive=str(inner),archive_sha256=runner.sha(inner.read_bytes()),fixture_ids=['e'*64],helper_label='UNIT-ONLY')
        plan = dict(role=bundle['role'],campaign_id=bundle['campaign_id'],generation=0,
                    source_registration_sha256=bundle['source_registration_sha256'],distribution=dict(shards=[shard]))
        output = self.base/('job % ! spaces '+kind)
        # Mock ONLY the owner admission boundary. No registry, key, gold case,
        # real plan or frozen worker executor is opened/created by these tests.
        if kind=='play':
            result = (plan,object(),{},self.base,{shard['id']:bundle})
            with mock.patch('distributed_campaign.control._load',return_value=result):
                receipt = builder.build(self.plan_path,shard['id'],output)
        else:
            audit = self.base/'MOCK_AUDIT_GATE_NOT_A_REAL_PLAN.json'
            audit.write_bytes(b'MOCK AUDIT ADMISSION; ZERO ACTORS\n')
            result = (plan,object(),{},self.base,plan,{}, {shard['id']:bundle})
            with mock.patch('distributed_campaign.control._audit_plan',return_value=result):
                receipt = builder.build(self.plan_path,shard['id'],output,audit)
        return output,runner.load_config(output),bundle,receipt

    def test_runtime_and_context_tamper_stop_before_credential_or_process(self):
        output,config,bundle,_ = self.fixture()
        for key,value in (('version','3.12.0'),('full_version','DIFFERENT PATCH BUILD'),('platform','OTHER WINDOWS'),
                          ('executable_sha256','0'*64),('implementation','PyPy')):
            changed = dict(config['approved_runtime'],**{key:value})
            with self.subTest(key=key),self.assertRaises(ValueError):
                runner.verify_runtime(config,changed)
        config['approved_runtime']['full_version']='CHANGED'
        config['approved_runtime_fingerprint']=runner.fingerprint(config['approved_runtime'])
        (output/'delivery.json').write_bytes(runner.canonical(config))
        # Both outer metadata and its runtime digest changed: source bundle
        # context still rejects the substitution before private configuration.
        with (mock.patch.object(runner,'_credential',side_effect=AssertionError('NO KEY ACCESS')),
              mock.patch.object(runner,'stream_worker',side_effect=AssertionError('NO ACTORS'))):
            with self.assertRaises(ValueError):runner.run(output)

    def test_source_and_role_tamper_stop_before_private_configuration(self):
        output,config,bundle,_ = self.fixture()
        worker,_ = runner.verify_package(output)
        path = worker/'distributed_campaign/worker.py'
        path.write_bytes(path.read_bytes()+b'# changed\n')
        with mock.patch.object(runner,'_credential',side_effect=AssertionError('NO KEY ACCESS')):
            with self.assertRaises(ValueError):runner.run(output)
        for key,value in (('work_role','audit'),('campaign_id','f'*64),('slot',dict(slot_id='WRONG',physical_slot_id='WRONG'))):
            changed = copy.deepcopy(config); changed[key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):runner.check_bundle_context(bundle,changed)

    def test_wrong_fresh_cached_or_assignment_credential_stops_before_work(self):
        output,config,bundle,_=self.fixture()
        worker,_=runner.verify_package(output)
        wrong=self.base/'SYNTHETIC_WRONG_ID_NOT_A_PRIVATE_KEY.json'
        wrong.write_bytes(runner.canonical(dict(slot_id='OTHER-UNIT',physical_slot_id='OTHER-UNIT')))
        fake_auth=types.SimpleNamespace(import_credentials=mock.Mock(side_effect=AssertionError('Wrong identity copied')),
                load_credentials=lambda path:object(),public_identity=lambda obj:dict(slot_id='OTHER-UNIT',physical_slot_id='OTHER-UNIT'))
        modules=(fake_auth,protocol,roles)
        local=self.base/'UNIT_ONLY_NOT_REAL_LOCALAPPDATA'
        with (mock.patch.dict(os.environ,{'LOCALAPPDATA':str(local)}),
              mock.patch.object(runner,'_load_worker_modules',return_value=modules),
              mock.patch.object(runner,'_select_credential',return_value=wrong)):
            with self.assertRaisesRegex(ValueError,'another helper'):
                runner._credential(config,worker,event=lambda text:None)
            cached=local/'ZoneRushPrivate'/('architecture-v2-'+config['slot']['slot_id'])/'credential.json'
            cached.parent.mkdir(parents=True);cached.write_bytes(b'SYNTHETIC CACHED MARKER; NOT A KEY')
            with self.assertRaisesRegex(ValueError,'another helper'):
                runner._credential(config,worker,event=lambda text:None)
        invalid_roles=types.SimpleNamespace(authenticate_assignment=mock.Mock(side_effect=ValueError('MOCK assignment MAC rejected')))
        with (mock.patch.object(runner,'_credential',return_value=(wrong,object(),(fake_auth,protocol,invalid_roles))),
              mock.patch.object(runner,'stream_worker',side_effect=AssertionError('No actor process may start'))):
            with self.assertRaisesRegex(ValueError,'assignment MAC rejected'):
                runner.run(output,event=lambda text:None)
        self.assertFalse((output/'job_settings.json').exists())

    def test_worker_count_and_context_are_persistent_across_cpu_changes(self):
        output,config,_,_ = self.fixture()
        self.assertEqual(runner.choose_workers(output,config,cpu_count=16),4)
        before = (output/'job_settings.json').read_bytes()
        self.assertEqual(runner.choose_workers(output,config,cpu_count=2),4)
        self.assertEqual(before,(output/'job_settings.json').read_bytes())
        with self.assertRaises(ValueError):runner.choose_workers(output,config,requested=2)
        changed = dict(config,shard_id='0'*64)
        with self.assertRaises(ValueError):runner.choose_workers(output,changed)
        (output/'job_settings.json').unlink()
        (output/'results').mkdir()
        (output/'results/header.json').write_bytes(b'{}')
        with self.assertRaises(ValueError):runner.choose_workers(output,config,cpu_count=2)

    def test_progress_is_streamed_before_process_end_and_python_environment_is_clean(self):
        events,seen = [],{}
        class Child:
            stdout = iter(['Completed full80-turn matches:50/6552; owner acceptance pending\n','Completed full80-turn matches:100/6552; owner acceptance pending\n'])
            def wait(self):
                if len(events)!=2:raise AssertionError('Progress was buffered until completion')
                return 0
        def popen(command,**kwargs):
            seen.update(kwargs)
            return Child()
        code = runner.stream_worker(['NOT EXECUTED'],self.base,events.append,
                environment={'PYTHONPATH':'UNTRUSTED','PYTHONHOME':'BAD','PYTHONINSPECT':'1','PYTHONSAFEPATH':'1'},popen=popen)
        self.assertEqual(code,0)
        self.assertFalse(any(key.startswith('PYTHON') for key in seen['env']))
        self.assertIn('50/6552',events[0])
        audits=[]
        runner._progress('Completed independent full-game audits:50/6553; owner acceptance pending','audit',audits.append)
        self.assertIn('new games:0',audits[0])
        self.assertNotIn('original full matches',audits[0])

    def test_extract_rejects_windows_alias_traversal_duplicates_links_and_zip_bombs(self):
        output,config,_,_ = self.fixture()
        archive = output/'worker_payload.zip'
        original = archive.read_bytes()
        for name in ('../outside.py','/absolute.py','a\\b.py','CON.py','a./b.py','a /b.py','a//b.py','bundle.json','BUNDLE.JSON'):
            archive.write_bytes(original)
            with warnings.catch_warnings():
                warnings.simplefilter('ignore',UserWarning)
                with zipfile.ZipFile(archive,'a') as zipped:zipped.writestr(name,b'# invalid\n')
            changed = dict(config,inner_archive_sha256=runner.sha(archive.read_bytes()))
            with self.subTest(name=name),self.assertRaises(ValueError):runner.inspect_payload(archive,changed)
        archive.write_bytes(original)
        with zipfile.ZipFile(archive,'a') as zipped:
            link=zipfile.ZipInfo('linked.py'); link.create_system=3; link.external_attr=(stat.S_IFLNK|0o777)<<16
            zipped.writestr(link,b'../outside')
        with self.assertRaises(ValueError):runner.inspect_payload(archive,dict(config,inner_archive_sha256=runner.sha(archive.read_bytes())))
        archive.write_bytes(original)
        with mock.patch.object(runner,'MAX_EXPANDED_BYTES',1):
            with self.assertRaises(ValueError):runner.inspect_payload(archive,config)

    def test_cmd_powershell_preflight_handles_spaces_percent_bang_and_failure_codes(self):
        if os.name!='nt':self.skipTest('Native Windows command path control')
        output,config,_,_=self.fixture()
        environment=dict(os.environ,ZONE_RUSH_CHECK_PACKAGE_ONLY='1',PYTHONPATH=str(self.base/'UNTRUSTED'),PYTHONHOME=str(self.base/'NO_RUNTIME'))
        checked=subprocess.run(['cmd.exe','/D','/V:ON','/C','START_HERE.cmd'],cwd=output,env=environment,capture_output=True,text=True,timeout=30)
        self.assertEqual(checked.returncode,0,checked.stdout+checked.stderr)
        report=json.loads(next(line for line in checked.stdout.splitlines() if line.startswith('{')))
        self.assertEqual((report['actor_calls'],report['new_games'],report['primary_credit']),(0,0,0))
        changed=output/'worker/distributed_campaign/worker.py'
        changed.write_bytes(changed.read_bytes()+b'# deliberate corruption\n')
        stopped=subprocess.run(['cmd.exe','/D','/V:ON','/C','START_HERE.cmd'],cwd=output,env=environment,capture_output=True,text=True,timeout=30)
        self.assertNotEqual(stopped.returncode,0)

    def test_results_export_includes_only_three_files_and_no_extra_game_credit(self):
        output,config,bundle,_=self.fixture('audit')
        result=output/'results'; result.mkdir()
        runtime=copy.deepcopy(config['approved_runtime'])
        header=dict(format=protocol.FORMAT,role=config['role'],campaign_id=config['campaign_id'],generation=config['generation'],
                    slot=config['slot'],runtime=runtime,work_role='audit',shard_id=config['shard_id'],bundle_sha256=config['bundle_sha256'],
                    worker_primary_credit=0,bmcts_audits=0,workers=4)
        header['authentication']={'payload':roles.header_payload(header)}
        record=dict(fixture=bundle['fixtures'][0]['id'],candidate='f'*64,SYNTHETIC_EXPORT_ONLY=True)
        entry=dict(record=record,authentication={'payload':roles.result_payload(bundle,header,record)})
        lines=runner.canonical(entry)+b'\n'
        progress=dict(shard_id=config['shard_id'],bundle_sha256=config['bundle_sha256'],work_role='audit',complete=True,
                      expected_tasks=1,bmcts_audits=0,completed_tasks=1,completed_games=0,completed_full_game_audits=1,worker_primary_credit=0,
                      cuda_used_by_policy=False,records_sha256=runner.sha(lines))
        (result/'header.json').write_bytes(runner.canonical(header))
        (result/'records.jsonl').write_bytes(lines)
        (result/'progress.json').write_bytes(runner.canonical(progress))
        (result/'PRIVATE_CREDENTIAL.json').write_bytes(b'FAKE SECRET MARKER DO NOT RETURN')
        (result/'source.py').write_bytes(b'NOT RETURNED')
        # Fake HMAC boundary for packaging mechanics only. These records have no
        # actual actor proof and are NOT presented to any real owner admission.
        fake_auth=types.SimpleNamespace(verify=lambda credential,purpose,envelope,expected_slot=None:envelope['payload'])
        returned=runner._export_results(output,config,bundle,object(),(fake_auth,protocol,roles))
        with zipfile.ZipFile(returned) as zipped:
            self.assertEqual(set(zipped.namelist()),set(runner.RETURN_FILES))
            self.assertTrue(all(b'FAKE SECRET MARKER' not in zipped.read(name) for name in zipped.namelist()))
        progress['completed_games']=1
        (result/'progress.json').write_bytes(runner.canonical(progress))
        with self.assertRaises(ValueError):runner._export_results(output,config,bundle,object(),(fake_auth,protocol,roles))


if __name__=='__main__':unittest.main()
