"""Full synthetic metadata/cubes only; no actual outcomes, games or authorities."""
import copy
from itertools import combinations
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from deadline_campaign import design,train_report as t


class TrainReportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        parent=design.ROOT/'.cache'/'deadline-report-synthetic-tests'
        parent.mkdir(parents=True,exist_ok=True)
        cls.temp=tempfile.TemporaryDirectory(prefix='SYNTHETIC-NO-GAMES-',dir=parent)
        cls.directory=Path(cls.temp.name)
        cls.entries=[]
        for index,body in enumerate(design.initial_population()):
            path=cls.directory/('source-%d.py'%index);path.write_bytes(body)
            cls.entries.append(design.source_entry(path))
        fixtures=[]
        maps=[design.sha(('SYNTHETIC-MAP-%02d'%i).encode()) for i in range(16)]
        for m,map_id in enumerate(maps):
            for field in design.FIELDS:
                for seat in range(4):
                    for token in range(1,5):
                        for slot,entry in enumerate(cls.entries):
                            key=[m,field,seat,token,slot];ordinal=len(fixtures)
                            fixtures.append(dict(id=design.sha(design.canonical(['SYNTHETIC-FIXTURE',key])),
                                focal_actor_id=design.sha(design.canonical(['SYNTHETIC-FOCAL',key])),
                                phase='train',generation=0,map_id=map_id,map_index=500+m,
                                field=field,seat=seat,token=token,candidate_slot=slot,candidate=entry['sha256'],
                                opponents=[dict(seat=s,id=design.sha(design.canonical(['SYNTHETIC-RIVAL',key,s])),
                                    seed=2**96+4*ordinal+s) for s in range(4) if s!=seat]))
        cls.registration=dict(format=design.FORMAT,phase='train',generation=0,candidates=cls.entries,fixtures=fixtures,
            guards={str((design.ROOT/name).resolve()):digest for name,digest in t.source_pins().items()},
            protocol=dict(maps=16,candidates=8,fields=list(design.FIELDS),seat_token_crosses=16,complete_games=8192,
                opponent_instances=24576,matched_rival_streams=False),SYNTHETIC_NO_GAMES=True)
        ranking=[]
        for i,entry in enumerate(cls.entries):
            cube=[[(i*7+m*3+f*5)%97 for f in range(4)] for m in range(16)]
            total=sum(map(sum,cube));score=102400+i
            ranking.append(dict(sha256=entry['sha256'],games=1024,pairwise_numerator_sum=total,score_sum=score,
                mean_pairwise=total/2048,mean_score=score/1024,map_field_pw2=cube,
                fields={field:sum(row[f] for row in cube)/512 for f,field in enumerate(design.FIELDS)}))
        cls.aggregate=dict(maps=sorted(maps),games=8192,ranking=ranking)

    @classmethod
    def tearDownClass(cls): cls.temp.cleanup()

    def test_all28_source_lexical_contrasts_and_independent_full_bootstrap(self):
        import numpy as np
        result=t.report(self.registration,self.aggregate)
        expected=list(combinations(sorted(e['sha256'] for e in self.entries),2))
        self.assertEqual([(c['a'],c['b']) for c in result['contrasts']],expected)
        self.assertEqual(result['contrast_count'],28)
        self.assertFalse(result['winner_inferred']);self.assertFalse(result['promoted'])
        self.assertFalse(result['admission']['certifies_executed_games'])
        self.assertIn('independent actual rival streams',result['pairing'])
        self.assertEqual({a['metadata']['family'] for a in result['arms']},
                         {'e8-config','original-blocker','original-feint','public-memory-blocker'})
        self.assertTrue(all(a['metadata']['source_sha256']==expected_sha for a,expected_sha in
                            zip(result['arms'],sorted(e['sha256'] for e in self.entries))))
        # Independent per-map contrast first, then one complete20k-draw scalar
        # bootstrap; the implementation instead bootstraps all arm cubes first.
        indexed={r['sha256']:r for r in self.aggregate['ranking']};a,b=expected[0]
        permap=[sum(x-y for x,y in zip(left,right))/128
                for left,right in zip(indexed[a]['map_field_pw2'],indexed[b]['map_field_pw2'])]
        rng=np.random.default_rng(t.BASE_SEED)
        draws=rng.integers(0,16,size=(20000,16),dtype=np.int64)
        values=sorted(sum(permap[int(i)] for i in draw)/16 for draw in draws)
        contrast=result['contrasts'][0]
        self.assertEqual(contrast['mean_pairwise_delta'],sum(permap)/16)
        self.assertEqual(contrast['unadjusted_95_interval'],[values[499],values[19499]])
        self.assertEqual(contrast['descriptive_bonferroni28_95_interval'],[values[16],values[19981]])
        self.assertEqual(result['bootstrap']['shared_map_draws_sha256'],design.sha(draws.astype('<i8').tobytes()))
        self.assertEqual(result['bootstrap']['bonferroni28_order_statistics'],[16,19981])
        self.assertTrue(all('exploratory' in f['interpretation'] for c in result['contrasts'] for f in c['fields'].values()))

    def test_incomplete_duplicate_foreign_nonfinite_and_noninteger_data_rejected(self):
        changes=[lambda r,a:a.update(games=8191),lambda r,a:a['ranking'].pop(),
            lambda r,a:a['maps'].reverse(),lambda r,a:a['ranking'][0]['map_field_pw2'][0].__setitem__(0,True),
            lambda r,a:a['ranking'][0]['map_field_pw2'][0].__setitem__(0,97),
            lambda r,a:a['ranking'][0].update(mean_pairwise=float('nan')),
            lambda r,a:a['ranking'][0].update(pairwise_numerator_sum=0),
            lambda r,a:a['ranking'][0]['fields'].__setitem__('economic',-1),
            lambda r,a:r['fixtures'].pop(),lambda r,a:r.update(phase='development'),
            lambda r,a:r['protocol'].update(matched_rival_streams=True),
            lambda r,a:r['fixtures'][1]['opponents'][0].update(seed=r['fixtures'][0]['opponents'][0]['seed']),
            lambda r,a:r['guards'].__setitem__(str((design.ROOT/'deadline_campaign/train_report.py').resolve()),'0'*64),
            lambda r,a:r['candidates'][0].update(sha256='0'*64)]
        for change in changes:
            with self.subTest(change=change):
                r=copy.deepcopy(self.registration);a=copy.deepcopy(self.aggregate);change(r,a)
                with self.assertRaises(ValueError): t.report(r,a)

    def test_generation_separates_bootstrap_stream_without_changing_policy_inputs(self):
        r=copy.deepcopy(self.registration);r['generation']=1
        for f in r['fixtures']: f['generation']=1;f['map_index']+=16
        result=t.report(r,self.aggregate)
        self.assertEqual(result['bootstrap']['effective_seed'],t.BASE_SEED+1)
        import numpy as np
        draws=np.random.default_rng(t.BASE_SEED+1).integers(0,16,size=(20000,16),dtype=np.int64)
        self.assertEqual(result['bootstrap']['shared_map_draws_sha256'],design.sha(draws.astype('<i8').tobytes()))
        self.assertEqual(result['primary_campaign_credit'],0)

    def test_cli_requires_root_declaration_binds_receipt_and_never_overwrites(self):
        registration=self.directory/'registration.SYNTHETIC.json'
        registration.write_bytes(design.canonical(self.registration)+b'\n')
        payload=dict(phase='train',generation=0,registration_sha256=design.sha(registration.read_bytes()),
            original_games=8192,independently_regenerated_callbacks=8192*320,both_referees=True,promoted=False,
            original_primary_campaign_credit=0,completed_per_game_bmcts_audits=0,
            aggregate=self.aggregate)
        accepted=self.directory/'accepted.SYNTHETIC.json'
        accepted.write_bytes(design.canonical(dict(scope='acceptance',payload=payload,mac='SYNTHETIC-NOT-AUTHENTICATED'))+b'\n')
        output=self.directory/'report.SYNTHETIC.json'
        args=['--registration',str(registration),'--accepted-payload',str(accepted),'--output',str(output)]
        with self.assertRaises(SystemExit): t.main(args)
        with patch('builtins.print'): t.main(args+['--caller-root-admitted'])
        result=json.loads(output.read_bytes())
        self.assertTrue(result['caller_root_admitted_declaration'])
        self.assertIn('not authenticated',result['admission']['status'])
        with self.assertRaises(FileExistsError),patch('builtins.print'): t.main(args+['--caller-root-admitted'])
        payload['registration_sha256']='0'*64
        accepted.write_bytes(design.canonical(payload)+b'\n')
        with self.assertRaises(ValueError): t.main(args+['--caller-root-admitted'])


if __name__=='__main__': unittest.main()
