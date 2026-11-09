"""Prospective balanced ten-hour cohorts; no game execution or admission."""
import copy
import hashlib
import json
from pathlib import Path
import random
from functools import lru_cache

from evolution.genomes import GenomeSpace
from primary_campaign import core
from primary_local import recipe
from primary_migration.contract import validate_catalog_bytes

ROOT=Path(__file__).resolve().parents[1]
FORMAT='zone-rush-deadline-balanced-campaign/1'
CATALOG=ROOT/'.cache/primary/campaign_v1_20261109/catalog.json'
CATALOG_SHA256=recipe.CATALOG_SHA256
TRAIN_MAPS=16
FIELDS=tuple(core.FIELDS)
SEED=20261109014339
REFERENCES=(recipe.E8,recipe.BLOCKER,recipe.FEINT)
LEARNED_DISTINCT='8d988cfc38dc1de0d5a80bfd468bd2b091c4569609bb503e6e1c70c6515bbb14'


def canonical(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode('utf8')


def sha(body): return hashlib.sha256(body).hexdigest()


def seed(domain,*coordinates):
    return int.from_bytes(hashlib.sha256(canonical([FORMAT,SEED,domain,*coordinates])).digest()[:16],'big')


def catalog():
    body=CATALOG.read_bytes()
    validate_catalog_bytes(body,CATALOG_SHA256)
    return json.loads(body)


def source_entry(path):
    path=Path(path).resolve()
    return dict(path=str(path),sha256=sha(path.read_bytes()))


def original_sources():
    return {name:source_entry(ROOT/path) for name,path in {
        'planner':'bot.py','research':'tester_bots/research_alternative.py',
        'racer':'tester_bots/racer.py','blocker':'tester_bots/blocker.py'}.items()}


def classify(body):
    try:
        result=recipe.classify_source(body)
    except ValueError:
        from deadline_strategy.space import PublicMemoryTemplateSpace
        from deadline_strategy.goal_space import PersistentGoalTemplateSpace
        for space in (PublicMemoryTemplateSpace(),PersistentGoalTemplateSpace()):
            try:
                genes=space.inspect_export(body)
                break
            except ValueError: pass
        else: raise ValueError('Unknown exact reviewed standalone source template')
        result=dict(source_sha256=sha(body),family=space.family,genes=genes,
            genotype_sha256=sha(canonical([space.family,[(k,float(v) if v else 0.0) for k,v in sorted(genes.items())]])))
    result['strategy_family']='original-blocker' if result['family'] in ('public-memory-blocker','persistent-goal-public-memory-blocker') else result['family']
    return result


def space_for(family):
    if family=='e8-config': return GenomeSpace((ROOT/'bot.py').read_bytes())
    if family=='public-memory-blocker':
        from deadline_strategy.space import PublicMemoryTemplateSpace
        return PublicMemoryTemplateSpace()
    if family=='persistent-goal-public-memory-blocker':
        from deadline_strategy.goal_space import PersistentGoalTemplateSpace
        return PersistentGoalTemplateSpace()
    from evolution_templates.space import TemplateSpace
    return TemplateSpace(family)


def child(parent,generation,family,attempt=0):
    info=classify(parent); space=space_for(info['family'])
    if family!=info['strategy_family']:
        raise ValueError('Declared child strategy family differs from its exact parent template')
    genes=space.mutate(info['genes'],seed('numeric-child',generation,family,attempt),
        scale=.08 if info['family']=='e8-config' else .06)
    return space.export(genes)


def initial_population():
    defense=(ROOT/'.cache/confirmation/architectures_v2_001/defense_50d.py').read_bytes()
    bodies=[(ROOT/'bot.py').read_bytes(),defense,(ROOT/'tester_bots/blocker.py').read_bytes(),
        (ROOT/'confirmation_campaign/evidence/architectures_v2/feint_original.py').read_bytes(),
        (ROOT/'strategy_candidates/blocker_public_memory.py').read_bytes()]
    # Exact registered source identity is checked below. Each executed cohort
    # separately archives all candidate bytes, including this known control.
    if [sha(body) for body in bodies[:4]]!=[recipe.E8,recipe.DEFENSE,recipe.BLOCKER,recipe.FEINT]:
        raise ValueError('Exact four original architecture controls required')
    learned=(ROOT/'.cache/primary/campaign_v1_20261109/train_004/offspring_07.py').read_bytes()
    if sha(learned)!=LEARNED_DISTINCT:
        raise ValueError('Exact retained learned stage4 genotype changed')
    result=bodies+[learned]+[child(bodies[index],0,family) for index,family in
        ((2,'original-blocker'),(3,'original-feint'))]
    validate_population(result,8)
    return result


def next_population(previous_bodies,ranking,generation):
    """References + two complete-generation nonreference elites + three children."""
    if type(generation) is not int or generation<1 or len(previous_bodies)!=8:
        raise ValueError('A complete previous eight-policy TRAIN generation is required')
    indexed={sha(body):body for body in previous_bodies}
    if len(indexed)!=8 or len(ranking)!=8 or {row['sha256'] for row in ranking}!=set(indexed):
        raise ValueError('Ranking must cover exactly the previous complete population')
    result=[(ROOT/path).read_bytes() for path in ('bot.py','tester_bots/blocker.py',
        'confirmation_campaign/evidence/architectures_v2/feint_original.py')]
    if generation==1:
        # Prospective structural experiment: keep its exact f5 control in the
        # same generation. This is fixed before any initial TRAIN outcome.
        f5=(ROOT/'strategy_candidates/blocker_public_memory.py').read_bytes()
        result.append(f5)
        result += [indexed[row['sha256']] for row in ranking
                   if row['sha256'] not in (*REFERENCES,sha(f5))][:1]
    else:
        result += [indexed[row['sha256']] for row in ranking if row['sha256'] not in REFERENCES][:2]
    used={sha(body) for body in result}
    genotypes={classify(body)['genotype_sha256'] for body in result}
    for family in ('e8-config','original-blocker','original-feint'):
        if generation==1 and family=='original-blocker':
            from deadline_strategy.goal_space import PersistentGoalTemplateSpace
            space=PersistentGoalTemplateSpace();body=space.export(space.defaults)
            info=classify(body)
            if info['source_sha256'] in used or info['genotype_sha256'] in genotypes:
                raise ValueError('Prospective persistent-goal comparison duplicated an existing source')
            result.append(body);used.add(info['source_sha256']);genotypes.add(info['genotype_sha256']);continue
        parents=[indexed[row['sha256']] for row in ranking
                 if classify(indexed[row['sha256']])['strategy_family']==family]
        if not parents: raise ValueError('Missing source-family parent')
        for attempt in range(64):
            body=child(parents[0],generation,family,attempt); info=classify(body)
            if info['source_sha256'] not in used and info['genotype_sha256'] not in genotypes:
                result.append(body); used.add(info['source_sha256']); genotypes.add(info['genotype_sha256']); break
        else: raise ValueError('Prospective mutation deduplication exhausted')
    validate_population(result,8)
    return result


def validate_population(bodies,count):
    if type(bodies) not in (list,tuple) or len(bodies)!=count or count not in (2,8):
        raise ValueError('Exact registered cohort policy count required')
    metadata=[classify(body) for body in bodies]
    if len({row['source_sha256'] for row in metadata})!=count or len({row['genotype_sha256'] for row in metadata})!=count:
        raise ValueError('Duplicate candidate bytes or genotype')
    return metadata


@lru_cache(maxsize=1)
def _rival_spaces():
    return (GenomeSpace((ROOT/'bot.py').read_bytes()),
            GenomeSpace((ROOT/'tester_bots/research_alternative.py').read_bytes()).genes)


def _rivals(phase,generation,map_index,field_index,seat,token,slot):
    # Training streams are injective across all arms. Heldout streams share
    # actual rival parameters/RNG across arms, but never share live instances.
    paired_slot=slot if phase=='train' else 0
    coordinate=[phase,generation,map_index,field_index,seat,token,paired_slot]
    rng=random.Random(seed('rival-family',*coordinate))
    families=list(core.FIELDS[FIELDS[field_index]]); rng.shuffle(families)
    e8,research=_rival_spaces()
    # An injective namespace above all old 65-bit rival seeds, below 2**128.
    phase_index={'train':0,'development':1,'final':2}[phase]
    ordinal=(((((phase_index*10000+map_index)*4+field_index)*4+seat)*4+token-1)*8+paired_slot)*4
    answer=[]
    for rival_seat in range(4):
        if rival_seat==seat: continue
        family=families.pop(); actual_seed=(1<<96)+(SEED<<40)+ordinal+rival_seat
        rng=random.Random(seed('rival-parameters',*coordinate,rival_seat))
        spec=dict(seat=rival_seat,family=family,seed=actual_seed,
                  epsilon=rng.uniform(.01,.45),commitment=rng.uniform(.2,.95))
        if family in ('planner','research'):
            spec['genes']=e8.mutate(research if family=='research' else e8.genes,
                seed('rival-genes',*coordinate,rival_seat),scale=.16,grouped=True)
        spec['id']=sha(canonical(['deadline-rival-instance/1',*coordinate,slot,rival_seat,spec]))
        answer.append(spec)
    return answer


def cohort(phase,generation,boards,candidates,guards):
    if phase not in ('train','development','final') or type(generation) is not int or generation<0:
        raise ValueError('Explicit valid phase and generation required')
    if phase!='train' and generation!=0:
        raise ValueError('Only one prospective generation for each heldout phase')
    count=2 if phase=='final' else 8
    if len(candidates)!=count or len({c['sha256'] for c in candidates})!=count:
        raise ValueError('Exact distinct candidate entries required')
    bodies=[]
    for entry in candidates:
        if type(entry) is not dict or set(entry)!={'path','sha256'} or type(entry['path']) is not str:
            raise ValueError('Exact source path and digest required')
        body=Path(entry['path']).read_bytes()
        if sha(body)!=entry['sha256']: raise ValueError('Candidate source hash mismatch')
        bodies.append(body)
    validate_population(bodies,count)
    expected_phase='train' if phase=='train' else phase
    if not boards or len({b['rotation_orbit'] for b in boards})!=len(boards):
        raise ValueError('Distinct reserved map orbits required')
    if any(b['phase']!=expected_phase or (phase=='train' and b['map_index']<500) for b in boards):
        raise ValueError('Consumed or foreign-phase map requested')
    pinned=catalog()
    if any(type(b.get('map_index')) is not int or b['map_index'] not in range(len(pinned))
           or canonical(b)!=canonical(pinned[b['map_index']]) for b in boards):
        raise ValueError('Map is not the exact reserved pinned catalog record')
    if phase=='train' and (len(boards)!=TRAIN_MAPS or [b['map_index'] for b in boards]!=list(range(500+generation*16,516+generation*16))):
        raise ValueError('Only the next prospective complete TRAIN generation is allowed')
    fixtures=[]
    for board in boards:
        for fi,field in enumerate(FIELDS):
            for seat in range(4):
                for token in range(1,5):
                    for slot,candidate in enumerate(candidates):
                        opponents=_rivals(phase,generation,board['map_index'],fi,seat,token,slot)
                        f=dict(map_id=board['id'],map_index=board['map_index'],base=list(board['base']),
                            map_family=board['family'],seat=seat,token=token,field=field,
                            candidate_slot=slot,candidate=candidate['sha256'],opponents=opponents,
                            phase=phase,generation=generation)
                        f['focal_actor_id']=sha(canonical(['deadline-focal-instance/1',f]))
                        f['id']=sha(canonical(f)); fixtures.append(f)
    if len({f['id'] for f in fixtures})!=len(fixtures): raise ValueError('Fixture identity collision')
    rival_ids=[s['id'] for f in fixtures for s in f['opponents']]
    if len(set(rival_ids))!=len(rival_ids): raise ValueError('Rival instance identity collision')
    if phase=='train':
        seeds=[s['seed'] for f in fixtures for s in f['opponents']]
        if len(set(seeds))!=len(seeds): raise ValueError('TRAIN rival seed reused')
    return dict(format=FORMAT,phase=phase,generation=generation,seed=SEED,rules={'catch_requires_stay':True},
        guards=copy.deepcopy(guards),sources=original_sources(),candidates=copy.deepcopy(candidates),fixtures=fixtures,
        protocol=dict(maps=len(boards),candidates=count,fields=list(FIELDS),seat_token_crosses=16,
            complete_games=len(boards)*count*64,opponent_instances=3*len(fixtures),
            matched_rival_streams=phase!='train',focal_rng='Original exact public-seat initialization; fresh namespace each game.',
            primary_campaign_credit=0,bmcts_credit=0,promoted=False))
