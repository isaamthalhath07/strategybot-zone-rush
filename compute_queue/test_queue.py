"""Tiny local protocol tests; no primary campaign credit or external traffic."""
import copy
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from compute_queue import queue as q


def job(identity="tiny"):
    from search_coach.belief import PublicObservation
    from tests.reference_engine import Game
    return dict(schema=1, kind="public_history_gpu_coach", job_id=identity,
                initial_observation=PublicObservation.from_view(Game(base=[2] * 64).views()[0]).serializable(),
                transitions=[], search=dict(seed=17, horizon=1, plans_per_root=1, rollouts_per_plan=1))


class QueueTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from search_coach.gpu_batch import run_batch
        cls.result = run_batch([job()], device="cpu", max_trajectories=q.CHUNK, verify_all=True)

    def setUp(self):
        cache = q.ROOT / ".cache"
        cache.mkdir(exist_ok=True)
        self.directory = tempfile.TemporaryDirectory(dir=cache, prefix="queue-test-")
        self.addCleanup(self.directory.cleanup)
        self.now = [1000.0]
        self.store = q.Store(Path(self.directory.name) / "queue.sqlite", lease_seconds=3, clock=lambda: self.now[0])
        self.a, self.ta = self.store.add_worker()
        self.b, self.tb = self.store.add_worker()
        self.task = self.store.enqueue([job()])

    def claim(self):
        assigned = self.store.claim(self.a)
        return {key: assigned[key] for key in ("task", "lease")}

    def test_disjoint_concurrent_claim_and_inner_job_identity(self):
        with ThreadPoolExecutor(max_workers=2) as pool:
            claims = list(pool.map(self.store.claim, [self.a, self.b]))
        self.assertEqual(sum(claim["task"] is not None for claim in claims), 1)
        self.assertEqual(self.store.enqueue([job()]), self.task)
        different = job()
        different["search"]["seed"] += 1
        with self.assertRaises(q.sqlite3.IntegrityError):
            self.store.enqueue([different])
        self.assertEqual(sum(self.store.counts()["tasks"].values()), 1)

    def test_heartbeat_expiry_reassignment_and_stale_rejection(self):
        old = self.claim()
        self.now[0] += 2
        self.store.heartbeat(self.a, **old)
        self.now[0] += 2
        self.assertEqual(self.store.claim(self.b), {"task": None})
        self.now[0] += 2
        current = self.store.claim(self.b)
        self.assertEqual(current["task"], self.task)
        self.assertNotEqual(old["lease"], current["lease"])
        with self.assertRaises(q.Conflict):
            self.store.submit(self.a, **old, result=self.result)
        with self.assertRaises(q.Conflict):
            self.store.status(self.a, current["task"], current["lease"])

    def test_lost_claim_response_retry_reuses_and_renews_own_live_lease(self):
        first = self.store.claim(self.a)
        self.store.enqueue([job("second")])
        self.now[0] += 2
        retry = self.store.claim(self.a)
        self.assertEqual(retry, first)
        self.now[0] += 2
        self.assertEqual(self.store.status(self.a, first["task"], first["lease"])["state"], "leased")
        other = self.store.claim(self.b)
        self.assertNotEqual(other["task"], first["task"])
        with self.store.connect() as db:
            self.assertEqual([row[0] for row in db.execute("SELECT attempts FROM jobs")], [1, 1])

    def test_worker_heartbeat_covers_prefix_validation(self):
        server = q.make_server(self.store, 0)
        serving = threading.Thread(target=server.serve_forever, daemon=True)
        serving.start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        config = dict(schema=1, url="http://127.0.0.1:" + str(server.server_port),
                      worker=self.a, token=self.ta, source_pins=self.store.source_pins)
        observed = threading.Event()
        original = self.store.heartbeat
        def heartbeat(*args, **kwargs):
            observed.set()
            return original(*args, **kwargs)
        def slow_validation(jobs):
            self.assertTrue(observed.wait(5), "Heartbeat did not start during validation")
            raise ValueError("Stop this test before GPU work")
        with patch.object(self.store, "heartbeat", side_effect=heartbeat), patch.object(q, "validate_jobs", side_effect=slow_validation):
            with self.assertRaisesRegex(ValueError, "Stop this test"):
                q.work(config, device="cpu", max_jobs=1)

    def test_async_semantic_idempotence_verification_and_restart(self):
        assignment = self.claim()
        self.assertEqual(self.store.submit(self.a, **assignment, result=self.result)["state"], "verifying")
        self.now[0] += 10000  # Verification pending must outlive a worker lease.
        self.assertEqual(self.store.claim(self.b), {"task": None})
        duplicate = copy.deepcopy(self.result)
        duplicate["timing_seconds"]["total_end_to_end"] += 10
        duplicate["device"] = "cuda"
        self.assertTrue(self.store.submit(self.a, **assignment, result=duplicate)["duplicate"])
        restarted = q.Store(self.store.path, clock=lambda: self.now[0])
        self.assertTrue(restarted.verify_one())
        self.assertEqual(restarted.status(self.a, **assignment)["state"], "accepted")
        self.assertTrue(restarted.submit(self.a, **assignment, result=duplicate)["duplicate"])
        self.assertEqual(restarted.counts()["tasks"], {"accepted": 1})
        self.assertEqual(restarted.counts()["primary_campaign_games"], 0)
        duplicate["trace_sha256"] = "0" * 64
        with self.assertRaises(q.Conflict):
            restarted.submit(self.a, **assignment, result=duplicate)

    def test_owner_recomputes_and_quarantines_corruption(self):
        assignment = self.claim()
        for name in ("command", "module", "path"):
            with self.assertRaises(ValueError):
                self.store.submit(self.a, **assignment, result=dict(self.result, **{name: "unused"}))
        bad = copy.deepcopy(self.result)
        bad["jobs"][0]["root_estimates"][0]["best_common_plan"]["value_numerator_sum"] += 1
        self.store.submit(self.a, **assignment, result=bad)
        self.assertTrue(self.store.verify_one())
        self.assertEqual(self.store.status(self.a, **assignment)["state"], "quarantined")
        self.assertEqual(self.store.counts()["primary_campaign_games"], 0)

    def test_source_changes_and_strict_public_boundary(self):
        root = Path(self.directory.name) / "package"
        for name in q.SOURCE_PATHS:
            destination = root / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(q.ROOT / name, destination)
        with patch.object(q, "ROOT", root):
            q.check_pins(self.store.source_pins)
            (root / "search_coach/gpu_batch.py").write_bytes(b"changed")
            with self.assertRaises(ValueError):
                self.store.claim(self.a)
        for extra in ({"opponent_seed": 1}, {"command": "ignored"}, {"module": "os"}):
            with self.assertRaises(ValueError):
                q.validate_jobs([dict(job(), **extra)])
        for body in (b'{"a":1,"a":2}', b'{"a":NaN}', b'{"a":1e999}', b" " * (q.MAX_BYTES + 1)):
            with self.assertRaises(ValueError):
                q.decode(body)
        for url in ("http://192.168.1.2:9001", "https://user:password@example.com", "https://example.com/?token=x"):
            with self.assertRaises(ValueError):
                q.endpoint(url)

    def test_http_auth_scope_and_invalid_json(self):
        server = q.make_server(self.store, 0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        base = "http://127.0.0.1:" + str(server.server_port)
        config = dict(url=base, token=self.ta)
        with self.assertRaises(HTTPError) as error:
            q.request(dict(config, token="invalid"), "/v1/claim", {})
        self.assertEqual(error.exception.code, 401)
        assignment = q.request(config, "/v1/claim", {})
        identity = {key: assignment[key] for key in ("task", "lease")}
        for malformed in ({"task": {}, "lease": identity["lease"]}, dict(identity, lease="x")):
            with self.assertRaises(HTTPError) as error:
                q.request(config, "/v1/status", malformed)
            self.assertEqual(error.exception.code, 400)
        with self.assertRaises(HTTPError) as error:
            q.request(dict(config, token=self.tb), "/v1/status", identity)
        self.assertEqual(error.exception.code, 409)
        req = Request(base + "/v1/claim", data=b'{"a":1,"a":2}', headers={
            "Authorization": "Bearer " + self.ta, "Content-Type": "application/json"})
        with self.assertRaises(HTTPError) as error:
            urlopen(req, timeout=5)
        self.assertEqual(error.exception.code, 400)


class LocalEndToEnd(unittest.TestCase):
    def test_two_persistent_processes_cuda_and_cpu(self):
        import torch
        self.assertTrue(torch.cuda.is_available(), "Run this integration test in the verified CUDA environment")
        cache = q.ROOT / ".cache/compute_queue"
        cache.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=cache, prefix="e2e-") as directory:
            directory = Path(directory)
            store = q.Store(directory / "queue.sqlite", lease_seconds=30)
            for index in range(4):
                store.enqueue([job("local-public-" + str(index))])
            server, stop = q.make_server(store, 0), threading.Event()
            serving = threading.Thread(target=server.serve_forever, daemon=True)
            verifying = threading.Thread(target=q.verifier_loop, args=(store, stop), daemon=True)
            serving.start()
            verifying.start()
            processes = []
            try:
                for device in ("cpu", "cuda"):
                    identity, token = store.add_worker()
                    config = directory / (device + ".json")
                    config.write_bytes(q.canonical(dict(schema=1, url="http://127.0.0.1:" + str(server.server_port),
                        worker=identity, token=token, source_pins=store.source_pins)))
                    process = subprocess.Popen([sys.executable, "-m", "compute_queue.queue", "work", "--config", str(config),
                        "--device", device, "--max-jobs", "2"], cwd=q.ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    processes.append(process)
                for process in processes:
                    stdout, stderr = process.communicate(timeout=120)
                    self.assertEqual(process.returncode, 0, (stdout + stderr).decode(errors="replace"))
                self.assertEqual(store.counts()["tasks"], {"accepted": 4})
                with store.connect() as db:
                    rows = db.execute("SELECT owner,attempts,result FROM jobs").fetchall()
                self.assertEqual(len(set(row["owner"] for row in rows)), 2)
                self.assertEqual([row["attempts"] for row in rows], [1] * 4)
                results = [json.loads(row["result"]) for row in rows]
                evidence = dict(schema=1, local_only=True, accepted_tasks=4, persistent_worker_processes=2,
                    jobs_per_process=2, devices=sorted(set(result["device"] for result in results)),
                    synthetic_game_turns=sum(result["synthetic_game_turns"] for result in results),
                    independent_owner_cpu_verification=True, primary_campaign_games=0, full_bmcts_games=0,
                    source_pins=store.source_pins, public_https_path_tested=False)
                (cache / "local_e2e.json").write_bytes(q.canonical(evidence) + b"\n")
            finally:
                for process in processes:
                    if process.poll() is None:
                        process.kill()
                        process.wait()
                server.shutdown()
                server.server_close()
                stop.set()
                serving.join()
                verifying.join(timeout=20)


if __name__ == "__main__":
    unittest.main()
