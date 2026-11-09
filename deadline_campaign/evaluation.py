"""Complete-cohort aggregation and prospectively fixed map-block inference."""
from fractions import Fraction
import math

from .design import FIELDS,canonical,sha

BOOTSTRAP_REPLICATES=20000
BOOTSTRAP_SEED=20261109114339
FIELD_NONINFERIORITY_MARGIN=.05


def _int(value,low,high): return type(value) is int and low<=value<=high


def aggregate(registration,rows):
    fixtures={f['id']:f for f in registration['fixtures']}
    candidates=[c['sha256'] for c in registration['candidates']]
    maps=sorted({f['map_id'] for f in fixtures.values()})
    cells={}
    seen=set()
    for row in rows:
        key=row.get('fixture')
        if key not in fixtures or key in seen: raise ValueError('Duplicate or foreign outcome')
        seen.add(key); f=fixtures[key]
        if (row.get('candidate')!=f['candidate'] or row.get('map_id')!=f['map_id']
                or row.get('focal_seat')!=f['seat'] or row.get('field')!=f['field']
                or row.get('opponent_ids')!=[s['id'] for s in f['opponents']]
                or row.get('faults')!=[] or type(row.get('scores')) is not list or len(row['scores'])!=4
                or any(not _int(v,0,2**63-1) for v in row['scores'])):
            raise ValueError('Outcome identity, faults or exact scores invalid')
        scores=row['scores']; score=scores[f['seat']]
        pw2=sum(2 if score>value else 1 if score==value else 0 for seat,value in enumerate(scores) if seat!=f['seat'])
        if (type(row.get('focal_pw')) not in (int,float) or row['focal_pw']!=pw2/2
                or not _int(row.get('focal_score'),0,2**63-1) or row['focal_score']!=score):
            raise ValueError('Pairwise arithmetic changed')
        cell=(f['candidate'],f['map_id'],f['field'],f['seat'],f['token'])
        if cell in cells: raise ValueError('Duplicate map/field/seat/token cell')
        cells[cell]=(pw2,score)
    if seen!=set(fixtures): raise ValueError('Incomplete cohort cannot be ranked')
    if len(cells)!=len(candidates)*len(maps)*64:
        raise ValueError('Complete balanced64-cell crossing per map/candidate required')
    result=[]
    for candidate in candidates:
        cube=[]; field_sums={field:0 for field in FIELDS}; score_sum=0; pw_sum=0
        for map_id in maps:
            per_map=[]
            for field in FIELDS:
                selected=[cells[candidate,map_id,field,seat,token] for seat in range(4) for token in range(1,5)]
                p=sum(v[0] for v in selected); s=sum(v[1] for v in selected)
                field_sums[field]+=p; pw_sum+=p; score_sum+=s; per_map.append(p)
            cube.append(per_map)
        games=len(maps)*64
        result.append(dict(sha256=candidate,games=games,pairwise_numerator_sum=pw_sum,score_sum=score_sum,
            mean_pairwise=pw_sum/(2*games),mean_score=score_sum/games,
            fields={field:field_sums[field]/(32*len(maps)) for field in FIELDS},
            map_field_pw2=cube))
    result.sort(key=lambda r:(-Fraction(r['pairwise_numerator_sum'],2*r['games']),
        -min(Fraction(sum(row[index] for row in r['map_field_pw2']),32*len(maps)) for index in range(4)),
        -Fraction(r['score_sum'],r['games']),r['sha256']))
    return dict(maps=maps,games=len(rows),ranking=result,
        fitness='Equal map/field/seat/token mean pairwise0..3, then worst field, raw score, source SHA.',
        selection_claim='TRAIN/DEV ranks are exploratory; no unadjusted winner significance.')


def final_decision(aggregated,challenger,anchor):
    if challenger==anchor: raise ValueError('Distinct frozen challenger and anchor required')
    arms={r['sha256']:r for r in aggregated['ranking']}
    if set(arms)!={challenger,anchor} or len(aggregated['maps'])<64:
        raise ValueError('Complete fixed untouched final two-arm panel required')
    import numpy as np
    # Field pw2 sums have16games/map. Both arms receive matched rival streams.
    delta=(np.asarray(arms[challenger]['map_field_pw2'],dtype=np.int64)
           -np.asarray(arms[anchor]['map_field_pw2'],dtype=np.int64))/32.0
    if delta.shape!=(len(aggregated['maps']),4) or not np.isfinite(delta).all():
        raise ValueError('Invalid complete paired map-block contrast')
    rng=np.random.default_rng(BOOTSTRAP_SEED)
    boot=np.empty((BOOTSTRAP_REPLICATES,5),dtype=np.float64)
    for start in range(0,BOOTSTRAP_REPLICATES,1000):
        count=min(1000,BOOTSTRAP_REPLICATES-start)
        indices=rng.integers(0,len(delta),size=(count,len(delta)))
        fields=delta[indices].mean(axis=1)
        boot[start:start+count,:4]=fields
        boot[start:start+count,4]=fields.mean(axis=1)
    # Explicit order statistics avoid a version-dependent interpolation choice.
    ordered=np.sort(boot,axis=0)
    low=int(.025*BOOTSTRAP_REPLICATES)-1; high=int(.975*BOOTSTRAP_REPLICATES)-1
    field_low=int((.05/4)*BOOTSTRAP_REPLICATES)-1
    overall=[float(ordered[low,4]),float(ordered[high,4])]
    fields={field:dict(delta=float(delta[:,index].mean()),
        lower_one_sided_bonferroni=float(ordered[field_low,index]),
        noninferiority_margin=FIELD_NONINFERIORITY_MARGIN)
        for index,field in enumerate(FIELDS)}
    passed=(overall[0]>0 and all(r['lower_one_sided_bonferroni']>-FIELD_NONINFERIORITY_MARGIN for r in fields.values()))
    return dict(challenger=challenger,anchor=anchor,selected=challenger if passed else anchor,promoted=passed,
        maps=len(delta),games=aggregated['games'],mean_pairwise_delta=float(delta.mean()),
        overall_two_sided_95_percentile_interval=overall,fields=fields,
        bootstrap=dict(replicates=BOOTSTRAP_REPLICATES,seed=BOOTSTRAP_SEED,resampling='whole matched map blocks; same draws for all fields and overall',
            overall_order_statistics=[low,high],field_lower_order_statistic=field_low),
        decision_rule='Promote iff overall95% lower>0 AND all4 Bonferroni one-sided field lower bounds>-.05PW; otherwise anchor.',
        inference_limit='Prospective approximate percentile map bootstrap; neither exact coverage nor a joint5-claim familywise guarantee. Unknown rival algorithms remain untested.',
        final_used_for_tuning=False,primary_campaign_credit=0,bmcts_credit=0)
