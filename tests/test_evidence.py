"""Independent integrity and replay checks on the actual comparison evidence."""
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path
import unittest
import zipfile

from simulator import server

ROOT = Path(__file__).resolve().parents[1]


class EvidenceTests(unittest.TestCase):
    def test_archived_sources_match_every_registered_hash_and_the_release(self):
        manifest = json.loads((ROOT/"validation/source_archive_manifest.json").read_text())
        archive = ROOT/manifest["archive"]
        self.assertEqual(hashlib.sha256(archive.read_bytes()).hexdigest(), manifest["sha256"])
        with zipfile.ZipFile(archive) as z:
            for entry in manifest["files"]:
                self.assertEqual(hashlib.sha256(z.read(entry["path"])).hexdigest(), entry["sha256"])
            for stage in ("screen", "selection", "final"):
                spec = json.loads((ROOT/("validation/%s_spec.json" % stage)).read_text())
                for source in spec["sources"]:
                    self.assertEqual(hashlib.sha256(z.read(source["path"])).hexdigest(), source["sha256"])
            previous=json.loads((ROOT/"validation/previous_release_manifest.json").read_text())
            self.assertEqual(hashlib.sha256(z.read("consolidation_candidates/presence_guarded.py")).hexdigest(),previous["bot_sha256"])

    def test_registered_results_recompute_and_sampled_games_replay(self):
        referee = server.bootstrap()[1]
        totals, boards = 0, []
        expected = {"screen": (69, 828), "selection": (15, 1920), "final": (6, 2304)}
        for stage, (policies, count) in expected.items():
            path = ROOT/("validation/%s_results.json.gz" % stage)
            with gzip.open(path, "rt", encoding="utf8") as handle:
                result = json.load(handle)
            spec = result["registration"]["spec"]
            self.assertEqual(spec, json.loads((ROOT/("validation/%s_spec.json" % stage)).read_text()))
            self.assertFalse(result["registration"]["rules"]["catch_requires_stay"])
            self.assertEqual(hashlib.sha256((ROOT/"validation/benchmark_versions"/(result["registration"]["benchmark_sha256"]+".py")).read_bytes()).hexdigest(),
                             result["registration"]["benchmark_sha256"])
            self.assertEqual(len(result["games"]), count)
            self.assertEqual(len(result["summary"]), policies)
            totals += count
            fixtures = {row["id"]: row for row in spec["fixtures"]}
            boards.append({tuple(f["base"]) for f in fixtures.values()})
            for candidate, summary in result["summary"].items():
                rows = [row for row in result["games"] if row["candidate"] == candidate]
                self.assertEqual(len(rows), len(fixtures))
                self.assertEqual({r["fixture"] for r in rows}, set(fixtures))
                mean = sum(r["focal_pw"] for r in rows)/len(rows)
                self.assertAlmostEqual(mean, summary["mean_pw"])
                self.assertAlmostEqual(sum(r["focal_score"] for r in rows)/len(rows), summary["mean_score"])
                for row in rows:
                    self.assertEqual(row["focal_pw"], 3*referee.pairwise(row["scores"])[row["focal_seat"]])
                    self.assertEqual(len(row["actions"]), 80)
                    self.assertEqual([t["calls"] for t in row["timing"]], [80]*4)
                # Reconstruct both ends of every candidate's fixture list independently.
                for row in (rows[0], rows[-1]):
                    fixture = fixtures[row["fixture"]]
                    game = referee.Referee(fixture["base"], rules=result["registration"]["rules"],
                                           start_token=fixture["token"])
                    for actions in row["actions"]:
                        game.step(actions)
                    self.assertTrue(game.over())
                    self.assertEqual(game.score, row["scores"])
            if stage in ("selection", "final"):
                self.assertFalse([f for row in result["games"] for f in row["faults"]])
            if stage == "final":
                self.assertEqual(next(iter(result["summary"])), "presence_guarded")
                self.assertEqual(result["summary"]["presence_guarded"]["mean_pw"], 1.875)
                crossings = Counter((f["map_group"], f["field"]) for f in fixtures.values())
                self.assertEqual(len(crossings), 8*3)
                self.assertEqual(set(crossings.values()), {16})
                for key in crossings:
                    self.assertEqual({(f["seat"], f["token"]) for f in fixtures.values()
                                      if (f["map_group"], f["field"]) == key},
                                     {(s, t) for s in range(4) for t in range(1, 5)})
        self.assertEqual(totals, 5052)
        self.assertFalse(boards[0] & boards[1] or boards[0] & boards[2] or boards[1] & boards[2])


if __name__ == "__main__":
    unittest.main()
