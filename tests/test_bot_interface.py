"""Rule and public-interface regressions for the guarded presence candidate."""
import ast
import copy
from enum import Enum
import importlib.util
import json
from pathlib import Path
import sys
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tests import reference_engine as engine


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT/path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def guarded():
    return load('guarded_contract', 'bot.py')


def signature(public):
    board = public.board
    cells = [c for row in board for c in row] if len(board) == 8 else board
    return (public.bot_id, public.is_priority_token, tuple(public.legal_actions),
            tuple((c.occupant,c.owner,c.is_upgraded,c.is_home,c.is_frozen,c.base_points) for c in cells))


class GuardedCandidateTests(unittest.TestCase):

    def test_flat_dictionary_string_inputs_match_public_objects(self):
        public=engine.Game(base=[3]*64,rules={'catch_requires_stay':True}).views()[0]
        expected=guarded().act(public)
        raw={'bot_id':'1','is_priority_token':'true','legal_actions':[a.lower() for a in public.legal_actions],
             'board':[dict(occupant=str(c.occupant),owner=str(c.owner),base_points=str(c.base_points),
                       is_upgraded=str(c.is_upgraded).lower(),is_home=str(c.is_home).lower(),
                       is_frozen=str(c.is_frozen).lower()) for row in public.board for c in row]}
        before=copy.deepcopy(raw)
        actual=guarded().act(raw)
        self.assertEqual(actual,expected.lower())
        self.assertEqual(raw,before)

    def test_original_enum_action_object_is_returned(self):
        actions=Enum('Action','NORTH EAST SOUTH WEST STAY SHIELD')
        public=engine.Game(base=[3]*64,rules={'catch_requires_stay':True}).views()[0]
        expected=guarded().act(public)
        public.legal_actions=[getattr(actions,name) for name in public.legal_actions]
        actual=guarded().act(public)
        self.assertIs(actual,getattr(actions,expected))

    def test_failed_home_completion_stops_retrying_unsupported_upgrade(self):
        current=engine.Game(base=[3 if p in (0,7,56,63) else 1 for p in range(64)],
                            rules={'catch_requires_stay':True,'home_upgradable':False})
        candidate=guarded(); actions=[]
        for _ in range(8):
            public=current.views()[0]
            action=candidate.act(public); actions.append(action)
            current.step([action,'STAY','STAY','STAY'])
        self.assertEqual(actions[:3],['STAY']*3)
        self.assertIn(actions[3],('EAST','SOUTH'))
        self.assertIn(0,candidate._history[1]['failed_jobs'])
        self.assertNotEqual(current.pos[0],0)
        self.assertEqual(candidate._policy_failures,0)

    def test_invalid_public_shape_uses_legal_fallback(self):
        candidate=guarded()
        self.assertEqual(candidate.act({'board':[],'bot_id':1,'legal_actions':['stay','east']}),'stay')
        self.assertEqual(candidate._input_failures,1)
        self.assertEqual(candidate._policy_failures,0)

    def test_stdlib_only_no_io_or_dynamic_execution(self):
        tree=ast.parse((ROOT/'bot.py').read_text())
        imports={a.name.split('.')[0] for n in ast.walk(tree) if isinstance(n,ast.Import) for a in n.names}
        imports|={n.module.split('.')[0] for n in ast.walk(tree) if isinstance(n,ast.ImportFrom)}
        self.assertLessEqual(imports,{'collections'})
        self.assertFalse(any(isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id in
                             {'print','open','input','exec','eval','compile','__import__'} for n in ast.walk(tree)))


if __name__=='__main__':
    unittest.main()
