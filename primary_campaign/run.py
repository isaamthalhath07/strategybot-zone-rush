"""Execute real primary games, then independently regenerate every actor decision.

No GPU proxy policy or BMCTS search is used here. Bounded execution defaults to
one of the EIGHTY training generations in the immutable two-million-game plan.
The development/final maps remain reserved; their execution is not implemented
by this training runner and must not be claimed complete.
"""
import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
import json
import os
from pathlib import Path
import shutil
import time

from evolution import oversight, runner
from evolution.genomes import digest
from primary_campaign import core


def completed_lines(path):
    path = Path(path)
    if not path.exists():
        return []
    body = path.read_bytes()
    if body and not body.endswith(b'\n'):
        split = body.rfind(b'\n')+1
        tail = body[split:]
        backup = path.with_name(path.name+'.interrupted-'+digest(tail)+'.bin')
        core.atomic(backup, tail)
        with path.open('r+b') as handle:
            handle.truncate(split)
            handle.flush()
            os.fsync(handle.fileno())
        body = body[:split]
    return [oversight.strict_loads(line) for line in body.splitlines()]


def task_maps(registration):
    return ({candidate['sha256']: candidate for candidate in registration['candidates']},
            {fixture['id']: fixture for fixture in registration['fixtures']})


def checked_rows(stage, registration):
    candidates, fixtures = task_maps(registration)
    rows, seen = [], set()
    for row in completed_lines(Path(stage)/'games.jsonl'):
        key = row['fixture']
        if key not in fixtures or key in seen or row['candidate'] != fixtures[key]['candidate']:
            raise ValueError('Duplicate, foreign or reassigned primary result')
        runner.verify_row(row, candidates[row['candidate']], fixtures[key])
        rows.append(row)
        seen.add(key)
    return rows


def append(handle, value):
    handle.write(core.canonical(value)+b'\n')
    handle.flush()
    os.fsync(handle.fileno())


def execute_generation(directory, index, workers=6):
    directory = Path(directory).resolve()
    manifest, catalog = core.load_catalog(directory)
    registration = core.prepare_generation(directory, index)
    stage = directory/('train_%03d' % index)
    core.validate_registration(registration, manifest, catalog)
    rows = checked_rows(stage, registration)
    done = {row['fixture'] for row in rows}
    candidates, fixtures = task_maps(registration)
    if (stage/'summary.json').exists():
        summary = core.read_sealed(stage/'summary.json')
        if (len(rows) != len(fixtures) or summary['candidates'] != core.summarize(rows, registration)
                or summary['registration_sha256'] != digest((stage/'registration.json').read_bytes())
                or summary['games_sha256'] != digest((stage/'games.jsonl').read_bytes())):
            raise ValueError('Consumed primary summary differs from replayed evidence')
        return summary
    started, initial_count = time.perf_counter(), len(rows)
    with (stage/'games.jsonl').open('ab') as handle:
        with ProcessPoolExecutor(max_workers=workers, initializer=runner.init_worker) as pool:
            # Map-major order interleaves candidate assignments under changing
            # thermal/load conditions, rather than finishing one candidate first.
            futures = {pool.submit(runner.play_game, candidates[fixture['candidate']], fixture, registration['sources']): fixture
                       for fixture in registration['fixtures'] if fixture['id'] not in done}
            for future in as_completed(futures):
                fixture = futures[future]
                row = future.result()  # Never silently substitute an action/game.
                runner.verify_row(row, candidates[fixture['candidate']], fixture)
                append(handle, row)
                rows.append(row)
                if len(rows) % 100 == 0 or len(rows) == len(fixtures):
                    print('PRIMARY train%d: %d/%d actual games; independent acceptance pending' % (index, len(rows), len(fixtures)), flush=True)
    core.check_guards(manifest['guards'])
    elapsed = time.perf_counter()-started
    summary = dict(format=core.FORMAT, phase='train', generation=index, profile=manifest['profile'],
                   registration_sha256=digest((stage/'registration.json').read_bytes()),
                   games_sha256=digest((stage/'games.jsonl').read_bytes()), candidates=core.summarize(rows, registration),
                   games_completed=len(rows), actual_callbacks=len(rows)*320, bmcts_audits=0,
                   independent_acceptance_pending=True, promoted=False,
                   performance=dict(new_games=len(rows)-initial_count, wall_s=elapsed, workers=workers,
                                    new_games_per_s=(len(rows)-initial_count)/elapsed,
                                    games_jsonl_bytes=(stage/'games.jsonl').stat().st_size,
                                    projected_2m_games_jsonl_bytes=(stage/'games.jsonl').stat().st_size*2000000//len(rows),
                                    caveat='Projection covers game transcripts only; registrations, audits and backups need additional storage. CPU timings include this observed load; no GPU speedup claimed.'))
    return core.seal(stage/'summary.json', summary)


def audit_task(candidate, fixture, sources, row):
    outcome = oversight.audit_game(candidate, fixture, sources, row, regenerate=True)
    return dict(fixture=fixture['id'], candidate=candidate['sha256'], row_sha256=digest(core.canonical(row)),
                proof_kind='dual_referee_fresh_actor_regeneration', all_actors_regenerated=True,
                referee_sha256=oversight.REFEREE_SHA, engine_sha256=oversight.ENGINE_SHA,
                oversight_sha256=digest((core.ROOT/'evolution/oversight.py').read_bytes()), **outcome)


def validate_actor_audit(outcome, row):
    if (outcome['fixture'] != row['fixture'] or outcome['candidate'] != row['candidate']
            or outcome['row_sha256'] != digest(core.canonical(row))
            or outcome['proof_kind'] != 'dual_referee_fresh_actor_regeneration'
            or outcome['all_actors_regenerated'] is not True
            or outcome['referee_sha256'] != oversight.REFEREE_SHA or outcome['engine_sha256'] != oversight.ENGINE_SHA
            or outcome['oversight_sha256'] != digest((core.ROOT/'evolution/oversight.py').read_bytes())
            or type(outcome['callbacks_regenerated']) is not int or outcome['callbacks_regenerated'] != 320
            or type(outcome['public_memory_oracles']) is not int
            or not 80 <= outcome['public_memory_oracles'] <= 320 or outcome['public_memory_oracles'] % 80):
        raise ValueError('Actor audit proof is incomplete or belongs to another real game')


def audit_generation(directory, index, workers=6):
    directory = Path(directory).resolve()
    manifest, catalog = core.load_catalog(directory)
    stage = directory/('train_%03d' % index)
    registration = core.read_sealed(stage/'registration.json')
    core.validate_registration(registration, manifest, catalog)
    if (stage/'audit.json').exists():
        return core.validated_audit(stage)
    summary = core.read_sealed(stage/'summary.json')
    rows = checked_rows(stage, registration)
    if (len(rows) != len(registration['fixtures']) or summary['candidates'] != core.summarize(rows, registration)
            or summary['games_sha256'] != digest((stage/'games.jsonl').read_bytes())):
        raise ValueError('Cannot audit incomplete or changed generation')
    candidates, fixtures = task_maps(registration)
    by_fixture = {row['fixture']: row for row in rows}
    audits, done = [], set()
    for outcome in completed_lines(stage/'actor_audits.jsonl'):
        key = outcome['fixture']
        if (key not in by_fixture or key in done or outcome['candidate'] != by_fixture[key]['candidate']
                or outcome['row_sha256'] != digest(core.canonical(by_fixture[key]))
                or outcome['callbacks_regenerated'] != 320):
            raise ValueError('Independent audit checkpoint changed')
        validate_actor_audit(outcome, by_fixture[key])
        audits.append(outcome)
        done.add(key)
    with (stage/'actor_audits.jsonl').open('ab') as handle:
        with ProcessPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(audit_task, candidates[row['candidate']], fixtures[row['fixture']], registration['sources'], row): row['fixture']
                       for row in rows if row['fixture'] not in done}
            for future in as_completed(futures):
                outcome = future.result()  # Any divergence blocks the NEXT generation.
                validate_actor_audit(outcome, by_fixture[outcome['fixture']])
                append(handle, outcome)
                audits.append(outcome)
                if len(audits) % 100 == 0 or len(audits) == len(rows):
                    print('PRIMARY independent audit: %d/%d games regenerated in TWO referees' % (len(audits), len(rows)), flush=True)
    core.check_guards(manifest['guards'])
    approved = dict(format=core.FORMAT, approved=True, all_actors_regenerated=True,
                    campaign_id=manifest['campaign_id'], phase=registration['phase'],
                    generation=registration['generation'], profile=manifest['profile'],
                    registration_sha256=digest((stage/'registration.json').read_bytes()),
                    games_sha256=digest((stage/'games.jsonl').read_bytes()),
                    summary_sha256=digest((stage/'summary.json').read_bytes()),
                    actor_audits_sha256=digest((stage/'actor_audits.jsonl').read_bytes()),
                    games_audited=len(audits), callbacks_regenerated=sum(item['callbacks_regenerated'] for item in audits),
                    public_memory_oracles=sum(item['public_memory_oracles'] for item in audits),
                    primary_games_accepted=len(rows) if manifest['profile'] == 'full_primary' else 0,
                    audit_replays_are_new_primary_games=False, bmcts_audits=0, promoted=False,
                    oversight_sha256=digest((core.ROOT/'evolution/oversight.py').read_bytes()))
    core.seal(stage/'audit.json', approved)
    return core.validated_audit(stage)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, required=True)
    parser.add_argument('--seed', type=int, default=202611090001)
    parser.add_argument('--train-generations', type=int, default=1)
    parser.add_argument('--workers', type=int, default=6)
    parser.add_argument('--initialize-only', action='store_true')
    parser.add_argument('--prepare-only', action='store_true')
    args = parser.parse_args()
    if not 1 <= args.train_generations <= 80 or not 1 <= args.workers <= 24:
        parser.error('Require1..80 training generations and1..24 workers')
    manifest = core.create_catalog(args.directory, args.seed)
    print(json.dumps(dict(profile=manifest['profile'], requested_games=2000000,
                          scheduled_games=manifest['scheduled_games'], bounded_training_generations=args.train_generations,
                          disk_free_bytes=shutil.disk_usage(args.directory).free,
                          development_and_final='reserved; execution intentionally unavailable in this training runner',
                          bmcts_audits=0, promoted=False)), flush=True)
    if args.initialize_only:
        return
    for index in range(args.train_generations):
        core.prepare_generation(args.directory, index)
        if args.prepare_only:
            break
        execute_generation(args.directory, index, args.workers)
        audit_generation(args.directory, index, args.workers)


if __name__ == '__main__':
    main()
