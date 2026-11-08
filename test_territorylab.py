"""Rule and information-boundary checks for spatial adaptation experiments."""
import unittest

import engine
from botlib import CORNERS, parse
from territorylab import evaluate, opponents, policy
from territorylab.model import RegionModel, depth


class TerritoryTests(unittest.TestCase):
    def test_first_move_does_not_identify_centre(self):
        game = engine.Game(base=engine.make_map(seed=11))
        old = parse(game.views()[0])
        game.step(["EAST", "WEST", "WEST", "EAST"])
        new = parse(game.views()[0])
        model = RegionModel()
        model.update(old, new, CORNERS, 2)
        self.assertEqual(model.prob, [[1/3]*3 for _ in range(4)])
        self.assertEqual(model.n, [0]*4)
        self.assertEqual(game.owner[1], 0)  # arrival is not a capture

    def test_skipped_claim_does_not_prove_centre(self):
        model = RegionModel()
        game = engine.Game(base=engine.make_map(seed=21))
        game.step(["EAST", "WEST", "WEST", "EAST"])
        old = parse(game.views()[0])
        game.step(["EAST", "WEST", "WEST", "EAST"])
        model.update(old, parse(game.views()[0]), CORNERS, 3)
        self.assertEqual(model.skips, [1]*4)
        self.assertTrue(all(0.05 < p < 0.8 for probs in model.prob for p in probs))

    def test_inward_turn_is_more_informative_than_edge_travel(self):
        game = engine.Game(base=engine.make_map(seed=25))
        game.step(["EAST", "WEST", "WEST", "EAST"])
        old = parse(game.views()[0])
        rim = game.clone()
        rim.step(["EAST", "WEST", "WEST", "EAST"])
        inward = game.clone()
        inward.step(["SOUTH", "SOUTH", "NORTH", "NORTH"])
        a, b = RegionModel(), RegionModel()
        a.update(old, parse(rim.views()[0]), CORNERS, 3)
        b.update(old, parse(inward.views()[0]), CORNERS, 3)
        self.assertGreater(b.prob[0][0], a.prob[0][0])
        self.assertGreater(a.prob[0][1], b.prob[0][1])

    def test_frozen_stay_and_unlabelled_idle_abstain(self):
        game = engine.Game(base=engine.make_map(seed=31))
        model = RegionModel()
        old = parse(game.views()[0])
        game.step(["STAY"]*4)
        model.update(old, parse(game.views()[0]), CORNERS, 3)
        self.assertEqual(model.n, [0]*4)
        game.frozen = [2]*4
        old = parse(game.views()[0])
        game.step(["STAY"]*4)
        model.update(old, parse(game.views()[0]), CORNERS, 4)
        self.assertEqual(model.n, [0]*4)

    def test_two_inward_opponents_raise_centre_demand(self):
        model = RegionModel()
        game = engine.Game(base=[2]*64)
        model.prob[1] = model.prob[2] = [0.95, 0.025, 0.025]
        model.n = [10]*4
        board = parse(game.views()[0])
        demand = model.demand(board, game.pos, CORNERS, 1)
        uniform = model.demand(board, game.pos, CORNERS, 1, False)
        self.assertGreater(sum(demand[p] for p in range(64) if depth(p) >= 2),
                           sum(uniform[p] for p in range(64) if depth(p) >= 2))

    def test_no_feature_control_is_exact(self):
        task = evaluate.tasks("discovery", 4, 918311)[0]
        baseline = evaluate.play(task, "baseline")
        # A disabled spatial agent must not change the accepted policy.
        policy.VARIANTS["off"] = {}
        try:
            off = evaluate.play(task, "off")
        finally:
            del policy.VARIANTS["off"]
        for key in ("pw", "score", "scores", "action_hash"):
            self.assertEqual(baseline[key], off[key])

    def test_fresh_families_and_balanced_schedule(self):
        self.assertFalse(set(opponents.SPLITS["discovery"]) & set(opponents.SPLITS["final"]))
        tasks = evaluate.tasks("development", 224, 815523)
        for kind in {t["map_kind"] for t in tasks}:
            group = [t for t in tasks if t["map_kind"] == kind]
            self.assertEqual(len({(t["seat"], t["token"]) for t in group}), 16)
        self.assertEqual([sum(t["scenario"] == k for t in tasks) for k in range(4)], [56]*4)

    def test_demand_is_equivariant_under_horizontal_reflection(self):
        game = engine.Game(base=engine.make_map(seed=281))
        game.step(["EAST", "SOUTH", "WEST", "NORTH"])
        board = parse(game.views()[0])
        reflect = lambda p: p//8*8+7-p%8
        reflected = [[a[reflect(p)] for p in range(64)] for a in board]
        homes = [reflect(p) for p in CORNERS]
        positions = [reflect(p) for p in game.pos]
        model = RegionModel()
        model.n = [5]*4
        model.prob = [[0.8, 0.1, 0.1], [0.1, 0.8, 0.1], [0.1, 0.1, 0.8], [0.3, 0.3, 0.4]]
        normal = model.demand(board, game.pos, CORNERS, 1)
        mirrored = model.demand(reflected, positions, homes, 1)
        for p in range(64):
            self.assertAlmostEqual(normal[p], mirrored[reflect(p)], places=12)

    def test_prior_control_removes_history_but_keeps_geometry(self):
        from territorylab.attribution import PriorModel
        game = engine.Game(base=engine.make_map(seed=92))
        board = parse(game.views()[0])
        model = PriorModel()
        before = model.demand(board, game.pos, CORNERS, 1)
        model.prob = [[0.98, 0.01, 0.01]]*4
        model.n = [50]*4
        after = model.demand(board, game.pos, CORNERS, 1)
        self.assertEqual(before, after)
        self.assertEqual(model.n, [50]*4)


if __name__ == "__main__":
    unittest.main(verbosity=2)
