"""Authenticate complete V2 coverage before the preregistered descriptive analysis.

No game, actor, audit, qualification, tuning or promotion is executed here.
"""
from array import array
from collections import Counter
from dataclasses import dataclass
from fractions import Fraction
import hashlib
import math
from pathlib import Path
import random
import re
import time

from confirmation_campaign import architectures
from distributed_campaign import auth, protocol as p
from primary_campaign import core

FORMAT = 'zone-rush-accepted-architecture-report/1'
REGISTRATION_SHA256 = 'b5ffb74f5c8ad1c7a984a54d41d86efb26cb99ae2318a8b7d5a631d23ad24eb9'
EXPECTED_GAMES, EXPECTED_MAPS = 32768, 128
HEX = re.compile('[0-9a-f]{64}\\Z')
ACTION_NAMES = frozenset(('NORTH', 'EAST', 'SOUTH', 'WEST', 'STAY', 'SHIELD'))
BOOTSTRAP_ALGORITHM = 'stdlib Random(seed).randrange(M), replicate-major then registered-map draw order; shared draws for all six contrasts/v1'


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _integer(value, low, high):
    return type(value) is int and low <= value <= high


def _number(value):
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


def _sealed(path, maximum):
    path = Path(path)
    _require(path.stat().st_size <= maximum, 'Sealed analysis input exceeds its bound')
    body = path.read_bytes()
    digest = p.sha(body)
    _require(path.with_suffix('.sha256').read_text(encoding='ascii').strip() == digest,
             'Sealed analysis input fingerprint mismatch')
    return p.loads(body), digest


def _signed(registry, purpose, path):
    envelope, digest = _sealed(path, 16*1024*1024)
    return auth.verify_owner(registry, 'distributed-control-'+purpose+'/v2', envelope), digest, envelope['authority_id']


def _fraction(numerator, denominator):
    value = Fraction(numerator, denominator)
    return dict(numerator=value.numerator, denominator=value.denominator, decimal=float(value))


def _source_hashes():
    files = list(Path(__file__).resolve().parent.glob('*.py'))
    files += [Path(auth.__file__), Path(architectures.__file__), Path(p.__file__)]
    return {str(path.resolve()):p.sha(path.read_bytes()) for path in files if not path.name.startswith('test_')}


def _design(registration):
    _require(registration['format'] == architectures.FORMAT and registration['role'] == 'extra_control_assignment'
             and registration['phase'] == 'architecture_confirmation' and registration['generation'] == 0,
             'Only the frozen V2 extra architecture study is reportable')
    _require(registration['protocol']['inference'] == architectures.inference_plan(), 'Frozen statistical inference plan changed')
    _require(registration['planned_games'] == EXPECTED_GAMES and len(registration['fixtures']) == EXPECTED_GAMES
             and len(registration['maps']) == EXPECTED_MAPS, 'Study map or fixture coverage is incomplete')
    arms = [candidate['sha256'] for candidate in registration['candidates']]
    fields = registration['protocol']['fields']
    maps = [item['id'] for item in registration['maps']]
    _require(arms == list(architectures.ARMS) and len(set(maps)) == EXPECTED_MAPS and fields == list(core.FIELDS),
             'Frozen arm, map or field identities changed')
    fixtures, cells, groups, actors = {}, Counter(), {}, set()
    for fixture in registration['fixtures']:
        identity = fixture['id']
        cell = (fixture['map_id'], fixture['candidate'], fixture['field'], fixture['seat'], fixture['token'])
        _require(identity not in fixtures and fixture['map_id'] in maps and fixture['candidate'] in arms
                 and fixture['field'] in fields and _integer(fixture['seat'], 0, 3) and _integer(fixture['token'], 1, 4),
                 'Duplicate, foreign or invalid registered fixture')
        fixtures[identity] = fixture
        cells[cell] += 1
        groups.setdefault(fixture['pair_key'], []).append(fixture)
        for actor in [fixture['focal_actor_id']]+[spec['id'] for spec in fixture['opponents']]:
            _require(actor not in actors, 'Registered actor identity was reused')
            actors.add(actor)
    _require(len(cells) == EXPECTED_GAMES and set(cells.values()) == {1}
             and len(groups) == EXPECTED_GAMES//4, 'Registered matched crossing is incomplete')
    for group in groups.values():
        first = group[0]
        _require(len(group) == 4 and {item['candidate'] for item in group} == set(arms), 'Matched condition misses an arm')
        parameters = [{k:v for k,v in spec.items() if k != 'id'} for spec in first['opponents']]
        for item in group[1:]:
            _require(all(item[k] == first[k] for k in ('map_id', 'field', 'seat', 'token', 'parent_pair_id'))
                     and [{k:v for k,v in spec.items() if k != 'id'} for spec in item['opponents']] == parameters,
                     'Matched opponent parameters or condition changed')
    return arms, fields, maps, fixtures


def _context(registration_path, registry_path):
    registration_path, registry_path = Path(registration_path).resolve(), Path(registry_path).resolve()
    registry = auth.load_registry(registry_path)
    pointer_path = registration_path.parent/'distributed_control_v2/acceptance.json'
    pointer, pointer_sha, authority_id = _signed(registry, 'study-acceptance', pointer_path)
    _require(set(pointer) == {'canonical_output', 'acceptance_sha256', 'source_registration_sha256',
                             'actual_extra_games', 'primary_games_accepted'}, 'Malformed canonical study acceptance pointer')
    directory = Path(pointer['canonical_output']).resolve()
    _require(str(directory) == pointer['canonical_output']
             and directory.is_relative_to((core.ROOT/'.cache/distributed_campaign').resolve()),
             'Canonical accepted output is outside the owner control cache')
    accepted, acceptance_sha, _ = _signed(registry, 'acceptance', directory/'acceptance.json')
    _require(acceptance_sha == pointer['acceptance_sha256'], 'Canonical acceptance pointer changed')
    for item in (pointer, accepted):
        _require(_integer(item['actual_extra_games'], EXPECTED_GAMES, EXPECTED_GAMES)
                 and _integer(item['primary_games_accepted'], 0, 0), 'Study is incomplete or primary credit changed')
    _require(accepted['format'] == p.FORMAT and accepted['role'] == 'extra_control_assignment'
             and accepted['approved'] is True and _integer(accepted['bmcts_audits'], 0, 0)
             and accepted['production_promoted'] is False
             and accepted['all_original_rows_physically_replayed'] is True
             and accepted['all_actual_original_rows_have_different_slot_peer_audit'] is True
             and _integer(accepted['gold_study_cases_counted_once'], 8, 8)
             and _integer(accepted['qualification_replica_games_credited'], 0, 0)
             and _integer(accepted['remote_full_actor_callbacks'], EXPECTED_GAMES*320, EXPECTED_GAMES*320)
             and _integer(accepted['remote_public_memory_oracles'], 0, EXPECTED_GAMES*320)
             and accepted['remote_public_memory_oracles'] % 80 == 0
             and _integer(accepted['owner_canary_games'], 8, EXPECTED_GAMES)
             and accepted['owner_canary_callbacks'] == accepted['owner_canary_games']*320,
             'Acceptance lacks complete extra-study physical/audit/counting assurance')
    _require(all(type(accepted[key]) is str and HEX.fullmatch(accepted[key]) for key in
                 ('study_registration_sha256', 'plan_sha256', 'audit_plan_sha256', 'games_sha256')),
             'Malformed accepted evidence fingerprints')
    registration, registration_sha = _sealed(registration_path, 100*1024*1024)
    _require(registration_sha == REGISTRATION_SHA256 == pointer['source_registration_sha256']
             == accepted['study_registration_sha256'], 'This is not the exact frozen V2 registration')
    architectures.validate(registration)
    design = _design(registration)
    _require(accepted['campaign_id'] == registration['campaign_id'], 'Accepted campaign identity changed')
    plan, plan_sha, _ = _signed(registry, 'plan', directory/'plan.json')
    _require(plan_sha == accepted['plan_sha256'] and plan['role'] == 'extra_control_assignment'
             and plan['format'] == p.FORMAT and plan['campaign_id'] == registration['campaign_id'] and _integer(plan['generation'], 0, 0)
             and plan['source_registration_path'] == str(registration_path)
             and plan['source_registration_sha256'] == registration_sha and plan['registry_path'] == str(registry_path)
             and _integer(plan['planned_extra_games'], EXPECTED_GAMES, EXPECTED_GAMES) and _integer(plan['primary_games_accepted'], 0, 0)
             and _integer(plan['bmcts_audits'], 0, 0) and plan['production_promotion'] is False
             and type(accepted['trust_model']) is str and accepted['trust_model'] == plan['trust_model'],
             'Authenticated plan has a foreign source, role, authority or cohort')
    binding, binding_sha, _ = _signed(registry, 'study-binding', registration_path.parent/'distributed_control_v2/binding.json')
    _require(binding == dict(source_registration_path=str(registration_path), source_registration_sha256=registration_sha,
                            canonical_output=str(directory), helpers=plan['helpers'], registry_path=str(registry_path),
                            role='extra_control_assignment',
                            rule='One owner-issued original-game cohort per frozen study; alternate outputs cannot resubmit it.'),
             'Canonical study binding disagrees with the accepted controller')
    return registration, design, directory/'games.jsonl', dict(
        authority_id=authority_id, campaign_id=registration['campaign_id'], registration_sha256=registration_sha,
        study_acceptance_sha256=pointer_sha, acceptance_sha256=acceptance_sha, plan_sha256=plan_sha,
        study_binding_sha256=binding_sha, games_sha256=accepted['games_sha256'],
        audit_plan_sha256=accepted['audit_plan_sha256'], accepted_extra_games=EXPECTED_GAMES,
        canonical_output=str(directory), owner_runtime=plan['owner_runtime'], helpers=plan['helpers'],
        trust_model=accepted['trust_model'])


@dataclass
class Bucket:
    games: int = 0
    pw2: int = 0
    score_sum: int = 0
    score_min: int | None = None
    score_max: int = 0
    focal_max: float = 0
    first_max: float = 0
    regular_max: float = 0
    all_max: float = 0

    def __post_init__(self):
        self.histogram = [0]*7
        self.focal_totals, self.all_totals, self.elapsed = [], [], []

    def add(self, row, pw2):
        self.games += 1; self.pw2 += pw2; self.score_sum += row['focal_score']
        self.score_min = row['focal_score'] if self.score_min is None else min(self.score_min, row['focal_score'])
        self.score_max = max(self.score_max, row['focal_score']); self.histogram[pw2] += 1
        focal = row['timing'][row['focal_seat']]
        self.focal_totals.append(focal['total_ms'])
        self.all_totals.append(math.fsum(t['total_ms'] for t in row['timing']))
        self.elapsed.append(row['elapsed_s'])
        self.focal_max = max(self.focal_max, focal['max_ms']); self.first_max = max(self.first_max, focal['first_ms'])
        self.regular_max = max(self.regular_max, focal['regular_max_ms'])
        self.all_max = max(self.all_max, *(t['max_ms'] for t in row['timing']))

    def summary(self):
        return dict(games=self.games, pairwise_numerator_sum=self.pw2, mean_pairwise=_fraction(self.pw2, 2*self.games),
                    pairwise_numerator_histogram=self.histogram, mean_raw_score=_fraction(self.score_sum, self.games),
                    raw_score_sum=self.score_sum, raw_score_min=self.score_min, raw_score_max=self.score_max, faults=0,
                    timing=dict(focal_calls=80*self.games, focal_total_ms=math.fsum(self.focal_totals),
                                focal_mean_call_ms=math.fsum(self.focal_totals)/(80*self.games), focal_max_ms=self.focal_max,
                                focal_first_max_ms=self.first_max, focal_regular_max_ms=self.regular_max,
                                all_player_calls=320*self.games, all_player_total_ms=math.fsum(self.all_totals),
                                all_player_max_ms=self.all_max, summed_game_elapsed_s=math.fsum(self.elapsed)))


def _row(row, fixture):
    _require(type(row) is dict and set(row) == {'candidate', 'fixture', 'map_id', 'focal_seat', 'field', 'scores',
             'focal_pw', 'focal_score', 'opponent_ids', 'actions', 'timing', 'faults', 'elapsed_s'}, 'Malformed accepted game row')
    _require(row['candidate'] == fixture['candidate'] and row['fixture'] == fixture['id'] and row['map_id'] == fixture['map_id']
             and row['field'] == fixture['field'] and type(row['focal_seat']) is int and row['focal_seat'] == fixture['seat']
             and row['opponent_ids'] == [spec['id'] for spec in fixture['opponents']] and row['faults'] == [],
             'Accepted game source, fixture, condition, opponent or fault record changed')
    _require(type(row['scores']) is list and len(row['scores']) == 4
             and all(_integer(score, 0, 2**63-1) for score in row['scores'])
             and type(row['focal_score']) is int and row['focal_score'] == row['scores'][fixture['seat']],
             'Invalid accepted integer score vector')
    own = row['focal_score']
    pw2 = sum(2 if own > score else 1 if own == score else 0 for i, score in enumerate(row['scores']) if i != fixture['seat'])
    _require(type(row['focal_pw']) in (int, float) and row['focal_pw'] == pw2/2, 'Pairwise result disagrees with final scores')
    _require(type(row['actions']) is list and len(row['actions']) == 80
             and all(type(joint) is list and len(joint) == 4 and all(type(action) is str and action in ACTION_NAMES for action in joint)
                     for joint in row['actions']), 'Accepted game has an incomplete or malformed action transcript')
    _require(type(row['timing']) is list and len(row['timing']) == 4 and _number(row['elapsed_s']), 'Invalid game timing')
    for timing in row['timing']:
        _require(type(timing) is dict and set(timing) == {'calls', 'total_ms', 'max_ms', 'first_ms', 'regular_max_ms'}
                 and _integer(timing['calls'], 80, 80)
                 and all(_number(timing[key]) for key in ('total_ms', 'max_ms', 'first_ms', 'regular_max_ms'))
                 and timing['max_ms'] == max(timing['first_ms'], timing['regular_max_ms'])
                 and timing['total_ms'] >= timing['max_ms'] and timing['first_ms'] <= 2000 and timing['regular_max_ms'] <= 200,
                 'Malformed or out-of-budget accepted callback timing')
    return pw2


def _collect(path, design, expected_sha):
    arms, fields, maps, fixtures = design
    mi, ai, fi = ({key:i for i,key in enumerate(values)} for values in (maps, arms, fields))
    cube = [[[0]*4 for _ in arms] for _ in maps]
    overall = [Bucket() for _ in arms]
    by_field = [[Bucket() for _ in fields] for _ in arms]
    seen, cells, digest = set(), Counter(), hashlib.sha256()
    _require(Path(path).stat().st_size <= 1024**3, 'Accepted games file exceeds its explicit one-GiB bound')
    with Path(path).open('rb') as stream:
        while True:
            line = stream.readline(256*1024+1)
            if not line:
                break
            _require(len(line) <= 256*1024 and line.endswith(b'\n') and line.strip(), 'Torn, empty or oversize accepted game row')
            digest.update(line)
            row = p.loads(line)
            identity = row.get('fixture') if type(row) is dict else None
            _require(identity in fixtures and identity not in seen and len(seen) < EXPECTED_GAMES,
                     'Duplicate, foreign or excess accepted fixture')
            fixture = fixtures[identity]
            pw2 = _row(row, fixture)
            seen.add(identity)
            cell = (fixture['map_id'], fixture['candidate'], fixture['field'], fixture['seat'], fixture['token'])
            cells[cell] += 1
            m, a, f = mi[fixture['map_id']], ai[fixture['candidate']], fi[fixture['field']]
            cube[m][a][f] += pw2
            overall[a].add(row, pw2); by_field[a][f].add(row, pw2)
    _require(digest.hexdigest() == expected_sha, 'Exact accepted games-file hash changed')
    _require(seen == set(fixtures) and len(seen) == EXPECTED_GAMES and len(cells) == EXPECTED_GAMES
             and set(cells.values()) == {1}, 'Complete unique map/source/field/seat/token coverage is required before analysis')
    return cube, overall, by_field


def _bootstrap(cube, plan):
    """Pure arithmetic helper. CLI reaches this only after full authentication."""
    _require(plan == architectures.inference_plan(), 'Preregistered inference plan changed')
    _require(2 <= len(cube) <= 256 and all(len(row) == 4 and all(len(fields) == 4 and
             all(_integer(total, 0, 6*16) for total in fields) for fields in row) for row in cube), 'Invalid map aggregate cube')
    map_sums = [tuple(sum(fields) for fields in row) for row in cube]
    m = len(map_sums)
    pairs = [(i,j) for i in range(4) for j in range(i+1,4)]
    samples = [array('i') for _ in pairs]
    rng, draws_sha = random.Random(plan['bootstrap_seed']), hashlib.sha256()
    for _ in range(plan['bootstrap_replicates']):
        totals = [0]*4
        indices = [rng.randrange(m) for _ in range(m)]
        draws_sha.update(bytes(indices))
        for index in indices:
            row = map_sums[index]
            totals[0] += row[0]; totals[1] += row[1]; totals[2] += row[2]; totals[3] += row[3]
        for k,(i,j) in enumerate(pairs):
            samples[k].append(totals[i]-totals[j])
    low, high = plan['order_statistic_indices_zero_based']
    results, denominator = [], 2*64*m
    for (i,j), values in zip(pairs, samples):
        values = sorted(values)
        observed = sum(row[i]-row[j] for row in map_sums)
        field_contrasts = [sum(row[i][f]-row[j][f] for row in cube) for f in range(4)]
        first_worst = min(sum(row[i][f] for row in cube) for f in range(4))
        second_worst = min(sum(row[j][f] for row in cube) for f in range(4))
        results.append(dict(first=architectures.ARMS[i], second=architectures.ARMS[j],
                            mean_pairwise_difference=_fraction(observed, denominator),
                            descriptive_bonferroni_interval=[_fraction(values[low],denominator), _fraction(values[high],denominator)],
                            interval_contains_zero=values[low] <= 0 <= values[high],
                            field_mean_differences={field:_fraction(value, 2*16*m) for field,value in zip(core.FIELDS,field_contrasts)},
                            minimum_paired_field_difference=_fraction(min(field_contrasts), 2*16*m),
                            worst_field_mean_difference=_fraction(first_worst-second_worst, 2*16*m)))
    return results, dict(algorithm=BOOTSTRAP_ALGORITHM, shared_map_draws_for_all_six=True,
                         map_order='Frozen registration maps array', replicates=plan['bootstrap_replicates'],
                         seed=plan['bootstrap_seed'], draw_indices_sha256=draws_sha.hexdigest(),
                         percentile_indices_zero_based=[low,high], map_clusters=m,
                         interpretation=plan['caveat'], finite_sample_familywise_coverage_proved=False)


def analyze(registration_path, registry_path):
    """Read only: no partial rankings, game execution, promotion or credits."""
    started, source_guard = time.perf_counter(), _source_hashes()
    registration, design, games_path, provenance = _context(registration_path, registry_path)
    cube, overall, fields = _collect(games_path, design, provenance['games_sha256'])
    before_bootstrap = time.perf_counter()
    comparisons, bootstrap = _bootstrap(cube, registration['protocol']['inference'])
    arm_results = []
    for i, candidate in enumerate(registration['candidates']):
        result = dict(name=candidate['name'], sha256=candidate['sha256'], **overall[i].summary())
        result['fields'] = {field:bucket.summary() for field,bucket in zip(design[1],fields[i])}
        minimum = min(Fraction(bucket.pw2,2*bucket.games) for bucket in fields[i])
        result['worst_field_mean_pairwise'] = _fraction(minimum.numerator,minimum.denominator)
        result['worst_fields'] = [field for field,bucket in zip(design[1],fields[i]) if Fraction(bucket.pw2,2*bucket.games) == minimum]
        arm_results.append(result)
    _require(source_guard == _source_hashes(), 'Analysis source changed during computation; discard the report')
    return dict(format=FORMAT, role='report_only_extra_study', provenance=provenance, inference_plan=registration['protocol']['inference'],
                coverage=dict(complete=True, unique_games=EXPECTED_GAMES, maps=EXPECTED_MAPS, arms=4, fields=4,
                              seat_token_crosses=16, games_per_arm=8192, games_per_arm_field=2048,
                              all_registered_fixtures_once=True, faults=0),
                arms=arm_results, comparisons=comparisons, bootstrap=bootstrap, source_sha256=source_guard,
                timings=dict(validation_and_collection_s=before_bootstrap-started,
                             statistics_s=time.perf_counter()-before_bootstrap, total_report_s=time.perf_counter()-started),
                timing_caveat='Recorded timings include different owner/helper hardware, process allocation and concurrent load. They are descriptive and not a hardware-normalized policy-speed ranking.',
                field_inference='Field means and field contrasts are descriptive point estimates; no additional simultaneous field intervals are claimed.',
                new_games_executed=0, new_actor_callbacks=0, primary_match_credit=0, completed_game_audit_credit=0,
                full_bmcts_audit_credit=0, promoted=False, tuning_performed=False,
                caveat='All six preregistered descriptive map-cluster contrasts are reported. This is not universal superiority, a finite-sample familywise guarantee, or an automatic release decision.')
