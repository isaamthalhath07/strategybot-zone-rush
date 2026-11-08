"""Referee tests: rulebook examples, plus a differential check against engine.py from main.

Run from the repo root:  python -m unittest discover -s harness -p "test_*.py"
"""
import importlib.util
import itertools
import os
import random
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import referee  # noqa: E402
from referee import Referee, example_map, random_map  # noqa: E402

FLAGS = ("frozen_stay_counts", "claim_resets_progress", "catch_requires_stay",
         "lost_contest_is_stay", "home_upgradable")


def load_main_engine():
    """engine.py as it is on main (falls back to the copy in this checkout)."""
    root = os.path.dirname(HERE)
    try:
        src = subprocess.run(["git", "show", "origin/main:engine.py"], cwd=root,
                             capture_output=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError):
        path = os.path.join(root, "engine.py")
        if not os.path.exists(path):
            return None
        with open(path, "rb") as f:
            src = f.read()
    tmp = os.path.join(tempfile.mkdtemp(), "main_engine.py")
    with open(tmp, "wb") as f:
        f.write(src)
    spec = importlib.util.spec_from_file_location("main_engine", tmp)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def place(ref, seat, cell, owner=None, upg=False):
    ref.pos[seat - 1] = cell
    if owner is not None:
        ref.owner[cell] = owner
        ref.upg[cell] = upg


class RulebookExamples(unittest.TestCase):
    def test_example_map_matches_rulebook_diagram(self):
        base = example_map()
        self.assertEqual(base[0:8], [1, 1, 1, 2, 2, 1, 1, 1])
        self.assertEqual(base[24:32], [2, 2, 3, 3, 3, 3, 2, 2])
        self.assertEqual(base, base[::-1])

    def test_raid_on_upgraded_cell_takes_three_stays_and_pays_48(self):
        g = Referee(example_map())
        cell = 3 * 8 + 3
        self.assertEqual(g.base[cell], 3)
        g.owner[cell], g.upg[cell] = 2, True
        place(g, 1, cell - 1)
        g.step(["EAST", "STAY", "STAY", "STAY"])          # arriving doesn't count
        self.assertEqual(g.prog[0], 0)
        g.step(["STAY"] * 4)
        g.step(["STAY"] * 4)
        self.assertEqual(g.owner[cell], 2)
        out = g.step(["STAY"] * 4)
        self.assertEqual(g.owner[cell], 1)
        self.assertFalse(g.upg[cell])
        raid = [e for e in out["events"] if e["type"] == "raid"][0]
        self.assertEqual(raid["bonus"], 48)

    def test_shield_freezes_raider_and_resets_progress(self):
        g = Referee(example_map())
        cell = 3 * 8 + 3
        g.owner[cell], g.upg[cell] = 2, True
        place(g, 1, cell)
        g.step(["STAY"] * 4)
        self.assertEqual(g.prog[0], 1)
        out = g.step(["STAY", "SHIELD", "STAY", "STAY"])
        self.assertEqual(g.prog[0], 0)
        self.assertEqual(g.frozen[0], 2)
        self.assertEqual(g.frozen[1], 0)
        self.assertEqual(g.cd[1], 4)
        self.assertTrue(any(e["type"] == "shield" and e["caught"] == [1] for e in out["events"]))
        self.assertEqual(g.legal(0), ["STAY"])
        self.assertNotIn("SHIELD", g.legal(1))

    def test_shield_that_catches_nobody_backfires(self):
        g = Referee(example_map())
        g.step(["STAY", "SHIELD", "STAY", "STAY"])
        self.assertEqual(g.frozen[1], 2)

    def test_no_swaps(self):
        g = Referee(example_map())
        place(g, 1, 10)
        place(g, 2, 11)
        g.step(["EAST", "WEST", "STAY", "STAY"])
        self.assertEqual(g.pos[:2], [10, 11])

    def test_owner_wins_contest(self):
        g = Referee(example_map())
        place(g, 1, 19)
        place(g, 2, 21)
        g.owner[20] = 2
        g.token = 1
        g.step(["EAST", "WEST", "STAY", "STAY"])
        self.assertEqual(g.pos[1], 20)
        self.assertEqual(g.pos[0], 19)

    def test_token_order_decides_neutral_contest(self):
        g = Referee(example_map())             # rulebook: seat 3 holds the token, order 3-4-1-2
        place(g, 1, 19)
        place(g, 4, 21)
        g.token = 3
        out = g.step(["EAST", "STAY", "STAY", "WEST"])
        self.assertEqual(g.pos[3], 20)
        self.assertEqual(g.pos[0], 19)
        contest = [e for e in out["events"] if e["type"] == "contest"][0]
        self.assertEqual((contest["winner"], contest["why"]), (4, "token"))

    def test_homes_never_fall(self):
        g = Referee(example_map())
        place(g, 1, 6)
        g.step(["EAST", "STAY", "STAY", "STAY"])
        self.assertEqual(g.pos[0], 6)              # seat 2 is still at home on cell 7
        place(g, 2, 15)
        for _ in range(5):
            g.step(["EAST", "STAY", "STAY", "STAY"])
            g.step(["STAY"] * 4)
        self.assertEqual(g.owner[7], 2)

    def test_legal_excludes_occupied_flag(self):
        g = Referee(example_map(), rules={"legal_excludes_occupied": True})
        plain = Referee(example_map())
        for ref in (g, plain):
            place(ref, 1, 1)
            place(ref, 2, 2)
        self.assertNotIn("EAST", g.legal(0))
        self.assertIn("EAST", plain.legal(0))

    def test_scoring_and_places(self):
        self.assertEqual(referee.places([10, 20, 20, 5]), [3, 1, 1, 4])
        self.assertEqual(referee.pairwise([10, 20, 20, 5]), [1 / 3, 2.5 / 3, 2.5 / 3, 0.0])


class MatchesMainEngine(unittest.TestCase):
    """Random play through both referees under every combination of the five shared flags."""

    @classmethod
    def setUpClass(cls):
        cls.engine = load_main_engine()

    def compare(self, flags, seed, turns=80):
        eng = self.engine
        rnd = random.Random(seed)
        base = random_map(seed) if seed % 2 else example_map()
        self.assertEqual(base, eng.make_map(seed=seed) if seed % 2 else eng.make_map(canonical=True))
        start = rnd.randint(1, 4)
        mine = Referee(base, rules=flags, start_token=start, max_turns=turns)
        theirs = eng.Game(base=base, max_turns=turns, rules=flags, start_token=start)
        while not mine.over():
            actions = []
            for i in range(4):
                legal = mine.legal(i)
                self.assertEqual(sorted(legal), sorted(theirs.legal(i)))
                roll = rnd.random()
                if roll < 0.40 and "STAY" in legal:
                    a = "STAY"
                elif roll < 0.52 and "SHIELD" in legal:
                    a = "SHIELD"
                elif roll < 0.54:
                    a = rnd.choice(["SHIELD", "JUMP", None, "NORTH"])
                else:
                    a = rnd.choice(legal)
                actions.append(a)
            mine.step(actions)
            theirs.step(actions)
            state = (mine.pos, mine.owner, [int(u) for u in mine.upg], mine.frozen, mine.cd,
                     mine.prog, mine.score, mine.token)
            expect = (theirs.pos, theirs.owner, list(theirs.upg), theirs.frozen, theirs.cd,
                      theirs.prog, theirs.score, theirs.token)
            self.assertEqual(state, expect, "flags=%r seed=%d turn=%d" % (flags, seed, mine.turn - 1))

    def test_all_flag_combinations(self):
        if self.engine is None:
            self.skipTest("engine.py from main is not available")
        for combo in itertools.product((False, True), repeat=len(FLAGS)):
            flags = dict(zip(FLAGS, combo))
            for seed in range(12):
                self.compare(flags, seed)


if __name__ == "__main__":
    unittest.main()
