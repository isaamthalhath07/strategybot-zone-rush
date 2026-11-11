"""Independent metadata/synthetic arithmetic checks; zero played matches.

The real fixed catalog supplies map metadata only. No accepted/live outcome,
authority/key, controller, actor callback, referee or GPU is invoked here.
"""
from collections import Counter, defaultdict
import copy
from datetime import timedelta
from fractions import Fraction
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from deadline_campaign import budget, design, evaluation


def synthetic_scores(seat,pw2):
    own,rivals = ((0,[1,1,1]),(0,[0,1,1]),(1,[0,2,2]),(1,[0,1,2]),
                  (2,[0,1,3]),(2,[0,1,2]),(3,[0,1,2]))[pw2]
    values = iter(rivals)
    return [own if s==seat else next(values) for s in range(4)]


def synthetic_rows(registration,fn):
    rows=[]
    for f in registration['fixtures']:
        scores=synthetic_scores(f['seat'],fn(f))
        actual=sum(2 if scores[f['seat']]>v else 1 if scores[f['seat']]==v else 0
                   for s,v in enumerate(scores) if s!=f['seat'])
        rows.append(dict(fixture=f['id'],candidate=f['candidate'],map_id=f['map_id'],
            focal_seat=f['seat'],field=f['field'],opponent_ids=[s['id'] for s in f['opponents']],
            faults=[],scores=scores,focal_score=scores[f['seat']],focal_pw=actual/2))
    return rows


class IndependentDesignTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog=design.catalog()  # Exact catalog bytes/content, no game rows.
        cls.bodies=design.initial_population()
        parent=design.ROOT/'.cache'/'deadline-design-independent-synthetic'
        parent.mkdir(parents=True,exist_ok=True)
        cls.temp=tempfile.TemporaryDirectory(prefix='SYNTHETIC-SOURCE-ONLY-',dir=parent)
        cls.entries=[]
        for index,body in enumerate(cls.bodies):
            path=Path(cls.temp.name)/('synthetic-candidate-%d.py'%index)
            path.write_bytes(body)
            cls.entries.append(design.source_entry(path))
        cls.guards={str(design.ROOT/'deadline_campaign/design.py'):design.sha((design.ROOT/'deadline_campaign/design.py').read_bytes())}
        cls.train=design.cohort('train',0,cls.catalog[500:516],cls.entries,cls.guards)
        cls.dev=design.cohort('development',0,cls.catalog[8000:8001],cls.entries,cls.guards)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_full_real_catalog_train_crossing_and_all_fresh_streams(self):
        reg=self.train
        self.assertEqual(len(reg['fixtures']),8192)
        expected={(b['id'],field,seat,token,slot) for b in self.catalog[500:516]
                  for field in design.FIELDS for seat in range(4) for token in range(1,5) for slot in range(8)}
        actual={(f['map_id'],f['field'],f['seat'],f['token'],f['candidate_slot']) for f in reg['fixtures']}
        self.assertEqual(actual,expected)
        self.assertEqual(len({f['id'] for f in reg['fixtures']}),8192)
        self.assertEqual(len({f['focal_actor_id'] for f in reg['fixtures']}),8192)
        specs=[s for f in reg['fixtures'] for s in f['opponents']]
        self.assertEqual(len({s['id'] for s in specs}),24576)
        self.assertEqual(len({s['seed'] for s in specs}),24576)
        self.assertTrue(all(type(s['seed']) is int and 2**96<=s['seed']<2**128 for s in specs))
        self.assertEqual(len({s['seed'].to_bytes(16,'big') for s in specs}),24576)
        parameter_hashes=[]
        for f in reg['fixtures']:
            self.assertEqual({s['seat'] for s in f['opponents']},set(range(4))-{f['seat']})
            self.assertEqual(Counter(s['family'] for s in f['opponents']),Counter(design.core.FIELDS[f['field']]))
            for s in f['opponents']:
                self.assertTrue(.01<=s['epsilon']<=.45)
                self.assertTrue(.2<=s['commitment']<=.95)
                parameter_hashes.append(design.sha(design.canonical({k:v for k,v in s.items() if k not in ('id','seed')})))
        self.assertEqual(len(set(parameter_hashes)),len(parameter_hashes))
        self.assertFalse(reg['protocol']['matched_rival_streams'])
        self.assertEqual(reg['protocol']['primary_campaign_credit'],0)
        self.assertEqual(reg['protocol']['bmcts_credit'],0)

    def test_heldout_arms_share_exact_streams_but_have_distinct_instance_ids(self):
        grouped=defaultdict(list)
        for f in self.dev['fixtures']:
            grouped[(f['map_id'],f['field'],f['seat'],f['token'])].append(f)
        self.assertEqual(len(grouped),64)
        for group in grouped.values():
            self.assertEqual(len(group),8)
            canonical=lambda f:[{k:v for k,v in s.items() if k!='id'} for s in f['opponents']]
            self.assertTrue(all(canonical(f)==canonical(group[0]) for f in group))
            self.assertEqual(len({s['id'] for f in group for s in f['opponents']}),24)
            self.assertEqual(len({f['focal_actor_id'] for f in group}),8)
        train_seeds={s['seed'] for f in self.train['fixtures'] for s in f['opponents']}
        self.assertFalse(train_seeds & {s['seed'] for f in self.dev['fixtures'] for s in f['opponents']})

    def test_phase_catalog_and_candidate_bytes_are_not_caller_assertions(self):
        boards=copy.deepcopy(self.catalog[500:516])
        changed=copy.deepcopy(boards)
        changed[0]['base'][1]=1 if changed[0]['base'][1]!=1 else 2
        changed[0]['id']=design.sha(bytes(changed[0]['base']))
        with self.assertRaises(ValueError): design.cohort('train',0,changed,self.entries,self.guards)
        changed=copy.deepcopy(boards)
        changed[0]=copy.deepcopy(self.catalog[9000])
        changed[0].update(phase='train',map_index=500)
        with self.assertRaises(ValueError): design.cohort('train',0,changed,self.entries,self.guards)
        entries=copy.deepcopy(self.entries);entries[0]['sha256']='0'*64
        with self.assertRaises(ValueError): design.cohort('train',0,boards,entries,self.guards)
        with self.assertRaises(ValueError): design.cohort('development',1,self.catalog[8000:8001],self.entries,self.guards)
        with self.assertRaises(ValueError): design.cohort('train',True,boards,self.entries,self.guards)
        with self.assertRaises(ValueError): design.cohort('train',0,boards[:-1],self.entries,self.guards)
        with self.assertRaises(ValueError): design.cohort('train',0,self.catalog[499:515],self.entries,self.guards)

    def test_exact_structural_family_and_genotype_canonicalization(self):
        infos=[design.classify(body) for body in self.bodies]
        self.assertEqual([i['family'] for i in infos[:5]],
            ['e8-config','e8-config','original-blocker','original-feint','public-memory-blocker'])
        self.assertEqual(infos[4]['strategy_family'],'original-blocker')
        self.assertEqual(infos[2]['genes'],infos[4]['genes'])
        self.assertNotEqual(infos[2]['genotype_sha256'],infos[4]['genotype_sha256'])
        self.assertNotEqual(infos[0]['genotype_sha256'],infos[1]['genotype_sha256'])
        with self.assertRaises(ValueError): design.classify(self.bodies[4]+b'\n# Unregistered structural edit\n')
        with self.assertRaises(ValueError): design.validate_population(self.bodies[:7]+[self.bodies[0]],8)

    def test_complete_synthetic_rank_and_prospective_goal_control_then_template_inheritance(self):
        reg=self.train
        def outcome(f):
            # Explicitly synthetic metadata arithmetic; no policy has played.
            return 6 if f['candidate_slot']==4 else (f['candidate_slot']+design.FIELDS.index(f['field']))%6
        rows=synthetic_rows(reg,outcome)
        result=evaluation.aggregate(reg,rows)
        means={entry['sha256']:Fraction(sum(outcome(f) for f in reg['fixtures'] if f['candidate']==entry['sha256']),2048)
               for entry in self.entries}
        self.assertEqual(result['ranking'][0]['sha256'],self.entries[4]['sha256'])
        for row in result['ranking']:
            self.assertEqual(row['games'],1024)
            self.assertEqual(row['mean_pairwise'],float(means[row['sha256']]))
            self.assertEqual(len(row['map_field_pw2']),16)
        with self.assertRaises(ValueError): evaluation.aggregate(reg,rows[:-1])
        with self.assertRaises(ValueError): evaluation.aggregate(reg,rows+[rows[0]])
        bad=copy.deepcopy(rows);bad[0]['focal_pw']=float('nan')
        with self.assertRaises(ValueError): evaluation.aggregate(reg,bad)
        traced=[];original=design.child
        def child(parent,generation,family,attempt=0):
            traced.append((design.classify(parent)['family'],generation,family,attempt))
            return original(parent,generation,family,attempt)
        with patch.object(design,'child',side_effect=child):
            population=design.next_population(self.bodies,result['ranking'],1)
        self.assertEqual([design.sha(body) for body in population[:3]],list(design.REFERENCES))
        self.assertEqual(population[3],self.bodies[4])  # Mandatory same-generation f5 control.
        self.assertEqual(design.classify(population[6])['family'],'persistent-goal-public-memory-blocker')
        self.assertFalse(any(family=='original-blocker' for _,_,family,_ in traced))
        from deadline_strategy.goal_space import PersistentGoalTemplateSpace
        goal=PersistentGoalTemplateSpace()
        self.assertEqual(population[6],goal.export(goal.defaults))
        self.assertEqual(len(design.validate_population(population,8)),8)
        # Pure parent-routing fixtures, explicitly not admitted scientific ranks:
        # gen2 must preserve whichever Blocker structural template is ranked first.
        for chosen_family in ('public-memory-blocker','persistent-goal-public-memory-blocker'):
            ordered=sorted(population,key=lambda body:(design.classify(body)['family']!=chosen_family,design.sha(body)))
            synthetic_parent_order=[dict(sha256=design.sha(body)) for body in ordered]
            traced.clear()
            with patch.object(design,'child',side_effect=child):
                next_generation=design.next_population(population,synthetic_parent_order,2)
            self.assertIn((chosen_family,2,'original-blocker',0),traced)
            self.assertEqual(design.classify(next_generation[6])['family'],chosen_family)
        with self.assertRaises(ValueError): design.child(self.bodies[4],2,'original-feint')

    def test_budget_uses_full_pipeline_slowest_rate_and_reserves(self):
        records=[dict(games=256,wall_seconds=s,full_actor_audits=256,both_referees=True) for s in (25,32)]
        self.assertEqual(budget.conservative_rate(records),6.4)
        plan=budget.heldout_budget(records)
        self.assertEqual(plan['development_games'],plan['development_maps']*512)
        self.assertEqual(plan['final_games'],plan['final_maps']*128)
        self.assertGreaterEqual(plan['packaging_reserved_seconds'],2700)
        exact=budget.TRAIN_CUTOFF-timedelta(seconds=8192/6.4+120)
        self.assertTrue(budget.may_start_generation(exact,records,games=8192,coaching_and_setup_seconds=120))
        self.assertFalse(budget.may_start_generation(exact+timedelta(microseconds=1),records,games=8192,coaching_and_setup_seconds=120))
        bad=copy.deepcopy(records);bad[0]['score']=3
        with self.assertRaises(ValueError): budget.heldout_budget(bad)
        bad=copy.deepcopy(records);bad[0]['full_actor_audits']=255
        with self.assertRaises(ValueError): budget.heldout_budget(bad)

    def test_rank_ties_use_worst_field_then_score_then_hash(self):
        def outcome(f):
            if f['candidate_slot']==0:
                return (6,0,6,0)[design.FIELDS.index(f['field'])]
            return 3
        rows=synthetic_rows(self.dev,outcome)
        for row,f in zip(rows,self.dev['fixtures']):
            # Common score offset keeps every pairwise result unchanged.
            offset=100 if f['candidate_slot']==0 else 20 if f['candidate_slot']==1 else 10
            row['scores']=[s+offset for s in row['scores']]
            row['focal_score']=row['scores'][f['seat']]
        result=evaluation.aggregate(self.dev,rows)
        ranking=[r['sha256'] for r in result['ranking']]
        self.assertEqual(ranking[0],self.entries[1]['sha256'])
        self.assertEqual(ranking[-1],self.entries[0]['sha256'])
        self.assertEqual(ranking[1:-1],sorted(e['sha256'] for e in self.entries[2:]))
        self.assertTrue(all(r['mean_pairwise']==1.5 for r in result['ranking']))

    def test_frozen_final_rule_needs_overall_gain_and_every_field_noninferiority(self):
        maps=['SYNTHETIC-FINAL-MAP-%03d'%i for i in range(64)]
        def final(challenger,anchor):
            rows=[]
            for name,cube in (('challenger',challenger),('anchor',anchor)):
                rows.append(dict(sha256=name,games=4096,pairwise_numerator_sum=sum(map(sum,cube)),
                    score_sum=4096,mean_pairwise=sum(map(sum,cube))/8192,mean_score=1,
                    map_field_pw2=cube))
            return evaluation.final_decision(dict(maps=maps,games=8192,ranking=rows),'challenger','anchor')
        anchor=[[48]*4 for _ in maps]
        passed=final([[52]*4 for _ in maps],anchor)
        self.assertTrue(passed['promoted']);self.assertEqual(passed['selected'],'challenger')
        self.assertEqual(passed['overall_two_sided_95_percentile_interval'],[.125,.125])
        self.assertEqual(passed['bootstrap']['overall_order_statistics'],[499,19499])
        self.assertEqual(passed['bootstrap']['field_lower_order_statistic'],249)
        tied=final(anchor,anchor)
        self.assertFalse(tied['promoted']);self.assertEqual(tied['selected'],'anchor')
        field_loss=final([[45,60,60,60] for _ in maps],anchor)
        self.assertGreater(field_loss['mean_pairwise_delta'],0)
        self.assertFalse(field_loss['promoted']);self.assertEqual(field_loss['selected'],'anchor')


if __name__=='__main__': unittest.main()
