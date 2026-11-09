"""Infrastructure invariants; these tests never run or count a campaign game."""

from collections import Counter
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from . import doctor, offline


PINS = {"bot.py": "a" * 64, "worker.py": "b" * 64}


def plan(**kwargs):
    return offline.make_plan(PINS, "bot.py", "worker.py", **kwargs)


def result_for(manifest, task):
    games = []
    for episode in range(task["episode_start"], task["episode_end"]):
        seat, _ = offline.seating(task["map_index"], episode)
        games.append({"episode": episode, "completed": True, "turns": 80,
                      "transcript_sha256": "c" * 64, "bmcts_audited": True,
                      "planner_seed": 1,
                      "opponent_ids": offline.opponents(manifest["campaign_id"], task["map_index"], episode, seat)})
    return {"schema": offline.RESULT_SCHEMA, "campaign_id": manifest["campaign_id"],
            "manifest_sha256": manifest["manifest_sha256"], "task_id": task["id"],
            "policy_sha256": PINS["bot.py"], "evaluator_sha256": PINS["worker.py"],
            "games": games}


class AllocationTests(unittest.TestCase):
    def test_full_two_million_schedule_has_no_missing_or_overlapping_game(self):
        manifest = plan()
        allocations = offline.partition(manifest, 6)
        self.assertEqual(manifest["total_games"], 2000000)
        self.assertEqual(len(manifest["tasks"]), 80000)
        allocated = [identity for worker in allocations for identity in worker["tasks"]]
        self.assertEqual(len(set(allocated)), 80000)
        self.assertEqual(set(allocated), {task["id"] for task in manifest["tasks"]})
        self.assertEqual(sum(worker["scheduled_games"] for worker in allocations), 2000000)
        per_map = {}
        for task in manifest["tasks"]:
            index = task["map_index"]
            expected = per_map.get(index, 0)
            self.assertEqual(task["episode_start"], expected)
            self.assertEqual(task["episode_end"] - task["episode_start"], task["games"])
            per_map[index] = task["episode_end"]
        self.assertEqual(set(per_map.values()), {200})
        self.assertEqual(len(per_map), 10000)

    def test_seats_and_tokens_balanced_per_map_and_over_map_rotations(self):
        all_pairs = Counter()
        for index in range(4):
            pairs = Counter(offline.seating(index, episode) for episode in range(200))
            self.assertEqual(set(pairs.values()), {12, 13})
            seats = Counter()
            tokens = Counter()
            for (seat, token), count in pairs.items():
                seats[seat] += count
                tokens[token] += count
            self.assertEqual(set(seats.values()), {50})
            self.assertEqual(set(tokens.values()), {50})
            all_pairs.update(pairs)
        self.assertEqual(set(all_pairs.values()), {50})

    def test_task_ids_stable_and_bound_to_all_source_pins(self):
        first = plan(maps=2, games_per_map=8, episodes_per_task=3)
        second = offline.make_plan(dict(reversed(list(PINS.items()))), "bot.py", "worker.py",
                                   maps=2, games_per_map=8, episodes_per_task=3)
        self.assertEqual(first, second)
        changed = offline.make_plan({**PINS, "worker.py": "d" * 64}, "bot.py", "worker.py",
                                    maps=2, games_per_map=8, episodes_per_task=3)
        self.assertTrue({task["id"] for task in first["tasks"]}.isdisjoint(
            {task["id"] for task in changed["tasks"]}))
        # Each map's tail is allocated once, even when task size does not divide its games.
        self.assertEqual([t["games"] for t in first["tasks"]], [3, 3, 2, 3, 3, 2])

    def test_source_boundary_and_schedule_tampering(self):
        for unsafe in ("../bot.py", "/bot.py", "C:/bot.py", "a/../b.py", "a\\b.py", "./bot.py"):
            with self.subTest(path=unsafe), self.assertRaises(ValueError):
                offline.file_hashes(".", [unsafe])
        with tempfile.TemporaryDirectory() as directory:
            Path(directory, "bot.py").write_bytes(b"public bot")
            self.assertEqual(offline.file_hashes(directory, ["bot.py"]),
                             {"bot.py": hashlib.sha256(b"public bot").hexdigest()})
        manifest = plan(maps=1, games_per_map=8, episodes_per_task=3)
        manifest["tasks"][1]["episode_start"] = 2
        with self.assertRaises(ValueError):
            offline.validate_plan(manifest)

    def test_opponent_instance_ids_never_reused_in_small_campaign(self):
        identities = []
        for index in range(8):
            for episode in range(200):
                seat, _ = offline.seating(index, episode)
                identities.extend(offline.opponents("e" * 64, index, episode, seat))
        self.assertEqual(len(identities), 4800)
        self.assertEqual(len(set(identities)), len(identities))


class ResultTests(unittest.TestCase):
    def setUp(self):
        self.manifest = plan(maps=1, games_per_map=8, episodes_per_task=3)
        self.result = result_for(self.manifest, self.manifest["tasks"][0])

    def test_valid_claims_cannot_credit_verified_games_or_bmcts(self):
        summary = offline.inventory(self.manifest, [self.result])
        self.assertEqual(summary["claimed_completed_games"], 3)
        self.assertEqual(summary["claimed_bmcts_audits"], 3)
        self.assertEqual(summary["verified_games"], 0)
        self.assertEqual(summary["verified_bmcts_audits"], 0)
        self.assertEqual(summary["missing_tasks"], 2)

    def test_duplicate_and_unknown_results_rejected(self):
        with self.assertRaises(ValueError):
            offline.inventory(self.manifest, [self.result, self.result])
        unknown = copy.deepcopy(self.result)
        unknown["task_id"] = "f" * 64
        with self.assertRaises(ValueError):
            offline.inventory(self.manifest, [unknown])

    def test_wrong_campaign_or_code_or_missing_episodes_rejected(self):
        for key in ("campaign_id", "manifest_sha256", "policy_sha256", "evaluator_sha256"):
            changed = copy.deepcopy(self.result)
            changed[key] = "f" * 64
            with self.subTest(field=key), self.assertRaises(ValueError):
                offline.inventory(self.manifest, [changed])
        changed = copy.deepcopy(self.result)
        changed["games"].pop()
        with self.assertRaises(ValueError):
            offline.inventory(self.manifest, [changed])

    def test_malformed_counters_and_reused_opponents_rejected(self):
        for field, value in (("episode", True), ("turns", True), ("turns", 81),
                             ("turns", 0), ("completed", 1), ("planner_seed", -1),
                             ("bmcts_audited", 1), ("transcript_sha256", "bad"),
                             ("opponent_ids", ["a" * 64] * 3)):
            changed = copy.deepcopy(self.result)
            changed["games"][0][field] = value
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                offline.inventory(self.manifest, [changed])

    def test_nonstandard_and_ambiguous_json_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory, "bad.json")
            for text in ('{"id":1,"id":2}', '{"score":NaN}', '{"score":Infinity}'):
                path.write_text(text, encoding="utf-8")
                with self.subTest(text=text), self.assertRaises(ValueError):
                    offline.load_json(path)


class DoctorTests(unittest.TestCase):
    def test_cuda_detection_without_working_kernel_keeps_cpu_recommendation(self):
        response = {"exit_code": 0, "stdout": json.dumps({"installed": True, "cuda_available": True,
                    "devices": [{"name": "test", "index": 0, "kernel_ok": False}]}), "stderr": ""}
        with mock.patch.object(doctor, "command", return_value=response):
            report = doctor.collect(probe_torch=True)
        self.assertEqual(report["suggested_backend"], "cpu")
        self.assertFalse(report["ready_for_games"])

    def test_kernel_success_does_not_certify_game_execution(self):
        response = {"exit_code": 0, "stdout": json.dumps({"installed": True,
                    "devices": [{"name": "test", "index": 0, "kernel_ok": True}]}), "stderr": ""}
        with mock.patch.object(doctor, "command", return_value=response):
            report = doctor.collect(probe_torch=True)
        self.assertEqual(report["suggested_backend"], "cuda")
        self.assertFalse(report["ready_for_games"])

    def test_atomic_report_and_home_path_redaction(self):
        response = {"error": "C:\\Users\\Alice\\env\\kernel.dll /home/bob/env /Users/carol/env"}
        with mock.patch.object(doctor, "command", return_value=response):
            report = doctor.collect()
        encoded = json.dumps(report)
        for name in ("Alice", "bob", "carol"):
            self.assertNotIn(name, encoded)
        self.assertNotIn("executable", report["python"])
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory, "hardware.json")
            doctor.atomic_json(path, report)
            self.assertEqual(json.loads(path.read_text(encoding="utf-8")), report)
            self.assertEqual([p.name for p in Path(directory).iterdir()], ["hardware.json"])


if __name__ == "__main__":
    unittest.main()
