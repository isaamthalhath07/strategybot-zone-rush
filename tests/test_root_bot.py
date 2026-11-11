"""Contracts for the root submission, checked on the independent reference engine.

These tests bind to behaviour every later version of the lab bot must keep (legal,
timely, input left untouched, exact own bookkeeping, tolerant of interface variations),
not to one version's coefficients, so shipping a new candidate does not rewrite them.
"""
import ast
import copy
from enum import Enum
import importlib.util
from pathlib import Path
import time
import unittest

from tests import reference_engine as engine

ROOT = Path(__file__).resolve().parents[1]
BOT = ROOT / "bot.py"
RULES = {"catch_requires_stay": True}


def load(name="root_bot_contract"):
    spec = importlib.util.spec_from_file_location(name, BOT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def signature(view):
    return (view.bot_id, view.is_priority_token, tuple(view.legal_actions),
            tuple((c.occupant, c.owner, c.is_upgraded, c.is_home, c.is_frozen, c.base_points)
                  for row in view.board for c in row))


class RootBotTests(unittest.TestCase):
    def test_standard_library_only_and_no_io_or_dynamic_execution(self):
        tree = ast.parse(BOT.read_text(encoding="utf8"))
        imports = {a.name.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
        imports |= {n.module.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
        self.assertLessEqual(imports, {"time", "random"})
        self.assertEqual(len([n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "act"]), 1)
        self.assertFalse(any(isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                             and n.func.id in {"open", "print", "input", "exec", "eval", "compile", "__import__"}
                             for n in ast.walk(tree)))

    def test_selfplay_is_legal_timely_and_keeps_exact_own_books(self):
        worst, calls, unexplained = 0.0, 0, 0
        for case in range(4):
            game = engine.Game(base=engine.make_map(seed=411100 + case), start_token=case + 1, rules=RULES)
            players = [load("root_seat_%d" % s) for s in range(4)]
            while not game.over():
                actions = []
                for seat, public in enumerate(game.views()):
                    before = signature(public)
                    start = time.perf_counter()
                    action = players[seat].act(public)
                    elapsed = (time.perf_counter() - start) * 1000
                    worst = max(worst, elapsed)
                    calls += 1
                    self.assertLess(elapsed, 2000 if game.turn == 1 else 200)
                    self.assertIn(action, public.legal_actions)
                    self.assertEqual(signature(public), before)          # input never mutated
                    if action == "SHIELD":
                        self.assertEqual(game.cd[seat], 0)               # never a wasted cast
                    memory = players[seat]._MEMS[seat + 1]
                    self.assertEqual(memory.turn, game.turn)
                    self.assertEqual(memory.scores[1:], game.score)
                    self.assertEqual(memory.prog[seat + 1], game.prog[seat])
                    self.assertEqual(memory.cd[seat + 1], game.cd[seat])
                    actions.append(action)
                game.step(actions)
            # A rival that shields and backfires while standing on another bot's land
            # looks, from the public board, exactly like that landlord catching it. The
            # tracker takes the likelier story and corrects itself when a later cast
            # contradicts it (counted in `unexplained`). That is a property of the
            # public information, not a fault, and the bot's random choices decide
            # whether a game contains such a turn, so it cannot be required to be zero.
            # The books that must be exact (own score, progress, cooldown) are checked
            # on every callback above.
            unexplained += sum(players[seat]._MEMS[seat + 1].unexplained for seat in range(4))
        self.assertEqual(calls, 1280)
        self.assertLessEqual(unexplained, 12)                            # under 1% of callbacks
        print("Root bot self-play: 1,280 callbacks; worst %.3f ms; %d ambiguous freezes re-read"
              % (worst, unexplained))

    def test_one_module_can_play_all_four_seats_and_a_second_game(self):
        shared = load("root_shared")
        for repeat in range(2):                 # the second pass is a new game in the same module
            game = engine.Game(base=engine.make_map(seed=411200), start_token=2, rules=RULES)
            separate = [load("root_separate_%d" % s) for s in range(4)]
            for _ in range(40):
                views = game.views()
                # Separate modules draw their own private random streams, so their moves
                # may differ from the shared module's; both must stay legal and in step.
                actions = [shared.act(v) for v in views]
                for seat, v in enumerate(views):
                    self.assertIn(actions[seat], v.legal_actions)
                    self.assertIn(separate[seat].act(v), v.legal_actions)
                    self.assertEqual(shared._MEMS[seat + 1].turn, game.turn)
                    self.assertEqual(shared._MEMS[seat + 1].scores[1:], game.score)
                game.step(actions)

    def test_dictionary_string_inputs_and_lower_case_actions(self):
        public = engine.Game(base=[3] * 64, rules=RULES).views()[0]
        expected = load().act(public)
        raw = {"bot_id": "1", "is_priority_token": "true",
               "legal_actions": [a.lower() for a in public.legal_actions],
               "board": [dict(occupant=str(c.occupant), owner=str(c.owner), base_points=str(c.base_points),
                              is_upgraded=str(c.is_upgraded).lower(), is_home=str(c.is_home).lower(),
                              is_frozen=str(c.is_frozen).lower()) for row in public.board for c in row]}
        before = copy.deepcopy(raw)
        self.assertEqual(load().act(raw), expected.lower())
        self.assertEqual(raw, before)

    def test_enum_action_objects_are_returned_unchanged(self):
        actions = Enum("Action", "NORTH EAST SOUTH WEST STAY SHIELD")
        public = engine.Game(base=[3] * 64, rules=RULES).views()[0]
        expected = load().act(public)
        public.legal_actions = [getattr(actions, name) for name in public.legal_actions]
        self.assertIs(load().act(public), getattr(actions, expected))

    def test_bare_tuple_cells_in_documented_field_order(self):
        public = engine.Game(base=[2] * 64, rules=RULES).views()[2]
        expected = load().act(public)
        public.board = [[(c.occupant, c.owner, c.is_upgraded, c.is_home, c.is_frozen, c.base_points)
                         for c in row] for row in public.board]
        self.assertEqual(load().act(public), expected)

    def test_unreadable_input_still_returns_a_legal_action(self):
        module = load()
        self.assertEqual(module.act({"board": [], "bot_id": 1, "legal_actions": ["EAST", "STAY"]}), "STAY")
        self.assertEqual(module.act({"board": None, "bot_id": 1, "legal_actions": ["EAST"]}), "EAST")

    def test_internal_error_plays_a_working_fallback_not_a_forfeit(self):
        module = load()
        game = engine.Game(base=[2] * 64, rules=RULES)

        def broken(v, m):
            raise RuntimeError("planner bug")
        module._decide = broken
        took = []
        for _ in range(6):
            public = game.views()[0]
            action = module.act(public)
            self.assertIn(action, public.legal_actions)
            took.append(action)
            game.step([action, "STAY", "STAY", "STAY"])
        self.assertTrue(any(a in ("EAST", "SOUTH") for a in took))       # it still goes and claims land
        self.assertGreater(sum(1 for o in game.owner if o == 1), 1)

    def test_frozen_turn_and_single_option_are_answered_directly(self):
        game = engine.Game(base=[2] * 64, rules=RULES)
        public = game.views()[0]
        public.legal_actions = ["STAY"]
        self.assertEqual(load().act(public), "STAY")


if __name__ == "__main__":
    unittest.main()
