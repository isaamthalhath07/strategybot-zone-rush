"""Metadata and independent public-copy contracts for the isolated profiler."""
import unittest
from unittest import mock

from runtime_bench import pilot
from tests import reference_engine as engine


class RuntimePilotTests(unittest.TestCase):
    def test_metadata_supports_interpreters_without_cpython_gc_controls(self):
        with mock.patch.object(pilot, 'gc', object()):
            value = pilot.metadata()
        self.assertIsNone(value['gc_threshold'])
        self.assertIn(value['implementation'], ('CPython', 'PyPy'))
        self.assertEqual(len(value['executable_sha256']), 64)

    def test_structural_clone_is_private_and_has_only_the_starter_contract(self):
        game = engine.Game()
        for _ in range(4):
            public = game.views()[0]
            copied = pilot.clone_public(public)
            self.assertEqual(pilot.runner.signature(copied), pilot.runner.signature(public))
            self.assertEqual(set(copied.__slots__), {'board', 'bot_id', 'is_priority_token', 'legal_actions'})
            for source_row, copied_row in zip(public.board, copied.board):
                self.assertIsNot(source_row, copied_row)
                for source, target in zip(source_row, copied_row):
                    self.assertIsNot(source, target)
                    self.assertEqual(set(target.__slots__), {'occupant', 'owner', 'is_upgraded', 'is_home', 'is_frozen', 'base_points'})
            copied.board[0][0].owner = 99
            copied.legal_actions.clear()
            self.assertNotEqual(public.board[0][0].owner, 99)
            self.assertTrue(public.legal_actions)
            game.step(['STAY']*4)


if __name__ == '__main__':
    unittest.main()
