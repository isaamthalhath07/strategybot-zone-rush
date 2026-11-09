"""Owner-local receipts for the separate ten-hour protocol, never game credit.

The root coordinator writes canonical ``manifest.json`` plus LF first. This
module then exclusively binds a fresh local key to that manifest and canonical
campaign directory. It reuses the unchanged legacy ACL/link primitives, not a
legacy key, admission purpose, or approval. No authority object enters workers.
"""
import hashlib
import hmac
import json
import math
import os
from pathlib import Path
import secrets
import stat

from campaign_holdout import authority as permissions

ROOT=permissions.ROOT
FORMAT='deadline-owner-local-receipt/1'
PURPOSE='zone-rush-ten-hour-owner-local-authority/1'
SCOPES=frozenset(('manifest','registration','start','acceptance','shortlist',
                  'dev-selection','final-decision','failure'))
PRIVATE_DIRECTORY='.deadline-authority'


def canonical(value):
    """Only exact JSON builtins; never implicit object/subclass serialization."""
    def validate(item):
        kind=type(item)
        if item is None or kind in (str,bool,int): return
        if kind is float and math.isfinite(item): return
        if kind is list:
            for child in item: validate(child)
            return
        if kind is dict and all(type(key) is str for key in item):
            for child in item.values(): validate(child)
            return
        raise ValueError('Authority accepts finite exact plain JSON only')
    validate(value)
    return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode('utf8')


def _loads(body):
    def pairs(items):
        result={}
        for key,value in items:
            if key in result: raise ValueError('Duplicate authority JSON key')
            result[key]=value
        return result
    def nonfinite(_): raise ValueError('Nonfinite authority JSON')
    value=json.loads(body,object_pairs_hook=pairs,parse_constant=nonfinite)
    if body!=canonical(value)+b'\n':
        raise ValueError('Authority JSON must use exact canonical bytes plus LF')
    return value


def _sha(body): return hashlib.sha256(body).hexdigest()


def _hex(value,length=64):
    return type(value) is str and len(value)==length and all(c in '0123456789abcdef' for c in value)


def _campaign_path(campaign):
    target=Path(os.path.abspath(campaign))
    cache=ROOT/'.cache'
    if target==cache or not target.is_relative_to(cache):
        raise ValueError('Deadline authority must stay in a distinct canonical ignored-cache campaign')
    permissions._without_links(target,cache)
    if not target.is_dir(): raise ValueError('Write the campaign and canonical manifest before initialization')
    return target


def _checked(campaign,path):
    return permissions._without_links(path,campaign)


def _regular(path):
    if not stat.S_ISREG(path.lstat().st_mode): raise ValueError('Authority requires a regular file')


def _manifest(campaign):
    path=_checked(campaign,campaign/'manifest.json')
    _regular(path)
    body=path.read_bytes()
    value=_loads(body)
    if type(value) is not dict: raise ValueError('Campaign manifest must be a plain JSON object')
    return _sha(body)


def _write_new(path,body,private=False):
    descriptor=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    try:
        if private: permissions.restrict(path)  # restrict EMPTY file before secrets
        with os.fdopen(descriptor,'wb',closefd=False) as stream:
            stream.write(body);stream.flush();os.fsync(stream.fileno())
    finally:
        os.close(descriptor)


def _mac(secret,purpose,payload):
    return hmac.new(secret,canonical(dict(purpose=purpose,payload=payload)),hashlib.sha256).hexdigest()


def _read_binding(campaign):
    private=_checked(campaign,campaign/PRIVATE_DIRECTORY)
    permissions.verify_private(private,directory=True)
    binding_path=_checked(campaign,private/'binding.json')
    key_path=_checked(campaign,private/'private.key')
    for path in (binding_path,key_path):
        _regular(path);permissions.verify_private(path)
        if path.stat().st_nlink!=1: raise ValueError('Linked private authority files are forbidden')
    binding=_loads(binding_path.read_bytes())
    if (type(binding) is not dict or set(binding)!={'format','purpose','campaign','manifest_sha256','authority_id','mac'}
            or binding['format']!=FORMAT or binding['purpose']!=PURPOSE
            or binding['campaign']!=str(campaign) or binding['manifest_sha256']!=_manifest(campaign)
            or not _hex(binding['authority_id'],32) or not _hex(binding['mac'])):
        raise ValueError('Foreign, malformed or changed deadline authority binding')
    secret=key_path.read_bytes()
    if len(secret)!=32: raise ValueError('Invalid local authority key; no automatic recovery')
    content={key:value for key,value in binding.items() if key!='mac'}
    if not hmac.compare_digest(binding['mac'],_mac(secret,PURPOSE+'/binding',content)):
        raise ValueError('Deadline authority binding authentication failed')
    return binding,secret


class Authority:
    __slots__=('_campaign','_manifest_sha256','_identity')

    def __init__(self,*_):
        raise TypeError('Use Authority.create(campaign) or Authority.load(campaign)')

    @classmethod
    def _instance(cls,campaign,binding):
        result=object.__new__(cls)
        result._campaign=campaign
        result._manifest_sha256=binding['manifest_sha256']
        result._identity=binding['authority_id']
        return result

    @property
    def campaign(self): return self._campaign

    @property
    def manifest_sha256(self): return self._manifest_sha256

    @property
    def authority_id(self): return self._identity

    @classmethod
    def create(cls,campaign):
        campaign=_campaign_path(campaign);manifest_sha=_manifest(campaign)
        private=_checked(campaign,campaign/PRIVATE_DIRECTORY)
        private.mkdir(exist_ok=False)  # a failed/old binding is never replaced
        permissions.restrict(private,directory=True)
        _checked(campaign,private)
        secret=secrets.token_bytes(32)
        _write_new(_checked(campaign,private/'private.key'),secret,private=True)
        binding=dict(format=FORMAT,purpose=PURPOSE,campaign=str(campaign),
            manifest_sha256=manifest_sha,authority_id=secrets.token_hex(16))
        binding['mac']=_mac(secret,PURPOSE+'/binding',binding)
        _write_new(_checked(campaign,private/'binding.json'),canonical(binding)+b'\n',private=True)
        # Detect any path, manifest, ACL or secret-write failure before returning.
        return cls.load(campaign)

    @classmethod
    def load(cls,campaign):
        campaign=_campaign_path(campaign)
        binding,_=_read_binding(campaign)
        return cls._instance(campaign,binding)

    def _check(self):
        campaign=_campaign_path(self._campaign)
        binding,secret=_read_binding(campaign)
        if binding['manifest_sha256']!=self._manifest_sha256 or binding['authority_id']!=self._identity:
            raise ValueError('Loaded authority identity changed; no rebinding')
        return secret

    def _path(self,path):
        path=Path(path)
        if not path.is_absolute(): path=self._campaign/path
        target=Path(os.path.abspath(path))
        _checked(self._campaign,target)
        if (target==self._campaign or target==self._campaign/'manifest.json'
                or target.is_relative_to(self._campaign/PRIVATE_DIRECTORY)):
            raise ValueError('Receipt cannot overwrite manifest or private authority')
        return target

    def seal(self,scope,payload,path):
        if type(scope) is not str or scope not in SCOPES: raise ValueError('Unknown deadline authority scope')
        if type(payload) is not dict: raise ValueError('Receipt payload must be a plain JSON object')
        canonical(payload)
        secret=self._check();target=self._path(path)
        target.parent.mkdir(parents=True,exist_ok=True)
        self._path(target)
        content=dict(format=FORMAT,purpose=PURPOSE,campaign=str(self._campaign),
            manifest_sha256=self._manifest_sha256,authority_id=self._identity,scope=scope,payload=payload)
        envelope=dict(content,mac=_mac(secret,PURPOSE+'/receipt',content))
        _write_new(target,canonical(envelope)+b'\n')
        self.read(scope,target)  # verify durable bytes and current binding
        return envelope

    def read(self,scope,path):
        if type(scope) is not str or scope not in SCOPES: raise ValueError('Unknown deadline authority scope')
        secret=self._check();target=self._path(path);_regular(target)
        envelope=_loads(target.read_bytes())
        if (type(envelope) is not dict or set(envelope)!={'format','purpose','campaign','manifest_sha256','authority_id','scope','payload','mac'}
                or envelope['format']!=FORMAT or envelope['purpose']!=PURPOSE
                or envelope['campaign']!=str(self._campaign) or envelope['manifest_sha256']!=self._manifest_sha256
                or envelope['authority_id']!=self._identity or envelope['scope']!=scope
                or type(envelope['payload']) is not dict or not _hex(envelope['mac'])):
            raise ValueError('Foreign campaign, manifest, purpose or scope in deadline receipt')
        content={key:value for key,value in envelope.items() if key!='mac'}
        if not hmac.compare_digest(envelope['mac'],_mac(secret,PURPOSE+'/receipt',content)):
            raise ValueError('Deadline receipt authentication failed')
        return envelope['payload']
