"""Independent public-only memory controls; never campaign/strength evidence."""
import random
import unittest

from evolution.oversight import referee, signature, state_equal
from strategy_candidates.test_public_memory import CORRECTED, observe, path
from tests import reference_engine as engine


class IndependentMemoryTests(unittest.TestCase):
    def test_own_shield_immunity_does_not_disprove_another_owners_shield(self):
        game, (_, fixed), _ = observe(path(own_final='SHIELD', defender_final='SHIELD',
                                         raider_final='STAY'), 0)
        self.assertEqual(game.frozen[:3], [2, 2, 0])
        self.assertEqual(game.cd[:3], [4, 0, 4])
        self.assertEqual(fixed.last_shield[1], 25)
        self.assertEqual(fixed.last_shield[3], 25)
        self.assertEqual(fixed.prog, 0)
        self.assertFalse(fixed._can_shield(3, 29))
        self.assertTrue(fixed._can_shield(3, 30))

    def test_already_frozen_observer_does_not_disprove_a_new_catch(self):
        actions = path(own_final='SHIELD', raider_final='STAY')
        # Fortify cell6 before leaving it; the other rival's first STAY must
        # leave the land owned by player3 for the following Shield.
        actions[9][2] = 'STAY'
        actions[12][2] = 'WEST'
        actions.append(['STAY', 'STAY', 'SHIELD', 'STAY'])
        game, (_, fixed), _ = observe(actions, 0)
        self.assertEqual(game.frozen[:3], [1, 2, 0])
        self.assertEqual(fixed.last_shield[3], 26)
        self.assertEqual(fixed.prog, game.prog[0])

    def test_forward_progress_and_scores_over_random_legal_public_histories(self):
        # Scripted accepted actions isolate memory, not planner strength. Truth
        # is inspected only by this test AFTER a four-field public observation.
        for seed in range(24):
            rng = random.Random(0x55A17+seed)
            game = engine.Game(base=engine.make_map(seed=seed), start_token=1+seed % 4,
                               rules={'catch_requires_stay': True})
            shadow = referee.Referee(game.base, start_token=game.token, rules=game.rules)
            trackers = [CORRECTED(seed=seat+1) for seat in range(4)]
            for step in range(81):
                views = game.views()
                for seat, view in enumerate(views):
                    before = signature(view)
                    trackers[seat]._observe(view)
                    self.assertEqual(signature(view), before)
                    self.assertEqual(trackers[seat].prog, game.prog[seat], (seed, step, seat))
                    self.assertEqual([trackers[seat].score[s] for s in range(1, 5)], game.score,
                                     (seed, step, seat))
                if step == 80:
                    break
                joint = []
                for seat, view in enumerate(views):
                    choices = list(view.legal_actions)+['STAY']*4
                    if 'SHIELD' in view.legal_actions:
                        choices += ['SHIELD']*2
                    action = rng.choice(choices)
                    trackers[seat].last = action
                    joint.append(action)
                game.step(joint)
                shadow.step(joint)
                state_equal(game, shadow)


if __name__ == '__main__':
    unittest.main()
