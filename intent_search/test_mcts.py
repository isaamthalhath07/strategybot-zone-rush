"""Public-boundary, joint-posterior and every-turn two-referee regression tests.

All fixtures are synthetic public prefixes. No campaign, archived study outcome,
actual controller or full-match actor task is loaded or executed.
"""
import copy
import inspect
import itertools
import math
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from opponent_prediction.intent_filter import IntentFilter, InferenceBudgetExceeded
from search_coach.belief import PublicObservation
from tests import reference_engine as ref
from . import mcts as m


def job(actions=(), *, focal=0, token=1, **options):
    game=ref.Game(start_token=token)
    initial=PublicObservation.from_view(game.views()[focal]).serializable()
    transitions=[]
    for joint in actions:
        game.step(joint)
        transitions.append(dict(own_action=joint[focal],observation=PublicObservation.from_view(game.views()[focal]).serializable()))
    return game,dict(schema=1,kind=m.FORMAT,root_id='synthetic',initial_observation=initial,transitions=transitions,
                     search={**dict(simulations=16,horizon=3,trace=True),**options})


def ambiguity():
    c=['NORTH']*6+['WEST','NORTH','STAY','WEST','STAY','SOUTH']
    return [['STAY','STAY',action,'STAY'] for action in c]+[['EAST',action,'STAY','STAY'] for action in
             ('WEST','SOUTH','NORTH','SOUTH','NORTH')]


def deterministic(result):
    return {key:value for key,value in result.items() if key not in ('root_id','timing')}


class JointIntentSearchTests(unittest.TestCase):
    def test_hidden_distinct_actual_worlds_same_public_input_and_root_label_invariance(self):
        prefix=ambiguity()
        ga,a=job(prefix+[['STAY','STAY','SHIELD','STAY']]+[['STAY']*4]*2,seed=91)
        gb,b=job(prefix+[['STAY','SHIELD','SHIELD','STAY']]+[['STAY']*4]*2,seed=91)
        self.assertNotEqual(ga.cd[1],gb.cd[1]);self.assertEqual(a,b)
        b['root_id']='arbitrary-other-label'
        ra,rb=m.recommend(a),m.recommend(b)
        self.assertEqual(deterministic(ra),deterministic(rb))
        self.assertFalse(ra['posterior']['actual_private_state_accepted'])
        self.assertFalse(ra['posterior']['marginal_factorization'])

    def test_prepared_weights_equal_complete_frozen_joint_posterior(self):
        _,raw=job([['STAY']*4]*3,token=3)
        belief=IntentFilter(raw['initial_observation'],mode='persistent')
        for item in raw['transitions']:belief.advance(item['own_action'],item['observation'])
        root=m.prepare(raw)
        keys=sorted(belief.states)
        expected=tuple((s,t,w) for s,key in enumerate(keys) for t,w in enumerate(belief.weights[key]) if w != -math.inf)
        self.assertEqual(root.joint,expected)
        self.assertEqual(root.types,belief.types)
        self.assertGreater(len({round(w,8) for _,_,w in root.joint}),1)
        self.assertAlmostEqual(math.fsum(math.exp(w) for _,_,w in root.joint),1.0)

    def test_joint_draws_preserve_state_type_correlation_and_nonuniform_mass(self):
        types=tuple(itertools.product(range(4),repeat=3))
        weights={'a':[-math.inf]*64,'b':[-math.inf]*64}
        weights['a'][0]=math.log(.9);weights['b'][63]=math.log(.1)
        entries=m.joint_entries(('a','b'),types,weights)
        root=SimpleNamespace(history_sha256='unit-public-history',options={'seed':71},joint=entries)
        draws=[m.draw_joint(root,s) for s in range(4096)]
        self.assertEqual(set(draws),{(0,0),(1,63)})
        self.assertAlmostEqual(draws.count((0,0))/len(draws),.9,delta=.03)
        self.assertEqual(draws,[m.draw_joint(root,s) for s in range(4096)])
        # Finite very small log mass is retained without exp-underflow pruning.
        tiny={'a':[-math.inf]*64};tiny['a'][0]=0.0;tiny['a'][63]=-1000.0
        self.assertEqual(len(m.joint_entries(('a',),types,tiny)),2)

    def test_every_sampled_turn_matches_two_referees_and_tree_keys_are_public(self):
        _,raw=job(seed=41,simulations=32,horizon=5)
        with patch.object(m,'equal_referees',wraps=m.equal_referees) as checked:
            result=m.recommend(raw)
        self.assertEqual(checked.call_count,32*(5+1))
        self.assertEqual(result['counterfactual_dual_referee_turns'],160)
        self.assertTrue(result['all_sampled_turns_dual_referee_checked'])
        root=m.prepare(raw)
        nodes={n['id']:n for n in result['tree']}
        for trace in result['trace']:
            game=root.states[trace['inferred_state_index']].clone()
            shadow=m.shadow_of(game)
            for step in trace['steps']:
                self.assertEqual(m.pack(PublicObservation.from_view(game.views()[root.focal])).hex(),step['before'])
                if step['node'] is not None:self.assertEqual(step['before'],nodes[step['node']]['observation'])
                game.step(step['joint_actions']);shadow.step(step['joint_actions']);m.equal_referees(game,shadow)
                self.assertEqual(step['observation'],m.pack(PublicObservation.from_view(game.views()[root.focal])).hex())
            self.assertEqual(trace['value'],m.utility(game,root.focal,75,12))
        self.assertEqual(nodes[0]['value_sum'],sum(t['value'] for t in result['trace']))
        self.assertTrue(all(n['observation'] and len(bytes.fromhex(n['observation']))==65 for n in nodes.values()))

    def test_persistent_types_fixed_and_simultaneous_rivals_cannot_see_current_focal_action(self):
        root=m.prepare(job(seed=3)[1])
        views=tuple(PublicObservation.from_view(v) for v in root.states[0].views())
        assignment=root.types[0]
        calls=[]
        original=m.policy
        def capture(view,hypothesis):
            self.assertIs(type(view),PublicObservation)
            calls.append((view.bot_id,hypothesis));return original(view,hypothesis)
        predictions=[]
        with patch.object(m,'policy',capture):
            for hypothetical_focal_action in views[root.focal].legal_actions:
                predictions.append(m.rival_actions(views,assignment,root.rivals,root.history_sha256,3,7,0))
        self.assertTrue(all(row==predictions[0] for row in predictions))
        self.assertTrue(all(bot_id != root.focal+1 for bot_id,_ in calls))
        self.assertNotIn('focal_action',inspect.signature(m.rival_actions).parameters)
        self.assertNotIn('simulation',inspect.signature(m.focal_rollout).parameters)
        seen=[]
        original_rivals=m.rival_actions
        def traced(*args):seen.append(args[1]);return original_rivals(*args)
        with patch.object(m,'rival_actions',traced):m.recommend(job(seed=3)[1])
        for i in range(16):self.assertEqual(seen[i*3:i*3+3],[seen[i*3]]*3)

    def test_node_cap_uses_same_public_rollout_across_different_type_particles(self):
        _,raw=job([['STAY','SHIELD','SHIELD','SHIELD']],seed=7,max_nodes=1,simulations=32)
        calls=[];original=m.focal_rollout
        def captured(view,history,seed,depth):
            action=original(view,history,seed,depth)
            calls.append((m.pack(view),history,seed,depth,action));return action
        with patch.object(m,'focal_rollout',captured):result=m.recommend(raw)
        repeated={}
        for view,history,seed,depth,action in calls:repeated.setdefault((view,history,seed,depth),[]).append(action)
        self.assertTrue(any(len(values)>1 for values in repeated.values()))
        self.assertTrue(all(len(set(values))==1 for values in repeated.values()))
        self.assertEqual(len(result['tree']),1)
        self.assertEqual(result['node_cap_hits'],32)
        self.assertGreater(len({t['joint_type_index'] for t in result['trace']}),1)
        self.assertTrue(all(v['visits']>=2 for v in result['root_estimates'].values()))

    def test_true_terminal_clock_exact_rank_backup_and_no_terminal_actor_view(self):
        _,raw=job([['STAY']*4]*79,horizon=8,income_tail=80,simulations=12)
        result=m.recommend(raw)
        self.assertEqual(result['effective_horizon'],1)
        self.assertTrue(result['true_terminal_reached']);self.assertEqual(result['income_tail'],0)
        self.assertEqual(result['cutoff_utility'],'exact_terminal_pairwise_numerator')
        self.assertEqual(len(result['tree']),1)
        for trace in result['trace']:
            scores=trace['final_scores'];own=scores[0]
            expected=sum(2 if own>x else 1 if own==x else 0 for i,x in enumerate(scores) if i != 0)
            self.assertEqual(trace['value'],expected)
            self.assertIsNone(trace['steps'][0]['observation'])
            self.assertTrue(trace['steps'][0]['terminal'])
        self.assertFalse(result['terminal_turn81_view_fabricated'])

    def test_private_input_invalid_budget_inference_cap_and_work_cap_rejected(self):
        game,raw=job()
        bad_inputs=[game]
        for key,value in [('actual_state',{}),('controller_seed',1),('joint_posterior',[]),('future_tape',[])]:
            bad=copy.deepcopy(raw);bad[key]=value;bad_inputs.append(bad)
        bad=copy.deepcopy(raw);bad['initial_observation']['cooldowns']=[0]*4;bad_inputs.append(bad)
        bad=copy.deepcopy(raw);bad['transitions']=[{}]*80;bad_inputs.append(bad)
        bad=copy.deepcopy(raw);bad['search']['simulations']=2;bad_inputs.append(bad)
        bad=copy.deepcopy(raw);bad['search']['seed']=True;bad_inputs.append(bad)
        bad=copy.deepcopy(raw);bad['search']['max_joint_sampling_terms']=1;bad_inputs.append(bad)
        for bad in bad_inputs:
            with self.assertRaises(ValueError):m.recommend(bad)
        _,raw=job(token=3,max_particles=64)
        with self.assertRaises(InferenceBudgetExceeded):m.recommend(raw)

    def test_any_source_or_referee_disagreement_quarantines_before_a_recommendation(self):
        raw=job()[1]
        with patch.object(m,'source_pins',side_effect=[{'a':'first'},{'a':'changed'}]):
            with self.assertRaisesRegex(ValueError,'QUARANTINED'):m.recommend(raw)
        original=m.Referee.step
        def corrupt(shadow,actions):original(shadow,actions);shadow.score[0]+=1
        with patch.object(m.Referee,'step',corrupt):
            with self.assertRaisesRegex(ValueError,'QUARANTINED'):m.recommend(raw)


if __name__=='__main__':unittest.main()
