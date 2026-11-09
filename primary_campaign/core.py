"""Immutable maps and single-assignment tasks for the requested primary campaign."""
from collections import Counter, defaultdict
import json
import os
from pathlib import Path
import random

from evolution import league, maps, runner, oversight
from evolution.genomes import GenomeSpace, digest

ROOT = runner.ROOT
FORMAT = 'zone-rush-primary-campaign/1'
DEFAULT_SHAPE = dict(train_maps=8000, development_maps=1000, final_maps=1000,
                     maps_per_generation=100, episodes_per_map=200, population=8)
INCUMBENT = 'e8b3682d8b39d3fc4d22cdcd8927161290a90cd472d3ede4132ae716f8c6f8f5'
FIELDS = {'economic': ('planner', 'planner', 'farmer'),
          'independent': ('racer', 'blocker', 'raider'),
          'erratic': ('wanderer', 'mixed', 'planner'),
          'pressure': ('interceptor', 'feinter', 'research')}


def canonical(value):
    return runner.canonical(value)


def seed_for(*items):
    return int(digest(canonical(items))[:16], 16)


def rotation_orbit(base):
    """Quarter turns with rotated seats describe equivalent mirrored boards."""
    variants, current = [], list(base)
    for _ in range(4):
        variants.append(bytes(current))
        current = [current[(7-c)*8+r] for r in range(8) for c in range(8)]
    return min(variants).hex()


def atomic(path, body):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name+'.pending')
    with temporary.open('wb') as handle:
        handle.write(body)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def seal(path, value):
    path, body = Path(path), canonical(value)+b'\n'
    if path.exists() and path.read_bytes() != body:
        raise ValueError('Refusing to overwrite immutable campaign evidence: '+str(path))
    if not path.exists():
        atomic(path, body)
    fingerprint = path.with_suffix('.sha256')
    expected = (digest(body)+'\n').encode('ascii')
    if fingerprint.exists() and fingerprint.read_bytes() != expected:
        raise ValueError('Campaign fingerprint changed')
    if not fingerprint.exists():
        atomic(fingerprint, expected)
    return value


def read_sealed(path):
    path = Path(path)
    body = path.read_bytes()
    if digest(body) != path.with_suffix('.sha256').read_text().strip():
        raise ValueError('Campaign artifact fingerprint mismatch: '+str(path))
    return oversight.strict_loads(body)


def guard_sources():
    paths = [ROOT/relative for relative in (
        'bot.py', 'tester_bots/research_alternative.py', 'tester_bots/racer.py', 'tester_bots/blocker.py',
        'evolution/runner.py', 'evolution/genomes.py', 'evolution/maps.py', 'evolution/opponents.py',
        'evolution/league.py', 'evolution/oversight.py', 'tests/reference_engine.py',
        'simulator/vendor_harness/referee.py')]
    paths.extend(path for path in (ROOT/'primary_campaign').glob('*.py') if not path.name.startswith('test_'))
    return {str(path.resolve()): digest(path.read_bytes()) for path in paths}


def check_guards(guards):
    for path, expected in guards.items():
        if digest(Path(path).read_bytes()) != expected:
            raise ValueError('Campaign code/source changed: '+path)


def historical_map_ids():
    paths = set((ROOT/'validation/official').glob('*_spec.json'))
    if (ROOT/'.cache/evolution').exists():
        paths.update((ROOT/'.cache/evolution').rglob('registration.json'))
    result = set()
    for path in paths:
        data = json.loads(path.read_text(encoding='utf8'))
        result.update(rotation_orbit(fixture['base']) for fixture in data['fixtures'])
    return result


def create_catalog(directory, seed=202611090001, shape=None):
    directory = Path(directory).resolve()
    shape = dict(DEFAULT_SHAPE if shape is None else shape)
    if set(shape) != set(DEFAULT_SHAPE) or any(type(v) is not int or v <= 0 for v in shape.values()):
        raise ValueError('Invalid campaign shape')
    if (shape['episodes_per_map'] != 200 or shape['population'] != 8
            or shape['maps_per_generation'] % 4 or shape['train_maps'] % shape['maps_per_generation']):
        raise ValueError('Require 200/map, population8 and training blocks divisible by4')
    if (directory/'manifest.json').exists():
        manifest = load_catalog(directory)[0]
        if manifest['seed'] != seed or manifest['shape'] != shape:
            raise ValueError('Campaign resume settings changed')
        return manifest
    if digest((ROOT/'bot.py').read_bytes()) != INCUMBENT:
        raise ValueError('Primary campaign requires the pinned current incumbent')
    seen, used_seeds, catalog = historical_map_ids(), set(), []
    phase_seed_ids = {}
    for phase in ('train', 'development', 'final'):
        phase_seed_ids[phase] = seed_for(seed, phase)
        for index in range(shape[phase+'_maps']):
            for retry in range(10000):
                map_seed = seed_for(seed, phase, index, retry)
                if map_seed in used_seeds:
                    continue
                board = maps.generate(1, map_seed)[0]
                if rotation_orbit(board['base']) not in seen:
                    break
            else:
                raise ValueError('Could not generate distinct campaign map')
            seen.add(rotation_orbit(board['base']))
            used_seeds.add(map_seed)
            catalog.append(dict(map_index=len(catalog), phase=phase, phase_index=index,
                                seed=map_seed, seed_retry=retry, family=board['family'], id=board['id'],
                                rotation_orbit=rotation_orbit(board['base']), base=board['base']))
    seal(directory/'catalog.json', catalog)
    sources = {name: runner.source_entry(ROOT/path) for name, path in {
        'planner': 'bot.py', 'research': 'tester_bots/research_alternative.py',
        'racer': 'tester_bots/racer.py', 'blocker': 'tester_bots/blocker.py'}.items()}
    profile = 'full_primary' if shape == DEFAULT_SHAPE else 'mechanics_test'
    manifest = dict(format=FORMAT, seed=seed, shape=shape, profile=profile,
                    requested_primary_games=2000000, scheduled_games=len(catalog)*200,
                    training_generations=shape['train_maps']//shape['maps_per_generation'],
                    catalog_sha256=digest((directory/'catalog.json').read_bytes()),
                    phase_seed_ids=phase_seed_ids, sources=sources, guards=guard_sources(),
                    incumbent_sha256=INCUMBENT, bmcts_audits=0,
                    promotion_allowed=False, heldouts_reserved_until_training_audited=True,
                    fitness='Equal-weight mean of64 seat/token/field outcome cells, then raw score, then source hash.',
                    caveat='Primary opponents are new instances each game; parameters do not constitute new algorithms. Comparisons are unpaired. Additional paired controls are required for promotion.')
    manifest['campaign_id'] = digest(canonical(manifest))
    return seal(directory/'manifest.json', manifest)


def load_catalog(directory):
    directory = Path(directory)
    manifest, catalog = read_sealed(directory/'manifest.json'), read_sealed(directory/'catalog.json')
    if manifest['format'] != FORMAT or digest((directory/'catalog.json').read_bytes()) != manifest['catalog_sha256']:
        raise ValueError('Campaign catalog changed')
    shape = manifest['shape']
    if (set(shape) != set(DEFAULT_SHAPE) or any(type(v) is not int or v <= 0 for v in shape.values())
            or shape['episodes_per_map'] != 200 or shape['population'] != 8
            or shape['maps_per_generation'] % 4 or shape['train_maps'] % shape['maps_per_generation']):
        raise ValueError('Invalid catalog schedule shape')
    if (manifest['profile'] != ('full_primary' if shape == DEFAULT_SHAPE else 'mechanics_test')
            or manifest['scheduled_games'] != sum(shape[p+'_maps'] for p in ('train', 'development', 'final'))*200
            or manifest['requested_primary_games'] != 2000000
            or manifest['training_generations'] != shape['train_maps']//shape['maps_per_generation']
            or manifest['phase_seed_ids'] != {p: seed_for(manifest['seed'], p) for p in ('train', 'development', 'final')}
            or manifest['campaign_id'] != digest(canonical({k: v for k, v in manifest.items() if k != 'campaign_id'}))):
        raise ValueError('Catalog labels/counts differ from their actual schedule')
    check_guards(manifest['guards'])
    expected_sources = {name: runner.source_entry(ROOT/path) for name, path in {
        'planner': 'bot.py', 'research': 'tester_bots/research_alternative.py',
        'racer': 'tester_bots/racer.py', 'blocker': 'tester_bots/blocker.py'}.items()}
    if (manifest['guards'] != guard_sources() or manifest['sources'] != expected_sources
            or manifest['incumbent_sha256'] != INCUMBENT or digest((ROOT/'bot.py').read_bytes()) != INCUMBENT):
        raise ValueError('Campaign removed or replaced a required source guard')
    if len(catalog) != sum(manifest['shape'][phase+'_maps'] for phase in ('train', 'development', 'final')):
        raise ValueError('Incomplete campaign catalog')
    ids, seeds, orbits = set(), set(), set()
    expected_order = [(phase, index) for phase in ('train', 'development', 'final')
                      for index in range(shape[phase+'_maps'])]
    for index, board in enumerate(catalog):
        if (board['map_index'] != index or not maps.valid(board['base'])
                or digest(bytes(board['base'])) != board['id'] or board['id'] in ids or board['seed'] in seeds
                or board['rotation_orbit'] != rotation_orbit(board['base']) or board['rotation_orbit'] in orbits
                or (board['phase'], board['phase_index']) != expected_order[index]
                or type(board['seed_retry']) is not int or not 0 <= board['seed_retry'] < 10000
                or board['seed'] != seed_for(manifest['seed'], board['phase'], board['phase_index'], board['seed_retry'])):
            raise ValueError('Invalid, duplicate or reordered campaign map')
        ids.add(board['id'])
        seeds.add(board['seed'])
        orbits.add(board['rotation_orbit'])
        reproduced = maps.generate(1, board['seed'])[0]
        if (reproduced['base'], reproduced['id'], reproduced['family']) != (board['base'], board['id'], board['family']):
            raise ValueError('Catalog map does not reproduce from its declared seed')
    return manifest, catalog


def validated_audit(directory):
    directory = Path(directory)
    manifest, catalog = load_catalog(directory.parent)
    registration = read_sealed(directory/'registration.json')
    validate_registration(registration, manifest, catalog)
    audit = read_sealed(directory/'audit.json')
    if (audit.get('approved') is not True or audit.get('all_actors_regenerated') is not True
            or audit['registration_sha256'] != digest((directory/'registration.json').read_bytes())
            or audit['games_sha256'] != digest((directory/'games.jsonl').read_bytes())
            or audit['summary_sha256'] != digest((directory/'summary.json').read_bytes())
            or audit['actor_audits_sha256'] != digest((directory/'actor_audits.jsonl').read_bytes())
            or audit['oversight_sha256'] != digest((ROOT/'evolution/oversight.py').read_bytes())):
        raise ValueError('Independent audit does not approve these exact completed games')
    if (audit['format'] != FORMAT or audit['campaign_id'] != manifest['campaign_id']
            or audit['phase'] != registration['phase'] or audit['generation'] != registration['generation']
            or audit['profile'] != manifest['profile'] or audit['bmcts_audits'] != 0
            or audit['promoted'] is not False):
        raise ValueError('Independent audit belongs to another campaign stage')
    # Declared aggregate counts never grant credit: derive every task from the
    # actual transcript, physically replay it, and match its individual audit.
    from primary_campaign import run
    rows = run.checked_rows(directory, registration)
    by_fixture = {row['fixture']: row for row in rows}
    expected = {fixture['id'] for fixture in registration['fixtures']}
    if set(by_fixture) != expected:
        raise ValueError('Independent audit has incomplete actual game coverage')
    summary = read_sealed(directory/'summary.json')
    if (summary['candidates'] != summarize(rows, registration)
            or summary['registration_sha256'] != audit['registration_sha256']
            or summary['games_sha256'] != audit['games_sha256']
            or summary['games_completed'] != len(rows) or summary['actual_callbacks'] != len(rows)*320
            or summary['phase'] != registration['phase'] or summary['generation'] != registration['generation']
            or summary['profile'] != manifest['profile'] or summary['bmcts_audits'] != 0
            or summary['promoted'] is not False):
        raise ValueError('Audited summary differs from actual game evidence')
    body = (directory/'actor_audits.jsonl').read_bytes()
    if body and not body.endswith(b'\n'):
        raise ValueError('Approved actor audit contains an incomplete record')
    seen, callbacks, oracles = set(), 0, 0
    for line in body.splitlines():
        item = oversight.strict_loads(line)
        fixture_id = item['fixture']
        if fixture_id not in by_fixture or fixture_id in seen:
            raise ValueError('Duplicate or foreign actor-audit task')
        run.validate_actor_audit(item, by_fixture[fixture_id])
        seen.add(fixture_id)
        callbacks += item['callbacks_regenerated']
        oracles += item['public_memory_oracles']
    if (seen != expected or audit['games_audited'] != len(seen)
            or audit['callbacks_regenerated'] != callbacks or callbacks != len(seen)*320
            or audit['public_memory_oracles'] != oracles
            or audit['primary_games_accepted'] != (len(rows) if manifest['profile'] == 'full_primary' else 0)):
        raise ValueError('Independent regeneration coverage/credit is incomplete')
    return audit


def sources_space():
    return GenomeSpace((ROOT/'bot.py').read_bytes()), GenomeSpace((ROOT/'tester_bots/research_alternative.py').read_bytes()).genes


def expected_opponents(manifest, board, episode, seat, field, space, research):
    """Reconstruct full identities/parameters; a field label alone proves nothing."""
    context = [manifest['campaign_id'], board['map_index'], episode]
    rng = random.Random(seed_for(*context, 'rivals'))
    families = list(FIELDS[field])
    rng.shuffle(families)
    opponents = []
    for rival_seat in range(4):
        if rival_seat == seat:
            continue
        family = families.pop()
        spec = dict(seat=rival_seat, family=family, seed=seed_for(*context, rival_seat),
                    epsilon=rng.uniform(.01, .45), commitment=rng.uniform(.2, .95))
        if family in ('planner', 'research'):
            spec['genes'] = space.mutate(research if family == 'research' else space.genes,
                                         spec['seed'], scale=.16, grouped=True)
        spec['id'] = digest(canonical(dict(context=context, seat=rival_seat, spec=spec)))
        opponents.append(spec)
    return opponents


def prepare_generation(directory, index):
    directory = Path(directory).resolve()
    manifest, catalog = load_catalog(directory)
    if type(index) is not int or not 0 <= index < manifest['training_generations']:
        raise ValueError('Invalid training generation')
    stage = directory/('train_%03d' % index)
    if index:
        validated_audit(directory/('train_%03d' % (index-1)))
    if (stage/'registration.json').exists():
        registration = read_sealed(stage/'registration.json')
        validate_registration(registration, manifest, catalog)
        return registration
    space, research = sources_space()
    elites = []
    if index:
        previous = directory/('train_%03d' % (index-1))
        validated_audit(previous)  # No unaudited fitness may breed another generation.
        prior_registration = read_sealed(previous/'registration.json')
        prior_summary = read_sealed(previous/'summary.json')
        candidates = {candidate['sha256']: candidate for candidate in prior_registration['candidates']}
        for row in prior_summary['candidates']:
            if row['sha256'] != INCUMBENT:
                parent = candidates[row['sha256']]
                elites.append(dict(sha256=parent['sha256'], genes=parent['genes']))
            if len(elites) == 3:
                break
    population = league.make_population(space, research, elites, 8, seed_for(manifest['seed'], 'breed', index))
    candidates = []
    for entry in population:
        path = stage/(entry['name']+'.py')
        body = space.export(entry['genes'])
        if path.exists() and path.read_bytes() != body:
            raise ValueError('Generation candidate changed')
        if not path.exists():
            atomic(path, body)
        candidates.append(dict(entry, path=str(path.resolve())))
    size = manifest['shape']['maps_per_generation']
    boards = [board for board in catalog if board['phase'] == 'train'][index*size:(index+1)*size]
    occurrence, fixtures = Counter(), []
    for board in boards:
        for episode in range(200):
            seat, token = maps.seat_token(board['map_index'], episode)
            n = occurrence[seat, token]
            occurrence[seat, token] += 1
            candidate = candidates[(n+4*seat+token-1) % 8]
            field = list(FIELDS)[(n//8+n%8+2*seat+token-1) % 4]
            opponents = expected_opponents(manifest, board, episode, seat, field, space, research)
            fixture = dict(map_id=board['id'], map_index=board['map_index'], base=board['base'],
                           map_family=board['family'], episode=episode, seat=seat, token=token,
                           field=field, candidate=candidate['sha256'], opponents=opponents)
            fixture['id'] = digest(canonical(fixture))
            fixtures.append(fixture)
    registration = dict(format=FORMAT, phase='train', generation=index, campaign_id=manifest['campaign_id'],
                        profile=manifest['profile'], sources=manifest['sources'], guards=manifest['guards'],
                        rules={'catch_requires_stay': True}, candidates=candidates, fixtures=fixtures,
                        promotion_allowed=False, bmcts_audits=0, paired_controls=False)
    validate_registration(registration, manifest, catalog)
    return seal(stage/'registration.json', registration)


def validate_registration(registration, manifest, catalog):
    if (registration['format'] != FORMAT or registration['campaign_id'] != manifest['campaign_id']
            or registration['rules'] != {'catch_requires_stay': True} or registration['promotion_allowed'] is not False
            or registration['phase'] != 'train' or registration['profile'] != manifest['profile']
            or registration['sources'] != manifest['sources'] or registration['guards'] != manifest['guards']
            or registration['paired_controls'] is not False or registration['bmcts_audits'] != 0
            or type(registration['generation']) is not int
            or not 0 <= registration['generation'] < manifest['training_generations']):
        raise ValueError('Unexpected primary registration')
    check_guards(registration['guards'])
    candidates = {candidate['sha256']: candidate for candidate in registration['candidates']}
    if len(candidates) != 8 or registration['candidates'][0]['sha256'] != INCUMBENT:
        raise ValueError('Require8 distinct candidates with incumbent control')
    space, research = sources_space()
    for candidate in candidates.values():
        body = Path(candidate['path']).read_bytes()
        if body != space.export(candidate['genes']) or digest(body) != candidate['sha256']:
            raise ValueError('Candidate changed beyond its registered numerical genome')
    size, index = manifest['shape']['maps_per_generation'], registration['generation']
    expected_boards = [board for board in catalog if board['phase'] == 'train'][index*size:(index+1)*size]
    boards = {board['map_index']: board for board in expected_boards}
    expected = {(board['map_index'], episode) for board in expected_boards for episode in range(200)}
    seen, ids, rival_ids, counts, pair_counts, occurrence = set(), set(), set(), Counter(), Counter(), Counter()
    for fixture in registration['fixtures']:
        key = fixture['map_index'], fixture['episode']
        if key in seen or key not in expected or fixture['id'] in ids:
            raise ValueError('Duplicate or foreign primary fixture')
        board = boards[key[0]]
        if fixture['base'] != board['base'] or fixture['map_id'] != board['id']:
            raise ValueError('Primary board differs from catalog')
        seat, token = maps.seat_token(*key)
        if (seat, token) != (fixture['seat'], fixture['token']):
            raise ValueError('Primary seat/token schedule changed')
        n = occurrence[seat, token]
        occurrence[seat, token] += 1
        candidate = registration['candidates'][(n+4*seat+token-1) % 8]['sha256']
        if fixture['candidate'] != candidate:
            raise ValueError('Candidate/seat/token confounding or assignment changed')
        if fixture['field'] != list(FIELDS)[(n//8+n%8+2*seat+token-1) % 4]:
            raise ValueError('Primary field balance schedule changed')
        if fixture['opponents'] != expected_opponents(manifest, board, fixture['episode'], seat,
                                                      fixture['field'], space, research):
            raise ValueError('Primary opponent family/seed/parameters differ from the registered recipe')
        if fixture['id'] != digest(canonical({k: v for k, v in fixture.items() if k != 'id'})):
            raise ValueError('Primary fixture hash mismatch')
        if len(fixture['opponents']) != 3 or {s['seat'] for s in fixture['opponents']} != set(range(4))-{seat}:
            raise ValueError('Invalid primary rival seats')
        context = [manifest['campaign_id'], fixture['map_index'], fixture['episode']]
        for spec in fixture['opponents']:
            wanted = digest(canonical(dict(context=context, seat=spec['seat'], spec={k: v for k, v in spec.items() if k != 'id'})))
            if spec['id'] != wanted or spec['id'] in rival_ids:
                raise ValueError('Primary opponent is reused or changed')
            rival_ids.add(spec['id'])
        seen.add(key)
        ids.add(fixture['id'])
        counts[candidate] += 1
        pair_counts[candidate, seat, token] += 1
    if seen != expected or set(counts.values()) != {size*200//8}:
        raise ValueError('Incomplete or candidate-imbalanced primary registration')
    if len(pair_counts) != 8*16 or max(pair_counts.values())-min(pair_counts.values()) > 1:
        raise ValueError('Candidate/seat/token balance failed')
    return dict(games=len(seen), new_rivals=len(rival_ids), candidate_games=dict(counts),
                pair_min=min(pair_counts.values()), pair_max=max(pair_counts.values()))


def summarize(rows, registration):
    fixtures = {fixture['id']: fixture for fixture in registration['fixtures']}
    output = []
    for candidate in registration['candidates']:
        games = [row for row in rows if row['candidate'] == candidate['sha256']]
        strata = defaultdict(list)
        for row in games:
            fixture = fixtures[row['fixture']]
            strata[fixture['seat'], fixture['token'], fixture['field']].append(row['focal_pw'])
        if len(strata) != 64:
            raise ValueError('Missing a candidate seat/token/field outcome cell')
        output.append(dict(name=candidate['name'], sha256=candidate['sha256'], games=len(games),
                           mean_pw=sum(row['focal_pw'] for row in games)/len(games),
                           standardized_pw=sum(sum(values)/len(values) for values in strata.values())/64,
                           mean_score=sum(row['focal_score'] for row in games)/len(games),
                           stratum_counts={str(key): len(value) for key, value in sorted(strata.items())}))
    return sorted(output, key=lambda row: (-row['standardized_pw'], -row['mean_score'], row['sha256']))
