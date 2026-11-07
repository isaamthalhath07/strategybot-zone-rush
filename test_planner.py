"""Economic and legal-state regressions from the independent strategy audit."""
import math
import itertools
import unittest

import engine
import mybot


class PlannerRulesTests(unittest.TestCase):
    def setUp(self):
        self.agent = mybot.Agent(params={
            "w_claim": 1.0, "w_upgrade": 1.0, "w_raid": 1.0,
            "w_raid_late": 1.0, "w_denial": 0.0, "combo": 1.0,
            "consolidate": 0.0, "home_bonus": 1.0, "raid_risk": 0.0,
            "lead_caution": 0.0,
        })
        self.agent._cellmod = [1.0] * 64
        self.agent._expose = [0.0] * 64
        self.agent.tr.home_of = [0] * 64
        self.owner = [0] * 64
        self.upg = [0] * 64
        self.occ = [0] * 64
        self.base = [1] * 64
        self.frz = [0] * 64
        self.care = [0.0, 1.0, 1.0, 1.0]

    def gain(self, kind, need=1, used=0, remaining=1):
        return self.agent._work_gain(
            9, kind, 3, need, used, self.owner, self.upg,
            self.occ, 1, remaining, 1.0, self.care, 0)

    def test_final_turn_capture_receives_completion_turn_income(self):
        game = engine.Game()
        game.turn = 80
        game.pos[0] = 9
        game.base[9] = 3
        before = game.score[0]
        old_income = game.income[0]
        game.step(["STAY"] * 4)
        self.assertEqual(game.score[0] - before - old_income, 3)
        self.assertEqual(self.gain(0), 3.0)

    def test_final_turn_upgrade_receives_completion_turn_income(self):
        self.owner[9] = 1
        self.assertEqual(self.gain(1), 3.0)
        self.assertEqual(self.gain(1, need=3, remaining=3), 3.0)

    def test_final_turn_raid_has_bounty_and_income(self):
        self.owner[9] = 2
        self.assertEqual(self.gain(2), 27.0)

    def test_combo_counts_income_between_capture_and_upgrade(self):
        # Four stays: income of 3, 3, 3, then 6 on the upgrading stay.
        self.assertEqual(self.gain(3, need=4, remaining=4), 15.0)
        self.assertEqual(self.gain(3, need=4, used=1, remaining=5), 15.0)

    def test_immune_home_does_not_trigger_capture_defence(self):
        self.owner[0] = 1
        self.occ[0] = 2
        self.base[0] = 3
        self.agent.tr.home_of[0] = 1
        self.assertFalse(self.agent._should_shield(
            self.owner, self.upg, self.occ, self.frz, self.base,
            1, 40, 1.0, self.care))

    def test_immune_home_has_no_capture_threat(self):
        self.owner[0] = 1
        self.occ[1] = 2
        self.base[0] = 3
        self.agent.tr.home_of[0] = 1
        self.assertEqual(self.agent._threat(
            0, self.owner, self.upg, self.base, self.occ,
            1, 40, self.care), 0.0)

    def test_final_turn_shield_requires_possible_capture(self):
        self.owner[9] = 1
        self.upg[9] = 1
        self.occ[9] = 2
        self.assertFalse(self.agent._should_shield(
            self.owner, self.upg, self.occ, self.frz, self.base,
            1, 1, 1.0, self.care))

    def test_final_turn_shield_still_stops_imminent_capture(self):
        self.owner[9] = 1
        self.upg[9] = 1
        self.occ[9] = 2
        self.agent.tr.prog[1] = 2
        self.assertTrue(self.agent._should_shield(
            self.owner, self.upg, self.occ, self.frz, self.base,
            1, 1, 1.0, self.care))

    def test_planner_restores_progress_cost_after_leaving(self):
        game = engine.Game()
        game.pos[0] = 9
        game.owner[9] = 1
        self.agent.tr.init_static(game.base, game.home)
        self.agent.tr.pos = game.pos[:]
        self.agent.tr.prog[0] = 2
        self.agent._deep = 1.0
        self.agent._deadline = math.inf
        self.agent.P.update(visits=2, horizon=12, beam=32, hold=0.0)
        owner, upg = game.owner[:], game.upg[:]
        occ = [0] * 64
        for seat, position in enumerate(game.pos, 1):
            occ[position] = seat
        self.agent._candidates = lambda *args: [
            (10.0, 0, 9, 1, 1, 1),  # two banked stays make the next one enough
            (9.0, 0, 10, 0, 1, 1),
        ]
        returning_costs = []

        def record_gain(p, kind, value, need, used, *args):
            if p == 9 and used > 0:
                returning_costs.append(need)
            return 10.0

        self.agent._work_gain = record_gain
        self.agent._plan_walk(owner, upg, game.base, game.home, occ,
                               [0] * 64, 1, 9, 12, 1.0, self.care)
        self.assertTrue(returning_costs, "returning route was not exercised")
        self.assertEqual(set(returning_costs), {3})

    def test_negative_surrogate_does_not_force_idle(self):
        game = engine.Game()
        game.pos[0] = 9
        game.owner[9] = 1
        game.upg[9] = 1
        game.owner[10] = 2
        self.agent.tr.init_static(game.base, game.home)
        self.agent.tr.pos = game.pos[:]
        self.agent._deep = 1.0
        self.agent._deadline = math.inf
        self.agent.plan_target = 10
        self.agent._candidates = lambda *args: [(1.0, 0, 10, 2, 1, 1)]
        self.agent._work_gain = lambda *args: -10.0
        occ = [0] * 64
        for seat, position in enumerate(game.pos, 1):
            occ[position] = seat
        action = self.agent._plan_walk(
            game.owner, game.upg, game.base, game.home, occ,
            [0] * 64, 1, 9, 12, 1.0, self.care)
        # The route score is a calibrated surrogate. Treating zero as an idle
        # floor lost 0.23 pairwise wins in a frozen-code 100-game ablation;
        # movement also reveals new candidates outside the current reach.
        self.assertEqual(action, "EAST")
        self.assertEqual(self.agent.plan_target, 10)

    def test_home_frame_follows_observed_seat_mapping(self):
        # Seat numbering may differ between engines. Every legal assignment
        # of the four homes must map that seat's actual home to local (0, 0).
        for assignment in itertools.permutations(mybot.CORNERS):
            home_of = [0] * 64
            for seat, home in enumerate(assignment, 1):
                home_of[home] = seat
            self.agent.tr.init_static([1] * 64, home_of)
            for seat, home in enumerate(assignment, 1):
                with self.subTest(assignment=assignment, seat=seat):
                    frame = self.agent._home_frame(seat)
                    self.assertEqual(frame[home], 0)
                    self.assertEqual(frame[63 - home], 63)
                    self.assertEqual(set(frame), set(range(64)))


if __name__ == "__main__":
    unittest.main(verbosity=2)
