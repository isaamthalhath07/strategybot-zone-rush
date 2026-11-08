"""Presence-SHIELD contracts; historical STAY-only releases stay untouched."""
import ast
import copy
import hashlib
import importlib.util
from pathlib import Path
import random
import sys
import unittest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / 'vendor_harness'))
import referee
sys.path.insert(0, str(HERE))
from test_candidate import view


def load(name='research_presence.py'):
    path = HERE / 'candidates' / name
    spec = importlib.util.spec_from_file_location('presence_candidate', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def game():
    return referee.Referee(referee.example_map(), rules={'catch_requires_stay': False})


def observe(module, current, seat, requested='STAY'):
    observation = view(current.observation(seat))
    unchanged = copy.deepcopy(observation)
    action = module.act(observation)
    assert observation == unchanged
    assert action in observation.legal_actions
    memory = module._history[seat]
    memory['last'] = requested
    return action, memory


class PresenceCandidateTests(unittest.TestCase):
    def test_historical_sources_unchanged(self):
        expected = {
            'research_fixed.py': '1a718fd8b5146f9b6a5796b00a1a7a7993ae17edc66cc17d997b086cfaf83bc6',
            'transfer_fixed.py': 'fe03b8164ed3b4ebd2a04abcdfbb6fa729bdc34dea825088f7e82bf6e5b5ab5e',
        }
        for name, digest in expected.items():
            self.assertEqual(hashlib.sha256((HERE / 'candidates' / name).read_bytes()).hexdigest(), digest)

    def test_t34_move_between_defender_cells_is_caught_and_attributed(self):
        module, current = load(), game()
        current.turn = 34
        current.pos = [36, 7, 63, 56]
        current.owner[36] = current.owner[28] = 2
        observe(module, current, 1, 'NORTH')
        result = current.step(['NORTH', 'SHIELD', 'STAY', 'STAY'])
        _, memory = observe(module, current, 1)
        self.assertEqual(current.pos[0], 28)
        self.assertEqual(current.frozen[0], 2)
        self.assertEqual(memory['positions'][1], 28)
        self.assertEqual(memory['progress'], 0)
        self.assertEqual(memory['shield_certain'], {2})
        self.assertEqual(memory['cooldown'][2], 4)
        self.assertEqual(memory['raid_catches'].get((2, 28)), 1)
        self.assertTrue(any(e['type'] == 'shield' and e['caught'] == [1] for e in result['events']))

    def test_arriving_from_neutral_land_is_also_caught(self):
        module, current = load(), game()
        current.pos = [36, 7, 63, 56]
        current.owner[28] = 2
        observe(module, current, 1, 'NORTH')
        current.step(['NORTH', 'SHIELD', 'STAY', 'STAY'])
        _, memory = observe(module, current, 1)
        self.assertEqual(current.frozen[0], 2)
        self.assertEqual(memory['cooldown'][2], 4)
        self.assertIn(2, memory['shield_certain'])

    def test_leaving_entire_defender_land_baits_a_miss(self):
        module, current = load(), game()
        current.pos = [36, 7, 63, 56]
        current.owner[36] = 2
        observe(module, current, 1, 'NORTH')
        current.step(['NORTH', 'SHIELD', 'STAY', 'STAY'])
        _, memory = observe(module, current, 1)
        self.assertFalse(current.frozen[0])
        self.assertEqual(current.frozen[1], 2)
        self.assertEqual(memory['cooldown'][2], 4)
        self.assertEqual(memory['shield_certain'], {2})

    def test_simultaneous_shielders_can_catch_each_other(self):
        module, current = load(), game()
        current.pos = [28, 27, 63, 56]
        current.owner[28], current.owner[27] = 2, 1
        observe(module, current, 1, 'SHIELD')
        current.step(['SHIELD', 'SHIELD', 'STAY', 'STAY'])
        _, memory = observe(module, current, 1)
        self.assertEqual(current.frozen[:2], [2, 2])
        self.assertEqual(memory['shield_certain'], {1, 2})
        self.assertEqual(memory['cooldown'][1:3], [4, 4])
        self.assertEqual(memory['progress'], 0)

    def test_already_frozen_bot_is_not_caught_again(self):
        module, current = load(), game()
        current.pos = [28, 7, 63, 56]
        current.owner[28], current.frozen[0] = 2, 1
        observe(module, current, 1)
        current.step(['STAY', 'SHIELD', 'STAY', 'STAY'])
        _, memory = observe(module, current, 1)
        self.assertEqual(current.frozen[0], 0)
        self.assertEqual(current.frozen[1], 2)
        self.assertEqual(memory['cooldown'][2], 4)
        self.assertEqual(memory['progress'], 0)

    def test_moving_within_land_is_learned_as_retention(self):
        module, current = load(), game()
        current.pos = [36, 7, 63, 56]
        current.owner[36] = current.owner[28] = 2
        _, memory = observe(module, current, 2)
        prior = memory['stay_hits'][1][0] / memory['stay_trials'][1][0]
        current.step(['NORTH', 'STAY', 'STAY', 'STAY'])
        _, memory = observe(module, current, 2)
        posterior = memory['stay_hits'][1][0] / memory['stay_trials'][1][0]
        self.assertGreater(posterior, prior)

    def test_all_endpoints_owned_means_certain_presence(self):
        module, current = load(), game()
        current.pos = [27, 7, 63, 56]
        for p in (27, 19, 28, 35, 26):
            current.owner[p] = 2
        _, memory = observe(module, current, 2)
        obs = view(current.observation(2))
        cells = [cell for row in obs.board for cell in row]
        self.assertEqual(module._presence_chance(1, 2, cells, memory['positions'], memory), 1.0)

    def test_adjacent_arrival_is_forecast_without_pending_action(self):
        module, current = load(), game()
        current.pos = [36, 7, 63, 56]
        current.owner[28] = 2
        _, memory = observe(module, current, 2)
        obs = view(current.observation(2))
        cells = [cell for row in obs.board for cell in row]
        probability = module._presence_chance(1, 2, cells, memory['positions'], memory)
        self.assertGreater(probability, 0.)
        self.assertLess(probability, 1.)

    def test_arrival_and_capture_need_full_cooldown_window(self):
        module = load()
        memory, frozen, exposure = {'cooldown': [0, 0, 1, 0, 0]}, [False]*5, [.8]*5
        # One move onto enemy land, then one capture stay: CD1 protects only
        # the arrival, whereas CD2 protects both resolved turns.
        self.assertLess(module._raid_completion_chance(2, 2, frozen, memory, exposure), 1.)
        memory['cooldown'][2] = 2
        self.assertEqual(module._raid_completion_chance(2, 2, frozen, memory, exposure), 1.)

    def test_renewal_abort_leaves_entire_owner_land_when_possible(self):
        module, current = load(), game()
        current.pos = [27, 7, 63, 56]
        current.owner[27], current.upg[27] = 2, True
        for p in (19, 28, 35):
            current.owner[p], current.base[p] = 2, 3
        current.base[26] = 1
        observe(module, current, 1, 'STAY')
        current.step(['STAY', 'SHIELD', 'STAY', 'STAY'])
        for _ in range(2):
            observe(module, current, 1, 'STAY')
            current.step(['STAY']*4)
        action, memory = observe(module, current, 1)
        self.assertEqual(memory['cooldown'][2], 2)
        self.assertGreater(memory['raid_catches'].get((2, 27), 0), 0)
        self.assertEqual(action, 'WEST', 'north/east/south remain on the same active defender land')
        self.assertNotEqual(current.owner[current.target(27, action)], 2)

    def test_seeded_presence_histories_keep_real_cooldowns_possible(self):
        for seed in range(12):
            name = 'research_presence.py' if seed % 2 else 'transfer_presence.py'
            modules = {seat: load(name) for seat in range(1, 5)}
            current = referee.Referee(referee.random_map(23100+seed),
                rules={'catch_requires_stay': False}, start_token=seed % 4+1)
            rnd = random.Random(62410+seed)
            while not current.over():
                actions = [rnd.choice(current.legal(index)) for index in range(4)]
                for seat, module in modules.items():
                    _, memory = observe(module, current, seat, actions[seat-1])
                    with self.subTest(seed=seed, turn=current.turn, seat=seat):
                        self.assertEqual(memory['turn'], current.turn)
                        self.assertEqual(memory['progress'], current.prog[seat-1])
                        self.assertEqual(memory['scores'][1:], current.score)
                        for rival in range(1, 5):
                            self.assertIn(current.cd[rival-1], memory['cooldown_possible'][rival])
                            self.assertLessEqual(memory['cooldown'][rival], current.cd[rival-1])
                current.step(actions)

    def test_presence_pair_has_identical_code_and_preserved_weights(self):
        trees, configs = [], []
        for name in ('research_presence.py', 'transfer_presence.py'):
            path = HERE / 'candidates' / name
            tree = ast.parse(path.read_text(encoding='utf-8'))
            assignment = next(node for node in tree.body if isinstance(node, ast.Assign)
                and any(isinstance(t, ast.Name) and t.id == 'CONFIG' for t in node.targets))
            configs.append(ast.literal_eval(assignment.value))
            tree.body.remove(assignment)
            trees.append(ast.dump(tree, include_attributes=False))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    self.assertTrue(all(a.name.split('.')[0] in sys.stdlib_module_names for a in node.names))
                if isinstance(node, ast.ImportFrom):
                    self.assertFalse(node.level)
                    self.assertIn(node.module.split('.')[0], sys.stdlib_module_names)
        self.assertEqual(trees[0], trees[1])
        self.assertEqual(configs[0], load('research_fixed.py').CONFIG)
        self.assertEqual(configs[1], load('transfer_fixed.py').CONFIG)


if __name__ == '__main__':
    unittest.main(verbosity=2)
