"""Independent pure planning checks: no actual stage, study or actor is read/run."""
from collections import Counter
from dataclasses import replace
from fractions import Fraction
from functools import lru_cache
from pathlib import Path
import unittest
from unittest.mock import patch

from evolution.genomes import GenomeSpace
from evolution_templates.space import TemplateSpace
from primary_migration import contract
from . import recipe as model


ROOT=Path(__file__).resolve().parents[1]
FIELDS=('economic','independent','erratic','pressure')


@lru_cache(maxsize=4)
def sources():
    base=GenomeSpace((ROOT/'bot.py').read_bytes())
    result=[base.body]
    for index in range(1,8):
        genes=dict(base.genes);genes['inertia']=.05+index/1000
        result.append(base.export(genes))
    return tuple(result)


def original_counter_schedule(stage):
    """Independent original generation loop; no migration closed-form helper."""
    occurrence=Counter();result=[]
    for map_index in range(stage*100,(stage+1)*100):
        for episode in range(200):
            seat=episode%4;token=(episode//4+seat+map_index)%4+1
            n=occurrence[seat,token];occurrence[seat,token]+=1
            candidate=(n+4*seat+token-1)%8
            field=FIELDS[(n//8+n%8+2*seat+token-1)%4]
            result.append(dict(map_index=map_index,episode=episode,phase='train',stage_index=stage,
                seat=seat,token=token,candidate_slot=candidate,field=field,canonical_slot=200*map_index+episode))
    return result


def evidence(stage,bodies,levels=None):
    counts=Counter((r['candidate_slot'],r['seat'],r['token'],r['field']) for r in original_counter_schedule(stage))
    candidates=[];levels=[0,5,4,3,2,1,0,0] if levels is None else levels
    for slot,source in enumerate(bodies):
        cells=tuple(model.CellFitness(seat,token,field,n,levels[slot]*n,(100+slot)*n)
            for (s,seat,token,field),n in sorted(counts.items()) if s==slot)
        candidates.append(model.CandidateEvidence(source,cells))
    return model.TrainingEvidence(stage,tuple(candidates),'1'*64,'2'*64,'3'*64,'4'*64)


def study():
    base=GenomeSpace((ROOT/'bot.py').read_bytes());genes=dict(base.genes)
    genes.update(backfire_cost=1.674416,feint_weight=1.167526,shield_prior=.333592,
                 shield_weight=1.227437,stay_prior=.771476)
    defense=base.export(genes)
    assert model.sha(defense)==model.DEFENSE
    bodies=[base.body,defense,(ROOT/'tester_bots/blocker.py').read_bytes(),
        (ROOT/'confirmation_campaign/evidence/architectures_v2/feint_original.py').read_bytes()]
    # Entirely invented aggregate levels: stronger other families must not be
    # selected as the e8-family parent. This is not current-study evidence.
    arms=tuple(model.StudyArm(body,8192,level*8192,(400+index)*8192)
        for index,(body,level) in enumerate(zip(bodies,(2,4,6,6))))
    return model.StudyEvidence(arms,'5'*64,'6'*64,'7'*64)


class IndependentRecipeTests(unittest.TestCase):
    def test_exact_source_reconstruction_rejects_the_candidate_genomespace_trap(self):
        e8=sources()[0]
        changed=e8+b'\n# GenomeSpace(candidate) would bless this altered implementation\n'
        unsafe=GenomeSpace(changed)
        self.assertEqual(unsafe.export(unsafe.genes),changed)
        with self.assertRaises(ValueError): model.classify_source(changed)
        for body,family,oracles in ((e8,'e8-config',80),
                ((ROOT/'tester_bots/blocker.py').read_bytes(),'original-blocker',0),
                ((ROOT/'confirmation_campaign/evidence/architectures_v2/feint_original.py').read_bytes(),'original-feint',0)):
            metadata=model.classify_source(body)
            self.assertEqual((metadata['family'],metadata['expected_focal_legacy_oracles_per_full_game']),(family,oracles))
            self.assertFalse(metadata['runtime_qualified']);self.assertFalse(metadata['grants_admission'])
            self.assertEqual(metadata['new_primary_credit'],0)
            for tamper in (body+b'\nimport os\n',body.replace(b'seed=seat * 7919',b'seed=seat * 7920')):
                if tamper!=body:
                    with self.assertRaises(ValueError): model.classify_source(tamper)
        for bad in (None,'not bytes',b'',b'CONFIG = {}\n',True):
            with self.assertRaises(ValueError): model.classify_source(bad)

    def test_independent_old_counter_loop_matches_all20k_slots_and_real_field_imbalance(self):
        rows=original_counter_schedule(5)
        for row in rows:
            self.assertEqual(contract.slot_schedule(row['map_index'],row['episode']),row)
        self.assertEqual(len({r['canonical_slot'] for r in rows}),20000)
        self.assertEqual((min(r['canonical_slot'] for r in rows),max(r['canonical_slot'] for r in rows)),(100000,119999))
        self.assertEqual(Counter(r['candidate_slot'] for r in rows),{slot:2500 for slot in range(8)})
        cells=Counter((r['candidate_slot'],r['seat'],r['token'],r['field']) for r in rows)
        field_counts=Counter((r['candidate_slot'],r['field']) for r in rows)
        self.assertEqual(len(cells),512);self.assertEqual(set(cells.values()),{39,40})
        self.assertEqual(set(field_counts.values()),{624,626,628})
        self.assertNotEqual(set(field_counts.values()),{625})
        for map_index,episode in ((500,0),(7999,199)):
            row=contract.slot_schedule(map_index,episode)
            self.assertTrue(100000<=row['canonical_slot']<1600000)
        for args in ((True,0),(500,True),(-1,0),(10000,0),(500,200)):
            with self.assertRaises(ValueError): contract.slot_schedule(*args)
        for stage in (4,80,True,5.0):
            with self.assertRaises(ValueError): model.stage_recipe(b'{}',stage,sources())

    def test_injective65bit_rival_seeds_roundtrip_ninebyte_keys_without_oldnamespace_overlap(self):
        keys=set();seeds=set()
        for row in original_counter_schedule(5):
            for seat in range(4):
                if seat==row['seat']: continue
                seed=contract.rival_seed(row['map_index'],row['episode'],seat)
                self.assertEqual(seed,(1<<64)+4*row['canonical_slot']+seat)
                key=model.rival_seed_blob(seed)
                self.assertEqual(len(key),9);self.assertEqual(int.from_bytes(key,'big'),seed)
                self.assertNotEqual(key,model.seed_blob(seed-(1<<64)))
                self.assertNotIn(seed,seeds);self.assertNotIn(key,keys)
                seeds.add(seed);keys.add(key)
        self.assertEqual(len(keys),60000)
        self.assertEqual(int.from_bytes(model.seed_blob((1<<64)-1),'big'),(1<<64)-1)
        for bad in (True,False,float(1<<64),-1,1<<65):
            with self.assertRaises(ValueError): model.seed_blob(bad)
        with self.assertRaises(ValueError): model.rival_seed_blob((1<<64)-1)
        first=contract.slot_schedule(500,0)
        with self.assertRaises(ValueError): contract.rival_seed(500,0,first['seat'])

    def test_typed_verifier_results_are_caller_assertions_never_boolean_admission(self):
        for verifier in (None,lambda *args:True,lambda *args:{'approved':True}):
            with self.assertRaises(ValueError): model.population_recipe(5,'SYNTHETIC','SYNTHETIC',verify_evidence=verifier)
        prior=evidence(4,sources());complete=study()
        for bad in (replace(prior,stage_index=3),replace(prior,stage_index=4.0),replace(prior,phase='development'),
                    replace(prior,campaign_id='f'*64),replace(prior,catalog_sha256='f'*64),
                    replace(prior,completed_games=19999),replace(prior,receipt_sha256='not a hash')):
            with self.assertRaises(ValueError): model._training(bad,5)
        for bad in (replace(complete,completed_games=32767),replace(complete,arms=complete.arms[:-1]),
                    replace(complete,arms=(replace(complete.arms[0],games=8191),*complete.arms[1:])),True,{'complete':True}):
            with self.assertRaises(ValueError): model._study(bad)
        metadata=model.description()
        self.assertFalse(metadata['grants_admission']);self.assertFalse(metadata['certifies_executed_games'])
        self.assertEqual(metadata['new_primary_credit'],0);self.assertEqual(metadata['bmcts_audits'],0)

    def test_64cell_fraction_fitness_beats_misleading_raw_pairwise_mean(self):
        prior=evidence(4,sources(),[0]*8)
        candidates=list(prior.candidates)
        a=[];b=[];extra=1
        for cell in candidates[1].cells:
            a.append(replace(cell,pairwise_numerator_sum=1 if cell.games==39 else 0))
        for cell in candidates[2].cells:
            value=0
            if cell.games==40: value=15+extra;extra=0
            b.append(replace(cell,pairwise_numerator_sum=value))
        candidates[1]=replace(candidates[1],cells=tuple(a));candidates[2]=replace(candidates[2],cells=tuple(b))
        prior=replace(prior,candidates=tuple(candidates))
        self.assertLess(sum(c.pairwise_numerator_sum for c in a),sum(c.pairwise_numerator_sum for c in b))
        ranked=model._training(prior,5)
        self.assertEqual(ranked[0]['source_sha256'],model.sha(candidates[1].source))
        self.assertEqual(ranked[0]['standardized'],Fraction(60,2*39*64))
        self.assertEqual(ranked[1]['standardized'],Fraction(61,2*40*64))
        malformed=replace(candidates[1],cells=(candidates[1].cells[0],)*64)
        with self.assertRaises(ValueError): model._training(replace(prior,candidates=(candidates[0],malformed,*candidates[2:])),5)

    def test_stage5_and_later_parent_lineage_use_only_the_declared_complete_evidence(self):
        prior=evidence(4,sources());complete=study();seen=[]
        def verifier(scope,envelope):
            seen.append((scope,envelope))
            return prior if scope=='fully-accepted-primary-train/1' else complete
        result=model.population_recipe(5,'SYNTHETIC_PREVIOUS','SYNTHETIC_STUDY',verify_evidence=verifier)
        payload=result['payload'];candidates=payload['candidates']
        self.assertEqual([c['source_sha256'] for c in candidates[:3]],[model.E8,model.BLOCKER,model.FEINT])
        self.assertEqual(candidates[5]['lineage']['parents'],[model.DEFENSE])
        self.assertEqual(candidates[6]['lineage']['parents'],[model.BLOCKER])
        self.assertEqual(candidates[7]['lineage']['parents'],[model.FEINT])
        self.assertTrue(payload['requires_external_admission_bridge']);self.assertEqual(payload['primary_games_accepted'],0)
        self.assertEqual(seen,[('fully-accepted-primary-train/1','SYNTHETIC_PREVIOUS'),('complete-four-arm-study/1','SYNTHETIC_STUDY')])
        later=evidence(5,result['candidate_sources'],[0,0,0,1,1,6,5,4])
        updated=model.population_recipe(6,'SYNTHETIC_STAGE5',verify_evidence=lambda *args:later)
        children=updated['payload']['candidates'][5:]
        self.assertEqual([c['lineage']['parents'][0] for c in children],
                         [model.sha(result['candidate_sources'][slot]) for slot in (5,6,7)])
        with self.assertRaises(ValueError): model.population_recipe(7,None,verify_evidence=lambda *args:later)
        with self.assertRaises(ValueError): model.population_recipe(6,None,complete,verify_evidence=lambda *args:later)

    def test_duplicate_exports_and_all64_failed_attempt_lineages_are_preserved(self):
        previous=evidence(4,sources());complete=study()
        with self.assertRaises(ValueError): model._population((sources()[0],)*8)
        with patch.object(GenomeSpace,'mutate',side_effect=lambda parent,*args,**kwargs:dict(parent)):
            with self.assertRaisesRegex(ValueError,'All64') as caught:
                model.population_recipe(5,None,complete,
                    verify_evidence=lambda scope,value:previous if scope=='fully-accepted-primary-train/1' else complete)
        attempts=caught.exception.recipe_attempts
        self.assertEqual(len(attempts),64);self.assertEqual([a['attempt'] for a in attempts],list(range(64)))
        self.assertEqual(len({a['mutation_seed'] for a in attempts}),64)
        self.assertTrue(all(a['family']=='e8-config' and a['status']!='retained' for a in attempts))
        self.assertTrue(all(a['parents']==[model.DEFENSE] for a in attempts))

    def test_distinct_numeric_spellings_cannot_bypass_genotype_deduplication(self):
        base=GenomeSpace((ROOT/'bot.py').read_bytes())
        pairs=[]
        for first,second in ((1,1.0),(0.0,-0.0)):
            genes=dict(base.genes);genes['inertia']=.13
            key='cash_weight' if first==1 else 'inertia'
            genes[key]=first;one=base.export(genes)
            genes[key]=second;two=base.export(genes)
            self.assertNotEqual(one,two)
            self.assertNotEqual(model.sha(one),model.sha(two))
            self.assertEqual(model.classify_source(one)['genotype_sha256'],model.classify_source(two)['genotype_sha256'])
            pairs.append((one,two))
        for pair in pairs:
            bodies=(*sources()[:6],*pair)
            with self.assertRaisesRegex(ValueError,'genotype'): model._population(bodies)


if __name__=='__main__': unittest.main()
