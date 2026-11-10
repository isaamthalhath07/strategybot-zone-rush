"""Official effective-STAY shielding and public-history candidate contracts."""
import ast
import importlib.util
from pathlib import Path
import random
import time
import unittest

from tests import reference_engine as engine

ROOT = Path(__file__).resolve().parents[1]
CANDIDATE = ROOT / "tester_bots" / "guarded_transfer.py"   # the previous release


def load():
    spec = importlib.util.spec_from_file_location("official_candidate_contract", CANDIDATE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def signature(v):
    return (v.bot_id, v.is_priority_token, tuple(v.legal_actions),
            tuple((c.owner, c.occupant, c.is_upgraded, c.is_home, c.is_frozen, c.base_points)
                  for row in v.board for c in row))


def observe(module, g, action=None, offer_unfiltered=False):
    public = g.views()[0]
    if offer_unfiltered and not g.frozen[0] and "SHIELD" not in public.legal_actions:
        public.legal_actions.append("SHIELD")
    before = signature(public)
    returned = module.act(public)
    assert returned in public.legal_actions and signature(public) == before
    memory = module._history[1]
    if action is not None:
        memory["last"] = action
    return returned, memory


class OfficialCandidateTests(unittest.TestCase):
    def game(self):
        return engine.Game(base=[2]*64, rules={"catch_requires_stay": True})

    def test_successful_move_within_land_or_arrival_escapes(self):
        for old_owner in (0, 2):
            module, g = load(), self.game()
            g.pos[0], g.owner[36], g.owner[28] = 36, old_owner, 2
            observe(module, g, "NORTH")
            g.step(["NORTH", "SHIELD", "STAY", "STAY"])
            _, memory = observe(module, g)
            self.assertEqual(g.pos[0], 28)
            self.assertEqual(g.frozen[:2], [0, 2])
            self.assertEqual(memory["shield_certain"], {2})
            self.assertEqual(memory["cooldown"][2], 4)
            self.assertEqual(memory["progress"], 0)
            self.assertFalse(memory["raid_catches"])

    def test_blocked_move_counts_as_stay_and_is_caught(self):
        module, g = load(), self.game()
        g.pos[0], g.pos[2], g.owner[36] = 36, 28, 2
        observe(module, g, "NORTH")
        g.step(["NORTH", "SHIELD", "STAY", "STAY"])
        _, memory = observe(module, g)
        self.assertEqual(g.pos[0], 36)
        self.assertEqual(g.frozen[:2], [2, 0])
        self.assertEqual(memory["shield_certain"], {2})
        self.assertEqual(memory["cooldown"][2], 4)
        self.assertEqual(memory["raid_catches"][(2, 36)], 1)

    def test_mutual_shielders_backfire_rather_than_catching_each_other(self):
        module, g = load(), self.game()
        g.pos[:2], g.owner[28], g.owner[27] = [28, 27], 2, 1
        observe(module, g, "SHIELD")
        g.step(["SHIELD", "SHIELD", "STAY", "STAY"])
        _, memory = observe(module, g)
        self.assertEqual(g.frozen[:2], [2, 2])
        self.assertEqual(memory["shield_certain"], {1, 2})
        self.assertEqual(memory["cooldown"][1:3], [4, 4])
        self.assertFalse(memory["raid_catches"])

    def test_stationary_work_and_shield_ambiguity_is_not_forced_into_a_catch(self):
        module, g = load(), self.game()
        g.pos[0], g.owner[28] = 28, 2
        # A cold-start requester could either execute its offered Shield or
        # have it normalized to STAY on hidden cooldown. Public evidence alone
        # must retain both backfire and landlord-catch explanations.
        observe(module, g, "SHIELD")
        g.step(["SHIELD", "STAY", "STAY", "STAY"])
        _, memory = observe(module, g)
        self.assertIn(4, memory["cooldown_possible"][1])
        self.assertIn(0, memory["cooldown_possible"][1])
        self.assertIn(0, memory["cooldown_possible"][2])
        self.assertIn(4, memory["cooldown_possible"][2])
        self.assertNotIn(2, memory["shield_certain"])

    def _prefix_onto_enemy_land(self, module, g):
        for a, b in (("EAST", "WEST"), ("EAST", "STAY"), ("EAST", "SOUTH"),
                     ("EAST", "STAY"), ("EAST", "STAY"), ("EAST", "STAY")):
            observe(module, g, a)
            g.step([a, b, "STAY", "STAY"])
        self.assertEqual(g.pos[0], 6)
        self.assertEqual(g.owner[6], 2)

    def test_known_available_own_shield_remains_certain_when_it_backfires(self):
        module, g = load(), self.game()
        self._prefix_onto_enemy_land(module, g)
        observe(module, g, "SHIELD")
        g.step(["SHIELD", "STAY", "STAY", "STAY"])
        _, memory = observe(module, g)
        self.assertEqual(g.frozen[0], 2)
        self.assertEqual(memory["shield_certain"], {1})
        self.assertEqual(memory["cooldown_possible"][1], {4})
        self.assertEqual(memory["cooldown_possible"][2], {0})

    def test_unfiltered_legal_lists_do_not_allow_known_cooldown_shields(self):
        module, g = load(), self.game()
        self._prefix_onto_enemy_land(module, g)
        observe(module, g, "SHIELD")
        g.step(["SHIELD", "STAY", "STAY", "STAY"])
        for _ in range(4):
            action, memory = observe(module, g, offer_unfiltered=True)
            if g.cd[0] > 0:
                self.assertNotEqual(action, "SHIELD")
            self.assertEqual(memory["cooldown_possible"][1], {g.cd[0]})
            g.step([action, "STAY", "STAY", "STAY"])
        self.assertFalse(memory["shield_legal_filters"])

    def test_cold_start_does_not_invent_availability_from_an_unfiltered_offer(self):
        module, g = load(), self.game()
        g.turn, g.cd[0], g.owner[1] = 34, 3, 1
        for _ in range(4):
            action, memory = observe(module, g, offer_unfiltered=True)
            self.assertIn(g.cd[0], memory["cooldown_possible"][1])
            self.assertNotEqual(action, "SHIELD")
            g.step([action, "STAY", "STAY", "STAY"])
        _, memory = observe(module, g, offer_unfiltered=True)
        self.assertEqual(memory["cooldown_possible"][1], {0})

    def test_public_histories_keep_exact_own_state_and_possible_real_cooldowns(self):
        worst, calls = 0.0, 0
        for case in range(12):
            players = [load() for _ in range(4)]
            g = engine.Game(base=engine.make_map(seed=410033+case), start_token=case%4+1,
                            rules={"catch_requires_stay": True})
            rng = random.Random(82017+case)
            while not g.over():
                actual = []
                for seat, public in enumerate(g.views()):
                    before = signature(public)
                    start = time.perf_counter()
                    action = players[seat].act(public)
                    worst = max(worst, (time.perf_counter()-start)*1000)
                    calls += 1
                    self.assertIn(action, public.legal_actions)
                    self.assertEqual(signature(public), before)
                    memory = players[seat]._history[seat+1]
                    self.assertEqual(memory["turn"], g.turn)
                    self.assertEqual(memory["scores"][1:], g.score)
                    self.assertEqual(memory["progress"], g.prog[seat])
                    self.assertEqual(players[seat]._input_failures, 0)
                    self.assertEqual(players[seat]._policy_failures, 0)
                    self.assertEqual(memory["inference_failures"], 0)
                    for rival in range(4):
                        self.assertIn(g.cd[rival], memory["cooldown_possible"][rival+1])
                    if case >= 6:
                        action = rng.choice(public.legal_actions)
                        memory["last"] = action
                    actual.append(action)
                g.step(actual)
        self.assertEqual(calls, 3840)
        self.assertLess(worst, 200)
        print("Official STAY candidate: 3,840 public calls, exact own oracle, real cooldowns retained; worst %.3f ms" % worst)

    def test_all_home_clock_and_interface_guards_are_retained(self):
        module, g = load(), self.game()
        for turn in range(1, 9):
            public = g.views()[0]
            public.legal_actions = ["STAY"]
            self.assertEqual(module.act(public), "STAY")
            self.assertEqual(module._history[1]["turn"], turn)
            self.assertEqual(module._history[1]["scores"][1:], g.score)
            g.step(["STAY"]*4)
        raw = {"board": [], "bot_id": "1", "legal_actions": ["stay", "east"]}
        self.assertEqual(module.act(raw), "stay")

    def test_standalone_has_no_data_or_dynamic_execution_dependency(self):
        tree = ast.parse(CANDIDATE.read_text())
        imports = {a.name.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
        imports |= {n.module.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
        self.assertEqual(imports, {"collections"})
        self.assertEqual(len([n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "act"]), 1)
        self.assertFalse(any(isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                             and n.func.id in {"open", "print", "input", "exec", "eval", "compile", "__import__"}
                             for n in ast.walk(tree)))


if __name__ == "__main__":
    unittest.main()
