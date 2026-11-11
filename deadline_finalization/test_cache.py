"""Synthetic data/MAC fixtures only; no live authority, callbacks or GPU use."""
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

from . import cache as c


class FakeAuthority:
    """In-memory synthetic secret; no real key file is created or read."""
    def __init__(self,campaign): self.campaign=campaign;self.writes=[]
    @property
    def manifest_sha256(self): return c.sha((self.campaign/'manifest.json').read_bytes())
    def mac(self,scope,payload):
        return hmac.new(b'SYNTHETIC-TEST-SECRET-NOT-A-REAL-KEY',
            c.canonical([str(self.campaign),scope,payload]),hashlib.sha256).hexdigest()
    def path(self,path):
        path=Path(path)
        return path if path.is_absolute() else self.campaign/path
    def seal(self,scope,payload,path):
        target=self.path(path);target.parent.mkdir(parents=True,exist_ok=True)
        envelope=dict(scope=scope,payload=copy.deepcopy(payload),mac=self.mac(scope,payload))
        with target.open('xb') as handle: handle.write(c.canonical(envelope)+b'\n')
        self.writes.append(target);return envelope
    def read(self,scope,path):
        envelope=c._read(self.path(path))
        if envelope['scope']!=scope or not hmac.compare_digest(envelope['mac'],self.mac(scope,envelope['payload'])):
            raise ValueError('SYNTHETIC MAC/scope mismatch')
        return copy.deepcopy(envelope['payload'])


def write(path,value):
    body=c.canonical(value)+b'\n';path.write_bytes(body)
    path.with_suffix('.sha256').write_text(c.sha(body)+'\n')


class CacheTests(unittest.TestCase):
    def setUp(self):
        parent=c.ROOT/'.cache/finalization-unit-tests';parent.mkdir(parents=True,exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(prefix='SYNTHETIC-',dir=parent);self.addCleanup(self.temp.cleanup)
        self.campaign=Path(self.temp.name);self.authority=FakeAuthority(self.campaign)
        self.real_authority_check=c._check_authority
        fake_only=patch.object(c,'_check_authority',return_value=None)
        fake_only.start();self.addCleanup(fake_only.stop)
        self.configuration=dict(batch_size=128,workers=8,audit_workers=4)
        self.manifest=dict(format=c.frozen.design.FORMAT,source_sha256=c.frozen.source_pins(),
            execution_configuration=self.configuration,catalog_sha256=c.frozen.design.CATALOG_SHA256)
        write(self.campaign/'manifest.json',self.manifest)
        self.stage=self.campaign/'train_000';self.stage.mkdir();(self.stage/'candidates').mkdir()
        candidate=self.stage/'candidates'/(c.sha(b'SYNTHETIC')+'.py');candidate.write_bytes(b'SYNTHETIC')
        self.registration=dict(phase='train',generation=0,
            candidates=[dict(path=str(candidate),sha256=c.sha(candidate.read_bytes()))],sources=c.rival_sources(),
            guards={str(c.ROOT/k):v for k,v in self.manifest['source_sha256'].items()})
        write(self.stage/'registration.json',self.registration)
        self.authority.seal('registration',{'SYNTHETIC':True},self.stage/'registration_receipt.json')
        self.authority.seal('start',{'SYNTHETIC':True},self.stage/'started.json')
        execution=self.stage/'execution';execution.mkdir();(execution/'.execution_claim').mkdir()
        (execution/'batch_00000').mkdir();self.turns=execution/'batch_00000'/'turns.jsonl'
        self.turns.write_bytes(b'SYNTHETIC-PROOF-BYTES\n')
        (execution/'originals.jsonl').write_bytes(b'SYNTHETIC-ORIGINAL\n')
        (execution/'audits.jsonl').write_bytes(b'SYNTHETIC-AUDIT\n')
        self.summary=dict(originals_sha256=c.sha((execution/'originals.jsonl').read_bytes()),
            audits_sha256=c.sha((execution/'audits.jsonl').read_bytes()),wall_before_final_publication_s=1.)
        self.aggregate={'games':1,'ranking':[]}
        self.accepted=dict(aggregate=self.aggregate,registration_sha256=c.sha((self.stage/'registration.json').read_bytes()),
            originals_sha256=self.summary['originals_sha256'],audits_sha256=self.summary['audits_sha256'])
        self.authority.seal('acceptance',self.accepted,self.stage/'accepted.json')
        write(execution/'summary.json',self.summary)
        write(execution/'execution_started.json',dict(cpu_runtime=c._environment(),**self.configuration))

    def open(self):
        c.publish_amendment(self.campaign,self.authority)
        return c.IntegrityCache(self.campaign,self.authority)

    def certify(self,cache):
        with patch.object(c,'_canonical_stage_check') as canonical,patch.object(c,'_full_check',
                return_value=(self.summary,self.aggregate,self.accepted)) as full:
            result=cache.create('train_000')
        canonical.assert_called_once();full.assert_called_once()
        return result

    def test_full_certificate_then_byte_identical_reuse_is_isolated_and_zero_credit(self):
        cache=self.open();certificate=self.certify(cache)
        summary,aggregate=cache.read(self.registration,self.stage)
        self.assertEqual((summary,aggregate),(self.summary,self.aggregate))
        aggregate['games']=99;summary['audits_sha256']='bad'
        self.assertEqual(cache.read(self.registration,self.stage),(self.summary,self.aggregate))
        self.assertTrue(all(type(certificate[k]) is int and certificate[k]==0 for k in c.ZERO))
        with self.assertRaises(ValueError): cache.create('train_000')

    def test_same_size_same_mtime_proof_tamper_rejects(self):
        cache=self.open();self.certify(cache);info=self.turns.stat();body=self.turns.read_bytes()
        self.turns.write_bytes(b'X'*len(body));os.utime(self.turns,ns=(info.st_atime_ns,info.st_mtime_ns))
        with self.assertRaises(ValueError): cache.read(self.registration,self.stage)

    def test_extra_missing_directory_and_failed_tree_reject(self):
        cache=self.open();self.certify(cache)
        extra=self.stage/'execution'/'extra.json';extra.write_bytes(b'NEW')
        with self.assertRaises(ValueError): cache.read(self.registration,self.stage)
        extra.unlink();newdir=self.stage/'execution'/'new-empty';newdir.mkdir()
        with self.assertRaises(ValueError): cache.read(self.registration,self.stage)
        newdir.rmdir();body=self.turns.read_bytes();self.turns.unlink()
        with self.assertRaises(ValueError): cache.read(self.registration,self.stage)
        self.turns.write_bytes(body);error=self.stage/'execution'/'error.json';error.write_bytes(b'SYNTHETIC-FAILED')
        with self.assertRaises(ValueError): cache.read(self.registration,self.stage)

    def test_certificate_mac_role_scope_and_foreign_stage_reject(self):
        cache=self.open();self.certify(cache);path=cache.folder/'train_000.json';body=path.read_bytes()
        record=json.loads(body);record['payload']['aggregate']['games']=99;path.write_bytes(c.canonical(record)+b'\n')
        with self.assertRaises(ValueError): cache.read(self.registration,self.stage)
        path.write_bytes((self.stage/'accepted.json').read_bytes())
        with self.assertRaises(ValueError): cache.read(self.registration,self.stage)
        path.write_bytes(body)
        for change in ({'stage':'train_001'},{'new_games':False},{'new_actor_callbacks':1},{'role':'GAME-ADMISSION'}):
            payload=json.loads(body)['payload'];payload.update(change);path.unlink()
            self.authority.seal('acceptance',payload,path)
            with self.subTest(change=change),self.assertRaises(ValueError): cache.read(self.registration,self.stage)
            path.write_bytes(body)

    def test_mutation_during_full_validation_never_creates_certificate(self):
        cache=self.open()
        def full(*_):
            self.turns.write_bytes(b'CHANGED-DURING-CHECK\n');return self.summary,self.aggregate,self.accepted
        with patch.object(c,'_canonical_stage_check'),patch.object(c,'_full_check',side_effect=full):
            with self.assertRaises(ValueError): cache.create('train_000')
        self.assertFalse((cache.folder/'train_000.json').exists())

    def test_failure_before_full_check_and_missing_cache_never_fallback(self):
        cache=self.open()
        with patch.object(c,'_full_check') as full:
            with self.assertRaises(FileNotFoundError): cache.read(self.registration,self.stage)
        full.assert_not_called()
        with patch.object(c,'_canonical_stage_check',side_effect=ValueError('SYNTHETIC BAD RECIPE')),patch.object(c,'_full_check') as full:
            with self.assertRaises(ValueError): cache.create('train_000')
        full.assert_not_called()

    def test_adapter_source_configuration_and_prospective_amendment_guards(self):
        cache=self.open();self.certify(cache);changed=c.source_pins();changed['deadline_finalization/cache.py']='0'*64
        with patch.object(c,'source_pins',return_value=changed):
            with self.assertRaises(ValueError): cache.read(self.registration,self.stage)
        amended=copy.deepcopy(cache.amendment);amended['execution_configuration']['workers']=4
        path=cache.amendment_path;path.unlink();self.authority.seal('registration',amended,path)
        with self.assertRaises(ValueError): cache.read(self.registration,self.stage)

    def test_amendment_after_holdout_or_for_foreign_path_rejects(self):
        (self.campaign/'development').mkdir()
        with self.assertRaises(ValueError): c.publish_amendment(self.campaign,self.authority)
        with self.assertRaises(ValueError): c.fingerprint_tree(self.campaign,'../train_000')

    def test_caller_assertion_is_not_an_owner_authority(self):
        with self.assertRaises(ValueError): self.real_authority_check(self.campaign,self.authority)
        with self.assertRaises(ValueError): self.real_authority_check(self.campaign,True)

    def test_function_graph_uses_one_copied_namespace_and_fresh_execute_is_original(self):
        cache=self.open();before=dict(c.frozen.__dict__);namespace=c.cloned_phase_namespace(cache)
        self.assertIs(namespace['_execute'],c.frozen._execute)
        self.assertIs(namespace['_execute'].__globals__,c.frozen.__dict__)
        self.assertIs(namespace['_execute'].__globals__['_verify_output'],before['_verify_output'])
        self.assertIs(namespace['_train_chain'].__globals__,namespace)
        self.assertIs(namespace['_validate_acceptance'].__globals__,namespace)
        self.assertIs(namespace['_validate_acceptance'].__code__,before['_validate_acceptance'].__code__)
        self.assertEqual(namespace['_verify_output'],cache.read)
        self.assertEqual(set(before),set(c.frozen.__dict__))
        self.assertTrue(all(c.frozen.__dict__[key] is value for key,value in before.items()))
        with self.assertRaises(ValueError): c.run_phase(cache,'train')


if __name__=='__main__': unittest.main()
