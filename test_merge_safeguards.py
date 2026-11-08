"""Exercise main's rule-interpretation safeguards in both merged exports."""
import importlib.util
import itertools
from pathlib import Path
import unittest

import engine


ROOT = Path(__file__).resolve().parent


def fresh_module(filename):
    spec = importlib.util.spec_from_file_location("merge_check_" + filename[:-3], ROOT / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.SAFETY["deterministic"] = True
    return module


def permuted_start(corners):
    game = engine.Game(base=[3] * 64)
    for seat, cell in enumerate(corners, 1):
        game.pos[seat - 1] = cell
        game.owner[cell] = seat
        game.home[cell] = seat
    return game


class MergeSafeguardsTests(unittest.TestCase):
    def test_failed_home_upgrade_leaves_after_completion_should_have_happened(self):
        # A valuable home makes the planner attempt an upgrade. The alternate
        # server rule prevents completion, which used to trap it for most turns.
        base = [1] * 64
        for cell in engine.CORNERS.values():
            base[cell] = 3
        for filename in ("fusion.py", "bot.py"):
            with self.subTest(export=filename):
                module = fresh_module(filename)
                game = engine.Game(base=base, rules={"home_upgradable": False})
                actions = []
                for _ in range(8):
                    view = game.views()[0]
                    action = module.act(view)
                    self.assertIn(action, view.legal_actions)
                    actions.append(action)
                    game.step([action, "STAY", "STAY", "STAY"])
                self.assertEqual(actions[:3], ["STAY"] * 3)
                self.assertIn(actions[3], ("EAST", "SOUTH"))
                self.assertNotEqual(game.pos[0], 0)
                self.assertFalse(game.upg[0])
                brain = module._F_BRAINS[1]
                self.assertIn(0, brain.econ.mem["dead"])
                self.assertEqual(brain.errors, {"econ": 0, "route": 0})

    def test_all_starting_corner_assignments_are_recognized(self):
        for filename in ("fusion.py", "bot.py"):
            module = fresh_module(filename)
            for corners in itertools.permutations(engine.CORNERS.values()):
                game = permuted_start(corners)
                for seat, view in enumerate(game.views(), 1):
                    with self.subTest(export=filename, corners=corners, seat=seat):
                        observation = module._f_normalize(view)
                        self.assertTrue(observation.fresh)
                        self.assertEqual(observation.pos[seat], corners[seat - 1])

    def test_reused_module_resets_on_a_different_corner_assignment(self):
        for filename in ("fusion.py", "bot.py"):
            with self.subTest(export=filename):
                module = fresh_module(filename)
                previous = engine.Game(base=[3] * 64)
                for _ in range(4):
                    action = module.act(previous.views()[0])
                    previous.step([action, "STAY", "STAY", "STAY"])
                self.assertTrue(module._F_BRAINS[1].progressed)
                self.assertEqual(module._F_BRAINS[1].turns, 4)

                game = permuted_start((7, 0, 56, 63))
                view = game.views()[0]
                self.assertIn(module.act(view), view.legal_actions)
                brain = module._F_BRAINS[1]
                self.assertEqual(brain.turns, 1)
                self.assertEqual(brain.econ.mem["turn"], 1)
                self.assertTrue(brain.econ.mem["known_start"])
                self.assertEqual(brain.cold_left, 0)
                self.assertEqual(brain.errors, {"econ": 0, "route": 0})


if __name__ == "__main__":
    unittest.main()
