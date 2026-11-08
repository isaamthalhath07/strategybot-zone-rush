"""New-match post-movement shields, with explicit historical-rule replay."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

try:
    from . import history, server
    from .test_server import FakeProcess
except ImportError:
    import history
    import server
    from test_server import FakeProcess


class ShieldResolutionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.match, cls.referee, _sources, cls.provenance = server.bootstrap()

    def game(self, **overrides):
        return self.referee.Referee(self.referee.example_map(), rules=dict(server.NEW_GAME_RULES, **overrides))

    @staticmethod
    def moving_fixture(game):
        # Uploaded 44e7 T34's essential geometry: human at D2, Red at D4,
        # moving WEST to human-owned C4. Neither bot starts frozen.
        game.turn, game.token = 34, 2
        game.pos = [11, 27, 53, 43]
        game.owner[11] = game.owner[26] = game.owner[27] = 1

    def test_red_D4_to_C4_is_caught_and_human_does_not_backfire(self):
        game = self.game()
        self.moving_fixture(game)
        result = game.step(["SHIELD", "WEST", "NORTH", "STAY"])
        shield = next(e for e in result["events"] if e["type"] == "shield")
        self.assertEqual(game.pos[1], 26)
        self.assertEqual(shield["caught"], [2])
        self.assertFalse(shield["backfire"])
        self.assertEqual(game.frozen[:2], [0, 2])
        self.assertEqual(game.owner[26], 1)
        self.assertEqual(game.legal(1), ["STAY"])

    def test_arrival_from_outside_is_caught_after_movement(self):
        game = self.game()
        game.pos[1], game.owner[26] = 34, 1
        result = game.step(["SHIELD", "NORTH", "STAY", "STAY"])
        self.assertEqual(game.pos[1], 26)
        self.assertEqual(game.frozen[:2], [0, 2])
        self.assertEqual(next(e for e in result["events"] if e["type"] == "shield")["caught"], [2])

    def test_leaving_all_shield_owner_land_escapes(self):
        game = self.game()
        game.pos[1], game.owner[27] = 27, 1
        result = game.step(["SHIELD", "WEST", "STAY", "STAY"])
        self.assertEqual(game.pos[1], 26)
        self.assertEqual(game.frozen[:2], [2, 0])
        self.assertTrue(next(e for e in result["events"] if e["type"] == "shield")["backfire"])

    def test_already_frozen_rival_is_ineligible(self):
        game = self.game()
        game.pos[1], game.owner[26], game.frozen[1] = 26, 1, 1
        result = game.step(["SHIELD", "STAY", "STAY", "STAY"])
        self.assertEqual(game.frozen[:2], [2, 0])
        self.assertEqual(next(e for e in result["events"] if e["type"] == "shield")["caught"], [])

    def test_shield_protects_every_owned_cell_and_resets_both_raids(self):
        game = self.game()
        game.pos[1:3] = [10, 20]
        game.owner[10] = game.owner[20] = 1
        game.upg[20], game.prog[2] = True, 2
        result = game.step(["SHIELD", "STAY", "STAY", "STAY"])
        self.assertEqual(next(e for e in result["events"] if e["type"] == "shield")["caught"], [2, 3])
        self.assertEqual([game.owner[p] for p in (10, 20)], [1, 1])
        self.assertEqual(game.frozen[1:3], [2, 2])
        self.assertEqual(game.prog[1:3], [0, 0])
        self.assertFalse(any(e["type"] == "raid" for e in result["events"]))

    def test_using_own_shield_on_rival_land_does_not_grant_immunity(self):
        game = self.game()
        game.pos[1], game.owner[26] = 26, 1
        game.step(["SHIELD", "SHIELD", "STAY", "STAY"])
        self.assertEqual(game.frozen[:2], [0, 2])

    def test_new_human_game_explicit_model_and_legacy_override_are_separate(self):
        updated = server.HumanGame(dict(id="fixture"), "unused", 1, 1, 1, self.match, self.referee, FakeProcess)
        legacy = server.HumanGame(dict(id="fixture"), "unused", 1, 1, 1, self.match, self.referee, FakeProcess,
                                  rules={"catch_requires_stay": True})
        try:
            self.assertFalse(updated.g.rules["catch_requires_stay"])
            self.assertTrue(legacy.g.rules["catch_requires_stay"])
            self.assertTrue(self.referee.DEFAULT_RULES["catch_requires_stay"], "vendored defaults must not be silently rewritten")
            self.moving_fixture(legacy.g)
            legacy.g.step(["SHIELD", "WEST", "NORTH", "STAY"])
            self.assertEqual(legacy.g.frozen[:2], [2, 0], "historical rule model still reproduces its recorded outcome")
            self.assertEqual(set(updated.public("ai")), {"game_id", "turn", "over", "observation"})
        finally:
            updated.close()
            legacy.close()

    def test_new_recordings_hash_explicit_rules_without_changing_referee_source(self):
        root = (server.HERE / ".test-tmp").resolve()
        self.assertEqual(root.parent, server.HERE.resolve())
        root.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="post-movement-shield-", dir=root) as folder:
            updated = server.HumanGame(dict(id="fixture"), "unused", 2, 1, 1, self.match, self.referee,
                                       FakeProcess, history_dir=folder)
            try:
                recorded = history.read_history(folder, updated.id)["metadata"]
                self.assertFalse(recorded["rules"]["catch_requires_stay"])
                digest = hashlib.sha256(json.dumps(recorded["rules"], sort_keys=True, separators=(",", ":")).encode()).hexdigest()
                self.assertEqual(recorded["rules_sha256"], digest)
                self.assertEqual(recorded["referee_sha256"], self.provenance["files"]["referee.py"])
            finally:
                updated.close()

    def test_uploaded_turn34_changes_only_under_explicit_new_model(self):
        path = Path(r"C:\Users\LEGION\Downloads\zone-rush-44e7eb1d4c604285ab1af22ba0b3b7dc.json")
        if not path.exists():
            # The always-present geometric regression above remains mandatory.
            return
        before_hash = hashlib.sha256(path.read_bytes()).hexdigest()
        data = json.loads(path.read_text(encoding="utf-8"))
        self.assertTrue(data["metadata"]["rules"]["catch_requires_stay"])
        record = data["turns"][33]

        def build(rules):
            game = self.referee.Referee(data["metadata"]["base"], rules=rules)
            for name in ("owner", "upg", "pos", "frozen", "cd", "prog", "score"):
                setattr(game, name, copy.deepcopy(record["before"][name]))
            game.turn, game.token = record["before"]["turn"], record["before"]["token"]
            return game

        legacy = build(data["metadata"]["rules"])
        self.assertEqual(legacy.step(record["used"]), record["resolved"])
        self.assertEqual(legacy.snapshot(), record["after"])
        updated = build(dict(data["metadata"]["rules"], catch_requires_stay=False))
        result = updated.step(record["used"])
        self.assertEqual(updated.pos[1], 26)
        self.assertEqual(updated.frozen[:2], [0, 2])
        self.assertEqual(next(e for e in result["events"] if e["type"] == "shield")["caught"], [2])
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), before_hash, "the historical download must not be rewritten")

    def test_new_and_legacy_candidate_manifests_do_not_share_selection(self):
        class Repo:
            def refs(self):
                return []
        root = (server.HERE / ".test-tmp").resolve()
        root.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="rule-model-catalogs-", dir=root) as folder:
            folder = Path(folder)
            for filename, body in (("legacy.py", b"def act(state):\n return 'STAY'\n"),
                                   ("presence.py", b"def act(state):\n return state.legal_actions[0]\n")):
                (folder / filename).write_bytes(body)
                digest = hashlib.sha256(body).hexdigest()
                manifest = dict(format="zone-rush-candidate-catalog/1",
                                candidates=[dict(path=filename, sha256=digest, label=filename)],
                                recommended_sha256=digest, recommendation="Explicit model selection")
                manifest_name = "validated_catalog.json" if filename == "legacy.py" else server.PRESENCE_MANIFEST
                (folder / manifest_name).write_text(json.dumps(manifest), encoding="utf-8")
            legacy_bytes = (folder / "validated_catalog.json").read_bytes()
            legacy = server.Catalog(Repo(), None, folder)
            updated = server.Catalog(Repo(), None, folder, server.PRESENCE_MANIFEST)
            self.assertEqual(legacy.entries[legacy.recommended_id]["path"], "legacy.py")
            self.assertEqual(updated.entries[updated.recommended_id]["path"], "presence.py")
            self.assertNotEqual(legacy.recommended_id, updated.recommended_id)
            self.assertEqual((folder / "validated_catalog.json").read_bytes(), legacy_bytes)

    def test_presence_model_does_not_promote_unevaluated_legacy_git_winner(self):
        class Repo:
            def refs(self):
                return [dict(kind="remote", ref=server.PREFERRED_REF, commit="a"*40)]
            def bots_in_commit(self, _sha):
                return [dict(path=server.PREFERRED_PATH)]
            def blobs(self, specs):
                return [b"def act(state):\n return 'STAY'\n" for _ in specs]
        root = (server.HERE / ".test-tmp").resolve()
        root.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="unselected-presence-", dir=root) as folder:
            updated = server.Catalog(Repo(), None, folder, server.PRESENCE_MANIFEST)
            self.assertIsNone(updated.recommended_id)
            self.assertTrue(updated.entries)
            self.assertFalse(any(e["recommended"] for e in updated.entries.values()))


if __name__ == "__main__":
    unittest.main()
