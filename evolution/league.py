"""Bounded mu+lambda experiments on the current policy; never deploys a bot.

Discovery alone selects research elites. Fresh confirmation is consumed once
per selected challenge and never supplies future evolutionary fitness. Every
game here is an extra control: neither a primary-campaign game nor a BMCTS audit.
"""
import argparse
import json
import os
from pathlib import Path
import random

from evolution.genomes import GenomeSpace, digest
from evolution.maps import generate
from evolution import runner
from evolution import oversight

ROOT = runner.ROOT
FORMAT = 'zone-rush-evolution-league/1'
METHODS = ('sparse_mutation', 'grouped_mutation', 'crossover', 'archive_mutation')


def encoded(value):
    return (json.dumps(value, sort_keys=True, indent=2, allow_nan=False)+'\n').encode('utf8')


def atomic_write(path, body):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name+'.pending')
    with temporary.open('wb') as handle:
        handle.write(body)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def immutable(path, value):
    """Existing completed artifacts are compared, never overwritten."""
    path, body = Path(path), encoded(value)
    if path.exists():
        if path.read_bytes() != body:
            raise ValueError('Immutable league artifact changed: '+str(path))
    else:
        atomic_write(path, body)
    return digest(body)


def seed_for(seed, round_index, phase):
    return int(digest(runner.canonical([seed, round_index, phase]))[:16], 16)


def ranked(summary):
    return sorted(summary, key=lambda row: (-row['mean_pw'], -row['mean_score'], row['sha256']))


def gene_entry(space, genes, kind, parents=(), **metadata):
    body = space.export(genes)
    return dict(genes=dict(genes), sha256=digest(body),
                lineage=dict(kind=kind, parents=list(parents), **metadata))


def make_population(space, research, elites, population, seed):
    """Retain the real incumbent and multiple research elites, then breed."""
    if not 4 <= population <= 32:
        raise ValueError('Population must be between 4 and 32')
    baseline = gene_entry(space, space.genes, 'production_control')
    archive = gene_entry(space, research, 'research_archive')
    parents = [baseline]+list(elites)+[archive]
    for parent in parents:
        if digest(space.export(parent['genes'])) != parent['sha256']:
            raise ValueError('Parent genome identity changed')
    output, seen = [], set()

    def retain(entry, name):
        if entry['sha256'] in seen:
            return False
        seen.add(entry['sha256'])
        output.append(dict(entry, name=name))
        return True

    retain(baseline, 'incumbent')
    for index, parent in enumerate(elites[:min(3, population//3)]):
        retained = gene_entry(space, parent['genes'], 'elite_retained', [parent['sha256']])
        retain(retained, 'elite_%02d' % index)
    retain(archive, 'research_archive')
    rng = random.Random(seed)
    attempts = 0
    while len(output) < population:
        if attempts >= population*100:
            raise ValueError('Could not breed distinct bounded offspring')
        kind = METHODS[attempts % len(METHODS)]
        attempts += 1
        mutation_seed = rng.getrandbits(63)
        parent = rng.choice(parents)
        if kind == 'crossover':
            other = rng.choice(parents)
            genes = space.crossover(parent['genes'], other['genes'], mutation_seed)
            ancestry = [parent['sha256'], other['sha256']]
        elif kind == 'archive_mutation':
            genes = space.mutate(research, mutation_seed, scale=0.09, grouped=True)
            ancestry = [archive['sha256']]
        else:
            genes = space.mutate(parent['genes'], mutation_seed, scale=0.07,
                                 grouped=(kind == 'grouped_mutation'))
            ancestry = [parent['sha256']]
        entry = gene_entry(space, genes, kind, ancestry, seed=mutation_seed)
        retain(entry, 'offspring_%02d' % len(output))
    return output


def select_elites(registration, summary, count=3):
    """This function accepts discovery data only, never confirmation outcomes."""
    if registration['role'] != 'discovery':
        raise ValueError('Confirmation must not enter evolutionary fitness')
    baseline = registration['candidates'][0]['sha256']
    candidates = {entry['sha256']: entry for entry in registration['candidates']}
    result = []
    for row in ranked(summary):
        if row['sha256'] != baseline:
            candidate = candidates[row['sha256']]
            result.append(dict(genes=dict(candidate['genes']), sha256=candidate['sha256'],
                               discovery_fitness=dict(mean_pw=row['mean_pw'], mean_score=row['mean_score']),
                               source_registration=digest(encoded(registration))))
            if len(result) == count:
                break
    return result


def collect_excluded(directory, current=None):
    """Content-exclude previous controls and every league round's holdout."""
    paths = set((ROOT/'validation/official').glob('*_spec.json'))
    for search_root in (ROOT/'.cache/evolution', Path(directory)):
        if search_root.exists():
            paths.update(search_root.rglob('registration.json'))
    excluded = []
    for path in sorted(paths):
        if current is not None and path.parent.resolve() == Path(current).resolve():
            continue
        data = json.loads(path.read_text(encoding='utf8'))
        excluded.extend(fixture['base'] for fixture in data['fixtures'])
    return excluded


def check_guards(registration):
    guards = dict(registration['guards'])
    guards.update({source['path']: source['sha256'] for source in registration.get('sources', {}).values()})
    guards.update({candidate['path']: candidate['sha256'] for candidate in registration.get('candidates', [])})
    for path, expected in guards.items():
        if digest(Path(path).read_bytes()) != expected:
            raise ValueError('Pinned league source changed: '+path)


def stage_registration(directory):
    directory = Path(directory)
    body = (directory/'registration.json').read_bytes()
    expected = (directory/'registration.sha256').read_text().strip()
    planned = (directory/'league_registration.json').read_bytes()
    if digest(body) != expected or body != planned:
        raise ValueError('Stage registration differs from its sealed league plan')
    registration = json.loads(body)
    check_guards(registration)
    return registration


def prepare_stage(directory, league_directory, spec, round_index, phase, entries, maps):
    """Reseal only an unconsumed stage; completed registrations are immutable."""
    directory = Path(directory)
    plan_path = directory/'league_registration.json'
    if plan_path.exists():
        planned = plan_path.read_bytes()
        registration = json.loads(planned)
        expected = dict(round=round_index, phase=phase, league_spec_sha256=digest(encoded(spec)))
        if registration.get('league') != expected:
            raise ValueError('Stage belongs to another league plan')
        if [entry['sha256'] for entry in registration['candidates']] != [entry['sha256'] for entry in entries]:
            raise ValueError('Sealed population differs from discovery ancestry')
        current = directory/'registration.json'
        fingerprint = directory/'registration.sha256'
        matches = (current.exists() and current.read_bytes() == planned and fingerprint.exists()
                   and fingerprint.read_text().strip() == digest(planned))
        if not matches:
            if (directory/'summary.json').exists() or ((directory/'games.jsonl').exists()
                                                      and (directory/'games.jsonl').stat().st_size):
                raise ValueError('Consumed stage cannot be resealed')
            atomic_write(current, planned)
            atomic_write(fingerprint, (digest(planned)+'\n').encode('ascii'))
        return stage_registration(directory)
    if (directory/'games.jsonl').exists() or (directory/'summary.json').exists():
        raise ValueError('Refusing to reconfigure a consumed non-league stage')
    stage_seed = seed_for(spec['seed'], round_index, phase)
    if directory.exists():
        registration = json.loads((directory/'registration.json').read_text(encoding='utf8'))
        if registration['seed'] != stage_seed:
            raise ValueError('Incomplete stage has another seed')
    else:
        registration = runner.create_registration(directory, stage_seed, maps, 1,
                                                  confirmation=(phase == 'confirmation'))
    space = GenomeSpace((ROOT/'bot.py').read_bytes())
    candidates = []
    for entry in entries:
        body = space.export(entry['genes'])
        if digest(body) != entry['sha256']:
            raise ValueError('Candidate lineage hash mismatch')
        path = directory/('league_'+entry['name']+'.py')
        if path.exists() and path.read_bytes() != body:
            raise ValueError('Candidate file changed')
        if not path.exists():
            atomic_write(path, body)
        candidates.append(dict(entry, path=str(path.resolve())))
    fresh_maps = generate(maps, stage_seed, collect_excluded(league_directory, directory))
    old_map_order = list(dict.fromkeys(fixture['map_id'] for fixture in registration['fixtures']))
    if len(old_map_order) != maps:
        raise ValueError('Unexpected initial stage map count')
    replacements = dict(zip(old_map_order, fresh_maps))
    for fixture in registration['fixtures']:
        board = replacements[fixture['map_id']]
        fixture.update(base=board['base'], map_id=board['id'], map_family=board['family'])
        for opponent in fixture['opponents']:
            content = {key: value for key, value in opponent.items() if key != 'id'}
            opponent['id'] = digest(runner.canonical(dict(campaign=stage_seed, map=board['id'],
                                                         episode=fixture['episode'], spec=content)))
        fixture['id'] = digest(runner.canonical({key: value for key, value in fixture.items() if key != 'id'}))
    registration.update(candidates=candidates,
                        league=dict(round=round_index, phase=phase, league_spec_sha256=digest(encoded(spec))),
                        promotion_allowed=False)
    registration['guards'][str(Path(__file__).resolve())] = digest(Path(__file__).read_bytes())
    registration['guards'].update(spec['guards'])
    immutable(plan_path, registration)
    atomic_write(directory/'registration.json', plan_path.read_bytes())
    atomic_write(directory/'registration.sha256', (digest(plan_path.read_bytes())+'\n').encode('ascii'))
    return stage_registration(directory)


def completed_stage(directory):
    """Replay immutable completed evidence without rewriting its summary."""
    directory = Path(directory)
    registration = stage_registration(directory)
    candidates = {candidate['sha256']: candidate for candidate in registration['candidates']}
    fixtures = {fixture['id']: fixture for fixture in registration['fixtures']}
    rows, seen = [], set()
    for line in (directory/'games.jsonl').read_text(encoding='utf8').splitlines():
        row = json.loads(line)
        key = row['candidate'], row['fixture']
        if key in seen or key[0] not in candidates or key[1] not in fixtures:
            raise ValueError('Duplicate or foreign completed league result')
        runner.verify_row(row, candidates[key[0]], fixtures[key[1]])
        rows.append(row)
        seen.add(key)
    if seen != {(candidate, fixture) for candidate in candidates for fixture in fixtures}:
        raise ValueError('Completed stage is missing registered games')
    baseline = registration['candidates'][0]['sha256']
    derived = dict(registration_sha256=digest((directory/'registration.json').read_bytes()),
                   summary=runner.summarize(rows, registration['candidates']),
                   paired=[runner.paired(rows, candidate['sha256'], baseline)
                           for candidate in registration['candidates'][1:]],
                   games_completed=len(rows), callbacks=sum(t['calls'] for row in rows for t in row['timing']),
                   games_bmcts_audited=0, primary_campaign_games=0, promoted=False)
    stored = json.loads((directory/'summary.json').read_text(encoding='utf8'))
    if stored != derived:
        raise ValueError('Completed league summary differs from replayed evidence')
    return stored


def evaluate_stage(directory, workers):
    if (Path(directory)/'summary.json').exists():
        return completed_stage(directory)
    runner.evaluate(Path(directory), workers)
    return completed_stage(directory)


def independent_gate(directory, workers):
    """Fail closed before breeding: replay BOTH referees and every actor call."""
    directory = Path(directory)
    identity = dict(registration_sha256=digest((directory/'registration.json').read_bytes()),
                    transcripts_sha256=digest((directory/'games.jsonl').read_bytes()),
                    summary_sha256=digest((directory/'summary.json').read_bytes()),
                    auditor_sha256=digest(Path(oversight.__file__).read_bytes()))
    path = directory/'independent_audit.json'
    if path.exists():
        proof = json.loads(path.read_text())
        if proof.get('identity') != identity or proof.get('validity') != 'passed':
            raise ValueError('Independent audit proof changed or refers to different evidence')
        return proof
    report = oversight.audit_stage(directory, workers=workers, regenerate=True)
    if (report['registration_sha256'] != identity['registration_sha256']
            or report['transcripts_sha256'] != identity['transcripts_sha256']
            or not report['zero_faults'] or not report['two_referees_every_turn']
            or report['regenerated_callbacks'] != report['games']*320):
        raise ValueError('Independent audit did not certify all games and actor calls')
    proof = dict(validity='passed', identity=identity, report=report,
                 promotion_allowed=False, final_generalization_review_required=True)
    immutable(path, proof)
    return proof


def load_spec(directory, seed, rounds, population, discovery_maps, confirmation_maps, workers):
    values = dict(seed=seed, rounds=rounds, population=population,
                  discovery_maps=discovery_maps, confirmation_maps=confirmation_maps, workers=workers)
    if (type(seed) is not int or not 1 <= rounds <= 100 or not 4 <= population <= 32
            or not 1 <= discovery_maps <= 10000 or not 1 <= confirmation_maps <= 10000
            or not 1 <= workers <= 24):
        raise ValueError('Invalid bounded league settings')
    path = Path(directory)/'league_spec.json'
    if path.exists():
        body = path.read_bytes()
        if digest(body) != path.with_suffix('.sha256').read_text().strip():
            raise ValueError('League specification fingerprint changed')
        spec = json.loads(body)
        if spec['settings'] != values:
            raise ValueError('Resume settings differ from immutable league settings')
        check_guards(spec)
        return spec
    guards = {str((ROOT/relative).resolve()): digest((ROOT/relative).read_bytes()) for relative in (
        'bot.py', 'tester_bots/research_alternative.py', 'tester_bots/racer.py', 'tester_bots/blocker.py',
        'evolution/runner.py', 'evolution/genomes.py', 'evolution/maps.py', 'evolution/opponents.py',
        'evolution/league.py', 'evolution/oversight.py', 'tests/reference_engine.py',
        'simulator/vendor_harness/referee.py')}
    spec = dict(format=FORMAT, seed=seed, settings=values, guards=guards,
                incumbent_sha256=digest((ROOT/'bot.py').read_bytes()),
                research_archive_sha256=digest((ROOT/'tester_bots/research_alternative.py').read_bytes()),
                selection='Discovery mean pairwise outcome, then mean score, then ascending source hash.',
                challenge_gate='Positive fresh paired mean and map-cluster bootstrap lower95 > 0; independent review still required.',
                counting='All league games are extra controls; primary_campaign_games=0; BMCTS audits=0.',
                confirmation_used_for_fitness=False, production_auto_promotion=False)
    immutable(path, spec)
    immutable_path_hash = (digest(path.read_bytes())+'\n').encode('ascii')
    atomic_write(path.with_suffix('.sha256'), immutable_path_hash)
    return spec


def run_league(directory, seed=202611082301, rounds=4, population=8,
               discovery_maps=8, confirmation_maps=32, workers=6):
    directory = Path(directory).resolve()
    directory.mkdir(parents=True, exist_ok=True)
    spec = load_spec(directory, seed, rounds, population, discovery_maps, confirmation_maps, workers)
    space = GenomeSpace((ROOT/'bot.py').read_bytes())
    research = GenomeSpace((ROOT/'tester_bots/research_alternative.py').read_bytes()).genes
    elites, completed = [], []
    try:
        for index in range(rounds):
            check_guards(spec)
            round_directory = directory/('round_%03d' % index)
            entries = make_population(space, research, elites, population, seed_for(seed, index, 'breeding'))
            discovery_directory = round_directory/'discovery'
            registration = prepare_stage(discovery_directory, directory, spec, index, 'discovery', entries, discovery_maps)
            discovery = evaluate_stage(discovery_directory, workers)
            independent_gate(discovery_directory, workers)
            # These elites are finalized BEFORE any confirmation is inspected.
            elites = select_elites(registration, discovery['summary'])
            immutable(round_directory/'research_elites.json', elites)
            best = ranked(discovery['summary'])[0]
            baseline = registration['candidates'][0]
            challenger = next(candidate for candidate in registration['candidates'] if candidate['sha256'] == best['sha256'])
            selection = dict(round=index, method=spec['selection'], incumbent=baseline['sha256'],
                             challenger=None if challenger['sha256'] == baseline['sha256'] else challenger['sha256'],
                             discovery_registration_sha256=discovery['registration_sha256'],
                             discovery_summary_sha256=digest((discovery_directory/'summary.json').read_bytes()),
                             confirmation_may_change_elites=False)
            immutable(round_directory/'selection.json', selection)
            decision = dict(round=index, selection=selection, promoted=False, deployment_performed=False,
                            primary_campaign_games=0, games_bmcts_audited=0,
                            discovery_games=discovery['games_completed'], confirmation_games=0,
                            independent_review_required=True, audit_status='pending_independent_review')
            if selection['challenger'] is None:
                decision.update(status='incumbent_won_discovery', eligible_for_review=False,
                                confirmation_consumed=False)
            else:
                holdout_directory = round_directory/'confirmation'
                challenge_entries = [dict(baseline), dict(challenger, name='discovery_challenger')]
                prepare_stage(holdout_directory, directory, spec, index, 'confirmation',
                              challenge_entries, confirmation_maps)
                confirmation = evaluate_stage(holdout_directory, workers)
                independent_gate(holdout_directory, workers)
                paired = next(row for row in confirmation['paired']
                              if row['first'] == challenger['sha256'] and row['second'] == baseline['sha256'])
                eligible = paired['mean'] > 0 and paired['bootstrap_95'][0] > 0
                decision.update(status='review_required' if eligible else 'challenge_not_confirmed',
                                eligible_for_review=eligible, confirmation_consumed=True,
                                confirmation_games=confirmation['games_completed'],
                                confirmation_registration_sha256=confirmation['registration_sha256'],
                                confirmation_summary_sha256=digest((holdout_directory/'summary.json').read_bytes()),
                                paired=paired)
            immutable(round_directory/'challenge.json', decision)
            completed.append(decision)
            check_guards(spec)
            state = dict(format=FORMAT, league_spec_sha256=digest(encoded(spec)), status='running',
                         rounds_completed=len(completed), planned_rounds=rounds, rounds=completed,
                         production_incumbent_sha256=spec['incumbent_sha256'], production_changed=False,
                         extra_control_games=sum(row['discovery_games']+row['confirmation_games'] for row in completed),
                         primary_campaign_games=0, games_bmcts_audited=0, promoted=False,
                         audit_status='pending_independent_review')
            atomic_write(directory/'league_state.json', encoded(state))
            print('League round %d/%d: %s; production incumbent unchanged' % (index+1, rounds, decision['status']), flush=True)
        state['status'] = 'bounded_experiment_complete'
        atomic_write(directory/'league_state.json', encoded(state))
        return state
    except BaseException as error:
        atomic_write(directory/'league_failure.json', encoded(dict(
            error_type=type(error).__name__, reason=str(error), rounds_completed=len(completed),
            production_changed=False, promoted=False, audit_status='pending_independent_review')))
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, required=True)
    parser.add_argument('--seed', type=int, default=202611082301)
    parser.add_argument('--rounds', type=int, default=4)
    parser.add_argument('--population', type=int, default=8)
    parser.add_argument('--discovery-maps', type=int, default=8)
    parser.add_argument('--confirmation-maps', type=int, default=32)
    parser.add_argument('--workers', type=int, default=6)
    args = parser.parse_args()
    result = run_league(args.directory, args.seed, args.rounds, args.population,
                        args.discovery_maps, args.confirmation_maps, args.workers)
    print(json.dumps(result, indent=2), flush=True)


if __name__ == '__main__':
    main()
