"""Pure synthetic schedule/aggregate tests. ZERO games, keys or admission.

The ten-thousand-map catalog below is synthetic and its digest boundary is
explicitly patched only in tests. No actual catalog/stage/study outcome is read.
The50d body is reconstructed from its already public exact source genotype.
"""
import ast
from collections import Counter
from dataclasses import replace
import hashlib
from pathlib import Path
import unittest
from unittest.mock import patch

from evolution.genomes import GenomeSpace
from primary_migration import contract
from . import recipe as r


def config50d(space):
    genes = dict(space.genes)
    genes.update(backfire_cost=1.674416,feint_weight=1.167526,shield_prior=.333592,
                 shield_weight=1.227437,stay_prior=.771476)
    body = space.export(genes)
    assert r.sha(body)==r.DEFENSE
    return body


def source_population():
    space = r._e8_space();result = [space.body]
    for value in range(1,8):
        genes = dict(space.genes);genes['inertia']=value/100
        result.append(space.export(genes))
    return tuple(result)


def training(stage,sources,levels=None):
    counts = Counter()
    for m in range(stage*100,(stage+1)*100):
        for episode in range(200):
            row=contract.slot_schedule(m,episode)
            counts[row['candidate_slot'],row['seat'],row['token'],row['field']]+=1
    values = []
    for slot,source in enumerate(sources):
        level = (levels or [6,5,5,4,3,2,1,0])[slot]
        cells = tuple(r.CellFitness(seat,token,field,n,level*n,(100+slot)*n)
                      for (s,seat,token,field),n in sorted(counts.items()) if s==slot)
        values.append(r.CandidateEvidence(source,cells))
    return r.TrainingEvidence(stage,tuple(values),'1'*64,'2'*64,'3'*64,'4'*64)


def complete_study():
    space = r._e8_space()
    bodies = [space.body,config50d(space),*r._references()[1:]]
    # Synthetic means make50d the e8-family parent, regardless of other families.
    arms = tuple(r.StudyArm(source,8192,level*8192,(300+index)*8192)
                 for index,(source,level) in enumerate(zip(bodies,(3,4,6,6))))
    return r.StudyEvidence(arms,'5'*64,'6'*64,'7'*64)


def synthetic_catalog():
    records,seen,counter = [],set(),0
    while len(records)<10000:
        value=counter;counter+=1;quarter=[]
        for _ in range(16):
            quarter.append(value%3+1);value//=3
        base=[quarter[min(row,7-row)*4+min(column,7-column)] for row in range(8) for column in range(8)]
        orbit=contract.rotation_orbit(base)
        if orbit in seen:
            continue
        seen.add(orbit);index=len(records)
        phase,start=('train',0) if index<8000 else ('development',8000) if index<9000 else ('final',9000)
        records.append(dict(map_index=index,phase=phase,phase_index=index-start,base=base,
            id=r.sha(bytes(base)),rotation_orbit=orbit,seed=index,family='SYNTHETIC_METADATA_ONLY'))
    return r.canonical(records)


class ExactFamilyTests(unittest.TestCase):
    def test_exact_e8_50d_blocker_feint_and_mutant_export_classification(self):
        space=r._e8_space()
        for body,family,oracles in ((space.body,'e8-config',80),(config50d(space),'e8-config',80),
                (r._references()[1],'original-blocker',0),(r._references()[2],'original-feint',0)):
            meta=r.classify_source(body)
            self.assertEqual((meta['family'],meta['expected_focal_legacy_oracles_per_full_game']),(family,oracles))
            self.assertFalse(meta['runtime_qualified']);self.assertFalse(meta['grants_admission'])
        for body in source_population()[1:]:
            self.assertEqual(r.classify_source(body)['family'],'e8-config')
        for family in r.FAMILIES[1:]:
            template=r.TemplateSpace(family)
            body=template.export(template.mutate(template.defaults,11))
            self.assertEqual(r.classify_source(body)['family'],family)

    def test_ast_equivalent_comment_or_correctness_edits_and_duplicate_genotypes_reject(self):
        body=r._e8_space().body
        for changed in (body+b'\n# not canonical\n',body.replace(b'"_policy_failures = 0"',b'"_policy_failures = 1"')+b'\n',
                        body.replace(b'conditional_postraid_upgrade\': True',b'conditional_postraid_upgrade\': False')):
            with self.assertRaises(ValueError):r.classify_source(changed)
        population=list(source_population());population[-1]=population[-2]
        with self.assertRaises(ValueError):r._population(population)
        genes=dict(r._e8_space().genes);genes.update(inertia=.13,cash_weight=1)
        first=r._e8_space().export(genes);genes['cash_weight']=1.0;second=r._e8_space().export(genes)
        self.assertNotEqual(r.sha(first),r.sha(second))
        self.assertEqual(r.classify_source(first)['genotype_sha256'],r.classify_source(second)['genotype_sha256'])
        population=list(source_population());population[-2:]=[first,second]
        with self.assertRaisesRegex(ValueError,'genotype'):r._population(population)
        genes.update(risk_open=0.0);first=r._e8_space().export(genes)
        genes['risk_open']=-0.0;second=r._e8_space().export(genes)
        self.assertNotEqual(r.sha(first),r.sha(second))
        self.assertEqual(r.classify_source(first)['genotype_sha256'],r.classify_source(second)['genotype_sha256'])

    def test_65bit_seed_keys_preserve_high_bits_and_injective_contract_coordinates(self):
        keys=set()
        for m in (500,501,7900,7999):
            for episode in range(200):
                own=contract.slot_schedule(m,episode)['seat']
                for seat in range(4):
                    if seat==own:continue
                    seed=contract.rival_seed(m,episode,seat)
                    key=r.rival_seed_blob(seed)
                    self.assertEqual(len(key),9);self.assertEqual(int.from_bytes(key,'big'),seed)
                    self.assertGreaterEqual(seed,1<<64);self.assertNotIn(key,keys);keys.add(key)
                    self.assertNotEqual(key,r.seed_blob(seed-(1<<64)))
        for bad in (True,float(1<<64),-1,1<<65):
            with self.assertRaises(ValueError):r.seed_blob(bad)


class PopulationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.previous=training(4,source_population());cls.study=complete_study()

    def verifier(self,scope,envelope):
        if scope=='fully-accepted-primary-train/1' and envelope=='SYNTHETIC_PREVIOUS':return self.previous
        if scope=='complete-four-arm-study/1' and envelope=='SYNTHETIC_COMPLETE_STUDY':return self.study
        raise ValueError('Unverified synthetic envelope')

    def make(self,**options):
        return r.population_recipe(5,'SYNTHETIC_PREVIOUS','SYNTHETIC_COMPLETE_STUDY',verify_evidence=self.verifier,**options)

    def test_stage5_keeps_references_elites_current_stage_ties_and_complete_study_e8_parent(self):
        result=self.make();meta=result['payload']['candidates']
        self.assertEqual([row['source_sha256'] for row in meta[:3]],[r.E8,r.BLOCKER,r.FEINT])
        previous=self.previous.candidates
        self.assertEqual([row['source_sha256'] for row in meta[3:5]],[r.sha(previous[2].source),r.sha(previous[1].source)])
        self.assertEqual([row['family'] for row in meta[5:]],list(r.FAMILIES))
        self.assertEqual(meta[5]['lineage']['parents'],[r.DEFENSE])
        self.assertEqual(meta[6]['lineage']['parents'],[r.BLOCKER]);self.assertEqual(meta[7]['lineage']['parents'],[r.FEINT])
        self.assertEqual(result,self.make())
        self.assertEqual(len({row['genotype_sha256'] for row in meta}),8)
        self.assertFalse(result['payload']['certifies_executed_games']);self.assertEqual(result['payload']['primary_games_accepted'],0)

    def test_later_parent_and_elite_selection_skip_all_fixed_refs_and_never_compare_stages(self):
        previous=r.population_recipe(5,'SYNTHETIC_PREVIOUS','SYNTHETIC_COMPLETE_STUDY',verify_evidence=self.verifier)
        evidence=training(5,previous['candidate_sources'],[6,6,6,5,4,3,2,1])
        result=r.population_recipe(6,'SYNTHETIC_STAGE5',verify_evidence=lambda scope,envelope:evidence,allow_crossover=True)
        meta=result['payload']['candidates']
        self.assertEqual([row['source_sha256'] for row in meta[3:5]],[r.sha(previous['candidate_sources'][3]),r.sha(previous['candidate_sources'][4])])
        self.assertEqual([row['lineage']['parents'][0] for row in meta[5:]],[r.E8,r.BLOCKER,r.FEINT])
        self.assertTrue(all(row['lineage']['crossover'] for row in meta[5:]))
        with self.assertRaises(ValueError):r.population_recipe(7,None,verify_evidence=lambda *args:evidence)
        with self.assertRaises(ValueError):r.population_recipe(6,None,True,verify_evidence=lambda *args:evidence)

    def test_unknown_or_incomplete_caller_evidence_never_grants_acceptance(self):
        for callback in (None,lambda *args:True,lambda *args:{'approved':True}):
            with self.assertRaises(ValueError):r.population_recipe(5,None,None,verify_evidence=callback)
        for previous in (replace(self.previous,stage_index=4.0),replace(self.previous,completed_games=19999),
                         replace(self.previous,phase='development')):
            with self.assertRaises(ValueError):r.population_recipe(5,None,None,verify_evidence=lambda *args:previous)
        malformed=replace(self.previous.candidates[1],cells=self.previous.candidates[1].cells[:-1])
        previous=replace(self.previous,candidates=(self.previous.candidates[0],malformed,*self.previous.candidates[2:]))
        with self.assertRaises(ValueError):r.population_recipe(5,None,None,verify_evidence=lambda *args:previous)
        with self.assertRaises(ValueError):
            r._study(replace(self.study,completed_games=32767))

    def test_all64_dedup_attempts_preserved_on_failure_without_replacement(self):
        with patch.object(GenomeSpace,'mutate',side_effect=lambda parent,*args,**kwargs:dict(parent)):
            with self.assertRaisesRegex(ValueError,'All64') as caught:self.make()
        attempts=caught.exception.recipe_attempts
        self.assertEqual(len(attempts),64)
        self.assertEqual([row['attempt'] for row in attempts],list(range(64)))
        self.assertEqual(len({row['mutation_seed'] for row in attempts}),64)


class WholeSyntheticStageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog=synthetic_catalog();cls.digest=r.sha(cls.catalog)

    def test_full20k_metadata_preserves_schedule_domain_seeds_rival_specs_and_reserved_boundaries(self):
        with patch.object(r,'CATALOG_SHA256',self.digest),patch.object(contract,'ORIGINAL_CATALOG_SHA256',self.digest),\
                patch('tests.reference_engine.Game',side_effect=AssertionError('No Game may run')),\
                patch('evolution.oversight.make_actors',side_effect=AssertionError('No actor may run')):
            result=r.stage_recipe(self.catalog,5,tuple(r._references())+source_population()[1:6])
        payload=result['payload'];fixtures=payload['fixtures']
        self.assertEqual(len(fixtures),20000);self.assertEqual(len({row['map_id'] for row in fixtures}),100)
        self.assertEqual(Counter(row['candidate_slot'] for row in fixtures),{slot:2500 for slot in range(8)})
        self.assertEqual(payload['balance']['cell_min'],39);self.assertEqual(payload['balance']['cell_max'],40)
        self.assertEqual(len({r.rival_seed_blob(spec['seed']) for row in fixtures for spec in row['opponents']}),60000)
        for row in fixtures:
            schedule=contract.slot_schedule(row['map_index'],row['episode'])
            self.assertEqual((row['seat'],row['token'],row['field'],row['candidate_slot'],row['canonical_slot']),
                tuple(schedule[key] for key in ('seat','token','field','candidate_slot','canonical_slot')))
            self.assertEqual(Counter(spec['family'] for spec in row['opponents']),Counter(r.core.FIELDS[row['field']]))
            self.assertEqual(len(row['opponents']),3)
            for spec in row['opponents']:
                self.assertEqual(spec['seed'],contract.rival_seed(row['map_index'],row['episode'],spec['seat']))
                self.assertTrue(.01<=spec['epsilon']<=.45);self.assertTrue(.2<=spec['commitment']<=.95)
                without={key:value for key,value in spec.items() if key!='id'}
                self.assertEqual(spec['id'],contract.rival_identity(payload['version_id'],row['map_index'],row['episode'],spec['seat'],r.sha(r.canonical(without))))
        first=fixtures[0]
        for spec in first['opponents']:
            self.assertNotEqual(spec['seed'],r.domain_seed(payload['version_id'],'rival-genes',first['map_index'],first['episode'],spec['seat']))
        self.assertEqual(payload['primary_games_accepted'],0);self.assertEqual(payload['bmcts_audits'],0)
        self.assertFalse(payload['promoted'])
        for stage in (4,80,True):
            with self.assertRaises(ValueError):r.stage_recipe(self.catalog,stage,source_population())


if __name__=='__main__':unittest.main()
