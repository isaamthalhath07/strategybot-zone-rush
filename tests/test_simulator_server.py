"""Protocol, simultaneous information, process lifetime and deadline tests."""
import copy
import http.client
from http.server import ThreadingHTTPServer
import json
from pathlib import Path
import tempfile
import threading
import time
import unittest

from simulator import server


class FakeProcess:
    created = []

    def __init__(self, path):
        self.path, self.calls, self.closed = path, [], False
        self.status = "ok"
        self.created.append(self)

    def spawn(self):
        pass

    def finish_load(self, _timeout):
        return {"ok": True}

    def act(self, obs, turn, timing):
        self.calls.append((copy.deepcopy(obs), turn, dict(timing)))
        return dict(used="STAY", status=self.status, error=None, note=None)

    def close(self):
        self.closed = True


class ProtocolTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.match, cls.referee, cls.sources, _manifest = server.bootstrap()
        cls.catalog = server.Catalog()
        cls.metadata, cls.file = cls.catalog.resolve(cls.catalog.recommended_id)

    def setUp(self):
        self.app = server.App.__new__(server.App)
        self.app.match, self.app.referee, self.app.sources = self.match, self.referee, self.sources
        self.app.catalog, self.app.vendor = self.catalog, {}
        self.app.process_factory, self.app.game = FakeProcess, None
        self.app.lock = threading.RLock()
        self.state = self.app.new(dict(seed=7, seat=1, start_token=2))

    def tearDown(self):
        self.app.close()

    def submit(self, action="STAY", **overrides):
        body = dict(game_id=self.state["game_id"], turn=self.state["turn"], action=action)
        body.update(overrides)
        return self.app.action(body)

    def test_simultaneous_public_observations_and_no_pending_leaks(self):
        previous = {seat: self.app.game.g.observation(seat) for seat in self.app.game.workers}
        state = self.submit("EAST")
        for seat, process in self.app.game.workers.items():
            obs, turn, limits = process.calls[0]
            self.assertEqual(obs, previous[seat])
            self.assertEqual(set(obs), {"board", "bot_id", "is_priority_token", "legal_actions"})
            self.assertEqual(turn, 1)
            self.assertEqual(limits["turn_ms"], 200)
            self.assertEqual(limits["first_ms"], 2000)
        self.assertFalse({"prog", "cd", "progress", "cooldown", "pending", "positions", "frozen"} & set(state))
        self.assertEqual(state["last_turn"]["requested"], ["EAST", None, None, None])
        self.assertTrue(all(e["type"] not in ("progress", "reset") for e in state["last_turn"]["events"]))
        for row in state["board"]:
            for cell in row:
                self.assertEqual(set(cell), set(server.CELL_FIELDS))

    def test_illegal_action_does_not_advance_or_call_ai(self):
        with self.assertRaises(server.APIError) as caught:
            self.submit("NORTH")
        self.assertEqual(caught.exception.status, 400)
        self.assertEqual(self.app.game.g.turn, 1)
        self.assertTrue(all(not p.calls for p in self.app.game.workers.values()))

    def test_duplicate_future_missing_and_cross_game_requests_rejected(self):
        self.submit()
        for overrides in ({}, {"turn": 3}, {"turn": 2, "game_id": "other"}, {"turn": 2.0},
                          {"turn": True}, {"turn": 2, "game_id": None}):
            with self.subTest(overrides=overrides):
                with self.assertRaises(server.APIError) as caught:
                    self.submit(**overrides)
                self.assertEqual(caught.exception.status, 409)
        self.assertEqual(self.app.game.g.turn, 2)

    def test_new_game_closes_old_workers_and_rejects_old_id(self):
        old = self.app.game
        state = self.app.new(dict(seed=9001, seat=4, start_token=3))
        self.assertTrue(all(p.closed for p in old.workers.values()))
        self.assertNotEqual(state["game_id"], old.id)
        with self.assertRaises(server.APIError) as caught:
            self.app.action(dict(game_id=old.id, turn=1, action="STAY"))
        self.assertEqual(caught.exception.status, 409)

    def test_frozen_human_only_stays_and_failed_ai_uses_stay(self):
        self.app.game.g.frozen[0] = 2
        self.assertEqual(self.app.state()["legal_actions"], ["STAY"])
        with self.assertRaises(server.APIError):
            self.submit("EAST")
        for p in self.app.game.workers.values():
            p.status = "crash"
        state = self.submit()
        self.assertEqual(state["last_turn"]["effective"], ["STAY"] * 4)
        self.assertEqual(len(state["faults"]), 3)

    def test_invalid_seeds_and_seats_preserve_current_game(self):
        old = self.app.game
        for bad in (-1, 2147483648, "abc", 1.5, True, None, []):
            with self.subTest(seed=bad):
                with self.assertRaises(server.APIError):
                    self.app.new(dict(seed=bad))
                self.assertIs(self.app.game, old)
                self.assertFalse(old.closed)
        for field, value in (("seat", 0), ("seat", 5), ("start_token", True)):
            with self.assertRaises(server.APIError):
                self.app.new({field: value})

    def test_complete_eighty_turn_game_closes_workers(self):
        for _turn in range(80):
            self.state = self.submit()
        self.assertTrue(self.state["over"])
        self.assertEqual(self.state["turn"], 81)
        self.assertEqual(self.state["legal_actions"], [])
        self.assertTrue(all(p.closed for p in self.app.game.workers.values()))
        with self.assertRaises(server.APIError):
            self.submit()

    def test_catalog_refresh_preserves_active_game_identity(self):
        old_game = self.app.game
        choices = self.app.bots()
        self.assertIs(self.app.game, old_game)
        self.assertIn(choices["recommended_bot_id"], self.app.catalog.entries)
        self.assertEqual(self.app.state()["game_id"], self.state["game_id"])

    def assert_strict(self, payload):
        self.assertEqual(set(payload), {"game_id", "turn", "over", "observation"})
        self.assertEqual(set(payload["observation"]),
                         {"board", "bot_id", "is_priority_token", "legal_actions"})
        self.assertEqual(payload["observation"], self.app.game.g.observation(self.app.game.seat))
        forbidden = {"scores", "human_progress", "human_cooldown", "last_turn", "faults", "places", "bot", "seed"}
        self.assertFalse(forbidden & set(payload))

    def test_strict_view_uses_exact_public_observation_and_fresh_lists(self):
        strict = self.app.state("ai")
        self.assert_strict(strict)
        strict["observation"]["board"][0][0][1] = 999
        strict["observation"]["legal_actions"].append("DIAGONAL")
        self.assertEqual(self.app.game.g.owner[0], 1)
        self.assertNotIn("DIAGONAL", self.app.game.g.legal(0))
        self.app.game.g.frozen[0] = 1
        self.assertEqual(self.app.state("ai")["observation"]["legal_actions"], ["STAY"])
        self.assertIn("scores", self.app.state(), "standard view remains unchanged")

    def test_all_strict_http_endpoints_hide_observer_fields(self):
        httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.handler_for(self.app))
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        connection = http.client.HTTPConnection("127.0.0.1", httpd.server_port, timeout=5)

        def request(method, path, body=None):
            connection.request(method, path, json.dumps(body) if body is not None else None,
                               {"Content-Type": "application/json"})
            response = connection.getresponse()
            payload = json.loads(response.read())
            self.assertEqual(response.status, 200, payload)
            return payload

        try:
            before = request("GET", "/api/state?view=ai")
            self.assert_strict(before)
            fresh = request("POST", "/api/new", dict(seed=17, seat=3, view="ai"))
            self.assert_strict(fresh)
            expected_board = copy.deepcopy(fresh["observation"]["board"])
            after = request("POST", "/api/action", dict(game_id=fresh["game_id"], turn=fresh["turn"],
                                                       action="STAY", view="ai"))
            self.assert_strict(after)
            self.assertEqual(after["turn"], 2)
            for process in self.app.game.workers.values():
                self.assertEqual(process.calls[0][0]["board"], expected_board)
            standard = request("GET", "/api/state")
            self.assertIn("scores", standard)
            self.assertIn("last_turn", standard)
        finally:
            connection.close()
            httpd.shutdown()
            httpd.server_close()
            thread.join(timeout=2)

    def test_completed_strict_game_still_hides_scores_and_results(self):
        state = self.app.state("ai")
        for _turn in range(80):
            state = self.app.action(dict(game_id=state["game_id"], turn=state["turn"],
                                         action="STAY", view="ai"))
        self.assertTrue(state["over"])
        self.assert_strict(state)

    def test_http_rejects_cross_origin_and_stale_actions(self):
        httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.handler_for(self.app))
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        try:
            connection = http.client.HTTPConnection("127.0.0.1", httpd.server_port, timeout=5)
            payload = json.dumps(dict(game_id="wrong", turn=1, action="STAY"))
            connection.request("POST", "/api/action", payload, {"Content-Type": "application/json"})
            response = connection.getresponse()
            self.assertEqual(response.status, 409)
            response.read()
            connection.request("POST", "/api/action", payload,
                               {"Content-Type": "application/json", "Origin": "https://example.com"})
            response = connection.getresponse()
            self.assertEqual(response.status, 403)
            response.read()
            connection.close()
        finally:
            httpd.shutdown()
            httpd.server_close()
            thread.join(timeout=2)


class RealWorkerTests(unittest.TestCase):
    def test_strict_observation_equals_actual_worker_received_fields(self):
        match, referee, _sources, _manifest = server.bootstrap()
        fixture_root = (server.HERE / ".test-tmp").resolve()
        self.assertEqual(fixture_root.parent, server.HERE.resolve())
        fixture_root.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="strict-worker-", dir=fixture_root) as folder:
            path = Path(folder) / "bot.py"
            path.write_text(
                "import json\ndef act(state):\n"
                " fields=('occupant','owner','is_upgraded','is_home','is_frozen','base_points')\n"
                " obs=dict(board=[[[getattr(c,k) for k in fields] for c in row] for row in state.board],"
                "bot_id=state.bot_id,is_priority_token=state.is_priority_token,legal_actions=state.legal_actions)\n"
                " print(json.dumps(obs))\n return 'STAY'\n", encoding="utf-8")
            game = server.HumanGame(dict(id="fixture"), str(path), 23, 1, 1, match, referee,
                                    process_factory=FakeProcess)
            worker = match.BotProcess(str(path))
            try:
                observation = game.public("ai")["observation"]
                worker.spawn()
                self.assertTrue(worker.finish_load(5)["ok"])
                record = worker.act(observation, 1, server.TIMING)
                self.assertEqual(record["status"], "ok")
                self.assertEqual(json.loads(record["out"]), observation)
            finally:
                worker.close()
                game.close()

    def test_new_game_reaps_three_actual_old_processes(self):
        fixture_root = (server.HERE / ".test-tmp").resolve()
        fixture_root.mkdir(exist_ok=True)
        history_folder = tempfile.TemporaryDirectory(prefix="worker-history-", dir=fixture_root)
        self.addCleanup(history_folder.cleanup)
        app = server.App(history_dir=history_folder.name)
        fixture_bot = next(iter(app.catalog.entries))
        newest = []
        try:
            app.new(dict(bot_id=fixture_bot, seed=131, seat=1, start_token=1))
            old = [w.proc for w in app.game.workers.values()]
            app.new(dict(bot_id=fixture_bot, seed=132, seat=2, start_token=2))
            newest = [w.proc for w in app.game.workers.values()]
            self.assertTrue(all(p.poll() is not None for p in old))
            self.assertEqual(len({p.pid for p in newest}), 3)
            self.assertTrue({p.pid for p in old}.isdisjoint(p.pid for p in newest))
        finally:
            app.close()
        self.assertTrue(all(p.poll() is not None for p in newest))

    def test_independent_processes_deadlines_and_cleanup(self):
        match, referee, _sources, _manifest = server.bootstrap()
        fixture_root = (server.HERE / ".test-tmp").resolve()
        self.assertEqual(fixture_root.parent, server.HERE.resolve())
        fixture_root.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="zone-rush-human-", dir=fixture_root) as folder:
            path = Path(folder) / "bot.py"
            path.write_text("import time\nturn=0\ndef act(state):\n global turn\n turn+=1\n time.sleep(.25)\n return next((a for a in state.legal_actions if a!='STAY' and a!='SHIELD'),'STAY')\n", encoding="utf-8")
            game = server.HumanGame(dict(id="fixture"), str(path), 13, 1, 1, match, referee)
            processes = [w.proc for w in game.workers.values()]
            try:
                self.assertEqual(len({p.pid for p in processes}), 3)
                state = game.action("STAY", 1, game.id)
                self.assertFalse(state["faults"], "250 ms is allowed on the first AI turn")
                positions = list(game.g.pos)
                state = game.action("STAY", 2, game.id)
                self.assertEqual([f["kind"] for f in state["faults"]], ["late"] * 3)
                self.assertEqual(game.g.pos[1:], positions[1:], "late requests must become STAY")
            finally:
                game.close()
            self.assertTrue(all(p.poll() is not None for p in processes))


if __name__ == "__main__":
    unittest.main()
