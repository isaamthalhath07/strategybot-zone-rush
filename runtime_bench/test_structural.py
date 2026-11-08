"""Shape boundaries, snapshot privacy and exact experimental-runner provenance."""
import ast
import copy
import hashlib
from pathlib import Path
import tempfile
import unittest

from evolution import runner as frozen
from runtime_bench import structural_runner_v1 as experimental
from runtime_bench import build_structural_runner as builder
from runtime_bench.public_copy_v1 import clone_public
from tests import reference_engine as engine

ROOT = Path(__file__).resolve().parents[1]


class StructuralCopyTests(unittest.TestCase):
    def test_exact_function_copy_with_one_public_copy_call_change(self):
        original = (ROOT/'evolution/runner.py').read_bytes()
        self.assertEqual(hashlib.sha256(original).hexdigest(), builder.EXPECTED)
        first = {node.name: ast.get_source_segment(original.decode(), node) for node in ast.parse(original).body
                 if isinstance(node, ast.FunctionDef) and node.name in builder.NAMES}
        text = (ROOT/'runtime_bench/structural_runner_v1.py').read_text()
        second = {node.name: ast.get_source_segment(text, node) for node in ast.parse(text).body
                  if isinstance(node, ast.FunctionDef) and node.name in builder.NAMES}
        self.assertEqual(set(first), set(second))
        for name in first:
            restored = second[name].replace('view = clone_public(view)', 'view = copy.deepcopy(view)')
            self.assertEqual(first[name], restored)
        self.assertIsNot(frozen._CODE, experimental._CODE)

    def test_all_public_values_equal_generic_deepcopy_over_an80_turn_history(self):
        game = engine.Game(base=engine.make_map(77231))
        for turn in range(80):
            for view in game.views():
                expected, actual = copy.deepcopy(view), clone_public(view)
                self.assertEqual(frozen.signature(expected), frozen.signature(actual))
                self.assertIs(type(expected), type(actual))
                for left, right in zip(expected.board, actual.board):
                    for a, b in zip(left, right):
                        self.assertIs(type(a), type(b))
                        for slot in a.__slots__:
                            self.assertIs(type(getattr(a, slot)), type(getattr(b, slot)))
            game.step(['STAY']*4 if turn % 5 else ['SHIELD']*4)

    def test_retained_and_modified_actor_views_do_not_alias_any_future_or_rival_view(self):
        game = engine.Game()
        saved = []
        for _ in range(10):
            raw = game.views()
            left, right = clone_public(raw[0]), clone_public(raw[1])
            before = frozen.signature(right)
            prior_signature = frozen.signature(raw[0])
            if saved:
                old = saved[-1]
                old.board[0][0].owner = 99
                old.board[0].clear()
                old.legal_actions.clear()
                old.bot_id = 4
            self.assertEqual(frozen.signature(raw[0]), prior_signature)
            self.assertEqual(frozen.signature(right), before)
            self.assertEqual(frozen.signature(left), prior_signature)
            left.board[1][1].base_points = 99
            self.assertNotEqual(raw[0].board[1][1].base_points, 99)
            self.assertNotEqual(right.board[1][1].base_points, 99)
            for row, copied in zip(raw[0].board, left.board):
                self.assertIsNot(row, copied)
                for original_cell, cloned_cell in zip(row, copied):
                    self.assertIsNot(original_cell, cloned_cell)
            saved.append(left)
            game.step(['STAY']*4)

    def test_noncanonical_shapes_domains_and_alias_graphs_fail_closed(self):
        factories = [lambda v: {'board': v.board},
                     lambda v: engine.View([], v.bot_id, v.is_priority_token, v.legal_actions),
                     lambda v: engine.View([row for row in v.board[:-1]], 1, True, ['STAY']),
                     lambda v: engine.View(v.board, True, True, ['STAY']),
                     lambda v: engine.View(v.board, 1, 1, ['STAY']),
                     lambda v: engine.View(v.board, 1, True, []),
                     lambda v: engine.View(v.board, 1, True, ['TELEPORT']),
                     lambda v: engine.View(v.board, 1, True, ('STAY',))]
        for make in factories:
            with self.assertRaises((TypeError, ValueError)):
                clone_public(make(engine.Game().views()[0]))
        for slot, value in [('occupant', True), ('owner', 5), ('base_points', 0),
                            ('is_upgraded', 1), ('is_home', 'false'), ('is_frozen', 0)]:
            public = engine.Game().views()[0]
            setattr(public.board[0][0], slot, value)
            with self.assertRaises((TypeError, ValueError)):
                clone_public(public)
        public = engine.Game().views()[0]
        public.board[0][1] = public.board[0][0]
        with self.assertRaises(TypeError):
            clone_public(public)
        public = engine.Game().views()[0]
        public.board[1] = public.board[0]
        with self.assertRaises(ValueError):
            clone_public(public)

    def test_input_mutation_rejected_and_retained_view_mutation_remains_isolated_in_both_runners(self):
        cache = ROOT/'.cache/runtime_bench'
        cache.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='negative-actors-', dir=cache) as name:
            path = Path(name)/'actor.py'
            specs = [dict(seat=seat, family='farmer', seed=seat, epsilon=.2, commitment=.5,
                          id='test_rival_%d' % seat) for seat in range(1, 4)]
            fixture = dict(base=engine.make_map(298), seat=0, token=1, id='isolation_test',
                           map_id='test_map', field='negative_test_only', opponents=specs)
            path.write_text("def act(view):\n    view.board[0][0].owner = 99\n    return 'STAY'\n")
            candidate = dict(path=str(path), sha256=hashlib.sha256(path.read_bytes()).hexdigest())
            for backend in (frozen, experimental):
                with self.assertRaisesRegex(ValueError, 'input mutation'):
                    backend.play_game(candidate, fixture, {})
            path.write_text("saved = []\ndef act(view):\n    if saved:\n        saved[-1].board[0][0].owner = 99\n        saved[-1].legal_actions.clear()\n    saved.append(view)\n    return 'STAY'\n")
            candidate['sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
            first = frozen.play_game(candidate, fixture, {})
            second = experimental.play_game(candidate, fixture, {})
            self.assertEqual(first['actions'], second['actions'])
            self.assertEqual(first['scores'], second['scores'])
            self.assertEqual(first['faults'], [])
            self.assertEqual(second['faults'], [])


if __name__ == '__main__':
    unittest.main()
