"""Reachable defense trap and conservative public-uncertainty boundaries."""
import copy
from pathlib import Path
import unittest

from evolution import mathematical_probes as probes
from evolution.runner import signature
from tests import reference_engine as engine

HERE = Path(__file__).parent


def replay(path, proof):
    module = probes.load(path)
    game = engine.Game(base=proof['base'], start_token=proof['initial_token'])
    for joint in proof['prefix']:
        module.act(game.views()[0])
        module._history[1]['last'] = joint[0]
        game.step(joint)
    return module, game


class AvailabilityTests(unittest.TestCase):
    def test_reachable_trap_retains_defense_before_the_landlord_can_remove_it(self):
        proof = probes.anticipatory_shield_counterexample()
        self.assertEqual(proof['incumbent_action'], 'STAY')
        for name in ('availability_only.py', 'arrival_and_availability.py'):
            module, game = replay(HERE/name, proof)
            public = game.views()[0]
            before = signature(public)
            action = module.act(public)
            self.assertEqual(action, 'SHIELD')
            self.assertEqual(signature(public), before)
            memory = module._history[1]
            self.assertEqual(memory['enemy_progress'][3], 1)
            self.assertEqual(memory['cooldown_possible'][2], {0})
            self.assertEqual(memory['scores'][1:], game.score)
            self.assertEqual(memory['progress'], game.prog[0])
            self.assertFalse(memory['inference_failures'])
            game.step([action, 'SHIELD', 'STAY', 'STAY'])
            game.step(['STAY']*4)
            self.assertEqual(game.owner[18], 1)
            self.assertGreater(game.score[0], game.score[2])
            self.assertFalse(module._policy_failures)

    def test_trigger_requires_certain_readiness_and_no_free_escape(self):
        proof = probes.anticipatory_shield_counterexample()
        module, game = replay(HERE/'availability_only.py', proof)
        module.act(game.views()[0])
        memory = module._history[1]
        owner = game.owner[:]
        frozen = [False]+[bool(value) for value in game.frozen]
        occupied = {p for i, p in enumerate(game.pos) if i != 0}
        legal = game.legal(0)
        self.assertTrue(module._future_defense_at_risk(1, game.pos[0], owner, frozen, memory, occupied, legal))
        uncertain = copy.deepcopy(memory)
        uncertain['cooldown_possible'][2] = {0, 1}
        self.assertFalse(module._future_defense_at_risk(1, game.pos[0], owner, frozen, uncertain, occupied, legal))
        self.assertFalse(module._future_defense_at_risk(1, game.pos[0], owner, frozen, memory, set(), legal))
        frozen[2] = True
        self.assertFalse(module._future_defense_at_risk(1, game.pos[0], owner, frozen, memory, occupied, legal))


if __name__ == '__main__':
    unittest.main()
