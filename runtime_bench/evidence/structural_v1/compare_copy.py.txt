"""Matched, uncredited full-game test of an explicitly versioned copy backend."""
import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
import hashlib
import json
import multiprocessing
from pathlib import Path
import statistics
import time

from runtime_bench import pilot
from runtime_bench import structural_runner_v1
from evolution import runner

ROOT = Path(__file__).resolve().parents[1]
HELPER_SHA256 = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
_BACKEND, _TASKS, _SOURCES = None, None, None


def backend(name):
    return runner if name == 'frozen' else structural_runner_v1


def one_game(selected_backend, task, sources):
    candidate, fixture, expected = task
    started, cpu_started = time.perf_counter(), time.process_time()
    actual = selected_backend.play_game(candidate, fixture, sources)
    game_finished, cpu_finished = time.perf_counter(), time.process_time()
    for key in pilot.CONTRACT_KEYS:
        if actual[key] != expected[key]:
            raise ValueError('Recorded full-game parity failed: '+key+' '+fixture['id'])
    selected_backend.verify_row(actual, candidate, fixture)
    return dict(fixture=fixture['id'], start=started, stop=time.perf_counter(),
                game_s=game_finished-started, process_cpu_s=cpu_finished-cpu_started,
                actor_ms=sum(rec['total_ms'] for rec in actual['timing']),
                max_call_ms=max(rec['max_ms'] for rec in actual['timing']),
                action_sha256=pilot.sha(runner.canonical(actual['actions'])), calls=320)


def initialize(name, tasks, sources, warmup, barrier):
    global _BACKEND, _TASKS, _SOURCES
    _BACKEND, _TASKS, _SOURCES = backend(name), tasks, sources
    _BACKEND.init_worker()
    for index in range(warmup):
        one_game(_BACKEND, tasks[index % len(tasks)], sources)
    barrier.wait(timeout=60)


def worker(index):
    return one_game(_BACKEND, _TASKS[index], _SOURCES)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--backend', choices=('frozen', 'structural-v1'), required=True)
    parser.add_argument('--tasks', type=int, default=64)
    parser.add_argument('--repeats', type=int, default=2)
    parser.add_argument('--warmup', type=int, default=8)
    parser.add_argument('--workers', type=int, default=1)
    args = parser.parse_args()
    if not 1 <= args.tasks <= 128 or not 1 <= args.repeats <= 3 or not 0 <= args.warmup <= 32 or args.workers not in (1, 2):
        parser.error('Bounded test requires tasks1..128/repeats1..3/warmup0..32/workers1..2')
    args.out.mkdir(parents=True, exist_ok=False)
    registration, guards, tasks = pilot.load_tasks(args.stage, args.tasks)
    experimental_files = [ROOT/'runtime_bench/structural_runner_v1.py', ROOT/'runtime_bench/public_copy_v1.py']
    experiment_guards = {str(path): pilot.sha(path.read_bytes()) for path in experimental_files}
    blocks, rows = [], []
    warm_started = time.perf_counter()
    if args.workers == 1:
        implementation = backend(args.backend)
        implementation.init_worker()
        for index in range(args.warmup):
            one_game(implementation, tasks[index % len(tasks)], registration['sources'])
        warm_wall = time.perf_counter()-warm_started
        for repeat in range(args.repeats):
            started = time.perf_counter()
            results = [one_game(implementation, task, registration['sources']) for task in tasks]
            blocks.append(dict(repeat=repeat, games=len(results), wall_s=time.perf_counter()-started))
            rows.extend(results)
    else:
        context = multiprocessing.get_context('spawn')
        barrier = context.Barrier(args.workers)
        with ProcessPoolExecutor(max_workers=args.workers, mp_context=context, initializer=initialize,
                                 initargs=(args.backend, tasks, registration['sources'], args.warmup, barrier)) as pool:
            for repeat in range(args.repeats):
                futures = [pool.submit(worker, index) for index in range(len(tasks))]
                results = [future.result() for future in as_completed(futures)]
                if repeat == 0:
                    warm_wall = min(row['start'] for row in results)-warm_started
                blocks.append(dict(repeat=repeat, games=len(results),
                                   wall_s=max(row['stop'] for row in results)-min(row['start'] for row in results)))
                rows.extend(results)
    for path, expected in dict(guards, **experiment_guards).items():
        if pilot.sha(Path(path).read_bytes()) != expected:
            raise ValueError('Source changed during controlled copy experiment')
    timed_wall = sum(block['wall_s'] for block in blocks)
    report = dict(runtime=pilot.metadata(), backend=args.backend, workers=args.workers,
                  baseline_runner_sha256=structural_runner_v1.BASE_RUNNER_SHA256,
                  experimental_sources=experiment_guards, source_guards=guards,
                  benchmark_helper_sha256=HELPER_SHA256, task_ids=[task[1]['id'] for task in tasks],
                  registration_sha256=pilot.sha((args.stage/'registration.json').read_bytes()),
                  warmup_games_per_worker=args.warmup, warmup_wall_s=warm_wall,
                  blocks=blocks, timed_games=len(rows), timed_wall_s=timed_wall,
                  games_per_s=len(rows)/timed_wall, callbacks=len(rows)*320,
                  action_vectors_compared=len(rows)*80, all_recorded_actions_equal=True,
                  actor_ms=sum(row['actor_ms'] for row in rows), process_cpu_s=sum(row['process_cpu_s'] for row in rows),
                  median_game_s=statistics.median(row['game_s'] for row in rows),
                  max_call_ms=max(row['max_call_ms'] for row in rows), memory_oracles_enforced=True,
                  original_source_edited=False, monkeypatch=False, primary_games_accepted=0, bmcts_audits=0,
                  migration_performed=False,
                  caveat='Full real-policy game generation and score verification; excludes dataset loading/disk append/independent audit. Finite repeated records under current concurrent system load.')
    (args.out/'report.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf8')
    (args.out/'game_metrics.json').write_text(json.dumps(rows, indent=2)+'\n', encoding='utf8')
    print(json.dumps({key: value for key, value in report.items()
                      if key not in ('task_ids', 'source_guards', 'experimental_sources')}, indent=2), flush=True)


if __name__ == '__main__':
    main()
