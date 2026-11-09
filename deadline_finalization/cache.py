"""Owner-authenticated cache of fully verified, byte-identical old evidence.

No actor/physics validation is removed from a fresh execution. Existing proof
trees are rehashed in full on every reuse; source/configuration/rival/runtime
guards and all frozen phase/acceptance checks remain. This is trusted-owner
integrity bookkeeping, not a hardware or hostile-host attestation.
"""
import argparse
import copy
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import stat
import sys
import types

from campaign_holdout import authority as paths
from deadline_campaign import controller as frozen
from deadline_campaign.authority import canonical

ROOT=Path(__file__).resolve().parents[1]
FORMAT='deadline-unchanged-evidence-integrity-cache/1'
AMENDMENT_FORMAT='deadline-prospective-finalization-amendment/1'
ROLE='Revalidation of already admitted unchanged evidence only; zero execution/admission credit'
FOLDER='finalization_integrity'
RIVALS={
    'planner':('bot.py','e8b3682d8b39d3fc4d22cdcd8927161290a90cd472d3ede4132ae716f8c6f8f5'),
    'research':('tester_bots/research_alternative.py','6f2ac1487cd0a66793db3f2fab01f621d9c945a4f71a78cc92d176ef1de321f4'),
    'racer':('tester_bots/racer.py','a35c2c4811645091adef6cbd263f1573bf2b184d5dd5741a070234a422ce54c8'),
    'blocker':('tester_bots/blocker.py','1bb70109a75e2880bfdf3ac9b6fd8e368b0f3d02b9a3e65de53cef0defa505e5'),
}
ZERO=dict(new_games=0,new_actor_callbacks=0,new_physics_steps=0,primary_credit=0,bmcts_credit=0)


def require(condition,message):
    if not condition: raise ValueError(message)


def sha(body): return hashlib.sha256(body).hexdigest()


def same(a,b): return canonical(a)==canonical(b)


def source_pins():
    return {p.relative_to(ROOT).as_posix():sha(p.read_bytes())
        for p in sorted(Path(__file__).parent.glob('*.py')) if not p.name.startswith('test_')}


def _code_material(value):
    if isinstance(value,types.CodeType):
        return dict(bytecode=value.co_code.hex(),constants=[_code_material(v) for v in value.co_consts],
            names=list(value.co_names),variables=list(value.co_varnames),free=list(value.co_freevars),cells=list(value.co_cellvars),
            argcount=value.co_argcount,posonly=value.co_posonlyargcount,kwonly=value.co_kwonlyargcount,
            flags=value.co_flags,stacksize=value.co_stacksize,locals=value.co_nlocals,
            filename=value.co_filename,firstline=value.co_firstlineno,name=value.co_name,qualname=value.co_qualname,
            exceptions=value.co_exceptiontable.hex(),lines=value.co_linetable.hex())
    if isinstance(value,Path): return {'path':str(value)}
    if type(value) is bytes: return {'bytes':value.hex()}
    if type(value) in (tuple,list): return [_code_material(v) for v in value]
    if type(value) is frozenset: return {'frozenset':sorted((_code_material(v) for v in value),key=canonical)}
    if type(value) is dict: return {k:_code_material(v) for k,v in value.items()}
    if value is None or type(value) in (str,int,float,bool): return value
    raise ValueError('Unexpected frozen function constant/default type')


def function_contracts():
    result={}
    for name,value in frozen.__dict__.items():
        if isinstance(value,types.FunctionType) and value.__globals__ is frozen.__dict__:
            require(value.__closure__ is None,'Unexpected frozen controller closure')
            result[name]=dict(code_sha256=sha(canonical(_code_material(value.__code__))),
                defaults=_code_material(value.__defaults__),keyword_defaults=_code_material(value.__kwdefaults__),closure=None)
    return result


def _path(campaign,path):
    return paths._without_links(Path(os.path.abspath(path)),campaign)


def _campaign(campaign):
    campaign=Path(os.path.abspath(campaign))
    paths._without_links(campaign,ROOT/'.cache')
    require(campaign.is_dir(),'An existing canonical campaign is required')
    return campaign


def _read(path):
    body=path.read_bytes();value=frozen.oversight.strict_loads(body)
    require(body==canonical(value)+b'\n','Exact canonical JSON plus LF required')
    return value


def _environment():
    return dict(implementation=platform.python_implementation(),python_version=platform.python_version(),full_python_version=sys.version)


def rival_sources():
    return {name:dict(path=str(ROOT/relative),sha256=digest) for name,(relative,digest) in RIVALS.items()}


def _check_authority(campaign,authority):
    require(type(authority) is frozen.Authority and authority.campaign==campaign,
        'The exact owner-local campaign authority is required; no caller assertion or substitute verifier')


def _source_guard(campaign,authority):
    _check_authority(campaign,authority)
    manifest_path=_path(campaign,campaign/'manifest.json');manifest=_read(manifest_path)
    require(sha(manifest_path.read_bytes())==authority.manifest_sha256,'Authority/manifest identity changed')
    require(manifest['source_sha256']==frozen.source_pins(),'Frozen campaign source closure changed')
    for entry in rival_sources().values():
        require(sha(Path(entry['path']).read_bytes())==entry['sha256'],'Qualified rival source changed')
    require(manifest.get('fallback_only') is not True,'Fallback-only releases have no evidence to cache')
    return manifest


def publish_amendment(campaign,authority):
    """Explicit root-only operation; never invoked implicitly by cache reads."""
    campaign=_campaign(campaign);manifest=_source_guard(campaign,authority)
    require(frozen._heldout_absent(campaign),'Finalization amendment must precede every heldout reservation/freeze')
    parent=_path(campaign,campaign/FOLDER);parent.mkdir(exist_ok=True)
    payload=dict(format=AMENDMENT_FORMAT,role=ROLE,campaign=str(campaign),manifest_sha256=authority.manifest_sha256,
        original_source_sha256=manifest['source_sha256'],adapter_source_sha256=source_pins(),
        original_function_contracts=function_contracts(),
        execution_configuration=manifest['execution_configuration'],qualified_rival_sources=rival_sources(),
        created_utc=datetime.now(timezone.utc).isoformat(),heldout_outcomes_consumed=False,
        method='Full original validation once before certification; every reuse authenticates and rehashes every bound proof byte. Fresh _execute remains the original function.',
        preserved='Original canonical registration/population/phase/acceptance/statistical/timeout rules and all fresh320 actor replays/two referees.',
        proof_scope='All execution files/directories, all candidate files, registration and its seal/receipt, start and accepted receipts. Optional analysis reports are not evidence inputs.',
        **ZERO)
    authority.seal('registration',payload,parent/'amendment.json')
    return payload


def _stage_name(name):
    require(type(name) is str and (re.fullmatch(r'train_[0-9]{3}',name) is not None or name in ('development','final')),
        'Exact existing TRAIN/DEV/FINAL stage name required')
    return name


def _hash_file(campaign,path):
    _path(campaign,path);info=path.lstat()
    require(stat.S_ISREG(info.st_mode),'Only regular proof files may enter an integrity tree')
    require(info.st_nlink==1,'Hardlinked proof files are forbidden')
    digest=hashlib.sha256()
    with path.open('rb') as stream:
        while True:
            block=stream.read(1024*1024)
            if not block: break
            digest.update(block)
    return digest.hexdigest()


def fingerprint_tree(campaign,name):
    """Read-only full-byte scan; no size/mtime shortcuts or parsed outcomes."""
    campaign=_campaign(campaign);directory=_path(campaign,campaign/_stage_name(name))
    require(directory.is_dir(),'Existing completed stage directory required')
    allowed={'registration.json','registration.sha256','registration_receipt.json','started.json','accepted.json',
        'candidates','execution','report.json','report.sha256'}
    require(not (directory/'failure_receipt.json').exists(),'Failed stage receipt forbids cache reuse')
    require({path.name for path in directory.iterdir()}<=allowed,'Unexpected stage-root member')
    for path in directory.iterdir():
        _path(campaign,path)
        if path.name not in ('candidates','execution'):
            require(stat.S_ISREG(path.lstat().st_mode),'Stage-root artifact must be a regular file')
    files={};directories=[]
    for relative in ('registration.json','registration.sha256','registration_receipt.json','started.json','accepted.json'):
        path=directory/relative;files[relative]=_hash_file(campaign,path)
    for top in ('candidates','execution'):
        start=_path(campaign,directory/top);require(start.is_dir(),'Complete candidate/execution tree required')
        pending=[start]
        while pending:
            current=pending.pop();_path(campaign,current)
            require(stat.S_ISDIR(current.lstat().st_mode),'Proof directory replaced by a non-directory')
            directories.append(current.relative_to(directory).as_posix())
            for child in sorted(current.iterdir()):
                _path(campaign,child);info=child.lstat()
                if stat.S_ISDIR(info.st_mode): pending.append(child)
                else: files[child.relative_to(directory).as_posix()]=_hash_file(campaign,child)
    require('execution/summary.json' in files and 'execution/error.json' not in files,'No partial/failed execution cache')
    return dict(directories=sorted(directories),files=dict(sorted(files.items())))


def _full_check(campaign,authority,directory,registration,configuration):
    """Passive capture of the exact original full verifier result, called once."""
    namespace=dict(frozen.__dict__);captured=[];original=frozen._verify_output
    def observe(reg,path):
        require(same(reg,registration) and path==directory,'Full validator changed the intended stage')
        value=original(reg,path);captured.append(value);return value
    namespace['_verify_output']=observe
    function=frozen._validate_acceptance
    checked=types.FunctionType(function.__code__,namespace,function.__name__,function.__defaults__,function.__closure__)
    checked.__kwdefaults__=function.__kwdefaults__
    accepted=checked(campaign,authority,directory,registration,configuration)
    require(len(captured)==1,'Exactly one unchanged full validation result required')
    summary,aggregate=captured[0]
    require(same(accepted['aggregate'],aggregate),'Full validation aggregate changed')
    return summary,aggregate,accepted


def _canonical_stage_check(campaign,authority,manifest,directory,registration):
    # Candidate lineage is still rebuilt by the untouched full phase chain on
    # reuse. Certification additionally checks this stage's exact catalog,
    # crossing, source/template bytes and authenticated registration receipt.
    phase=registration['phase'];generation=registration['generation'];catalog=frozen.design.catalog()
    if phase=='train':
        boards=catalog[500+16*generation:516+16*generation]
    else:
        short=authority.read('shortlist',campaign/'shortlist.json')
        indices=short['development_map_indices' if phase=='development' else 'final_map_indices']
        boards=[catalog[index] for index in indices]
    bodies=[Path(entry['path']).read_bytes() for entry in registration['candidates']]
    checked=frozen._validate_registration(campaign,authority,manifest,directory,phase,generation,bodies,boards)
    require(same(checked,registration),'Canonical stage registration changed')


class IntegrityCache:
    def __init__(self,campaign,authority):
        self.campaign=_campaign(campaign);self.authority=authority
        self.folder=_path(self.campaign,self.campaign/FOLDER)
        self.amendment_path=_path(self.campaign,self.folder/'amendment.json')
        self.amendment=authority.read('registration',self.amendment_path)
        self.amendment_sha256=sha(self.amendment_path.read_bytes())
        self._guard()

    def _guard(self):
        manifest=_source_guard(self.campaign,self.authority)
        amendment=self.authority.read('registration',self.amendment_path)
        require(sha(self.amendment_path.read_bytes())==self.amendment_sha256 and same(amendment,self.amendment),
            'Prospective amendment changed')
        require(amendment.get('format')==AMENDMENT_FORMAT and amendment.get('role')==ROLE
            and amendment.get('campaign')==str(self.campaign) and amendment.get('manifest_sha256')==self.authority.manifest_sha256
            and same(amendment.get('original_source_sha256'),manifest['source_sha256'])
            and same(amendment.get('adapter_source_sha256'),source_pins())
            and same(amendment.get('original_function_contracts'),function_contracts())
            and same(amendment.get('execution_configuration'),manifest['execution_configuration'])
            and same(amendment.get('qualified_rival_sources'),rival_sources())
            and amendment.get('heldout_outcomes_consumed') is False
            and all(type(amendment.get(k)) is int and amendment[k]==0 for k in ZERO),'Foreign/inconsistent finalization amendment')
        return manifest

    def _registration(self,name,manifest):
        directory=_path(self.campaign,self.campaign/_stage_name(name));registration=frozen._sealed(directory/'registration.json')
        require(same(registration['guards'],{str(ROOT/k):v for k,v in manifest['source_sha256'].items()}),
            'Stage does not bind all frozen source guards')
        require(same(registration['sources'],rival_sources()),'Stage rival mixture/source differs from qualification')
        expected='train' if name.startswith('train_') else name
        require(registration['phase']==expected and type(registration['generation']) is int
            and registration['generation']==(int(name[6:]) if expected=='train' else 0),'Stage phase/generation mismatch')
        for entry in registration['candidates']:
            require(Path(entry['path'])==directory/'candidates'/(entry['sha256']+'.py'),'Noncanonical candidate source path')
        return directory,registration

    def create(self,name):
        manifest=self._guard();name=_stage_name(name);target=_path(self.campaign,self.folder/(name+'.json'))
        require(not target.exists(),'Fresh cache certificate required; no overwrite/partial recovery')
        directory,registration=self._registration(name,manifest)
        before=fingerprint_tree(self.campaign,name)
        _canonical_stage_check(self.campaign,self.authority,manifest,directory,registration)
        summary,aggregate,accepted=_full_check(self.campaign,self.authority,directory,registration,manifest['execution_configuration'])
        after=fingerprint_tree(self.campaign,name)
        require(same(before,after),'Proof bytes changed during full certification')
        header=frozen._sealed(directory/'execution'/'execution_started.json')
        environment={k:header['cpu_runtime'][k] for k in _environment()}
        require(environment==_environment(),'Qualified CPU Python runtime changed')
        self._guard()
        payload=dict(format=FORMAT,role=ROLE,campaign=str(self.campaign),stage=name,
            manifest_sha256=self.authority.manifest_sha256,amendment_sha256=self.amendment_sha256,
            original_source_sha256=manifest['source_sha256'],adapter_source_sha256=source_pins(),
            execution_configuration=manifest['execution_configuration'],qualified_rival_sources=rival_sources(),
            environment=environment,registration_sha256=after['files']['registration.json'],
            accepted_sha256=after['files']['accepted.json'],proof_tree=after,
            summary=summary,aggregate=aggregate,aggregate_sha256=sha(canonical(aggregate)),summary_sha256=sha(canonical(summary)),
            prior_full_validation='Original _validate_acceptance code/defaults/closure; copied globals replace only _verify_output with passive original-result capture.',
            created_utc=datetime.now(timezone.utc).isoformat(),**ZERO)
        self.authority.seal('acceptance',payload,target)
        return payload

    def read(self,registration,directory):
        """Cache-only reader: never falls back or silently certifies anything."""
        manifest=self._guard();directory=Path(directory)
        require(directory.parent==self.campaign,'Foreign cached stage directory')
        name=_stage_name(directory.name);target=_path(self.campaign,self.folder/(name+'.json'))
        payload=self.authority.read('acceptance',target)
        require(payload.get('format')==FORMAT and payload.get('role')==ROLE and payload.get('stage')==name
            and payload.get('campaign')==str(self.campaign) and payload.get('manifest_sha256')==self.authority.manifest_sha256
            and payload.get('amendment_sha256')==self.amendment_sha256
            and same(payload.get('original_source_sha256'),manifest['source_sha256'])
            and same(payload.get('adapter_source_sha256'),source_pins())
            and same(payload.get('execution_configuration'),manifest['execution_configuration'])
            and same(payload.get('qualified_rival_sources'),rival_sources())
            and payload.get('environment')==_environment()
            and all(type(payload.get(k)) is int and payload[k]==0 for k in ZERO),'Foreign, unqualified or credit-bearing cache certificate')
        checked_directory,actual=self._registration(name,manifest)
        require(checked_directory==directory and same(actual,registration),'Cached registration differs from canonical phase input')
        tree=fingerprint_tree(self.campaign,name)
        require(same(tree,payload['proof_tree']),'Proof tree bytes, members or directories changed; cache rejected')
        require(payload['registration_sha256']==tree['files']['registration.json']
            and payload['accepted_sha256']==tree['files']['accepted.json']
            and payload['registration_sha256']==sha(canonical(registration)+b'\n'),'Cache registration/acceptance binding changed')
        accepted=self.authority.read('acceptance',directory/'accepted.json')
        require(same(accepted['aggregate'],payload['aggregate']) and accepted['registration_sha256']==payload['registration_sha256']
            and accepted['originals_sha256']==payload['summary']['originals_sha256']
            and accepted['audits_sha256']==payload['summary']['audits_sha256'],'Actual admitted receipt differs from certified parsed results')
        require(payload['aggregate_sha256']==sha(canonical(payload['aggregate']))
            and payload['summary_sha256']==sha(canonical(payload['summary'])),'Cached parsed data changed')
        require(sha(canonical(payload['summary'])+b'\n')==tree['files']['execution/summary.json'],
            'Cached parsed summary is not the exact fully checked raw summary')
        return copy.deepcopy(payload['summary']),copy.deepcopy(payload['aggregate'])


def cloned_phase_namespace(cache):
    """All helpers share copied globals; fresh _execute is strictly original."""
    cache._guard();namespace=dict(frozen.__dict__)
    for name,value in frozen.__dict__.items():
        if isinstance(value,types.FunctionType) and value.__globals__ is frozen.__dict__:
            replacement=types.FunctionType(value.__code__,namespace,value.__name__,value.__defaults__,value.__closure__)
            replacement.__kwdefaults__=value.__kwdefaults__;replacement.__annotations__=dict(value.__annotations__)
            replacement.__qualname__=value.__qualname__;replacement.__module__=value.__module__
            namespace[name]=replacement
    namespace['_verify_output']=cache.read
    namespace['_execute']=frozen._execute
    return namespace


def run_phase(cache,action):
    require(action in ('freeze','development','final','fallback'),'Only frozen finalization phases are supported; no training adapter')
    namespace=cloned_phase_namespace(cache)
    result=namespace['freeze_shortlist' if action=='freeze' else action](cache.campaign)
    cache._guard()
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('amend','certify','freeze','development','final','fallback','profile-tree'))
    parser.add_argument('--stage');args=parser.parse_args()
    if args.action=='profile-tree':
        require(args.stage is not None,'An exact completed stage name is required')
        tree=fingerprint_tree(frozen.CAMPAIGN,args.stage)
        print(json.dumps(dict(files=len(tree['files']),directories=len(tree['directories']),proof_tree_sha256=sha(canonical(tree)),**ZERO)));return
    # Owner authority is deliberately loaded only in an explicitly launched CLI.
    campaign,authority,_=frozen._context(frozen.CAMPAIGN)
    if args.action=='amend': result=publish_amendment(campaign,authority)
    else:
        cache=IntegrityCache(campaign,authority)
        if args.action=='certify':
            require(args.stage is not None,'An exact admitted stage name is required');result=cache.create(args.stage)
        else: result=run_phase(cache,args.action)
    print(json.dumps(dict(action=args.action,result=result),sort_keys=True))


if __name__=='__main__':main()
