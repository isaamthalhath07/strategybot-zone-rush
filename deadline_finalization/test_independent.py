"""Independent synthetic cache faults; no real authority, keys, games or GPU.

Only NEW-module authority-type/full-validation/canonical-stage hooks are mocked.
Frozen controller globals and all original execution code remain untouched.
"""
import copy
import hashlib
import hmac
import json
import os
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import patch

from deadline_finalization import cache as c


class SyntheticMAC:
    def __init__(self,campaign): self.campaign=campaign
    @property
    def manifest_sha256(self): return c.sha((self.campaign/'manifest.json').read_bytes())
    def target(self,path):
        path=Path(path)
        return path if path.is_absolute() else self.campaign/path
    def tag(self,scope,payload):
        return hmac.new(b'INDEPENDENT-SYNTHETIC-NOT-A-REAL-OWNER-KEY',
            c.canonical([str(self.campaign),scope,payload]),hashlib.sha256).hexdigest()
    def seal(self,scope,payload,path):
        path=self.target(path);path.parent.mkdir(parents=True,exist_ok=True)
        envelope=dict(scope=scope,payload=copy.deepcopy(payload),mac=self.tag(scope,payload))
        with path.open('xb') as stream: stream.write(c.canonical(envelope)+b'\n')
        return envelope
    def read(self,scope,path):
        envelope=c._read(self.target(path))
        if envelope['scope']!=scope or not hmac.compare_digest(envelope['mac'],self.tag(scope,envelope['payload'])):
            raise ValueError('Independent SYNTHETIC MAC mismatch')
        return copy.deepcopy(envelope['payload'])


def sealed(path,value):
    body=c.canonical(value)+b'\n';path.write_bytes(body)
    path.with_suffix('.sha256').write_bytes((c.sha(body)+'\n').encode())


class IndependentCacheTests(unittest.TestCase):
    def setUp(self):
        parent=c.ROOT/'.cache'/'independent-finalization-synthetic-tests'
        parent.mkdir(parents=True,exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(prefix='SYNTHETIC-NO-GAMES-',dir=parent)
        self.addCleanup(self.temp.cleanup)
        self.campaign=Path(self.temp.name);self.authority=SyntheticMAC(self.campaign)
        self.configuration=dict(batch_size=128,workers=8,audit_workers=4)
        self.manifest=dict(source_sha256=c.frozen.source_pins(),execution_configuration=self.configuration,
                           catalog_sha256=c.frozen.design.CATALOG_SHA256)
        sealed(self.campaign/'manifest.json',self.manifest)
        self.stage=self.campaign/'train_000';self.stage.mkdir()
        (self.stage/'candidates').mkdir();self.execution=self.stage/'execution';self.execution.mkdir()
        (self.execution/'batch_00000').mkdir();(self.execution/'.execution_claim').mkdir()
        body=b'SYNTHETIC-NOT-AN-ACTOR';self.candidate=self.stage/'candidates'/(c.sha(body)+'.py')
        self.candidate.write_bytes(body)
        self.registration=dict(phase='train',generation=0,candidates=[dict(path=str(self.candidate),sha256=c.sha(body))],
            guards={str(c.ROOT/k):v for k,v in self.manifest['source_sha256'].items()},sources=c.rival_sources())
        sealed(self.stage/'registration.json',self.registration)
        self.authority.seal('registration',{'SYNTHETIC':True},self.stage/'registration_receipt.json')
        self.authority.seal('start',{'SYNTHETIC':True},self.stage/'started.json')
        self.proof=self.execution/'batch_00000'/'turns.jsonl';self.proof.write_bytes(b'INDEPENDENT-SYNTHETIC-PROOF\n')
        (self.execution/'originals.jsonl').write_bytes(b'SYNTHETIC-ORIGINAL\n')
        (self.execution/'audits.jsonl').write_bytes(b'SYNTHETIC-AUDIT\n')
        self.summary=dict(originals_sha256=c.sha((self.execution/'originals.jsonl').read_bytes()),
            audits_sha256=c.sha((self.execution/'audits.jsonl').read_bytes()),
            wall_before_final_publication_s=1.0,original_callbacks=320)
        self.aggregate=dict(games=1,ranking=[])
        self.accepted=dict(aggregate=self.aggregate,registration_sha256=c.sha((self.stage/'registration.json').read_bytes()),
            originals_sha256=self.summary['originals_sha256'],audits_sha256=self.summary['audits_sha256'])
        self.authority.seal('acceptance',self.accepted,self.stage/'accepted.json')
        sealed(self.execution/'summary.json',self.summary)
        sealed(self.execution/'execution_started.json',dict(cpu_runtime=c._environment(),**self.configuration))
        # Production defaults reject this object. Explicit new-module-only test
        # hook permits synthetic certificates without touching a real authority.
        self.type_guard=patch.object(c,'_check_authority',return_value=None)
        self.type_guard.start();self.addCleanup(self.type_guard.stop)
        c.publish_amendment(self.campaign,self.authority)
        self.cache=c.IntegrityCache(self.campaign,self.authority)

    def certify(self):
        with patch.object(c,'_canonical_stage_check') as canonical,patch.object(c,'_full_check',
                return_value=(self.summary,self.aggregate,self.accepted)) as full:
            result=self.cache.create('train_000')
        canonical.assert_called_once();full.assert_called_once()
        return result

    def replace_certificate(self,payload):
        path=self.cache.folder/'train_000.json';path.unlink()
        self.authority.seal('acceptance',payload,path)

    def test_normal_reuse_rehashes_candidate_bytes_even_same_size_and_mtime(self):
        self.certify()
        with patch.object(c,'_full_check',side_effect=AssertionError('No fallback validation on read')):
            self.assertEqual(self.cache.read(self.registration,self.stage),(self.summary,self.aggregate))
            info=self.candidate.stat();before=self.candidate.read_bytes()
            self.candidate.write_bytes(b'X'*len(before));os.utime(self.candidate,ns=(info.st_atime_ns,info.st_mtime_ns))
            with self.assertRaises(ValueError): self.cache.read(self.registration,self.stage)

    def test_root_failure_extra_member_and_optional_report_scope(self):
        self.certify()
        # Optional analysis is explicitly outside evidence; it cannot alter any
        # cached summary/aggregate or become a proof input through this cache.
        (self.stage/'report.json').write_bytes(b'SYNTHETIC-OPTIONAL-REPORT')
        (self.stage/'report.sha256').write_bytes(b'SYNTHETIC-OPTIONAL-SIDECAR')
        self.assertEqual(self.cache.read(self.registration,self.stage),(self.summary,self.aggregate))
        for name in ('failure_receipt.json','unregistered-proof.json'):
            path=self.stage/name;path.write_bytes(b'SYNTHETIC-NEW-ROOT-EVIDENCE')
            with self.subTest(name=name),self.assertRaises(ValueError): self.cache.read(self.registration,self.stage)
            path.unlink()
        extra=self.stage/'unregistered-directory';extra.mkdir()
        with self.assertRaises(ValueError): self.cache.read(self.registration,self.stage)

    def test_hardlinked_proof_rejected_even_when_every_byte_unchanged(self):
        self.certify();saved=self.proof.read_bytes();self.proof.unlink()
        external=self.campaign/'SYNTHETIC-ALIAS';external.write_bytes(saved)
        try: os.link(external,self.proof)
        except OSError:
            # This Windows host denies hardlink creation. Verify the exact
            # regular-file/nlink branch with explicit SYNTHETIC metadata;
            # this is not an actual filesystem hardlink qualification claim.
            self.proof.write_bytes(saved);actual=self.proof.stat();path=self.proof
            class SyntheticHardlinkMetadata:
                def __fspath__(self): return str(path)
                def lstat(self): return types.SimpleNamespace(st_mode=actual.st_mode,st_nlink=2)
                def open(self,*_): raise AssertionError('Hardlinked input must be rejected before reading')
            with self.assertRaises(ValueError): c._hash_file(self.campaign,SyntheticHardlinkMetadata())
            return
        self.assertGreater(self.proof.stat().st_nlink,1)
        with self.assertRaises(ValueError): self.cache.read(self.registration,self.stage)

    def test_signed_cache_parsed_summary_must_match_bound_raw_summary(self):
        certificate=self.certify();changed=copy.deepcopy(certificate)
        changed['summary']['original_callbacks']=999999
        changed['summary_sha256']=c.sha(c.canonical(changed['summary']))
        self.replace_certificate(changed)
        with self.assertRaises(ValueError): self.cache.read(self.registration,self.stage)

    def test_signed_context_drift_cannot_broaden_cached_evidence(self):
        certificate=self.certify()
        mutations=[lambda p:p.update(stage='development'),lambda p:p.update(new_physics_steps=True),
            lambda p:p.update(bmcts_credit=1),lambda p:p.update(amendment_sha256='0'*64),
            lambda p:p['execution_configuration'].update(workers=4),
            lambda p:p['qualified_rival_sources']['planner'].update(sha256='0'*64),
            lambda p:p['environment'].update(python_version='SYNTHETIC-FOREIGN-RUNTIME'),
            lambda p:p['original_source_sha256'].__setitem__('deadline_campaign/controller.py','0'*64),
            lambda p:p.update(accepted_sha256='0'*64)]
        for mutate in mutations:
            changed=copy.deepcopy(certificate);mutate(changed);self.replace_certificate(changed)
            with self.subTest(mutate=mutate),self.assertRaises(ValueError): self.cache.read(self.registration,self.stage)

    def test_failed_or_interrupted_full_check_cannot_publish_or_silently_retry(self):
        interrupt=KeyboardInterrupt('INDEPENDENT SYNTHETIC STOP')
        with patch.object(c,'_canonical_stage_check'),patch.object(c,'_full_check',side_effect=interrupt) as full:
            with self.assertRaises(KeyboardInterrupt) as caught: self.cache.create('train_000')
        self.assertIs(caught.exception,interrupt);full.assert_called_once()
        self.assertFalse((self.cache.folder/'train_000.json').exists())
        with patch.object(c,'_full_check') as full:
            with self.assertRaises(FileNotFoundError): self.cache.read(self.registration,self.stage)
        full.assert_not_called()

    def test_complete_clone_graph_preserves_frozen_globals_and_fresh_executor(self):
        original=dict(c.frozen.__dict__);namespace=c.cloned_phase_namespace(self.cache)
        self.assertIs(namespace['_execute'],original['_execute'])
        self.assertIs(namespace['_execute'].__globals__['_verify_output'],original['_verify_output'])
        self.assertEqual(namespace['_verify_output'],self.cache.read)
        for name,value in original.items():
            self.assertIs(c.frozen.__dict__[name],value)
            if isinstance(value,types.FunctionType) and value.__globals__ is c.frozen.__dict__ and name not in ('_execute','_verify_output'):
                self.assertIs(namespace[name].__code__,value.__code__)
                self.assertIs(namespace[name].__globals__,namespace)
                self.assertIs(namespace[name].__defaults__,value.__defaults__)
                self.assertIs(namespace[name].__closure__,value.__closure__)
        with self.assertRaises(ValueError): c.run_phase(self.cache,'train')

    def test_signed_amendment_binds_original_function_code_defaults_and_closure(self):
        contracts=c.function_contracts()
        for name in ('_execute','_verify_output','_validate_acceptance','_train_chain','freeze_shortlist','development','final'):
            self.assertIn(name,contracts)
            self.assertIsNone(contracts[name]['closure'])
            self.assertEqual(len(contracts[name]['code_sha256']),64)
        changed=copy.deepcopy(self.cache.amendment)
        changed['original_function_contracts']['_execute']['code_sha256']='0'*64
        path=self.cache.amendment_path;path.unlink()
        self.authority.seal('registration',changed,path)
        # Fresh object avoids relying solely on the old object's remembered
        # amendment SHA. The signed contract itself must match original code.
        with self.assertRaises(ValueError): c.IntegrityCache(self.campaign,self.authority)


if __name__=='__main__': unittest.main()
