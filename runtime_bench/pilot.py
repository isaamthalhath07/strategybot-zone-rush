"""Repeat recorded full games under another interpreter; never admits new games."""
import argparse
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
import copy
import cProfile
import gc
import hashlib
import json
import multiprocessing
import os
from pathlib import Path
import platform
import pstats
import statistics
import sys
import time

from evolution import runner
from tests import reference_engine as engine

ROOT = Path(__file__).resolve().parents[1]
HELPER_SHA256 = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
CONTRACT_KEYS = ('candidate', 'fixture', 'map_id', 'focal_seat', 'field', 'scores',
                 'focal_pw', 'focal_score', 'opponent_ids', 'actions', 'faults')
_TASKS, _SOURCES = None, None


def sha(body):
    return hashlib.sha256(body).hexdigest()


def metadata():
    return dict(implementation=platform.python_implementation(), python_version=platform.python_version(),
                full_version=sys.version, executable=sys.executable, executable_sha256=sha(Path(sys.executable).read_bytes()),
                platform=platform.platform(), processor=platform.processor(), logical_cores=os.cpu_count(),
                hash_seed=os.environ.get('PYTHONHASHSEED', 'random'),
                gc_threshold=getattr(gc, 'get_threshold', lambda: None)())


def load_tasks(stage, count):
    registration_body = (stage/'registration.json').read_bytes()
    if sha(registration_body) != (stage/'registration.sha256').read_text().strip():
        raise ValueError('Registered stage changed')
    registration = json.loads(registration_body)
    guards = dict(registration['guards'])
    guards.update({source['path']: source['sha256'] for source in registration['sources'].values()})
    guards.update({candidate['path']: candidate['sha256'] for candidate in registration['candidates']})
    for path, expected in guards.items():
        if sha(Path(path).read_bytes()) != expected:
            raise ValueError('Pinned experiment source changed: '+path)
    buckets = defaultdict(list)
    for fixture in registration['fixtures']:
        buckets[fixture['candidate'], fixture['field']].append(fixture)
    keys = sorted(buckets)
    selected = []
    for index in range(count):
        key = keys[index % len(keys)]
        fixtures = buckets[key]
        lap = index//len(keys)
        selected.append(fixtures[(lap*(len(fixtures)//2+1)) % len(fixtures)])
    if len({fixture['id'] for fixture in selected}) != len(selected):
        raise ValueError('Pilot task selection unexpectedly repeated a fixture')
    wanted = {fixture['id'] for fixture in selected}
    recorded = {}
    with (stage/'games.jsonl').open(encoding='utf8') as handle:
        for line in handle:
            row = json.loads(line)
            if row['fixture'] in wanted:
                recorded[row['fixture']] = row
    if set(recorded) != wanted:
        raise ValueError('Selected fixtures are not completed in the source campaign')
    candidates = {candidate['sha256']: candidate for candidate in registration['candidates']}
    tasks = [(candidates[fixture['candidate']], fixture, recorded[fixture['id']]) for fixture in selected]
    return registration, guards, tasks


def one_game(task, sources):
    candidate, fixture, expected = task
    start = time.perf_counter()
    cpu_start = time.process_time()
    actual = runner.play_game(candidate, fixture, sources)
    stop = time.perf_counter()
    cpu_stop = time.process_time()
    for key in CONTRACT_KEYS:
        if actual[key] != expected[key]:
            raise ValueError('Recorded CPython equivalence failed: %s fixture%s' % (key, fixture['id']))
    runner.verify_row(actual, candidate, fixture)
    return dict(fixture=fixture['id'], action_sha256=sha(runner.canonical(actual['actions'])),
                start=start, stop=stop, actor_ms=sum(rec['total_ms'] for rec in actual['timing']),
                max_call_ms=max(rec['max_ms'] for rec in actual['timing']),
                calls=sum(rec['calls'] for rec in actual['timing']), process_cpu_s=cpu_stop-cpu_start)


def worker_init(tasks, sources, warmup, barrier):
    global _TASKS, _SOURCES
    _TASKS, _SOURCES = tasks, sources
    runner.init_worker()
    for index in range(warmup):
        one_game(tasks[index % len(tasks)], sources)
    barrier.wait(timeout=60)


def worker_job(index):
    return one_game(_TASKS[index % len(_TASKS)], _SOURCES)


def clone_public(view):
    """Microbenchmark only: never substituted into the frozen runner."""
    board = [[engine.Cell(c.occupant, c.owner, c.is_upgraded, c.is_home,
                          c.is_frozen, c.base_points) for c in row] for row in view.board]
    return engine.View(board, view.bot_id, view.is_priority_token, list(view.legal_actions))


def profiles(task, sources, directory):
    profile = cProfile.Profile()
    profile.enable()
    one_game(task, sources)
    profile.disable()
    stats = pstats.Stats(profile)
    stats.dump_stats(str(directory/'one_game.prof'))
    rows = [dict(file=key[0], line=key[1], function=key[2], primitive_calls=value[0], calls=value[1],
                 self_s=value[2], cumulative_s=value[3]) for key, value in stats.stats.items()]
    find = lambda suffix, function: sum(row['cumulative_s'] for row in rows if row['file'].endswith(suffix) and row['function'] == function)
    public = engine.Game(base=task[1]['base']).views()[0]
    clones = [copy.deepcopy(public), clone_public(public)]
    if any(runner.signature(view) != runner.signature(public) for view in clones):
        raise ValueError('Structural-clone microbenchmark changed public fields')
    clones[1].board[0][0].owner = 99
    if public.board[0][0].owner == 99:
        raise ValueError('Structural clone shares mutable cells')
    micro = {}
    for name, function in [('generic_deepcopy', copy.deepcopy), ('structural_public_clone', clone_public)]:
        started = time.perf_counter()
        for _ in range(1000):
            function(public)
        micro[name+'_1000_s'] = time.perf_counter()-started
    payload = runner.canonical(task[2])+b'\n'
    started = time.perf_counter()
    for _ in range(1000):
        runner.canonical(task[2])
    micro['serialize1000_s'] = time.perf_counter()-started
    started = time.perf_counter()
    for _ in range(1000):
        sha(payload)
    micro['hash1000_s'] = time.perf_counter()-started
    with (directory/'fsync_test.jsonl').open('wb') as handle:
        started = time.perf_counter()
        for _ in range(50):
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        micro['append_flush_fsync50_s'] = time.perf_counter()-started
    return dict(instrumented_profile_not_throughput=True,
                categories=dict(deepcopy_s=find('copy.py', 'deepcopy'),
                                referee_step_s=find('reference_engine.py', 'step'),
                                views_s=find('reference_engine.py', 'views'),
                                namespace_s=find('runner.py', 'namespace'),
                                signature_s=find('runner.py', 'signature')),
                top_self=sorted(rows, key=lambda row: -row['self_s'])[:25],
                top_cumulative=sorted(rows, key=lambda row: -row['cumulative_s'])[:25],
                microbench=micro, structural_clone_used_by_actual_runner=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--tasks', type=int, default=64)
    parser.add_argument('--warmup', type=int, default=24)
    parser.add_argument('--repeats', type=int, default=2)
    parser.add_argument('--workers', type=int, default=1)
    parser.add_argument('--profile', action='store_true')
    args = parser.parse_args()
    if not 1 <= args.workers <= 2 or not 1 <= args.tasks <= 128 or not 0 <= args.warmup <= 64 or not 1 <= args.repeats <= 3:
        parser.error('Bounded pilot: workers1..2/tasks1..128/warmup0..64/repeats1..3')
    args.out.mkdir(parents=True, exist_ok=False)
    registration, guards, tasks = load_tasks(args.stage, args.tasks)
    warmup_start = time.perf_counter()
    results, blocks = [], []
    if args.workers == 1:
        runner.init_worker()
        for index in range(args.warmup):
            one_game(tasks[index % len(tasks)], registration['sources'])
        warmup_wall_s = time.perf_counter()-warmup_start
        for repeat in range(args.repeats):
            started = time.perf_counter()
            block = [one_game(task, registration['sources']) for task in tasks]
            blocks.append(dict(repeat=repeat, games=len(block), wall_s=time.perf_counter()-started))
            results.extend(block)
    else:
        context = multiprocessing.get_context('spawn')
        barrier = context.Barrier(args.workers)
        with ProcessPoolExecutor(max_workers=args.workers, mp_context=context, initializer=worker_init,
                                 initargs=(tasks, registration['sources'], args.warmup, barrier)) as pool:
            futures = [pool.submit(worker_job, index) for index in range(args.tasks*args.repeats)]
            results = [future.result() for future in as_completed(futures)]
        warmup_wall_s = min(row['start'] for row in results)-warmup_start
        blocks = [dict(repeat='combined_parallel', games=len(results),
                       wall_s=max(row['stop'] for row in results)-min(row['start'] for row in results))]
    profile = profiles(tasks[0], registration['sources'], args.out) if args.profile else None
    for path, expected in guards.items():
        if sha(Path(path).read_bytes()) != expected:
            raise ValueError('Pinned source changed during the interpreter pilot')
    timed_s = sum(block['wall_s'] for block in blocks)
    report = dict(runtime=metadata(), registration_sha256=sha((args.stage/'registration.json').read_bytes()),
                  task_ids=[task[1]['id'] for task in tasks], source_guards=guards,
                  warmup_games_per_worker=args.warmup, warmup_wall_s=warmup_wall_s,
                  timed_games=len(results), workers=args.workers, blocks=blocks,
                  timed_wall_s=timed_s, games_per_s=len(results)/timed_s,
                  action_vectors_compared=len(results)*80, callbacks=sum(row['calls'] for row in results),
                  actor_ms=sum(row['actor_ms'] for row in results),
                  game_process_cpu_s=sum(row['process_cpu_s'] for row in results),
                  median_game_wall_s=statistics.median(row['stop']-row['start'] for row in results),
                  max_call_ms=max(row['max_call_ms'] for row in results), profile=profile,
                  all_recorded_actions_equal=True, referee_memory_oracles_enforced=True,
                  primary_games_accepted=0, bmcts_audits=0, production_files_edited=False,
                  benchmark_helper_sha256=HELPER_SHA256,
                  caveat='Finite repeated-game interpreter parity/performance pilot under current concurrent system load; no new strength evidence or campaign credit.')
    (args.out/'report.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf8')
    (args.out/'game_metrics.json').write_text(json.dumps(results, indent=2)+'\n', encoding='utf8')
    print(json.dumps({key: value for key, value in report.items() if key not in ('source_guards', 'task_ids', 'profile')}, indent=2), flush=True)


if __name__ == '__main__':
    main()
