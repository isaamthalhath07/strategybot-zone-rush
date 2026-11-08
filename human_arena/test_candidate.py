"""Public-input regressions for the repaired research policy.

Optional uploaded-match tests use historical observations, never a running game.
Private referee values occur only as expected answers in the test harness.
"""
import ast
import copy
import hashlib
import importlib.util
import json
import os
import random
from pathlib import Path
import sys
import types
import unittest

HERE = Path(__file__).resolve().parent
SOURCE = HERE / 'candidates' / 'research_fixed.py'
ORIGINAL = HERE / 'candidates' / 'branch_1dca0c916af4.py'
TRANSCRIPT = Path(os.environ.get('ZONE_RUSH_TRANSCRIPT',
    r'C:\Users\LEGION\Downloads\zone-rush-d3846d56f462413789041954bdc8bc38.json'))
RENEWAL_TRANSCRIPT = Path(os.environ.get('ZONE_RUSH_RENEWAL_TRANSCRIPT',
    r'C:\Users\LEGION\Downloads\zone-rush-a48976861ec94db586fabe314f58fc4a.json'))
sys.path.insert(0, str(HERE / 'vendor_harness'))
import referee


def load(path=SOURCE):
    spec = importlib.util.spec_from_file_location('candidate_test', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def view(observation):
    fields = ('occupant', 'owner', 'is_upgraded', 'is_home', 'is_frozen', 'base_points')
    return types.SimpleNamespace(
        board=[[types.SimpleNamespace(**dict(zip(fields, cell))) for cell in row]
               for row in observation['board']],
        bot_id=observation['bot_id'], is_priority_token=observation['is_priority_token'],
        legal_actions=observation['legal_actions'][:])


def observe(module, game, seat, requested='STAY'):
    public = view(game.observation(seat))
    before = copy.deepcopy(public)
    action = module.act(public)
    assert public == before, 'callback changed its observation'
    assert action in public.legal_actions, action
    module._history[seat]['last'] = requested
    return action, module._history[seat]


class PublicTrackerTests(unittest.TestCase):
    def test_original_snapshot_is_unchanged(self):
        self.assertEqual(hashlib.sha256(ORIGINAL.read_bytes()).hexdigest(),
                         '1dca0c916af4ff4ac4c2e90fabe3f3c29c550c5db61663f8a3c2b0efc72f81ca')

    def test_standalone_stdlib_public_callback(self):
        tree = ast.parse(SOURCE.read_text(encoding='utf-8'))
        self.assertTrue(any(isinstance(node, ast.FunctionDef) and node.name == 'act' for node in tree.body))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                self.assertTrue(all(alias.name.split('.')[0] in sys.stdlib_module_names for alias in node.names))
            if isinstance(node, ast.ImportFrom):
                self.assertFalse(node.level)
                self.assertIn(node.module.split('.')[0], sys.stdlib_module_names)
        module, game = load(), referee.Referee(referee.example_map())
        self.assertIn(module.act(view(game.observation(1))), game.legal(0))

    def test_correctness_release_only_disables_declared_planning_changes(self):
        correctness = HERE / 'candidates' / 'research_correctness.py'
        line = 'CONFIG.update(conditional_postraid_upgrade=False, renewal_guard=False, imminent_shield=False)\n\n'
        self.assertEqual(correctness.read_text(encoding='utf-8').replace(line, ''), SOURCE.read_text(encoding='utf-8'))
        module = load(correctness)
        for key in ('conditional_postraid_upgrade', 'renewal_guard', 'imminent_shield'):
            self.assertFalse(module.CONFIG[key])

    def test_public_random_histories_preserve_progress_and_possible_cooldowns(self):
        for seed in range(6):
            path = SOURCE if seed % 2 else HERE / 'candidates' / 'research_correctness.py'
            modules = {seat: load(path) for seat in range(1, 5)}
            game = referee.Referee(referee.random_map(8100+seed), start_token=seed % 4+1)
            rnd = random.Random(9110+seed)
            while not game.over():
                actions = [rnd.choice(game.legal(index)) for index in range(4)]
                for seat, module in modules.items():
                    _, memory = observe(module, game, seat, actions[seat-1])
                    with self.subTest(seed=seed, turn=game.turn, seat=seat):
                        self.assertEqual(memory['turn'], game.turn)
                        self.assertEqual(memory['progress'], game.prog[seat-1])
                        self.assertEqual(memory['scores'][1:], game.score)
                        for rival in range(1, 5):
                            self.assertIn(game.cd[rival-1], memory['cooldown_possible'][rival])
                            self.assertLessEqual(memory['cooldown'][rival], game.cd[rival-1])
                game.step(actions)

    def test_all_home_stays_preserve_clock_and_finished_progress(self):
        module, game = load(), referee.Referee(referee.example_map())
        for turn in range(1, 9):
            _, memory = observe(module, game, 1)
            self.assertEqual(memory['turn'], turn)
            self.assertEqual(memory['progress'], game.prog[0])
            self.assertEqual(memory['scores'][1:], game.score)
            game.step(['STAY'] * 4)
        self.assertEqual(memory['progress'], 0, 'finished upgraded home has no banked work')

    def test_enemy_land_backfire_not_attributed_to_owner_who_worked(self):
        module, game = load(), referee.Referee(referee.example_map())
        game.pos = [18, 10, 63, 56]
        game.owner[18] = game.owner[10] = 1
        game.prog[0] = 2
        observe(module, game, 2, 'SHIELD')
        game.step(['STAY', 'SHIELD', 'STAY', 'STAY'])
        _, memory = observe(module, game, 2)
        self.assertTrue(game.upg[18], 'owner visibly upgraded instead of shielding')
        self.assertEqual(memory['cooldown'][2], 4)
        self.assertEqual(memory['cooldown'][1], 0)
        self.assertEqual(memory['shield_certain'], {2})
        self.assertEqual(memory['progress'], 0)

    def test_ambiguous_freeze_does_not_invent_defender_cooldown(self):
        module, game = load(), referee.Referee(referee.example_map())
        game.pos = [0, 10, 63, 56]
        game.owner[10] = 1
        game.upg[0] = True
        observe(module, game, 4)
        game.step(['STAY', 'SHIELD', 'STAY', 'STAY'])
        _, memory = observe(module, game, 4)
        self.assertEqual(memory['cooldown'][1], 0)
        self.assertIn(0, memory['cooldown_possible'][1])
        self.assertIn(4, memory['cooldown_possible'][1])
        self.assertNotIn(1, memory['shield_certain'])
        self.assertIn(2, memory['shield_possible'])

    def test_accepted_own_shield_is_known_even_on_enemy_land(self):
        module, game = load(), referee.Referee(referee.example_map())
        game.pos = [18, 10, 63, 56]
        game.owner[10] = 1
        game.owner[18] = 2
        observe(module, game, 2, 'SHIELD')
        game.step(['STAY', 'SHIELD', 'STAY', 'STAY'])
        _, memory = observe(module, game, 2)
        self.assertEqual(memory['cooldown'][2], 4)
        self.assertIn(2, memory['shield_certain'])
        self.assertFalse(game.frozen[1])
        self.assertEqual(memory['progress'], 0)

    def test_shield_request_substituted_with_stay_earns_real_work(self):
        module, game = load(), referee.Referee(referee.example_map())
        observe(module, game, 1, 'SHIELD')
        game.step(['STAY'] * 4)  # e.g. a late callback is replaced by server STAY
        _, memory = observe(module, game, 1)
        self.assertEqual(memory['progress'], 1)
        self.assertEqual(memory['cooldown'][1], 0)
        self.assertNotIn(1, memory['shield_possible'])

    def test_blocked_move_counts_as_stay_without_fabricating_motion(self):
        module, game = load(), referee.Referee(referee.example_map())
        game.pos[1] = 1
        observe(module, game, 1, 'EAST')
        game.step(['EAST', 'STAY', 'STAY', 'STAY'])
        _, memory = observe(module, game, 1)
        self.assertEqual(memory['positions'][1], 0)
        self.assertEqual(memory['progress'], game.prog[0])
        self.assertEqual(memory['progress'], 1)

    def test_completion_window_overrides_empirical_shield_risk(self):
        module = load()
        memory = {'cooldown': [0, 0, 4, 0, 0]}
        frozen = [False] * 5
        exposure = [.87] * 5
        self.assertEqual(module._raid_completion_chance(2, 4, frozen, memory, exposure), 1.)
        self.assertAlmostEqual(module._raid_completion_chance(2, 5, frozen, memory, exposure), .13)
        memory['cooldown'][2] = 0
        frozen[2] = True
        self.assertEqual(module._raid_completion_chance(2, 1, frozen, memory, exposure), 1.)
        self.assertLess(module._raid_completion_chance(2, 3, frozen, memory, exposure), 1.)

    def test_nonimminent_upgraded_intruder_does_not_bait_shield(self):
        module, game = load(), referee.Referee(referee.example_map())
        game.pos = [0, 27, 63, 56]
        game.owner[27], game.upg[27] = 1, True
        game.upg[0] = True
        action, _ = observe(module, game, 1)
        self.assertNotEqual(action, 'SHIELD', 'arrival cannot capture an upgraded cell')
        game.step(['STAY'] * 4)
        action, _ = observe(module, game, 1)
        self.assertNotEqual(action, 'SHIELD', 'one banked stay still cannot finish a three-stay raid')
        game.step(['STAY'] * 4)
        action, memory = observe(module, game, 1)
        self.assertEqual(memory['enemy_progress'][2], 2)
        self.assertEqual(action, 'SHIELD', 'a genuine completion threat must still be defendable')

    @unittest.skipUnless(TRANSCRIPT.exists(), 'optional uploaded match is not available')
    def test_full_public_prefix_has_exact_own_state_and_no_false_safe_windows(self):
        data = json.loads(TRANSCRIPT.read_text(encoding='utf-8'))
        modules = {seat: load() for seat in (2, 3, 4)}
        for record in data['turns']:
            for seat, module in modules.items():
                public = view(record['observations'][str(seat)])
                before = copy.deepcopy(public)
                action = module.act(public)
                self.assertEqual(public, before)
                self.assertIn(action, public.legal_actions)
                memory = module._history[seat]
                with self.subTest(turn=record['turn'], seat=seat):
                    self.assertEqual(memory['turn'], record['turn'])
                    self.assertEqual(memory['progress'], record['before']['prog'][seat-1])
                    self.assertEqual(memory['cooldown'][seat], record['before']['cd'][seat-1])
                    self.assertEqual(memory['scores'][1:], record['before']['score'])
                    for rival in range(1, 5):
                        actual_cd = record['before']['cd'][rival-1]
                        self.assertIn(actual_cd, memory['cooldown_possible'][rival])
                        self.assertLessEqual(memory['cooldown'][rival], actual_cd)
                # Only the actor's own historical requested action is supplied.
                # No hidden game field is passed to the candidate callback.
                module._history[seat]['last'] = record['bots'][seat-1]['chosen']

    @unittest.skipUnless(TRANSCRIPT.exists(), 'optional uploaded match is not available')
    def test_known_renewable_raid_is_aborted_from_public_history(self):
        data = json.loads(TRANSCRIPT.read_text(encoding='utf-8'))
        module = load()
        for record in data['turns'][:42]:
            action = module.act(view(record['observations']['4']))
            if record['turn'] < 42:
                module._history[4]['last'] = record['bots'][3]['chosen']
        memory = module._history[4]
        self.assertGreater(memory['raid_catches'].get((2, 28), 0), 0)
        self.assertEqual(memory['cooldown'][2], 2)
        self.assertNotEqual(action, 'STAY', 'defender recharges before a fresh three-stay raid finishes')
        self.assertNotEqual(memory.get('prior_target'), 28)

    @unittest.skipUnless(RENEWAL_TRANSCRIPT.exists(), 'optional independent renewal match is not available')
    def test_independent_human_renewal_trap_has_a_public_abort(self):
        data = json.loads(RENEWAL_TRANSCRIPT.read_text(encoding='utf-8'))
        module = load()
        seat = data['metadata']['human_seat']
        for record in data['turns'][:70]:
            action = module.act(view(record['observations'][str(seat)]))
            if record['turn'] < 70:
                module._history[seat]['last'] = record['human_action']
        memory = module._history[seat]
        self.assertEqual(memory['positions'][seat], 33)
        self.assertGreater(memory['raid_catches'].get((2, 33), 0), 0)
        self.assertEqual(memory['cooldown'][2], 2)
        self.assertEqual(memory['progress'], 0)
        self.assertNotEqual(action, 'STAY', 'two cooldown turns cannot protect a fresh three-stay raid')
        self.assertNotEqual(memory.get('prior_target'), 33)


if __name__ == '__main__':
    unittest.main(verbosity=2)
