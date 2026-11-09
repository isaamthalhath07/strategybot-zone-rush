"""Measure search recommendations against responding real rival continuations.

This is hindsight research, not a deployable hybrid or fresh strength evidence.
The coach receives public prefixes only. Referee/controller truth stays in the
observer, which regenerates rival actions after every counterfactual deviation.
"""
import argparse
import copy
from pathlib import Path
import time

from evolution import oversight, runner
from primary_campaign import core
from search_coach.belief import PublicObservation
from tests import reference_engine as engine
from tree_coach import mcts


ROOT = core.ROOT
FIELDS = tuple(core.FIELDS)


def public(view):
    return PublicObservation.from_view(view).serializable()


def choose_cases(stage):
    registration = core.read_sealed(stage/'registration.json')
    core.check_guards(registration['guards'])
    fixtures = {fixture['id']: fixture for fixture in registration['fixtures']}
    grouped = {field: [] for field in FIELDS}
    with (stage/'games.jsonl').open('rb') as handle:
        for line in handle:
            row = oversight.strict_loads(line)
            if row['candidate'] == core.INCUMBENT:
                key = core.digest(core.canonical(['coaching-usefulness-v1', row['fixture']]))
                grouped[row['field']].append((key, row))
    for rows in grouped.values():
        rows.sort(key=lambda item: item[0])
    used_maps, output = set(), []
    for turn in (34, 60):
        for field in FIELDS:
            for _, row in grouped[field]:
                fixture = fixtures[row['fixture']]
                if fixture['map_id'] not in used_maps:
                    output.append(dict(turn=turn, fixture=fixture, row=row))
                    used_maps.add(fixture['map_id'])
                    break
            else:
                raise ValueError('Insufficient distinct maps for preregistered field coverage')
    return registration, output


def actor_actions(game, actors, namespaces):
    result = []
    for seat, view in enumerate(game.views()):
        supplied = copy.deepcopy(view)
        before = oversight.signature(supplied)
        started = time.perf_counter()
        action = actors[seat](supplied)
        duration = time.perf_counter()-started
        oversight.check(oversight.signature(supplied) == before, 'Actor mutated its public input')
        oversight.check(type(action) is str and action in game.legal(seat), 'Illegal actor decision')
        oversight.check(duration <= (2 if game.turn == 1 else .2), 'Actor callback missed its deadline')
        namespace = namespaces[seat]
        if namespace is not None:
            oversight.check(not namespace.get('_input_failures', 0) and not namespace.get('_policy_failures', 0), 'Actor fallback')
            memory = namespace.get('_history', {}).get(seat+1, {})
            if 'cooldown_possible' in memory:
                oversight.check(not memory.get('inference_failures', 0), 'Inference fallback')
                oversight.check(memory['progress'] == game.prog[seat] and memory['scores'][1:] == game.score,
                                'Incorrect public score/progress memory')
                oversight.check(all(game.cd[i] in memory['cooldown_possible'][i+1] for i in range(4)),
                                'Public inference lost a feasible cooldown')
        result.append(action)
    return result


def prefix(candidate, fixture, sources, row, turn):
    actors, namespaces = oversight.make_actors(candidate, fixture, sources)
    game = engine.Game(base=fixture['base'], start_token=fixture['token'], rules={'catch_requires_stay': True})
    shadow = oversight.referee.Referee(fixture['base'], start_token=fixture['token'], rules={'catch_requires_stay': True})
    focal = fixture['seat']
    opening, transitions = public(game.views()[focal]), []
    for index in range(turn-1):
        joint = actor_actions(game, actors, namespaces)
        oversight.check(joint == row['actions'][index], 'Recorded prefix does not regenerate')
        game.step(joint)
        shadow.step(joint)
        oversight.state_equal(game, shadow)
        transitions.append(dict(own_action=joint[focal], observation=public(game.views()[focal])))
    return game, shadow, actors, namespaces, opening, transitions


def continuation(candidate, case, sources, requested):
    fixture, row, turn = case['fixture'], case['row'], case['turn']
    game, shadow, actors, namespaces, _, _ = prefix(candidate, fixture, sources, row, turn)
    focal, chosen = fixture['seat'], []
    while not game.over():
        joint = actor_actions(game, actors, namespaces)
        if game.turn == turn and requested is not None:
            oversight.check(requested in game.legal(focal), 'Illegal intervention')
            joint[focal] = requested
            # The hybrid observer must remember its accepted own action.
            # Planner intent updates remain intact; this is the declared
            # diagnostic intervention policy, not an unchanged bot run.
            namespaces[focal]['_history'][focal+1]['last'] = requested
        if requested is None:
            oversight.check(joint == row['actions'][game.turn-1], 'Baseline future does not regenerate')
        chosen.append(joint)
        game.step(joint)
        shadow.step(joint)
        oversight.state_equal(game, shadow)
    if requested is None:
        oversight.check(game.score == row['scores'], 'Baseline score changed')
    return dict(scores=game.score, pairwise_numerator=mcts.pairwise_numerator(game.score, focal),
                suffix_turns=len(chosen), action_trace_sha256=core.digest(core.canonical(chosen)),
                callbacks_regenerated=320, dual_referee_turns=80)


def run(stage, output):
    stage, output = Path(stage).resolve(), Path(output).resolve()
    if output.exists():
        raise FileExistsError('Preserve completed trial evidence')
    # This expensive independent admission is performed before case selection.
    approval = core.validated_audit(stage)
    registration, cases = choose_cases(stage)
    candidate = next(item for item in registration['candidates'] if item['sha256'] == core.INCUMBENT)
    paths = [Path(__file__), ROOT/'tree_coach/mcts.py', ROOT/'search_coach/belief.py', ROOT/'search_coach/beam.py']
    pins = {str(path): core.digest(path.read_bytes()) for path in paths}
    output.mkdir(parents=True, exist_ok=False)
    plan = dict(format='zone-rush-coach-usefulness/1', source_pins=pins,
                source_registration_sha256=core.digest((stage/'registration.json').read_bytes()),
                source_games_sha256=approval['games_sha256'], candidate_sha256=core.INCUMBENT,
                selection='Two fixed turns34/60 × four fields; lowest preregistered fixture hash on eight distinct maps; no outcome selection.',
                cases=[dict(fixture=item['fixture']['id'], turn=item['turn'], field=item['fixture']['field']) for item in cases],
                coach=dict(simulations=128, horizon=6, beam_width=6, support_cap=1024),
                primary_games=0, completed_per_game_bmcts_audits=0, promoted=False)
    core.seal(output/'registration.json', plan)
    results = []
    for index, case in enumerate(cases):
        fixture, row = case['fixture'], case['row']
        game, _, _, _, opening, transitions = prefix(candidate, fixture, registration['sources'], row, case['turn'])
        job = dict(schema=1, kind='public_history_tree_coach', job_id='usefulness-%02d'%index,
                   initial_observation=opening, transitions=transitions,
                   search=dict(plan['coach'], seed=2026110900+index))
        coach = mcts.recommend(job)
        core.seal(output/('public_input_%02d.json'%index), job)
        core.seal(output/('coach_%02d.json'%index), coach)
        baseline = continuation(candidate, case, registration['sources'], None)
        branches = {action: continuation(candidate, case, registration['sources'], action) for action in game.legal(fixture['seat'])}
        recommended = coach['recommended_action']
        baseline_action = row['actions'][case['turn']-1][fixture['seat']]
        oversight.check(branches[baseline_action]['scores'] == baseline['scores'], 'Explicit baseline action changed its continuation')
        outcome = dict(fixture=fixture['id'], field=fixture['field'], turn=case['turn'], baseline_action=baseline_action,
                       recommended_action=recommended, baseline=baseline, root_counterfactuals=branches,
                       recommendation_delta_pairwise=(branches[recommended]['pairwise_numerator']-baseline['pairwise_numerator'])/2,
                       hindsight_best_root=max(item['pairwise_numerator'] for item in branches.values())/2)
        core.seal(output/('case_%02d.json'%index), outcome)
        results.append(outcome)
        print('COACH usefulness %d/%d; full responding-controller continuations checked' % (index+1,len(cases)),flush=True)
    core.check_guards(pins)
    summary = dict(format=plan['format'], cases=len(results),
                   recommendations_changed=sum(item['recommended_action'] != item['baseline_action'] for item in results),
                   mean_delta_pairwise=sum(item['recommendation_delta_pairwise'] for item in results)/len(results),
                   wins=sum(item['recommendation_delta_pairwise']>0 for item in results),
                   losses=sum(item['recommendation_delta_pairwise']<0 for item in results),
                   results=results, primary_games=0, completed_per_game_bmcts_audits=0, promoted=False,
                   limitations=['Training-position hindsight experiment, not fresh-map strength evidence.',
                                'Actual rival identities/RNG exist only in evaluator; coach has public prefix only.',
                                'Each branch regenerates responding rivals; no recorded future tape after intervention.',
                                'Offline teacher time is not a deployment deadline claim.',
                                'One-step intervention synchronizes accepted-action memory; it is not the unchanged focal policy.'])
    core.seal(output/'summary.json', summary)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = run(args.stage, args.output)
    print({key:result[key] for key in ('cases','recommendations_changed','mean_delta_pairwise','wins','losses','primary_games')})


if __name__ == '__main__':
    main()
