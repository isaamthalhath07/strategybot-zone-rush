"""Synthetic-only author checks; no campaign, pilot or real recommendation."""
import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from aligned_search import evaluator as aligned
from intent_search import mcts
from search_coach.belief import PublicObservation
from tests import reference_engine as engine


def job(turns=0,**options):
    game = engine.Game()
    raw = dict(schema=1,kind=aligned.FORMAT,root_id='synthetic-author-only',
               initial_observation=PublicObservation.from_view(game.views()[0]).serializable(),
               transitions=[],search=dict(simulations=8,horizon=2,seed=71,**options))
    for _ in range(turns):
        game.step(['STAY']*4)
        raw['transitions'].append(dict(own_action='STAY',observation=PublicObservation.from_view(game.views()[0]).serializable()))
    return raw


class AuthorTests(unittest.TestCase):
    def test_strict_wire_and_complete_pair_allocation(self):
        for mutate in (lambda raw:raw.update(actual_seed=42),
                       lambda raw:raw.update(kind=mcts.FORMAT),
                       lambda raw:raw['search'].update(private_state={}),
                       lambda raw:raw['search'].update(simulations=10)):
            raw = job()
            mutate(raw)
            with self.assertRaises(ValueError):
                aligned.prepare(raw)

    def test_joint_posterior_and_inherited_caps_match_frozen_prepare_exactly(self):
        raw = job(turns=2)
        before = copy.deepcopy(raw)
        root,_ = aligned.prepare(raw)
        comparison = copy.deepcopy(raw)
        comparison['kind'] = mcts.FORMAT
        old = mcts.prepare(comparison)
        self.assertEqual(raw,before)
        self.assertEqual(root.joint,old.joint)
        self.assertEqual(root.types,old.types)
        self.assertEqual(len(root.types),64)
        self.assertEqual(root.posterior_summary,old.posterior_summary)
        self.assertEqual(root.history_sha256,old.history_sha256)
        raw['search']['max_joint_sampling_terms'] = 1
        with self.assertRaisesRegex(ValueError,'sampling work budget'):
            aligned.prepare(raw)

    def test_memory_cloning_copies_only_data_and_never_function_globals(self):
        _,normalized = aligned.prepare(job(turns=2))
        prefix = aligned.prefill(normalized)
        first = aligned.new_policy(prefix['root_memory'])
        second = aligned.new_policy(prefix['root_memory'])
        self.assertIs(first['act'].__globals__,first)
        self.assertIs(second['act'].__globals__,second)
        self.assertIsNot(first['act'].__globals__,second['act'].__globals__)
        original = aligned.memory_fingerprint(second['_history'])
        first['_history'][1]['last'] = 'SHIELD'
        self.assertEqual(aligned.memory_fingerprint(second['_history']),original)
        self.assertEqual(aligned.memory_fingerprint(prefix['root_memory']),original)
        with self.assertRaisesRegex(ValueError,'data-only'):
            aligned.new_policy({'function':lambda:None})

    def test_exact_ties_prefer_public_reconstructed_baseline(self):
        raw = job(turns=2)
        raw['search']['horizon'] = 1
        with patch.object(mcts,'utility',return_value=4):
            result = aligned.recommend(raw)
        self.assertEqual(result['baseline_action'],'STAY')
        self.assertEqual(result['recommended_action'],'STAY')
        self.assertEqual({row['empirical_pairwise_points'] for row in result['root_estimates'].values()},{2})
        self.assertEqual(result['pair_count'],2)
        self.assertEqual(result['counterfactual_dual_referee_turns'],8)
        self.assertEqual(result['counters']['simulation_policy_callbacks'],8)
        self.assertEqual(result['counters']['root_original_proposals'],9)

    def test_trace_covers_every_paired_world_action_and_immutable_input(self):
        raw = job()
        before = copy.deepcopy(raw)
        result = aligned.recommend(raw)
        self.assertEqual(raw,before)
        legal = result['legal_root_actions']
        self.assertEqual(len(result['trace']),2)
        for pair in result['trace']:
            self.assertEqual([row['root_action'] for row in pair['branches']],legal)
            rival_first = [tuple(step for seat,step in enumerate(branch['steps'][0]['joint_actions']) if seat != 0)
                           for branch in pair['branches']]
            self.assertEqual(len(set(rival_first)),1)
            for branch in pair['branches']:
                self.assertEqual(len(branch['steps']),2)
                self.assertEqual(branch['steps'][0]['accepted_action'],branch['root_action'])
                self.assertEqual(branch['steps'][0]['proposal'],result['baseline_action'])
                self.assertEqual(set(branch['steps'][0]['before']),{'board','bot_id','is_priority_token','legal_actions'})
        self.assertEqual(result['counters']['public_memory_oracles'],16)
        self.assertEqual(result['coverage']['actual_dual_referee_turns'],16)
        self.assertEqual(result['primary_match_credit'],0)
        self.assertEqual(result['full_bmcts_audit_credit'],0)
        self.assertIs(result['promoted'],False)

    def test_fallback_input_mutation_and_source_changes_abort(self):
        observation = PublicObservation.from_view(engine.Game().views()[0])
        for failure in ('fallback','mutation'):
            namespace = aligned.new_policy()
            def bad(view):
                if failure == 'fallback':
                    namespace['_policy_failures'] = 1
                else:
                    object.__setattr__(view.board[0][0],'owner',4)
                return 'STAY'
            namespace['act'] = bad
            with self.assertRaises(ValueError):
                aligned._call(namespace,observation,'synthetic',{},aligned._counters(),'simulation_policy_callbacks')
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as temporary:
            root = Path(temporary)
            (root/'bot.py').write_text('def act(view): return "STAY"',encoding='utf8')
            with patch.object(aligned,'ROOT',root),self.assertRaisesRegex(ValueError,'source changed'):
                aligned.new_policy()
        with patch.object(aligned,'source_pins',side_effect=[{'pin':'before'},{'pin':'after'}]):
            with self.assertRaisesRegex(ValueError,'source changed during'):
                aligned.recommend(job())


if __name__ == '__main__':
    unittest.main()
