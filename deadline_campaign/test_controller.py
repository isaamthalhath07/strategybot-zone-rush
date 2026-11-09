"""Synthetic receipt/cohort boundaries; no real actors, CUDA or live authority."""
import copy
from datetime import timedelta
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from . import controller as c


class FakeAuthority:
    def __init__(self,records): self.records=records
    def read(self,scope,path): return copy.deepcopy(self.records[scope])


class ControllerTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='SYNTHETIC-COORDINATOR-',dir=c.ROOT/'deadline_campaign')
        self.addCleanup(self.temp.cleanup);self.directory=Path(self.temp.name)

    def acceptance_fixture(self):
        reg=dict(phase='train',generation=0,fixtures=[{'id':'SYNTHETIC'}]*8192)
        c.frozen._seal(self.directory/'registration.json',reg)
        digest=c.design.sha((self.directory/'registration.json').read_bytes())
        began=c.budget.START+timedelta(hours=1);ended=began+timedelta(seconds=30)
        aggregate=dict(games=8192,ranking=[])
        accepted=dict(phase='train',generation=0,registration_sha256=digest,
            completed_utc=ended.isoformat(),original_games=8192,independently_regenerated_callbacks=8192*320,
            both_referees=True,promoted=False,original_primary_campaign_credit=0,completed_per_game_bmcts_audits=0,
            measurement=dict(games=8192,wall_seconds=29.99,full_actor_audits=8192,both_referees=True),
            originals_sha256='a'*64,audits_sha256='b'*64,aggregate=aggregate)
        started=dict(phase='train',generation=0,registration_sha256=digest,planned_games=8192,started_utc=began.isoformat())
        summary=dict(originals_sha256='a'*64,audits_sha256='b'*64,wall_before_final_publication_s=29.)
        return reg,accepted,started,summary,aggregate

    def test_acceptance_checks_lifecycle_time_and_actual_counts(self):
        reg,accepted,started,summary,aggregate=self.acceptance_fixture()
        def check(value,start=started):
            with patch.object(c,'_verify_output',return_value=(summary,aggregate)),\
                    patch.object(c,'now',return_value=c.budget.START+timedelta(hours=2)):
                return c._validate_acceptance(self.directory,FakeAuthority({'acceptance':value,'start':start}),self.directory,reg)
        self.assertEqual(check(accepted),accepted)
        for key,value in (('independently_regenerated_callbacks',320),('both_referees',False),
                          ('original_primary_campaign_credit',True),('completed_per_game_bmcts_audits',1),
                          ('completed_utc',(c.budget.TRAIN_CUTOFF+timedelta(seconds=1)).isoformat())):
            changed=copy.deepcopy(accepted);changed[key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):check(changed)
        for seconds in (1e-20,28.99,float('inf'),float('nan')):
            changed=copy.deepcopy(accepted);changed['measurement']['wall_seconds']=seconds
            with self.subTest(seconds=seconds),self.assertRaises(ValueError):check(changed)
        changed=copy.deepcopy(started);changed['generation']=1
        with self.assertRaises(ValueError):check(accepted,changed)

    def test_canonical_registration_rebuild_rejects_relabeling_and_receipt_swaps(self):
        bodies=c.design.initial_population();entries=[]
        for body in bodies:
            path=self.directory/(c.design.sha(body)+'.py');path.write_bytes(body);entries.append(c.design.source_entry(path))
        manifest={'source_sha256':{'bot.py':c.recipe.E8}}
        boards=c.design.catalog()[8000:8001]
        guards={str(c.ROOT/'bot.py'):c.recipe.E8}
        reg=c.design.cohort('development',0,boards,entries,guards)
        c.frozen._seal(self.directory/'registration.json',reg)
        receipt=dict(phase='development',generation=0,path=str(self.directory/'registration.json'),
            registration_sha256=c.design.sha((self.directory/'registration.json').read_bytes()),planned_games=512,
            map_indices=[8000],candidate_sha256=[entry['sha256'] for entry in entries])
        def check(record,actual_bodies=bodies):
            return c._validate_registration(self.directory,FakeAuthority({'registration':record}),manifest,
                self.directory,'development',0,actual_bodies,boards)
        self.assertEqual(check(receipt),reg)
        for key,value in (('phase','final'),('map_indices',[9000]),('planned_games',511),('registration_sha256','0'*64)):
            changed=copy.deepcopy(receipt);changed[key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):check(changed)
        with self.assertRaises(ValueError):check(receipt,list(reversed(bodies)))

    def test_no_training_after_any_heldout_phase_artifact(self):
        self.assertTrue(c._heldout_absent(self.directory))
        for name in ('shortlist.json','development','dev_selection.json','final','final_decision.json'):
            path=self.directory/name;path.write_bytes(b'SYNTHETIC')
            self.assertFalse(c._heldout_absent(self.directory));path.unlink()

    def test_controller_canonical_output_is_not_user_swappable(self):
        with patch.object(c.Authority,'load') as load:
            with self.assertRaises(ValueError):c._context(self.directory)
        load.assert_not_called()

    def test_controller_closes_reporter_and_structural_source_dependencies(self):
        from deadline_campaign.train_report import source_pins as report_pins
        from deadline_strategy.goal_space import source_pins as goal_pins
        actual=c.source_pins()
        for expected in (report_pins(),goal_pins()):
            self.assertTrue(set(expected)<=set(actual))
            self.assertTrue(all(actual[k]==v for k,v in expected.items()))

    def test_qualified_scheduling_binds_actual_header_and_signed_acceptance(self):
        reg,accepted,started,summary,aggregate=self.acceptance_fixture()
        configuration=dict(batch_size=128,workers=8,audit_workers=4)
        execution=self.directory/'execution';execution.mkdir()
        c.frozen._seal(execution/'execution_started.json',configuration)
        accepted['execution_configuration']=dict(configuration)
        accepted['execution_header_sha256']=c.design.sha((execution/'execution_started.json').read_bytes())
        def check(value,requested=configuration):
            with patch.object(c,'_verify_output',return_value=(summary,aggregate)),\
                    patch.object(c,'now',return_value=c.budget.START+timedelta(hours=2)):
                return c._validate_acceptance(self.directory,FakeAuthority({'acceptance':value,'start':started}),
                    self.directory,reg,requested)
        self.assertEqual(check(accepted),accepted)
        with self.assertRaises(ValueError):check(accepted,c.DEFAULT_EXECUTION)
        changed=copy.deepcopy(accepted);changed['execution_configuration']['workers']=4
        with self.assertRaises(ValueError):check(changed)
        changed=copy.deepcopy(accepted);changed['execution_header_sha256']='0'*64
        with self.assertRaises(ValueError):check(changed)
        with self.assertRaises(ValueError):c._assert_execution_configuration(self.directory,dict(batch_size=128.,workers=8,audit_workers=4))


if __name__=='__main__':unittest.main()
