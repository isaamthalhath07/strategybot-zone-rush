"""Exact deterministic equivalence and adversarial information-boundary checks."""
import copy
from dataclasses import fields
import inspect
import unittest
from unittest.mock import patch

import torch

from search_coach.belief import PublicObservation
from search_coach.gpu_batch import PublicPolicyBatch, _public_adapter, _tensor_state
from tests import reference_engine as ref
from . import protocol, scalar, tensor
from .tree import Tree


def job(actions=(), *, focal=0, token=1, root_id='test-root', **options):
    game = ref.Game(start_token=token)
    initial = PublicObservation.from_view(game.views()[focal]).serializable()
    transitions = []
    for joint in actions:
        game.step(joint)
        transitions.append(dict(own_action=joint[focal], observation=PublicObservation.from_view(game.views()[focal]).serializable()))
    return game, dict(schema=1, kind=protocol.FORMAT, root_id=root_id, initial_observation=initial,
                      transitions=transitions, search={**dict(simulations=24, horizon=3, trace=True), **options})


def ambiguity():
    c = ['NORTH']*6+['WEST', 'NORTH', 'STAY', 'WEST', 'STAY', 'SOUTH']
    result = [['STAY', 'STAY', action, 'STAY'] for action in c]
    result += [['EAST', action, 'STAY', 'STAY'] for action in ('WEST', 'SOUTH', 'NORTH', 'SOUTH', 'NORTH')]
    return result


def by_id(report):
    return {row['root_id']: row for row in report['roots']}


class PublicTreeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.old_threads = torch.get_num_threads()
        torch.set_num_threads(1)

    @classmethod
    def tearDownClass(cls):
        torch.set_num_threads(cls.old_threads)

    def test_exact_scalar_tensor_complete_statistics_and_observation_branching(self):
        _, raw = job(seed=41, beam_width=2)
        raw['search'].update(simulations=64, horizon=5)
        expected = scalar.search_many([raw])['roots']
        result = tensor.search_many([raw], verify_reference=True)
        self.assertEqual(expected, result['roots'])
        tree = result['roots'][0]['tree']
        self.assertTrue(any(len({c['action'] for c in n['children']}) < len(n['children']) for n in tree))
        self.assertTrue(any(n['visits'] > 1 for n in tree[1:]))
        self.assertGreater(sum(s['mode'] == 'tree' for t in result['roots'][0]['trace'] for s in t['steps']), 64)
        for node in tree:
            self.assertEqual(len(bytes.fromhex(node['observation'])), 65)
            self.assertLessEqual(sum(node['counts']), node['visits'])
        self.assertEqual(sum(tree[0]['counts']), tree[0]['visits'])

    def test_hidden_distinct_actual_worlds_same_public_prefix_and_id_independent_rng(self):
        prefix = ambiguity()
        left = prefix+[['STAY', 'STAY', 'SHIELD', 'STAY']]+[['STAY']*4]*2
        right = prefix+[['STAY', 'SHIELD', 'SHIELD', 'STAY']]+[['STAY']*4]*2
        ga, a = job(left, seed=91, beam_width=2)
        gb, b = job(right, seed=91, beam_width=2)
        self.assertNotEqual(ga.cd[1], gb.cd[1])
        self.assertEqual(a, b)
        b['root_id'] = 'different-arbitrary-id'
        pa, pb = protocol.prepare(a), protocol.prepare(b)
        self.assertNotEqual(pa.input_sha256, pb.input_sha256)
        self.assertEqual(pa.history_sha256, pb.history_sha256)
        self.assertEqual([protocol.model_keys(pa, s) for s in range(24)], [protocol.model_keys(pb, s) for s in range(24)])
        aa, bb = tensor.search_many([a, b], verify_reference=True)['roots']
        aa.pop('root_id'); bb.pop('root_id')
        self.assertEqual(aa, bb)
        self.assertEqual(aa['belief']['cooldown_domains'][1], [0, 2])

    def test_exact_65_bytes_including_frozen_flags_and_static_descriptor(self):
        game, raw = job(ambiguity()+[['STAY', 'STAY', 'SHIELD', 'STAY']])
        root = protocol.prepare(raw)
        self.assertFalse(hasattr(root, 'transitions'))
        self.assertFalse(hasattr(root, 'trace'))
        self.assertTrue(any(root.packed[p] & 128 for p in range(64)))
        batch = _tensor_state(list(root.states), 'cpu')
        focal = torch.full((len(root.states),), root.focal, dtype=torch.long)
        packed = tensor._bytes(tensor.packed_public(_public_adapter(batch), focal))
        for i, state in enumerate(root.states):
            obs = PublicObservation.from_view(state.views()[root.focal])
            self.assertEqual(packed[i*65:(i+1)*65], protocol.pack(obs))
            self.assertEqual(protocol.pack(obs), scalar._encode(obs))
            self.assertEqual(root.base, bytes(state.base))
            self.assertEqual(root.home, bytes(bool(v) for v in state.home))

    def test_every_legal_action_twice_before_fixed_beam_pruning_and_node_cap(self):
        _, raw = job(beam_width=1, max_nodes=1)
        root = protocol.prepare(raw)
        tree = Tree(root)
        legal = tree.nodes[0].legal
        for visit in range(2*len(legal)):
            action = tree.select(0)
            self.assertEqual(action, legal[visit % len(legal)])
            self.assertFalse(tree.nodes[0].pruned)
            tree.backup([0], [(0, action)], action)
        tree.select(0)
        self.assertEqual(len(tree.nodes[0].active), 1)
        result = tensor.search_many([raw], verify_reference=True)['roots'][0]
        self.assertEqual(len(result['tree']), 1)
        self.assertEqual(result['cap_hits'], 24)
        self.assertTrue(result['approximation']['node_cap'])
        self.assertTrue(all(result['tree'][0]['counts'][a] >= 2 for a in legal))

    def test_true_terminal_clock_clips_horizon_and_disables_income_projection(self):
        _, a = job([['STAY']*4]*79, income_tail=80)
        a['search']['horizon'] = 12
        b = copy.deepcopy(a); b['root_id'] = 'no-income-tail'; b['search']['income_tail'] = 0
        out = tensor.search_many([a, b], verify_reference=True)['roots']
        self.assertTrue(out[0]['terminal_reached'])
        self.assertEqual(out[0]['effective_horizon'], 1)
        self.assertEqual(out[0]['income_tail'], 0)
        self.assertEqual(out[0]['cutoff_utility'], 'exact_terminal_pairwise_numerator')
        for row in out:
            self.assertTrue(all(len(t['steps']) == 1 and 0 <= t['value'] <= 6 for t in row['trace']))
            row.pop('root_id')
        self.assertEqual(*out)

    def test_mixed_horizons_chunks_order_and_memory_budgets_do_not_change_tree(self):
        roots = [job([['STAY']*4]*turns, focal=i, token=i+1, root_id=str(i), seed=10+i)[1]
                 for i, turns in enumerate((0, 2, 78, 79))]
        together = tensor.search_many(roots, max_roots=4, verify_reference=True)
        chunks = tensor.search_many(reversed(roots), max_roots=1, max_support_states=3, max_tree_nodes=256)
        self.assertEqual(by_id(together), by_id(chunks))
        self.assertEqual({b['effective_horizon'] for b in together['batches']}, {1, 2, 3})
        with self.assertRaisesRegex(ValueError, 'exceeds'):
            tensor.search_many(roots, max_tree_nodes=255)

    def test_focal_default_key_is_public_fixed_across_particles_and_rivals_are_hypothetical(self):
        root = protocol.prepare(job(focal=2, token=1, seed=9)[1])
        first = protocol.model_keys(root, 0)
        second = protocol.model_keys(root, 1)
        self.assertEqual(first[root.focal], second[root.focal])
        self.assertTrue(all(first[p] != second[p] for p in range(4) if p != root.focal))
        # The rival model accepts no selected focal action, tree or referee object.
        self.assertEqual([f.name for f in fields(PublicPolicyBatch)], ['board', 'bot_id', 'is_priority_token', 'legal_actions'])
        self.assertEqual(list(inspect.signature(Tree.select).parameters), ['self', 'node_id'])
        captured = []
        original = tensor.public_policy
        def checked(public, keys, step):
            self.assertIs(type(public), PublicPolicyBatch)
            predicted = original(public, keys, step)
            captured.append((public.board.clone(), public.legal_actions.clone(), predicted.clone()))
            return predicted
        with patch.object(tensor, 'public_policy', checked):
            result = tensor.search_many([job(seed=9)[1]])['roots'][0]
        # At depth0, different exploratory focal actions start from the same
        # observation; all rival actions were calculated before focal override.
        depth0 = [t['steps'][0] for t in result['trace']]
        self.assertGreater(len({s['action'] for s in depth0}), 1)
        for i, step in enumerate(depth0):
            predicted = captured[i*3][2].tolist()
            self.assertEqual(step['joint'][1:], predicted[1:])

    def test_support_loss_is_reported_unsupported_without_inventing_state(self):
        _, raw = job([['STAY']*4], focal=1, token=3, support_cap=1)
        a = scalar.search_many([raw]); b = tensor.search_many([raw])
        self.assertEqual(a['roots'], [])
        self.assertEqual(a['unsupported'], b['unsupported'])
        self.assertIsNone(b['unsupported'][0]['recommended_action'])
        with self.assertRaisesRegex(ValueError, 'unique'):
            tensor.search_many([raw, raw])

    def test_private_snapshots_fields_malformed_maps_and_invalid_budgets_rejected(self):
        game, raw = job()
        invalid = [game]
        for key, value in [('state', game), ('actual_seed', 4), ('future_actions', [])]:
            bad = copy.deepcopy(raw); bad[key] = value; invalid.append(bad)
        bad = copy.deepcopy(raw); bad['initial_observation']['private_cd'] = [0]*4; invalid.append(bad)
        bad = copy.deepcopy(raw); bad['initial_observation']['board'][0][0].append(4); invalid.append(bad)
        bad = copy.deepcopy(raw); bad['initial_observation']['board'][0][0][5] = 2; invalid.append(bad)
        bad = copy.deepcopy(raw); bad['search']['simulations'] = 2; invalid.append(bad)
        bad = copy.deepcopy(raw); bad['search']['seed'] = True; invalid.append(bad)
        bad = copy.deepcopy(raw); bad['search']['exploration'] = float('nan'); invalid.append(bad)
        for bad in invalid:
            with self.subTest(kind=type(bad).__name__), self.assertRaises((ValueError, TypeError)):
                protocol.prepare(bad)
        for body in ('{"x":1,"x":2}', '{"x":NaN}'):
            with self.assertRaises(ValueError):
                protocol.strict_loads(body)

    def test_any_reference_or_source_disagreement_quarantines_entire_result(self):
        _, raw = job()
        with patch.object(scalar, 'run_prepared', return_value={'wrong': True}):
            with self.assertRaisesRegex(AssertionError, 'QUARANTINED'):
                tensor.search_many([raw], verify_reference=True)
        with patch.object(tensor, 'source_hashes', side_effect=[{'hash': 'a'}, {'hash': 'b'}]):
            with self.assertRaisesRegex(ValueError, 'QUARANTINED'):
                tensor.search_many([raw])

    def test_stream_sink_memory_limits_and_input_immutability(self):
        roots = [job(root_id=str(i), seed=i)[1] for i in range(3)]
        before = copy.deepcopy(roots)
        expected = tensor.search_many(roots)
        emitted = []
        streamed = tensor.search_many(iter(roots), result_sink=emitted.append, max_roots=1,
                                      max_retained_roots=1, max_retained_nodes=1)
        self.assertEqual(emitted, expected['roots'])
        self.assertEqual(streamed['roots'], [])
        self.assertEqual(streamed['supported_roots'], 3)
        self.assertEqual(before, roots)
        with self.assertRaisesRegex(ValueError, 'Retained result budget'):
            tensor.search_many(roots, max_retained_roots=2)
        with self.assertRaisesRegex(ValueError, 'input-root budget'):
            tensor.search_many(roots, max_input_roots=2)

    @unittest.skipUnless(torch.cuda.is_available(), 'CUDA unavailable')
    def test_real_cuda_complete_parity_for_hidden_support_terminal_chunks_and_reordering(self):
        roots = [job(root_id='opening', seed=41, beam_width=2)[1],
                 job(ambiguity()+[['STAY', 'STAY', 'SHIELD', 'STAY']]+[['STAY']*4]*2,
                     root_id='ambiguous', seed=91)[1],
                 job([['STAY']*4]*79, root_id='terminal', income_tail=80)[1]]
        cpu = tensor.search_many(roots, verify_reference=True)
        gpu = tensor.search_many(roots, device='cuda', verify_reference=True)
        chunks = tensor.search_many(reversed(roots), device='cuda', max_roots=1, verify_reference=True)
        graph = tensor.search_many(roots, device='cuda', use_cuda_graph=True, verify_reference=True)
        graph_chunks = tensor.search_many(reversed(roots), device='cuda', use_cuda_graph=True,
                                          max_roots=1, verify_reference=True)
        self.assertEqual(by_id(cpu), by_id(gpu))
        self.assertEqual(by_id(cpu), by_id(chunks))
        self.assertEqual(by_id(cpu), by_id(graph))
        self.assertEqual(by_id(cpu), by_id(graph_chunks))
        self.assertEqual(gpu['primary_match_credit'], 0)
        self.assertEqual(gpu['completed_game_audit_credit'], 0)

    @unittest.skipUnless(torch.cuda.is_available(), 'CUDA unavailable')
    def test_graph_stable_buffer_replay_matches_every_eager_hidden_physics_field(self):
        from .graph import PublicStepGraph
        states = [protocol.prepare(job(token=3)[1]).states[0],
                  protocol.prepare(job(ambiguity()+[['STAY', 'STAY', 'SHIELD', 'STAY']])[1]).states[0]]
        eager, captured = _tensor_state(states, 'cuda'), _tensor_state(states, 'cuda')
        focal = torch.tensor([0, 0], device='cuda')
        steps = torch.tensor([0, 18], device='cuda')
        keys = torch.tensor([123, 456, 789, 1011]*2, device='cuda')
        graph = PublicStepGraph(captured, focal, steps)
        # Warmup/capture advanced the local scratch state; restore it exactly as
        # the production prototype's per-simulation support gather does.
        names = ('owner', 'upg', 'pos', 'frozen', 'cd', 'prog', 'score', 'income', 'token')
        for name in names:
            getattr(captured, name).copy_(getattr(eager, name))
        graph.set_keys(keys)
        row = torch.arange(2, device='cuda')
        for depth in range(15):
            before = _public_adapter(eager)
            legal = before.legal_actions.reshape(2, 4, 6)[:, 0].cpu().tolist()
            requested = [next(a for a in range(6) if legal[i][a]) if depth%2 else None for i in range(2)]
            expected = tensor.public_policy(before, keys, (steps+depth).unsqueeze(1).expand(2, 4).reshape(-1)).reshape(2, 4)
            for i, action in enumerate(requested):
                if action is not None:
                    expected[i, 0] = action
            eager.step(expected)
            actual, packed = graph.step(requested, depth)
            self.assertTrue(torch.equal(actual, expected))
            self.assertEqual(tensor._bytes(packed), tensor._bytes(tensor.packed_public(_public_adapter(eager), focal)))
            for name in names+('base', 'home'):
                self.assertTrue(torch.equal(getattr(captured, name), getattr(eager, name)), (depth, name))


if __name__ == '__main__':
    unittest.main()
