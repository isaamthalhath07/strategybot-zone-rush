"""Actual CPU play, runtime qualification and full independent audit roles.

Only the helper coordinator loads its own credential. Actor pool jobs receive
public task data and source hashes, never secret material; pools use spawn.
"""
import argparse
from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait
import multiprocessing
import os
from pathlib import Path
import time

from distributed_campaign import protocol as p, roles

_RUNNER, _ROOT, _SOURCES, _CANDIDATES, _BUNDLE = None, None, None, None, None
BEHAVIOR = ('candidate','fixture','map_id','focal_seat','field','scores','focal_pw','focal_score','opponent_ids','actions','faults')


def initialize(root, expected):
    global _RUNNER, _ROOT, _SOURCES, _CANDIDATES, _BUNDLE
    _ROOT = Path(root).resolve()
    _BUNDLE = p.verify_bundle(_ROOT, expected)
    from evolution import runner
    if Path(runner.__file__).resolve() != p.safe_path(_ROOT, 'evolution/runner.py'):
        raise ValueError('Run from the extracted package root, not another checkout')
    _RUNNER = runner
    _RUNNER.init_worker()
    _SOURCES = {name: dict(value, path=str(p.safe_path(_ROOT, value['path']))) for name, value in _BUNDLE['sources'].items()}
    _CANDIDATES = {value['sha256']: dict(value, path=str(p.safe_path(_ROOT, value['path']))) for value in _BUNDLE['candidates']}


def audit_record(fixture, row):
    from evolution import oversight
    if Path(oversight.__file__).resolve() != p.safe_path(_ROOT, 'evolution/oversight.py'):
        raise ValueError('Independent auditor source belongs to another checkout')
    result = oversight.audit_game(_CANDIDATES[fixture['candidate']], fixture, _SOURCES, row, regenerate=True)
    return dict(fixture=fixture['id'], candidate=fixture['candidate'], row_sha256=p.sha(p.canonical(row)),
                proof_kind='dual_referee_fresh_actor_regeneration', all_actors_regenerated=True,
                referee_sha256=oversight.REFEREE_SHA, engine_sha256=oversight.ENGINE_SHA,
                oversight_sha256=p.sha(p.safe_path(_ROOT, 'evolution/oversight.py').read_bytes()), **result)


def do_task(fixture):
    kind = _BUNDLE.get('work_role', 'play')
    if kind == 'audit':
        creator = _BUNDLE['creators'][fixture['id']]
        if creator['physical_slot_id'] == _BUNDLE['target_slot']['physical_slot_id']:
            raise ValueError('A physical slot cannot audit its own played game')
        return audit_record(fixture, _BUNDLE['input_rows'][fixture['id']])
    row = _RUNNER.play_game(_CANDIDATES[fixture['candidate']], fixture, _SOURCES)
    _RUNNER.verify_row(row, _CANDIDATES[fixture['candidate']], fixture)
    if kind == 'qualify':
        expected = _BUNDLE['expected_rows'][fixture['id']]
        if any(row[key] != expected[key] for key in BEHAVIOR):
            raise ValueError('This actual runtime does not reproduce the canonical qualification game')
        return dict(game=row, audit=audit_record(fixture, row))
    if kind != 'play':
        raise ValueError('Unknown worker role')
    return row


def record_id(kind, record):
    return record['game']['fixture'] if kind == 'qualify' else record['fixture']


def verify_record(kind, record, fixture):
    if kind in ('play', 'qualify'):
        row = record['game'] if kind == 'qualify' else record
        _RUNNER.verify_row(row, _CANDIDATES[fixture['candidate']], fixture)
        if kind == 'qualify' and any(row[key] != _BUNDLE['expected_rows'][fixture['id']][key] for key in BEHAVIOR):
            raise ValueError('Qualification result differs from canonical recorded behavior')
    if kind in ('audit', 'qualify'):
        proof = record['audit'] if kind == 'qualify' else record
        row = record['game'] if kind == 'qualify' else _BUNDLE['input_rows'][fixture['id']]
        if (proof['fixture'] != fixture['id'] or proof['candidate'] != fixture['candidate']
                or proof['row_sha256'] != p.sha(p.canonical(row)) or proof['callbacks_regenerated'] != 320
                or proof['all_actors_regenerated'] is not True):
            raise ValueError('Incomplete or foreign full-game audit')


def execute(root, expected, output, workers=2, limit=None, credentials=None, secure_credentials=False):
    with p.ResultLease(output):
        return _execute_locked(root, expected, output, workers, limit, credentials, secure_credentials)


def _execute_locked(root, expected, output, workers=2, limit=None, credentials=None, secure_credentials=False):
    root, output = Path(root).resolve(), Path(output).resolve()
    if type(workers) is not int or not 1 <= workers <= 8 or (limit is not None and (type(limit) is not int or limit <= 0)):
        raise ValueError('Use1..8 CPU workers and a positive optional per-run limit')
    bundle = p.verify_bundle(root, expected)
    current, kind = p.runtime(), bundle.get('work_role', 'play')
    shadow = bundle['role'] == 'mechanics_shadow'
    credential = None
    if shadow:
        if any(current[key] != bundle['owner_runtime'][key] for key in ('implementation','version','full_version')):
            raise ValueError('Unsigned shadow tests require the reference runtime')
    else:
        from distributed_campaign import auth
        if credentials is None:
            raise ValueError('An owner-provisioned private helper credential is required')
        if secure_credentials:
            auth.secure_credentials(credentials)
        credential = auth.load_credentials(credentials)
        roles.authenticate_assignment(bundle, credential)
        if kind == 'qualify':
            if not roles.allowed_qualification_runtime(current):
                raise ValueError('This qualification tier tests CPython3.12.x only; no3.11/3.13 equivalence is assumed')
        elif roles.runtime_fingerprint(current) != roles.runtime_fingerprint(bundle['approved_runtime']):
            raise ValueError('Run this runtime qualification first; do not reinstall Python globally')
    if current['implementation'] != 'CPython':
        raise ValueError('The current actual policy worker is CPython CPU')
    output.mkdir(parents=True, exist_ok=True)
    header = dict(format=p.FORMAT, bundle_sha256=expected, shard_id=bundle['shard_id'],
                  campaign_id=bundle['campaign_id'], generation=bundle['generation'], role=bundle['role'],
                  work_role=kind, runtime=current, workers=workers, worker_primary_credit=0, bmcts_audits=0)
    if not shadow:
        header['slot'] = auth.public_identity(credential)
        header['authentication'] = auth.sign(credential, 'distributed-worker-header/v2', roles.header_payload(header))
    p.json_new(output/'header.json', header)
    initialize(root, expected)
    fixtures = {fixture['id']: fixture for fixture in bundle['fixtures']}
    result_path = output/('games.jsonl' if shadow else 'records.jsonl')
    stored = p.complete_rows(result_path, recover=True)
    records, done = [], set()
    for entry in stored:
        record = entry if shadow else entry['record']
        if not shadow:
            value = auth.verify(credential, 'distributed-result/'+kind+'/v2', entry['authentication'],
                                expected_slot=header['slot']['slot_id'])
            if value != roles.result_payload(bundle, header, record):
                raise ValueError('Signed checkpoint does not match its assignment/runtime/record')
        identity = record_id(kind, record)
        if identity not in fixtures or identity in done:
            raise ValueError('Checkpoint has duplicate or unassigned work')
        verify_record(kind, record, fixtures[identity])
        records.append(record)
        done.add(identity)
    pending = [fixture for fixture in bundle['fixtures'] if fixture['id'] not in done]
    if limit is not None:
        pending = pending[:limit]
    started, iterator = time.perf_counter(), iter(pending)
    with result_path.open('ab') as handle:
        with ProcessPoolExecutor(max_workers=workers, mp_context=multiprocessing.get_context('spawn'),
                                 initializer=initialize, initargs=(str(root), expected)) as pool:
            futures = {}
            def submit_one():
                fixture = next(iterator, None)
                if fixture is not None:
                    futures[pool.submit(do_task, fixture)] = fixture
                    return True
                return False
            for _ in range(min(len(pending), workers*2)):
                submit_one()
            try:
                while futures:
                    finished, _ = wait(futures, return_when=FIRST_COMPLETED)
                    for future in finished:
                        fixture = futures.pop(future)
                        record = future.result()
                        verify_record(kind, record, fixture)
                        entry = record if shadow else dict(record=record, authentication=auth.sign(
                            credential, 'distributed-result/'+kind+'/v2', roles.result_payload(bundle, header, record)))
                        handle.write(p.canonical(entry)+b'\n')
                        handle.flush()
                        os.fsync(handle.fileno())
                        records.append(record)
                        submit_one()
                        if len(records) % 50 == 0 or len(records) == len(bundle['fixtures']):
                            label = 'Completed full80-turn matches' if kind in ('play','qualify') else 'Completed independent full-game audits'
                            print('%s:%d/%d; owner acceptance pending; accepted primary:0; CPU policy' % (label,len(records),len(bundle['fixtures'])), flush=True)
            except BaseException:
                for future in futures:
                    future.cancel()  # Only at most2*workers jobs were in flight.
                raise
    p.verify_bundle(root, expected)
    report = dict(format=p.FORMAT, shard_id=bundle['shard_id'], bundle_sha256=expected, work_role=kind,
                  expected_tasks=len(bundle['fixtures']), completed_tasks=len(records), completed_games=len(records) if kind != 'audit' else 0,
                  completed_full_game_audits=len(records) if kind in ('audit','qualify') else 0,
                  this_run_tasks=len(pending), this_run_games=len(pending) if kind != 'audit' else 0,
                  this_run_wall_s=time.perf_counter()-started, records_sha256=p.sha(result_path.read_bytes()),
                  worker_primary_credit=0, bmcts_audits=0, cuda_used_by_policy=False, complete=len(records)==len(bundle['fixtures']))
    temporary = output/'progress.pending'
    with temporary.open('wb') as handle:
        handle.write(p.canonical(report)+b'\n'); handle.flush(); os.fsync(handle.fileno())
    os.replace(temporary, output/'progress.json')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--expected-manifest-sha', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--workers', type=int, default=2)
    parser.add_argument('--limit', type=int)
    parser.add_argument('--credentials', type=Path)
    parser.add_argument('--secure-credentials', action='store_true')
    args = parser.parse_args()
    result = execute(args.root,args.expected_manifest_sha,args.output,args.workers,args.limit,args.credentials,args.secure_credentials)
    print(p.canonical(result).decode(), flush=True)


if __name__ == '__main__':
    main()
