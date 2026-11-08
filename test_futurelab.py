"""Physical, public-information and experimental-control tests for foresight."""
import copy
import unittest

from baselines import v8 as bot
import engine
from botlib import parse
from futurelab import agent,evaluate,models,opponents,rollout


class FutureTests(unittest.TestCase):
    def test_disabled_control_is_exact(self):
        task = evaluate.tasks("discovery",4,172681)[0]
        agent.VARIANTS["off"] = {}
        try:
            before,after = evaluate.play(task,"baseline"),evaluate.play(task,"off")
        finally:
            del agent.VARIANTS["off"]
        for key in ("pw","score","scores","action_hash"):
            self.assertEqual(before[key],after[key])

    def test_reconstruction_uses_current_public_history(self):
        game = engine.Game(base=engine.make_map(seed=35))
        player = bot.Agent(params={"throttle":0,"budget_ms":10000})
        for _ in range(8):
            view = game.views()[0]
            action = player(view)
            reconstructed = rollout.reconstruct(parse(view),player.tr)
            for key in ("owner","upg","home","pos","prog","score","income","turn"):
                self.assertEqual(getattr(reconstructed,key),getattr(game,key))
            game.step([action,"STAY","STAY","STAY"])

    def test_simulation_does_not_mutate_observation_or_input_world(self):
        game = engine.Game(base=engine.make_map(seed=71))
        before = tuple(copy.deepcopy(getattr(game,k)) for k in engine.Game.__slots__)
        route = ((1,1),(9,2))
        profiles = [models.PROFILES[0]]*4
        rollout.simulate(game,0,route,profiles,2,12)
        after = tuple(getattr(game,k) for k in engine.Game.__slots__)
        self.assertEqual(before,after)
        self.assertEqual(route,((1,1),(9,2)))

    def test_actual_root_action_is_forced(self):
        game = engine.Game(base=[1]*64)
        _,_,trace = rollout.simulate(game,0,((9,1),),[models.PROFILES[0]]*4,0,1,True,first_action="STAY")
        self.assertEqual(trace[0][2][0],0)
        self.assertEqual(game.prog[0],0)

    def test_rival_claim_and_upgrade_happen_before_late_arrival(self):
        game = engine.Game(base=[1]*64)
        game.base[11] = 3
        game.pos[1] = 11
        game.turn = 5
        profiles = [models.PROFILES[1]]*4
        _,_,trace = rollout.simulate(game,0,((11,1),),profiles,0,5,True,first_action="EAST")
        self.assertEqual(trace[0][0][11],2)
        self.assertEqual(trace[3][1][11],1)

    def test_future_raid_uses_three_stays_and_resets_upgrade(self):
        game = engine.Game(base=[1]*64)
        game.turn = 78
        game.base[1] = 3
        game.pos[0] = 1
        game.owner[1],game.upg[1] = 2,1
        game.income[1] += 6
        profiles = [(1,1,0.3,0,1,0)]*4
        own,pw,trace = rollout.simulate(game,0,((1,1),),profiles,0,3,True,first_action="STAY")
        self.assertEqual(trace[0][0][1],2)
        self.assertEqual(trace[1][0][1],2)
        self.assertEqual(trace[2][0][1],1)
        self.assertEqual(trace[2][1][1],0)
        self.assertEqual(own,54)  # 48 bounty + 3 home income + 3 captured income

    def test_future_shield_cancels_capture(self):
        game = engine.Game(base=[1]*64)
        game.pos[0] = 1
        game.owner[1] = 2
        game.income[1] += 1
        profiles = [(1,1,0.3,0,1,1)]*4
        _,_,trace = rollout.simulate(game,0,((1,1),),profiles,0,1,True,first_action="STAY")
        self.assertEqual(trace[0][0][1],2)

    def test_frozen_and_ambiguous_stays_do_not_update_intent(self):
        game = engine.Game(base=[1]*64)
        b = models.Beliefs()
        board = parse(game.views()[0])
        b.predict(game,board)
        game.frozen = [2]*4
        game.step(["STAY"]*4)
        b.observe(parse(game.views()[0]))
        self.assertEqual(b.samples,[0]*4)

    def test_common_noise_does_not_depend_on_route(self):
        self.assertEqual(rollout.noise(3,12,2),rollout.noise(3,12,2))
        self.assertNotEqual(rollout.noise(3,12,2),rollout.noise(3,12,1))

    def test_split_isolation_and_balanced_crossings(self):
        all_sets = [set(v) for v in opponents.SPLITS.values()]
        self.assertEqual(sum(map(len,all_sets)),len(set.union(*all_sets)))
        tasks = evaluate.tasks("discovery",112,193381)
        for kind in {t["map_kind"] for t in tasks}:
            group = [t for t in tasks if t["map_kind"] == kind]
            self.assertEqual(len({(t["seat"],t["token"]) for t in group}),16)

    def test_bounded_simulation_matches_when_time_is_unlimited(self):
        from futurelab import bounded
        for sample in range(6):
            game = engine.Game(base=engine.make_map(seed=sample))
            profiles = [models.PROFILES[(sample+j)%6] for j in range(4)]
            route = ((9,1),)
            expected = rollout.simulate(game,0,route,profiles,sample,12,first_action="EAST")
            actual = bounded.simulate(game,0,route,profiles,sample,12,float("inf"),"EAST")
            self.assertEqual(expected,actual)

    def test_expired_prediction_abstains_instead_of_reusing_labels(self):
        from futurelab import bounded
        game = engine.Game()
        b = models.Beliefs()
        board = parse(game.views()[0])
        b.predict(game,board)
        bounded.predict(b,game,board,float("-inf"))
        self.assertIsNone(b.prediction)
        b.observe(board)
        self.assertEqual(b.samples,[0]*4)

    def test_bounded_routes_match_unlimited_proposals(self):
        from futurelab import bounded
        game = engine.Game(base=engine.make_map(seed=581))
        player = bot.Agent(params={"throttle":0,"budget_ms":10000})
        view = game.views()[0]
        player(view)
        board = parse(view)
        args = (player,board[1],board[2],board[0],game.home,board[4],1,0,80,
                max(1,player.P["kappa"]*80),player._care(1,80))
        self.assertEqual(agent.routes(*args),bounded.proposals(*args,float("inf")))

    def test_corrected_job_commit_completes_neutral_capture(self):
        from futurelab.alternatives import ConsistentAgent,VARIANTS
        player = ConsistentAgent(params={"throttle":0,"budget_ms":10000},feature=VARIANTS["committed"])
        player.job = (1,1)
        game = engine.Game(base=[1]*64)
        first = player(game.views()[0])
        self.assertEqual(first,"EAST")
        game.step([first,"STAY","STAY","STAY"])
        second = player(game.views()[0])
        self.assertEqual(second,"STAY")
        game.step([second,"STAY","STAY","STAY"])
        self.assertEqual(game.owner[1],1)

    def test_slow_clock_budget_returns_legal_action(self):
        import time
        from unittest.mock import patch
        from futurelab.bounded import BoundedAgent
        from futurelab.protocol import REGISTRY
        real = time.perf_counter
        for factor in (10,50,100):
            player = BoundedAgent(feature=REGISTRY["one_job"])
            game = engine.Game(base=engine.make_map(seed=277))
            view = game.views()[0]
            origin = real()
            clock = lambda: origin+(real()-origin)*factor
            with patch("time.perf_counter",clock):
                start = clock()
                action = player(view)
                elapsed = (clock()-start)*1000
            self.assertIn(action,view.legal_actions)
            self.assertLess(elapsed,200)


if __name__ == "__main__":
    unittest.main(verbosity=2)
