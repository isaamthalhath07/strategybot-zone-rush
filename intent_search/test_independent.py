"""Independent public/trace/clock checks; ZERO campaign or strength matches.

Canonical complete-history physical bound (not a tight reachable-state claim):
the public board/history fixes scores, income and freeze ages, own accepted
actions fix own cooldown/progress, and the token is resolved by the fourth view
(three views actually suffice). Only three rival cooldowns0..4 and progress0..2
remain: at most5**3*3**3=3375 steady physical explanations. An early loose bound
adds at most three token choices:10125. These exceed current declared caps as
upper bounds; no reachable>1024 example is claimed. Fixed64 behavioral types
multiply the steady bound to216000 joint pairs. Future latent goal/controller
memory would require a different bound. Budgets must continue to fail closed.
"""
from bisect import bisect_right
import collections
import copy
import hashlib
import itertools
import json
import math
import os
from pathlib import Path
from types import SimpleNamespace
import sys
import tempfile
import unittest
from unittest.mock import patch

from intent_search import mcts as model
from intent_search import __main__ as command
from opponent_prediction.intent_filter import policy
from search_coach.belief import PublicObservation
from simulator.vendor_harness.referee import Referee
from tests import reference_engine as ref


ROOT=Path(__file__).resolve().parents[1]


def canonical(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()


def sample_job(actions=(),*,focal=0,token=1,**options):
    game=ref.Game(start_token=token)
    opening=PublicObservation.from_view(game.views()[focal]).serializable()
    history=[]
    for joint in actions:
        if any(action not in game.legal(seat) for seat,action in enumerate(joint)):
            raise AssertionError('Illegal synthetic witness')
        game.step(joint)
        history.append(dict(own_action=joint[focal],observation=PublicObservation.from_view(game.views()[focal]).serializable()))
    return dict(schema=1,kind=model.FORMAT,root_id='INDEPENDENT_SYNTHETIC',initial_observation=opening,
                transitions=history,search={**dict(seed=71,simulations=24,horizon=3,trace=True),**options})


def shield_correlation_prefix():
    b=['WEST','STAY','SOUTH','WEST','STAY','EAST','EAST','NORTH']+['STAY']*4
    c=['STAY']*4+['NORTH']*6+['WEST','NORTH']
    d=['STAY']+['NORTH']*6+['EAST']*5
    return [list(row) for row in zip(['STAY']*12,b,c,d)]+[['STAY','SHIELD','STAY','STAY']]


def ambiguity_prefix():
    c=['NORTH']*6+['WEST','NORTH','STAY','WEST','STAY','SOUTH']
    result=[['STAY','STAY',action,'STAY'] for action in c]
    return result+[['EAST',action,'STAY','STAY'] for action in ('WEST','SOUTH','NORTH','SOUTH','NORTH')]


def encode(view):
    # Independently encode the documented dynamic public descriptor.
    body=bytearray()
    for occupant,owner,upgraded,home,frozen,base in view.cells:
        body.append(occupant+8*owner+64*upgraded+128*frozen)
    body.append(sum(2**ref.ACTIONS.index(a) for a in view.legal_actions)+64*view.is_priority_token)
    return body.hex()


def make_shadow(game):
    shadow=Referee(list(game.base),start_token=game.token,rules=dict(game.rules))
    for name in ('owner','upg','home','pos','frozen','cd','prog','score'):
        setattr(shadow,name,list(getattr(game,name)))
    shadow.turn=game.turn
    return shadow


def public_accounting(raw):
    previous=PublicObservation.from_view(raw['initial_observation'])
    focal=previous.bot_id-1
    scores=[0]*4
    freezes=[0]*4
    own_cd=own_progress=0
    income=[sum(cell[5]*(2 if cell[2] else 1) for cell in previous.cells if cell[1]==seat+1)
            for seat in range(4)]
    for item in raw['transitions']:
        after=PublicObservation.from_view(item['observation'])
        for before_cell,after_cell in zip(previous.cells,after.cells):
            old,new=before_cell[1],after_cell[1]
            if old and new and old!=new:
                scores[new-1]+=8*before_cell[5]*(2 if before_cell[2] else 1)
        income=[sum(cell[5]*(2 if cell[2] else 1) for cell in after.cells if cell[1]==seat+1)
                for seat in range(4)]
        scores=[score+delta for score,delta in zip(scores,income)]
        for seat,position in enumerate(after.positions):
            active=after.cells[position][4]
            freezes[seat]=(freezes[seat]-1 if freezes[seat] else 2) if active else 0
        action=item['own_action']
        own_cd=4 if action=='SHIELD' else max(0,own_cd-1)
        old_position,new_position=previous.positions[focal],after.positions[focal]
        before_cell=previous.cells[old_position]
        after_cell=after.cells[new_position]
        if freezes[focal] or action=='SHIELD' or old_position!=new_position or before_cell[4]:
            own_progress=0
        elif before_cell[1]==focal+1:
            own_progress=0 if after_cell[2] else own_progress+1
        elif before_cell[1]==0 or after_cell[1]==focal+1:
            own_progress=0
        elif before_cell[3]:
            own_progress=0
        else:
            own_progress+=1
        previous=after
    return scores,income,freezes,own_cd,own_progress


class IndependentIntentSearchTests(unittest.TestCase):
    def setUp(self):
        cache=ROOT/'.cache'
        cache.mkdir(exist_ok=True)
        self.temporary=tempfile.TemporaryDirectory(prefix='intent-search-independent-',dir=cache)
        self.addCleanup(self.temporary.cleanup)
        self.folder=Path(self.temporary.name)

    def test_full_counterfactual_trace_public_rng_physics_utility_and_backups(self):
        raw=sample_job(shield_correlation_prefix(),simulations=32,horizon=3)
        result=model.recommend(raw)
        root=model.prepare(raw)
        self.assertGreater(root.posterior_summary['physical_states'],1)
        legal_pairs={(state,typ) for state,typ,weight in root.joint}
        nodes={node['id']:node for node in result['tree']}
        expected={index:dict(visits=0,value=0,counts=[0]*6,values=[0]*6) for index in nodes}
        transitions=0
        for run in result['trace']:
            pair=(run['inferred_state_index'],run['joint_type_index'])
            self.assertIn(pair,legal_pairs)
            assignment=root.types[pair[1]]
            self.assertEqual(run['hypothetical_types'],[model.HYPOTHESES[i] for i in assignment])
            game=root.states[pair[0]].clone()
            shadow=make_shadow(game)
            visited=[0]
            selected=[]
            for depth,step in enumerate(run['steps']):
                self.assertEqual(game.turn,root.prefix_length+depth+1)
                public=tuple(PublicObservation.from_view(v) for v in game.views())
                self.assertEqual(step['before'],encode(public[root.focal]))
                if step['node'] is not None:
                    self.assertEqual(step['before'],nodes[step['node']]['observation'])
                    selected.append((step['node'],ref.ACTIONS.index(step['own_action'])))
                # Domain-separated policy draws independently reconstructed from
                # the public root and pre-turn views, with NO own action input.
                for rival_index,seat in enumerate(root.rivals):
                    data=[model.MODEL_VERSION,root.history_sha256,root.options['seed'],
                          'hypothetical-rival',run['simulation'],depth,seat]
                    digest=hashlib.sha256(canonical(data)).digest()
                    uniform=(int.from_bytes(digest[:7],'big')>>3)/(2**53)
                    probabilities=policy(public[seat],model.HYPOTHESES[assignment[rival_index]])
                    action=bisect_right(list(itertools.accumulate(probabilities)),uniform)
                    self.assertEqual(step['joint_actions'][seat],ref.ACTIONS[action])
                for seat,action in enumerate(step['joint_actions']):
                    self.assertIn(action,public[seat].legal_actions)
                game.step(step['joint_actions']);shadow.step(step['joint_actions'])
                for name in ('base','owner','upg','home','pos','frozen','cd','prog','score','turn','token'):
                    self.assertEqual(getattr(game,name),getattr(shadow,name),name)
                self.assertEqual(game.income,shadow.income())
                self.assertTrue(all(set(game.legal(i))==set(shadow.legal(i)) for i in range(4)))
                terminal=game.turn==81
                self.assertEqual(step['terminal'],terminal)
                post=None if terminal else encode(PublicObservation.from_view(game.views()[root.focal]))
                self.assertEqual(step['observation'],post)
                if step['node'] is not None and not terminal:
                    children=[child['node'] for child in nodes[step['node']]['children']
                              if child['action']==ref.ACTIONS.index(step['own_action']) and child['observation']==post]
                    self.assertLessEqual(len(children),1)
                    visited.extend(children)
                transitions+=1
            remaining=80-root.prefix_length-root.horizon
            projected=[s+min(12,remaining)*i for s,i in zip(game.score,game.income)]
            own=projected[root.focal]
            value=sum(2 if own>other else 1 if own==other else 0 for seat,other in enumerate(projected) if seat!=root.focal)
            self.assertEqual(run['value'],value)
            self.assertEqual(run['final_scores'],game.score)
            self.assertEqual(run['final_income'],game.income)
            for index in visited:
                expected[index]['visits']+=1
                expected[index]['value']+=value
            for index,action in selected:
                expected[index]['counts'][action]+=1
                expected[index]['values'][action]+=value
        self.assertEqual(transitions,96)
        self.assertEqual(result['counterfactual_dual_referee_turns'],transitions)
        for index,node in nodes.items():
            self.assertEqual(node['visits'],expected[index]['visits'])
            self.assertEqual(node['value_sum'],expected[index]['value'])
            self.assertEqual(node['counts'],expected[index]['counts'])
            self.assertEqual(node['values'],expected[index]['values'])
            if node['active']:
                self.assertTrue(all(node['counts'][action]>=2 for action in node['legal']))
        self.assertTrue(all(value['visits']>=2 for value in result['root_estimates'].values()))

    def test_indistinguishable_frozen_rivals_share_child_nodes_across_types(self):
        raw=sample_job([['STAY','SHIELD','SHIELD','SHIELD']],horizon=2,simulations=32)
        result=model.recommend(raw)
        by_action=collections.defaultdict(list)
        for trace in result['trace']:
            self.assertEqual(len(trace['steps']),2)
            by_action[trace['steps'][0]['own_action']].append(trace)
        shared_type_branches=0
        for runs in by_action.values():
            self.assertEqual(len({run['steps'][0]['observation'] for run in runs}),1)
            if len({run['joint_type_index'] for run in runs})>1:
                ids={run['steps'][1]['node'] for run in runs if run['steps'][1]['node'] is not None}
                self.assertEqual(len(ids),1)
                shared_type_branches+=1
        self.assertGreater(shared_type_branches,0)

    def test_complete_public_history_fixes_bookkeeping_despite_hidden_rival_cd(self):
        cases=[sample_job([['STAY']*4]*n) for n in (1,2,3)]
        cases.append(sample_job([['SHIELD','STAY','STAY','STAY']]+[['STAY']*4]*2))
        cases.append(sample_job(ambiguity_prefix()+[['STAY','STAY','SHIELD','STAY']]+[['STAY']*4]*2))
        cases.append(sample_job(shield_correlation_prefix(),focal=1))
        for raw in cases:
            root=model.prepare(raw)
            scores,income,frozen,cd,progress=public_accounting(raw)
            for hypothesis in root.states:
                self.assertEqual(hypothesis.score,scores)
                self.assertEqual(hypothesis.income,income)
                self.assertEqual(hypothesis.frozen,frozen)
                self.assertEqual(hypothesis.cd[root.focal],cd)
                self.assertEqual(hypothesis.prog[root.focal],progress)
        ambiguous=model.prepare(cases[-2])
        self.assertGreater(len({game.cd[1] for game in ambiguous.states}),1)

    def test_token_is_resolved_by_the_third_complete_public_view(self):
        for token in range(1,5):
            root=model.prepare(sample_job([['STAY']*4]*2,token=token))
            self.assertEqual({state.token for state in root.states},{(token+1)%4+1})

    def test_nontrivial_final_rank_has_no_terminal_observation_or_child(self):
        prefix=shield_correlation_prefix()[:12]+[['STAY']*4]*67
        raw=sample_job(prefix,focal=1,horizon=8,simulations=12,income_tail=80)
        result=model.recommend(raw)
        self.assertEqual(result['effective_horizon'],1)
        self.assertTrue(result['true_terminal_reached'])
        self.assertEqual(result['income_tail'],0)
        self.assertEqual(len(result['tree']),1)
        observed=set()
        for trace in result['trace']:
            scores=trace['final_scores'];own=scores[1]
            exact=sum(2 if own>score else 1 if own==score else 0 for seat,score in enumerate(scores) if seat!=1)
            self.assertEqual(trace['value'],exact)
            self.assertIsNone(trace['steps'][0]['observation'])
            self.assertTrue(trace['steps'][0]['terminal'])
            observed.add(exact)
        self.assertNotEqual(observed,{3})
        root=result['tree'][0]
        self.assertEqual(root['value_sum'],sum(row['value'] for row in result['trace']))

    def test_finite_uniform_tail_limit_does_not_remove_the_stored_log_entry(self):
        root=SimpleNamespace(history_sha256='unit-public',options={'seed':1},joint=((0,0,0.0),(0,63,-1000.0)))
        draws=iter((0,2**52-1))
        fake=SimpleNamespace(getrandbits=lambda count:next(draws))
        # Even the most favorable finite uniform for the tiny component cannot
        # beat the least favorable one for weight0. This is documented rounding
        # scope, not a claim of exact real-arithmetic rare-event sampling.
        with patch.object(model.random,'Random',return_value=fake):
            self.assertEqual(model.draw_joint(root,0),(0,0))
        self.assertEqual(len(root.joint),2)

    def test_cli_source_quarantine_never_publishes_or_creates_partial_output(self):
        source=self.folder/'input.json';output=self.folder/'quarantined.json'
        source.write_bytes(canonical(sample_job(horizon=1,simulations=8)))
        with patch.dict(model.FROZEN,{'opponent_prediction/intent_filter.py':'0'*64}),patch.object(sys,'argv',
                ['intent-search','--input',str(source),'--output',str(output)]):
            with self.assertRaisesRegex(ValueError,'QUARANTINED'): command.main()
        self.assertFalse(output.exists())
        self.assertFalse(list(self.folder.glob('.intent-search-unpublished-*')))

    def test_cli_exclusive_publication_preserves_a_concurrent_destination(self):
        source=self.folder/'input.json';output=self.folder/'concurrent.json'
        source.write_bytes(canonical(sample_job(horizon=1,simulations=8)))
        marker=b'EXISTING CONCURRENT EVIDENCE\n'
        def collision(pending,destination):
            Path(destination).write_bytes(marker)
            raise FileExistsError('Synthetic concurrent destination')
        method='rename' if os.name=='nt' else 'link'
        with patch.object(command.os,method,side_effect=collision),patch.object(sys,'argv',
                ['intent-search','--input',str(source),'--output',str(output)]):
            with self.assertRaises(FileExistsError): command.main()
        self.assertEqual(output.read_bytes(),marker)
        self.assertFalse(list(self.folder.glob('.intent-search-unpublished-*')))


if __name__=='__main__': unittest.main()
