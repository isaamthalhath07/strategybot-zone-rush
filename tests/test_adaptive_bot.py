"""Contracts for the released adaptive bot: interface, safety nets and tracking."""
import ast
import copy
from enum import Enum
import importlib.util
from pathlib import Path
import random
import unittest

from tests import reference_engine as engine

ROOT = Path(__file__).resolve().parents[1]


def load(path="bot.py", name="adaptive_contract"):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def signature(public):
    return (public.bot_id, public.is_priority_token, tuple(public.legal_actions),
            tuple((c.occupant, c.owner, c.is_upgraded, c.is_home, c.is_frozen, c.base_points)
                  for row in public.board for c in row))


def new_game(seed=7, token=1):
    return engine.Game(base=engine.make_map(seed=seed), start_token=token,
                       rules={"catch_requires_stay": True})


class InterfaceTests(unittest.TestCase):
    def test_flat_dictionary_string_inputs_match_public_objects(self):
        public = new_game().views()[0]
        expected = load().act(public)
        raw = {"bot_id": "1", "is_priority_token": True,
               "legal_actions": [a.lower() for a in public.legal_actions],
               "board": [dict(occupant=c.occupant, owner=c.owner, base_points=c.base_points,
                              is_upgraded=c.is_upgraded, is_home=c.is_home, is_frozen=c.is_frozen)
                         for row in public.board for c in row]}
        before = copy.deepcopy(raw)
        self.assertEqual(load().act(raw), expected.lower())
        self.assertEqual(raw, before)

    def test_original_action_object_is_returned(self):
        actions = Enum("Action", "NORTH EAST SOUTH WEST STAY SHIELD")
        public = new_game().views()[0]
        expected = load().act(public)
        public.legal_actions = [getattr(actions, name) for name in public.legal_actions]
        self.assertIs(load().act(public), getattr(actions, expected))

    def test_unreadable_input_answers_stay(self):
        bot = load()
        self.assertEqual(bot.act({"board": [], "bot_id": 1, "legal_actions": ["east", "stay"]}), "stay")
        self.assertEqual(bot.act(object()), "STAY")

    def test_standard_library_only_and_no_io_or_dynamic_execution(self):
        tree = ast.parse((ROOT / "bot.py").read_text(encoding="utf8"))
        imports = {a.name.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
        imports |= {n.module.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
        self.assertLessEqual(imports, {"time", "random"})
        banned = {"print", "open", "input", "exec", "eval", "compile", "__import__"}
        self.assertFalse(any(isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in banned
                             for n in ast.walk(tree)))


class SafetyNetTests(unittest.TestCase):
    def test_policy_exception_falls_back_to_legal_work_not_idling(self):
        bot = load()
        bot._plan = lambda *args: 1 / 0
        game = new_game()
        moved = False
        for _ in range(12):
            public = game.views()[0]
            action = bot.act(public)
            self.assertIn(action, public.legal_actions)
            moved = moved or action != "STAY"
            game.step([action, "STAY", "STAY", "STAY"])
        self.assertTrue(moved)
        self.assertGreater(bot._M.errors, 0)
        self.assertGreater(sum(1 for o in game.owner if o == 1), 1)

    def test_slow_turn_reduces_search_effort(self):
        bot = load()
        real = bot._decide

        def slow(v, m):
            end = bot.time.perf_counter() + 0.05
            while bot.time.perf_counter() < end:
                pass
            return real(v, m)
        bot._decide = slow
        game = new_game()
        for _ in range(2):
            action = bot.act(game.views()[0])
            game.step([action, "STAY", "STAY", "STAY"])
        self.assertLess(bot._M.scale, 1.0)

    def test_unsupported_home_upgrade_is_abandoned(self):
        game = engine.Game(base=[3 if p in (0, 7, 56, 63) else 1 for p in range(64)],
                           rules={"catch_requires_stay": True, "home_upgradable": False})
        bot = load()
        for _ in range(10):
            action = bot.act(game.views()[0])
            game.step([action, "STAY", "STAY", "STAY"])
        self.assertNotEqual(game.pos[0], 0)
        self.assertEqual(bot._M.errors, 0)

    def test_new_game_in_the_same_process_resets_memory(self):
        bot = load()
        game = new_game()
        for _ in range(20):
            action = bot.act(game.views()[0])
            game.step([action, "STAY", "STAY", "STAY"])
        self.assertEqual(bot._M.turn, 20)
        bot.act(new_game(seed=8).views()[0])
        self.assertEqual(bot._M.turn, 1)
        self.assertEqual(bot._M.scores, [0] * 5)


class TrackingAndStrengthTests(unittest.TestCase):
    def play(self, files, seed, token):
        random.seed(seed)
        game = new_game(seed=seed, token=token)
        players = [load(path, "seat%d" % k) for k, path in enumerate(files)]
        checks = wrong = 0
        while not game.over():
            actions = []
            for seat, public in enumerate(game.views()):
                before = signature(public)
                action = players[seat].act(public)
                self.assertIn(action, public.legal_actions)
                self.assertEqual(signature(public), before)
                if files[seat] == "bot.py":
                    memory = players[seat]._M
                    self.assertEqual(memory.errors, 0)
                    self.assertEqual(memory.turn, game.turn)
                    self.assertEqual(memory.scores[1:], game.score)
                    self.assertEqual(memory.prog[seat + 1], game.prog[seat])
                    self.assertEqual(memory.cd[seat + 1], game.cd[seat])
                    for rival in range(4):
                        checks += 2
                        wrong += memory.prog[rival + 1] != game.prog[rival]
                        wrong += memory.cd[rival + 1] != game.cd[rival]
                actions.append(action)
            game.step(actions)
        return game.score, checks, wrong

    def test_public_tracking_and_results_against_retained_testers(self):
        lineups = [["bot.py", "tester_bots/previous_release.py", "tester_bots/blocker.py", "tester_bots/racer.py"],
                   ["tester_bots/previous_release.py", "bot.py", "tester_bots/previous_release.py",
                    "tester_bots/previous_release.py"],
                   ["tester_bots/blocker.py", "tester_bots/fusion.py", "bot.py", "tester_bots/previous_release.py"],
                   ["tester_bots/racer.py", "tester_bots/previous_release.py", "tester_bots/blocker.py", "bot.py"]]
        outscored = games = checks = wrong = 0
        for k, files in enumerate(lineups):
            for rep in range(2):
                score, c, w = self.play(files, seed=4100 + 10 * k + rep, token=1 + (k + rep) % 4)
                seat = files.index("bot.py")
                outscored += sum(score[seat] > s for j, s in enumerate(score) if j != seat)
                games += 1
                checks += c
                wrong += w
        # Rival counters are inferred from public boards; a few shield causes are ambiguous.
        self.assertLess(wrong / checks, 0.01)
        # Eight fixed games are a regression guard, not a strength claim (see lab/README.md).
        self.assertGreater(outscored / games, 1.5)


if __name__ == "__main__":
    unittest.main()
