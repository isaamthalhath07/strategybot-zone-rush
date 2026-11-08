"""Recording evidence, replay, durability, exports and strict-view regressions.

These tests use temporary history files, fake bot processes and an ephemeral
HTTP listener. They never contact or operate the user's live matches.
"""
import copy
from concurrent.futures import ThreadPoolExecutor
import hashlib
import http.client
from http.server import ThreadingHTTPServer
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest import mock

try:
    from . import history, server
except ImportError:
    import history
    import server


class RecordedProcess:
    def __init__(self, path):
        self.path, self.closed, self.calls = path, False, []

    def spawn(self):
        pass

    def finish_load(self, _timeout):
        return {"ok": True, "ms": .05, "error": None, "out": ""}

    def act(self, observation, turn, timing):
        self.calls.append(copy.deepcopy(observation))
        # Seeded route-independent progression produces claims/upgrades/freezes
        # while keeping this an evidence test, not a strength benchmark.
        moves = [a for a in observation["legal_actions"] if a not in ("STAY", "SHIELD")]
        action = moves[0] if turn % 5 == 1 and moves else "STAY"
        return dict(legal=list(observation["legal_actions"]), chosen=action, returned=None,
                    used=action, status="ok", ms=.125,
                    limit_ms=timing["first_ms"] if turn == 1 else timing["turn_ms"],
                    over=False, out="", error=None, note=None)

    def close(self):
        self.closed = True


class HistoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.match, cls.referee, cls.sources, cls.vendor = server.bootstrap()
        cls.catalog = server.Catalog(cls.sources.Repo(str(server.ROOT)), cls.sources)

    def setUp(self):
        fixture_root = (server.HERE / ".test-tmp").resolve()
        self.assertEqual(fixture_root.parent, server.HERE.resolve())
        fixture_root.mkdir(exist_ok=True)
        self.folder = tempfile.TemporaryDirectory(prefix="history-evidence-", dir=fixture_root)
        self.directory = Path(self.folder.name) / "history"
        self.app = self.make_app()
        self.state = self.app.new(dict(seed=158, seat=1, start_token=2))

    def make_app(self):
        app = server.App.__new__(server.App)
        app.match, app.referee, app.sources, app.vendor = self.match, self.referee, self.sources, self.vendor
        app.catalog, app.process_factory, app.game = self.catalog, RecordedProcess, None
        app.lock, app.history_dir = threading.RLock(), self.directory
        return app

    def tearDown(self):
        self.app.close()
        self.folder.cleanup()

    def action(self, action="STAY", **overrides):
        body = dict(game_id=self.state["game_id"], turn=self.state["turn"], action=action)
        body.update(overrides)
        result = self.app.action(body)
        self.state = result
        return result

    def saved(self, game_id=None):
        return self.app.history_export(game_id or self.state["game_id"])

    def test_initial_seed_map_rules_and_exact_source_provenance(self):
        data = self.saved()
        meta = data["metadata"]
        self.assertEqual(meta["format"], history.FORMAT)
        self.assertEqual(meta["seed"], 158)
        self.assertEqual(meta["human_seat"], 1)
        self.assertEqual(meta["start_token"], 2)
        self.assertEqual(meta["base"], self.referee.random_map(158))
        self.assertEqual(meta["rules"], dict(self.referee.DEFAULT_RULES, **server.NEW_GAME_RULES))
        self.assertEqual(meta["recording_start_turn"], 1)
        self.assertFalse(meta["partial"])
        self.assertEqual(meta["bot"]["sha256"], self.state["bot"]["sha256"])
        self.assertEqual(meta["bot"]["commit"], self.state["bot"]["commit"])
        self.assertEqual(meta["referee_sha256"], hashlib.sha256((server.VENDOR / "referee.py").read_bytes()).hexdigest())
        self.assertEqual(meta["initial"], self.app.game.g.snapshot())
        expected = hashlib.sha256(json.dumps(meta["rules"], sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        self.assertEqual(meta["rules_sha256"], expected)
        self.assertEqual(data["turns"], [])

    def test_durable_turn_is_readable_before_response_is_constructed(self):
        game, checks = self.app.game, []
        original_public = game.public

        def inspect_before_response(view="standard"):
            data = history.read_history(self.directory, game.id)
            self.assertEqual(len(data["turns"]), 1)
            self.assertEqual(data["turns"][0]["after"], game.g.snapshot())
            self.assertEqual(game.history.saved_turns, 1)
            checks.append(True)
            return original_public(view)

        real_fsync = history.os.fsync
        with mock.patch.object(history.os, "fsync", wraps=real_fsync) as sync:
            with mock.patch.object(game, "public", side_effect=inspect_before_response):
                self.action()
            self.assertGreaterEqual(sync.call_count, 1)
        self.assertTrue(checks)

    def test_rejected_illegal_duplicate_and_cross_game_turns_are_not_recorded(self):
        with self.assertRaises(server.APIError):
            self.action("NORTH")
        self.assertEqual(len(self.saved()["turns"]), 0)
        first_turn = self.state["turn"]
        self.action()
        for overrides in ({"turn": first_turn}, {"turn": 99}, {"game_id": "wrong"}):
            with self.subTest(overrides=overrides):
                with self.assertRaises(server.APIError):
                    self.action(**overrides)
        self.assertEqual(len(self.saved()["turns"]), 1)
        self.assertEqual(self.app.history_status()["saved_turns"], 1)

    def test_concurrent_same_turn_requests_append_once(self):
        body = dict(game_id=self.state["game_id"], turn=1, action="STAY")

        def request():
            try:
                self.app.action(body)
                return 200
            except server.APIError as exc:
                return exc.status

        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(lambda _: request(), range(2)))
        self.assertEqual(sorted(outcomes), [200, 409])
        self.assertEqual(len(history.read_history(self.directory, body["game_id"])["turns"]), 1)

    def test_transcript_replays_all_eighty_transitions_and_worker_inputs(self):
        for turn in range(1, 81):
            legal = self.app.game.g.legal(0)
            preferred = ("EAST", "STAY", "STAY", "STAY", "STAY", "SOUTH", "STAY", "SHIELD")[turn % 8]
            self.action(preferred if preferred in legal else "STAY")
        data = self.saved()
        meta = data["metadata"]
        replay = self.referee.Referee(meta["base"], rules=meta["rules"], start_token=meta["start_token"],
                                      max_turns=meta["max_turns"])
        self.assertEqual(replay.snapshot(), meta["initial"])
        self.assertEqual(len(data["turns"]), 80)
        for turn in data["turns"]:
            self.assertEqual(replay.snapshot(), turn["before"])
            for seat in range(1, 5):
                self.assertEqual(turn["observations"][str(seat)], replay.observation(seat))
            for seat, action in enumerate(turn["used"], 1):
                self.assertIn(action, replay.legal(seat-1))
            self.assertEqual(turn["bots"][0]["source"], "human")
            for seat in range(2, 5):
                record = turn["bots"][seat-1]
                self.assertEqual(record["ms"], .125)
                self.assertEqual(record["limit_ms"], 2000 if turn["turn"] == 1 else 200)
                self.assertEqual(self.app.game.workers[seat].calls[turn["turn"]-1], turn["observations"][str(seat)])
            self.assertEqual(replay.step(turn["used"]), turn["resolved"])
            self.assertEqual(replay.snapshot(), turn["after"])
        self.assertEqual(data["ending"]["reason"], "completed")
        self.assertEqual(data["ending"]["final"], replay.snapshot())
        self.assertTrue(self.state["over"])

    def test_previous_and_current_exports_survive_app_restart(self):
        self.action()
        previous = self.state["game_id"]
        self.state = self.app.new(dict(seed=159, seat=2, start_token=3))
        current = self.state["game_id"]
        self.action()
        self.app.close()
        restarted = self.make_app()
        try:
            self.assertEqual(restarted.state(), {"game": None})
            self.assertEqual(len(restarted.history_export(previous)["turns"]), 1)
            self.assertEqual(restarted.history_export(previous)["ending"]["reason"], "replaced")
            self.assertEqual(len(restarted.history_export(current)["turns"]), 1)
            self.assertEqual(restarted.history_export(current)["ending"]["reason"], "server-stopped")
            self.assertEqual({r["game_id"] for r in history.list_histories(self.directory)}, {previous, current})
        finally:
            restarted.close()

    def test_recording_failure_pauses_before_any_further_ai_turn(self):
        with mock.patch.object(history.os, "fsync", side_effect=OSError("test disk unavailable")):
            with self.assertRaises(server.APIError) as caught:
                self.action()
        self.assertEqual(caught.exception.status, 503)
        calls = [len(w.calls) for w in self.app.game.workers.values()]
        turn = self.app.game.g.turn
        with self.assertRaises(server.APIError) as caught:
            self.app.action(dict(game_id=self.app.game.id, turn=turn, action="STAY"))
        self.assertEqual(caught.exception.status, 503)
        self.assertEqual(self.app.game.g.turn, turn)
        self.assertEqual([len(w.calls) for w in self.app.game.workers.values()], calls)
        self.assertTrue(self.app.history_status()["error"])
        self.assertFalse(self.app.history_status()["recording"])

    def test_strict_responses_never_gain_history_or_observer_fields(self):
        expected_keys = {"game_id", "turn", "over", "observation"}
        strict = self.app.state("ai")
        self.assertEqual(set(strict), expected_keys)
        strict = self.action(view="ai")
        self.assertEqual(set(strict), expected_keys)
        self.assertEqual(set(strict["observation"]), {"board", "bot_id", "is_priority_token", "legal_actions"})
        self.assertEqual(strict["observation"], self.app.game.g.observation(1))
        self.assertEqual(len(self.saved()["turns"]), 1)

    def test_truncated_last_record_preserves_earlier_evidence(self):
        self.action()
        path = history.path_for(self.directory, self.state["game_id"])
        self.app.close()
        with path.open("a", encoding="utf-8") as stream:
            stream.write('{"type":"turn","turn":')
        data = history.read_history(self.directory, self.state["game_id"])
        self.assertEqual(len(data["turns"]), 1)
        self.assertTrue(data["incomplete_last_record"])

    def test_recovered_completed_snapshot_is_partial_and_restore_is_idempotent(self):
        # This models the provided completed observer snapshot, not fabricated
        # historical turns. Its earlier action sequence is intentionally unknown.
        observer = copy.deepcopy(self.state)
        observer.update(turn=81, over=True, legal_actions=[], scores=[900, 1000, 1100, 1200],
                        places=[4, 3, 2, 1])
        snapshot = Path(self.folder.name) / "completed-observer.json"
        snapshot.write_text(json.dumps(observer), encoding="utf-8")
        restored = self.make_app()
        restored.history_dir = Path(self.folder.name) / "recovered-history"
        try:
            restored.restore_completed(snapshot)
            data = restored.history_export(observer["game_id"])
            self.assertTrue(data["metadata"]["partial"])
            self.assertEqual(data["metadata"]["recording_start_turn"], 81)
            self.assertEqual(data["turns"], [])
            self.assertEqual(data["ending"]["reason"], "recovered-completed-snapshot")
            self.assertTrue(restored.history_status()["snapshot_only"])
            path = history.path_for(restored.history_dir, observer["game_id"])
            first_bytes = path.read_bytes()
            restored.restore_completed(snapshot)
            self.assertEqual(path.read_bytes(), first_bytes)
            self.assertEqual(restored.state(), observer)
            self.assertEqual(set(restored.state("ai")), {"game_id", "turn", "over", "observation"})
            with self.assertRaises(server.APIError) as caught:
                restored.action(dict(game_id=observer["game_id"], turn=81, action="STAY"))
            self.assertEqual(caught.exception.status, 409)
        finally:
            restored.close()

    def test_http_current_previous_download_and_identifier_guards(self):
        self.action()
        previous = self.state["game_id"]
        self.state = self.app.new(dict(seed=180, seat=1))
        current = self.state["game_id"]
        self.action()
        httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.handler_for(self.app))
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        connection = http.client.HTTPConnection("127.0.0.1", httpd.server_port, timeout=5)
        try:
            for path, expected in (("/api/history/status", 200), ("/api/history", 200),
                                   ("/api/history/" + previous, 200), ("/api/history/" + current, 200),
                                   ("/api/history/not-an-id", 400), ("/api/history/" + "f"*32, 404),
                                   ("/api/history/..%2Fserver.py", 400)):
                with self.subTest(path=path):
                    connection.request("GET", path)
                    response = connection.getresponse()
                    payload = json.loads(response.read())
                    self.assertEqual(response.status, expected, payload)
                    if path.endswith(previous) or path.endswith(current):
                        self.assertEqual(payload["game_id"], path.rsplit("/", 1)[-1])
                        self.assertEqual(len(payload["turns"]), 1)
            connection.request("GET", "/api/state?view=ai")
            response = connection.getresponse()
            self.assertEqual(response.status, 200)
            self.assertEqual(set(json.loads(response.read())), {"game_id", "turn", "over", "observation"})
        finally:
            connection.close()
            httpd.shutdown()
            httpd.server_close()
            thread.join(timeout=2)


if __name__ == "__main__":
    unittest.main()
