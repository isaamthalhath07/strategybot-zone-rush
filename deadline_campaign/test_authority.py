"""Temporary synthetic owner-key tests only; no live authority or game use."""
import copy
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from deadline_campaign import authority as a


class AuthorityTests(unittest.TestCase):
    def setUp(self):
        parent=a.ROOT/'.cache'/'deadline-authority-tests'
        parent.mkdir(parents=True,exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(prefix='SYNTHETIC-',dir=parent)
        self.addCleanup(self.temp.cleanup)
        self.campaign=Path(self.temp.name)
        self.manifest={'format':'SYNTHETIC-NO-GAMES','deadline':'2026-11-09T11:43:39+00:00',
                       'large_seed':(1<<97)+17,'new_game_credit':0}
        self.manifest_path=self.campaign/'manifest.json'
        self.manifest_path.write_bytes(a.canonical(self.manifest)+b'\n')

    def create(self): return a.Authority.create(self.campaign)

    def test_scoped_roundtrip_exclusive_paths_and_private_key(self):
        authority=self.create()
        a.permissions.verify_private(self.campaign/a.PRIVATE_DIRECTORY,directory=True)
        key=self.campaign/a.PRIVATE_DIRECTORY/'private.key'
        a.permissions.verify_private(key)
        secret=key.read_bytes()
        self.assertEqual(len(secret),32)
        for scope in sorted(a.SCOPES):
            path=self.campaign/'receipts'/(scope+'.json')
            payload={'scope_data':scope,'count':0,'seed':(1<<112)+4,'finite':.25}
            envelope=authority.seal(scope,payload,path)
            self.assertEqual(authority.read(scope,path),payload)
            self.assertEqual(a.Authority.load(self.campaign).read(scope,path),payload)
            self.assertEqual(envelope['manifest_sha256'],a._sha(self.manifest_path.read_bytes()))
            text=path.read_text()
            self.assertNotIn(secret.hex(),text)
            self.assertNotIn('private.key',text)
            self.assertNotIn(a.PRIVATE_DIRECTORY,text)
            with self.assertRaises(FileExistsError): authority.seal(scope,payload,path)
            other='failure' if scope!='failure' else 'start'
            with self.assertRaises(ValueError): authority.read(other,path)
        with self.assertRaises(FileExistsError): self.create()
        self.assertEqual(key.read_bytes(),secret)

    def test_tamper_scope_purpose_and_foreign_campaign_rejected(self):
        authority=self.create();path=self.campaign/'receipt.json'
        authority.seal('acceptance',{'games':8,'credit':0},path)
        original=path.read_bytes()
        changes=[('scope','start'),('purpose','legacy'),('campaign',str(self.campaign/'other')),
                 ('manifest_sha256','0'*64),('authority_id','0'*32),('mac','0'*64),
                 ('payload',{'games':999,'credit':0})]
        for key,value in changes:
            with self.subTest(key=key):
                envelope=json.loads(original);envelope[key]=value
                path.write_bytes(a.canonical(envelope)+b'\n')
                with self.assertRaises(ValueError): authority.read('acceptance',path)
        path.write_bytes(original)
        foreign=self.campaign/'foreign';foreign.mkdir()
        (foreign/'manifest.json').write_bytes(self.manifest_path.read_bytes())
        second=a.Authority.create(foreign)
        (foreign/'copied.json').write_bytes(original)
        with self.assertRaises(ValueError): second.read('acceptance','copied.json')
        # Receipts bind campaign/scope/manifest, not their filename. A copy
        # inside the ORIGINAL campaign remains that original authority's proof.
        self.assertEqual(authority.read('acceptance',foreign/'copied.json'),{'games':8,'credit':0})

    def test_manifest_drift_and_binding_or_key_corruption_fail_closed(self):
        authority=self.create();authority.seal('start',{'ok':True},'start.json')
        original=self.manifest_path.read_bytes()
        self.manifest_path.write_bytes(a.canonical(dict(self.manifest,changed=True))+b'\n')
        with self.assertRaises(ValueError): a.Authority.load(self.campaign)
        with self.assertRaises(ValueError): authority.read('start','start.json')
        with self.assertRaises(ValueError): authority.seal('failure',{},'failure.json')
        self.manifest_path.write_bytes(original)
        binding=self.campaign/a.PRIVATE_DIRECTORY/'binding.json'
        body=binding.read_bytes();data=json.loads(body);data['authority_id']='e'*32
        binding.write_bytes(a.canonical(data)+b'\n')
        with self.assertRaises(ValueError): a.Authority.load(self.campaign)
        binding.write_bytes(body)
        key=self.campaign/a.PRIVATE_DIRECTORY/'private.key'
        key.write_bytes(b'bad')
        with self.assertRaises(ValueError): a.Authority.load(self.campaign)
        with self.assertRaises(FileExistsError): self.create()

    def test_plain_json_exact_types_and_canonical_bytes_required(self):
        class Number(int): pass
        class Text(str): pass
        class Mapping(dict): pass
        bad=[float('nan'),float('inf'),(1,2),{1:'bad'},Number(2),Text('bad'),Mapping(ok=True),object()]
        for value in bad:
            with self.subTest(kind=type(value)),self.assertRaises(ValueError): a.canonical({'x':value})
        authority=self.create()
        for i,value in enumerate(bad):
            with self.subTest(kind=type(value)),self.assertRaises(ValueError):
                authority.seal('start',{'x':value},'bad%d.json'%i)
        authority.seal('start',{'ok':True},'good.json')
        good=self.campaign/'good.json';body=good.read_bytes()
        variants=[body[:-1],b' '+body,body.replace(b'"scope":"start"',b'"scope":"start","scope":"start"'),
                  body.replace(b'"ok":true',b'"ok":NaN')]
        for variant in variants:
            good.write_bytes(variant)
            with self.assertRaises((ValueError,json.JSONDecodeError)): authority.read('start',good)
        good.write_bytes(body)
        with self.assertRaises(ValueError): authority.seal('unregistered',{},'bad.json')
        with self.assertRaises(ValueError): authority.seal('start',[],'bad.json')

    def test_initial_manifest_canonicality_and_campaign_boundary(self):
        self.manifest_path.write_bytes(b'{"b":1,"a":2}\n')
        with self.assertRaises(ValueError): self.create()
        self.assertFalse((self.campaign/a.PRIVATE_DIRECTORY).exists())
        self.manifest_path.write_bytes(b'{"a":1,"a":1}\n')
        with self.assertRaises(ValueError): self.create()
        self.manifest_path.write_bytes(a.canonical(self.manifest)+b'\n')
        with self.assertRaises(ValueError): a.Authority.create(a.ROOT/'deadline_campaign')
        with self.assertRaises(ValueError): a.Authority.load(a.ROOT/'.cache')
        authority=self.create()
        for path in ('../escaped.json','manifest.json',a.PRIVATE_DIRECTORY+'/receipt.json'):
            with self.subTest(path=path),self.assertRaises(ValueError): authority.seal('start',{},path)
        self.assertFalse((self.campaign.parent/'escaped.json').exists())

    def test_acl_failure_and_key_hardlink_are_not_recovered_or_ignored(self):
        authority=self.create()
        with patch.object(a.permissions,'verify_private',side_effect=PermissionError('synthetic bad ACL')):
            with self.assertRaises(PermissionError): a.Authority.load(self.campaign)
            with self.assertRaises(PermissionError): authority.seal('start',{},'bad.json')
        key=self.campaign/a.PRIVATE_DIRECTORY/'private.key'
        original_stat=Path.stat
        def linked_stat(path,*args,**kwargs):
            result=original_stat(path,*args,**kwargs)
            if path==key:
                values={name:getattr(result,name) for name in dir(result) if name.startswith('st_')}
                values['st_nlink']=2
                return SimpleNamespace(**values)
            return result
        # Windows denies creating this synthetic hardlink in this environment;
        # inject only the OS link-count result, without weakening any live ACL.
        with patch.object(Path,'stat',linked_stat):
            with self.assertRaises(ValueError): a.Authority.load(self.campaign)
        self.assertEqual(a.Authority.load(self.campaign).authority_id,authority.authority_id)

    def test_key_is_restricted_while_empty_and_no_automatic_failed_create_retry(self):
        calls=[];real=a.permissions.restrict
        def restrict(path,directory=False):
            if Path(path).name=='private.key': calls.append(Path(path).stat().st_size)
            return real(path,directory=directory)
        with patch.object(a.permissions,'restrict',side_effect=restrict): self.create()
        self.assertEqual(calls,[0])
        other=self.campaign/'failed-create';other.mkdir()
        (other/'manifest.json').write_bytes(self.manifest_path.read_bytes())
        with patch.object(a.permissions,'restrict',side_effect=PermissionError('synthetic restriction failure')):
            with self.assertRaises(PermissionError): a.Authority.create(other)
        with self.assertRaises(FileExistsError): a.Authority.create(other)


if __name__=='__main__': unittest.main()
