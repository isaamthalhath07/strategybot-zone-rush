"""Schedule corruption checks using explicitly mocked prior admission, no games."""
import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from evolution import runner
from primary_campaign import core
from confirmation_campaign import prepare


class ConfirmationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cache = core.ROOT/'.cache'
        cache.mkdir(exist_ok=True)
        cls.temp = tempfile.TemporaryDirectory(dir=cache,prefix='confirmation-unit-')
        base = Path(cls.temp.name)
        cls.space,_ = core.sources_space()
        genes = dict(cls.space.genes,backfire_cost=1.674416,feint_weight=1.167526,
                     shield_prior=.333592,shield_weight=1.227437,stay_prior=.771476)
        candidate = base/'unpromoted_50d.py'
        candidate.write_bytes(cls.space.export(genes))
        assert core.digest(candidate.read_bytes()) == prepare.CHALLENGER
        cls.parent = dict(campaign_id='mock-parent-no-games',catalog_sha256='mock-catalog',
                          guards=core.guard_sources(),sources={name:runner.source_entry(core.ROOT/path) for name,path in {
                              'planner':'bot.py','research':'tester_bots/research_alternative.py',
                              'racer':'tester_bots/racer.py','blocker':'tester_bots/blocker.py'}.items()})
        original = dict(sha256=prepare.CHALLENGER,path=str(candidate),genes=genes,name='mock-discovery-source')

        def prior(path):
            path=Path(path)
            if path.name=='summary.json':
                return dict(candidates=[dict(sha256=prepare.CHALLENGER)])
            if path.name=='registration.json':
                return dict(candidates=[original])
            raise ValueError('Unexpected mocked prior path')

        cls.patches=[patch.object(core,'load_catalog',return_value=(cls.parent,[])),
                     patch.object(core,'validated_audit',side_effect=lambda path:dict(generation=int(Path(path).name[-3:]),
                                  games_sha256='mock-no-games',registration_sha256='mock-no-registration')),
                     patch.object(core,'read_sealed',side_effect=prior),
                     patch.object(core,'historical_map_ids',return_value=set())]
        for item in cls.patches:
            item.start()
        try:
            cls.registration=prepare.make(base/'mock-campaign',base/'plan',map_count=4)
        except BaseException:
            for item in reversed(cls.patches):
                item.stop()
            cls.temp.cleanup()
            raise

    @classmethod
    def tearDownClass(cls):
        for item in reversed(cls.patches):
            item.stop()
        cls.temp.cleanup()

    def test_balanced_pairs_and_fresh_instance_ids(self):
        result=prepare.validate(self.registration)
        self.assertEqual(result,dict(games=512,paired_conditions=256,maps=4,
                                     unique_rival_instances=1536,primary_credit=0))

    def test_rehashed_easier_rivals_and_foreign_map_are_rejected(self):
        for field in ('opponents','base'):
            bad=copy.deepcopy(self.registration)
            fixture=bad['fixtures'][0]
            if field=='opponents':
                fixture['opponents'][0]['family']='farmer'
                fixture['opponents'][0]['seed']+=1
            else:
                fixture['base']=[1]*64
            fixture['id']=core.digest(core.canonical({k:v for k,v in fixture.items() if k!='id'}))
            with self.subTest(field=field),self.assertRaises(ValueError):
                prepare.validate(bad)

    def test_missing_duplicate_and_wrong_candidate_tasks_fail(self):
        for mode in ('missing','duplicate','reassigned'):
            bad=copy.deepcopy(self.registration)
            if mode=='missing':
                bad['fixtures'].pop()
            elif mode=='duplicate':
                bad['fixtures'].append(copy.deepcopy(bad['fixtures'][0]))
            else:
                bad['fixtures'][0]['candidate']='0'*64
            with self.subTest(mode=mode),self.assertRaises(ValueError):
                prepare.validate(bad)

    def test_source_gene_or_scope_drift_fails(self):
        for mode in ('guard','gene','credit'):
            bad=copy.deepcopy(self.registration)
            if mode=='guard':
                bad['guards'].pop(str(Path(prepare.__file__).resolve()))
            elif mode=='gene':
                bad['candidates'][0]['genes']['risk_open']+=.1
            else:
                bad['primary_games_accepted']=512
            with self.subTest(mode=mode),self.assertRaises(ValueError):
                prepare.validate(bad)

    def test_map_symmetry_seed_and_exclusion_are_enforced(self):
        for mode in ('symmetry','seed','exclusion'):
            bad=copy.deepcopy(self.registration)
            excluded=()
            if mode=='symmetry':
                bad['maps'][0]['base'][0]=1 if bad['maps'][0]['base'][0]!=1 else 2
            elif mode=='seed':
                bad['maps'][0]['seed']+=1
            else:
                excluded=[bad['maps'][0]['rotation_orbit']]
            with self.subTest(mode=mode),self.assertRaises(ValueError):
                prepare.validate(bad,excluded)


if __name__=='__main__':
    unittest.main()
