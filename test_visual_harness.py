"""Validate saved replay evidence against the engine, not the renderer."""
import json
from pathlib import Path
import unittest

import engine
import visual_harness


class ReplayEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = json.loads((Path(__file__).parent / "visual" / "replays.json").read_text(encoding="utf-8"))

    def test_recorded_boards_and_scores_follow_recorded_actions(self):
        """Catch fabricated, dropped or shifted animation frames and actions."""
        for replay in self.data["games"]:
            with self.subTest(replay=replay["title"]):
                g = engine.Game(base=replay["base"], rules=replay["rules"],
                                start_token=replay["start_token"])
                self.assertEqual(len(replay["frames"]), 81)
                for turn, frame in enumerate(replay["frames"]):
                    transition = frame["transition"]
                    if turn:
                        for seat, a in enumerate(transition["accepted"]):
                            self.assertIn(a, g.legal(seat))
                        self.assertEqual(g.step(transition["accepted"]), transition["effective"])
                    expected = visual_harness.snapshot(g, turn, transition)
                    self.assertEqual(frame, expected)
                self.assertEqual(replay["scores"], g.score)
                self.assertEqual(replay["places"], g.places())

    def test_provenance_matches_current_sources(self):
        root = Path(__file__).parent
        self.assertEqual(self.data["bot_sha256"], visual_harness.sha(root / self.data["bot_file"]))
        self.assertEqual(self.data["engine_sha256"], visual_harness.sha(root / "engine.py"))
        self.assertEqual(self.data["independent_opponent_sha256"],
                         visual_harness.sha(root / "audit" / "independent_bot.py"))

    def test_viewer_contains_exact_saved_games(self):
        html = (Path(__file__).parent / "visual" / "index.html").read_text(encoding="utf-8")
        payload = html.split("const REPLAYS = ", 1)[1].split(";\n(() =>", 1)[0]
        self.assertEqual(json.loads(payload), self.data)


if __name__ == "__main__":
    unittest.main()
