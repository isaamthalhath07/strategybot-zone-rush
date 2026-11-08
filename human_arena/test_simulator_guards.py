"""Regression tests for worker failures, saved corruption and candidate pinning."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest import mock

try:
    from . import history, server
    from .test_server import FakeProcess
except ImportError:
    import history
    import server
    from test_server import FakeProcess


class RepoFixture:
    body = b"def act(state):\n return 'STAY'\n"

    def refs(self):
        return [dict(kind="remote", ref=server.PREFERRED_REF, commit="a"*40)]

    def bots_in_commit(self, _sha):
        return [dict(path=server.PREFERRED_PATH)]

    def blobs(self, specs):
        return [self.body for _ in specs]


class CandidateTests(unittest.TestCase):
    def setUp(self):
        folder = (server.HERE / ".test-tmp").resolve()
        self.assertEqual(folder.parent, server.HERE.resolve())
        folder.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix="candidate-guards-", dir=folder)
        self.root = Path(self.temp.name)
        self.candidates = self.root / "candidates"
        self.candidates.mkdir()
        self.body = b"def act(state):\n return state.legal_actions[0]\n"
        (self.candidates / "fixed.py").write_bytes(self.body)
        self.digest = hashlib.sha256(self.body).hexdigest()

    def tearDown(self):
        self.temp.cleanup()

    def manifest(self, **changes):
        data = dict(format="zone-rush-candidate-catalog/1", candidates=[dict(path="fixed.py", sha256=self.digest,
                    label="Validated repaired policy")], recommended_sha256=self.digest,
                    recommendation="Best on the stated validation panel; unknown opponents remain untested.")
        data.update(changes)
        (self.candidates / "validated_catalog.json").write_text(json.dumps(data), encoding="utf-8")

    def test_validated_recommendation_pins_exact_bytes_and_metadata(self):
        self.manifest()
        catalog = server.Catalog(RepoFixture(), None, self.candidates)
        self.assertEqual(catalog.recommended_id, self.digest[:20])
        self.assertIn("stated validation panel", catalog.public()["recommendation"])
        with mock.patch.object(server, "HERE", self.root):
            metadata, filename = catalog.resolve(catalog.recommended_id)
            pinned = Path(filename)
            self.assertEqual(pinned.read_bytes(), self.body)
            self.assertEqual(metadata["source"], "local-candidate")
            self.assertIsNone(metadata["commit"])
            self.assertEqual(metadata["sha256"], self.digest)
            self.assertNotIn(str(self.root), json.dumps(metadata))
            (self.candidates / "fixed.py").write_text("def act(state):\n return 'SHIELD'\n", encoding="utf-8")
            self.assertEqual(pinned.read_bytes(), self.body, "editing a candidate must not alter a match snapshot")
            with self.assertRaises(RuntimeError):
                catalog.resolve(catalog.recommended_id)

    def test_bad_hash_path_or_manifest_never_overrides_git_recommendation(self):
        git_id = hashlib.sha256(RepoFixture.body).hexdigest()[:20]
        variants = [dict(candidates="bad"), dict(recommended_sha256="f"*64),
                    dict(candidates=[dict(path="../outside.py", sha256=self.digest, label="bad path")]),
                    dict(candidates=[dict(path="fixed.py", sha256="f"*64, label="wrong hash")])]
        for changes in variants:
            with self.subTest(changes=changes):
                self.manifest(**changes)
                catalog = server.Catalog(RepoFixture(), None, self.candidates)
                self.assertEqual(catalog.recommended_id, git_id)
                self.assertTrue(catalog.public()["warnings"])
                self.assertNotIn(self.digest[:20], catalog.entries)

    def test_no_manifest_exposes_no_unvalidated_local_policy(self):
        catalog = server.Catalog(RepoFixture(), None, self.candidates)
        self.assertNotIn(self.digest[:20], catalog.entries)
        with self.assertRaises(server.APIError):
            catalog.resolve([])


class SimulatorGuardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.match, cls.referee, cls.sources, cls.vendor = server.bootstrap()
        cls.catalog = server.Catalog(RepoFixture(), cls.sources)

    def setUp(self):
        folder = (server.HERE / ".test-tmp").resolve()
        self.assertEqual(folder.parent, server.HERE.resolve())
        folder.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix="simulator-guards-", dir=folder)
        self.app = server.App.__new__(server.App)
        self.app.match, self.app.referee, self.app.sources, self.app.vendor = self.match, self.referee, self.sources, self.vendor
        self.app.catalog, self.app.process_factory, self.app.game = self.catalog, FakeProcess, None
        self.app.lock, self.app.history_dir = threading.RLock(), Path(self.temp.name) / "history"
        self.state = self.app.new(dict(seed=190, seat=1))

    def tearDown(self):
        self.app.close()
        self.temp.cleanup()

    def submit(self, **changes):
        body = dict(action="STAY", game_id=self.app.game.id, turn=self.app.game.g.turn)
        body.update(changes)
        return self.app.action(body)

    def test_worker_protocol_exception_is_one_stay_not_a_partially_retried_turn(self):
        worker = self.app.game.workers[2]
        worker.act = mock.Mock(side_effect=ValueError("malformed worker JSON"))
        state = self.submit()
        self.assertEqual(state["turn"], 2)
        self.assertEqual(worker.state, "restart")
        self.assertTrue(worker.closed)
        self.assertEqual(state["last_turn"]["effective"][1], "STAY")
        self.assertEqual(state["faults"][0]["kind"], "worker-error")
        self.assertEqual(len(self.app.game.workers[3].calls), 1)
        saved = self.app.history_export(state["game_id"])
        self.assertEqual(len(saved["turns"]), 1)
        self.assertEqual(saved["turns"][0]["bots"][1]["status"], "worker-error")
        with self.assertRaises(server.APIError):
            self.submit(turn=1)
        self.assertEqual(worker.act.call_count, 1)

    def test_nonfinite_worker_timing_cannot_poison_recording(self):
        self.app.game.workers[2].act = lambda *_: dict(status="ok", used="STAY", ms=float("nan"))
        state = self.submit()
        self.assertEqual(state["turn"], 2)
        self.assertIsNone(self.app.game.recording_error)
        self.assertEqual(state["faults"][0]["kind"], "worker-error")
        self.assertEqual(len(self.app.history_export(state["game_id"])["turns"]), 1)

    def test_mutated_worker_legal_list_cannot_authorize_illegal_move(self):
        def act(observation, *_args):
            observation["legal_actions"].append("NORTH")
            return dict(status="ok", used="NORTH", ms=.1)
        self.app.game.workers[2].act = act
        state = self.submit()
        self.assertEqual(state["last_turn"]["effective"][1], "STAY")
        self.assertEqual(state["faults"][0]["kind"], "illegal")

    def test_invalid_view_rejected_before_ai_or_new_game_replacement(self):
        old = self.app.game
        for view in ("AI", None, [], "scoreboard"):
            with self.subTest(view=view):
                with self.assertRaises(server.APIError):
                    self.submit(view=view)
                with self.assertRaises(server.APIError):
                    self.app.new(dict(view=view))
                with self.assertRaises(server.APIError):
                    self.app.state(view)
        self.assertIs(self.app.game, old)
        self.assertEqual(old.g.turn, 1)
        self.assertTrue(all(not w.calls for w in old.workers.values()))

    def test_failed_replacement_preserves_old_game_and_workers(self):
        old, snapshot = self.app.game, self.app.state()
        with mock.patch.object(server, "HumanGame", side_effect=OSError("cannot create replacement")):
            with self.assertRaises(OSError):
                self.app.new(dict(seed=191))
        self.assertIs(self.app.game, old)
        self.assertEqual(self.app.state(), snapshot)
        self.assertTrue(all(not w.closed for w in old.workers.values()))

    def test_closed_game_rejects_action_before_mutation(self):
        old = copy.deepcopy(self.app.game.g.snapshot())
        self.app.close()
        with self.assertRaises(server.APIError) as caught:
            self.submit()
        self.assertEqual(caught.exception.status, 409)
        self.assertEqual(self.app.game.g.snapshot(), old)

    def test_freeze_counter_thaw_notice_and_shield_cooldown_are_separate(self):
        state = self.submit(action="SHIELD")
        self.assertEqual(state["human_frozen_turns"], 2)
        self.assertEqual(state["legal_actions"], ["STAY"])
        state = self.submit()
        self.assertEqual(state["human_frozen_turns"], 1)
        state = self.submit()
        self.assertEqual(state["human_frozen_turns"], 0)
        self.assertEqual(state["human_cooldown"], 2)
        self.assertIn("EAST", state["legal_actions"])
        self.assertTrue(state["last_turn"]["human_thawed"])
        strict = self.app.state("ai")
        self.assertEqual(set(strict), {"game_id", "turn", "over", "observation"})
        self.assertNotIn("human_frozen_turns", strict["observation"])

    def test_corrupt_history_is_rejected_and_skipped_without_breaking_list(self):
        healthy = self.app.game.id
        damaged = "f"*32
        path = history.path_for(self.app.history_dir, damaged)
        corruptions = ["null\n", "[]\n", json.dumps(dict(type="start", format=history.FORMAT, game_id="wrong"))+"\n"]
        for body in corruptions:
            with self.subTest(body=body):
                path.write_text(body, encoding="utf-8")
                with self.assertRaises(server.APIError) as caught:
                    self.app.history_export(damaged)
                self.assertEqual(caught.exception.status, 400)
                self.assertEqual([r["game_id"] for r in history.list_histories(self.app.history_dir)], [healthy])


if __name__ == "__main__":
    unittest.main()
