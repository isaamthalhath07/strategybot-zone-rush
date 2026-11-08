"""Independent outer-delivery tests using FAKE admission; ZERO real actors/jobs.

No canonical controller, qualification record, owner registry or credential is
opened. Every owner-admission boundary is explicitly mocked around synthetic
comments-only package files. These are wrapper tests, not authentication proof.
"""
from contextlib import ExitStack, contextmanager
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import stat
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import zipfile
import warnings

from distributed_campaign import protocol as protocol
from compute_delivery import builder, runner


ROOT = Path(__file__).resolve().parents[1]


def sha(body):
    return hashlib.sha256(body).hexdigest()


def canonical(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()


class IndependentDeliveryTests(unittest.TestCase):
    def setUp(self):
        cache=ROOT/'.cache'
        cache.mkdir(exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(prefix='delivery-INDEPENDENT-UNIT-',dir=cache)
        self.addCleanup(self.temp.cleanup)
        self.folder=Path(self.temp.name)
        self.plan_path=self.folder/'SYNTHETIC-NOT-A-PLAN.json'
        self.audit_path=self.folder/'SYNTHETIC-NOT-AN-AUDIT.json'
        self.plan_path.write_bytes(b'SYNTHETIC UNIT ADMISSION; NO REAL PLAN\n')
        self.audit_path.write_bytes(b'SYNTHETIC UNIT AUDIT; NO REAL PLAN\n')
        self.identity=dict(slot_id='UNIT-HELPER-A',physical_slot_id='UNIT-NOT-A-PHYSICAL-LAPTOP')
        self.runtime=dict(implementation='CPython',version='3.12.10',full_version='SYNTHETIC UNIT RUNTIME',
                          executable_sha256='f'*64,platform='SYNTHETIC UNIT WINDOWS',logical_cores=8,
                          actor_backend='CPython CPU',cuda_used_by_policy=False)

    def shard(self,work_role='play'):
        directory=self.folder/('synthetic-'+work_role)
        directory.mkdir()
        source=b'# UNIT TEST COMMENT ONLY; DO NOT EXECUTE ACTORS\n'
        relative='distributed_campaign/worker.py'
        (directory/'distributed_campaign').mkdir()
        (directory/relative).write_bytes(source)
        fixture=dict(id='1'*64,candidate=sha(source))
        bundle=dict(format=protocol.FORMAT,role='extra_control_assignment',work_role=work_role,
                    campaign_id='2'*64,generation=0,source_registration_sha256='3'*64,
                    shard_id=('4' if work_role=='play' else '5')*64,helper_label=self.identity['slot_id'],
                    owner_runtime=self.runtime,approved_runtime=self.runtime,target_slot=self.identity,
                    worker_primary_credit=0,bmcts_audits=0,cuda_used_by_policy=False,
                    files={relative:sha(source)},fixtures=[fixture],sources={},candidates=[],
                    authentication=dict(unit_test_only=True))
        if work_role=='audit':
            bundle['input_rows']={fixture['id']:dict(fixture=fixture['id'])}
            bundle['creators']={fixture['id']:dict(slot_id='UNIT-ORIGIN',physical_slot_id='UNIT-OTHER-PHYSICAL')}
        body=canonical(bundle)+b'\n'
        (directory/'bundle.json').write_bytes(body)
        (directory/'bundle.sha256').write_text(sha(body)+'\n',encoding='ascii')
        (directory/'RUN_INSTRUCTIONS.txt').write_text('SYNTHETIC UNIT; ZERO GAME CREDIT\n',encoding='ascii')
        archive=directory.with_suffix('.zip')
        with zipfile.ZipFile(archive,'x',compression=zipfile.ZIP_DEFLATED) as out:
            for path in sorted(directory.rglob('*')):
                if path.is_file(): out.write(path,path.relative_to(directory).as_posix())
        shard=dict(id=bundle['shard_id'],bundle_directory=str(directory),bundle_sha256=sha(body),
                   archive=str(archive),archive_sha256=sha(archive.read_bytes()),helper_label=self.identity['slot_id'],
                   fixture_ids=[fixture['id']],games=1)
        return shard,bundle

    @contextmanager
    def admitted(self,shard,bundle,*,audit=False):
        # Deliberately fake isolated unit authority. Authentic real plan/gold
        # creation and all actual worker/actor paths are prohibited here.
        plan=dict(role='extra_control_assignment',campaign_id=bundle['campaign_id'],generation=0,
                  source_registration_sha256=bundle['source_registration_sha256'],
                  primary_games_accepted=0,bmcts_audits=0,production_promotion=False,
                  distribution=dict(shards=[] if audit else [shard]),unit_test_only=True)
        registration=dict(campaign_id=bundle['campaign_id'],generation=0,fixtures=bundle['fixtures'])
        load=(plan,object(),registration,self.folder,{} if audit else {shard['id']:bundle})
        audit_plan=dict(campaign_id=bundle['campaign_id'],generation=0,
                        distribution=dict(shards=[shard]),primary_games_accepted=0,
                        parent_plan_sha256=sha(self.plan_path.read_bytes()),unit_test_only=True)
        full=(*load[:4],audit_plan,{}, {shard['id']:bundle})
        with ExitStack() as stack:
            selected=stack.enter_context(patch('distributed_campaign.control._audit_plan' if audit else
                                              'distributed_campaign.control._load',return_value=full if audit else load))
            stack.enter_context(patch('distributed_campaign.control.prepare',side_effect=AssertionError('NO REAL PLAN CREATION')))
            stack.enter_context(patch('distributed_campaign.control.prepare_audits',side_effect=AssertionError('NO REAL AUDIT CREATION')))
            stack.enter_context(patch('distributed_campaign.worker.execute',side_effect=AssertionError('NO ACTORS OR JOBS')))
            yield selected

    def test_owner_admission_rejection_prevents_any_delivery(self):
        output=self.folder/'rejected'
        with patch('distributed_campaign.control._load',side_effect=ValueError('UNIT_AUTH_REJECTED')):
            with self.assertRaisesRegex(ValueError,'UNIT_AUTH_REJECTED'):
                builder.build(self.plan_path,'4'*64,output)
        self.assertFalse(output.exists())

    def test_play_and_audit_use_their_distinct_authenticated_admission_paths(self):
        for kind in ('play','audit'):
            shard,bundle=self.shard(kind)
            output=self.folder/('delivery-'+kind)
            original=Path(shard['archive']).read_bytes()
            with self.admitted(shard,bundle,audit=kind=='audit') as admission:
                builder.build(self.plan_path,shard['id'],output,
                              audit_plan_path=self.audit_path if kind=='audit' else None)
            admission.assert_called()
            self.assertEqual(Path(shard['archive']).read_bytes(),original)
            config=json.loads((output/'delivery.json').read_bytes())
            self.assertEqual(config['work_role'],kind)
            self.assertEqual(config['role'],'extra_control_assignment')
            self.assertEqual(config['shard_id'],shard['id'])
            worker,packaged=runner.verify_package(output)
            self.assertEqual(packaged['work_role'],kind)
            self.assertEqual(packaged['fixtures'],bundle['fixtures'])
            self.assertEqual((worker/'bundle.json').read_bytes(),(Path(shard['bundle_directory'])/'bundle.json').read_bytes())

    def test_wrong_or_foreign_shard_cannot_be_packaged(self):
        shard,bundle=self.shard()
        output=self.folder/'foreign'
        with self.admitted(shard,bundle):
            with self.assertRaises((ValueError,KeyError)):
                builder.build(self.plan_path,'0'*64,output)
        self.assertFalse(output.exists())

    def test_authenticated_archive_byte_drift_cannot_be_copied(self):
        shard,bundle=self.shard()
        Path(shard['archive']).write_bytes(Path(shard['archive']).read_bytes()+b'CHANGED')
        output=self.folder/'changed-archive'
        with self.admitted(shard,bundle):
            with self.assertRaises(ValueError): builder.build(self.plan_path,shard['id'],output)
        self.assertFalse(output.exists())

    def test_delivery_does_not_sweep_owner_secrets_results_or_environment(self):
        shard,bundle=self.shard()
        marker=b'UNIT_PRIVATE_MARKER_NEVER_TRANSFER'
        for relative in ('private/owner.key','private/credential.json','results/records.jsonl','.venv/python.exe'):
            path=self.folder/relative
            path.parent.mkdir(parents=True,exist_ok=True)
            path.write_bytes(marker)
        output=self.folder/'isolated-delivery'
        with self.admitted(shard,bundle): builder.build(self.plan_path,shard['id'],output)
        for path in output.rglob('*'):
            if path.is_file(): self.assertNotIn(marker,path.read_bytes(),str(path.relative_to(output)))

    def test_extra_inner_zip_entry_cannot_smuggle_a_file_even_with_new_archive_hash(self):
        shard,bundle=self.shard()
        with zipfile.ZipFile(shard['archive'],'a') as out:
            out.writestr('private/credential.json',b'UNIT_SECRET_NOT_A_REAL_KEY')
        shard['archive_sha256']=sha(Path(shard['archive']).read_bytes())
        output=self.folder/'extra-entry'
        with self.admitted(shard,bundle):
            with self.assertRaises(ValueError): builder.build(self.plan_path,shard['id'],output)
        self.assertFalse(output.exists())

    def built(self,kind='play'):
        shard,bundle=self.shard(kind)
        output=self.folder/('delivery-'+kind)
        with self.admitted(shard,bundle,audit=kind=='audit'):
            builder.build(self.plan_path,shard['id'],output,
                          audit_plan_path=self.audit_path if kind=='audit' else None)
        return output,json.loads((output/'delivery.json').read_bytes()),bundle

    def unit_results(self,output,config,bundle,header_change=None,progress_change=None):
        """Fake local signed records; never mint/read a real helper capability."""
        directory=output/'results'
        directory.mkdir(exist_ok=True)
        header=dict(format=protocol.FORMAT,bundle_sha256=config['bundle_sha256'],slot=config['slot'],
                    work_role=config['work_role'],role=config['role'],campaign_id=config['campaign_id'],
                    generation=config['generation'],shard_id=config['shard_id'],runtime=config['approved_runtime'],
                    workers=2,worker_primary_credit=0,bmcts_audits=0)
        if header_change: header.update(header_change)
        def header_payload(value):
            return dict(unit_header_sha256=sha(canonical({k:v for k,v in value.items() if k!='authentication'})))
        def record_payload(packaged,head,record):
            return dict(unit_bundle=packaged['shard_id'],unit_header=header_payload(head),unit_record=sha(canonical(record)))
        header['authentication']={'unit_authenticated_payload':header_payload(header)}
        record=dict(fixture=bundle['fixtures'][0]['id'],unit_test_only=True)
        entry=dict(record=record,authentication={'unit_authenticated_payload':record_payload(bundle,header,record)})
        body=canonical(entry)+b'\n'
        progress=dict(format=protocol.FORMAT,bundle_sha256=config['bundle_sha256'],shard_id=config['shard_id'],
                      work_role=config['work_role'],expected_tasks=1,completed_tasks=1,complete=True,
                      completed_games=1 if config['work_role']=='play' else 0,
                      completed_full_game_audits=1 if config['work_role']=='audit' else 0,
                      worker_primary_credit=0,bmcts_audits=0,cuda_used_by_policy=False,records_sha256=sha(body))
        if progress_change: progress.update(progress_change)
        for name,value in (('header.json',canonical(header)+b'\n'),('records.jsonl',body),('progress.json',canonical(progress)+b'\n')):
            (directory/name).write_bytes(value)
        fake_auth=SimpleNamespace(verify=lambda credential,purpose,envelope,expected_slot:envelope['unit_authenticated_payload'])
        fake_roles=SimpleNamespace(header_payload=header_payload,result_payload=record_payload)
        return object(),(fake_auth,protocol,fake_roles)

    def test_exact_runtime_fingerprint_never_falls_back_to_similar_version(self):
        output,config,bundle=self.built()
        self.assertEqual(runner.verify_runtime(config,self.runtime),self.runtime)
        for alteration in ({'version':'3.12.11'},{'executable_sha256':'0'*64},{'platform':'OTHER_OS_BUILD'},
                           {'full_version':'SIMILAR_VERSION_DIFFERENT_BUILD'},{'implementation':'PyPy'}):
            with self.subTest(alteration=alteration),self.assertRaises(ValueError):
                runner.verify_runtime(config,dict(self.runtime,**alteration))

    def test_results_only_export_never_includes_credential_or_environment(self):
        output,config,bundle=self.built()
        credential,modules=self.unit_results(output,config,bundle)
        for name in ('credential.json','private/owner.key','.venv/python.exe','unrelated.py'):
            target=output/'results'/name
            target.parent.mkdir(parents=True,exist_ok=True)
            target.write_bytes(b'UNIT_PRIVATE_MARKER_MUST_NOT_RETURN')
        returned=runner._export_results(output,config,bundle,credential,modules)
        with zipfile.ZipFile(returned) as packed:
            self.assertEqual(set(packed.namelist()),{'header.json','records.jsonl','progress.json'})
            for name in packed.namelist(): self.assertNotIn(b'UNIT_PRIVATE_MARKER_MUST_NOT_RETURN',packed.read(name))

    def test_unrelated_existing_return_file_is_never_overwritten(self):
        output,config,bundle=self.built()
        credential,modules=self.unit_results(output,config,bundle)
        target=runner._export_results(output,config,bundle,credential,modules)
        marker=b'UNRELATED EXISTING FILE MUST SURVIVE\n'
        target.write_bytes(marker)
        with self.assertRaises((ValueError,FileExistsError,zipfile.BadZipFile)):
            runner._export_results(output,config,bundle,credential,modules)
        self.assertEqual(target.read_bytes(),marker)

    def test_linked_return_and_lock_paths_cannot_modify_an_unrelated_sentinel(self):
        output,config,bundle=self.built()
        credential,modules=self.unit_results(output,config,bundle)
        sentinel=self.folder/'unrelated-sentinel.txt'
        sentinel.write_bytes(b'UNCHANGED UNIT SENTINEL')
        target=runner._export_results(output,config,bundle,credential,modules)
        target.unlink()  # Remove only this synthetic test's generated archive.
        try: os.link(sentinel,target)
        except (OSError,NotImplementedError): self.skipTest('Hard-link creation unavailable in this test environment')
        with self.assertRaises(ValueError): runner._export_results(output,config,bundle,credential,modules)
        self.assertEqual(sentinel.read_bytes(),b'UNCHANGED UNIT SENTINEL')
        empty=self.folder/'empty-sentinel.txt';empty.write_bytes(b'')
        os.link(empty,output/'.delivery.lock')
        with self.assertRaises(ValueError):
            with runner.delivery_lease(output): pass
        self.assertEqual(empty.read_bytes(),b'')

    def test_wrong_signed_header_or_progress_context_cannot_be_exported(self):
        output,config,bundle=self.built()
        for alteration in ({'campaign_id':'FOREIGN'},{'generation':3},{'role':'primary_assignment'},
                           {'worker_primary_credit':1},{'bmcts_audits':1}):
            credential,modules=self.unit_results(output,config,bundle,header_change=alteration)
            with self.subTest(header=alteration),self.assertRaises(ValueError):
                runner._export_results(output,config,bundle,credential,modules)
        for alteration in ({'bundle_sha256':'0'*64},{'shard_id':'0'*64},{'work_role':'audit'},
                           {'expected_tasks':2},{'bmcts_audits':1}):
            credential,modules=self.unit_results(output,config,bundle,progress_change=alteration)
            with self.subTest(progress=alteration),self.assertRaises(ValueError):
                runner._export_results(output,config,bundle,credential,modules)

    def test_streaming_keeps_progress_live_and_scopes_python_environment_cleanup(self):
        events=[];captured={}
        process=SimpleNamespace(stdout=io.StringIO('Completed full80-turn matches:1/1; owner acceptance pending\n{"unit_summary":true}\n'),
                                wait=lambda:0)
        def fake_popen(command,**kwargs): captured.update(kwargs);return process
        environment=dict(PYTHONPATH='OTHER_CHECKOUT',PYTHONHOME='OTHER_PYTHON',PYTHONINSPECT='1',SAFE='keep')
        self.assertEqual(runner.stream_worker(['UNIT_NO_EXECUTION'],self.folder,events.append,environment,fake_popen),0)
        self.assertEqual(environment['PYTHONPATH'],'OTHER_CHECKOUT')
        self.assertEqual(captured['env'],{'SAFE':'keep'})
        self.assertTrue(any('owner acceptance pending' in line for line in events))
        self.assertFalse(any('unit_summary' in line for line in events))

    def test_stream_error_reaps_child_before_returning_an_exception(self):
        state={'finished':False}
        def wait(timeout=None): state['finished']=True;return 1
        def stop(): state['finished']=True
        process=SimpleNamespace(stdout=io.StringIO('x'*65537+'\n'),wait=wait,terminate=stop,kill=stop,
                                poll=lambda:1 if state['finished'] else None)
        with self.assertRaises(ValueError):
            runner.stream_worker(['UNIT_NO_EXECUTION'],self.folder,popen=lambda *args,**kwargs:process)
        self.assertTrue(state['finished'])

    def test_bad_zip_paths_duplicates_case_aliases_and_links_reject_before_extraction(self):
        output,config,bundle=self.built()
        original=(output/'worker_payload.zip').read_bytes()
        entries=('../escape.py','/absolute.py','C:/escape.py','data\\wrong.py','CON.txt',
                 'trailing. ','data/../alias.py','distributed_campaign/worker.py',
                 'DISTRIBUTED_CAMPAIGN/WORKER.PY','linked-file')
        for index,name in enumerate(entries):
            archive=self.folder/('malformed-%02d.zip'%index)
            archive.write_bytes(original)
            with warnings.catch_warnings():
                warnings.simplefilter('ignore',UserWarning)  # Intentional duplicate ZIP fixture.
                with zipfile.ZipFile(archive,'a') as packed:
                    info=zipfile.ZipInfo(name)
                    if name=='linked-file':
                        info.create_system=3
                        info.external_attr=(stat.S_IFLNK|0o777)<<16
                    packed.writestr(info,b'UNIT INVALID ARCHIVE ENTRY')
            changed=dict(config,inner_archive_sha256=sha(archive.read_bytes()))
            with self.subTest(name=name),self.assertRaises(ValueError):
                runner.inspect_payload(archive,changed)
        self.assertFalse((self.folder/'escape.py').exists())
        self.assertFalse((output/'worker').exists())

    def test_expansion_budget_and_local_extracted_source_tampering_fail_closed(self):
        output,config,bundle=self.built()
        with patch.object(runner,'MAX_EXPANDED_BYTES',1):
            with self.assertRaises(ValueError): runner.verify_package(output)
        self.assertFalse((output/'worker').exists())
        worker,packaged=runner.verify_package(output)
        source=worker/'distributed_campaign/worker.py'
        source.write_bytes(source.read_bytes()+b'# MODIFIED UNIT SOURCE\n')
        with self.assertRaises(ValueError): runner.verify_package(output)

    def test_qualification_cannot_be_retagged_as_a_real_play_delivery(self):
        shard,bundle=self.shard('qualify')
        output=self.folder/'not-a-play-job'
        with self.admitted(shard,bundle):
            with self.assertRaises(ValueError): builder.build(self.plan_path,shard['id'],output)
        self.assertFalse(output.exists())

    def test_runtime_metadata_cannot_be_rehashed_to_override_inner_approval(self):
        output,config,bundle=self.built()
        changed=copy.deepcopy(config)
        changed['approved_runtime']['executable_sha256']='0'*64
        changed['approved_runtime_fingerprint']=runner.fingerprint(changed['approved_runtime'])
        with self.assertRaises(ValueError): runner.verify_package(output,changed)

    def test_repeat_export_is_idempotent_and_new_progress_preserves_prior_return(self):
        output,config,bundle=self.built()
        credential,modules=self.unit_results(output,config,bundle)
        first=runner._export_results(output,config,bundle,credential,modules)
        body=first.read_bytes()
        repeated=runner._export_results(output,config,bundle,credential,modules)
        self.assertEqual(repeated,first)
        self.assertEqual(first.read_bytes(),body)
        progress=output/'results/progress.json'
        value=json.loads(progress.read_bytes())
        value['this_run_wall_s']=.125  # Harmless completed-resume metadata.
        progress.write_bytes(canonical(value)+b'\n')
        later=runner._export_results(output,config,bundle,credential,modules)
        self.assertNotEqual(later,first)
        self.assertEqual(first.read_bytes(),body)

    def staging(self):
        output,config,bundle=self.built()
        temporary=output/'.extract-independent-unit'
        temporary.mkdir()
        # Only this test's known comments-only synthetic ZIP is expanded here.
        with zipfile.ZipFile(output/'worker_payload.zip') as archive:
            for item in archive.infolist():
                path=temporary.joinpath(*item.filename.split('/'))
                path.parent.mkdir(parents=True,exist_ok=True)
                path.write_bytes(archive.read(item.filename))
        return output,temporary,output/'worker',bundle,config

    @staticmethod
    def windows_error(number):
        error=PermissionError('SYNTHETIC WINDOWS FILE LOCK')
        error.winerror=number
        return error

    def transient_promotion(self,number):
        root,staging,worker,bundle,config=self.staging()
        attempts=[];delays=[]
        def interrupted_rename(source,destination):
            attempts.append((Path(source),Path(destination)))
            if len(attempts)==1: raise self.windows_error(number)
            # Real native publication is used after the injected first failure.
            os.rename(source,destination)
        def pause(delay):
            delays.append(delay)
            time.sleep(delay)
        runner._promote_staging(root,staging,worker,bundle,config,platform_name='nt',
                                rename=interrupted_rename,sleep=pause)
        self.assertGreaterEqual(len(attempts),2)
        self.assertLessEqual(len(attempts),16)
        self.assertTrue(worker.is_dir())
        self.assertFalse(staging.exists())
        self.assertEqual((worker/'bundle.json').read_bytes(),canonical(bundle)+b'\n')
        self.assertTrue(delays)
        self.assertLessEqual(sum(delays),30)

    def test_extract_access_denied_5_is_retried_without_changing_source(self):
        self.transient_promotion(5)

    def test_extract_sharing_violation_32_is_retried_without_changing_source(self):
        self.transient_promotion(32)

    def test_extract_lock_violation_33_is_retried_without_changing_source(self):
        self.transient_promotion(33)

    def test_extract_retry_refuses_staging_source_tamper_before_second_attempt(self):
        root,staging,worker,bundle,config=self.staging()
        attempts=[]
        def blocked(source,destination):
            attempts.append(1)
            raise self.windows_error(32)
        def tamper(delay):
            code=staging/'distributed_campaign/worker.py'
            code.write_bytes(code.read_bytes()+b'# MODIFIED DURING UNIT RETRY\n')
        with self.assertRaises(ValueError):
            runner._promote_staging(root,staging,worker,bundle,config,platform_name='nt',rename=blocked,sleep=tamper)
        self.assertEqual(len(attempts),1)
        self.assertFalse(worker.exists())
        self.assertTrue(staging.exists())

    def test_extract_retry_never_overwrites_a_destination_that_appears(self):
        root,staging,worker,bundle,config=self.staging()
        attempts=[]
        def blocked(source,destination):
            attempts.append(1)
            raise self.windows_error(5)
        def concurrent_destination(delay):
            worker.mkdir()
            (worker/'sentinel.txt').write_bytes(b'EXISTING CONCURRENT DIRECTORY')
        with self.assertRaises((ValueError,FileExistsError)):
            runner._promote_staging(root,staging,worker,bundle,config,platform_name='nt',
                                    rename=blocked,sleep=concurrent_destination)
        self.assertEqual(len(attempts),1)
        self.assertEqual((worker/'sentinel.txt').read_bytes(),b'EXISTING CONCURRENT DIRECTORY')
        self.assertTrue(staging.exists())

    def test_extract_permanent_lock_has_bounded_retries_and_preserves_evidence(self):
        root,staging,worker,bundle,config=self.staging()
        attempts=[];delays=[]
        original=(staging/'bundle.json').read_bytes()
        def locked(source,destination):
            attempts.append(1)
            raise self.windows_error(5)
        with self.assertRaises((OSError,ValueError)):
            runner._promote_staging(root,staging,worker,bundle,config,platform_name='nt',rename=locked,sleep=delays.append)
        self.assertGreater(len(attempts),1)
        self.assertLessEqual(len(attempts),16)
        self.assertEqual(len(delays),len(attempts)-1)
        self.assertLessEqual(sum(delays),30)
        self.assertFalse(worker.exists())
        self.assertEqual((staging/'bundle.json').read_bytes(),original)

    def test_extract_unrelated_error_is_not_hidden_behind_windows_retries(self):
        root,staging,worker,bundle,config=self.staging()
        attempts=[];delays=[]
        def unrelated(source,destination):
            attempts.append(1)
            raise self.windows_error(112)  # Disk full is not a transient sharing lock.
        with self.assertRaises(OSError):
            runner._promote_staging(root,staging,worker,bundle,config,platform_name='nt',rename=unrelated,sleep=delays.append)
        self.assertEqual(len(attempts),1)
        self.assertFalse(delays)
        self.assertTrue(staging.exists())
        self.assertFalse(worker.exists())


if __name__=='__main__': unittest.main()
