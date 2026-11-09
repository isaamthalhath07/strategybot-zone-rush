"""Preregister a public-boundary experiment, then evaluate responding branches.

Preparation performs physics/public accounting only. It never calls an actor or
the teacher. Execution is a separate, exclusive operation after publication.
"""
import argparse
import copy
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import random
import time
import zipfile

from evolution import oversight
from primary_campaign import core
from search_coach.belief import PublicObservation
from tests import reference_engine as engine


ROOT = core.ROOT
FORMAT = 'zone-rush-joint-intent-causal-usefulness/1'
STAGE = ROOT/'.cache/primary/campaign_v1_20261109/train_000'
FIELDS = tuple(core.FIELDS)
TURNS = (30, 50, 65, 75)
SNAPSHOT = 'primary_campaign/evidence/accepted_stages_000_004.json'
SNAPSHOT_SHA256 = 'c54517e04524718d7ef9f576c78403b56126e04354ce318795380b976b4daa36'
EXCLUSION_PINS = {
    'coaching_trials/evidence/usefulness_001.zip': '6c722683cbb1a9b0bcba585a36604e6b30ed58363dae398308787a3a41a2c1e2',
    'coaching_trials/evidence/summary.json': '6e7bc9dc783e1c1d95073ba6e39c8a24f4ebb363db8f2757da131ad978081e24',
    'opponent_prediction/evidence/intent_001/registration.json': '1f57d80d08e1632ea220ce935955d0cfe52e2afa5df247a05f4465dff1c5008f',
    'opponent_prediction/evidence/intent_001/preregistration_evidence.json': 'df1c074ec7a3325f3bcf9562a13e28d244f40dcdc7c6e39ddb80d10ca63b9fec',
}
SEARCH = dict(simulations=96, horizon=6, beam_width=6, exploration=1.4,
              max_nodes=512, income_tail=12, max_states=1024, max_particles=65536,
              max_joint_intents=200000, max_joint_sampling_terms=4194304, trace=True)


def sha(body):
    return hashlib.sha256(body).hexdigest()


def public(view):
    return PublicObservation.from_view(view).serializable()


def source_pins():
    # Explicit runtime/helper closure. No existing file is changed by this module.
    names = ('bot.py', 'intent_trials/__init__.py', 'intent_trials/experiment.py',
             'intent_search/__init__.py', 'intent_search/mcts.py',
             'opponent_prediction/intent_filter.py', 'search_coach/belief.py',
             'gpu_tree_coach/protocol.py', 'gpu_tree_coach/tree.py',
             'evolution/oversight.py', 'evolution/runner.py', 'evolution/opponents.py',
             'evolution/maps.py', 'evolution/genomes.py', 'evolution/league.py',
             'primary_campaign/core.py', 'tests/reference_engine.py',
             'simulator/vendor_harness/referee.py', 'tester_bots/research_alternative.py',
             'tester_bots/racer.py', 'tester_bots/blocker.py')
    pins = {name: sha((ROOT/name).read_bytes()) for name in names}
    if pins['bot.py'] != core.INCUMBENT:
        raise ValueError('The immutable e8 incumbent changed')
    # This checks the teacher/model/referees without preparing a search root.
    from intent_search import mcts
    mcts.source_pins()
    return pins


def public_accounting(previous, current, scores):
    """Reconstruct all scores using public cells alone; no referee counter input."""
    current = PublicObservation.from_view(current)
    if len(scores) != 4 or any(type(value) is not int for value in scores):
        raise ValueError('Four exact public reconstructed scores required')
    result, income = list(scores), [0]*4
    prior = PublicObservation.from_view(previous) if previous is not None else None
    for index, cell in enumerate(current.cells):
        _, owner, upgraded, _, _, base = cell
        if owner:
            income[owner-1] += base*(1+int(upgraded))
        if prior is not None:
            old = prior.cells[index]
            if old[5] != base or old[3] != cell[3]:
                raise ValueError('Immutable public map/home changed')
            if old[1] and owner and old[1] != owner:
                result[owner-1] += 8*base*(1+int(old[2]))
    if prior is not None:
        result = [value+increment for value,increment in zip(result,income)]
    elif result != [0]*4:
        raise ValueError('Opening public scores must be zero')
    return result, income


def public_context(observation, scores, turn):
    """Selection features depend only on the root public view and prior scores."""
    observation = PublicObservation.from_view(observation)
    if type(turn) is not int or turn not in TURNS:
        raise ValueError('Only the four fixed decision turns are eligible')
    if len(scores) != 4 or any(type(value) is not int for value in scores):
        raise ValueError('Four prior public reconstructed scores required')
    focal = observation.bot_id-1
    cell = observation.cells[observation.positions[focal]]
    if cell[4] or len(observation.legal_actions) < 3:
        return None
    _,income = public_accounting(None, observation, [0]*4)
    projected = [score+(81-turn)*rate for score,rate in zip(scores,income)]
    margins = [abs(projected[focal]-projected[rival]) for rival in range(4) if rival != focal]
    return dict(turn=turn, public_scores=list(scores), public_income=income,
                remaining_turns=81-turn, projected_scores=projected,
                nearest_projected_rank_margin=min(margins),
                legal_actions=list(observation.legal_actions), focal_publicly_unfrozen=True)


def select_cases(candidates, excluded_orbits):
    """Greedy turn-major/field-major minimum public margin, then fixture SHA."""
    used, selected = set(excluded_orbits), []
    for turn in TURNS:
        for field in FIELDS:
            eligible = [case for case in candidates if case['turn'] == turn and case['field'] == field
                        and case['rotation_orbit'] not in used]
            if not eligible:
                raise ValueError('Insufficient distinct nonexcluded eligible maps; no case replacement policy')
            chosen = min(eligible, key=lambda case: (case['nearest_projected_rank_margin'], case['fixture']))
            selected.append(copy.deepcopy(chosen))
            used.add(chosen['rotation_orbit'])
    return selected


def _snapshot():
    body = (ROOT/SNAPSHOT).read_bytes()
    if sha(body) != SNAPSHOT_SHA256:
        raise ValueError('Published accepted-100k snapshot changed')
    snapshot = oversight.strict_loads(body)
    if (snapshot['primary_games_accepted'] != 100000 or snapshot['callbacks_regenerated'] != 32000000
            or [entry['generation'] for entry in snapshot['stages']] != list(range(5))
            or snapshot['bmcts_audits'] != 0 or snapshot['promoted'] is not False):
        raise ValueError('Exact accepted stages 0 through 4 required')
    return snapshot


def _admission(stage):
    stage = Path(stage).resolve()
    if stage != STAGE.resolve():
        raise ValueError('Only the fixed accepted TRAIN stage0 is authorized')
    receipt = _snapshot()['stages'][0]
    files = dict(receipt['exact_copy_files'], **{
        'registration.json': receipt['registration_sha256'],
        'games.jsonl': receipt['games_sha256'], 'actor_audits.jsonl': receipt['actor_audits_sha256']})
    for name, expected in files.items():
        body = (stage/name).read_bytes()
        if sha(body) != expected:
            raise ValueError('Exact admitted stage0 raw bytes changed: '+name)
        if name in receipt['exact_copy_files'] and body != (ROOT/'primary_campaign/evidence/train_000'/name).read_bytes():
            raise ValueError('Published stage0 exact-copy bytes differ')
    registration = core.read_sealed(stage/'registration.json')
    audit = core.read_sealed(stage/'audit.json')
    core.check_guards(registration['guards'])
    if (registration['generation'] != 0 or registration['phase'] != 'train'
            or audit['approved'] is not True or audit['all_actors_regenerated'] is not True
            or audit['callbacks_regenerated'] != 6400000 or audit['primary_games_accepted'] != 20000
            or audit['registration_sha256'] != receipt['registration_sha256']
            or audit['games_sha256'] != receipt['games_sha256']
            or audit['actor_audits_sha256'] != receipt['actor_audits_sha256']
            or audit['campaign_id'] != registration['campaign_id']):
        raise ValueError('Stage0 admission and source bindings differ')
    return registration, files


def _exclusions(registration, catalog):
    for name, expected in EXCLUSION_PINS.items():
        if sha((ROOT/name).read_bytes()) != expected:
            raise ValueError('Published prior-experiment exclusion evidence changed')
    with zipfile.ZipFile(ROOT/'coaching_trials/evidence/usefulness_001.zip') as archive:
        body = archive.read('registration.json')
        if sha(body) != archive.read('registration.sha256').decode().strip():
            raise ValueError('Prior coaching registration seal changed')
        old = oversight.strict_loads(body)
    pilot = core.read_sealed(ROOT/'opponent_prediction/evidence/intent_001/registration.json')
    evidence = oversight.strict_loads((ROOT/'opponent_prediction/evidence/intent_001/preregistration_evidence.json').read_bytes())
    if (evidence['registration_sha256'] != EXCLUSION_PINS['opponent_prediction/evidence/intent_001/registration.json']
            or len(old['cases']) != 8 or len(pilot['selected']) != 16):
        raise ValueError('Prior experiment case counts/source binding changed')
    fixtures = {fixture['id']: fixture for fixture in registration['fixtures']}
    maps = {board['id']:board for board in catalog}
    coach_maps = [fixtures[case['fixture']]['map_id'] for case in old['cases']]
    pilot_maps = [case['map_id'] for case in pilot['selected']]
    if len(set(coach_maps)) != 8 or len(set(pilot_maps)) != 16:
        raise ValueError('Published exclusions lack distinct old maps')
    return dict(source_sha256=dict(EXCLUSION_PINS), coaching_registration_sha256=sha(body),
                coaching_map_ids=coach_maps, forecast_pilot_map_ids=pilot_maps,
                coaching_rotation_orbits=[maps[identity]['rotation_orbit'] for identity in coach_maps],
                forecast_pilot_rotation_orbits=[maps[identity]['rotation_orbit'] for identity in pilot_maps],
                policy='Exclude all 8 old coaching and all16 forecast pilot map rotation orbits; abort if insufficient, never relax.')


def _selection_candidates(stage, registration):
    fixtures = {fixture['id']: fixture for fixture in registration['fixtures'] if fixture['candidate'] == core.INCUMBENT}
    found, candidates = set(), []
    # No row final score, root/future intention or model output is consulted.
    with (stage/'games.jsonl').open('rb') as handle:
        for line in handle:
            row = oversight.strict_loads(line)
            if row['candidate'] != core.INCUMBENT:
                continue
            fixture = fixtures[row['fixture']]
            if fixture['id'] in found:
                raise ValueError('Duplicate incumbent source row')
            found.add(fixture['id'])
            game = engine.Game(base=fixture['base'], start_token=fixture['token'], rules={'catch_requires_stay':True})
            shadow = oversight.referee.Referee(fixture['base'], start_token=fixture['token'], rules=game.rules)
            focal = fixture['seat']
            previous = PublicObservation.from_view(game.views()[focal])
            scores,income = public_accounting(None,previous,[0]*4)
            opening, transitions = previous.serializable(), []
            for turn in range(1,max(TURNS)+1):
                if scores != game.score or income != game.income:
                    raise ValueError('Independent public score/income reconstruction disagrees with observer')
                if turn in TURNS:
                    context = public_context(previous,scores,turn)
                    if context is not None:
                        prefix = dict(initial_observation=opening,transitions=transitions)
                        candidates.append(dict(context,fixture=fixture['id'],field=fixture['field'],map_id=fixture['map_id'],
                            rotation_orbit=core.rotation_orbit(fixture['base']),
                            public_prefix_sha256=sha(core.canonical(prefix))))
                if turn == max(TURNS):
                    break
                joint = row['actions'][turn-1]  # Strictly before every resulting root view.
                if any(type(action) is not str or action not in game.legal(seat) or action not in shadow.legal(seat)
                       for seat,action in enumerate(joint)) or len(joint) != 4:
                    raise ValueError('Illegal prior recorded action')
                game.step(joint); shadow.step(joint); oversight.state_equal(game,shadow)
                current = PublicObservation.from_view(game.views()[focal])
                scores,income = public_accounting(previous,current,scores)
                transitions.append(dict(own_action=joint[focal],observation=current.serializable()))
                previous = current
    if found != set(fixtures):
        raise ValueError('Complete incumbent TRAIN source rows required')
    return candidates


def _facts(stage):
    stage = Path(stage).resolve()
    registration,files = _admission(stage)
    # Metadata only, including reserved partitions; no reserved game/outcome file.
    manifest,catalog = core.load_catalog(stage.parent)
    core.validate_registration(registration,manifest,catalog)
    exclusions = _exclusions(registration,catalog)
    candidates = _selection_candidates(stage,registration)
    excluded = exclusions['coaching_rotation_orbits']+exclusions['forecast_pilot_rotation_orbits']
    selected = select_cases(candidates,excluded)
    return dict(stage_directory=str(stage),campaign_id=registration['campaign_id'],generation=0,
                stage_files_sha256=files,accepted_snapshot_sha256=SNAPSHOT_SHA256,
                manifest_sha256=sha((stage.parent/'manifest.json').read_bytes()),
                catalog_sha256=sha((stage.parent/'catalog.json').read_bytes()),
                candidate_sha256=core.INCUMBENT,exclusions=exclusions,
                eligible_public_roots=len(candidates),selected=selected)


def _protocol(facts):
    return dict(format=FORMAT,**facts,source_sha256=source_pins(),
        selection=dict(turns=list(TURNS),fields=list(FIELDS),order='turn-major then fixed field order',
            eligibility='Focal publicly unfrozen and at least3 public legal actions; sixteen distinct nonexcluded rotation orbits.',
            rank='Minimum nearest focal-versus-rival absolute projected score margin, then ascending fixture SHA256.',
            projection='Public score after t-1 plus (81-t)*public current income; score from ownership/capture changes and postturn income only.',
            forbidden='No current/future recorded action, final score, search recommendation, actual rival state/type/seed or outcome feature.',
            replay='Prior recorded joint actions drive two-referee physics only; no controller/model calls in selection.'),
        search=dict(SEARCH,seeds=[202611092300+index for index in range(16)],
            seed_rule='Explicit diagnostic seed202611092300+zero-based public selected case order; no actual rival seed/type/state input.',
            capacity='No posterior pruning or dropped case. Beam6 retains all legal actions. Frozen node-cap512 behavior uses the fixed public economic rollout at the same public history; it does not remove posterior explanations.'),
        intervention='After simultaneous original public actor calls, replace focal root action and synchronize _history[seat+1][last]; retain planner intent/target/bait updates. Then original focal act continues. This is a hybrid intervention, not an unchanged bot.',
        branches='Independent fresh controllers and RNG rebuilt from pinned sources/prefix for baseline and every legal root action; actual responding rivals after deviation, never future tape. All80turns/320callbacks in both referees, including original focal call before override.',
        baseline='Unchanged baseline and explicit baseline-action intervention must both regenerate complete original80-joint-action transcript and scores exactly, and match each other.',
        checks='Every callback strict four-field immutable public view, legal in both referees, <=2000ms first/200ms regular, no fallback, supported public score/progress/cooldown memory oracle after decision; actual coverage counters.',
        metric='Equal-field mean selected-teacher minus baseline official pairwise points0..3 (one per beaten rival, half per tie); all16 per-case values.',
        diagnostics='Evaluate ALL legal root alternatives. Report hindsight-best-one-step among these interventions versus this realized responding rival instance; no global optimum/equilibrium claim.',
        bootstrap=dict(replicates=20000,seed=202611092330,quantile_indices=[499,19499],
            allocation='Resample4 maps with replacement within each fixed field; equal field weights.',
            algorithm='stdlib Random(seed).randrange(4); replicate-major, FIELDS order,4 draws per field, original selected case order within field; shared draws for teacher and hindsight-opportunity deltas.',
            scope='Unadjusted descriptive95% percentile interval for consumed TRAIN boundary-selected sample; no universal strength, fresh-data or simultaneous guarantee.'),
        failure_policy='Any disagreement, deadline, unsupported history, inference/work cap, illegal/mutated input, fallback, missing branch/case or nonfinite value aborts whole experiment. Preserve partial files/error evidence; no replacement, cap change, pruning, tuning or silent retry after results.',
        execution_gate='Publish and commit complete sealed registration plus reviewed runtime source pins before execute; preparation produces zero teacher recommendations/controller callbacks/outcomes.',
        data_scope='Existing consumed accepted primary TRAIN stage0 e8 positions only; metadata catalog validates exclusions/TRAIN assignment. No new primary match, reserved development/final outcome, completed per-game BMCTS audit or promotion.',
        primary_games=0,completed_per_game_bmcts_audits=0,promoted=False)


def prepare(stage, output):
    output = Path(output).resolve()
    if output.exists() or output.is_relative_to(Path(stage).resolve().parent):
        raise ValueError('Fresh output outside immutable primary campaign required')
    protocol = _protocol(_facts(stage))
    output.mkdir(parents=True,exist_ok=False)
    core.seal(output/'registration.json',protocol)
    return protocol


def _validated(directory):
    protocol = core.read_sealed(Path(directory)/'registration.json')
    if protocol['source_sha256'] != source_pins():
        raise ValueError('Exact causal protocol runtime source changed')
    expected = _protocol(_facts(Path(protocol['stage_directory'])))
    if core.canonical(protocol) != core.canonical(expected):
        raise ValueError('Exact causal protocol/source/selection/claim changed, even if rehashed')
    return protocol


@dataclass(frozen=True, slots=True)
class PublicCell:
    occupant: int
    owner: int
    is_upgraded: bool
    is_home: bool
    is_frozen: bool
    base_points: int


@dataclass(frozen=True, slots=True)
class ActorView:
    board: tuple
    bot_id: int
    is_priority_token: bool
    legal_actions: tuple


def immutable_view(view):
    obs = PublicObservation.from_view(view)
    # PublicObservation canonicalizes legal actions for model hashing. Actual
    # controllers must retain the admitted view's ordering for exact RNG/ties.
    original_legal = tuple(view['legal_actions'] if isinstance(view,dict) else view.legal_actions)
    return ActorView(tuple(tuple(PublicCell(*cell) for cell in obs.cells[r*8:(r+1)*8]) for r in range(8)),
                     obs.bot_id,obs.is_priority_token,original_legal)


def actor_actions(game, shadow, actors, namespaces, audit):
    # All four snapshots are made before any actor callback/override.
    views = [immutable_view(view) for view in game.views()]
    result = []
    for seat,supplied in enumerate(views):
        if set(supplied.__slots__) != {'board','bot_id','is_priority_token','legal_actions'}:
            raise ValueError('Extra actor inputs')
        before = oversight.signature(supplied)
        started = time.perf_counter()
        action = actors[seat](supplied)
        elapsed = time.perf_counter()-started
        audit['callbacks_regenerated'] += 1
        audit['calls_by_seat'][seat] += 1
        audit['max_callback_ms'] = max(audit['max_callback_ms'],elapsed*1000)
        timings = audit.setdefault('timing',[dict(calls=0,total_ms=0.0,first_ms=0.0,regular_max_ms=0.0,max_ms=0.0) for _ in range(4)])
        timing = timings[seat]
        ms = elapsed*1000
        timing['calls'] += 1
        timing['total_ms'] += ms
        timing['max_ms'] = max(timing['max_ms'],ms)
        if game.turn == 1:
            timing['first_ms'] = ms
        else:
            timing['regular_max_ms'] = max(timing['regular_max_ms'],ms)
        if elapsed > (2 if game.turn == 1 else .2):
            raise ValueError('Actor callback missed deadline')
        if oversight.signature(supplied) != before:
            raise ValueError('Actor mutated public input')
        if type(action) is not str or action not in game.legal(seat) or action not in shadow.legal(seat):
            raise ValueError('Illegal actor decision')
        namespace = namespaces[seat]
        if namespace is not None:
            if namespace.get('_input_failures',0) or namespace.get('_policy_failures',0):
                raise ValueError('Actor fallback')
            memory = namespace.get('_history',{}).get(seat+1,{})
            if 'cooldown_possible' in memory:
                if (memory.get('inference_failures',0) or memory['progress'] != game.prog[seat]
                        or memory['scores'][1:] != game.score
                        or any(game.cd[index] not in memory['cooldown_possible'][index+1] for index in range(4))):
                    raise ValueError('Public memory lost referee-consistent truth')
                audit['public_memory_oracles'] += 1
        result.append(action)
    return result


def continuation(candidate, case, sources, requested=None):
    """Rebuild all80 turns and preserve partial branch evidence on an exception."""
    partial = {}
    try:
        return _continuation(candidate,case,sources,requested,partial)
    except BaseException as error:
        # Keep the exact failed branch's accumulated trace/coverage available to
        # execute's immutable error record; no partial branch earns completion.
        error.branch_evidence = partial
        raise


def _continuation(candidate, case, sources, requested, partial):
    """Rebuild the full actual world afresh; never splice a recorded future tape."""
    fixture,row,turn = case['fixture'],case['row'],case['turn']
    if type(turn) is not int or not 1 <= turn <= 80 or (requested is not None and type(requested) is not str):
        raise ValueError('A bounded root turn and optional string intervention are required')
    actors,namespaces = oversight.make_actors(candidate,fixture,sources)
    game = engine.Game(base=fixture['base'],start_token=fixture['token'],rules={'catch_requires_stay':True})
    shadow = oversight.referee.Referee(fixture['base'],start_token=fixture['token'],rules=game.rules)
    audit = dict(callbacks_regenerated=0,calls_by_seat=[0]*4,dual_referee_turns=0,
                 public_memory_oracles=0,max_callback_ms=0.0)
    focal,trace = fixture['seat'],[]
    partial.update(audit=audit,actions=trace,requested=requested,root_turn=turn)
    # Only this observer reads the actual original root action/outcome.
    explicit_baseline = requested is not None and requested == row['actions'][turn-1][focal]
    previous = PublicObservation.from_view(game.views()[focal])
    scores,income = public_accounting(None,previous,[0]*4)
    oversight.state_equal(game,shadow)
    while not game.over():
        partial['current_turn'] = game.turn
        joint = actor_actions(game,shadow,actors,namespaces,audit)
        if game.turn == turn and requested is not None:
            if requested not in game.legal(focal) or requested not in shadow.legal(focal):
                raise ValueError('Illegal focal intervention')
            joint[focal] = requested
            memory = namespaces[focal]['_history'][focal+1]
            memory['last'] = requested
        # No recorded post-root action is read on a deviating branch.
        if game.turn < turn or requested is None or explicit_baseline:
            if joint != row['actions'][game.turn-1]:
                raise ValueError('Original actor transcript does not regenerate')
        trace.append(list(joint))
        game.step(joint); shadow.step(joint); oversight.state_equal(game,shadow)
        audit['dual_referee_turns'] += 1
        current = PublicObservation.from_view(game.views()[focal])
        scores,income = public_accounting(previous,current,scores)
        if scores != game.score or income != game.income:
            raise ValueError('Independent public accounting diverged')
        previous = current
    if (audit['callbacks_regenerated'] != 320 or audit['calls_by_seat'] != [80]*4
            or audit['dual_referee_turns'] != 80 or not shadow.over()):
        raise ValueError('Incomplete branch coverage')
    if requested is None or explicit_baseline:
        if game.score != row['scores'] or trace != row['actions']:
            raise ValueError('Baseline does not reproduce complete original outcome')
    points = sum(1 if scores[focal] > score else .5 if scores[focal] == score else 0
                 for seat,score in enumerate(scores) if seat != focal)
    return dict(scores=scores,pairwise_points=points,actions=trace,
                action_trace_sha256=sha(core.canonical(trace)),audit=audit,
                intervention=requested,explicit_baseline_reproduced=explicit_baseline)


def public_job(fixture, row, case, seed):
    game = engine.Game(base=fixture['base'],start_token=fixture['token'],rules={'catch_requires_stay':True})
    shadow = oversight.referee.Referee(fixture['base'],start_token=fixture['token'],rules=game.rules)
    focal = fixture['seat']
    opening,transitions = public(game.views()[focal]),[]
    for joint in row['actions'][:case['turn']-1]:
        game.step(joint);shadow.step(joint);oversight.state_equal(game,shadow)
        transitions.append(dict(own_action=joint[focal],observation=public(game.views()[focal])))
    prefix = dict(initial_observation=opening,transitions=transitions)
    if sha(core.canonical(prefix)) != case['public_prefix_sha256']:
        raise ValueError('Preregistered public prefix changed')
    return dict(schema=1,kind='joint-intent-public-history-mcts/1',
                root_id='causal-public-case-%02d'%(seed-202611092300),**prefix,search=dict(SEARCH,seed=seed))


def statistics(cases, protocol):
    selected = protocol['selected']
    if len(cases) != 16 or any(core.canonical(result['case']) != core.canonical(case) for result,case in zip(cases,selected)):
        raise ValueError('All sixteen exact preregistered cases in order required')
    groups = [[index for index,case in enumerate(selected) if case['field'] == field] for field in FIELDS]
    if any(len(group) != 4 for group in groups) or len({case['rotation_orbit'] for case in selected}) != 16:
        raise ValueError('Four maps per field, sixteen distinct rotation orbits required')
    teacher = [case['teacher_delta_pairwise'] for case in cases]
    opportunity = [case['hindsight_opportunity_pairwise'] for case in cases]
    if any(type(value) not in (int,float) or not -3 <= value <= 3 or value*2 != int(value*2)
           for value in teacher+opportunity):
        raise ValueError('Finite official pairwise deltas required for every case')
    if any(gap < max(0,delta) or gap > 3 for gap,delta in zip(opportunity,teacher)):
        raise ValueError('All-action hindsight opportunity must include baseline and teacher')
    if any(case['recommended_action'] == case['baseline_action'] and delta != 0 for case,delta in zip(cases,teacher)):
        raise ValueError('An unchanged recommended action cannot have nonzero causal delta')
    rng = random.Random(protocol['bootstrap']['seed'])
    boot = [[],[]]
    draws = hashlib.sha256()
    for _ in range(protocol['bootstrap']['replicates']):
        indices = [group[rng.randrange(4)] for group in groups for _ in range(4)]
        draws.update(bytes(indices))
        for results,values in zip(boot,(teacher,opportunity)):
            results.append(sum(values[index] for index in indices)/16)
    lower,upper = protocol['bootstrap']['quantile_indices']
    result = dict(bootstrap=dict(protocol['bootstrap'],shared_draw_indices_sha256=draws.hexdigest()))
    for name,values,samples in zip(('selected_teacher','hindsight_opportunity'),(teacher,opportunity),boot):
        samples.sort()
        result[name] = dict(mean_delta_pairwise=sum(values)/16,
            descriptive95_interval=[samples[lower],samples[upper]],
            fields={field:sum(values[index] for index in group)/4 for field,group in zip(FIELDS,groups)})
    result.update(wins=sum(value>0 for value in teacher),losses=sum(value<0 for value in teacher),
                  ties=sum(value==0 for value in teacher),
                  recommendations_changed=sum(case['recommended_action'] != case['baseline_action'] for case in cases))
    return result


def execute(directory):
    directory = Path(directory).resolve()
    claim = directory/'.execution_claim'
    if claim.exists() or (directory/'execution_started.json').exists() or (directory/'results.json').exists():
        raise ValueError('Preserve completed/partial evidence; no automatic outcome retries')
    protocol = _validated(directory)
    # Atomic, exclusive claim: identical immutable seals alone would let two
    # concurrent callers both execute. A stale/failed claim is never removed.
    claim.mkdir(exist_ok=False)
    core.seal(directory/'execution_started.json',dict(format=FORMAT,
        registration_sha256=sha((directory/'registration.json').read_bytes()),primary_games=0))
    completed,active = [],dict(case=None,branch=None)
    try:
        stage = Path(protocol['stage_directory'])
        registration = core.read_sealed(stage/'registration.json')
        candidate = next(item for item in registration['candidates'] if item['sha256'] == core.INCUMBENT)
        fixtures = {item['id']:item for item in registration['fixtures']}
        wanted = {case['fixture'] for case in protocol['selected']}
        rows = {}
        with (stage/'games.jsonl').open('rb') as handle:
            for line in handle:
                row = oversight.strict_loads(line)
                if row['fixture'] in wanted:
                    if row['fixture'] in rows:
                        raise ValueError('Duplicate selected source row')
                    rows[row['fixture']] = row
        if set(rows) != wanted:
            raise ValueError('Selected source transcript missing')
        from intent_search import mcts
        for index,case in enumerate(protocol['selected']):
            active.update(case=index,branch='public_teacher')
            fixture,row = fixtures[case['fixture']],rows[case['fixture']]
            job = public_job(fixture,row,case,protocol['search']['seeds'][index])
            core.seal(directory/('public_input_%02d.json'%index),job)
            teacher = mcts.recommend(job)  # Exact public-only interface; no controller/world object.
            core.seal(directory/('teacher_%02d.json'%index),teacher)
            chosen = teacher['recommended_action']
            legal = case['legal_actions']
            if chosen not in legal:
                raise ValueError('Teacher selected illegal action')
            runtime_case = dict(fixture=fixture,row=row,turn=case['turn'])
            active['branch'] = 'baseline'
            baseline = continuation(candidate,runtime_case,registration['sources'])
            core.seal(directory/('baseline_%02d.json'%index),baseline)
            branches = {}
            for action in legal:
                active['branch'] = action
                branch = continuation(candidate,runtime_case,registration['sources'],action)
                core.seal(directory/('branch_%02d_%s.json'%(index,action)),branch)
                branches[action] = branch
            baseline_action = row['actions'][case['turn']-1][fixture['seat']]
            explicit = branches[baseline_action]
            if (explicit['scores'] != baseline['scores'] or explicit['actions'] != baseline['actions']
                    or explicit['pairwise_points'] != baseline['pairwise_points']):
                raise ValueError('Explicit baseline-action intervention changed full baseline')
            best = max(branch['pairwise_points'] for branch in branches.values())
            outcome = dict(case=case,baseline_action=baseline_action,recommended_action=chosen,
                baseline=baseline,root_counterfactuals=branches,
                teacher_delta_pairwise=branches[chosen]['pairwise_points']-baseline['pairwise_points'],
                hindsight_best_one_step_pairwise=best,
                hindsight_best_actions=[action for action in legal if branches[action]['pairwise_points'] == best],
                hindsight_opportunity_pairwise=best-baseline['pairwise_points'])
            core.seal(directory/('case_%02d.json'%index),outcome)
            completed.append(outcome)
            print(json.dumps(dict(completed_cases=len(completed),planned=16,primary_games=0)),flush=True)
        summary = dict(format=FORMAT,registration_sha256=sha((directory/'registration.json').read_bytes()),
            cases=completed,statistics=statistics(completed,protocol),primary_games=0,
            completed_per_game_bmcts_audits=0,promoted=False,
            limitation='Offline one-step hybrid causal usefulness on selected consumed TRAIN positions, realized responding rival instances and finite model/search; no fresh/universal strength, deployment timing, optimum or promotion claim.')
        _validated(directory)
        core.seal(directory/'results.json',summary)
        return summary
    except BaseException as error:
        core.seal(directory/'error.json',dict(format=FORMAT,active=active,completed_cases=len(completed),
            exception_type=type(error).__name__,message=str(error),primary_games=0,
            partial_branch=getattr(error,'branch_evidence',None),
            completed_per_game_bmcts_audits=0,promoted=False,
            status='failed_whole_experiment_preserve_all_partial_evidence_no_case_replacement'))
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command',required=True)
    prep = commands.add_parser('prepare')
    prep.add_argument('--stage',type=Path,default=STAGE)
    prep.add_argument('--output',type=Path,required=True)
    run = commands.add_parser('execute')
    run.add_argument('--directory',type=Path,required=True)
    args = parser.parse_args()
    if args.command == 'prepare':
        result = prepare(args.stage,args.output)
        print(json.dumps(dict(preregistered_cases=len(result['selected']),primary_games=0)))
    else:
        result = execute(args.directory)
        print(json.dumps(result['statistics']))


if __name__ == '__main__':
    main()
