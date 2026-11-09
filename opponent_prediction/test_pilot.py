"""Pilot contract/arithmetic tests; zero real games, traces or actors consumed.

Only expensive accepted-data admission is mocked. All statistics, selection,
schema checks, public labels and sealed-file checks run normally on synthetic
metadata/losses. No primary, study or reserved outcome is opened or executed.
"""
import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from opponent_prediction import pilot
from primary_campaign import core
from search_coach.belief import PublicObservation


def facts(directory):
    grouped={field:[] for field in core.FIELDS}
    for f,field in enumerate(core.FIELDS):
        for i in range(8):
            fixture='SYNTHETIC_FIXTURE_%d_%d'%(f,i)
            grouped[field].append((pilot.sha(core.canonical(['unit',fixture])),i%5,fixture,'UNIT_MAP_%d_%d'%(f,i)))
    return dict(campaign_directory=str((directory/'synthetic-campaign').resolve()),campaign_id='UNIT_ONLY_ZERO_CREDIT',
                manifest_sha256='1'*64,catalog_sha256='2'*64,
                stages=[dict(generation=i,registration_sha256=str(i)*64,games_sha256='a'*64,actor_audits_sha256='b'*64) for i in range(5)],
                selected=pilot.select(grouped))


def synthetic_cases(protocol):
    cases=[]
    for i,case in enumerate(protocol['selected']):
        f=list(core.FIELDS).index(case['field'])
        shock=i+1
        values=dict(uniform=100+shock,mixture=20+shock,persistent=20+shock+f)
        cases.append(dict(case=copy.deepcopy(case),models={mode:dict(mean_nll=values[mode]) for mode in pilot.MODES}))
    return cases


def reseal(path,value):
    body=core.canonical(value)+b'\n'
    path.write_bytes(body)
    path.with_suffix('.sha256').write_text(pilot.sha(body)+'\n',encoding='ascii')


class PilotTests(unittest.TestCase):
    def setUp(self):
        cache=Path(pilot.__file__).resolve().parent/'.cache'
        cache.mkdir(exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(prefix='pilot-SYNTHETIC-',dir=cache)
        self.directory=Path(self.temp.name)
        self.source=facts(self.directory)

    def tearDown(self):
        self.temp.cleanup()

    def prepare(self):
        output=self.directory/'registration'
        with patch.object(pilot,'_facts',return_value=copy.deepcopy(self.source)) as admission:
            value=pilot.prepare(Path(self.source['campaign_directory']),output)
        self.assertEqual(admission.call_args.kwargs,{'deep':True})
        return output,value

    def test_exact_protocol_reconstruction_rejects_rehashed_claims_scopes_schedule_and_extra_keys(self):
        output,original=self.prepare()
        with patch.object(pilot,'_facts',return_value=copy.deepcopy(self.source)) as admission:
            self.assertEqual(pilot._validated(output),original)
            self.assertEqual(admission.call_args.kwargs,{'deep':False})
        changes=[('metric','accuracy instead of NLL'),('model_claim','certified calibrated opponents'),
                 ('primary_contrast','reverse direction'),('data_scope','fresh heldout confirmation'),
                 ('final_view','terminal turn81'),('selection','select best observed outcomes'),
                 ('failure_policy','drop unsupported cases'),('primary_games',False),('full_bmcts_audits',1),
                 ('promotion',True),('observation_steps',80),('unregistered_extra_claim','strongest bot')]
        for key,value in changes:
            bad=copy.deepcopy(original);bad[key]=value;reseal(output/'registration.json',bad)
            with (self.subTest(key=key),patch.object(pilot,'_facts',return_value=copy.deepcopy(self.source)),
                  self.assertRaisesRegex(ValueError,'Exact preregistered')):pilot._validated(output)
        for key,value in [('unit','pooled field mixture'),('scope','simultaneous95% proof'),('seed',1),
                          ('replicates',100),('algorithm','outcome selected seed'),('quantile_indices',[0,19999])]:
            bad=copy.deepcopy(original);bad['bootstrap'][key]=value;reseal(output/'registration.json',bad)
            with (self.subTest(bootstrap=key),patch.object(pilot,'_facts',return_value=copy.deepcopy(self.source)),
                  self.assertRaisesRegex(ValueError,'Exact preregistered')):pilot._validated(output)
        bad=copy.deepcopy(original);bad['selected'][0]['map_id']='REASSIGNED';reseal(output/'registration.json',bad)
        with (patch.object(pilot,'_facts',return_value=copy.deepcopy(self.source)),self.assertRaises(ValueError)):
            pilot._validated(output)

    def test_selector_is_order_independent_has_four_fields_and_never_reuses_a_map(self):
        grouped={field:[('0',0,field+'-shared','shared')]+[(str(i+1),i,field+str(i),field+'-map'+str(i)) for i in range(8)]
                 for field in core.FIELDS}
        first=pilot.select(copy.deepcopy(grouped))
        second=pilot.select({field:list(reversed(values)) for field,values in grouped.items()})
        self.assertEqual(first,second)
        self.assertEqual(len({row['map_id'] for row in first}),16)
        self.assertEqual([row['field'] for row in first],list(core.FIELDS)*4)
        with self.assertRaisesRegex(ValueError,'Insufficient distinct'):
            pilot.select({field:[('0',0,field,'same-map')] for field in core.FIELDS})

    def test_stratified_shared_map_bootstrap_preserves_field_weights_and_registered_case_order(self):
        _,protocol=self.prepare()
        cases=synthetic_cases(protocol)
        forward=pilot._statistics(cases,protocol)
        reverse=pilot._statistics(list(reversed(cases)),protocol)
        self.assertEqual(forward,reverse)
        self.assertEqual([c['case'] for c in forward[0]],protocol['selected'])
        # Within each field the contrast is fixed despite common map shocks.
        # A pooled bootstrap would vary the number of draws from each field.
        contrasts=forward[2]
        expected=[1.5,-78.5,-80.0]
        for row,value in zip(contrasts,expected):
            self.assertEqual(row['mean_delta_nll'],value)
            self.assertEqual(row['descriptive95_interval'],[value,value])
        self.assertEqual(len(forward[3]),64)

    def test_partial_duplicate_nonfinite_or_reassigned_cases_never_emit_partial_statistics(self):
        _,protocol=self.prepare()
        cases=synthetic_cases(protocol)
        corrupt=[cases[:-1],cases[:-1]+[cases[0]]]
        bad=copy.deepcopy(cases);bad[0]['models']['uniform']['mean_nll']=float('nan');corrupt.append(bad)
        bad=copy.deepcopy(cases);bad[0]['case']['field']='wrong-field';corrupt.append(bad)
        bad=copy.deepcopy(cases);del bad[0]['models']['uniform'];corrupt.append(bad)
        for bad in corrupt:
            with self.assertRaises(ValueError):pilot._statistics(bad,protocol)

    def test_published_snapshot_cannot_be_replaced_by_rehashed_duplicate_stage_claim(self):
        snapshot=self.directory/'fake-published-snapshot.json'
        snapshot.write_bytes(b'{}')
        with patch.object(pilot,'SNAPSHOT',snapshot),self.assertRaisesRegex(ValueError,'snapshot changed'):
            pilot._snapshot()
        fake=dict(primary_games_accepted=100000,callbacks_regenerated=32000000,bmcts_audits=0,promoted=False,
                  stages=[dict(generation=0,primary_games_accepted=20000,callbacks_regenerated=6400000)]*5)
        body=core.canonical(fake);snapshot.write_bytes(body)
        with (patch.object(pilot,'SNAPSHOT',snapshot),patch.object(pilot,'SNAPSHOT_SHA256',pilot.sha(body)),
              self.assertRaisesRegex(ValueError,'five distinct')):pilot._snapshot()

    def test_public_exploratory_labels_exclude_own_intrusion_and_require_prior_nonfrozen_rival(self):
        cells=[[0,0,False,False,False,1] for _ in range(64)]
        for seat,pos in enumerate((0,7,63,56),1):cells[pos]=[seat,seat,False,True,False,1]
        cells[7][0]=0;cells[6]=[2,1,False,False,False,1]
        cells[63][4]=True;cells[56][4]=True
        obs=PublicObservation(tuple(tuple(c) for c in cells),1,True,('STAY',))
        context=pilot._public_context(obs,20)
        self.assertTrue(context['public_shield_opportunity_proxy']);self.assertFalse(context['all_rivals_frozen'])
        self.assertEqual(context['turn_bin'],'turn_01_20')
        cells[6][4]=True
        obs=PublicObservation(tuple(tuple(c) for c in cells),1,True,('STAY',))
        context=pilot._public_context(obs,21)
        self.assertFalse(context['public_shield_opportunity_proxy']);self.assertTrue(context['all_rivals_frozen'])
        self.assertEqual(context['turn_bin'],'turn_21_40')
        with self.assertRaises(ValueError):pilot._public_context(obs,80)

    def test_exploratory_counts_cover_79_steps_and_report_empty_slices_without_inference_claims(self):
        cells=tuple((0,0,False,False,False,1) for _ in range(64))
        mutable=list(cells)
        for seat,pos in enumerate((0,7,63,56),1):mutable[pos]=(seat,seat,False,True,False,1)
        obs=PublicObservation(tuple(mutable),1,True,('STAY',))
        contexts=[pilot._public_context(obs,t) for t in range(1,80)]
        case=dict(public_context=contexts,models={mode:dict(trace=[{'log_predictive_probability':-2.0}]*79) for mode in pilot.MODES})
        result=pilot._exploratory([case])
        self.assertEqual([result[name]['events'] for name in ('turn_01_20','turn_21_40','turn_41_60','turn_61_79')],[20,20,20,19])
        self.assertEqual(result['public_intrusion_no']['events'],79)
        self.assertEqual(result['public_intrusion_yes']['events'],0)
        self.assertIsNone(result['public_intrusion_yes']['models']['persistent']['mean_nll'])
        self.assertEqual(result['turn_61_79']['models']['mixture']['mean_nll'],2.0)


if __name__=='__main__':unittest.main()
