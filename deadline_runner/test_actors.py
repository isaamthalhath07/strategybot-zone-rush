"""Synthetic CPU actor checks; these confer no gold/study/campaign credit."""
import ast
import copy
from pathlib import Path
import tempfile
import unittest

from deadline_runner import actors
from evolution import oversight
from tests import reference_engine as engine


TOY = '''import random
CONFIG = {}
RNG = random.Random(934)
CALLS = 0
def act(view):
    global CALLS
    CALLS += 1
    assert CALLS <= 80, "globals reused across games"
    return RNG.choice(list(view.legal_actions))
'''


def compact(fixtures, games, turn):
    rows = []
    for fixture, game in zip(fixtures, games):
        board = [[c.occupant,c.owner,c.is_upgraded,c.is_home,c.is_frozen,c.base_points]
                 for row in game.board_view() for c in row]
        rows.append(dict(lane_id=fixture['id'],board=board,
                         legal=[[a in game.legal(seat) for a in actors.ACTIONS] for seat in range(4)],
                         priority=[game.token==seat+1 for seat in range(4)]))
    return dict(turn=turn,lanes=rows)


class ActorTests(unittest.TestCase):
    def setUp(self):
        parent = actors.ROOT/'deadline_runner'/'.cache'
        parent.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix='SYNTHETIC-ACTORS-',dir=parent)
        self.addCleanup(self.temp.cleanup)
        self.source = Path(self.temp.name)/'toy.py'
        self.source.write_text(TOY,encoding='utf8')
        self.entry = dict(path=str(self.source),sha256=actors.sha(self.source.read_bytes()))

    def registration(self, count=2, entries=None):
        entries = entries or [self.entry]
        fixtures = []
        for index in range(count):
            candidate = entries[index%len(entries)]
            fixtures.append(dict(id='SYNTHETIC-ACTOR-%d'%index,candidate=candidate['sha256'],
                seat=index%4,base=engine.make_map(seed=3100+index),token=index%4+1,
                opponents=[dict(id='SYNTHETIC-OPPONENT-%d'%seat,seat=seat,family='planner',
                                genes={},seed=2**64+seat,pair_parameter_id='a'*64)
                           for seat in range(4) if seat!=index%4]))
        return dict(guards={entry['path']:entry['sha256'] for entry in entries},
            candidates=copy.deepcopy(entries),sources={'planner':self.entry},fixtures=fixtures,
            observer_secret='PRIVATE-HEADER-MUST-NOT-ENTER-WORKERS')

    def games(self, registration):
        return [engine.Game(base=f['base'],start_token=f['token'],rules={'catch_requires_stay':True})
                for f in registration['fixtures']]

    def test_deep_immutable_shared_public_views_and_reference_legal_order(self):
        reg = self.registration(1)
        lane = compact(reg['fixtures'],self.games(reg),1)['lanes'][0]
        views = actors.freeze_lane(lane['board'],lane['legal'],lane['priority'])
        self.assertEqual(actors.View._fields,('board','bot_id','is_priority_token','legal_actions'))
        self.assertEqual(actors.Cell._fields,('occupant','owner','is_upgraded','is_home','is_frozen','base_points'))
        for seat, view in enumerate(views):
            self.assertIs(view.board,views[0].board)
            self.assertEqual(view.bot_id,seat+1)
            self.assertEqual(view.legal_actions,tuple(self.games(reg)[0].legal(seat)))
            self.assertIs(type(view.board),tuple)
            self.assertIs(type(view.board[0]),tuple)
            self.assertIs(type(view.is_priority_token),bool)
            for row in view.board:
                for cell in row:
                    self.assertEqual(tuple(type(v) for v in cell),(int,int,bool,bool,bool,int))
            with self.assertRaises(AttributeError): object.__setattr__(view,'bot_id',4)
            with self.assertRaises(AttributeError): object.__setattr__(view.board[0][0],'owner',4)
        # No alias to mutable transport leaves survives view construction.
        lane['board'][0][1] = 4
        self.assertEqual(views[0].board[0][0].owner,1)

    def test_constructor_strips_provenance_but_rejects_unknown_credentials(self):
        reg = self.registration()
        reg['candidates'][0].update(name='SYNTHETIC',source_kind='test-only',implementation_family='toy')
        lanes, sources = actors.constructor_messages(reg,[f['id'] for f in reg['fixtures']])
        self.assertEqual(set(sources['planner']),{'path','sha256'})
        self.assertNotIn('PRIVATE-HEADER',actors.canonical([lanes,sources]).decode())
        for lane in lanes:
            self.assertEqual(set(lane),{'lane_id','candidate','fixture'})
            self.assertEqual(set(lane['candidate']),{'path','sha256'})
            self.assertEqual(set(lane['fixture']),{'id','seat','opponents'})
            for spec in lane['fixture']['opponents']:
                self.assertNotIn('pair_parameter_id',spec)
                self.assertGreaterEqual(spec['seed'],2**64)
        bad = copy.deepcopy(reg)
        bad['fixtures'][0]['opponents'][0]['credential'] = 'DO-NOT-SEND'
        with self.assertRaises(ValueError): actors.constructor_messages(bad,[bad['fixtures'][0]['id']])
        bad = copy.deepcopy(reg)
        bad['fixtures'][0]['opponents'][0]['pair_parameter_id'] = 'not-a-digest'
        with self.assertRaises(ValueError): actors.constructor_messages(bad,[bad['fixtures'][0]['id']])
        bad = copy.deepcopy(reg)
        bad['fixtures'][0]['opponents'][0]['genes'] = {'credential':'forbidden'}
        with self.assertRaises(ValueError): actors.constructor_messages(bad,[bad['fixtures'][0]['id']])

    def test_spawn_shards_match_all_serial_callbacks_and_reset_fresh_globals(self):
        reg = self.registration()
        fixtures = reg['fixtures']; games = self.games(reg)
        serial = [oversight.make_actors(self.entry,f,reg['sources'])[0] for f in fixtures]
        ids = [f['id'] for f in fixtures]
        first = None
        with actors.FastActorPool(worker_count=2) as pool:
            setup = pool.initialize_batch(reg,ids)
            pids = [r['pid'] for r in setup['responses']]
            self.assertEqual(len(set(pids)),2)
            callbacks = 0
            for turn in range(1,81):
                envelope = compact(fixtures,games,turn)
                expected = [[actor(copy.deepcopy(view)) for actor,view in zip(group,game.views())]
                            for group,game in zip(serial,games)]
                result = pool.decide_turn(envelope)
                self.assertEqual([r['actions'] for r in result['lanes']],expected)
                self.assertEqual([r['pid'] for r in result['worker_chunks']],pids)
                self.assertEqual(result['admission_credit'],0)
                if turn==1: first = copy.deepcopy(expected)
                for row,game in zip(result['lanes'],games):
                    proof = row['proof']
                    self.assertEqual([proof[k] for k in ('attempted_callbacks','returned_callbacks','completed_callbacks')],[4]*3)
                    self.assertEqual([proof[k] for k in ('attempts_total','returned_total','completed_total')],[[turn]*4]*3)
                    self.assertEqual(proof['memory'],[None]*4)
                    self.assertTrue(all(set(item)=={'seat','callback_ms','attempted','returned','completed','fallback'} for item in proof['timing']))
                    callbacks += proof['completed_callbacks']
                    game.step(row['actions'])
            self.assertEqual(callbacks,640)
            self.assertTrue(all(game.over() for game in games))
            with self.assertRaises(ValueError): pool.decide_turn(compact(fixtures,games,81))
            reset = pool.reset()
            self.assertTrue(all(v['attempts_total']==[80]*4 for r in reset['responses'] for v in r['lanes'].values()))
            pool.initialize_batch(reg,ids)
            result = pool.decide_turn(compact(fixtures,self.games(reg),1))
            self.assertEqual([row['actions'] for row in result['lanes']],first)
            self.assertEqual([r['pid'] for r in result['worker_chunks']],pids)

    def test_exact_e8_blocker_feint_focals_match_serial_on_synthetic_public_history(self):
        names = ('bot.py','tester_bots/blocker.py',
                 'confirmation_campaign/evidence/architectures_v2/feint_original.py')
        pins = ('e8b3682d8b39d3fc4d22cdcd8927161290a90cd472d3ede4132ae716f8c6f8f5',
                '1bb70109a75e2880bfdf3ac9b6fd8e368b0f3d02b9a3e65de53cef0defa505e5',
                'f95dc9fc22660331b1368a876d907f111fd3cb21aef6e3e34315b41e6af94e94')
        entries = [dict(path=str(actors.ROOT/name),sha256=digest) for name,digest in zip(names,pins)]
        self.assertEqual([actors.sha(Path(e['path']).read_bytes()) for e in entries],list(pins))
        reg = self.registration(3,entries)
        # Keep opponents cheap and exact; the three distinct unchanged focal sources are the subject.
        fixtures = reg['fixtures']; games = self.games(reg)
        serial = [oversight.make_actors(entries[i],f,reg['sources']) for i,f in enumerate(fixtures)]
        with actors.FastActorPool(worker_count=2) as pool:
            pool.initialize_batch(reg,[f['id'] for f in fixtures])
            for turn in range(1,5):
                expected = [[actor(copy.deepcopy(view)) for actor,view in zip(group[0],game.views())]
                            for group,game in zip(serial,games)]
                result = pool.decide_turn(compact(fixtures,games,turn))
                self.assertEqual([row['actions'] for row in result['lanes']],expected)
                for row,group,fixture,game in zip(result['lanes'],serial,fixtures,games):
                    for seat,ns in enumerate(group[1]):
                        projection = actors._projection(ns,seat)
                        self.assertEqual(row['proof']['memory'][seat],projection)
                        if projection is not None:
                            self.assertEqual(projection['scores'][1:],game.score)
                            self.assertEqual(projection['progress'],game.prog[seat])
                            self.assertTrue(all(game.cd[s] in projection['cooldown_possible'][str(s+1)] for s in range(4)))
                    game.step(row['actions'])


if __name__=='__main__': unittest.main()
