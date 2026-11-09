"""Preregister a fresh two-policy confirmation without executing its games."""
import argparse
from collections import Counter
from pathlib import Path

from evolution import maps, runner
from evolution.genomes import GenomeSpace
from primary_campaign import core


CHALLENGER = '50d82d7ac58162e9cf651136afcedac5586db9a060f153854b00875f13efef37'
FORMAT = 'zone-rush-extra-paired-confirmation/1'


def make(campaign, output, seed=202611091739, map_count=128):
    campaign, output = Path(campaign).resolve(), Path(output).resolve()
    if type(seed) is not int or type(map_count) is not int or map_count < 4:
        raise ValueError('Explicit integer seed and at least four maps are required')
    if output.exists():
        raise FileExistsError('Preserve preregistered confirmation evidence')
    manifest, catalog = core.load_catalog(campaign)
    # Reproduce provenance before using any training-selected candidate.
    approvals = [core.validated_audit(campaign/('train_%03d'%index)) for index in (2,3)]
    summaries = [core.read_sealed(campaign/('train_%03d'%index)/'summary.json') for index in (2,3)]
    if any(summary['candidates'][0]['sha256'] != CHALLENGER for summary in summaries):
        raise ValueError('Preregistered challenger does not match its audited discovery evidence')
    registration = core.read_sealed(campaign/'train_002/registration.json')
    original = next(candidate for candidate in registration['candidates'] if candidate['sha256'] == CHALLENGER)
    space, research = core.sources_space()
    body = Path(original['path']).read_bytes()
    if body != space.export(original['genes']) or core.digest(body) != CHALLENGER:
        raise ValueError('Challenger source/genome changed')
    excluded = core.historical_map_ids() | {board['rotation_orbit'] for board in catalog}
    excluded_fingerprint = core.digest(core.canonical(sorted(excluded)))
    boards, seen = [], set(excluded)
    for index in range(map_count):
        for retry in range(10000):
            map_seed = core.seed_for(seed, 'extra-paired-confirmation', index, retry)
            board = maps.generate(1, map_seed)[0]
            orbit = core.rotation_orbit(board['base'])
            if orbit not in seen:
                break
        else:
            raise ValueError('Could not create a fresh legal confirmation map')
        seen.add(orbit)
        boards.append(dict(board, map_index=index, seed=map_seed, retry=retry, rotation_orbit=orbit))
    output.mkdir(parents=True, exist_ok=False)
    candidates = []
    for name, genes in (('incumbent',space.genes),('challenger_50d',original['genes'])):
        data = space.export(genes)
        path = output/(name+'.py')
        core.atomic(path,data)
        candidates.append(dict(name=name,genes=genes,path=str(path),sha256=core.digest(data)))
    protocol = dict(format=FORMAT,seed=seed,map_count=map_count,fields=list(core.FIELDS),
                    candidates=[candidate['sha256'] for candidate in candidates],
                    incumbent=core.INCUMBENT,challenger=CHALLENGER,
                    primary_catalog_sha256=manifest['catalog_sha256'],excluded_orbits_sha256=excluded_fingerprint,
                    design='Every map crosses all four fields, four focal seats and four starting tokens; two fresh actor instances use matched rival policy parameters.',
                    outcome='Equal map/field/seat/token mean of paired official pairwise-point differences.',
                    inference='99% descriptive map-cluster bootstrap; independent confirmation, not a universal or familywise guarantee.',
                    proposal_gate='Overall99%lower bound >0 and each field95%lower bound >-0.03; independent review and deployment checks still required.',
                    primary_games_accepted=0,bmcts_audits=0,promoted=False)
    control_id = core.digest(core.canonical(protocol))
    context = dict(campaign_id=control_id)
    fixtures = []
    for board in boards:
        for field_index, field in enumerate(core.FIELDS):
            for seat in range(4):
                for token in range(1,5):
                    episode = field_index*16+seat*4+token-1
                    specs = core.expected_opponents(context,board,episode,seat,field,space,research)
                    base = dict(map_id=board['id'],map_index=board['map_index'],map_family=board['family'],
                                base=board['base'],seat=seat,token=token,episode=episode,field=field)
                    pair_id = core.digest(core.canonical(dict(base,opponent_parameters=specs)))
                    for candidate in candidates:
                        opponents = []
                        for spec in specs:
                            # Matched parameters, separate per-match controller identities.
                            instance = dict(spec,pair_parameter_id=spec['id'])
                            instance['id'] = core.digest(core.canonical([spec['id'],candidate['sha256'],'fresh-instance']))
                            opponents.append(instance)
                        fixture = dict(base,pair_id=pair_id,candidate=candidate['sha256'],opponents=opponents)
                        fixture['id'] = core.digest(core.canonical(fixture))
                        fixtures.append(fixture)
    guards = dict(manifest['guards'])
    guards[str(Path(__file__).resolve())] = core.digest(Path(__file__).read_bytes())
    result = dict(format=FORMAT,role='extra_control_assignment',phase='confirmation',generation=0,
                  parent_campaign=str(campaign),
                  campaign_id=control_id,primary_campaign_id=manifest['campaign_id'],
                  rules={'catch_requires_stay':True},protocol=protocol,candidates=candidates,
                  sources=manifest['sources'],guards=guards,fixtures=fixtures,maps=boards,
                  counting='Extra complete-game paired controls. Zero primary games and zero full BMCTS audits.',
                  source_discovery_audits=[dict(generation=a['generation'],games_sha256=a['games_sha256'],
                                               registration_sha256=a['registration_sha256']) for a in approvals],
                  primary_games_accepted=0,bmcts_audits=0,promotion_allowed=False)
    validate(result,excluded)
    core.seal(output/'registration.json',result)
    return result


def validate(registration,excluded=()):
    if registration['format'] != FORMAT or registration['role'] != 'extra_control_assignment':
        raise ValueError('Wrong confirmation scope')
    if registration['primary_games_accepted'] != 0 or registration['promotion_allowed'] is not False:
        raise ValueError('Confirmation may not grant primary credit or automatic promotion')
    core.check_guards(registration['guards'])
    parent, catalog = core.load_catalog(Path(registration['parent_campaign']))
    required_guards = dict(parent['guards'])
    required_guards[str(Path(__file__).resolve())] = core.digest(Path(__file__).read_bytes())
    if (registration['guards'] != required_guards or registration['sources'] != parent['sources']
            or registration['rules'] != {'catch_requires_stay':True}
            or registration['primary_campaign_id'] != parent['campaign_id']
            or registration['protocol']['primary_catalog_sha256'] != parent['catalog_sha256']
            or registration['campaign_id'] != core.digest(core.canonical(registration['protocol']))):
        raise ValueError('Confirmation source protocol changed')
    excluded = set(excluded) | {board['rotation_orbit'] for board in catalog}
    candidates = {candidate['sha256']:candidate for candidate in registration['candidates']}
    if set(candidates) != {core.INCUMBENT,CHALLENGER}:
        raise ValueError('Unexpected comparison policies')
    space = GenomeSpace((core.ROOT/'bot.py').read_bytes())
    for identity,candidate in candidates.items():
        body = Path(candidate['path']).read_bytes()
        if body != space.export(candidate['genes']) or core.digest(body) != identity:
            raise ValueError('Confirmation candidate changed')
    orbits,task_ids,rivals,pairs,cells = set(),set(),set(),{},Counter()
    boards = {}
    for index, board in enumerate(registration['maps']):
        orbit = core.rotation_orbit(board['base'])
        if not maps.valid(board['base']) or orbit in orbits or orbit in excluded or orbit != board['rotation_orbit']:
            raise ValueError('Illegal, duplicate or leaked map')
        reproduced = maps.generate(1,board['seed'])[0]
        if (reproduced['base'] != board['base'] or reproduced['id'] != board['id']
                or reproduced['family'] != board['family'] or board['map_index'] != index
                or type(board['retry']) is not int or not 0 <= board['retry'] < 10000
                or board['seed'] != core.seed_for(registration['protocol']['seed'],'extra-paired-confirmation',index,board['retry'])):
            raise ValueError('Map does not reproduce')
        orbits.add(orbit)
        boards[index] = board
    if len(boards) != registration['protocol']['map_count']:
        raise ValueError('Map count differs from protocol')
    _, research = core.sources_space()
    for fixture in registration['fixtures']:
        board = boards.get(fixture['map_index'])
        if (board is None or type(fixture['seat']) is not int or fixture['seat'] not in range(4)
                or type(fixture['token']) is not int or fixture['token'] not in range(1,5)
                or fixture['field'] not in core.FIELDS or fixture['candidate'] not in candidates):
            raise ValueError('Foreign confirmation conditions')
        episode = list(core.FIELDS).index(fixture['field'])*16+fixture['seat']*4+fixture['token']-1
        common = dict(map_id=board['id'],map_index=board['map_index'],map_family=board['family'],
                      base=board['base'],seat=fixture['seat'],token=fixture['token'],episode=episode,field=fixture['field'])
        specs = core.expected_opponents({'campaign_id':registration['campaign_id']},board,episode,
                                        fixture['seat'],fixture['field'],space,research)
        pair_id = core.digest(core.canonical(dict(common,opponent_parameters=specs)))
        expected_opponents = []
        for spec in specs:
            instance = dict(spec,pair_parameter_id=spec['id'])
            instance['id'] = core.digest(core.canonical([spec['id'],fixture['candidate'],'fresh-instance']))
            expected_opponents.append(instance)
        expected = dict(common,pair_id=pair_id,candidate=fixture['candidate'],opponents=expected_opponents)
        expected['id'] = core.digest(core.canonical(expected))
        if fixture != expected:
            raise ValueError('Confirmation map/field/rival recipe changed')
        if fixture['id'] in task_ids or fixture['id'] != core.digest(core.canonical({k:v for k,v in fixture.items() if k!='id'})):
            raise ValueError('Duplicate/changed task')
        task_ids.add(fixture['id'])
        for spec in fixture['opponents']:
            if spec['id'] in rivals:
                raise ValueError('Controller instance reused')
            rivals.add(spec['id'])
        pairs.setdefault(fixture['pair_id'],[]).append(fixture)
        cells[fixture['candidate'],fixture['field'],fixture['seat'],fixture['token']] += 1
    for pair in pairs.values():
        if len(pair)!=2 or {f['candidate'] for f in pair}!=set(candidates):
            raise ValueError('Incomplete paired task')
        left,right = pair
        for key in ('map_id','base','seat','token','field'):
            if left[key] != right[key]:
                raise ValueError('Paired conditions differ')
        a=[{k:v for k,v in spec.items() if k!='id'} for spec in left['opponents']]
        b=[{k:v for k,v in spec.items() if k!='id'} for spec in right['opponents']]
        if a!=b:
            raise ValueError('Paired rival parameters differ')
    expected = len(registration['maps'])*4*16*2
    if len(task_ids)!=expected or len(cells)!=2*64 or set(cells.values())!={len(registration['maps'])}:
        raise ValueError('Incomplete balanced confirmation schedule')
    return dict(games=expected,paired_conditions=len(pairs),maps=len(orbits),unique_rival_instances=len(rivals),primary_credit=0)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--campaign',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    registration=make(args.campaign,args.output)
    print(validate(registration))


if __name__=='__main__':
    main()
