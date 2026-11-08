"""Infer hidden history solely from recorded public transitions."""
import copy
import importlib.util
from pathlib import Path
import random
from types import SimpleNamespace
import unittest
from simulator import server

ROOT=Path(__file__).resolve().parents[1]
referee=server.bootstrap()[1]
def load():
    spec=importlib.util.spec_from_file_location('submission_inference',ROOT/'bot.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module

def view(observation):
    fields=('occupant','owner','is_upgraded','is_home','is_frozen','base_points')
    return SimpleNamespace(board=[[SimpleNamespace(**dict(zip(fields,cell))) for cell in row] for row in observation['board']],
        bot_id=observation['bot_id'],is_priority_token=observation['is_priority_token'],legal_actions=observation['legal_actions'][:])
def game():return referee.Referee(referee.example_map(),rules={'catch_requires_stay':False})
def observe(module,current,seat,requested='STAY'):
    public=view(current.observation(seat));before=copy.deepcopy(public);action=module.act(public)
    assert public==before and action in public.legal_actions
    memory=module._history[seat];memory['last']=requested
    return action,memory

class PresenceCandidateTests(unittest.TestCase):

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
            modules = {seat: load() for seat in range(1, 5)}
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



if __name__ == '__main__':
    unittest.main(verbosity=2)
