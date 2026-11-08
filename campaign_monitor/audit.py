"""Bind live stage paths to their identities and derive disjoint coverage.

This structural monitor reuses the existing fully audited receipts. It does not
regenerate actors or substitute for the deep training gate/HMAC authority.
"""
import argparse
from collections import Counter
import json
import math
from pathlib import Path
import re
import time

from evolution import oversight
from evolution.genomes import digest
from primary_campaign import core, run


def require(condition, message):
    if not condition:
        raise ValueError(message)


def lines_snapshot(path):
    """Observe an active append without ever truncating or repairing it."""
    if not path.exists():
        return [], b'', 0
    body = path.read_bytes()
    committed_end = body.rfind(b'\n')+1
    committed = body[:committed_end]
    tail = len(body)-committed_end
    return [oversight.strict_loads(line) for line in committed.splitlines()], body, tail


def metadata_identity(value, index, manifest, label):
    require(type(value.get('generation')) is int and value['generation'] == index,
            '%s directory index differs from declared generation' % label)
    require(value.get('phase') == 'train' and value.get('profile') == manifest['profile'],
            '%s phase/profile changed' % label)


def unique_insert(seen, value, index, label):
    require(value not in seen, 'Global duplicate %s in stages%s/%s' % (label, seen.get(value), index))
    seen[value] = index


def check_row(row, fixture):
    require(row['candidate'] == fixture['candidate'] and row['fixture'] == fixture['id'], 'Actual task assignment changed')
    require(row['map_id'] == fixture['map_id'] and row['focal_seat'] == fixture['seat']
            and row['field'] == fixture['field'], 'Actual result metadata changed')
    require(row['opponent_ids'] == [spec['id'] for spec in fixture['opponents']] and row['faults'] == [],
            'Actual result rivals/faults changed')
    require(len(row['actions']) == 80 and all(len(actions) == 4 and all(type(a) is str and a in core.runner.engine.ACTIONS
            for a in actions) for actions in row['actions']), 'Actual game has incomplete/invalid action record')
    require(len(row['scores']) == 4 and all(type(value) is int for value in row['scores']), 'Actual score record invalid')
    seat = fixture['seat']
    pairwise = sum(1 if row['scores'][seat] > score else .5 if row['scores'][seat] == score else 0
                   for rival, score in enumerate(row['scores']) if rival != seat)
    require(row['focal_pw'] == pairwise and row['focal_score'] == row['scores'][seat], 'Actual ranking disagrees with scores')
    require(len(row['timing']) == 4, 'Missing callback records')
    for item in row['timing']:
        require(type(item['calls']) is int and item['calls'] == 80, 'Incomplete actual callback count')
        require(all(type(item[key]) in (int, float) and math.isfinite(item[key]) and item[key] >= 0
                    for key in ('first_ms', 'regular_max_ms', 'max_ms', 'total_ms')), 'Invalid actual callback timing')
        require(item['first_ms'] <= 2000 and item['regular_max_ms'] <= 200
                and item['max_ms'] == max(item['first_ms'], item['regular_max_ms'])
                and item['max_ms'] <= item['total_ms'] <= item['first_ms']+79*item['regular_max_ms']+1e-6,
                'Actual callback timing violates contract')


def inspect(directory):
    started = time.perf_counter()
    directory = Path(directory).resolve()
    manifest, catalog = core.load_catalog(directory)
    registry = sorted((int(match.group(1)), path) for path in directory.iterdir() if path.is_dir()
                      and (match := re.fullmatch(r'train_(\d{3})', path.name)))
    global_maps, global_tasks, global_rivals, global_seeds, actual_ids = {}, {}, {}, {}, {}
    results, prepared = [], []
    stage_size = manifest['shape']['maps_per_generation']
    training_maps = [board for board in catalog if board['phase'] == 'train']
    accepted, completed, approved_stages = 0, 0, []
    for index, stage in registry:
        require(index < manifest['training_generations'], 'Stage directory exceeds scheduled training')
        if not (stage/'registration.json').exists():
            require(not (stage/'games.jsonl').exists(), 'Unregistered stage contains actual games')
            results.append(dict(generation=index, status='preparation_incomplete', accepted_primary_games=0))
            continue
        registration = core.read_sealed(stage/'registration.json')
        metadata_identity(registration, index, manifest, 'registration')
        require(registration['campaign_id'] == manifest['campaign_id'], 'Registration belongs to another campaign')
        core.validate_registration(registration, manifest, catalog)
        prepared.append(index)
        expected_maps = {board['map_index']: board['id'] for board in training_maps[index*stage_size:(index+1)*stage_size]}
        registered_maps = {}
        fixtures = {}
        for fixture in registration['fixtures']:
            map_index = fixture['map_index']
            require(map_index in expected_maps and fixture['map_id'] == expected_maps[map_index], 'Stage uses wrong catalog slice')
            if map_index not in registered_maps:
                unique_insert(global_maps, fixture['map_id'], index, 'map content')
                registered_maps[map_index] = fixture['map_id']
            unique_insert(global_tasks, fixture['id'], index, 'registered task')
            require(fixture['id'] not in fixtures, 'Duplicate registered task within stage')
            fixtures[fixture['id']] = fixture
            for spec in fixture['opponents']:
                unique_insert(global_rivals, spec['id'], index, 'rival instance')
                unique_insert(global_seeds, spec['seed'], index, 'rival seed')
        require(registered_maps == expected_maps, 'Stage registration omits catalog maps')
        # Capture header availability BEFORE observing append files. A new
        # approval appearing later may be conservatively deferred to next scan.
        summary = core.read_sealed(stage/'summary.json') if (stage/'summary.json').exists() else None
        audit = core.read_sealed(stage/'audit.json') if (stage/'audit.json').exists() else None
        if summary:
            metadata_identity(summary, index, manifest, 'summary')
        if audit:
            metadata_identity(audit, index, manifest, 'audit')
            require(audit['campaign_id'] == manifest['campaign_id'], 'Audit campaign identity changed')
        rows, games_body, tail = lines_snapshot(stage/'games.jsonl')
        by_fixture = {}
        for row in rows:
            require(row['fixture'] in fixtures and row['fixture'] not in by_fixture, 'Actual task missing/duplicated/foreign')
            check_row(row, fixtures[row['fixture']])
            unique_insert(actual_ids, row['fixture'], index, 'actual completed task')
            by_fixture[row['fixture']] = row
        completed += len(rows)
        entry = dict(generation=index, registered_games=len(fixtures), complete_actual_rows=len(rows),
                     observed_uncommitted_tail_bytes=tail, accepted_primary_games=0,
                     registration_sha256=digest((stage/'registration.json').read_bytes()))
        if summary:
            require(not tail and set(by_fixture) == set(fixtures), 'Sealed summary has incomplete actual games')
            require(summary['registration_sha256'] == entry['registration_sha256'] and summary['games_sha256'] == digest(games_body),
                    'Sealed summary hashes differ from actual evidence')
            require(summary['games_completed'] == len(rows) and summary['actual_callbacks'] == len(rows)*320
                    and summary['candidates'] == core.summarize(rows, registration), 'Summary does not derive from actual outcomes')
        if not audit:
            entry['status'] = 'actual_games_pending_independent_admission' if summary else 'execution_pending_or_in_progress'
            results.append(entry)
            continue
        require(summary is not None, 'Approved audit has no sealed summary')
        require(audit['approved'] is True and audit['all_actors_regenerated'] is True
                and audit['registration_sha256'] == entry['registration_sha256']
                and audit['games_sha256'] == digest(games_body)
                and audit['summary_sha256'] == digest((stage/'summary.json').read_bytes()), 'Audit approval/hash binding changed')
        actor_rows, actor_body, actor_tail = lines_snapshot(stage/'actor_audits.jsonl')
        require(not actor_tail and audit['actor_audits_sha256'] == digest(actor_body), 'Approved actor-audit transcript changed')
        seen, callback_count, oracles = set(), 0, 0
        for outcome in actor_rows:
            require(outcome['fixture'] in by_fixture and outcome['fixture'] not in seen, 'Duplicate or foreign actor audit')
            run.validate_actor_audit(outcome, by_fixture[outcome['fixture']])
            seen.add(outcome['fixture'])
            callback_count += outcome['callbacks_regenerated']
            oracles += outcome['public_memory_oracles']
        require(seen == set(fixtures) and audit['games_audited'] == len(seen)
                and audit['callbacks_regenerated'] == callback_count == len(rows)*320
                and audit['public_memory_oracles'] == oracles, 'Independent admission lacks actual task coverage')
        credited = len(rows) if manifest['profile'] == 'full_primary' else 0
        require(audit['primary_games_accepted'] == credited and audit['bmcts_audits'] == 0
                and audit['promoted'] is False, 'Admission counting/promotion changed')
        accepted += credited
        approved_stages.append(index)
        entry.update(status='existing_independent_admission_structurally_verified', accepted_primary_games=credited,
                     audit_sha256=digest((stage/'audit.json').read_bytes()))
        results.append(entry)
    require(prepared == list(range(len(prepared))), 'Sealed stage index sequence contains a gap')
    require(approved_stages == list(range(len(approved_stages))), 'Approved admissions are not a contiguous stage prefix')
    return dict(format='zone-rush-readonly-campaign-monitor/1', campaign_id=manifest['campaign_id'],
                campaign_directory=str(directory), snapshot_status='consistent', stages=results,
                actual_complete_rows_observed=completed, existing_accepted_primary_games=accepted,
                registered_maps=len(global_maps), registered_tasks=len(global_tasks),
                unique_rival_instances=len(global_rivals), unique_rival_seeds=len(global_seeds),
                scheduled_training_generations=manifest['training_generations'],
                training_complete=len(approved_stages) == manifest['training_generations'],
                duration_s=time.perf_counter()-started, files_modified_in_campaign=False,
                new_actor_regenerations=0, new_primary_games_credited=0, bmcts_audits=0,
                limitation='Structural consistency and existing receipt coverage only; not a fresh deep actor/physics audit or HMAC evaluator authority.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    require(not args.out.resolve().is_relative_to(args.directory.resolve()), 'Monitor output must be outside live campaign')
    result = inspect(args.directory)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2)+'\n', encoding='utf8')
    print(json.dumps(result, indent=2), flush=True)


if __name__ == '__main__':
    main()
