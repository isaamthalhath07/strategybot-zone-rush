"""Independent queue boundary/retry checks. Never credits primary games."""
import copy
from pathlib import Path
import sys
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from compute_queue import queue as q


def public_job(identity="independent-review"):
    from search_coach.belief import PublicObservation
    from tests.reference_engine import Game
    return dict(schema=1, kind="public_history_gpu_coach", job_id=identity,
                initial_observation=PublicObservation.from_view(Game(base=[2]*64).views()[0]).serializable(),
                transitions=[], search=dict(seed=19, horizon=1, plans_per_root=1, rollouts_per_plan=1))


class IndependentQueueReview(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from search_coach.gpu_batch import run_batch
        cls.real_result = run_batch([public_job()], device="cpu", max_trajectories=q.CHUNK, verify_all=True)

    def setUp(self):
        cache = (q.ROOT/".cache").resolve()
        self.temp = tempfile.TemporaryDirectory(prefix="queue-independent-review-", dir=cache)
        self.directory = Path(self.temp.name).resolve()
        self.assertTrue(self.directory.is_relative_to(cache))
        self.addCleanup(self.temp.cleanup)
        self.now = [1000.0]
        self.store = q.Store(self.directory/"review.sqlite", lease_seconds=3, clock=lambda: self.now[0])
        self.a, self.ta = self.store.add_worker()
        self.b, self.tb = self.store.add_worker()
        self.task = self.store.enqueue([public_job()])

    def test_retried_claim_reuses_one_lease_and_preserves_other_worker_work(self):
        second = self.store.enqueue([public_job("second")])
        first = self.store.claim(self.a)
        self.now[0] += 1
        repeated = self.store.claim(self.a)
        self.assertEqual(first["task"], repeated["task"])
        self.assertEqual(first["lease"], repeated["lease"])
        self.assertEqual(first["jobs"], repeated["jobs"])
        other = self.store.claim(self.b)
        self.assertEqual(other["task"], second)
        with self.store.connect() as db:
            rows = db.execute("SELECT owner,attempts FROM jobs").fetchall()
        self.assertEqual({r["owner"] for r in rows}, {self.a, self.b})
        self.assertEqual([r["attempts"] for r in rows], [1, 1])
        self.assertEqual(self.store.counts()["primary_campaign_games"], 0)

    def test_worker_identity_and_expired_nonce_cannot_access_another_assignment(self):
        assignment = self.store.claim(self.a)
        identity = {key: assignment[key] for key in ("task", "lease")}
        for method in (self.store.status, self.store.heartbeat):
            with self.assertRaises(q.Conflict):
                method(self.b, **identity)
        self.now[0] += 4
        fresh = self.store.claim(self.b)
        self.assertEqual(fresh["task"], identity["task"])
        self.assertNotEqual(fresh["lease"], identity["lease"])
        with self.assertRaises(q.Conflict):
            self.store.submit(self.a, **identity, result=self.real_result)

    def test_malformed_assignment_types_fail_before_sqlite_binding(self):
        assignment = self.store.claim(self.a)
        variants = (({}, assignment["lease"]), (assignment["task"], []),
                    ("../database", assignment["lease"]), ("x"*64, "a"*48),
                    (assignment["task"], "G"*48))
        for task, lease in variants:
            with self.subTest(kind=(type(task).__name__, type(lease).__name__)), self.assertRaises(ValueError):
                self.store.status(self.a, task, lease)

    def test_public_jobs_reject_hidden_state_and_executable_fields(self):
        variants = []
        for key in ("opponent_seed", "cooldowns", "module", "command", "output_path"):
            item = public_job()
            item[key] = "../../outside"
            variants.append(item)
        item = public_job()
        item["initial_observation"]["private_progress"] = [1, 2, 0, 0]
        variants.append(item)
        item = public_job()
        item["search"]["horizon"] = 7
        variants.append(item)
        for item in variants:
            with self.assertRaises(ValueError):
                q.validate_jobs([item])

    def test_actual_owner_cpu_recomputation_quarantines_a_forged_value(self):
        assignment = self.store.claim(self.a)
        bad = copy.deepcopy(self.real_result)
        bad["jobs"][0]["root_estimates"][0]["best_common_plan"]["value_numerator_sum"] += 1
        identity = {key: assignment[key] for key in ("task", "lease")}
        self.store.submit(self.a, **identity, result=bad)
        from search_coach.gpu_batch import run_batch
        with patch("search_coach.gpu_batch.run_batch", wraps=run_batch) as called:
            self.assertTrue(self.store.verify_one())
        self.assertEqual(called.call_count, 1)
        self.assertEqual(called.call_args.kwargs["device"], "cpu")
        self.assertIs(called.call_args.kwargs["verify_all"], True)
        self.assertEqual(self.store.status(self.a, **identity)["state"], "quarantined")
        self.assertEqual(self.store.counts()["primary_campaign_games"], 0)
        self.assertEqual(self.store.counts()["full_bmcts_games"], 0)

    def test_unknown_result_fields_never_enter_verifying(self):
        assignment = self.store.claim(self.a)
        identity = {key: assignment[key] for key in ("task", "lease")}
        for key in ("command", "module", "file_path"):
            value = dict(self.real_result, **{key: "ignored executable text"})
            with self.assertRaises(ValueError):
                self.store.submit(self.a, **identity, result=value)
        self.assertEqual(self.store.status(self.a, **identity)["state"], "leased")

    def test_heartbeat_runs_during_slow_public_prefix_validation(self):
        assignment = self.store.claim(self.a)
        config = dict(schema=1, url="http://127.0.0.1:9001", worker=self.a,
                      token=self.ta, source_pins=self.store.source_pins)
        heartbeat = threading.Event()
        actual_validate = q.validate_jobs
        def slow_validate(jobs):
            self.assertTrue(heartbeat.wait(2), "Lease renewal started after prefix validation")
            actual_validate(jobs)
        def transport(_config, path, body):
            if path.endswith("claim"):
                return dict(assignment, lease_seconds=1)
            if path.endswith("heartbeat"):
                heartbeat.set()
                return {"state": "leased"}
            if path.endswith("result"):
                return {"state": "accepted"}
            raise AssertionError("Unexpected transport call")
        # This control-flow test uses no actual result acceptance or GPU claim.
        fake_gpu = SimpleNamespace(run_batch=lambda *args, **kwargs: {"test_only": True})
        with patch.dict(sys.modules, {"search_coach.gpu_batch": fake_gpu}), \
                patch.object(q, "request", side_effect=transport), \
                patch.object(q, "validate_jobs", side_effect=slow_validate):
            self.assertEqual(q.work(config, device="cpu", max_jobs=1), 1)
        self.assertTrue(heartbeat.is_set())
        self.assertEqual(self.store.counts()["tasks"], {"leased": 1})

    def test_http_auth_is_scoped_and_malformed_ids_return400(self):
        server = q.make_server(self.store, 0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        base = "http://127.0.0.1:"+str(server.server_port)
        assignment = q.request(dict(url=base, token=self.ta), "/v1/claim", {})
        identity = {key: assignment[key] for key in ("task", "lease")}
        for token, body, status in ((self.tb, identity, 409), ("invalid", identity, 401),
                                    (self.ta, dict(task={}, lease=assignment["lease"]), 400)):
            with self.assertRaises(HTTPError) as caught:
                q.request(dict(url=base, token=token), "/v1/status", body)
            self.assertEqual(caught.exception.code, status)
        for body in (b'{"task":1,"task":2}', b'{"x":NaN}'):
            request = Request(base+"/v1/claim", data=body,
                              headers={"Authorization": "Bearer "+self.ta,"Content-Type": "application/json"})
            with self.assertRaises(HTTPError) as caught:
                urlopen(request, timeout=5)
            self.assertEqual(caught.exception.code, 400)


if __name__ == "__main__":
    unittest.main()
