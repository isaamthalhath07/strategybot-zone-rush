"""Public-input and rule regressions for the smaller presence-rule candidate."""
import ast
import copy
import importlib.util
from pathlib import Path
import unittest
try:
    from .test_presence_candidate import game, observe, view
    from . import test_presence_candidate as reference
except ImportError:
    from test_presence_candidate import game, observe, view
    import test_presence_candidate as reference

HERE = Path(__file__).resolve().parent


def load():
    path = HERE / "candidates/transfer_presence_core.py"
    spec = importlib.util.spec_from_file_location("presence_core_contract", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class CorePresenceTests(unittest.TestCase):
    def test_presence_bookkeeping_and_existing_weights_are_preserved(self):
        actual = ast.parse((HERE/"candidates/transfer_presence_core.py").read_text())
        expected = ast.parse((HERE/"candidates/transfer_presence.py").read_text())
        names = {"_infer_shields", "_observe", "_presence_chance", "_work_needed", "_raid_completion_chance", "choose_terminal"}
        for name in names:
            a = next(n for n in actual.body if isinstance(n,ast.FunctionDef) and n.name==name)
            b = next(n for n in expected.body if isinstance(n,ast.FunctionDef) and n.name==name)
            self.assertEqual(ast.dump(a,include_attributes=False),ast.dump(b,include_attributes=False))
        self.assertEqual(load().CONFIG, reference.load("transfer_fixed.py").CONFIG)

    def test_moving_rival_and_mutual_shields_have_correct_cooldowns(self):
        module, current = load(), game()
        current.pos = [36,7,63,56]
        current.owner[36] = current.owner[28] = 2
        observe(module,current,1,"NORTH")
        current.step(["NORTH","SHIELD","STAY","STAY"])
        _, memory = observe(module,current,1)
        self.assertEqual(current.frozen[0],2)
        self.assertEqual(memory["cooldown"][2],4)
        self.assertEqual(memory["progress"],0)
        module, current = load(), game()
        current.pos[:2] = [28,27]
        current.owner[28],current.owner[27] = 2,1
        observe(module,current,1,"SHIELD")
        current.step(["SHIELD","SHIELD","STAY","STAY"])
        _, memory = observe(module,current,1)
        self.assertEqual(memory["shield_certain"],{1,2})
        self.assertEqual(memory["cooldown"][1:3],[4,4])

    def test_actual_core_selfplay_is_legal_immutable_and_tracks_real_state(self):
        for token in (1,3):
            current = game()
            current.token = token
            modules = [load() for _ in range(4)]
            while not current.over():
                actions = []
                for s,module in enumerate(modules,1):
                    public = view(current.observation(s))
                    before = copy.deepcopy(public)
                    action = module.act(public)
                    self.assertEqual(public,before)
                    self.assertIn(action,public.legal_actions)
                    memory = module._history[s]
                    self.assertEqual(memory["turn"],current.turn)
                    self.assertEqual(memory["scores"][1:],current.score)
                    self.assertEqual(memory["progress"],current.prog[s-1])
                    for rival in range(1,5):
                        self.assertIn(current.cd[rival-1],memory["cooldown_possible"][rival])
                    actions.append(action)
                current.step(actions)


if __name__ == "__main__":
    unittest.main()
