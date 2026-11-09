"""Preregister and measure public transition forecasts on accepted TRAIN traces.

This replays existing transcripts, not new campaign matches. No controller,
actual rival seed/type or future action reaches an IntentFilter. Policy
probabilities are derived from the prior public explanations; the next public
observation filters their joint probability mass. The selected own action
conditions physics only. No reserved game/transcript/outcome is read or replayed;
catalog metadata is loaded solely to validate TRAIN partition assignment.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import random
import time

from evolution import oversight, runner
from opponent_prediction.intent_filter import IntentFilter, MODES
from primary_campaign import core
from search_coach.belief import PublicObservation
from tests import reference_engine as engine


ROOT = core.ROOT
FORMAT = 'public-intent-filter-pilot/1'
SNAPSHOT = ROOT/'primary_campaign/evidence/accepted_stages_000_004.json'
SNAPSHOT_SHA256 = 'c54517e04524718d7ef9f576c78403b56126e04354ce318795380b976b4daa36'


def sha(body):
    return hashlib.sha256(body).hexdigest()


def pins():
    paths = ['opponent_prediction/intent_filter.py','opponent_prediction/pilot.py',
             'search_coach/belief.py','tests/reference_engine.py','evolution/oversight.py',
             'simulator/vendor_harness/referee.py','evolution/maps.py','evolution/runner.py',
             'primary_campaign/core.py']
    return {relative:sha((ROOT/relative).read_bytes()) for relative in paths}


def select(grouped):
    for values in grouped.values():
        values.sort()
    used,selected = set(),[]
    for _ in range(4):
        for field in core.FIELDS:
            match = next((row for row in grouped[field] if row[3] not in used),None)
            if match is None:
                raise ValueError('Insufficient distinct admitted training maps')
            _,generation,fixture,map_id = match
            selected.append(dict(generation=generation,fixture=fixture,map_id=map_id,field=field))
            used.add(map_id)
    return selected


def _snapshot():
    body = SNAPSHOT.read_bytes()
    if sha(body) != SNAPSHOT_SHA256:
        raise ValueError('Published accepted-100k snapshot changed')
    snapshot = oversight.strict_loads(body)
    if (snapshot['primary_games_accepted'] != 100000 or snapshot['callbacks_regenerated'] != 32000000
            or [r['generation'] for r in snapshot['stages']] != list(range(5))
            or any(r['primary_games_accepted'] != 20000 or r['callbacks_regenerated'] != 6400000 for r in snapshot['stages'])
            or snapshot['bmcts_audits'] != 0 or snapshot['promoted'] is not False):
        raise ValueError('This pilot requires the exact five distinct accepted stages 0 through 4')
    return snapshot


def _facts(campaign, *, deep):
    """Admission metadata only. No actor calls or held-out games are executed.

    Preparation checks the complete task recipe once. Resume rebinds its exact
    published bytes and source guards, without reconstructing100k task recipes.
    """
    campaign = campaign.resolve()
    snapshot = _snapshot()
    manifest,catalog = core.load_catalog(campaign)
    grouped = {field:[] for field in core.FIELDS}
    stages = []
    for receipt in snapshot['stages']:
        index = receipt['generation']
        stage = campaign/('train_%03d'%index)
        for name in ('audit.json','audit.sha256','summary.json','summary.sha256'):
            body = (stage/name).read_bytes()
            if body != (SNAPSHOT.parent/stage.name/name).read_bytes() or sha(body) != receipt['exact_copy_files'][name]:
                raise ValueError('Published accepted-stage receipt changed')
        registration = core.read_sealed(stage/'registration.json')
        if deep:
            core.validate_registration(registration,manifest,catalog)
        core.check_guards(registration['guards'])
        if (registration['generation'] != index or registration['campaign_id'] != manifest['campaign_id']
                or registration['phase'] != 'train' or sha((stage/'registration.json').read_bytes()) != receipt['registration_sha256']):
            raise ValueError('Source directory/index/registration binding changed')
        audit = core.read_sealed(stage/'audit.json')
        if (audit['approved'] is not True or audit['all_actors_regenerated'] is not True
                or audit['generation'] != index or audit['callbacks_regenerated'] != 6400000
                or audit['primary_games_accepted'] != 20000 or audit['campaign_id'] != manifest['campaign_id']
                or audit['games_sha256'] != receipt['games_sha256']
                or audit['actor_audits_sha256'] != receipt['actor_audits_sha256']
                or audit['registration_sha256'] != receipt['registration_sha256']):
            raise ValueError('Source lacks the original full actor admission')
        for filename, fingerprint in (('games.jsonl',receipt['games_sha256']),
                                      ('actor_audits.jsonl',receipt['actor_audits_sha256'])):
            if sha((stage/filename).read_bytes()) != fingerprint:
                raise ValueError('Hash-bound source records changed')
        stages.append(dict(generation=index,registration_sha256=receipt['registration_sha256'],
                           games_sha256=receipt['games_sha256'],actor_audits_sha256=receipt['actor_audits_sha256']))
        for fixture in registration['fixtures']:
            if fixture['candidate'] == core.INCUMBENT:
                ranking = sha(core.canonical(['intent-filter-pilot-v1',fixture['id']]))
                grouped[fixture['field']].append((ranking,index,fixture['id'],fixture['map_id']))
    return dict(campaign_directory=str(campaign),campaign_id=manifest['campaign_id'],
                manifest_sha256=sha((campaign/'manifest.json').read_bytes()),catalog_sha256=sha((campaign/'catalog.json').read_bytes()),
                stages=stages,selected=select(grouped))


def _protocol(facts):
    # Rebuild every semantic field and every setting; a rehashed sidecar cannot
    # turn a descriptive TRAIN pilot into a confirmation or change its schedule.
    return dict(format=FORMAT,**facts,accepted_snapshot_sha256=SNAPSHOT_SHA256,sources=pins(),
        selection='Four rounds over registered fields; lowest hashed eligible incumbent task on a previously unused map; no outcome filter.',
        data_scope='Consumed primary TRAIN transcripts only; no new matches, policy confirmation or reserved development/final games or outcomes. Full catalog metadata is read only to validate TRAIN assignment.',
        modes=list(MODES),limits=dict(max_states=1024,max_particles=65536,max_joint_intents=200000),
        metric='Equal-field-weight mean of game mean negative natural-log probability of the next complete focal public observation, conditional on accepted own action; four distinct maps per field and79 observed transitions per game.',
        observation_steps=79,physical_replay_turns=80,
        final_view='No terminal turn81 observation is used for model inference; all80 physical turns are still verified.',
        primary_contrast='persistent minus mixture negative-log-loss; smaller is better.',
        all_contrasts=[['persistent','mixture'],['persistent','uniform'],['mixture','uniform']],
        bootstrap=dict(replicates=20000,seed=202611092150,unit='whole selected map/game, stratified within each registered field',
                       allocation='Resample four maps with replacement within each of four fields; preserve equal field weights.',
                       algorithm='stdlib Random(seed).randrange(4); replicate-major, core.FIELDS order, four draws per field; cases in registered selected-fixture order; same draws for all three contrasts.',
                       quantile_indices=[499,19499],scope='Unadjusted descriptive95% percentile intervals; no simultaneous, fresh-data or strength guarantee.'),
        failure_policy='Any unsupported history, inference budget exception, nonfinite loss or replay mismatch aborts the whole pilot. Never omit a case, change caps or fit models after seeing outcomes. Unchanged deterministic retries grant no new data or game credit.',
        exploratory=dict(turn_bins=[[1,20],[21,40],[41,60],[61,79]],
            public_opportunity='Prior-public Shield-opportunity proxy: any nonfrozen rival occupies land owned by a different player. Cooldown readiness and intended STAY are unknown.',
            forced_context='Prior public all-rivals-frozen yes/no.',
            reporting='Counts and pooled per-event NLL by mode only; no extra intervals, significance, tactical-plan or strength claims.'),
        model_claim='Posterior conditional on four fixed heuristic policies, not calibrated real identity or a counterfactual strength result.',
        primary_games=0,full_bmcts_audits=0,promotion=False)


def prepare(campaign, output):
    if output.exists():
        raise ValueError('A fresh preregistration directory is required')
    campaign = campaign.resolve()
    if output.resolve().is_relative_to(campaign):
        raise ValueError('Research output must be outside the immutable primary campaign')
    protocol = _protocol(_facts(campaign,deep=True))
    output.mkdir(parents=True)
    core.seal(output/'registration.json',protocol)
    return protocol


def _validated(directory):
    protocol = core.read_sealed(directory/'registration.json')
    expected = _protocol(_facts(Path(protocol['campaign_directory']),deep=False))
    if core.canonical(protocol) != core.canonical(expected):
        raise ValueError('Exact preregistered pilot protocol, source, claim or selected recipe changed')
    return protocol


def _field_groups(cases):
    groups = [[i for i,case in enumerate(cases) if case['case']['field'] == field] for field in core.FIELDS]
    if len(cases) != 16 or len({case['case']['map_id'] for case in cases}) != 16 or any(len(group) != 4 for group in groups):
        raise ValueError('Four distinct maps per field and sixteen distinct maps overall are required')
    return groups


def _public_context(public, turn):
    if type(turn) is not int or not 1 <= turn <= 79:
        raise ValueError('Exploratory public context covers only observed turns1 through79')
    rivals = [cell for cell in public.cells if cell[0] not in (0,public.bot_id)]
    lower,upper = ((1,20) if turn <= 20 else (21,40) if turn <= 40 else (41,60) if turn <= 60 else (61,79))
    return dict(turn=turn,turn_bin='turn_%02d_%02d'%(lower,upper),
                public_shield_opportunity_proxy=any(cell[1] not in (0,cell[0]) and not cell[4] for cell in rivals),
                all_rivals_frozen=all(cell[4] for cell in rivals))


def _exploratory(cases):
    groups = {name:{mode:[] for mode in MODES} for name in ('turn_01_20','turn_21_40','turn_41_60','turn_61_79',
              'public_intrusion_yes','public_intrusion_no','all_rivals_frozen_yes','all_rivals_frozen_no')}
    for case in cases:
        contexts = case['public_context']
        if len(contexts) != 79 or any(len(case['models'][mode]['trace']) != 79 for mode in MODES):
            raise ValueError('Exploratory slices cannot drop public transitions')
        for step,context in enumerate(contexts):
            if context['turn'] != step+1:
                raise ValueError('Exploratory slice order changed')
            names = [context['turn_bin'],'public_intrusion_'+('yes' if context['public_shield_opportunity_proxy'] else 'no'),
                     'all_rivals_frozen_'+('yes' if context['all_rivals_frozen'] else 'no')]
            for mode in MODES:
                nll = -case['models'][mode]['trace'][step]['log_predictive_probability']
                if not math.isfinite(nll):
                    raise ValueError('Nonfinite exploratory loss; abort rather than drop a transition')
                for name in names:
                    groups[name][mode].append(nll)
    return {name:dict(events=len(values[MODES[0]]),
             models={mode:dict(total_nll=math.fsum(v),mean_nll=math.fsum(v)/len(v) if v else None) for mode,v in values.items()})
             for name,values in groups.items()}


def _statistics(cases, protocol):
    # Source-generation execution order must never change seeded map draws.
    indexed = {case['case']['fixture']:case for case in cases}
    wanted = protocol['selected']
    if len(cases) != len(indexed) or set(indexed) != {case['fixture'] for case in wanted}:
        raise ValueError('Complete unique preregistered cases are required before statistics')
    ordered = [indexed[case['fixture']] for case in wanted]
    if any(core.canonical(result['case']) != core.canonical(case) for result,case in zip(ordered,wanted)):
        raise ValueError('A measured case differs from its preregistered source condition')
    groups = _field_groups(ordered)
    if any(set(case['models']) != set(MODES) or any(type(case['models'][mode]['mean_nll']) not in (int,float)
           or not math.isfinite(case['models'][mode]['mean_nll']) for mode in MODES) for case in ordered):
        raise ValueError('All fixed models require a finite loss for every selected case; never drop a failed model/case')
    rng = random.Random(protocol['bootstrap']['seed'])
    deltas = [[case['models'][a]['mean_nll']-case['models'][b]['mean_nll'] for case in ordered]
              for a,b in protocol['all_contrasts']]
    boot = [[] for _ in deltas]
    draws_sha = hashlib.sha256()
    for _ in range(protocol['bootstrap']['replicates']):
        draw = [group[rng.randrange(4)] for group in groups for _ in range(4)]
        draws_sha.update(bytes(draw))
        for result,values in zip(boot,deltas):
            result.append(math.fsum(values[index] for index in draw)/16)
    contrasts = []
    lo,hi = protocol['bootstrap']['quantile_indices']
    for pair,values,samples in zip(protocol['all_contrasts'],deltas,boot):
        samples.sort()
        contrasts.append(dict(first=pair[0],second=pair[1],mean_delta_nll=math.fsum(values)/16,
                              descriptive95_interval=[samples[lo],samples[hi]]))
    models = {mode:dict(mean_nll=math.fsum(case['models'][mode]['mean_nll'] for case in ordered)/16,
              fields={field:math.fsum(ordered[i]['models'][mode]['mean_nll'] for i in group)/4
                      for field,group in zip(core.FIELDS,groups)}) for mode in MODES}
    return ordered,models,contrasts,draws_sha.hexdigest()


def execute(directory):
    protocol = _validated(directory)
    if (directory/'results.json').exists():
        raise ValueError('Completed pilot is immutable; do not rerun consumed outcomes')
    campaign = Path(protocol['campaign_directory'])
    all_cases = []
    by_generation = {}
    for case in protocol['selected']:
        by_generation.setdefault(case['generation'],[]).append(case)
    for generation,cases in by_generation.items():
        stage = campaign/('train_%03d'%generation)
        receipt = next(row for row in protocol['stages'] if row['generation'] == generation)
        if sha((stage/'registration.json').read_bytes()) != receipt['registration_sha256']:
            raise ValueError('Source registration changed')
        registration = core.read_sealed(stage/'registration.json')
        core.check_guards(registration['guards'])
        candidates,fixtures = ({x['sha256']:x for x in registration['candidates']},
                              {x['id']:x for x in registration['fixtures']})
        wanted = {case['fixture'] for case in cases}
        body = (stage/'games.jsonl').read_bytes()
        if sha(body) != receipt['games_sha256']:
            raise ValueError('Source transcripts changed after preregistration')
        rows = {}
        for line in body.splitlines():
            row = oversight.strict_loads(line)
            if row['fixture'] in wanted:
                if row['fixture'] in rows:
                    raise ValueError('Duplicate selected transcript')
                rows[row['fixture']] = row
        if set(rows) != wanted:
            raise ValueError('Selected transcript missing')
        for case in cases:
            row,fixture = rows[case['fixture']],fixtures[case['fixture']]
            if fixture['map_id'] != case['map_id'] or fixture['field'] != case['field'] or fixture['candidate'] != core.INCUMBENT:
                raise ValueError('Preregistered source condition changed')
            runner.verify_row(row,candidates[row['candidate']],fixture)
            game = engine.Game(base=fixture['base'],start_token=fixture['token'],rules={'catch_requires_stay':True})
            shadow = oversight.referee.Referee(game.base,start_token=game.token,rules=game.rules)
            focal = fixture['seat']
            initial = PublicObservation.from_view(game.views()[focal]).serializable()
            filters = {mode:IntentFilter(initial,mode=mode,**protocol['limits']) for mode in MODES}
            traces = {mode:[] for mode in MODES}
            public_context = []
            started = time.perf_counter()
            for step,joint in enumerate(row['actions']):
                if step < protocol['observation_steps']:
                    public_context.append(_public_context(PublicObservation.from_view(game.views()[focal]),step+1))
                # No actual rival action is passed to a model. It receives the
                # accepted own action and only the public successor observation.
                game.step(joint)
                shadow.step(joint)
                oversight.state_equal(game,shadow)
                if step < protocol['observation_steps']:
                    post = PublicObservation.from_view(game.views()[focal]).serializable()
                    for mode,belief in filters.items():
                        traces[mode].append(belief.advance(joint[focal],post))
            if game.score != row['scores']:
                raise ValueError('Replayed score changed')
            output = dict(case=case,observation_steps=79,physical_turns=80,models={},public_context=public_context,
                          wall_s=time.perf_counter()-started)
            for mode,belief in filters.items():
                output['models'][mode] = dict(mean_nll=-belief.log_evidence/79,log_evidence=belief.log_evidence,
                    maximum_physical_states=max(t['physical_states'] for t in traces[mode]),
                    maximum_modeled_particles=max(t['modeled_particles'] for t in traces[mode]),
                    legal_joint_intents_tested=sum(t['legal_joint_intents_tested'] for t in traces[mode]),
                    compatible_alias_intents=sum(t['compatible_alias_intents'] for t in traces[mode]),
                    type_marginals=belief.type_marginals(),trace=traces[mode])
            all_cases.append(output)
            print(json.dumps(dict(completed_histories=len(all_cases),planned=16,field=case['field'],
                                 wall_s=output['wall_s'],primary_games=0)),flush=True)
    all_cases,models,contrasts,draws_sha = _statistics(all_cases,protocol)
    summary = dict(format=FORMAT,histories=16,public_prediction_steps=16*79,physical_turns_replayed=16*80,
        models=models,contrasts=contrasts,bootstrap=dict(protocol['bootstrap'],shared_draw_indices_sha256=draws_sha),
        exploratory=dict(definition=protocol['exploratory'],slices=_exploratory(all_cases)),
        registration_sha256=sha((directory/'registration.json').read_bytes()),primary_games=0,
        full_bmcts_audits=0,promotion=False,limitation=protocol['model_claim'],cases=all_cases)
    _validated(directory)
    core.seal(directory/'results.json',summary)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command',required=True)
    make = commands.add_parser('prepare')
    make.add_argument('--campaign',type=Path,required=True)
    make.add_argument('--output',type=Path,required=True)
    run = commands.add_parser('execute')
    run.add_argument('--directory',type=Path,required=True)
    args = parser.parse_args()
    if args.command == 'prepare':
        result = prepare(args.campaign,args.output)
        print(json.dumps(dict(selected=len(result['selected']),primary_games=0)),flush=True)
    else:
        result = execute(args.directory)
        print(json.dumps({k:v for k,v in result.items() if k != 'cases'}),flush=True)


if __name__ == '__main__':
    main()
