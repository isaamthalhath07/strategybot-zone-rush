"""Stdlib outer launcher, copied to a delivery as RUN_WORK.py.

No game engine or policy is implemented here. Only a verified, unchanged signed
worker package may execute. Package checks and runtime probes execute no actors.
"""
import argparse
from contextlib import contextmanager
import hashlib
import io
import json
import os
from pathlib import Path,PurePosixPath
import platform
import re
import signal
import stat
import subprocess
import sys
import tempfile
import time
import zipfile

FORMAT = 'zone-rush-compute-delivery/1'
RUNTIME_KEYS = ('implementation','version','full_version','executable_sha256','platform')
MAX_ARCHIVE_BYTES = 256*1024*1024
MAX_EXPANDED_BYTES = 512*1024*1024
MAX_MANIFEST_BYTES = 128*1024*1024
MAX_FILES = 1024
AUXILIARY = {'bundle.json','bundle.sha256','RUN_INSTRUCTIONS.txt'}
RETURN_FILES = ('header.json','records.jsonl','progress.json')
WINDOWS_RENAME_DELAYS = (0.05,0.15,0.3,0.5)
WINDOWS_RETRY_ERRORS = frozenset((5,32,33))


def sha(body):
    return hashlib.sha256(body).hexdigest()


def canonical(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode('utf8')


def loads(body):
    def pairs(items):
        value = {}
        for key,item in items:
            if key in value:
                raise ValueError('Duplicate JSON field')
            value[key] = item
        return value
    def reject(value):
        raise ValueError('Nonfinite JSON constant')
    return json.loads(body,object_pairs_hook=pairs,parse_constant=reject)


def runtime_metadata():
    return dict(implementation=platform.python_implementation(),version=platform.python_version(),
                full_version=sys.version,executable_sha256=sha(Path(sys.executable).read_bytes()),
                platform=platform.platform())


def fingerprint(value):
    if type(value) is not dict or any(type(value.get(key)) is not str for key in RUNTIME_KEYS):
        raise ValueError('Malformed approved runtime')
    return sha(canonical({key:value[key] for key in RUNTIME_KEYS}))


def no_links(path):
    path = Path(os.path.abspath(path))
    for item in (path,*path.parents):
        if item.exists() or item.is_symlink():
            info = item.lstat()
            if item.is_symlink() or getattr(info,'st_file_attributes',0)&0x400:
                raise ValueError('Delivery paths cannot contain links or reparse points')
            if stat.S_ISREG(info.st_mode) and info.st_nlink!=1:
                raise ValueError('Delivery files cannot be hard links')
    return path


def relative_path(name):
    if type(name) is not str or not name or '\\' in name or ':' in name or '\x00' in name:
        raise ValueError('Unsafe package path')
    value = PurePosixPath(name)
    if value.is_absolute() or value.as_posix()!=name or any(part in ('.','..') for part in value.parts):
        raise ValueError('Unsafe package path')
    for part in value.parts:
        if part.endswith((' ','.')) or any(character in part for character in '<>"|?*'):
            raise ValueError('Unsafe Windows package component')
        if part.split('.')[0].upper() in {'CON','PRN','AUX','NUL',*(f'COM{i}' for i in range(1,10)),*(f'LPT{i}' for i in range(1,10))}:
            raise ValueError('Reserved Windows package name')
    return value


def context(config):
    keys = ('role','work_role','campaign_id','generation','shard_id','source_registration_sha256',
            'bundle_sha256','slot','expected_tasks','owner_plan_sha256','audit_plan_sha256',
            'approved_runtime_fingerprint')
    return {key:config[key] for key in keys}


def load_config(root):
    path = no_links(Path(root)/'delivery.json')
    if path.stat().st_size>65536:
        raise ValueError('Oversized outer metadata')
    value = loads(path.read_bytes())
    if (value['format']!=FORMAT or value['role']!='extra_control_assignment'
            or value['work_role'] not in ('play','audit') or type(value['expected_tasks']) is not int
            or not 1<=value['expected_tasks']<=200000 or value['primary_credit']!=0
            or value['cuda_used_by_policy'] is not False):
        raise ValueError('Unsupported delivery role/count/credit')
    if (type(value['slot']) is not dict or set(value['slot'])!={'slot_id','physical_slot_id'}
            or any(type(item) is not str or re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,127}',item) is None for item in value['slot'].values())):
        raise ValueError('Malformed registered helper identity')
    for key in ('campaign_id','shard_id','source_registration_sha256','bundle_sha256','inner_archive_sha256','owner_plan_sha256'):
        if type(value[key]) is not str or re.fullmatch(r'[0-9a-f]{64}',value[key]) is None:
            raise ValueError('Malformed delivery hash identity')
    if type(value['generation']) is not int or value['generation']<0:
        raise ValueError('Malformed generation identity')
    if fingerprint(value['approved_runtime'])!=value['approved_runtime_fingerprint']:
        raise ValueError('Approved runtime fingerprint metadata changed')
    if value['work_role']=='audit' and not value['audit_plan_sha256']:
        raise ValueError('Audit delivery requires its issued audit-plan binding')
    if value['work_role']=='play' and value['audit_plan_sha256'] is not None:
        raise ValueError('PLAY delivery cannot masquerade as an audit')
    return value


def check_bundle_context(bundle,config):
    for key in ('role','work_role','campaign_id','generation','shard_id','source_registration_sha256'):
        if type(bundle.get(key)) is not type(config[key]) or bundle[key]!=config[key]:
            raise ValueError('Signed worker role/campaign/shard/source context changed')
    if (bundle['target_slot']!=config['slot'] or len(bundle['fixtures'])!=config['expected_tasks']
            or len({fixture['id'] for fixture in bundle['fixtures']})!=config['expected_tasks']
            or fingerprint(bundle['approved_runtime'])!=config['approved_runtime_fingerprint']
            or bundle['worker_primary_credit']!=0 or bundle['cuda_used_by_policy'] is not False):
        raise ValueError('Signed worker slot/runtime/count changed')
    if config['work_role']=='audit':
        wanted = {fixture['id'] for fixture in bundle['fixtures']}
        if set(bundle['input_rows'])!=wanted or set(bundle['creators'])!=wanted:
            raise ValueError('Audit input rows/creator coverage changed')
        if any(creator['physical_slot_id']==config['slot']['physical_slot_id'] for creator in bundle['creators'].values()):
            raise ValueError('A physical creator cannot audit its own game')


def inspect_payload(archive,config):
    """Check the entire inner ZIP before extraction or importing its modules."""
    archive = no_links(archive)
    if archive.stat().st_size>MAX_ARCHIVE_BYTES or sha(archive.read_bytes())!=config['inner_archive_sha256']:
        raise ValueError('The owner-issued worker ZIP changed')
    with zipfile.ZipFile(archive) as zipped:
        entries = zipped.infolist()
        if not entries or len(entries)>MAX_FILES or sum(item.file_size for item in entries)>MAX_EXPANDED_BYTES:
            raise ValueError('Worker ZIP exceeds bounded extraction size')
        names,aliases = set(),set()
        for item in entries:
            relative_path(item.filename)
            if (item.is_dir() or item.filename in names or item.filename.casefold() in aliases
                    or stat.S_ISLNK(item.external_attr>>16) or item.flag_bits&1):
                raise ValueError('Duplicate, aliased, linked or encrypted ZIP entry')
            names.add(item.filename)
            aliases.add(item.filename.casefold())
        if 'bundle.json' not in names or zipped.getinfo('bundle.json').file_size>MAX_MANIFEST_BYTES:
            raise ValueError('Missing or oversized worker manifest')
        body = zipped.read('bundle.json')
        if sha(body)!=config['bundle_sha256']:
            raise ValueError('Signed worker manifest changed')
        bundle = loads(body)
        check_bundle_context(bundle,config)
        if names!=set(bundle['files'])|AUXILIARY:
            raise ValueError('Worker ZIP contains unregistered files or is incomplete')
        if zipped.read('bundle.sha256') not in tuple((config['bundle_sha256']+ending).encode('ascii') for ending in ('\n','\r\n')):
            raise ValueError('Worker manifest sidecar differs')
        for name,expected in bundle['files'].items():
            relative_path(name)
            if sha(zipped.read(name))!=expected:
                raise ValueError('An archived worker source changed')
        return bundle


def _validate_tree(tree,bundle,config,allow_cache):
    tree = no_links(tree)
    if not tree.is_dir():
        raise ValueError('Worker source tree is missing or is not a directory')
    expected = set(bundle['files'])|AUXILIARY
    directories = {parent.as_posix() for name in expected for parent in PurePosixPath(name).parents
                   if parent.as_posix()!='.'}
    for directory,children,files in os.walk(tree,topdown=True,followlinks=False):
        for name in children:
            path = no_links(Path(directory)/name)
            relative = path.relative_to(tree)
            if relative.as_posix() not in directories and not (allow_cache and '__pycache__' in relative.parts):
                raise ValueError('Unexpected directory in worker source tree')
        for name in files:
            path = no_links(Path(directory)/name)
            relative = path.relative_to(tree)
            if relative.as_posix() not in expected and not (allow_cache and '__pycache__' in relative.parts and path.suffix=='.pyc'):
                raise ValueError('Unexpected file in worker source tree')
    for name in expected:
        path = no_links(tree.joinpath(*relative_path(name).parts))
        if not path.is_file():
            raise ValueError('Incomplete extracted worker; preserve files and contact the owner')
        if name in bundle['files'] and sha(path.read_bytes())!=bundle['files'][name]:
            raise ValueError('An extracted worker source changed')
    if sha((tree/'bundle.json').read_bytes())!=config['bundle_sha256']:
        raise ValueError('Extracted worker manifest changed')
    if (tree/'bundle.sha256').read_bytes() not in tuple((config['bundle_sha256']+ending).encode('ascii') for ending in ('\n','\r\n')):
        raise ValueError('Extracted worker manifest sidecar changed')


def _promote_staging(root,staging,worker,bundle,config,platform_name=None,rename=None,sleep=None):
    """Exclusive Windows activation; retry only native access/sharing errors.

    Injection parameters are deterministic test hooks, never delivery metadata.
    Every failure preserves the complete staging tree. No permissions change.
    """
    root,staging,worker = map(lambda value:Path(os.path.abspath(value)),(root,staging,worker))
    platform_name = os.name if platform_name is None else platform_name
    if rename is None:
        if os.name!='nt':
            # stdlib POSIX rename can replace an existing empty directory. This
            # Windows delivery must not claim that primitive is exclusive.
            raise ValueError('Exclusive worker activation requires the approved Windows platform; staging is preserved')
        rename = os.rename
    sleep = time.sleep if sleep is None else sleep
    for attempt in range(len(WINDOWS_RENAME_DELAYS)+1):
        no_links(root); no_links(staging); no_links(worker)
        if (staging.parent.resolve()!=root.resolve() or worker!=root/'worker'
                or not staging.name.startswith('.extract-')):
            raise ValueError('Staging activation escaped its intended delivery directory')
        if worker.exists() or worker.is_symlink():
            raise ValueError('Worker destination appeared; refusing to replace it. Staging is preserved.')
        # Revalidate all source bytes and aliases on EVERY retry, not only the
        # first extraction. The authoritative archive must also remain intact.
        inspect_payload(root/'worker_payload.zip',config)
        _validate_tree(staging,bundle,config,allow_cache=False)
        with zipfile.ZipFile(root/'worker_payload.zip') as zipped:
            for name in AUXILIARY:
                if (staging/name).read_bytes()!=zipped.read(name):
                    raise ValueError('Staged auxiliary source differs from its authoritative ZIP')
        try:
            rename(staging,worker)  # Windows rename NEVER replaces an existing destination.
            return
        except OSError as error:
            # A racing destination (even an empty directory) is not a transient
            # error. Refuse immediately rather than attempting a later overwrite.
            no_links(staging); no_links(worker)
            if worker.exists() or worker.is_symlink():
                raise ValueError('Worker destination appeared during activation; staging is preserved') from error
            retry = (platform_name=='nt' and getattr(error,'winerror',None) in WINDOWS_RETRY_ERRORS
                     and attempt<len(WINDOWS_RENAME_DELAYS))
            if not retry:
                raise OSError('Unable to activate worker sources; complete staging preserved at '+str(staging)) from error
            sleep(WINDOWS_RENAME_DELAYS[attempt])


def verify_package(root,config=None):
    root = no_links(root)
    config = load_config(root) if config is None else config
    bundle = inspect_payload(root/'worker_payload.zip',config)
    worker = root/'worker'
    no_links(worker)
    if not worker.exists():
        temporary = Path(tempfile.mkdtemp(prefix='.extract-',dir=root))
        with zipfile.ZipFile(root/'worker_payload.zip') as zipped:
            for item in zipped.infolist():
                target = temporary.joinpath(*relative_path(item.filename).parts)
                target.parent.mkdir(parents=True,exist_ok=True)
                with target.open('xb') as handle:
                    handle.write(zipped.read(item.filename))
        _promote_staging(root,temporary,worker,bundle,config)
    _validate_tree(worker,bundle,config,allow_cache=True)
    return worker,bundle


def verify_runtime(config,metadata=None):
    actual = runtime_metadata() if metadata is None else metadata
    if (actual['implementation']!='CPython' or re.fullmatch(r'3\.12\.(?:0|[1-9][0-9]*)',actual['version']) is None
            or fingerprint(actual)!=config['approved_runtime_fingerprint']):
        raise ValueError('This Python build is not the exact approved runtime. Select your previously qualified environment; nothing is installed.')
    return actual


@contextmanager
def delivery_lease(root):
    root = no_links(root)
    lock = no_links(root/'.delivery.lock')
    descriptor = os.open(lock,os.O_RDWR|os.O_CREAT,0o600)
    try:
        if os.fstat(descriptor).st_size==0:
            os.write(descriptor,b'\0'); os.fsync(descriptor)
        os.lseek(descriptor,0,os.SEEK_SET)
        try:
            if os.name=='nt':
                import msvcrt
                msvcrt.locking(descriptor,msvcrt.LK_NBLCK,1)
            else:
                import fcntl
                fcntl.flock(descriptor,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except OSError as error:
            raise ValueError('This delivery is already running; keep its existing window') from error
        yield
    finally:
        os.close(descriptor)


def choose_workers(root,config,cpu_count=None,requested=None):
    path = no_links(Path(root)/'job_settings.json')
    binding = context(config)
    if path.exists():
        if path.stat().st_size>65536:
            raise ValueError('Oversized saved job settings')
        saved = loads(path.read_bytes())
        workers = saved['workers']
        if (saved['context']!=binding or type(workers) is not int or not 1<=workers<=8
                or (requested is not None and requested!=workers)):
            raise ValueError('Saved worker count/context changed; resume this exact job unchanged')
        return workers
    if (Path(root)/'results/header.json').exists():
        raise ValueError('Saved job settings are missing from an existing result; do not guess a new worker count')
    cores = (os.cpu_count() or 1) if cpu_count is None else cpu_count
    workers = max(1,min(4,cores//2)) if requested is None else requested
    if type(workers) is not int or not 1<=workers<=8:
        raise ValueError('Use a bounded worker count from1 through8')
    with path.open('xb') as handle:
        handle.write(canonical(dict(context=binding,workers=workers,python_executable=str(Path(sys.executable).resolve())))+b'\n')
        handle.flush(); os.fsync(handle.fileno())
    return workers


def _load_worker_modules(worker):
    sys.path.insert(0,str(worker))
    from distributed_campaign import auth,protocol,roles
    for module,name in ((auth,'auth'),(protocol,'protocol'),(roles,'roles')):
        if Path(module.__file__).resolve()!=(worker/'distributed_campaign'/(name+'.py')).resolve():
            raise ValueError('A module was imported from another checkout')
    return auth,protocol,roles


def _select_credential(config):
    try:
        import tkinter
        from tkinter import filedialog
        window = tkinter.Tk(); window.withdraw()
        selected = filedialog.askopenfilename(title='Choose your separately supplied PRIVATE credential for '+config['slot']['slot_id'],filetypes=[('Private credential','*.json')])
        window.destroy()
        if not selected:
            raise ValueError('No credential selected; no work started')
        return Path(selected)
    except ImportError:
        return Path(input('Paste the full path to your separately supplied PRIVATE credential: ').strip().strip('"'))


def _credential(config,worker,event=print):
    auth,protocol,roles = _load_worker_modules(worker)
    private = Path(os.environ['LOCALAPPDATA'])/'ZoneRushPrivate'/('architecture-v2-'+config['slot']['slot_id'])
    path = private/'credential.json'
    if not path.exists():
        source = no_links(_select_credential(config))
        if source.stat().st_size>512*1024:
            raise ValueError('Credential file exceeds its size bound')
        transfer = loads(source.read_bytes())
        if {key:transfer.get(key) for key in ('slot_id','physical_slot_id')}!=config['slot']:
            raise ValueError('That credential belongs to another helper')
        event('First setup: copying your helper key into a dedicated account-private folder. The owner master is never included.')
        auth.import_credentials(source,private)
    credential = auth.load_credentials(path)
    if auth.public_identity(credential)!=config['slot']:
        raise ValueError('Cached private configuration belongs to another helper')
    return path,credential,(auth,protocol,roles)


def _progress(line,work_role,event):
    prefix = 'Completed full80-turn matches' if work_role=='play' else 'Completed independent full-game audits'
    match = re.match(re.escape(prefix)+r':(\d+)/(\d+);',line)
    if match:
        label = 'Completed original full matches' if work_role=='play' else 'Completed full-game replays (new games:0)'
        event('%s: %s/%s; owner acceptance pending; primary credited:0; CPU policy' % (label,*match.groups()))
    elif not line.startswith('{'):
        event(line.rstrip())


def stream_worker(command,cwd,event=print,environment=None,popen=None,work_role='play'):
    environment = dict(os.environ if environment is None else environment)
    for name in ('PYTHONPATH','PYTHONHOME','PYTHONINSPECT','PYTHONSAFEPATH'):
        environment.pop(name,None)
    factory = subprocess.Popen if popen is None else popen
    group = dict(creationflags=subprocess.CREATE_NEW_PROCESS_GROUP) if os.name=='nt' else dict(start_new_session=True)
    process = factory(command,cwd=cwd,env=environment,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,
                      text=True,encoding='utf8',errors='replace',bufsize=1,**group)
    try:
        for line in process.stdout:
            if len(line)>65536:
                raise ValueError('Unexpected oversized worker output')
            _progress(line,work_role,event)
        return process.wait()
    except BaseException:
        # A stream/UI error must not release this delivery lease while leaving
        # the owned coordinator running. Real workers get their own process
        # group so the stop signal also reaches their spawned actor children.
        if process.poll() is None:
            try:
                if os.name=='nt' and hasattr(process,'send_signal'):
                    process.send_signal(signal.CTRL_BREAK_EVENT)
                elif os.name!='nt' and getattr(process,'pid',None):
                    os.killpg(process.pid,signal.SIGTERM)
                else:
                    process.terminate()
                process.wait(timeout=15)
            except (OSError,subprocess.TimeoutExpired):
                process.kill()
                process.wait(timeout=10)
        raise
    finally:
        if hasattr(process.stdout,'close'):
            process.stdout.close()


def _export_results(root,config,bundle,credential,modules):
    auth,protocol,roles = modules
    results = no_links(Path(root)/'results')
    for name in RETURN_FILES:
        no_links(results/name)
    header = loads((results/'header.json').read_bytes())
    progress = loads((results/'progress.json').read_bytes())
    expected_games = config['expected_tasks'] if config['work_role']=='play' else 0
    expected_audits = config['expected_tasks'] if config['work_role']=='audit' else 0
    if (header['format']!=protocol.FORMAT or header['role']!=config['role']
            or header['campaign_id']!=config['campaign_id'] or type(header['generation']) is not int
            or header['generation']!=config['generation']
            or header['worker_primary_credit']!=0 or header['bmcts_audits']!=0
            or header['bundle_sha256']!=config['bundle_sha256'] or header['slot']!=config['slot']
            or header['work_role']!=config['work_role'] or header['shard_id']!=config['shard_id']
            or fingerprint(header['runtime'])!=config['approved_runtime_fingerprint']
            or progress['shard_id']!=config['shard_id'] or progress['bundle_sha256']!=config['bundle_sha256']
            or progress['work_role']!=config['work_role'] or progress['expected_tasks']!=config['expected_tasks']
            or progress['complete'] is not True or progress['completed_tasks']!=config['expected_tasks']
            or progress['completed_games']!=expected_games or progress['completed_full_game_audits']!=expected_audits
            or progress['worker_primary_credit']!=0 or progress['bmcts_audits']!=0
            or progress['cuda_used_by_policy'] is not False):
        raise ValueError('Returned result identity/runtime/count is incomplete')
    if auth.verify(credential,'distributed-worker-header/v2',header['authentication'],expected_slot=config['slot']['slot_id'])!=roles.header_payload(header):
        raise ValueError('Worker header authentication failed')
    path = results/'records.jsonl'
    if path.stat().st_size>min(256*1024*1024,config['expected_tasks']*131072):
        raise ValueError('Results exceed their assigned byte bound')
    digest,seen = hashlib.sha256(),set()
    assigned = {fixture['id'] for fixture in bundle['fixtures']}
    with path.open('rb') as handle:
        while True:
            line = handle.readline(131073)
            if not line:
                break
            if len(line)>131072 or not line.endswith(b'\n'):
                raise ValueError('Return only a complete bounded checkpoint')
            digest.update(line)
            entry = loads(line)
            record = entry['record']; identity = record['fixture']
            if identity not in assigned or identity in seen:
                raise ValueError('Duplicate or foreign result record')
            expected = roles.result_payload(bundle,header,record)
            if auth.verify(credential,'distributed-result/'+config['work_role']+'/v2',entry['authentication'],expected_slot=config['slot']['slot_id'])!=expected:
                raise ValueError('Result authentication failed')
            seen.add(identity)
    if seen!=assigned or digest.hexdigest()!=progress['records_sha256']:
        raise ValueError('Completed record coverage/hash differs')
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer,'w',compression=zipfile.ZIP_DEFLATED) as zipped:
        for name in RETURN_FILES:
            entry = zipfile.ZipInfo(name,date_time=(2026,1,1,0,0,0))
            entry.compress_type = zipfile.ZIP_DEFLATED
            zipped.writestr(entry,(results/name).read_bytes())
    body = buffer.getvalue()
    returned = no_links(Path(root)/('RETURN_TO_OWNER_'+config['slot']['slot_id']+'_'+config['work_role']+'_'+sha(body)[:16]+'.zip'))
    if returned.exists():
        if returned.read_bytes()!=body:
            raise ValueError('Existing return archive differs; preserve it and contact the owner')
        return returned
    descriptor,temporary_name = tempfile.mkstemp(prefix='.return-',dir=root)
    temporary = Path(temporary_name)
    if temporary.parent.resolve()!=Path(root).resolve() or returned.parent.resolve()!=Path(root).resolve():
        os.close(descriptor)
        raise ValueError('Return publication escaped its delivery directory')
    try:
        with os.fdopen(descriptor,'wb') as handle:
            handle.write(body); handle.flush(); os.fsync(handle.fileno())
        # Windows rename is exclusive; POSIX link gives the same no-overwrite
        # publication. The temporary file is always inside this verified folder.
        if os.name=='nt':
            os.rename(temporary,returned)
        else:
            os.link(temporary,returned)
            temporary.unlink()
    except FileExistsError:
        no_links(returned)
        if returned.read_bytes()!=body:
            raise ValueError('Return target was occupied during publication')
    finally:
        if temporary.exists():
            temporary.unlink()
    return returned


def run(root,check_only=False,requested_workers=None,event=print):
    root = no_links(root)
    with delivery_lease(root):
        config = load_config(root)
        worker,bundle = verify_package(root,config)
        verify_runtime(config)
        if check_only:
            return dict(package_verified=True,runtime_verified=True,work_role=config['work_role'],
                        expected_tasks=config['expected_tasks'],actor_calls=0,new_games=0,primary_credit=0)
        credential_path,credential,modules = _credential(config,worker,event)
        modules[2].authenticate_assignment(bundle,credential)  # Before any actor subprocess.
        workers = choose_workers(root,config,requested=requested_workers)
        label = 'original full matches' if config['work_role']=='play' else 'independent full-game replays (not new games)'
        event('Assigned: %d %s. CPU workers:%d. GPU is not used; owner acceptance is pending.' % (config['expected_tasks'],label,workers))
        command = [sys.executable,'-m','distributed_campaign.worker','--root',str(worker),
                   '--expected-manifest-sha',config['bundle_sha256'],'--output',str(root/'results'),
                   '--workers',str(workers),'--credentials',str(credential_path)]
        if stream_worker(command,worker,event,work_role=config['work_role']):
            raise ValueError('Worker stopped. Preserve this folder/results and rerun to resume after contacting the owner if needed.')
        returned = _export_results(root,config,bundle,credential,modules)
        event('Complete. Send ONLY '+str(returned)+'. Never send your private credential or ZoneRushPrivate folder.')
        return dict(return_zip=str(returned),work_role=config['work_role'],local_completed_tasks=config['expected_tasks'],
                    owner_acceptance_pending=True,primary_credit=0,cuda_used_by_policy=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=Path(__file__).resolve().parent)
    parser.add_argument('--check-package',action='store_true')
    parser.add_argument('--runtime-probe',action='store_true')
    parser.add_argument('--workers',type=int)
    args = parser.parse_args()
    if args.runtime_probe:
        verify_runtime(load_config(args.root))
        print('APPROVED_RUNTIME_MATCH')
    else:
        print(canonical(run(args.root,args.check_package,args.workers)).decode())


if __name__=='__main__':
    try:
        main()
    except Exception as error:
        print('STOPPED: '+str(error),file=sys.stderr)
        sys.exit(1)
