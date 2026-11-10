"""Separate current STAY-only evidence from historical presence-rule trials."""
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path
import unittest
import zipfile

from simulator import server

ROOT = Path(__file__).resolve().parents[1]


class OfficialEvidenceTests(unittest.TestCase):
    def test_all_registered_sources_and_current_export_are_hash_bound(self):
        bodies = {}
        for relative in ("validation/source_archive_manifest.json", "validation/official/source_archive_manifest.json"):
            manifest = json.loads((ROOT/relative).read_text())
            archive = ROOT/manifest["archive"]
            self.assertEqual(hashlib.sha256(archive.read_bytes()).hexdigest(), manifest["sha256"])
            with zipfile.ZipFile(archive) as z:
                for entry in manifest["files"]:
                    body = z.read(entry["path"])
                    self.assertEqual(hashlib.sha256(body).hexdigest(), entry["sha256"])
                    bodies[entry["path"]] = body
        for stage in ("screen", "selection", "final", "followup", "ultimate"):
            spec = json.loads((ROOT/("validation/official/%s_spec.json" % stage)).read_text())
            self.assertTrue(spec["rules"]["catch_requires_stay"])
            for source in spec["sources"]:
                self.assertEqual(hashlib.sha256(bodies[source["path"]]).hexdigest(), source["sha256"])
        release = json.loads((ROOT/"release_manifest.json").read_text())
        previous = release["tester_bots"][0]
        self.assertEqual(previous["path"], "tester_bots/guarded_transfer.py")
        self.assertEqual(bodies[previous["source"]["path"]], (ROOT/previous["path"]).read_bytes())
        self.assertTrue(release["rules"]["catch_requires_stay"])

    def test_concurrent_ultimate_control_uses_the_exact_followup_fixtures(self):
        referee = server.bootstrap()[1]
        with gzip.open(ROOT/"validation/official/followup_results.json.gz", "rt", encoding="utf8") as handle:
            followup = json.load(handle)
        with gzip.open(ROOT/"validation/official/ultimate_results.json.gz", "rt", encoding="utf8") as handle:
            control = json.load(handle)
        self.assertEqual(control["registration"]["spec"]["fixtures"], followup["registration"]["spec"]["fixtures"])
        self.assertEqual(control["registration"]["rules"], followup["registration"]["rules"])
        rows = control["games"]
        self.assertEqual(len(rows), 576)
        self.assertFalse([fault for row in rows for fault in row["faults"]])
        self.assertEqual(sum(t["calls"] for row in rows for t in row["timing"]), 184320)
        fixtures = {f["id"]: f for f in control["registration"]["spec"]["fixtures"]}
        self.assertEqual({row["fixture"] for row in rows}, set(fixtures))
        for row in (rows[0], rows[-1]):
            fixture = fixtures[row["fixture"]]
            game = referee.Referee(fixture["base"], rules=control["registration"]["rules"], start_token=fixture["token"])
            for actions in row["actions"]:
                game.step(actions)
            self.assertEqual(game.score, row["scores"])
        self.assertEqual((ROOT/"ultimate.py").read_bytes(), (ROOT/"tester_bots/ultimate.py").read_bytes())

    def test_true_results_are_complete_replayable_and_not_pooled_with_false(self):
        referee = server.bootstrap()[1]
        expected = {"screen": (70, 840), "selection": (12, 1536), "final": (6, 2304), "followup": (2, 1152)}
        boards, total, calls = [], 0, 0
        for stage, (policies, count) in expected.items():
            with gzip.open(ROOT/("validation/official/%s_results.json.gz" % stage), "rt", encoding="utf8") as handle:
                data = json.load(handle)
            registration, rows = data["registration"], data["games"]
            self.assertTrue(registration["rules"]["catch_requires_stay"])
            spec = registration["spec"]
            self.assertEqual(spec, json.loads((ROOT/("validation/official/%s_spec.json" % stage)).read_text()))
            tool = ROOT/"validation/benchmark_versions"/(registration["benchmark_sha256"]+".py")
            self.assertEqual(hashlib.sha256(tool.read_bytes()).hexdigest(), registration["benchmark_sha256"])
            self.assertEqual(len(rows), count)
            self.assertEqual(len(data["summary"]), policies)
            self.assertFalse([f for row in rows for f in row["faults"]])
            fixtures = {f["id"]: f for f in spec["fixtures"]}
            boards.append({tuple(f["base"]) for f in fixtures.values()})
            total += len(rows)
            for candidate, summary in data["summary"].items():
                games = [row for row in rows if row["candidate"] == candidate]
                self.assertEqual(len(games), len(fixtures))
                self.assertEqual({row["fixture"] for row in games}, set(fixtures))
                self.assertAlmostEqual(summary["mean_pw"], sum(row["focal_pw"] for row in games)/len(games))
                for row in games:
                    self.assertEqual(len(row["actions"]), 80)
                    self.assertEqual([t["calls"] for t in row["timing"]], [80]*4)
                    calls += sum(t["calls"] for t in row["timing"])
                    self.assertEqual(row["focal_pw"], 3*referee.pairwise(row["scores"])[row["focal_seat"]])
                for row in (games[0], games[-1]):
                    fixture = fixtures[row["fixture"]]
                    game = referee.Referee(fixture["base"], rules=registration["rules"], start_token=fixture["token"])
                    for actions in row["actions"]:
                        game.step(actions)
                    self.assertEqual(game.score, row["scores"])
            if stage != "screen":
                self.assertEqual(set(Counter((f["map_group"], f["field"]) for f in fixtures.values()).values()), {16})
            if stage == "followup":
                release = json.loads((ROOT/"release_manifest.json").read_text())
                self.assertEqual(next(iter(data["summary"])), release["previous_release"]["policy"])
                self.assertEqual(len(boards[-1]), 12)
        self.assertEqual(total, 5832)
        self.assertEqual(calls, 1866240)
        for i, board_set in enumerate(boards):
            for previous in boards[:i]:
                self.assertFalse(board_set & previous)

    def test_original_turn34_recording_is_exact_under_the_clarified_rule(self):
        data = json.loads((ROOT/"validation/official/turn34_verification.json").read_text())
        referee = server.bootstrap()[1]
        self.assertTrue(data["rules"]["catch_requires_stay"])
        game = referee.Referee(data["base"], rules=data["rules"], start_token=data["start_token"])
        for turn, actions in enumerate(data["actions"], 1):
            if turn == 34:
                self.assertEqual(game.snapshot(), data["turn34_before"])
            resolved = game.step(actions)
        self.assertEqual(len(data["actions"]), 34)
        self.assertEqual(resolved, data["turn34_resolution"])
        self.assertEqual(game.snapshot(), data["turn34_after"])
        self.assertEqual(game.pos[1], 26)
        self.assertEqual(game.frozen[:2], [2, 0])


if __name__ == "__main__":
    unittest.main()
