"""Independent public-memory/paired-world mechanics; synthetic jobs only.

No campaign artifact, real cohort, trained opponent or strength outcome is read.
"""
import copy
from dataclasses import FrozenInstanceError
import hashlib
from pathlib import Path
import unittest
from unittest.mock import patch

from intent_search import mcts
from search_coach.belief import PublicObservation
from tests import reference_engine as ref
from . import evaluator as model


ROOT = Path(__file__).resolve().parents[1]


def blocked_prefix():
    return [['SHIELD','WEST','STAY','STAY'],
            ['STAY','WEST','STAY','STAY'],
            ['STAY','WEST','STAY','STAY'],
            ['EAST','WEST','STAY','STAY'],
            ['STAY','WEST','STAY','STAY']]


def job(actions=(),*,focal=0,token=1,**options):
    game = ref.Game(start_token=token,rules={'catch_requires_stay':True})
    initial = PublicObservation.from_view(game.views()[focal]).serializable()
    transitions = []
    for joint in actions:
        if any(action not in game.legal(seat) for seat,action in enumerate(joint)):
            raise AssertionError('Illegal synthetic prefix')
        game.step(joint)
        transitions.append(dict(own_action=joint[focal],
            observation=PublicObservation.from_view(game.views()[focal]).serializable()))
    defaults = dict(seed=71,simulations=2*len(game.legal(focal)),horizon=3,trace=True)
    return game,dict(schema=1,kind=model.FORMAT,root_id='SYNTHETIC_ONLY',
        initial_observation=initial,transitions=transitions,search=dict(defaults,**options))


def actual_engine_prefill(actions,*,focal=0,token=1):
    """Independent real-view calls, with no evaluator adapter or policy factory."""
    path = ROOT/'bot.py'
    body = path.read_bytes()
    assert hashlib.sha256(body).hexdigest() == model.INCUMBENT
    namespace = {'__name__':'independent_e8_synthetic','__file__':str(path)}
    exec(compile(body,str(path),'exec'),namespace)
    game = ref.Game(start_token=token,rules={'catch_requires_stay':True})
    trace = []
    for joint in actions:
        raw_view = copy.deepcopy(game.views()[focal])
        proposal = namespace['act'](raw_view)
        proposed_memory = copy.deepcopy(namespace['_history'])
        namespace['_history'][focal+1]['last'] = joint[focal]
        trace.append(dict(proposal=proposal,actor_legal_actions=list(raw_view.legal_actions),
            proposed_memory=proposed_memory,accepted_memory=copy.deepcopy(namespace['_history'])))
        game.step(joint)
    before_root = copy.deepcopy(namespace['_history'])
    baseline = namespace['act'](copy.deepcopy(game.views()[focal]))
    if namespace['_input_failures'] or namespace['_policy_failures']:
        raise AssertionError('Independent e8 fallback')
    return game,namespace,before_root,baseline,trace


class IndependentAlignedTests(unittest.TestCase):
    def test_full_prefill_matches_exact_e8_calls_with_real_engine_legal_order(self):
        for actions,focal,token in (([['STAY']*4]*3,0,1),
                                    ([['STAY']*4]*3,1,3),(blocked_prefix(),0,1)):
            with self.subTest(focal=focal,token=token,turns=len(actions)):
                game,raw = job(actions,focal=focal,token=token)
                original = copy.deepcopy(raw)
                _,normalized = model.prepare(raw)
                reconstructed = model.prefill(normalized)
                actual,namespace,before,baseline,trace = actual_engine_prefill(actions,focal=focal,token=token)
                self.assertEqual(raw,original)
                self.assertEqual(reconstructed['before_root_memory'],before)
                self.assertEqual(reconstructed['root_memory'],namespace['_history'])
                self.assertEqual(reconstructed['baseline_action'],baseline)
                self.assertEqual(model.policy_view(game.views()[focal]).legal_actions,
                                 tuple(actual.views()[focal].legal_actions))
                for recorded,expected in zip(reconstructed['trace'][:-1],trace):
                    self.assertEqual(recorded['proposal'],expected['proposal'])
                    self.assertEqual(recorded['actor_legal_actions'],expected['actor_legal_actions'])
                    self.assertEqual(recorded['memory_after_proposal_sha256'],
                                     model.memory_fingerprint(expected['proposed_memory']))
                    self.assertEqual(recorded['memory_after_accepted_sha256'],
                                     model.memory_fingerprint(expected['accepted_memory']))
                self.assertEqual(reconstructed['counters']['prefix_policy_callbacks'],len(actions))
                self.assertEqual(reconstructed['counters']['root_probe_callbacks'],1)

    def test_policy_memory_is_public_label_invariant_and_sibling_globals_are_fresh(self):
        game,raw = job(blocked_prefix())
        _,one = model.prepare(raw)
        other = copy.deepcopy(raw);other['root_id']='OTHER_SYNTHETIC_LABEL';other['search']['seed']+=1
        _,two = model.prepare(other)
        a,b = model.prefill(one),model.prefill(two)
        self.assertEqual(a['before_root_memory'],b['before_root_memory'])
        self.assertEqual(a['root_memory'],b['root_memory'])
        self.assertEqual(a['baseline_action'],b['baseline_action'])
        left,right = model.new_policy(a['before_root_memory']),model.new_policy(a['before_root_memory'])
        self.assertIs(left['act'].__globals__,left)
        self.assertIs(right['act'].__globals__,right)
        self.assertIsNot(left['act'],right['act'])
        self.assertIsNot(left['_history'],right['_history'])
        left_action = left['act'](model.policy_view(game.views()[0]))
        right_action = right['act'](model.policy_view(game.views()[0]))
        self.assertEqual(left_action,right_action)
        self.assertEqual(left['_history'],right['_history'])
        proposed = copy.deepcopy(left['_history'])
        model._sync(left,1,'EAST')
        self.assertEqual(left['_history'][1]['last'],'EAST')
        self.assertEqual({k:v for k,v in left['_history'][1].items() if k!='last'},
                         {k:v for k,v in proposed[1].items() if k!='last'})
        left['_history'][1]['cooldown_possible'][1].add(99)
        self.assertNotIn(99,right['_history'][1]['cooldown_possible'][1])
        self.assertNotIn(99,a['before_root_memory'][1]['cooldown_possible'][1])
        with self.assertRaises(ValueError):
            model.new_policy({'hidden_callable':lambda:None})

    def test_paired_worlds_root_simultaneity_and_actual_transition_coverage(self):
        _,raw = job(blocked_prefix(),horizon=2)
        root,normalized = model.prepare(raw)
        states_before = [copy.deepcopy((g.owner,g.pos,g.prog,g.score,g.cd,g.turn)) for g in root.states]
        steps,calls,namespaces = [],[],[]
        actual_step,actual_factory,actual_rivals = ref.Game.step,model.new_policy,mcts.rival_actions

        def step(game,actions):
            steps.append((game.turn,list(actions)))
            return actual_step(game,actions)

        def factory(memory=None):
            namespace = actual_factory(memory)
            original = namespace['act']
            def actor(view):
                self.assertEqual(set(view.__slots__),{'board','bot_id','is_priority_token','legal_actions'})
                calls.append((id(namespace),model._signature(view)))
                return original(view)
            namespace['act'] = actor
            namespaces.append(namespace)
            return namespace

        rival_calls = []
        def rivals(*args):
            rival_calls.append((args[1],args[5],args[6]))
            return actual_rivals(*args)

        with patch.object(model,'prepare',return_value=(root,normalized)), \
             patch.object(ref.Game,'step',step),patch.object(model,'new_policy',factory), \
             patch.object(mcts,'rival_actions',rivals), \
             patch.object(mcts,'equal_referees',wraps=mcts.equal_referees) as compared:
            result = model.recommend(raw)
        expected = root.options['simulations']*root.horizon
        self.assertEqual(len(steps),expected)
        self.assertEqual(compared.call_count,expected+root.options['simulations'])
        self.assertEqual(len(calls),len(raw['transitions'])+1+expected)
        self.assertEqual(len(namespaces),1+root.options['simulations'])
        self.assertEqual(len({id(ns) for ns in namespaces}),len(namespaces))
        self.assertEqual(result['counters']['simulation_policy_callbacks'],expected)
        self.assertEqual(result['counters']['dual_referee_turns'],len(steps))
        self.assertEqual(result['counters']['public_memory_oracles'],expected)
        self.assertEqual(result['counters']['root_accepted_action_synchronizations'],root.options['simulations'])
        self.assertEqual(states_before,[copy.deepcopy((g.owner,g.pos,g.prog,g.score,g.cd,g.turn)) for g in root.states])
        offset = 0
        for pair in result['trace']:
            self.assertEqual((pair['inferred_state_index'],pair['joint_type_index']),mcts.draw_joint(root,pair['pair_index']))
            self.assertEqual({branch['root_action'] for branch in pair['branches']},set(root.observation.legal_actions))
            root_others = []
            for branch in pair['branches']:
                root_others.append([a for seat,a in enumerate(branch['steps'][0]['joint_actions']) if seat!=root.focal])
                for depth in range(root.horizon):
                    assignment,pair_index,recorded_depth = rival_calls[offset]
                    self.assertEqual(assignment,root.types[pair['joint_type_index']])
                    self.assertEqual((pair_index,recorded_depth),(pair['pair_index'],depth))
                    offset += 1
            self.assertTrue(all(actions==root_others[0] for actions in root_others))
        self.assertEqual(offset,len(rival_calls))

    def test_blocked_root_retains_accepted_move_and_public_progress_matches_physics(self):
        _,raw = job(blocked_prefix(),horizon=2)
        root,_ = model.prepare(raw)
        result = model.recommend(raw)
        for pair in result['trace']:
            branch = next(branch for branch in pair['branches'] if branch['root_action']=='EAST')
            first,second = branch['steps']
            self.assertEqual(first['accepted_action'],'EAST')
            self.assertEqual(first['effective_own_action'],'STAY')
            game = root.states[pair['inferred_state_index']].clone()
            at = game.pos[root.focal]
            effective = game.step(first['joint_actions'])
            self.assertEqual(game.pos[root.focal],at)
            self.assertEqual(effective[root.focal],'STAY')
            self.assertEqual(game.prog[root.focal],1)
            self.assertEqual(second['before'],PublicObservation.from_view(game.views()[root.focal]).serializable())
            self.assertNotEqual(first['memory_after_proposal_sha256'],first['policy_memory_sha256'])
            self.assertEqual(first['policy_memory_sha256'],second['memory_before_sha256'])

    def test_terminal_rank_exact_and_no_turn81_actor_view(self):
        _,raw = job(blocked_prefix()+[['STAY']*4]*74,horizon=8,income_tail=80)
        actual_views = ref.Game.views
        def no_terminal_view(game):
            self.assertLess(game.turn,81,'Fabricated terminal actor/public observation')
            return actual_views(game)
        with patch.object(ref.Game,'views',no_terminal_view):
            result = model.recommend(raw)
        self.assertEqual(result['effective_horizon'],1)
        self.assertTrue(result['true_terminal_reached'])
        self.assertEqual(result['income_tail'],0)
        self.assertFalse(result['terminal_turn81_view_fabricated'])
        values = set()
        for pair in result['trace']:
            for branch in pair['branches']:
                own = branch['final_scores'][0]
                exact = sum(2 if own>score else 1 if own==score else 0
                            for seat,score in enumerate(branch['final_scores']) if seat!=0)
                self.assertEqual(branch['value_numerator'],exact)
                self.assertEqual(len(branch['steps']),1)
                self.assertIsNone(branch['steps'][0]['after'])
                self.assertIsNone(branch['steps'][0]['after_history_sha256'])
                values.add(exact)
        self.assertNotEqual(values,{3})

    def test_policy_view_is_immutable_and_never_exposes_private_fields(self):
        game,raw = job()
        first,second = model.policy_view(raw['initial_observation']),model.policy_view(game.views()[0])
        self.assertEqual(model._signature(first),model._signature(second))
        self.assertIsNot(first.board,second.board)
        self.assertIsNot(first.board[0][0],second.board[0][0])
        with self.assertRaises(FrozenInstanceError):
            first.board[0][0].owner = 4
        for key,value in (('actual_state',game),('actual_rival_seed',4),('continuation',{}),('future_tape',[])):
            bad = copy.deepcopy(raw);bad[key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):
                model.prepare(bad)
        for key in ('cooldowns','scores','progress','private_game'):
            bad = copy.deepcopy(raw);bad['initial_observation'][key]=[]
            with self.subTest(key=key),self.assertRaises(ValueError):
                model.prepare(bad)


if __name__=='__main__':
    unittest.main()
