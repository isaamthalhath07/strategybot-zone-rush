"""Recover only own-cast substitutions excluded by observable physics."""
import unittest

from tests import reference_engine as engine
from tests import test_official_candidate as public


class RejectedShieldTests(unittest.TestCase):
    def game(self):
        return engine.Game(base=[2]*64, rules={"catch_requires_stay": True})

    def advance(self, module, game, actions):
        public.observe(module, game, actions[0])
        game.step(actions)

    def assert_recovered(self, module, game, own_cd=0, shielders=None):
        _, memory = public.observe(module, game)
        self.assertEqual(memory["turn"], game.turn)
        self.assertEqual(memory["scores"][1:], game.score)
        self.assertEqual(memory["progress"], game.prog[0])
        self.assertEqual(memory["cooldown_possible"][1], {own_cd})
        self.assertEqual(memory["shield_certain"], shielders or set())
        self.assertTrue(memory["own_action_substituted"])
        self.assertEqual(memory["last_effective"], "STAY")
        self.assertEqual(memory["inference_failures"], 0)
        self.assertEqual(module._policy_failures, 0)
        return memory

    def test_rejected_empty_shield_advances_incomplete_own_work_without_fake_cooldown(self):
        module, game = public.load(), self.game()
        public.observe(module, game, "SHIELD")
        game.step(["STAY"]*4)
        memory = self.assert_recovered(module, game)
        self.assertEqual(memory["progress"], 1)
        self.assertIsNone(memory["shield_legal_filters"], "a rejected cast cannot prove an unfiltered list")

    def test_rejected_shield_can_complete_own_upgrade(self):
        module, game = public.load(), self.game()
        for _ in range(2):
            self.advance(module, game, ["STAY"]*4)
        public.observe(module, game, "SHIELD")
        game.step(["STAY"]*4)
        self.assert_recovered(module, game)
        self.assertTrue(game.upg[0])
        self.assertEqual(game.prog[0], 0)

    def test_rejected_shield_can_claim_neutral_land(self):
        module, game = public.load(), self.game()
        self.advance(module, game, ["EAST", "STAY", "STAY", "STAY"])
        public.observe(module, game, "SHIELD")
        game.step(["STAY"]*4)
        self.assert_recovered(module, game)
        self.assertEqual(game.owner[1], 1)
        self.assertEqual(game.prog[0], 0)

    def onto_upgraded_enemy_land(self, module, game):
        for actions in (("EAST", "WEST"), ("EAST", "STAY"), ("EAST", "STAY"),
                        ("EAST", "STAY"), ("EAST", "STAY"), ("STAY", "SOUTH"),
                        ("EAST", "STAY")):
            self.advance(module, game, list(actions)+["STAY", "STAY"])
        self.assertEqual(game.pos[0], 6)
        self.assertEqual(game.owner[6], 2)
        self.assertTrue(game.upg[6])

    def test_rejected_shield_can_advance_an_incomplete_upgraded_raid(self):
        module, game = public.load(), self.game()
        self.onto_upgraded_enemy_land(module, game)
        public.observe(module, game, "SHIELD")
        game.step(["STAY"]*4)
        memory = self.assert_recovered(module, game)
        self.assertEqual(memory["progress"], 1)
        self.assertEqual(game.owner[6], 2)

    def test_rejected_shield_can_complete_an_upgraded_raid(self):
        module, game = public.load(), self.game()
        self.onto_upgraded_enemy_land(module, game)
        for _ in range(2):
            self.advance(module, game, ["STAY"]*4)
        public.observe(module, game, "SHIELD")
        game.step(["STAY"]*4)
        self.assert_recovered(module, game)
        self.assertEqual(game.owner[6], 1)
        self.assertFalse(game.upg[6])

    def test_lost_holding_proves_rejected_own_cast_and_opponent_catch(self):
        module, game = public.load(), self.game()
        # Entire prefix is legal public play. Seat3 reaches our claimed C1
        # equivalent while we circle on seat2's land. Losing that holding is
        # incompatible with our active global protection, so our requested
        # Shield provably did not execute.
        prefix = [
            ("EAST", "WEST", "NORTH"), ("EAST", "STAY", "NORTH"),
            ("EAST", "SOUTH", "NORTH"), ("EAST", "STAY", "NORTH"),
            ("EAST", "STAY", "NORTH"), ("STAY", "STAY", "NORTH"),
            ("EAST", "STAY", "NORTH"), ("WEST", "SOUTH", "SOUTH"),
            ("EAST", "STAY", "WEST"), ("EAST", "STAY", "WEST"),
            ("WEST", "STAY", "NORTH"),
        ]
        for actions in prefix:
            self.advance(module, game, list(actions)+["STAY"])
        self.assertEqual(game.pos[:3], [6, 22, 5])
        self.assertEqual(game.owner[5], 1)
        self.assertEqual(game.owner[6], 2)
        public.observe(module, game, "SHIELD")
        game.step(["STAY", "SHIELD", "STAY", "STAY"])
        memory = self.assert_recovered(module, game, shielders={2})
        self.assertEqual(game.frozen[0], 2)
        self.assertEqual(game.owner[5], 3)
        self.assertEqual(memory["cooldown_possible"][2], {4})


if __name__ == "__main__":
    unittest.main()
