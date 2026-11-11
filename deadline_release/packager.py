"""Build a portable release from explicitly selected, byte-pinned local sources.

This tool selects nothing and performs no strength evaluation.  It never calls
Git or changes a source file.  The default validation uses no worker games.
"""
import argparse
import ast
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
import time
import zipfile

ROOT = Path(__file__).resolve().parents[1]
HERE = Path(__file__).resolve().parent
FORMAT = 'deadline-portable-release/1'
RULES = dict(frozen_stay_counts=False, claim_resets_progress=True,
             catch_requires_stay=True, lost_contest_is_stay=True,
             home_upgradable=True, legal_excludes_occupied=False)
RUNTIME = (
    'simulator/__init__.py', 'simulator/server.py', 'simulator/history.py',
    'simulator/README.md', 'simulator/.gitignore',
    'simulator/static/app.js', 'simulator/static/index.html', 'simulator/static/style.css',
    'simulator/vendor_harness/worker.py', 'simulator/vendor_harness/sources.py',
    'simulator/vendor_harness/referee.py', 'simulator/vendor_harness/match.py',
    'simulator/vendor_harness/provenance.json', 'tests/__init__.py',
    'tests/reference_engine.py', 'tests/reference_engine.provenance.json',
    'tests/test_rules.py', 'tests/test_simulator_catalog.py',
    'tests/test_simulator_server.py', 'tests/test_simulator_history.py',
    'tests/test_simulator_guards.py', 'tests/test_simulator_views.py',
)
TEMPLATES = {
    'portable_tests.py': 'tests/test_portable_release.py',
    'portable_check.py': 'tools/check_release.py',
    'portable_smoke.py': 'tools/smoke_release.py', 'play.py': 'play.py',
}
SECRET_KEYS = frozenset(('private_key', 'owner_key', 'master_key', 'password',
    'access_token', 'api_key', 'client_secret', 'credentials', 'hmac_key',
    'record_key', 'registry_key', 'secret_key'))


def sha(body):
    return hashlib.sha256(body).hexdigest()


def encoded(value):
    return (json.dumps(value, sort_keys=True, indent=2, allow_nan=False)+'\n').encode('utf8')


def digest(value):
    if type(value) is not str or re.fullmatch('[0-9a-f]{64}', value) is None:
        raise ValueError('Expected an exact lowercase SHA-256')
    return value


def relative(name):
    if type(name) is not str or '\\' in name or ':' in name:
        raise ValueError('Invalid portable relative path')
    path = PurePosixPath(name)
    if path.is_absolute() or not path.parts or any(p in ('', '.', '..') for p in path.parts):
        raise ValueError('Invalid portable relative path')
    return path.as_posix()


def no_secrets(value):
    if isinstance(value, dict):
        for key, item in value.items():
            if type(key) is not str or key.lower() in SECRET_KEYS:
                raise ValueError('Private credentials must not enter a release')
            no_secrets(item)
    elif isinstance(value, (list, tuple)):
        for item in value: no_secrets(item)
    elif isinstance(value, str) and re.search(r'-----BEGIN (?:[A-Z]+ )?PRIVATE KEY',value):
        raise ValueError('Private key material must not enter a release')


def policy(body):
    tree = ast.parse(body)
    if not any(isinstance(n, ast.FunctionDef) and n.name == 'act'
               for n in tree.body):
        raise ValueError('Selected policy must define top-level act(state)')
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names = [a.name.split('.')[0] for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            if node.level or node.module is None:
                raise ValueError('Policy must be standalone; no relative imports')
            names = [node.module.split('.')[0]]
        else:
            continue
        if set(names)-sys.stdlib_module_names:
            raise ValueError('Policy imports a non-standard-library dependency')


def pinned(path, expected):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise ValueError('Pinned input must be a regular local file')
    path=path.resolve()
    body = path.read_bytes()
    if sha(body) != digest(expected):
        raise ValueError('Pinned input bytes changed: '+path.name)
    return path, body


def source_pins():
    """Exact packager, template and portable runtime closure, without Git."""
    paths = {name: ROOT/name for name in RUNTIME}
    paths.update({'deadline_release/'+n: HERE/n for n in ('__init__.py', 'packager.py', *TEMPLATES)})
    return {name: sha(path.read_bytes()) for name, path in sorted(paths.items())}


def _write(directory, name, body):
    name = relative(name); path = directory/name
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb') as stream: stream.write(body)


def _seal(directory, manifest):
    body = encoded(manifest)
    # The manifest excludes itself and its sidecar, preventing recursive hashes.
    (directory/'package_manifest.json').write_bytes(body)
    (directory/'package_manifest.json.sha256').write_text(sha(body)+'\n', encoding='ascii')


def _readme(selected, status, note):
    return ('''# Zone Rush portable release

Use Python 3.12. No installation, Git, Torch, NumPy or network connection is required.
Run `python play.py` (or double-click `play.cmd` on Windows), then open
http://127.0.0.1:8779/. Three separate copies of the selected bot play against you.
The menu also offers the explicitly retained tester bots.

Run `python -I -S -B tools/check_release.py` for the packaged rules, public-input,
catalog, recording and interface checks. These checks execute one opening per
source but no full policy games. An optional explicit process smoke is
`python -I -S -B tools/smoke_release.py --games 1`; this is a control/interface
check, not evidence that the bot is strongest. Its output and complete turn
recording are saved under `validation/`.

New games use the official STAY-only Shield interpretation. A moving rival
escapes; a blocked move counts as STAY. The simulator is a bundled local
reference, and the competition server remains authoritative. AI view exposes
only the four documented public fields. Ordinary play records observer history
under `simulator/history/`; that history is never supplied to bots.

`bot.py` and each tester are copied byte for byte. `release_manifest.json` pins
the selectable sources. `package_manifest.json` pins the shipped files, tool
closure and supplied public decision evidence. Local future play, snapshots,
and later validation reports are intentionally outside the original file map.
The research history remains in the development repository, outside this compact
runtime package. No selection or new research credit is created by packaging.

Selection status: **%s**. Selected source SHA-256: `%s`.

%s
''' % (status, selected, note)).encode('utf8')


def build_release(selected_source_path, selected_sha256, tester_entries, output_directory,
                  *, selection_note='Reference packaging check; no final selection.',
                  decision_manifest=None, evidence_entries=(), validate=True):
    """Copy exact bodies into a fresh folder; return its verified manifest.

    Each tester/evidence entry is {path, sha256, label}; testers may also name
    a safe filename. A final_selection decision must bind this SHA and supplied
    public evidence. This is a caller declaration, not an inferred strength claim.
    """
    if type(validate) is not bool or type(selection_note) is not str or not selection_note.strip():
        raise ValueError('Explicit validation setting and selection note required')
    selected_path, selected = pinned(selected_source_path, selected_sha256); policy(selected)
    if type(tester_entries) not in (list, tuple) or len(tester_entries)>32:
        raise ValueError('Expected at most32 explicit testers')
    if decision_manifest is not None and type(decision_manifest) is not dict:
        raise ValueError('Decision must be a plain JSON object')
    if type(evidence_entries) not in (list,tuple) or len(evidence_entries)>64:
        raise ValueError('Expected at most64 explicitly public evidence files')
    decision = dict(decision_manifest if decision_manifest is not None else dict(status='reference_only', selected_source_sha256=selected_sha256))
    no_secrets(decision)
    if decision.get('status') not in ('reference_only', 'final_selection') or decision.get('selected_source_sha256') != selected_sha256:
        raise ValueError('Decision must bind the selected source and its status')
    if decision['status']=='final_selection' and (not validate or not evidence_entries):
        raise ValueError('Final selection requires validation and explicit pinned public decision evidence')
    inputs = [(selected_path, selected)]; payload = {'bot.py': selected}; testers=[]; seen={selected_sha256}
    for entry in tester_entries:
        if type(entry) is not dict or set(entry)-{'path','sha256','label','filename'}:
            raise ValueError('Unknown tester fields')
        path, body = pinned(entry['path'], entry['sha256']); policy(body)
        filename=entry.get('filename', path.name)
        if type(filename) is not str or re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]*\.py',filename) is None:
            raise ValueError('Unsafe tester filename')
        name='tester_bots/'+filename; label=entry.get('label',path.stem)
        if type(label) is not str or not label.strip() or len(label)>160:
            raise ValueError('Invalid tester label')
        if name in payload or entry['sha256'] in seen:
            raise ValueError('Duplicate tester source or filename')
        payload[name]=body; seen.add(entry['sha256']); inputs.append((path,body))
        testers.append(dict(path=name,sha256=entry['sha256'],label=label))
    public_evidence=[]
    for index, entry in enumerate(evidence_entries):
        if type(entry) is not dict or set(entry)-{'path','sha256','label'}:
            raise ValueError('Unknown evidence fields')
        path, body=pinned(entry['path'],entry['sha256'])
        if path.suffix.lower() not in ('.json','.jsonl','.md','.txt') or len(body)>32*1024*1024:
            raise ValueError('Only bounded, explicitly public text evidence is accepted')
        text=body.decode('utf8'); no_secrets(text)
        if path.suffix.lower()=='.json': no_secrets(json.loads(text))
        if path.suffix.lower()=='.jsonl':
            for line in text.splitlines():
                if line.strip(): no_secrets(json.loads(line))
        filename=re.sub('[^A-Za-z0-9_.-]','_',path.name)
        name='validation/evidence/%03d_%s'%(index,filename)
        payload[name]=body; inputs.append((path,body))
        public_evidence.append(dict(path=name,sha256=entry['sha256'],label=entry.get('label',path.name)))
    no_secrets(public_evidence); no_secrets(selection_note)
    closure=source_pins()
    for name in RUNTIME:
        body=(ROOT/name).read_bytes()
        if sha(body)!=closure[name]: raise ValueError('Runtime bytes changed before copying')
        payload[name]=body
    for name,target in TEMPLATES.items():
        body=(HERE/name).read_bytes()
        if sha(body)!=closure['deadline_release/'+name]: raise ValueError('Template bytes changed before copying')
        payload[target]=body
    for name in ('__init__.py','packager.py',*TEMPLATES):
        body=(HERE/name).read_bytes()
        if sha(body)!=closure['deadline_release/'+name]: raise ValueError('Tool bytes changed before copying')
        payload['validation/packager_sources/'+name]=body
    payload['tester_bots/__init__.py']=b''
    payload['play.cmd']=b'@echo off\r\ncd /d "%~dp0"\r\npython play.py %*\r\n'
    payload['README.md']=_readme(selected_sha256,decision['status'],selection_note)
    payload['validation/selection.json']=encoded(dict(decision=decision,note=selection_note,evidence=public_evidence))
    release=dict(format='zone-rush-consolidated-release/1',bot_sha256=selected_sha256,
        policy='exact_selected_source',rules=RULES,tester_bots=testers,recommendation=selection_note,
        source=dict(name=selected_path.stem,sha256=selected_sha256,status=decision['status']))
    payload['release_manifest.json']=encoded(release)
    destination=Path(output_directory).resolve()
    if destination.exists(): raise FileExistsError('Output must be fresh; preserve existing success/failure evidence')
    destination.mkdir(parents=True,exist_ok=False)
    manifest=dict(format=FORMAT,selected_source_sha256=selected_sha256,selection_status=decision['status'],
        python_requirement='3.12',runtime_dependencies='Python standard library only',source_pins=closure,
        public_evidence=public_evidence,files={},validation=dict(status='not_run',ordinary_worker_games=0,primary_games=0))
    try:
        for name,body in payload.items(): _write(destination,name,body)
        manifest['files']={name:sha(body) for name,body in sorted(payload.items())}; _seal(destination,manifest)
        if validate:
            began=time.perf_counter()
            temporary=destination/'validation'/'temporary'; temporary.mkdir()
            environment=dict(os.environ,TMP=str(temporary),TEMP=str(temporary))
            result=subprocess.run([sys.executable,'-I','-S','-B',str(destination/'tools/check_release.py'),
                '--output','validation/build_validation.json'],cwd=destination,capture_output=True,text=True,timeout=180,env=environment)
            _write(destination,'validation/build_validation.log',(result.stdout+result.stderr).encode('utf8'))
            report=json.loads((destination/'validation/build_validation.json').read_bytes())
            manifest['validation']=dict(status='passed' if result.returncode==0 and report['passed'] else 'failed',
                tests=report['tests'],wall_seconds=time.perf_counter()-began,ordinary_worker_games=0,primary_games=0,
                report='validation/build_validation.json')
            for name in ('validation/build_validation.log','validation/build_validation.json'):
                manifest['files'][name]=sha((destination/name).read_bytes())
            _seal(destination,manifest)
            if manifest['validation']['status']!='passed': raise ValueError('Portable validation failed; evidence preserved')
        for path,body in inputs:
            if path.read_bytes()!=body: raise ValueError('Input changed during packaging: '+path.name)
        if source_pins()!=closure: raise ValueError('Packaging/runtime source closure changed during build')
        return verify_release(destination)
    except BaseException as error:
        (destination/'packaging_error.json').write_bytes(encoded(dict(format='portable-packaging-error/1',
            exception_type=type(error).__name__,message=str(error),selected_source_sha256=selected_sha256,primary_games=0)))
        raise


def verify_release(directory):
    """Read-only byte/manifest verification; no actors, subprocesses or physics."""
    directory=Path(directory).resolve(); body=(directory/'package_manifest.json').read_bytes()
    if (directory/'package_manifest.json.sha256').read_text(encoding='ascii').strip()!=sha(body):
        raise ValueError('Package manifest seal mismatch')
    manifest=json.loads(body)
    if manifest.get('format')!=FORMAT or not isinstance(manifest.get('files'),dict): raise ValueError('Invalid package manifest')
    if (directory/'packaging_error.json').exists(): raise ValueError('Package has preserved build failure')
    for name,expected in manifest['files'].items():
        path=(directory/relative(name)).resolve()
        if not path.is_relative_to(directory) or path.is_symlink() or sha(path.read_bytes())!=digest(expected):
            raise ValueError('Package file fingerprint mismatch: '+name)
    release=json.loads((directory/'release_manifest.json').read_bytes())
    if encoded(release['rules'])!=encoded(RULES) or release['bot_sha256']!=manifest['selected_source_sha256']:
        raise ValueError('Chosen source/rule manifest disagreement')
    required={'bot.py','release_manifest.json','README.md','play.py',*RUNTIME,*TEMPLATES.values()}
    if not required.issubset(manifest['files']): raise ValueError('Portable runtime closure incomplete')
    for name in RUNTIME:
        if manifest['files'][name]!=manifest['source_pins'].get(name): raise ValueError('Runtime source provenance mismatch')
    for name,target in TEMPLATES.items():
        if manifest['files'][target]!=manifest['source_pins'].get('deadline_release/'+name): raise ValueError('Template source provenance mismatch')
    for name in ('__init__.py','packager.py',*TEMPLATES):
        if manifest['files'].get('validation/packager_sources/'+name)!=manifest['source_pins'].get('deadline_release/'+name):
            raise ValueError('Archived packager source provenance mismatch')
    seen=set()
    for name,expected in [('bot.py',release['bot_sha256'])]+[(e['path'],e['sha256']) for e in release['tester_bots']]:
        if name!='bot.py' and re.fullmatch(r'tester_bots/[A-Za-z0-9][A-Za-z0-9_-]*\.py',name) is None:
            raise ValueError('Invalid tester manifest path')
        if expected in seen or manifest['files'].get(name)!=expected: raise ValueError('Chosen source hash/catalog mismatch')
        seen.add(expected); policy((directory/name).read_bytes())
    provenance=json.loads((directory/'simulator/vendor_harness/provenance.json').read_bytes())
    for name,expected in provenance['files'].items():
        if manifest['files'].get('simulator/vendor_harness/'+relative(name))!=expected:
            raise ValueError('Vendored harness provenance mismatch')
    selection=json.loads((directory/'validation/selection.json').read_bytes()); no_secrets(selection)
    if (manifest['selection_status'] not in ('reference_only','final_selection')
            or selection['decision'].get('status')!=manifest['selection_status']
            or selection['decision'].get('selected_source_sha256')!=manifest['selected_source_sha256']
            or release['source'].get('status')!=manifest['selection_status']
            or encoded(selection['evidence'])!=encoded(manifest['public_evidence'])
            or selection['note']!=release['recommendation']):
        raise ValueError('Selection declaration disagreement')
    for entry in manifest['public_evidence']:
        if manifest['files'].get(entry['path'])!=entry['sha256']: raise ValueError('Public evidence source mismatch')
    if manifest['selection_status']=='final_selection' and (manifest['validation']['status']!='passed' or not manifest['public_evidence']):
        raise ValueError('Final selection lacks successful package validation')
    validation=manifest['validation']
    if type(validation.get('primary_games')) is not int or validation['primary_games']!=0 or type(validation.get('ordinary_worker_games')) is not int or validation['ordinary_worker_games']!=0:
        raise ValueError('Packaging cannot claim game credit')
    if validation['status']=='passed':
        report=json.loads((directory/validation['report']).read_bytes())
        if (report.get('passed') is not True or type(report.get('tests')) is not int or report['tests']!=validation['tests']
                or report['failures']!=0 or report['errors']!=0 or report['skipped']!=0 or report['ordinary_worker_games']!=0 or report['primary_games']!=0):
            raise ValueError('Package validation receipt disagreement')
    if 'smoke' in manifest:
        smoke=manifest['smoke']; prior=(directory/smoke['pre_smoke_manifest']).read_bytes()
        if sha(prior)!=smoke['pre_smoke_manifest_sha256']: raise ValueError('Pre-smoke manifest mismatch')
        prior_header=json.loads(prior)
        if (prior_header.get('format')!=FORMAT or prior_header.get('selected_source_sha256')!=manifest['selected_source_sha256']
                or any(manifest['files'].get(n)!=h for n,h in prior_header['files'].items())
                or type(smoke.get('primary_games')) is not int or smoke['primary_games']!=0):
            raise ValueError('Pre-smoke source closure disagreement')
        names,report=_smoke_files(directory,smoke['report'],sha(prior),manifest['selected_source_sha256'])
        if type(smoke['ordinary_worker_games']) is not int or smoke['ordinary_worker_games']!=report['ordinary_worker_games'] or any(name not in manifest['files'] for name in names):
            raise ValueError('Smoke evidence closure incomplete')
    return manifest


def _smoke_files(directory, report_name, prior_sha, selected_sha):
    report_name=relative(report_name)
    if not report_name.startswith('validation/'): raise ValueError('Smoke report must be in validation/')
    report=json.loads((directory/report_name).read_bytes())
    count=report.get('ordinary_worker_games')
    if (report.get('format')!='portable-process-smoke/1' or report.get('passed') is not True
            or report.get('bot_sha256')!=selected_sha or report.get('package_manifest_sha256')!=prior_sha
            or type(count) is not int or count not in (1,2) or type(report.get('primary_games')) is not int
            or report['primary_games']!=0 or len(report.get('games',[]))!=count):
        raise ValueError('Smoke source, completion or credit receipt mismatch')
    names=[report_name]; identifiers=set()
    for game in report['games']:
        identifier=game['game_id']; name=relative(game['history_file'])
        if (re.fullmatch('[0-9a-f]{32}',identifier) is None or identifier in identifiers
                or name!='validation/smoke_history/'+identifier+'.jsonl'):
            raise ValueError('Invalid smoke history identity')
        identifiers.add(identifier); names.append(name); body=(directory/name).read_bytes()
        if sha(body)!=digest(game['history_sha256']): raise ValueError('Smoke history fingerprint mismatch')
        records=[json.loads(line) for line in body.decode('utf8').splitlines()]
        if len(records)!=82: raise ValueError('Smoke must contain opening,80 turns and completed ending')
        initial,ending=records[0],records[-1]; human=initial.get('human_seat')
        if (initial.get('type')!='start' or initial.get('game_id')!=identifier or initial.get('partial') is not False
                or initial.get('bot',{}).get('sha256')!=selected_sha or type(human) is not int or human not in range(1,5)
                or encoded(initial.get('rules'))!=encoded(RULES) or initial.get('max_turns')!=80
                or ending.get('type')!='end' or ending.get('reason')!='completed'):
            raise ValueError('Smoke history source/rules/completion mismatch')
        previous=initial['initial']; actual=0; maximum=0.
        for turn,record in enumerate(records[1:-1],1):
            if (record.get('type')!='turn' or type(record.get('turn')) is not int or record['turn']!=turn
                    or record.get('before')!=previous or record['after'].get('turn')!=turn+1
                    or len(record['used'])!=4 or len(record['bots'])!=4 or set(record['observations'])!={'1','2','3','4'}):
                raise ValueError('Smoke turn/tape/state chain mismatch')
            for seat in range(1,5):
                observation=record['observations'][str(seat)]
                if set(observation)!={'board','bot_id','is_priority_token','legal_actions'} or observation['bot_id']!=seat:
                    raise ValueError('Smoke public input boundary mismatch')
                if record['used'][seat-1] not in observation['legal_actions']: raise ValueError('Smoke illegal accepted action')
                if seat==human: continue
                callback=record['bots'][seat-1]; milliseconds=callback.get('ms')
                if (callback.get('status')!='ok' or callback.get('chosen')!=record['used'][seat-1]
                        or callback.get('used')!=record['used'][seat-1] or type(milliseconds) not in (int,float)
                        or not math.isfinite(milliseconds) or not 0<=milliseconds<=(2000 if turn==1 else 200)):
                    raise ValueError('Smoke actual callback/fallback/deadline mismatch')
                actual+=1; maximum=max(maximum,milliseconds)
            previous=record['after']
        if ending.get('final')!=previous or previous['turn']!=81: raise ValueError('Smoke terminal state mismatch')
        for key,value in dict(turns=80,actual_ai_callbacks=240,fresh_replay_callbacks=240,faults=0,dual_referee_turns=80).items():
            if type(game.get(key)) is not int or game[key]!=value: raise ValueError('Smoke measured coverage mismatch')
        if (actual!=240 or game.get('actual_max_callback_ms')!=maximum
                or type(game.get('supported_memory_oracle_checks')) is not int
                or not 0<=game['supported_memory_oracle_checks']<=240):
            raise ValueError('Smoke callback/oracle receipt mismatch')
    return names,report


def include_smoke_evidence(directory, report_path='validation/smoke_result.json'):
    """Seal an already completed explicit smoke, preserving its original manifest.

    This verifies recorded source/tape/count/deadline bindings; it executes no
    callback or new game. The source-bound smoke tool performed both CPU replays.
    """
    directory=Path(directory).resolve(); manifest=verify_release(directory)
    if 'smoke' in manifest: raise FileExistsError('A smoke receipt is already sealed')
    prior=(directory/'package_manifest.json').read_bytes()
    names,report=_smoke_files(directory,report_path,sha(prior),manifest['selected_source_sha256'])
    prior_name='validation/pre_smoke_package_manifest.json'
    _write(directory,prior_name,prior)
    manifest['files'][prior_name]=sha(prior)
    for name in names: manifest['files'][name]=sha((directory/name).read_bytes())
    manifest['smoke']=dict(report=relative(report_path),pre_smoke_manifest=prior_name,
        pre_smoke_manifest_sha256=sha(prior),ordinary_worker_games=report['ordinary_worker_games'],primary_games=0)
    _seal(directory,manifest)
    return verify_release(directory)


def make_zip(directory, archive_path):
    """Archive only sealed release payload; exclude live history and caches."""
    directory=Path(directory).resolve(); manifest=verify_release(directory); archive=Path(archive_path).resolve()
    names=sorted([*manifest['files'],'package_manifest.json','package_manifest.json.sha256'])
    if archive.exists(): raise FileExistsError('Archive must be fresh')
    archive.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(archive,'x',compression=zipfile.ZIP_DEFLATED) as stream:
        for name in names: stream.writestr(name,(directory/name).read_bytes())
    with zipfile.ZipFile(archive) as stream:
        if stream.namelist()!=names: raise ValueError('Archive filename mismatch')
        for name in names:
            if stream.read(name)!=(directory/name).read_bytes(): raise ValueError('Archive byte mismatch')
    verify_release(directory)
    return dict(path=str(archive),sha256=sha(archive.read_bytes()),files=len(names))


def main():
    parser=argparse.ArgumentParser(description=__doc__); sub=parser.add_subparsers(dest='command',required=True)
    build=sub.add_parser('build'); build.add_argument('--selected',required=True); build.add_argument('--sha256',required=True)
    build.add_argument('--testers-json',required=True); build.add_argument('--output',required=True)
    build.add_argument('--decision-json'); build.add_argument('--evidence-json'); build.add_argument('--note',required=True)
    verify=sub.add_parser('verify'); verify.add_argument('directory')
    archive=sub.add_parser('zip'); archive.add_argument('directory'); archive.add_argument('archive')
    smoke=sub.add_parser('seal-smoke'); smoke.add_argument('directory'); smoke.add_argument('--report',default='validation/smoke_result.json')
    args=parser.parse_args()
    if args.command=='build':
        result=build_release(args.selected,args.sha256,json.loads(Path(args.testers_json).read_bytes()),args.output,
            selection_note=args.note,decision_manifest=json.loads(Path(args.decision_json).read_bytes()) if args.decision_json else None,
            evidence_entries=json.loads(Path(args.evidence_json).read_bytes()) if args.evidence_json else ())
    elif args.command=='verify': result=verify_release(args.directory)
    elif args.command=='seal-smoke': result=include_smoke_evidence(args.directory,args.report)
    else: result=make_zip(args.directory,args.archive)
    print(json.dumps(result,sort_keys=True,indent=2))


if __name__=='__main__': main()
