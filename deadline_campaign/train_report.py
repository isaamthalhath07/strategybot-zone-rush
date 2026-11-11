"""Read-only complete TRAIN contrasts; never authenticates, selects or promotes.

Source files are read only to classify exact registered policy bytes. No actor,
referee, GPU, private key, authority or controller is invoked by this module.
"""
import argparse
from itertools import combinations
import json
import math
from pathlib import Path

from . import design

FORMAT='zone-rush-complete-deadline-train-report/1'
REPLICATES=20000
BASE_SEED=20261109114339
UNADJUSTED_ORDER=(499,19499)
# floor(.05/(2*28)*20000)-1 and floor((1-.05/(2*28))*20000)-1.
BONFERRONI28_ORDER=(16,19981)
SOURCE_CLOSURE=('deadline_campaign/__init__.py','deadline_campaign/design.py','deadline_campaign/train_report.py',
    'primary_local/recipe.py','evolution/genomes.py','evolution_templates/space.py',
    'deadline_strategy/__init__.py','deadline_strategy/space.py','deadline_strategy/goal_space.py',
    'strategy_candidates/build_public_memory.py')


def require(value,message):
    if not value: raise ValueError(message)


def _integer(value,low,high): return type(value) is int and low<=value<=high


def _hex(value):
    return type(value) is str and len(value)==64 and all(c in '0123456789abcdef' for c in value)


def _finite(value):
    try: return type(value) in (int,float) and math.isfinite(value)
    except OverflowError: return False


def source_pins():
    return {name:design.sha((design.ROOT/name).read_bytes()) for name in SOURCE_CLOSURE}


def _validated(registration,aggregate):
    require(type(registration) is dict and registration.get('format')==design.FORMAT
        and registration.get('phase')=='train' and _integer(registration.get('generation'),0,467),
        'Only an explicitly complete deadline TRAIN generation is reportable')
    generation=registration['generation']; entries=registration.get('candidates');protocol=registration.get('protocol',{})
    require(type(entries) is list and len(entries)==8 and all(type(e) is dict and set(e)=={'path','sha256'}
        and type(e['path']) is str and _hex(e['sha256']) for e in entries)
        and len({e['sha256'] for e in entries})==8,'Eight exact distinct source entries required')
    require(type(protocol) is dict and protocol.get('maps')==16 and protocol.get('candidates')==8
        and protocol.get('fields')==list(design.FIELDS) and protocol.get('seat_token_crosses')==16
        and protocol.get('complete_games')==8192 and protocol.get('opponent_instances')==24576
        and protocol.get('matched_rival_streams') is False,'Exact complete independent-stream TRAIN protocol required')
    guards=registration.get('guards')
    require(type(guards) is dict and all(guards.get(str((design.ROOT/name).resolve()))==digest
        for name,digest in source_pins().items()),'Reporter/classifier source closure differs from registered source guards')
    metadata=[]
    for entry in entries:
        path=Path(entry['path']).resolve()
        require(path.is_relative_to(design.ROOT) and path.suffix=='.py','Only local registered Python sources may be read')
        body=path.read_bytes();require(design.sha(body)==entry['sha256'],'Registered candidate source changed')
        info=design.classify(body)
        require(info['source_sha256']==entry['sha256'],'Exact source classifier mismatch')
        metadata.append(dict(info,source_path=str(path)))
    fixtures=registration.get('fixtures')
    require(type(fixtures) is list and len(fixtures)==8192,'No partial fixture list')
    ids=set();cells=set();maps={};rival_ids=set();rival_seeds=set();focal_ids=set()
    for f in fixtures:
        require(type(f) is dict and _hex(f.get('id')) and f['id'] not in ids
            and f.get('phase')=='train' and type(f.get('generation')) is int and f['generation']==generation
            and _integer(f.get('candidate_slot'),0,7) and f.get('candidate')==entries[f['candidate_slot']]['sha256']
            and _integer(f.get('seat'),0,3) and _integer(f.get('token'),1,4) and f.get('field') in design.FIELDS
            and _integer(f.get('map_index'),500+16*generation,515+16*generation) and _hex(f.get('map_id')),
            'Foreign, duplicate or malformed TRAIN fixture')
        cell=(f['candidate'],f['map_id'],f['field'],f['seat'],f['token'])
        require(cell not in cells,'Duplicate map/field/seat/token cell')
        require(f['map_index'] not in maps or maps[f['map_index']]==f['map_id'],'Map-index identity mismatch')
        require(_hex(f.get('focal_actor_id')) and f['focal_actor_id'] not in focal_ids,'Focal instance reused')
        specs=f.get('opponents')
        require(type(specs) is list and len(specs)==3 and {s.get('seat') for s in specs}==set(range(4))-{f['seat']},
                'Three correct rival seats required')
        for spec in specs:
            require(_hex(spec.get('id')) and spec['id'] not in rival_ids and _integer(spec.get('seed'),2**96,2**128-1)
                and spec['seed'] not in rival_seeds,'TRAIN rival identity or actual integer seed reused')
            rival_ids.add(spec['id']);rival_seeds.add(spec['seed'])
        ids.add(f['id']);cells.add(cell);maps[f['map_index']]=f['map_id'];focal_ids.add(f['focal_actor_id'])
    require(len(maps)==len(set(maps.values()))==16,'Sixteen distinct complete map identities required')
    expected={(e['sha256'],m,field,seat,token) for e in entries for m in maps.values()
              for field in design.FIELDS for seat in range(4) for token in range(1,5)}
    require(cells==expected,'Incomplete exact TRAIN crossing')
    require(type(aggregate) is dict and aggregate.get('maps')==sorted(maps.values()) and aggregate.get('games')==8192,
            'Aggregate is incomplete or belongs to other maps')
    ranking=aggregate.get('ranking')
    require(type(ranking) is list and len(ranking)==8 and {r.get('sha256') for r in ranking}=={e['sha256'] for e in entries},
            'Aggregate must cover exactly all eight arms')
    indexed={r['sha256']:r for r in ranking}
    for row in ranking:
        cube=row.get('map_field_pw2')
        require(type(cube) is list and len(cube)==16 and all(type(line) is list and len(line)==4
            and all(_integer(v,0,96) for v in line) for line in cube),'Exact integer16map×4field cube required')
        total=sum(map(sum,cube));games=1024
        require(type(row.get('games')) is int and row['games']==games
            and type(row.get('pairwise_numerator_sum')) is int and row['pairwise_numerator_sum']==total
            and _integer(row.get('score_sum'),0,2**63-1)
            and _finite(row.get('mean_pairwise')) and row['mean_pairwise']==total/(2*games)
            and _finite(row.get('mean_score')) and row['mean_score']==row['score_sum']/games,
            'Aggregate totals, means or count drift')
        require(type(row.get('fields')) is dict and set(row['fields'])==set(design.FIELDS)
            and all(_finite(row['fields'][field]) and row['fields'][field]==sum(line[i] for line in cube)/512
                    for i,field in enumerate(design.FIELDS)),'Field mean arithmetic drift')
    return metadata,indexed


def report(registration,aggregate):
    """Read exact policy sources; calculate all contrasts from supplied complete data.

    Admission is a required caller responsibility and is not asserted by this
    function. Returning a report grants no acceptance, selection or game credit.
    """
    metadata,indexed=_validated(registration,aggregate)
    import numpy as np
    generation=registration['generation'];seed=BASE_SEED+generation
    shas=sorted(indexed);pairs=list(combinations(shas,2))
    cubes=np.asarray([indexed[s]['map_field_pw2'] for s in shas],dtype=np.int64)
    # One shared draw matrix for every source pair and field.
    rng=np.random.default_rng(seed)
    draws=rng.integers(0,16,size=(REPLICATES,16),dtype=np.int64)
    draw_digest=design.sha(draws.astype('<i8',copy=False).tobytes())
    boot=np.empty((REPLICATES,8,4),dtype=np.float64)
    for start in range(0,REPLICATES,1000):
        stop=min(start+1000,REPLICATES)
        boot[start:stop]=cubes[:,draws[start:stop],:].mean(axis=2).transpose(1,0,2)/32.0
    contrasts=[]
    for a,b in pairs:
        ia,ib=shas.index(a),shas.index(b)
        point=(cubes[ia]-cubes[ib])/32.0
        field_draws=boot[:,ia,:]-boot[:,ib,:]
        overall=np.sort(field_draws.mean(axis=1));fields=np.sort(field_draws,axis=0)
        contrasts.append(dict(a=a,b=b,orientation='a minus b',mean_pairwise_delta=float(point.mean()),
            unadjusted_95_interval=[float(overall[i]) for i in UNADJUSTED_ORDER],
            descriptive_bonferroni28_95_interval=[float(overall[i]) for i in BONFERRONI28_ORDER],
            fields={field:dict(delta=float(point[:,j].mean()),
                unadjusted_95_interval=[float(fields[i,j]) for i in UNADJUSTED_ORDER],
                interpretation='descriptive/exploratory; not adjusted across fields or all field contrasts')
                for j,field in enumerate(design.FIELDS)}))
    metadata={m['source_sha256']:m for m in metadata}
    return dict(format=FORMAT,phase='train',generation=generation,maps=16,games=8192,
        registration_canonical_sha256=design.sha(design.canonical(registration)),
        aggregate_canonical_sha256=design.sha(design.canonical(aggregate)),
        source_sha256=source_pins(),
        admission=dict(status='not verified by reporter; caller must supply only a complete root-admitted generation',
                       private_key_used=False,authority_invoked=False,certifies_executed_games=False),
        pairing='Map-matched complete field/seat/token crossing; fresh independent actual rival streams across TRAIN arms. No identical-lineup pairing.',
        arms=[dict(metadata=metadata[s],games=indexed[s]['games'],mean_pairwise=indexed[s]['mean_pairwise'],
            mean_score=indexed[s]['mean_score'],fields=indexed[s]['fields'],
            worst_field_mean=min(indexed[s]['fields'].values())) for s in shas],
        contrast_count=28,contrasts=contrasts,
        bootstrap=dict(replicates=REPLICATES,base_seed=BASE_SEED,generation=generation,effective_seed=seed,
            generator='NumPy default_rng PCG64; int64 draws with replacement',numpy_version=str(np.__version__),
            shared_map_draws_sha256=draw_digest,map_order=aggregate['maps'],
            resampling='whole maps; same draws for all arms/fields/28 contrasts',
            unadjusted_order_statistics=list(UNADJUSTED_ORDER),bonferroni28_order_statistics=list(BONFERRONI28_ORDER),
            quantiles='zero-based floor(p*20000)-1; no interpolation'),
        limitations=['Sixteen finite map clusters; percentile-bootstrap intervals are approximate, not exact simultaneous coverage.',
            'Bonferroni28 labels cover only the28 overall contrasts; field intervals are exploratory.',
            'TRAIN parent/elite selection and prior source selection create selection uncertainty; no winner inference or promotion.',
            'Map resampling does not isolate rival-stream variance or establish strength against unseen algorithms.',
            'Fresh instances/parameter draws are not new algorithms; deterministic planner policies have no action RNG to reseed.'],
        winner_inferred=False,selection_performed=False,promoted=False,primary_campaign_credit=0,bmcts_credit=0)


def _loads(body):
    def pairs(items):
        result={}
        for key,value in items:
            if key in result: raise ValueError('Duplicate JSON key')
            result[key]=value
        return result
    def reject(_): raise ValueError('Nonfinite JSON')
    return json.loads(body,object_pairs_hook=pairs,parse_constant=reject)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--registration',type=Path,required=True)
    parser.add_argument('--accepted-payload',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--caller-root-admitted',action='store_true',required=True,
        help='Explicit caller declaration only; reporter does not verify authority/MAC/admission')
    args=parser.parse_args(argv)
    raw=args.registration.read_bytes();registration=_loads(raw)
    accepted_raw=args.accepted_payload.read_bytes();accepted=_loads(accepted_raw)
    if type(accepted) is dict and 'payload' in accepted:
        require(accepted.get('scope')=='acceptance','Only an acceptance envelope may be unwrapped')
        accepted=accepted['payload']
    require(type(accepted) is dict and accepted.get('phase')=='train'
        and type(accepted.get('generation')) is int and accepted['generation']==registration.get('generation')
        and accepted.get('registration_sha256')==design.sha(raw)
        and type(accepted.get('original_games')) is int and accepted['original_games']==8192
        and type(accepted.get('independently_regenerated_callbacks')) is int
        and accepted['independently_regenerated_callbacks']==8192*320
        and accepted.get('both_referees') is True and accepted.get('promoted') is False
        and all(type(accepted.get(key)) is int and accepted[key]==0
            for key in ('original_primary_campaign_credit','completed_per_game_bmcts_audits')),
        'Explicit complete root-published TRAIN payload matching raw registration required')
    result=report(registration,accepted['aggregate'])
    result['caller_root_admitted_declaration']=True
    result['input_files']=dict(registration_sha256=design.sha(raw),accepted_payload_sha256=design.sha(accepted_raw))
    result['admission']['status']='Caller declares root-admitted; reporter has not authenticated the receipt/MAC or independently re-admitted outcomes.'
    body=design.canonical(result)+b'\n'
    with args.output.open('xb') as stream: stream.write(body)
    print(design.sha(body))


if __name__=='__main__': main()
