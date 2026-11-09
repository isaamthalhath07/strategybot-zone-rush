"""Adversarial continuation mechanics, with ZERO campaign/strength credit.

The source tape below comes from tiny synthetic public-input controllers.  It
is deliberately sensitive to both RNG/callback history and a changed board.
"""
import copy
from dataclasses import FrozenInstanceError
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from evolution import oversight
from tests import reference_engine as engine


ROOT = Path(__file__).resolve().parents[1]

SYNTHETIC_SOURCE = '''
import random
CONFIG = {}
RNG = random.Random(4819)
CALLS = 0
DRAWS = []
OBSERVED = []
PAST_ACCEPTED = []
_history = {}
_input_failures = 0
_policy_failures = 0
def act(view):
    global CALLS
    CALLS += 1
    cells = [cell for row in view.board for cell in row]
    positions = tuple(next(p for p,c in enumerate(cells) if c.occupant == who)
                      for who in range(1,5))
    me = view.bot_id
    OBSERVED.append((positions, tuple(c.owner for c in cells), view.is_priority_token))
    PAST_ACCEPTED.append(_history.get(me, {}).get('last'))
    draw = RNG.random()
    DRAWS.append(draw)
    action = 'STAY'
    if me == 2 and positions[0] != 0 and positions[1] == 7:
        action = 'WEST'
    elif me == 3:
        legal = [a for a in view.legal_actions if a != 'SHIELD']
        action = legal[int(draw*len(legal))]
    memory = _history.setdefault(me, {})
    memory.update(last=action, intent_from_proposal=action, intent_clock=CALLS)
    return action
'''


def pairwise_numerator(scores, focal):
    return sum(2 if scores[focal] > other else 1 if scores[focal] == other else 0
               for seat, other in enumerate(scores) if seat != focal)


class SyntheticControllers(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='.synthetic-',dir=Path(__file__).parent)
        self.addCleanup(self.temporary.cleanup)
        path = Path(self.temporary.name)/'synthetic_actor.py'
        path.write_text(SYNTHETIC_SOURCE, encoding='utf8')
        self.candidate = dict(path=str(path), sha256=hashlib.sha256(path.read_bytes()).hexdigest())
        self.sources = dict(planner=self.candidate)
        self.fixture = dict(id='SYNTHETIC_ONLY', map_id='SYNTHETIC_ONLY', seat=0,
                            field='economic', base=engine.make_map(canonical=True), token=1,
                            opponents=[dict(id='SYNTHETIC_%d'%seat, seat=seat,
                                            family='planner', genes={}) for seat in (1,2,3)])

    def independent_source_tape(self):
        # Deliberately independent of every continuation helper under test.
        actors, namespaces = oversight.make_actors(self.candidate, self.fixture, self.sources)
        game = engine.Game(base=self.fixture['base'], rules={'catch_requires_stay':True})
        actions = []
        while not game.over():
            views = game.views()
            chosen = [actor(copy.deepcopy(views[seat])) for seat,actor in enumerate(actors)]
            self.assertTrue(all(action in game.legal(seat) for seat,action in enumerate(chosen)))
            actions.append(chosen)
            game.step(chosen)
        return dict(actions=actions, scores=list(game.score),
                    focal_pw=pairwise_numerator(game.score,0)/2,
                    focal_score=game.score[0]), namespaces

    def observed_continuation(self, row, requested, *, turn=6):
        from intent_trials import experiment as trial
        fresh_namespaces, trace, interventions, compared_turns = [], [], [], []
        factory, step, compare = oversight.make_actors, engine.Game.step, oversight.state_equal

        def watch_factory(*args,**kwargs):
            actors,namespaces = factory(*args,**kwargs)
            fresh_namespaces.append(namespaces)
            return actors,namespaces

        def watch_step(game,joint):
            trace.append(list(joint))
            if game.turn == turn:
                memory = fresh_namespaces[-1][0]['_history'][1]
                interventions.append(copy.deepcopy(memory))
            return step(game,joint)

        def watch_compare(game,shadow):
            compared_turns.append(game.turn)
            return compare(game,shadow)

        case = dict(fixture=self.fixture,row=row,turn=turn)
        with patch.object(oversight,'make_actors',side_effect=watch_factory), \
             patch.object(engine.Game,'step',watch_step), \
             patch.object(oversight,'state_equal',side_effect=watch_compare):
            result = trial.continuation(self.candidate,case,self.sources,requested)
        self.assertEqual(len(fresh_namespaces),1,'Each branch must freshly build exactly four actors')
        namespaces = fresh_namespaces[0]
        self.assertEqual([ns['CALLS'] for ns in namespaces],[80]*4)
        self.assertEqual(len(trace),80)
        self.assertEqual(len(interventions),1)
        # Independent observer counters, rather than trusting reported constants.
        self.assertEqual(result['audit']['callbacks_regenerated'],sum(ns['CALLS'] for ns in namespaces))
        self.assertEqual(result['audit']['calls_by_seat'],[ns['CALLS'] for ns in namespaces])
        self.assertEqual([rec['calls'] for rec in result['audit']['timing']],[80]*4)
        self.assertEqual(result['audit']['dual_referee_turns'],len(trace))
        self.assertEqual(compared_turns,list(range(1,82)))
        self.assertEqual(result['actions'],trace)
        expected_digest = hashlib.sha256(json.dumps(trace,sort_keys=True,
            separators=(',',':'),allow_nan=False).encode()).hexdigest()
        self.assertEqual(result['action_trace_sha256'],expected_digest)
        for seat in range(1,4):
            self.assertEqual([view[:2] for view in namespaces[seat]['OBSERVED']],
                             [view[:2] for view in namespaces[0]['OBSERVED']])
        independent = engine.Game(base=self.fixture['base'],rules={'catch_requires_stay':True})
        for joint in trace:
            self.assertTrue(all(action in independent.legal(seat) for seat,action in enumerate(joint)))
            independent.step(joint)
        self.assertTrue(independent.over())
        self.assertEqual(result['scores'],independent.score)
        self.assertEqual(result['pairwise_points'],pairwise_numerator(independent.score,0)/2)
        return result,trace,namespaces,interventions[0]

    def test_immutable_actor_views_preserve_original_legal_order_and_are_isolated(self):
        from intent_trials import experiment as trial
        raw = engine.Game().views()
        views = [trial.immutable_view(view) for view in raw]
        self.assertEqual(views[0].legal_actions,tuple(raw[0].legal_actions))
        self.assertEqual(set(views[0].__slots__),{'board','bot_id','is_priority_token','legal_actions'})
        self.assertEqual(set(views[0].board[0][0].__slots__),
                         {'occupant','owner','is_upgraded','is_home','is_frozen','base_points'})
        for view in views[1:]:
            self.assertIsNot(view.board,views[0].board)
            self.assertIsNot(view.board[0][0],views[0].board[0][0])
        with self.assertRaises(FrozenInstanceError):
            views[0].board[0][0].owner = 2
        with self.assertRaises(TypeError):
            views[0].legal_actions[0] = 'EAST'
        self.assertEqual(raw[0].board[0][0].owner,1)

    def test_callback_admission_rejects_mutation_illegal_actions_and_fallbacks(self):
        from intent_trials import experiment as trial

        def mutate(view):
            # Deliberate bypass of the ordinary frozen-dataclass protection:
            # the independent before/after signature must still reject it.
            object.__setattr__(view.board[0][0],'owner',2)
            return 'STAY'

        for label,first,namespace in (
            ('mutation',mutate,None),
            ('illegal',lambda view:'FORBIDDEN',None),
            ('input fallback',lambda view:'STAY',{'_input_failures':1}),
            ('policy fallback',lambda view:'STAY',{'_policy_failures':1}),
        ):
            with self.subTest(label=label):
                game = engine.Game()
                shadow = oversight.referee.Referee(game.base)
                audit = dict(callbacks_regenerated=0,calls_by_seat=[0]*4,
                             max_callback_ms=0.0,public_memory_oracles=0)
                with self.assertRaises(ValueError):
                    trial.actor_actions(game,shadow,[first]+[lambda view:'STAY']*3,
                                        [namespace,None,None,None],audit)
                self.assertEqual(audit['callbacks_regenerated'],1)
                self.assertEqual(audit['calls_by_seat'],[1,0,0,0])
                self.assertEqual(game.owner[0],1,'Actor mutation escaped its isolated view')

    def test_both_first_and_regular_deadlines_are_enforced(self):
        from intent_trials import experiment as trial
        for turn,elapsed in ((1,2.001),(2,.201)):
            with self.subTest(turn=turn):
                game = engine.Game()
                shadow = oversight.referee.Referee(game.base)
                game.turn = shadow.turn = turn
                audit = dict(callbacks_regenerated=0,calls_by_seat=[0]*4,
                             max_callback_ms=0.0,public_memory_oracles=0)
                with patch.object(trial.time,'perf_counter',side_effect=[0.0,elapsed]), \
                     self.assertRaisesRegex(ValueError,'deadline'):
                    trial.actor_actions(game,shadow,[lambda view:'STAY']*4,[None]*4,audit)
                self.assertEqual(audit['callbacks_regenerated'],1)

    def test_supported_public_memory_oracles_are_exercised_and_fail_closed(self):
        from intent_trials import experiment as trial

        def setup():
            game = engine.Game()
            shadow = oversight.referee.Referee(game.base)
            namespaces = [dict(_history={seat+1:dict(progress=0,scores=[0]*5,
                cooldown_possible=[set()]+[{0} for _ in range(4)],inference_failures=0)})
                for seat in range(4)]
            audit = dict(callbacks_regenerated=0,calls_by_seat=[0]*4,
                         max_callback_ms=0.0,public_memory_oracles=0)
            return game,shadow,namespaces,audit

        game,shadow,namespaces,audit = setup()
        trial.actor_actions(game,shadow,[lambda view:'STAY']*4,namespaces,audit)
        self.assertEqual(audit['public_memory_oracles'],4)
        for label in ('score','progress','cooldown','inference fallback'):
            with self.subTest(label=label):
                game,shadow,namespaces,audit = setup()
                memory = namespaces[0]['_history'][1]
                if label == 'score':
                    memory['scores'][1] = 1
                elif label == 'progress':
                    memory['progress'] = 1
                elif label == 'cooldown':
                    memory['cooldown_possible'][2] = {1}
                else:
                    memory['inference_failures'] = 1
                with self.assertRaisesRegex(ValueError,'Public memory'):
                    trial.actor_actions(game,shadow,[lambda view:'STAY']*4,namespaces,audit)
                self.assertEqual(audit['public_memory_oracles'],0)

    def test_baseline_and_explicit_same_action_have_identical_full_tape(self):
        row,_ = self.independent_source_tape()
        baseline,trace,_,_ = self.observed_continuation(row,None)
        explicit,forced,_,_ = self.observed_continuation(row,row['actions'][5][0])
        self.assertEqual(trace,row['actions'])
        self.assertEqual(forced,trace)
        self.assertEqual(explicit['scores'],baseline['scores'])
        self.assertEqual(explicit['pairwise_points'],pairwise_numerator(row['scores'],0)/2)
        self.assertEqual(explicit['action_trace_sha256'],baseline['action_trace_sha256'])
        self.assertTrue(explicit['explicit_baseline_reproduced'])

    def test_changed_board_causes_real_rival_response_from_next_turn(self):
        row,_ = self.independent_source_tape()
        result,trace,namespaces,memory = self.observed_continuation(row,'EAST')
        self.assertEqual(trace[:5],row['actions'][:5])
        self.assertEqual(trace[5][1:],row['actions'][5][1:])
        self.assertEqual(trace[5][0],'EAST')
        self.assertEqual(trace[6][1],'WEST')
        self.assertNotEqual(trace[6][1],row['actions'][6][1])
        self.assertEqual(memory['last'],'EAST')
        self.assertEqual(memory['intent_from_proposal'],'STAY')
        self.assertEqual(namespaces[0]['PAST_ACCEPTED'][6],'EAST')
        self.assertNotEqual(result['scores'],row['scores'])
        self.assertNotEqual(result['pairwise_points'],row['focal_pw'])
        # Replaying the original future tape would erase the measured response.
        broken = engine.Game(base=self.fixture['base'],rules={'catch_requires_stay':True})
        broken_trace = copy.deepcopy(row['actions'])
        broken_trace[5][0] = 'EAST'
        for joint in broken_trace:
            broken.step(joint)
        self.assertNotEqual(result['scores'],broken.score)

    def test_branch_cannot_read_recorded_future_and_replays_rng_from_opening(self):
        row,_ = self.independent_source_tape()
        first,trace,namespaces,_ = self.observed_continuation(row,'EAST')

        class PrefixOnlyTape(list):
            def __getitem__(self,index):
                if isinstance(index,slice):
                    if index.stop is None or index.stop > 6:
                        raise AssertionError('Counterfactual consulted recorded future tape')
                elif index >= 6 or index < 0:
                    raise AssertionError('Counterfactual consulted recorded future tape')
                return super().__getitem__(index)

        poisoned = dict(row,actions=PrefixOnlyTape(row['actions'][:6]+[['FORBIDDEN_FUTURE']*4 for _ in range(74)]))
        second,again,fresh,_ = self.observed_continuation(poisoned,'EAST')
        self.assertEqual(again,trace)
        self.assertEqual(second['scores'],first['scores'])
        for old,new in zip(namespaces,fresh):
            self.assertIsNot(old,new)
            self.assertIsNot(old['RNG'],new['RNG'])
            self.assertEqual(old['DRAWS'],new['DRAWS'])
            self.assertEqual(old['OBSERVED'],new['OBSERVED'])

    def test_keyboard_interrupt_preserves_partial_branch_and_is_reraised(self):
        from intent_trials import experiment as trial
        row,_ = self.independent_source_tape()
        interruption = KeyboardInterrupt('SYNTHETIC_INTERRUPT_ONLY')
        factory = oversight.make_actors

        def interrupting_factory(*args,**kwargs):
            actors,namespaces = factory(*args,**kwargs)
            original = actors[0]

            def interrupt_on_third_callback(view):
                if namespaces[0]['CALLS'] == 2:
                    raise interruption
                return original(view)

            actors[0] = interrupt_on_third_callback
            return actors,namespaces

        with patch.object(oversight,'make_actors',side_effect=interrupting_factory), \
             self.assertRaises(KeyboardInterrupt) as caught:
            trial.continuation(self.candidate,dict(fixture=self.fixture,row=row,turn=6),self.sources)
        self.assertIs(caught.exception,interruption)
        partial = caught.exception.branch_evidence
        self.assertEqual(partial['actions'],row['actions'][:2])
        self.assertEqual(partial['audit']['callbacks_regenerated'],8)
        self.assertEqual(partial['audit']['calls_by_seat'],[2]*4)
        self.assertEqual(partial['audit']['dual_referee_turns'],2)
        self.assertEqual(partial['current_turn'],3)
        self.assertEqual(partial['root_turn'],6)
        self.assertIsNone(partial['requested'])

    def test_fresh_execution_rebuilds_function_globals_and_past_rng(self):
        actors, namespaces = oversight.make_actors(self.candidate, self.fixture, self.sources)
        fresh, fresh_namespaces = oversight.make_actors(self.candidate, self.fixture, self.sources)
        self.assertEqual(len({id(ns) for ns in namespaces+fresh_namespaces}),8)
        self.assertIs(actors[0].__globals__, namespaces[0])
        self.assertIs(fresh[0].__globals__, fresh_namespaces[0])
        views = engine.Game().views()
        for seat in range(4):
            self.assertEqual(actors[seat](copy.deepcopy(views[seat])),
                             fresh[seat](copy.deepcopy(views[seat])))
        self.assertEqual([ns['DRAWS'] for ns in namespaces],
                         [ns['DRAWS'] for ns in fresh_namespaces])
        # A tempting deepcopy of callbacks does not clone their function globals.
        broken_branch = copy.deepcopy(actors)
        self.assertIs(broken_branch[0],actors[0])
        broken_branch[0](copy.deepcopy(views[0]))
        self.assertEqual(namespaces[0]['CALLS'],2)
        self.assertEqual(fresh_namespaces[0]['CALLS'],1)
        self.assertNotEqual(namespaces[0]['DRAWS'][-1],fresh_namespaces[0]['DRAWS'][-1])

    def test_accepted_shield_history_sync_is_needed_for_real_public_inference(self):
        entry = dict(path=str(ROOT/'bot.py'),
                     sha256=hashlib.sha256((ROOT/'bot.py').read_bytes()).hexdigest())
        good, stale = oversight.player_namespace(entry), oversight.player_namespace(entry)
        game = engine.Game(rules={'catch_requires_stay':True})
        for namespace in (good,stale):
            proposed = namespace['act'](copy.deepcopy(game.views()[0]))
            self.assertNotEqual(proposed,'SHIELD')
        retained_intent = copy.deepcopy(good['_history'][1])
        good['_history'][1]['last'] = 'SHIELD'
        self.assertEqual({k:v for k,v in good['_history'][1].items() if k!='last'},
                         {k:v for k,v in retained_intent.items() if k!='last'})
        game.step(['SHIELD','STAY','STAY','STAY'])
        good['act'](copy.deepcopy(game.views()[0]))
        stale['act'](copy.deepcopy(game.views()[0]))
        memory = good['_history'][1]
        self.assertEqual(memory['inference_failures'],0)
        self.assertEqual(memory['progress'],game.prog[0])
        self.assertEqual(memory['scores'][1:],game.score)
        self.assertTrue(all(game.cd[i] in memory['cooldown_possible'][i+1] for i in range(4)))
        self.assertGreater(stale['_history'][1]['inference_failures'],0)


if __name__ == '__main__':
    unittest.main()
