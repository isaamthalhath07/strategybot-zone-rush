from datetime import timedelta
import unittest
from . import budget as b


class BudgetTests(unittest.TestCase):
    def measurement(self,games=256,seconds=85):
        return dict(games=games,wall_seconds=seconds,full_actor_audits=games,both_referees=True)

    def test_deadline_reserves_heldout_and_packaging_at_observed_slow_rate(self):
        result=b.heldout_budget([self.measurement(seconds=75)])
        self.assertEqual(b.DEADLINE-b.START,timedelta(hours=10))
        self.assertEqual(result['development_maps'],24)
        self.assertEqual(result['final_maps'],80)
        self.assertEqual(result['packaging_reserved_seconds'],2700)
        self.assertFalse(result['heldout_outcomes_consumed'])
        self.assertEqual(result['new_game_credit'],0)

    def test_faster_complete_work_adds_maps_but_keeps_crossing_and_safety(self):
        rows=[self.measurement(seconds=25),self.measurement(seconds=32)]
        result=b.heldout_budget(rows)
        self.assertEqual(result['conservative_games_per_second'],6.4)
        self.assertEqual(result['development_games'],56*8*4*16)
        self.assertEqual(result['final_games'],192*2*4*16)
        self.assertLessEqual(result['development_games']/6.4,4800)
        self.assertLessEqual(result['final_games']/6.4,3900)
        self.assertEqual(result['development_setup_admission_analysis_reserved_seconds'],600)
        with self.assertRaises(ValueError):b.heldout_budget([self.measurement()])

    def test_incomplete_work_boolean_counts_scores_and_bad_rates_never_set_volume(self):
        for key,value in (('full_actor_audits',255),('full_actor_audits',True),('both_referees',False),
                          ('wall_seconds',0),('wall_seconds',float('nan')),('games',True)):
            row=self.measurement();row[key]=value
            with self.subTest(key=key,value=value),self.assertRaises(ValueError):b.heldout_budget([row])
        row=self.measurement();row['win_rate']=1
        with self.assertRaises(ValueError):b.heldout_budget([row])
        with self.assertRaises(ValueError):b.heldout_budget([self.measurement(seconds=1000)])

    def test_only_whole_generations_with_full_reserves_can_start(self):
        rows=[self.measurement()]
        self.assertTrue(b.may_start_generation(b.START+timedelta(hours=2),rows,coaching_and_setup_seconds=1800))
        self.assertFalse(b.may_start_generation(b.TRAIN_CUTOFF-timedelta(minutes=1),rows))
        with self.assertRaises(ValueError):b.may_start_generation(b.START.replace(tzinfo=None),rows)


if __name__=='__main__':unittest.main()
