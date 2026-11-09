"""Pure TRAIN continuation and prospective in-memory population recipes.

Nothing here plays, prepares, writes, signs or admits a campaign. Evidence must
be authenticated by a separate reviewed caller adapter before this recipe is
used. Typed wrappers and declared counts are not cryptographic admission.
"""
import ast
import copy
from collections import Counter
from dataclasses import dataclass
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import random

from evolution.genomes import GenomeSpace
from evolution_templates.space import TemplateSpace
from primary_campaign import core
from primary_migration import contract

ROOT = Path(__file__).resolve().parents[1]
FORMAT = 'zone-rush-pure-primary-local-recipe/1'
CAMPAIGN_ID = '66269bc2443cdff375116b3e168f1e8db6f27cc4a758a8c00e84f949d4bcac10'
CATALOG_SHA256 = '311b51f5eef35402f88887bd18f54053fedf923cc17d3b8b13d6d1e2142f794f'
E8 = 'e8b3682d8b39d3fc4d22cdcd8927161290a90cd472d3ede4132ae716f8c6f8f5'
DEFENSE = '50d82d7ac58162e9cf651136afcedac5586db9a060f153854b00875f13efef37'
BLOCKER = '1bb70109a75e2880bfdf3ac9b6fd8e368b0f3d02b9a3e65de53cef0defa505e5'
FEINT = 'f95dc9fc22660331b1368a876d907f111fd3cb21aef6e3e34315b41e6af94e94'
STUDY_REGISTRATION_SHA256 = 'b5ffb74f5c8ad1c7a984a54d41d86efb26cb99ae2318a8b7d5a631d23ad24eb9'
FAMILIES = ('e8-config','original-blocker','original-feint')
FROZEN = {
    'bot.py':E8,'tester_bots/blocker.py':BLOCKER,
    'confirmation_campaign/evidence/architectures_v2/feint_original.py':FEINT,
    'tester_bots/research_alternative.py':'6f2ac1487cd0a66793db3f2fab01f621d9c945a4f71a78cc92d176ef1de321f4',
    'evolution/genomes.py':'a16800b4daed6f4b78190db9db755ba17447c179d601a5a481754478f1ad70f2',
    'primary_campaign/core.py':'6d0de2dae757a4db821bddbb6bad1978bd6f6ac4d612ac60946b2ff01412d6fa',
    'primary_migration/contract.py':'9ed340e989d849ceafef275f1d11d27c144b7ad757bc79f18e011ca54935c91e',
    'evolution_templates/space.py':'bce6dd1fa5950a8752182ce4c70e17ea10d74245a7fe650cc735b3483b2ae041',
}
OPERATORS = dict(rival_mutation=dict(scale=.16,grouped=True),
    e8_child_mutation=dict(scale=.08,grouped=False),template_child_mutation=dict(scale=.06,max_changes=3),
    maximum_dedup_attempts=64,crossover='Optional same-family top-two grouped crossover, always followed by mutation.')


def canonical(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode('utf8')


def sha(body):
    return hashlib.sha256(body).hexdigest()


def require(condition,message):
    if not condition:
        raise ValueError(message)


def _integer(value,low,high):
    return type(value) is int and low <= value <= high


def _hash(value):
    return type(value) is str and len(value)==64 and all(character in '0123456789abcdef' for character in value)


def source_pins():
    result = {}
    for name,expected in FROZEN.items():
        actual = sha((ROOT/name).read_bytes())
        require(actual==expected,'Frozen recipe/source-family dependency changed: '+name)
        result[name] = actual
    for name in ('primary_local/__init__.py','primary_local/recipe.py'):
        result[name] = sha((ROOT/name).read_bytes())
    return dict(sorted(result.items()))


def description():
    return dict(format=FORMAT,campaign_id=CAMPAIGN_ID,catalog_sha256=CATALOG_SHA256,
        train_stages=[5,79],maps_per_stage=100,episodes_per_map=200,population=8,operators=copy.deepcopy(OPERATORS),
        fixed_references=[E8,BLOCKER,FEINT],elite_rule='Highest previous-stage standardized64-cell fitness; skip all fixed-reference and already-retained identities.',
        source_sha256=source_pins(),certifies_executed_games=False,grants_admission=False,new_primary_credit=0,
        bmcts_audits=0,promoted=False,reserved_development_slots=200000,reserved_final_slots=200000)


def version_id():
    return sha(canonical(description()))


def domain_seed(version,domain,*coordinates):
    require(_hash(version) and type(domain) is str and domain,'Explicit version and domain required')
    return int.from_bytes(hashlib.sha256(canonical([FORMAT,version,domain,*coordinates])).digest()[:16],'big')


def seed_blob(seed):
    """Lossless9-byte global uniqueness key, including old64-bit seeds."""
    return contract.seed_key(seed)


def rival_seed_blob(seed):
    require(_integer(seed,1<<64,(1<<65)-1),'Prospective rival seed must retain all65 bits')
    return contract.seed_key(seed)


def _e8_space():
    body = (ROOT/'bot.py').read_bytes()
    require(sha(body)==E8,'Exact e8 export template changed')
    return GenomeSpace(body)


def _config(body):
    tree = ast.parse(body)
    nodes = [node for node in tree.body if isinstance(node,ast.Assign)
             and any(isinstance(target,ast.Name) and target.id=='CONFIG' for target in node.targets)]
    require(len(nodes)==1 and len(nodes[0].targets)==1,'One exact CONFIG assignment required')
    genes = ast.literal_eval(nodes[0].value)
    require(type(genes) is dict,'A numeric CONFIG dictionary required')
    return genes


def classify_source(body):
    """Exact canonical export equality, never AST-similarity/runtime approval."""
    require(type(body) is bytes and 0 < len(body) <= 256*1024,'Bounded exact standalone source bytes required')
    space = _e8_space()
    try:
        genes = _config(body)
        space.validate(genes)
        if space.export(genes)==body:
            family = 'e8-config'
        else:
            raise ValueError('Not canonical e8 export bytes')
    except (ValueError,TypeError,SyntaxError,KeyError,UnicodeError):
        family,genes = None,None
        for name in FAMILIES[1:]:
            try:
                genes = TemplateSpace(name).inspect_export(body)
                family = name
                break
            except (ValueError,TypeError,SyntaxError,KeyError,UnicodeError):
                pass
        require(family is not None,'Unknown or noncanonical source family; exact reviewed export required')
    genotype = sha(canonical([family,[(key,0.0 if value==0 else float(value)) for key,value in sorted(genes.items())]]))
    return dict(source_sha256=sha(body),family=family,genes=dict(genes),genotype_sha256=genotype,
        expected_focal_legacy_oracles_per_full_game=80 if family=='e8-config' else 0,
        required_actor_callbacks_per_game=320,required_referees=2,
        runtime_qualified=False,grants_admission=False,new_primary_credit=0)


def _references():
    return [(ROOT/'bot.py').read_bytes(),(ROOT/'tester_bots/blocker.py').read_bytes(),
            (ROOT/'confirmation_campaign/evidence/architectures_v2/feint_original.py').read_bytes()]


def _population(bodies):
    require(type(bodies) in (list,tuple) and len(bodies)==8,'Eight exact in-memory candidate sources required')
    metadata = [classify_source(body) for body in bodies]
    require(metadata[0]['source_sha256']==E8 and len({row['source_sha256'] for row in metadata})==8
        and len({row['genotype_sha256'] for row in metadata})==8,'Exact e8 control and eight distinct source/genotype candidates required')
    return metadata


def stage_recipe(catalog_bytes,stage_index,candidate_bodies):
    """Return metadata plus source bytes in memory; no stage/output is created."""
    guards = source_pins()
    require(_integer(stage_index,5,79),'Only TRAIN continuation stages5 through79 are allowed')
    require(type(catalog_bytes) is bytes and len(catalog_bytes)<=64*1024*1024,'Exact original catalog bytes required')
    contract.validate_catalog_bytes(catalog_bytes,CATALOG_SHA256)
    catalog = contract._strict_json(catalog_bytes)
    metadata = _population(candidate_bodies)
    require([row['source_sha256'] for row in metadata[:3]]==[E8,BLOCKER,FEINT],
            'Continuation slots0/1/2 must retain exact e8/Blocker/Feint references')
    version = version_id();space = _e8_space()
    research = GenomeSpace((ROOT/'tester_bots/research_alternative.py').read_bytes()).genes
    descriptors,fixtures = [],[]
    rival_keys,rival_ids,focal_ids = set(),set(),set()
    boards = catalog[stage_index*100:(stage_index+1)*100]
    require(len(boards)==100 and len({board['rotation_orbit'] for board in boards})==100
        and all(board['phase']=='train' and board['map_index']==stage_index*100+index for index,board in enumerate(boards)),
        'Exact distinct TRAIN maps for the fixed global stage required')
    for board in boards:
        for episode in range(200):
            descriptor = contract.slot_schedule(board['map_index'],episode)
            require(descriptor['phase']=='train' and descriptor['stage_index']==stage_index,'Reserved phase/schedule drift')
            descriptors.append(descriptor)
            families = list(core.FIELDS[descriptor['field']])
            random.Random(domain_seed(version,'rival-family',board['map_index'],episode)).shuffle(families)
            opponents = []
            for seat in range(4):
                if seat==descriptor['seat']:
                    continue
                family = families.pop()
                rng = random.Random(domain_seed(version,'rival-numeric',board['map_index'],episode,seat))
                seed = contract.rival_seed(board['map_index'],episode,seat)
                spec = dict(seat=seat,family=family,seed=seed,epsilon=rng.uniform(.01,.45),commitment=rng.uniform(.2,.95))
                if family in ('planner','research'):
                    spec['genes'] = space.mutate(research if family=='research' else space.genes,
                        domain_seed(version,'rival-genes',board['map_index'],episode,seat),scale=.16,grouped=True)
                spec['id'] = contract.rival_identity(version,board['map_index'],episode,seat,sha(canonical(spec)))
                key = rival_seed_blob(seed)
                require(key not in rival_keys and spec['id'] not in rival_ids,'Repeated planned rival seed/identity')
                rival_keys.add(key);rival_ids.add(spec['id']);opponents.append(spec)
            candidate = metadata[descriptor['candidate_slot']]['source_sha256']
            focal = sha(canonical(['primary-local-focal-instance/1',version,descriptor['canonical_slot'],candidate]))
            require(focal not in focal_ids,'Repeated focal instance identity')
            focal_ids.add(focal)
            fixture = dict(map_id=board['id'],map_index=board['map_index'],base=list(board['base']),
                map_family=board['family'],episode=episode,seat=descriptor['seat'],token=descriptor['token'],
                field=descriptor['field'],candidate_slot=descriptor['candidate_slot'],candidate=candidate,
                canonical_slot=descriptor['canonical_slot'],focal_actor_id=focal,opponents=opponents)
            fixture['id'] = sha(canonical(fixture));fixtures.append(fixture)
    balance = contract.validate_schedule(descriptors,stage_index*100,100,'train')
    pairs = Counter((row['candidate_slot'],row['seat'],row['token']) for row in descriptors)
    cells = Counter((row['candidate_slot'],row['seat'],row['token'],row['field']) for row in descriptors)
    counts = Counter(row['candidate_slot'] for row in descriptors)
    require(counts=={slot:2500 for slot in range(8)} and len(pairs)==128 and set(pairs.values())=={156,157}
        and len(cells)==512 and set(cells.values())=={39,40}
        and len(rival_keys)==len(rival_ids)==60000 and len(focal_ids)==20000,'Complete exact map/seat/token/field/rival balance required')
    balance.update(candidate_field_counts={str((slot,field)):sum(count for (s,_,_,f),count in cells.items() if s==slot and f==field)
                                          for slot in range(8) for field in core.FIELDS},
                   cell_min=39,cell_max=40,rival_instances=60000,focal_instances=20000)
    payload = dict(format=FORMAT,version_id=version,campaign_id=CAMPAIGN_ID,catalog_sha256=CATALOG_SHA256,
        phase='train',generation=stage_index,planned_games=20000,maps=100,episodes_per_map=200,
        candidates=metadata,fixtures=fixtures,balance=balance,source_sha256=guards,
        focal_rng='Original source public-seat initialization unchanged; fresh instance does not claim fresh focal reseeding.',
        rival_rng='Injective65-bit actual seed; independent family/numeric/genome domain seeds; nine-byte uniqueness keys.',
        requires_external_admission_bridge=True,certifies_executed_games=False,primary_games_accepted=0,bmcts_audits=0,promoted=False)
    require(source_pins()==guards,'Source changed while building pure stage recipe')
    return dict(payload=payload,recipe_sha256=sha(canonical(payload)),candidate_sources=tuple(candidate_bodies))


@dataclass(frozen=True)
class CellFitness:
    seat: int
    token: int
    field: str
    games: int
    pairwise_numerator_sum: int
    score_sum: int


@dataclass(frozen=True)
class CandidateEvidence:
    source: bytes
    cells: tuple


@dataclass(frozen=True)
class TrainingEvidence:
    stage_index: int
    candidates: tuple
    registration_sha256: str
    games_sha256: str
    audits_sha256: str
    receipt_sha256: str
    completed_games: int = 20000
    campaign_id: str = CAMPAIGN_ID
    catalog_sha256: str = CATALOG_SHA256
    phase: str = 'train'


@dataclass(frozen=True)
class StudyArm:
    source: bytes
    games: int
    pairwise_numerator_sum: int
    score_sum: int


@dataclass(frozen=True)
class StudyEvidence:
    arms: tuple
    games_sha256: str
    audits_sha256: str
    receipt_sha256: str
    completed_games: int = 32768
    registration_sha256: str = STUDY_REGISTRATION_SHA256


def _training(evidence,target):
    require(type(evidence) is TrainingEvidence and _integer(evidence.stage_index,4,78)
        and evidence.stage_index==target-1 and evidence.phase=='train'
        and evidence.campaign_id==CAMPAIGN_ID and evidence.catalog_sha256==CATALOG_SHA256
        and _integer(evidence.completed_games,20000,20000)
        and all(_hash(getattr(evidence,key)) for key in ('registration_sha256','games_sha256','audits_sha256','receipt_sha256')),
        'External verified immediately previous complete TRAIN evidence required; declarations do not grant admission')
    require(type(evidence.candidates) is tuple and len(evidence.candidates)==8
        and all(type(row) is CandidateEvidence for row in evidence.candidates),'Eight typed previous candidate aggregates required')
    metadata = _population([row.source for row in evidence.candidates])
    if evidence.stage_index==4:
        require(all(row['family']=='e8-config' for row in metadata),'Legacy stage4 is the exact e8-config family only')
    if evidence.stage_index>=5:
        require([row['source_sha256'] for row in metadata[:3]]==[E8,BLOCKER,FEINT],'Prior continuation reference slots changed')
    expected = Counter()
    for map_index in range(evidence.stage_index*100,(evidence.stage_index+1)*100):
        for episode in range(200):
            row = contract.slot_schedule(map_index,episode)
            expected[row['candidate_slot'],row['seat'],row['token'],row['field']]+=1
    result = []
    for slot,(candidate,meta) in enumerate(zip(evidence.candidates,metadata)):
        require(type(candidate.cells) is tuple and len(candidate.cells)==64,'Complete64-cell fitness aggregates required')
        seen,standardized,raw = set(),Fraction(0),0
        for cell in candidate.cells:
            require(type(cell) is CellFitness and _integer(cell.seat,0,3) and _integer(cell.token,1,4)
                and cell.field in core.FIELDS and (cell.seat,cell.token,cell.field) not in seen
                and _integer(cell.games,1,2500) and cell.games==expected[slot,cell.seat,cell.token,cell.field]
                and _integer(cell.pairwise_numerator_sum,0,6*cell.games) and _integer(cell.score_sum,0,(1<<63)-1),
                'Changed, duplicated or incomplete current-stage fitness cell')
            seen.add((cell.seat,cell.token,cell.field))
            standardized+=Fraction(cell.pairwise_numerator_sum,2*cell.games*64);raw+=cell.score_sum
        result.append(dict(meta,source=candidate.source,standardized=standardized,raw_mean=Fraction(raw,2500)))
    return sorted(result,key=lambda row:(-row['standardized'],-row['raw_mean'],row['source_sha256']))


def _study(evidence):
    require(type(evidence) is StudyEvidence and evidence.registration_sha256==STUDY_REGISTRATION_SHA256
        and _integer(evidence.completed_games,32768,32768)
        and all(_hash(getattr(evidence,key)) for key in ('games_sha256','audits_sha256','receipt_sha256'))
        and type(evidence.arms) is tuple and len(evidence.arms)==4,'External verified COMPLETE four-arm study required, never partial means')
    result = []
    for arm in evidence.arms:
        require(type(arm) is StudyArm and _integer(arm.games,8192,8192)
            and _integer(arm.pairwise_numerator_sum,0,6*8192) and _integer(arm.score_sum,0,(1<<63)-1),
            'Complete typed four-arm mean aggregates required')
        meta = classify_source(arm.source)
        result.append(dict(meta,source=arm.source,standardized=Fraction(arm.pairwise_numerator_sum,2*8192),raw_mean=Fraction(arm.score_sum,8192)))
    require({row['source_sha256'] for row in result}=={E8,DEFENSE,BLOCKER,FEINT},'Exact complete four reference architectures required')
    return sorted(result,key=lambda row:(-row['standardized'],-row['raw_mean'],row['source_sha256']))


def population_recipe(stage_index,previous_envelope,study_envelope=None,*,verify_evidence=None,allow_crossover=False):
    """Caller-verifier assertion is mandatory; this module is not an authority."""
    require(_integer(stage_index,5,79) and type(allow_crossover) is bool,'Fixed TRAIN stage and Boolean crossover recipe required')
    require(callable(verify_evidence),'A separate reviewed evidence verifier is required; approved=True is not admission')
    guards = source_pins();version = version_id()
    prior = verify_evidence('fully-accepted-primary-train/1',previous_envelope)
    ranked = _training(prior,stage_index)
    study = None
    if stage_index==5:
        require(study_envelope is not None,'Stage5 requires the COMPLETE verified four-arm study')
        study = verify_evidence('complete-four-arm-study/1',study_envelope)
        initial = _study(study)
    else:
        require(study_envelope is None,'Later parents use current previous TRAIN stage only, never cross-stage study ranking')
        initial = ranked
    bodies = _references();metadata = [classify_source(body) for body in bodies]
    retained = [dict(row,slot=index,kind='fixed_reference',lineage=dict(parents=[])) for index,row in enumerate(metadata)]
    seen = {row['source_sha256'] for row in metadata};genotypes = {row['genotype_sha256'] for row in metadata}
    for row in ranked:
        if row['source_sha256'] in seen or row['genotype_sha256'] in genotypes:
            continue
        bodies.append(row['source']);seen.add(row['source_sha256']);genotypes.add(row['genotype_sha256'])
        retained.append({**{key:value for key,value in row.items() if key not in ('source','standardized','raw_mean')},
            'slot':len(retained),'kind':'previous_stage_elite','lineage':dict(parents=[row['source_sha256']],
                fitness_stage=prior.stage_index,receipt_sha256=prior.receipt_sha256,
                standardized=[row['standardized'].numerator,row['standardized'].denominator],
                raw_mean=[row['raw_mean'].numerator,row['raw_mean'].denominator])})
        if len(retained)==5:
            break
    require(len(retained)==5,'Two distinct non-reference elites required; no cross-generation fallback')
    all_attempts = []
    for family in FAMILIES:
        if stage_index==5 and family!='e8-config':
            parents = [dict(row,source=body) for row,body in zip(metadata,bodies[:3]) if row['family']==family]
        else:
            parents = [row for row in initial if row['family']==family]
        require(parents,'A fixed reference ensures a previous-stage parent for every family')
        exporter = _e8_space() if family=='e8-config' else TemplateSpace(family)
        for attempt in range(64):
            first = parents[0];genes = dict(first['genes']);ancestry = [first['source_sha256']]
            cross_seed = domain_seed(version,'population-crossover',stage_index,family,attempt)
            mutation_seed = domain_seed(version,'population-mutation',stage_index,family,attempt)
            crossed = allow_crossover and len(parents)>=2
            if crossed:
                genes = exporter.crossover(genes,parents[1]['genes'],cross_seed)
                ancestry.append(parents[1]['source_sha256'])
            if family=='e8-config':
                genes = exporter.mutate(genes,mutation_seed,scale=.08,grouped=False)
            else:
                genes = exporter.mutate(genes,mutation_seed,scale=.06,max_changes=3)
            body = exporter.export(genes);meta = classify_source(body)
            reason = ('source_duplicate' if meta['source_sha256'] in seen else
                      'genotype_duplicate' if meta['genotype_sha256'] in genotypes else
                      'unchanged_parent' if meta['genotype_sha256']==first['genotype_sha256'] else 'retained')
            record = dict(family=family,attempt=attempt,parents=ancestry,crossover=crossed,
                crossover_seed=cross_seed if crossed else None,mutation_seed=mutation_seed,genes=genes,
                source_sha256=meta['source_sha256'],genotype_sha256=meta['genotype_sha256'],status=reason)
            all_attempts.append(record)
            if reason=='retained':
                seen.add(meta['source_sha256']);genotypes.add(meta['genotype_sha256']);bodies.append(body)
                retained.append(dict(meta,slot=len(retained),kind='bounded_family_child',lineage=record))
                break
        else:
            error = ValueError('All64 preregistered family dedup attempts exhausted; no replacement/tuning recipe')
            error.recipe_attempts = tuple(copy.deepcopy(all_attempts))
            raise error
    _population(bodies)
    require(len(bodies)==8 and source_pins()==guards,'Population coverage or source guards changed')
    payload = dict(format=FORMAT,version_id=version,generation=stage_index,candidates=retained,attempts=all_attempts,
        previous_stage=prior.stage_index,previous_receipt_sha256=prior.receipt_sha256,
        study_receipt_sha256=None if study is None else study.receipt_sha256,allow_crossover=allow_crossover,
        operators=copy.deepcopy(OPERATORS),source_sha256=guards,
        evidence_scope='Typed records are caller-verifier assertions only; this pure module cannot authenticate admission.',
        requires_external_admission_bridge=True,certifies_executed_games=False,primary_games_accepted=0,bmcts_audits=0,promoted=False)
    return dict(payload=payload,recipe_sha256=sha(canonical(payload)),candidate_sources=tuple(bodies))
