"""Legal dual-referee counterexamples, with truth used by the observer only."""
import copy
from pathlib import Path
import unittest

from evolution.oversight import signature, referee, state_equal
from tests import reference_engine as engine
from strategy_candidates import build_public_memory as builder


def load(body, name):
    namespace = {'__name__': name}
    exec(compile(body, name, 'exec'), namespace)
    return namespace['BlockerBot']


ORIGINAL = load((builder.ROOT/'tester_bots/blocker.py').read_bytes(), 'original_blocker_memory')
CORRECTED = load(builder.build(), 'corrected_blocker_memory')


def path(own_final='STAY', defender_final='STAY', raider_final='SHIELD'):
    """All four actions on every turn are legal before simultaneous execution."""
    defender = (['NORTH']*6 + ['WEST', 'NORTH', 'STAY', 'WEST']
                + ['STAY']*4 + ['SOUTH'] + ['STAY']*10)
    actions = []
    for turn in range(1, 26):
        a = 'STAY' if turn < 20 else 'EAST' if turn < 25 else own_final
        b = ('STAY' if turn < 20 else
             {20: 'WEST', 21: 'SOUTH', 22: 'NORTH', 23: 'SOUTH', 24: 'NORTH',
              25: raider_final}[turn])
        c = defender[turn-1] if turn < 25 else defender_final
        actions.append([a, b, c, 'STAY'])
    return actions


def observe(actions, seat):
    game = engine.Game(rules={'catch_requires_stay': True})
    shadow = referee.Referee(game.base, start_token=game.token, rules=game.rules)
    trackers = (ORIGINAL(seed=7919*(seat+1)), CORRECTED(seed=7919*(seat+1)))
    public = []
    for joint in actions:
        views = game.views()
        for index, action in enumerate(joint):
            if action not in views[index].legal_actions:
                raise AssertionError('Scripted action was illegal')
        view = views[seat]
        public.append((signature(view), joint[seat]))
        for tracker in trackers:
            # This isolates the state tracker. The scripted own action, rather
            # than a planner recommendation, is the action actually accepted.
            before = signature(view)
            tracker._observe(copy.deepcopy(view))
            tracker.last = joint[seat]
            if signature(view) != before:
                raise AssertionError('Public input changed')
        game.step(joint)
        shadow.step(joint)
        state_equal(game, shadow)
    view = game.views()[seat]
    public.append((signature(view), None))
    for tracker in trackers:
        tracker._observe(copy.deepcopy(view))
    return game, trackers, public


class PublicMemoryTests(unittest.TestCase):
    def test_generated_standalone_matches_the_pinned_builder(self):
        self.assertEqual((Path(__file__).parent/'blocker_public_memory.py').read_bytes(), builder.build())

    def test_backfire_elsewhere_does_not_erase_own_progress_or_invent_owner_cooldown(self):
        game, (old, fixed), _ = observe(path(), 0)
        self.assertEqual(game.pos[:3], [5, 6, 13])
        self.assertEqual(game.frozen, [0, 2, 0, 0])
        self.assertEqual(game.cd[2], 0)
        self.assertEqual(game.prog[0], 1)
        self.assertEqual(old.prog, 0)  # Explicit regression reproduction.
        self.assertFalse(old._can_shield(3, 26))
        self.assertEqual(fixed.prog, game.prog[0])
        self.assertTrue(fixed._can_shield(3, 26))

    def test_blocked_move_is_stay_and_still_proves_owner_did_not_shield(self):
        game, (_, fixed), _ = observe(path(own_final='EAST'), 0)
        self.assertEqual(game.pos[0], 5)  # East lost to the occupant on cell6.
        self.assertEqual(game.prog[0], 1)
        self.assertEqual(fixed.prog, 1)
        self.assertTrue(fixed._can_shield(3, 26))

    def test_publicly_moved_landowner_cannot_have_cast_a_shield(self):
        game, (old, fixed), _ = observe(path(defender_final='EAST'), 3)
        self.assertEqual(game.pos[2], 14)
        self.assertFalse(old._can_shield(3, 26))
        self.assertTrue(fixed._can_shield(3, 26))

    def test_own_known_nonshield_action_is_not_replaced_by_a_guess(self):
        game, (old, fixed), _ = observe(path(own_final='WEST'), 2)
        self.assertEqual(game.cd[2], 0)
        self.assertEqual(old.last_shield[3], 25)
        self.assertEqual(fixed.last_shield[3], -99)
        self.assertTrue(fixed._can_shield(3, 26))

    def test_publicly_indistinguishable_backfire_and_enemy_shield_stay_indistinguishable(self):
        left, (_, a), public_a = observe(path(own_final='WEST'), 0)
        right, (_, b), public_b = observe(path(own_final='WEST', defender_final='SHIELD',
                                               raider_final='STAY'), 0)
        self.assertEqual(public_a, public_b)
        self.assertNotEqual(left.cd, right.cd)  # Hidden truth differs.
        self.assertEqual(a.__dict__, b.__dict__ | {'rng': a.rng})
        va, vb = left.views()[0], right.views()[0]
        self.assertEqual(a._decide(va), b._decide(vb))


if __name__ == '__main__':
    unittest.main()
