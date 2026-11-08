"""Planning/identity checks only: zero matches, actor calls or admission credit."""
from collections import Counter
import copy
import hashlib
import json
from pathlib import Path
import random
import sqlite3
import unittest

from primary_migration import contract as c


ROOT = Path(__file__).resolve().parents[1]
LEGACY = ROOT/'.cache/primary/campaign_v1_20261109'


def descriptors(start,count):
    return (c.slot_schedule(index,episode) for index in range(start,start+count) for episode in range(200))


class PlanningContractTests(unittest.TestCase):
    def test_budget_preserves_existing_prefix_and_exact_original_goal(self):
        proposal = c.planned_budget([0,1,2,3,4])
        self.assertEqual(proposal['declared_legacy_slots'],100000)
        self.assertEqual(proposal['remaining_train_maps'],7500)
        self.assertEqual(proposal['remaining_train_stages'],75)
        self.assertEqual(proposal['remaining_train_slots'],1500000)
        self.assertEqual(sum(proposal[key] for key in ('declared_legacy_slots','remaining_train_slots',
                         'reserved_development_slots','reserved_final_slots')),2000000)
        self.assertFalse(proposal['certifies_executed_games'])
        self.assertEqual(proposal['new_primary_credit'],0)

    def test_prefix_cannot_be_copied_reordered_gapped_or_boolean(self):
        for stages in ([0,1,1],[0,2],[1,0],[False],[0,1.0],list(range(81))):
            with self.subTest(stages=stages),self.assertRaises(ValueError):
                c.planned_budget(stages)

    def test_stage_five_balance_and_last_stage_repeat_the_registered_pattern(self):
        report = c.validate_schedule(descriptors(500,100),500,100,'train')
        self.assertEqual(report['planning_slots_checked'],20000)
        self.assertEqual(set(report['candidate_counts'].values()),{2500})
        self.assertEqual((report['candidate_pair_min'],report['candidate_pair_max']),(156,157))
        self.assertEqual(report['observed_candidate_cells'],512)
        for episode in range(200):
            for offset in range(100):
                early,late = c.slot_schedule(500+offset,episode),c.slot_schedule(7900+offset,episode)
                for key in ('seat','token','candidate_slot','field'):
                    self.assertEqual(early[key],late[key])
        self.assertFalse(report['certifies_executed_games'])

    def test_development_uses_all_eight_and_final_exactly_one(self):
        dev = c.validate_schedule(descriptors(8000,1000),8000,1000,'development')
        final = c.validate_schedule(descriptors(9000,1000),9000,1000,'final')
        self.assertEqual(dev['candidate_counts'],{index:25000 for index in range(8)})
        self.assertEqual(final['candidate_counts'],{0:200000})
        self.assertEqual(final['observed_candidate_cells'],64)
        self.assertEqual(final['candidate_pair_min'],12500)
        self.assertEqual(final['candidate_pair_max'],12500)
        self.assertEqual(dev['new_primary_credit']+final['new_primary_credit'],0)

    def test_closed_form_matches_independent_occurrence_iteration_in_heldouts(self):
        for start in (8000,9000):
            occurrence = Counter()
            for index in range(start,start+101):
                for episode in range(200):
                    seat,token = episode%4,(episode//4+episode%4+index)%4+1
                    n = occurrence[seat,token]
                    occurrence[seat,token] += 1
                    value = c.slot_schedule(index,episode)
                    candidate = (n+4*seat+token-1)%8 if start==8000 else 0
                    field = c.FIELDS[(n//8+n%8+2*seat+token-1)%4]
                    self.assertEqual((value['candidate_slot'],value['field']),(candidate,field))

    def test_changed_candidate_seat_token_field_phase_or_extra_input_is_rejected(self):
        original = list(descriptors(500,1))
        for field,value in (('candidate_slot',7),('seat',3),('token',4),('field','pressure'),
                            ('phase','final'),('map_index',8000),('episode',True),('hidden_input',123)):
            bad = copy.deepcopy(original)
            bad[0][field] = value
            with self.subTest(field=field),self.assertRaises(ValueError):
                c.validate_schedule(bad,500,1,'train')
        for bad in (original[:-1],original+[original[0]]):
            with self.assertRaises(ValueError):
                c.validate_schedule(bad,500,1,'train')
        with self.assertRaises(ValueError):
            c.validate_schedule([],7999,2,'train')

    def test_new_rival_seeds_are_injective_disjoint_and_do_not_change_global_rng(self):
        before = random.getstate()
        seen = set()
        for index in range(500,600):
            for episode in range(200):
                focal = episode%4
                for seat in range(4):
                    if seat==focal:
                        continue
                    seed = c.rival_seed(index,episode,seat)
                    self.assertGreaterEqual(seed,1<<64)
                    self.assertEqual(divmod(seed-(1<<64),4),(200*index+episode,seat))
                    self.assertNotIn(seed,seen)
                    seen.add(seed)
        self.assertEqual(len(seen),60000)
        sample = c.rival_seed(500,0,1)
        self.assertEqual(random.Random(sample).getrandbits(64),random.Random(sample).getrandbits(64))
        self.assertEqual(before,random.getstate())
        with self.assertRaises(ValueError):
            c.rival_seed(500,0,0)

    def test_instance_identity_binds_version_and_entire_spec(self):
        original = c.rival_identity('1'*64,500,0,1,'2'*64)
        for version,index,episode,seat,spec in (('3'*64,500,0,1,'2'*64),('1'*64,501,0,1,'2'*64),
                                              ('1'*64,500,1,0,'2'*64),('1'*64,500,0,2,'2'*64),
                                              ('1'*64,500,0,1,'4'*64)):
            self.assertNotEqual(original,c.rival_identity(version,index,episode,seat,spec))

    def test_seed_index_is_lossless_above_sqlite_and_float_integer_limits(self):
        values = [(1<<64)-1,c.rival_seed(500,0,1),c.rival_seed(9999,199,0)]
        with sqlite3.connect(':memory:') as database:
            database.execute('CREATE TABLE seeds(value BLOB PRIMARY KEY CHECK(length(value)=9)) WITHOUT ROWID')
            database.executemany('INSERT INTO seeds VALUES (?)',[(c.seed_key(value),) for value in values])
            restored = [int.from_bytes(row[0],'big') for row in database.execute('SELECT value FROM seeds ORDER BY value')]
            self.assertEqual(restored,sorted(values))
            with self.assertRaises(sqlite3.IntegrityError):
                database.execute('INSERT INTO seeds VALUES (?)',(c.seed_key(values[1]),))
        for value in (float(values[1]),True,-1,1<<65):
            with self.assertRaises(ValueError):
                c.seed_key(value)

    def test_catalog_slot_cannot_gain_duplicate_version_or_candidate_credit(self):
        reservations = c.SlotReservations(c.ORIGINAL_CATALOG_SHA256)
        self.assertTrue(reservations.reserve(500,0,'1'*64,'2'*64,'3'*64))
        self.assertFalse(reservations.reserve(500,0,'1'*64,'2'*64,'3'*64))
        for version,task,row in (('4'*64,'2'*64,'3'*64),('1'*64,'4'*64,'3'*64),('1'*64,'2'*64,'4'*64)):
            with self.assertRaises(ValueError):
                reservations.reserve(500,0,version,task,row)
        with self.assertRaises(ValueError):
            c.SlotReservations('f'*64)


class ExistingEvidenceCompatibilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not (LEGACY/'catalog.json').exists() or not (LEGACY/'train_004/registration.json').exists():
            raise unittest.SkipTest('Ignored local legacy evidence unavailable; pure planning checks still run')

    def test_exact_existing_catalog_and_rehashed_replacement_rejection(self):
        body = (LEGACY/'catalog.json').read_bytes()
        report = c.validate_catalog_bytes(body,c.ORIGINAL_CATALOG_SHA256)
        self.assertEqual(report['catalog_maps'],10000)
        self.assertEqual(report['scheduled_primary_slots'],2000000)
        self.assertEqual(report['new_primary_credit'],0)
        changed = body+b' '
        with self.assertRaises(ValueError):
            c.validate_catalog_bytes(changed,hashlib.sha256(changed).hexdigest())

    def test_all_100000_legacy_assignments_match_without_replaying_any_actor(self):
        old_seeds = set()
        checked = 0
        for index in range(5):
            registration = json.loads((LEGACY/('train_%03d'%index)/'registration.json').read_bytes())
            candidates = {entry['sha256']:position for position,entry in enumerate(registration['candidates'])}
            for fixture in registration['fixtures']:
                expected = c.slot_schedule(fixture['map_index'],fixture['episode'])
                self.assertEqual((fixture['seat'],fixture['token'],candidates[fixture['candidate']],fixture['field']),
                                 (expected['seat'],expected['token'],expected['candidate_slot'],expected['field']))
                for rival in fixture['opponents']:
                    self.assertLess(rival['seed'],1<<64)
                    self.assertNotIn(rival['seed'],old_seeds)
                    old_seeds.add(rival['seed'])
                checked += 1
        self.assertEqual(checked,100000)
        self.assertEqual(len(old_seeds),300000)

    def test_only_exact_known_sources_can_claim_their_zero_or_eighty_oracles(self):
        paths = [ROOT/'bot.py',ROOT/'tester_bots/blocker.py',
                 ROOT/'confirmation_campaign/evidence/architectures_v2/feint_original.py']
        train = json.loads((LEGACY/'train_002/registration.json').read_bytes())
        paths += [Path(next(entry['path'] for entry in train['candidates'] if entry['sha256'].startswith('50d82d7a')))]
        for path in paths:
            body = path.read_bytes()
            value = c.classify_exact_reference(body)
            expected = 80 if value['family']=='e8-config' else 0
            self.assertEqual(value['expected_focal_legacy_oracles_per_full_game'],expected)
            self.assertEqual(value['required_actor_callbacks_per_game'],320)
            self.assertEqual(value['required_referees'],2)
            self.assertFalse(value['qualifies_mutants'])
            self.assertFalse(value['grants_runtime_approval'])
            with self.assertRaises(ValueError):
                c.classify_exact_reference(body+b'\n# unregistered source, even if behaviorally harmless\n')


if __name__=='__main__':
    unittest.main()
