"""Metadata and synthetic admission tests only; zero actor/CUDA/game calls."""
import copy
from datetime import timedelta
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from . import experiment as e,maps


class FakeAuthority:
    def __init__(self,campaign):
        self.campaign=campaign;self.manifest_sha256=e.sha((campaign/'manifest.json').read_bytes());self.records={}
    def seal(self,scope,payload,path):
        path=Path(path)
        if not path.is_absolute(): path=self.campaign/path
        key=(scope,str(path));self.records[key]=copy.deepcopy(payload)
        path.parent.mkdir(parents=True,exist_ok=True)
        with path.open('xb') as stream: stream.write(e.canonical({'scope':scope,'payload':payload})+b'\n')
    def read(self,scope,path):
        path=Path(path)
        if not path.is_absolute(): path=self.campaign/path
        return copy.deepcopy(self.records[(scope,str(path))])


def measurement(seconds=100):
    return dict(games=512,wall_seconds=seconds,full_actor_audits=512,both_referees=True)


def rows_for(reg,challenger_pw2=6,anchor_pw2=0,pressure_pw2=None):
    rows=[]
    for f in reg['fixtures']:
        pw=challenger_pw2 if f['candidate_slot']==0 else anchor_pw2
        if f['candidate_slot']==0 and f['field']=='pressure' and pressure_pw2 is not None: pw=pressure_pw2
        values=[0]*(pw//2)+([10] if pw%2 else [])+[20]*(3-pw//2-pw%2)
        scores=[];iterator=iter(values)
        for seat in range(4): scores.append(10 if seat==f['seat'] else next(iterator))
        rows.append(dict(fixture=f['id'],candidate=f['candidate'],map_id=f['map_id'],focal_seat=f['seat'],field=f['field'],
            opponent_ids=[s['id'] for s in f['opponents']],faults=[],scores=scores,focal_score=10,focal_pw=pw/2))
    return rows


class OfficialTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.maps=maps.validate(e.MAPS)
        temporary=e.ROOT/'deadline_official_check/.t';temporary.mkdir(exist_ok=True)
        cls.temp=tempfile.TemporaryDirectory(prefix='o',dir=temporary);cls.addClassCleanup(cls.temp.cleanup)
        cls.root=Path(cls.temp.name);chosen=cls.root/'synthetic.py';chosen.write_bytes(b'def act(s):\n return "STAY"\n')
        cls.chosen=dict(path=str(chosen),sha256=e.sha(chosen.read_bytes()))
        cls.entries=[cls.chosen,dict(path=str(e.ROOT/'bot.py'),sha256=e.E8)]
        cls.reg=e.registration(cls.maps['maps'],cls.entries,{'synthetic': '0'*64})

    def test_frozen64_generator_metadata_and_complete_exclusions(self):
        value=self.maps;self.assertEqual(len(value['maps']),64);self.assertEqual(len(value['selection_ledger']),113)
        self.assertEqual(value['exclusions']['unique_rotation_orbits'],10218)
        generate=maps.generator();excluded,proof=maps.exclusions()
        self.assertTrue({b['rotation_orbit'] for b in value['maps']}.isdisjoint(excluded))
        self.assertEqual(len({b['rotation_orbit'] for b in value['maps']}),64)
        for b in value['maps']:
            self.assertEqual(b['base'],generate(b['seed']));self.assertLessEqual(b['base'][0],2)
            for r in range(8):
                for c in range(8): self.assertEqual(b['base'][r*8+c],b['base'][r*8+7-c])
        self.assertEqual({p['unique_rotation_orbits'] for p in proof['inputs'][:2]},{10000,128})
        self.assertTrue(all(v==0 for v in (value['executed_games'],value['primary_campaign_credit'],value['bmcts_credit'])))

    def test_all8192_exact_cells_and_fresh_matched_rival_streams(self):
        reg=self.reg;self.assertEqual(len(reg['fixtures']),8192)
        self.assertEqual(len({f['id'] for f in reg['fixtures']}),8192)
        self.assertEqual(len({r['id'] for f in reg['fixtures'] for r in f['opponents']}),8192*3)
        cells={(f['map_index'],f['field'],f['seat'],f['token'],f['candidate_slot']) for f in reg['fixtures']}
        self.assertEqual(len(cells),8192)
        for first,second in zip(reg['fixtures'][::2],reg['fixtures'][1::2]):
            self.assertEqual(first['rival_map_coordinate'],12000+first['map_index'])
            self.assertEqual([{k:v for k,v in r.items() if k!='id'} for r in first['opponents']],
                             [{k:v for k,v in r.items() if k!='id'} for r in second['opponents']])
            self.assertNotEqual(first['focal_actor_id'],second['focal_actor_id'])
            self.assertEqual(first['map_origin'],'fresh_official_generator_not_primary_catalog')
        self.assertEqual(reg['role'],e.ROLE)
        self.assertEqual({k:v['sha256'] for k,v in reg['sources'].items()},e.RIVALS)

    def test_whole64_map_gate_and_single_field_safety_failure(self):
        success,aggregated=e.endpoint(self.reg,rows_for(self.reg));self.assertTrue(success['promoted'])
        self.assertEqual(success['selected'],self.chosen['sha256']);self.assertEqual(success['mean_pairwise_delta'],3)
        self.assertEqual(success['overall_two_sided_95_percentile_interval'],[3,3])
        self.assertEqual(success['bootstrap']['overall_order_statistics'],[499,19499])
        self.assertEqual(success['bootstrap']['field_lower_order_statistic'],249)
        # Strong overall gain cannot rescue one clearly inferior field.
        unsafe,_=e.endpoint(self.reg,rows_for(self.reg,challenger_pw2=6,anchor_pw2=1,pressure_pw2=0))
        self.assertGreater(unsafe['mean_pairwise_delta'],0);self.assertFalse(unsafe['promoted']);self.assertEqual(unsafe['selected'],e.E8)
        tie,_=e.endpoint(self.reg,rows_for(self.reg,challenger_pw2=2,anchor_pw2=2));self.assertFalse(tie['promoted'])
        self.assertEqual(aggregated['games'],8192);self.assertEqual(len(aggregated['maps']),64)

    def test_partial_duplicate_and_changed_score_pairwise_cannot_reach_endpoint(self):
        rows=rows_for(self.reg)
        for bad in (rows[:-1],rows+[rows[0]],rows[:-1]+[rows[0]]):
            with self.assertRaises(ValueError): e.endpoint(self.reg,bad)
        rows[0]['focal_pw']=0
        with self.assertRaises(ValueError): e.endpoint(self.reg,rows)

    def test_timing_only_fixed_volume_boundary_and_no_redundant_e8(self):
        rate=512/100*.8;seconds=8192/rate+600+900;boundary=e.CUTOFF-timedelta(seconds=seconds)
        result=e.availability(boundary,self.chosen['sha256'],[measurement()]);self.assertEqual(result['status'],'available')
        self.assertEqual(result['headroom_seconds'],600);self.assertEqual(result['primary_proof_headroom_seconds'],900)
        self.assertEqual(result['total_reserved_seconds'],1500)
        self.assertEqual(e.availability(boundary+timedelta(microseconds=1),self.chosen['sha256'],[measurement()])['status'],'unavailable')
        self.assertEqual(e.availability(e.CUTOFF+timedelta(days=1),e.E8,[])['planned_games'],0)
        with self.assertRaises(ValueError): e.availability(boundary.replace(tzinfo=None),self.chosen['sha256'],[measurement()])
        with self.assertRaises(ValueError): e.availability(boundary,self.chosen['sha256'],[dict(measurement(),both_referees=False)])

    def test_atomic_execution_claim_and_same_interruption_preserved_with_e8_fallback(self):
        directory=self.root/'interruption';directory.mkdir();campaign=self.root/'owner';campaign.mkdir()
        e.frozen._seal(campaign/'manifest.json',dict(source_sha256={}))
        authority=FakeAuthority(campaign)
        e.frozen._seal(directory/'plan.json',dict(synthetic=True));e.frozen._seal(directory/'prepared.json',dict(synthetic=True))
        e.frozen._seal(directory/'registration.json',dict(synthetic=True))
        configuration=dict(batch_size=128,workers=8,audit_workers=4)
        prepared=dict(measurements=[measurement(1)],timing_receipts=[],execution_configuration=configuration)
        fault=KeyboardInterrupt('synthetic actor pipeline interruption');calls=[]
        def fail(*args,**kwargs):
            calls.append(1);e.frozen._seal(directory/'partial_original_evidence.json',dict(attempted_callbacks=7));raise fault
        context=(campaign,directory,dict(source_sha256={}),prepared,self.reg,'b'*64)
        with patch.object(e,'_registered',return_value=context),patch.object(e,'_timings',return_value=([measurement(1)],[],configuration)),\
             patch.object(e,'now',return_value=e.CUTOFF-timedelta(hours=1)),patch.object(e.runner,'run_fixtures',side_effect=fail):
            with self.assertRaises(KeyboardInterrupt) as caught: e.execute(campaign,authority)
            self.assertIs(caught.exception,fault)
            with self.assertRaises((FileExistsError,ValueError)): e.execute(campaign,authority)
        self.assertEqual(len(calls),1)
        decision=authority.read('final-decision',directory/'release_decision.json')
        self.assertEqual(decision['selected'],e.E8);self.assertEqual(decision['status'],'failed_or_incomplete')
        self.assertEqual(decision['official_games'],0);self.assertTrue((directory/'partial_original_evidence.json').exists())

    def test_registration_rejects_identical_arm_or_unpinned_source(self):
        with self.assertRaises(ValueError): e.registration(self.maps['maps'],[self.entries[1],self.entries[1]],{})
        bad=copy.deepcopy(self.entries);bad[0]['sha256']='0'*64
        with self.assertRaises(ValueError): e.registration(self.maps['maps'],bad,{})
        with self.assertRaises(ValueError): e.registration(self.maps['maps'][:-1],self.entries,{})


if __name__=='__main__': unittest.main()
