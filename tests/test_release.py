"""The actual standalone release and recorded human-play pipeline."""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import time
import unittest

from simulator import server
from tests import reference_engine as engine

ROOT = Path(__file__).resolve().parents[1]


def load(path=ROOT / "bot.py"):
    spec = importlib.util.spec_from_file_location("release_contract", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def signature(view):
    return (view.bot_id, view.is_priority_token, tuple(view.legal_actions),
            tuple((c.occupant, c.owner, c.is_upgraded, c.is_home, c.is_frozen, c.base_points)
                  for row in view.board for c in row))


class ReleaseTests(unittest.TestCase):
    def test_release_and_testers_match_the_saved_fingerprints(self):
        manifest = json.loads((ROOT / "release_manifest.json").read_text(encoding="utf8"))
        self.assertEqual(hashlib.sha256((ROOT/"bot.py").read_bytes()).hexdigest(), manifest["bot_sha256"])
        self.assertTrue(manifest["rules"]["catch_requires_stay"])
        self.assertGreaterEqual(len(manifest["tester_bots"]), 3)
        for tester in manifest["tester_bots"]:
            self.assertEqual(hashlib.sha256((ROOT/tester["path"]).read_bytes()).hexdigest(), tester["sha256"])
        catalog = server.Catalog()
        self.assertFalse(catalog.warnings)
        self.assertEqual(catalog.recommended_id, manifest["bot_sha256"][:20])

    def test_public_selfplay_has_exact_tracking_no_fallback_and_no_late_actions(self):
        worst, callbacks = 0.0, 0
        for case in range(4):
            game = engine.Game(base=engine.make_map(seed=290011+case), start_token=case+1,
                               rules={"catch_requires_stay": True})
            players = [load() for _ in range(4)]
            while not game.over():
                actions = []
                for seat, public in enumerate(game.views()):
                    before = signature(public)
                    # View exposes only the official four fields; no Game is supplied.
                    self.assertEqual(set(public.__slots__), {"board", "bot_id", "is_priority_token", "legal_actions"})
                    start = time.perf_counter()
                    action = players[seat].act(public)
                    elapsed = (time.perf_counter()-start)*1000
                    worst = max(worst, elapsed)
                    callbacks += 1
                    self.assertLess(elapsed, 2000 if game.turn == 1 else 200)
                    self.assertIn(action, public.legal_actions)
                    self.assertEqual(signature(public), before)
                    memory = players[seat]._M
                    self.assertEqual(memory.errors, 0)
                    self.assertEqual(memory.scale, 1.0)
                    if action == "SHIELD":
                        self.assertEqual(game.cd[seat], 0)
                    # Reconstructed from public boards only; the referee is consulted to grade it.
                    self.assertEqual(memory.turn, game.turn)
                    self.assertEqual(memory.scores[1:], game.score)
                    self.assertEqual(memory.prog[seat+1], game.prog[seat])
                    self.assertEqual(memory.cd[seat+1], game.cd[seat])
                    if memory.token is not None:
                        self.assertEqual(memory.token_holder(game.turn), game.token)
                    actions.append(action)
                game.step(actions)
        self.assertEqual(callbacks, 1280)
        print("Release public self-play: 1,280 callbacks; worst %.3f ms" % worst)

    def test_all_home_opening_retains_clock_and_completion_income(self):
        player = load()
        game = engine.Game(base=[3]*64, rules={"catch_requires_stay": True})
        for turn in range(1, 9):
            public = game.views()[0]
            public.legal_actions = ["STAY"]
            self.assertEqual(player.act(public), "STAY")
            memory = player._M
            self.assertEqual(memory.turn, turn)
            self.assertEqual(memory.scores[1:], game.score)
            self.assertEqual(memory.prog[1], game.prog[0])
            game.step(["STAY"]*4)

    def test_real_workers_complete_and_record_eighty_turns_without_private_view_fields(self):
        directory = server.HERE / ".test-tmp"
        directory.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=directory) as temp:
            app = server.App(history_dir=Path(temp))
            try:
                state = app.new(dict(seed=20261108, seat=1, token=2, view="ai"))
                game_id = state["game_id"]
                for turn in range(1, 81):
                    self.assertEqual(state["turn"], turn)
                    self.assertEqual(set(state), {"game_id", "turn", "over", "observation"})
                    self.assertEqual(set(state["observation"]), {"board", "bot_id", "is_priority_token", "legal_actions"})
                    state = app.action(dict(game_id=game_id, turn=turn, action="STAY", view="ai"))
                self.assertTrue(state["over"])
                self.assertFalse(app.game.faults)
                transcript = app.history_export(game_id)
                self.assertEqual(len(transcript["turns"]), 80)
                self.assertTrue(transcript["metadata"]["rules"]["catch_requires_stay"])
                self.assertEqual(transcript["metadata"]["bot"]["sha256"],
                                 hashlib.sha256((ROOT/"bot.py").read_bytes()).hexdigest())
                g = app.referee.Referee(transcript["metadata"]["base"],
                                        rules=transcript["metadata"]["rules"],
                                        start_token=transcript["metadata"]["start_token"])
                for row in transcript["turns"]:
                    # History is observer evidence, not an input into any worker.
                    self.assertEqual(g.step(row["used"]), row["resolved"])
                    self.assertEqual(g.snapshot(), row["after"])
            finally:
                app.close()


if __name__ == "__main__":
    unittest.main()
