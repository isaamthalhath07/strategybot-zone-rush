"""Independent bounded protocol review: concurrent submits and isolated views."""
import copy
from concurrent.futures import ThreadPoolExecutor
import threading
import time
import unittest

from simulator import server


class RecordingWorker:
    def __init__(self, _path):
        self.calls = []
        self.closed = False

    def spawn(self):
        pass

    def finish_load(self, _limit):
        return {"ok": True}

    def act(self, observation, turn, timing):
        self.calls.append((copy.deepcopy(observation), turn, dict(timing)))
        # Even if a test adapter mutates its dict, another AI must retain its
        # independently frozen observation and the referee must stay unchanged.
        observation["board"][0][0][1] = 4
        observation["legal_actions"].append("NOT_AN_ACTION")
        time.sleep(0.01)
        return {"used": "STAY", "status": "ok"}

    def close(self):
        self.closed = True


class ReviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.match, cls.referee, _, _ = server.bootstrap()

    def setUp(self):
        self.game = server.HumanGame({"id": "review-fixture"}, "unused", 193, 1, 1,
                                    self.match, self.referee, RecordingWorker)
        self.app = server.App.__new__(server.App)
        self.app.lock = threading.RLock()
        self.app.game = self.game

    def tearDown(self):
        self.app.close()

    def test_concurrent_duplicate_advances_once(self):
        body = {"game_id": self.game.id, "turn": 1, "action": "EAST"}
        barrier = threading.Barrier(2)

        def request():
            barrier.wait(timeout=2)
            try:
                self.app.action(dict(body))
                return "accepted"
            except server.APIError as exc:
                return exc.status

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(lambda _: request(), range(2)))
        self.assertCountEqual(results, ["accepted", 409])
        self.assertEqual(self.game.g.turn, 2)
        self.assertTrue(all(len(worker.calls) == 1 for worker in self.game.workers.values()))

    def test_preaction_views_are_separate_and_public_only(self):
        before = {seat: self.game.g.observation(seat) for seat in self.game.workers}
        result = self.app.action({"game_id": self.game.id, "turn": 1, "action": "EAST"})
        for seat, worker in self.game.workers.items():
            observation, turn, timing = worker.calls[0]
            self.assertEqual(observation, before[seat])
            self.assertEqual(set(observation), {"board", "bot_id", "is_priority_token", "legal_actions"})
            self.assertEqual(turn, 1)
            self.assertTrue(timing["enforce"])
            self.assertEqual((timing["turn_ms"], timing["first_ms"]), (200, 2000))
        self.assertEqual(self.game.g.pos[0], 1)
        self.assertEqual(self.game.g.owner[0], 1)
        self.assertNotIn("NOT_AN_ACTION", result["legal_actions"])
        self.assertEqual(result["last_turn"]["requested"], ["EAST", None, None, None])
        self.assertFalse(any("pending" in key or "ai_actions" in key for key in result))

    def test_final_score_ties_ignore_cell_counts(self):
        self.game.g.score = [100, 100, 1, 0]
        self.game.g.owner[1] = 1
        self.game.g.turn = 81
        public = self.game.public()
        # The vendored UI uses competition ranks (shared first is 1/1/3/4),
        # while root engine.py uses mean places. Both must keep the pair tied.
        self.assertEqual(public["places"], [1, 1, 3, 4])
        self.assertEqual(public["legal_actions"], [])


if __name__ == "__main__":
    unittest.main()
