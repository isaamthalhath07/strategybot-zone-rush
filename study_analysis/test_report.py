"""Synthetic arithmetic/authentication tests. ZERO real games or actor calls.

The signed fixture is a deliberately fake isolated unit authority. Its source
registration digest/validator are patched ONLY in these tests. No actual V2
result, gold case, acceptance pointer or real owner registry is read or written.
"""
import copy
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from confirmation_campaign import architectures
from distributed_campaign import auth, protocol as p
from primary_campaign import core
from . import report as r


def digest(value):
    return p.sha(p.canonical(value))


def write_sealed(path, value):
    body = p.canonical(value)+b'\n'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(body)
    path.with_suffix('.sha256').write_text(p.sha(body)+'\n', encoding='ascii')
    return p.sha(body)


def synthetic_design():
    arms, fields = list(architectures.ARMS), list(core.FIELDS)
    maps = [dict(id=digest(['UNIT_ONLY_NOT_A_REAL_MAP', m])) for m in range(128)]
    fixtures = []
    for m, board in enumerate(maps):
        for field in fields:
            for seat in range(4):
                for token in range(1, 5):
                    pair = digest(['SYNTHETIC_ZERO_GAMES', m, field, seat, token])
                    for a, candidate in enumerate(arms):
                        fixture = dict(id=digest([pair,a]), map_id=board['id'], candidate=candidate, field=field,
                                       seat=seat, token=token, pair_key=pair, parent_pair_id=pair,
                                       focal_actor_id=digest([pair,a,'focal']),
                                       opponents=[dict(seat=i, family='unit_stub', seed=i, id=digest([pair,a,i])) for i in range(4) if i != seat])
                        fixtures.append(fixture)
    return dict(format=architectures.FORMAT, role='extra_control_assignment', phase='architecture_confirmation',
                generation=0, campaign_id=digest('SYNTHETIC_UNIT_ONLY_ZERO_REAL_GAME_CREDIT'),
                protocol=dict(fields=fields, inference=architectures.inference_plan()),
                planned_games=32768, maps=maps, fixtures=fixtures,
                candidates=[dict(name='unit_arm_'+str(i),sha256=arm) for i,arm in enumerate(arms)])


def synthetic_row(fixture, arm_index=0, map_index=0):
    own = ([40,25,15,0] if map_index%2 == 0 else [0,15,25,40])[arm_index]
    scores, rival = [], iter((10,20,30))
    for i in range(4):
        scores.append(own if i == fixture['seat'] else next(rival))
    pw2 = sum(2 if own>x else 1 if own==x else 0 for i,x in enumerate(scores) if i != fixture['seat'])
    return dict(candidate=fixture['candidate'], fixture=fixture['id'], map_id=fixture['map_id'],
                focal_seat=fixture['seat'], field=fixture['field'], scores=scores, focal_score=own, focal_pw=pw2/2,
                opponent_ids=[s['id'] for s in fixture['opponents']], actions=[['STAY']*4]*80,
                timing=[dict(calls=80,total_ms=80.0,max_ms=1.0,first_ms=1.0,regular_max_ms=1.0) for _ in range(4)],
                faults=[], elapsed_s=.002)


class ArithmeticTests(unittest.TestCase):
    def test_shared_map_draws_cancel_common_map_difficulty_exactly(self):
        cube = [[[16*v]*4 for v in values] for values in ((4,3,2,1),(5,4,3,2))]
        comparisons, bootstrap = r._bootstrap(cube, architectures.inference_plan())
        self.assertEqual(len(comparisons), 6)
        for result in comparisons:
            i, j = architectures.ARMS.index(result['first']), architectures.ARMS.index(result['second'])
            expected = r._fraction(j-i, 2)
            self.assertEqual(result['mean_pairwise_difference'], expected)
            self.assertEqual(result['descriptive_bonferroni_interval'], [expected,expected])
        self.assertEqual(bootstrap['replicates'],60000)
        self.assertEqual(bootstrap['percentile_indices_zero_based'],[249,59749])
        self.assertTrue(bootstrap['shared_map_draws_for_all_six'])

    def test_anticorrelated_maps_give_known_tail_endpoints_and_exact_zero_mean(self):
        cube = [[[16*v]*4 for v in values] for values in ((6,4,2,0),(0,2,4,6))]
        comparisons, _ = r._bootstrap(cube, architectures.inference_plan())
        for result in comparisons:
            i,j = architectures.ARMS.index(result['first']),architectures.ARMS.index(result['second'])
            self.assertEqual(result['mean_pairwise_difference'],r._fraction(0,1))
            self.assertEqual(result['descriptive_bonferroni_interval'],[r._fraction(i-j,1),r._fraction(j-i,1)])
        with self.assertRaisesRegex(ValueError,'plan changed'):
            r._bootstrap(cube,dict(architectures.inference_plan(),bootstrap_replicates=100))

    def test_worst_field_definitions_are_distinct_and_all_fields_reported(self):
        # A's worst field and B's worst field occur in different fields.
        cube = [[[0,96,96,96],[32,0,32,32],[16]*4,[0]*4]]*2
        comparisons,_ = r._bootstrap(cube,architectures.inference_plan())
        ab = comparisons[0]
        self.assertEqual(ab['worst_field_mean_difference'],r._fraction(0,1))
        self.assertEqual(ab['minimum_paired_field_difference'],r._fraction(-1,1))
        self.assertEqual(set(ab['field_mean_differences']),set(core.FIELDS))


class AcceptedReportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cache = core.ROOT/'.cache/distributed_campaign'
        cache.mkdir(parents=True,exist_ok=True)
        cls.temporary = tempfile.TemporaryDirectory(prefix='study-analysis-SYNTHETIC-',dir=cache)
        cls.root = Path(cls.temporary.name)
        cls.meta = auth.provision(cls.root/'private',{'unit_owner':'UNIT_ONLY_NOT_A_PHYSICAL_WORKER'})
        cls.registry = auth.load_registry(cls.meta['registry_path'])
        cls.registration = synthetic_design()
        cls.registration_path = cls.root/'study/registration.json'
        cls.reg_sha = write_sealed(cls.registration_path,cls.registration)
        cls.directory = cls.root/'controller'
        cls.directory.mkdir()
        cls.game_path = cls.directory/'games.jsonl'
        sha = hashlib.sha256()
        arm_i = {arm:i for i,arm in enumerate(architectures.ARMS)}
        map_i = {item['id']:i for i,item in enumerate(cls.registration['maps'])}
        with cls.game_path.open('wb') as out:
            for fixture in cls.registration['fixtures']:
                line=p.canonical(synthetic_row(fixture,arm_i[fixture['candidate']],map_i[fixture['map_id']]))+b'\n'
                sha.update(line);out.write(line)
        cls.game_sha = sha.hexdigest()
        cls.plan = dict(format=p.FORMAT,role='extra_control_assignment',campaign_id=cls.registration['campaign_id'],generation=0,
                        source_registration_path=str(cls.registration_path.resolve()),source_registration_sha256=cls.reg_sha,
                        registry_path=cls.meta['registry_path'],planned_extra_games=32768,primary_games_accepted=0,bmcts_audits=0,
                        production_promotion=False,helpers=['unit_owner'],owner_runtime={'unit_only':True},
                        trust_model='SYNTHETIC UNIT TEST AUTHORITY; ZERO REAL GAMES')
        plan_sha=write_sealed(cls.directory/'plan.json',auth.sign_owner(cls.registry,'distributed-control-plan/v2',cls.plan))
        cls.binding=dict(source_registration_path=str(cls.registration_path.resolve()),source_registration_sha256=cls.reg_sha,
                         canonical_output=str(cls.directory.resolve()),helpers=['unit_owner'],registry_path=cls.meta['registry_path'],
                         role='extra_control_assignment',rule='One owner-issued original-game cohort per frozen study; alternate outputs cannot resubmit it.')
        cls.canonical=cls.registration_path.parent/'distributed_control_v2'
        write_sealed(cls.canonical/'binding.json',auth.sign_owner(cls.registry,'distributed-control-study-binding/v2',cls.binding))
        cls.accepted=dict(format=p.FORMAT,role='extra_control_assignment',campaign_id=cls.registration['campaign_id'],approved=True,
                          actual_extra_games=32768,primary_games_accepted=0,bmcts_audits=0,study_registration_sha256=cls.reg_sha,
                          plan_sha256=plan_sha,audit_plan_sha256='f'*64,games_sha256=cls.game_sha,
                          remote_full_actor_callbacks=32768*320,remote_public_memory_oracles=0,
                          owner_canary_games=8,owner_canary_callbacks=2560,all_original_rows_physically_replayed=True,
                          all_actual_original_rows_have_different_slot_peer_audit=True,gold_study_cases_counted_once=8,
                          qualification_replica_games_credited=0,production_promoted=False,
                          trust_model='SYNTHETIC UNIT TEST AUTHORITY; ZERO REAL GAMES')
        cls._restore()

    @classmethod
    def _restore(cls):
        accepted_sha=write_sealed(cls.directory/'acceptance.json',auth.sign_owner(cls.registry,'distributed-control-acceptance/v2',cls.accepted))
        cls.pointer=dict(canonical_output=str(cls.directory.resolve()),acceptance_sha256=accepted_sha,
                         source_registration_sha256=cls.reg_sha,actual_extra_games=32768,primary_games_accepted=0)
        write_sealed(cls.canonical/'acceptance.json',auth.sign_owner(cls.registry,'distributed-control-study-acceptance/v2',cls.pointer))

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def setUp(self):
        self.patches=[patch.object(r,'REGISTRATION_SHA256',self.reg_sha),patch.object(architectures,'validate',return_value=True)]
        for item in self.patches:item.start()

    def tearDown(self):
        self._restore()
        for item in reversed(self.patches):item.stop()

    def context(self):
        return r._context(self.registration_path,self.meta['registry_path'])

    def test_complete_synthetic_acceptance_reports_all_arms_fields_and_six_contrasts(self):
        with (patch('evolution.runner.play_game',side_effect=AssertionError('NO ACTORS')),
              patch('primary_campaign.run.audit_task',side_effect=AssertionError('NO AUDIT'))):
            result=r.analyze(self.registration_path,self.meta['registry_path'])
        self.assertEqual(result['coverage']['unique_games'],32768)
        self.assertEqual(len(result['arms']),4);self.assertEqual(len(result['comparisons']),6)
        for arm in result['arms']:
            self.assertEqual(arm['games'],8192)
            self.assertEqual(arm['mean_pairwise'],r._fraction(3,2))
            self.assertEqual(len(arm['fields']),4)
            self.assertEqual(arm['faults'],0)
            self.assertEqual(arm['timing']['focal_calls'],8192*80)
        self.assertEqual(result['new_games_executed'],0)
        self.assertEqual(result['primary_match_credit'],0)
        self.assertFalse(result['promoted'])
        serialized=json.dumps(result)
        self.assertNotIn('owner_key',serialized);self.assertNotIn('"mac":',serialized)

    def test_authenticated_but_partial_wrong_role_counting_or_assurance_refuses_ranking(self):
        mutations=[('actual_extra_games',8),('primary_games_accepted',1),('approved',False),('role','primary_assignment'),
                   ('bmcts_audits',1),('production_promoted',True),('remote_full_actor_callbacks',32768*320-1),
                   ('all_actual_original_rows_have_different_slot_peer_audit',False),('qualification_replica_games_credited',8)]
        for key,value in mutations:
            accepted=dict(self.accepted,**{key:value})
            sha=write_sealed(self.directory/'acceptance.json',auth.sign_owner(self.registry,'distributed-control-acceptance/v2',accepted))
            pointer=dict(self.pointer,acceptance_sha256=sha)
            write_sealed(self.canonical/'acceptance.json',auth.sign_owner(self.registry,'distributed-control-study-acceptance/v2',pointer))
            with (self.subTest(key=key),patch.object(r,'_bootstrap',side_effect=AssertionError('PARTIAL RANKING')),
                  self.assertRaises(ValueError)):r.analyze(self.registration_path,self.meta['registry_path'])
            self._restore()

    def test_foreign_owner_wrong_purpose_or_modified_pointer_fails_authentication(self):
        body=json.loads((self.canonical/'acceptance.json').read_text())
        body['payload']['actual_extra_games']=8
        write_sealed(self.canonical/'acceptance.json',body)
        with self.assertRaises(auth.AuthUnavailable):self.context()
        write_sealed(self.canonical/'acceptance.json',auth.sign_owner(self.registry,'distributed-control-acceptance/v2',self.pointer))
        with self.assertRaises(auth.AuthUnavailable):self.context()
        self._restore()
        foreign=auth.provision(self.root/'foreign-private',{'other_owner':'UNIT_ONLY_OTHER_AUTHORITY'})
        with self.assertRaises(auth.AuthUnavailable):r._context(self.registration_path,foreign['registry_path'])

    def test_absent_acceptance_refuses_before_reading_any_outcomes_or_bootstrap(self):
        with (patch.object(r,'_collect',side_effect=AssertionError('OUTCOMES OPENED')),
              patch.object(r,'_bootstrap',side_effect=AssertionError('PARTIAL RANKING')),
              self.assertRaises(FileNotFoundError)):
            r.analyze(self.root/'missing-study/registration.json',self.meta['registry_path'])

    def test_foreign_source_pointer_hash_or_canonical_binding_refuses_report(self):
        bad=dict(self.pointer,acceptance_sha256='0'*64)
        write_sealed(self.canonical/'acceptance.json',auth.sign_owner(self.registry,'distributed-control-study-acceptance/v2',bad))
        with self.assertRaisesRegex(ValueError,'pointer changed'):self.context()
        self._restore()
        bad=dict(self.binding,canonical_output=str(self.root/'other'))
        write_sealed(self.canonical/'binding.json',auth.sign_owner(self.registry,'distributed-control-study-binding/v2',bad))
        try:
            with self.assertRaisesRegex(ValueError,'binding'):self.context()
        finally:write_sealed(self.canonical/'binding.json',auth.sign_owner(self.registry,'distributed-control-study-binding/v2',self.binding))

    def test_duplicate_changed_source_rank_fault_or_timing_rows_rejected(self):
        fixture=self.registration['fixtures'][0]
        row=synthetic_row(fixture)
        for key,value in [('candidate',architectures.ARMS[1]),('focal_pw',.5),('faults',['unit fault']),
                          ('scores',[True,1,2,3]),('actions',[['STAY']*4]*79),('elapsed_s',float('inf'))]:
            with self.subTest(key=key),self.assertRaises(ValueError):r._row(dict(row,**{key:value}),fixture)
        invalid=copy.deepcopy(row);invalid['timing'][0]['regular_max_ms']=201
        with self.assertRaises(ValueError):r._row(invalid,fixture)
        small=self.root/'tiny.jsonl'
        line=p.canonical(row)+b'\n'
        small.write_bytes(line*2)
        with self.assertRaisesRegex(ValueError,'Duplicate'):
            r._collect(small,r._design(self.registration),p.sha(line*2))
        small.write_bytes(line)
        with self.assertRaisesRegex(ValueError,'Complete unique'):
            r._collect(small,r._design(self.registration),p.sha(line))
        with self.assertRaisesRegex(ValueError,'hash changed'):
            r._collect(small,r._design(self.registration),'0'*64)

    def test_score_ties_produce_exact_half_points_instead_of_score_margin(self):
        fixture=self.registration['fixtures'][0]
        row=synthetic_row(fixture)
        row.update(scores=[10,10,20,30],focal_score=10,focal_pw=.5)
        self.assertEqual(r._row(row,fixture),1)
        bucket=r.Bucket();bucket.add(row,1)
        self.assertEqual(bucket.summary()['mean_pairwise'],r._fraction(1,2))
        row.update(scores=[20,10,20,30],focal_score=20,focal_pw=1.5)
        self.assertEqual(r._row(row,fixture),3)

    def test_registration_or_statistical_protocol_corruption_is_not_repaired(self):
        bad=copy.deepcopy(self.registration);bad['protocol']['inference']['bootstrap_seed']+=1
        with self.assertRaisesRegex(ValueError,'inference plan'):r._design(bad)
        bad=copy.deepcopy(self.registration);bad['fixtures'][1]['opponents'][0]['seed']+=1
        with self.assertRaisesRegex(ValueError,'Matched opponent'):r._design(bad)
        bad=copy.deepcopy(self.registration);bad['fixtures']=bad['fixtures'][:-1]
        with self.assertRaisesRegex(ValueError,'coverage is incomplete'):r._design(bad)


if __name__=='__main__':unittest.main()
