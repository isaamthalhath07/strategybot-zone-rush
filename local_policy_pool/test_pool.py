"""Spawn and exact-source CPU tests; no CUDA, gold or study outcomes."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from evolution import oversight
from local_policy_pool import ActorPool,PoolExecutionError
from local_policy_pool.pool import ROOT,canonical,sha,source_pins
from tests import reference_engine as engine

TOY='''
import random
CONFIG={}
RNG=random.Random(934)
CALLS=0
def act(view):
 global CALLS
 CALLS+=1
 choices=list(view.legal_actions)
 return choices[(CALLS+int(RNG.random()*len(choices)))%len(choices)]
'''


def wire(view):
    return dict(board=[[[c.occupant,c.owner,c.is_upgraded,c.is_home,c.is_frozen,c.base_points] for c in row] for row in view.board],
                bot_id=view.bot_id,is_priority_token=view.is_priority_token,legal_actions=list(view.legal_actions))


class PoolTests(unittest.TestCase):
    def setUp(self):
        parent=ROOT/'local_policy_pool'/'.cache'; parent.mkdir(exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(prefix='SYNTHETIC-',dir=parent); self.addCleanup(self.temp.cleanup)
        self.folder=Path(self.temp.name); self.source=self.folder/'toy.py'; self.source.write_text(TOY,encoding='utf8')

    def registration(self,path=None,genes=None):
        path=path or self.source; entry=dict(path=str(path),sha256=sha(path.read_bytes()))
        fixtures=[dict(id='SYNTHETIC-'+str(i),candidate=entry['sha256'],seat=i,
            opponents=[dict(id='r%d'%s,seat=s,family='planner',seed=4,genes=copy.deepcopy(genes or {})) for s in range(4) if s!=i]) for i in range(2)]
        return dict(guards={str(path):entry['sha256']},candidates=[entry],sources={'planner':entry},fixtures=fixtures,
                    PRIVATE_HEADER_MUST_NEVER_REACH_WORKER='SYNTHETIC_SENTINEL')

    def serial(self,reg):
        entry=reg['candidates'][0]
        return [oversight.make_actors(entry,f,reg['sources'])[0] for f in reg['fixtures']]

    def input(self,games,turn):
        return dict(turn=turn,lanes=[dict(lane_id='SYNTHETIC-'+str(i),views=[wire(v) for v in g.views()]) for i,g in enumerate(games)])

    def test_80_turn_spawn_shards_match_serial_and_reset_without_cross_game_memory(self):
        reg=self.registration(); serial=self.serial(reg); games=[engine.Game(start_token=i+1) for i in range(2)]
        with ActorPool(2,evidence_directory=self.folder/'evidence') as pool:
            setup=pool.initialize_batch(reg,['SYNTHETIC-0','SYNTHETIC-1'])
            pids=[r['pid'] for r in setup['responses']]; self.assertEqual(len(set(pids)),2)
            first=None
            for turn in range(1,81):
                supplied=self.input(games,turn)
                expected=[[actor(view) for actor,view in zip(actors,g.views())] for actors,g in zip(serial,games)]
                got=pool.decide_turn(supplied)
                self.assertEqual(got['actions'],expected); self.assertEqual([r['pid'] for r in got['worker_chunks']],pids)
                if first is None: first=got['actions']
                for lane,proof in enumerate(got['proofs']):
                    self.assertEqual(proof['attempts_total'],[turn]*4); self.assertEqual(proof['completed_total'],[turn]*4)
                    self.assertTrue(all(p['public_memory_projection'] is None for p in proof['seats']))
                    games[lane].step(got['actions'][lane])
            with self.assertRaises(ValueError): pool.decide_turn(self.input(games,81))
            reset=pool.reset()
            for response in reset['responses']:
                self.assertTrue(all(c['attempts']==[80]*4 for c in response['lanes'].values()))
            pool.initialize_batch(reg,['SYNTHETIC-0','SYNTHETIC-1'])
            self.assertEqual(pool.decide_turn(self.input([engine.Game(start_token=i+1) for i in range(2)],1))['actions'],first)
        self.assertNotIn('SYNTHETIC_SENTINEL',(self.folder/'evidence'/'events.jsonl').read_text())

    def test_encoded_worker_error_preserves_attempts_and_forbids_retry(self):
        self.source.write_text('CONFIG={}\nCALLS=0\ndef act(view):\n global CALLS\n CALLS+=1\n if CALLS==2: raise ValueError("SYNTHETIC_STOP")\n return "STAY"\n',encoding='utf8')
        reg=self.registration(); games=[engine.Game(start_token=i+1) for i in range(2)]
        with ActorPool(2) as pool:
            pool.initialize_batch(reg,['SYNTHETIC-0','SYNTHETIC-1']); got=pool.decide_turn(self.input(games,1))
            for g,joint in zip(games,got['actions']): g.step(joint)
            with self.assertRaises(PoolExecutionError) as failed: pool.decide_turn(self.input(games,2))
            for response in failed.exception.evidence['responses']:
                self.assertEqual(response['error']['type'],'ValueError')
                self.assertEqual(response['active_seat_proofs'][0]['completed'],False)
                for lane in response['lane_counters'].values():
                    self.assertEqual(lane['attempts'],[2,1,1,1]); self.assertEqual(lane['completed'],[1]*4)
            with self.assertRaises(ValueError): pool.decide_turn(self.input(games,2))
            reset=pool.reset(); self.assertTrue(all(r['failed_batch'] for r in reset['responses']))

    def test_input_validation_has_zero_attempts_and_no_private_or_reordered_views(self):
        reg=self.registration(); games=[engine.Game(start_token=i+1) for i in range(2)]
        with ActorPool(1) as pool:
            pool.initialize_batch(reg,['SYNTHETIC-0','SYNTHETIC-1'])
            for mutation in ('extra','turn','bool-turn','float-turn','lane','board'):
                supplied=self.input(games,1)
                if mutation=='extra': supplied['lanes'][0]['views'][0]['scores']=[0]*4
                if mutation=='turn': supplied['turn']=2
                if mutation=='bool-turn': supplied['turn']=True
                if mutation=='float-turn': supplied['turn']=1.0
                if mutation=='lane': supplied['lanes'].reverse()
                if mutation=='board': supplied['lanes'][0]['views'][1]['board'][0][0][5]=3
                with self.subTest(mutation=mutation),self.assertRaises(ValueError): pool.decide_turn(supplied)
            result=pool.decide_turn(self.input(games,1))
            self.assertEqual([p['attempts_total'] for p in result['proofs']],[[1]*4,[1]*4])

    def test_known_e8_source_matches_serial_public_actions_and_memory_projections(self):
        entry=dict(path=str(ROOT/'bot.py'),sha256=sha((ROOT/'bot.py').read_bytes()))
        genes=oversight.player_namespace(entry)['CONFIG']; reg=self.registration(ROOT/'bot.py',genes)
        serial=self.serial(reg); games=[engine.Game(start_token=i+1) for i in range(2)]
        with ActorPool(2) as pool:
            pool.initialize_batch(reg,['SYNTHETIC-0','SYNTHETIC-1'])
            for turn in range(1,5):
                supplied=self.input(games,turn)
                expected=[[actor(view) for actor,view in zip(actors,g.views())] for actors,g in zip(serial,games)]
                got=pool.decide_turn(supplied); self.assertEqual(got['actions'],expected)
                for lane,proof in enumerate(got['proofs']):
                    for seat,item in enumerate(proof['seats']):
                        projection=item['public_memory_projection']
                        if projection is not None:
                            self.assertEqual(projection['scores'][1:],games[lane].score)
                            self.assertEqual(projection['progress'],games[lane].prog[seat])
                    games[lane].step(got['actions'][lane])

    def test_illegal_mutation_and_fallback_return_no_substitute_and_preserve_return_count(self):
        sources={
            'illegal':'CONFIG={}\ndef act(view): return "BOGUS"\n',
            'mutation':'CONFIG={}\ndef act(view):\n object.__setattr__(view,"bot_id",4)\n return "STAY"\n',
            'fallback':'CONFIG={}\n_policy_failures=1\ndef act(view): return "STAY"\n'}
        for mode,body in sources.items():
            with self.subTest(mode=mode):
                self.source.write_text(body,encoding='utf8'); reg=self.registration()
                with ActorPool(1) as pool:
                    pool.initialize_batch(reg,['SYNTHETIC-0','SYNTHETIC-1'])
                    with self.assertRaises(PoolExecutionError) as failed:
                        pool.decide_turn(self.input([engine.Game(),engine.Game(start_token=2)],1))
                    response=failed.exception.evidence['responses'][0]
                    proof=response['active_seat_proofs'][0]
                    self.assertTrue(proof['returned']); self.assertFalse(proof['completed'])
                    counters=response['lane_counters']['SYNTHETIC-0']
                    self.assertEqual(counters['attempts'],[1,0,0,0]); self.assertEqual(counters['returned'],[1,0,0,0])
                    self.assertEqual(counters['completed'],[0]*4)
                    self.assertEqual(response['active_completed_actions'],[])
                    if mode=='mutation': self.assertFalse(proof['input_unchanged'])
                    if mode=='fallback': self.assertTrue(proof['fallback'])

    def test_source_mutated_by_last_turn_callback_is_rejected_before_final_return(self):
        self.source.write_text('CONFIG={}\nCALLS=0\ndef act(view):\n global CALLS\n CALLS+=1\n if CALLS==80:\n  with open(__file__,"a") as handle: handle.write("\\n# SYNTHETIC_MUTATION\\n")\n return "STAY"\n',encoding='utf8')
        reg=self.registration(); games=[engine.Game(start_token=i+1) for i in range(2)]
        with ActorPool(1) as pool:
            pool.initialize_batch(reg,['SYNTHETIC-0','SYNTHETIC-1'])
            for turn in range(1,80):
                got=pool.decide_turn(self.input(games,turn))
                for game,joint in zip(games,got['actions']): game.step(joint)
            with self.assertRaises(PoolExecutionError) as failed: pool.decide_turn(self.input(games,80))
            response=failed.exception.evidence['responses'][0]
            self.assertIn('source bytes changed',response['error']['message'])
            self.assertEqual(len(response['completed_lane_actions']),2)
            for counters in response['lane_counters'].values(): self.assertEqual(counters['completed'],[80]*4)

    def test_frozen_qualification_spec_key_sets_accept_and_strip_pairing_provenance_before_dispatch(self):
        body=(ROOT/'.cache/local_cuda/qualification_gold_002/registration.json').read_bytes()
        self.assertEqual(sha(body),'8dce44596dd69a2958ead21030febd09ae485bf2f45069ec80f17d03ec319977')
        frozen=json.loads(body)
        shapes=sorted({tuple(sorted(spec)) for fixture in frozen['fixtures'] for spec in fixture['opponents']})
        self.assertEqual(len(shapes),2)
        self.assertTrue(all('pair_parameter_id' in keys for keys in shapes))
        for shape in shapes:
            with self.subTest(keys=shape):
                reg=self.registration()
                for fixture in reg['fixtures']:
                    for spec in fixture['opponents']:
                        values=dict(id=spec['id'],seat=spec['seat'],family='planner' if 'genes' in shape else 'wanderer',
                                    seed=4,genes={},epsilon=.1,commitment=.5,pair_parameter_id='a'*64)
                        spec.clear(); spec.update({key:copy.deepcopy(values[key]) for key in shape})
                original=copy.deepcopy(reg); dispatched=[]
                def collect(commands):
                    dispatched.extend(copy.deepcopy(commands))
                    return [dict(ok=True,source_sha256=source_pins()) for _ in commands]
                with ActorPool(1) as pool,patch.object(pool,'_collect',side_effect=collect):
                    pool.initialize_batch(reg,['SYNTHETIC-0','SYNTHETIC-1'])
                    command=dispatched[0]
                    self.assertEqual(command['operation'],'initialize')
                    self.assertNotIn('pair_parameter_id',canonical(command).decode())
                    for lane in command['lanes']:
                        for constructor_spec in lane['fixture']['opponents']:
                            self.assertEqual(set(constructor_spec),set(shape)-{'pair_parameter_id'})
                self.assertEqual(reg,original)

    def test_invalid_pairing_provenance_and_unknown_credential_fields_reject_before_dispatch(self):
        for value in ('A'*64,'g'*64,'a'*63,False,None):
            reg=self.registration(); reg['fixtures'][0]['opponents'][0]['pair_parameter_id']=value
            with self.subTest(value=value),ActorPool(1) as pool:
                with patch.object(pool,'_collect',side_effect=AssertionError('Worker dispatch occurred')):
                    with self.assertRaisesRegex(ValueError,'lowercase64-hex'): pool.initialize_batch(reg,['SYNTHETIC-0'])
        reg=self.registration(); reg['fixtures'][0]['opponents'][0].update(pair_parameter_id='a'*64,credentials='SYNTHETIC_PRIVATE_SENTINEL')
        with ActorPool(1) as pool,patch.object(pool,'_collect',side_effect=AssertionError('Worker dispatch occurred')):
            with self.assertRaisesRegex(ValueError,'credential field'): pool.initialize_batch(reg,['SYNTHETIC-0'])


if __name__=='__main__': unittest.main()
