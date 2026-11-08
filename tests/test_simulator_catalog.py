"""The focused simulator runs from local files, independent of Git history."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import types
import unittest
from unittest import mock

from simulator import server


BOT = b"def act(state):\n return 'STAY'\n"
TESTER = b"def act(state):\n return state.legal_actions[0]\n"


class LocalCatalogTests(unittest.TestCase):
    def setUp(self):
        directory = server.HERE / ".test-tmp"
        directory.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix="local-release-", dir=directory)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.snapshot = self.root / "snapshots"
        (self.root / "bot.py").write_bytes(BOT)
        (self.root / "tester_bots").mkdir()
        (self.root / "tester_bots/strong.py").write_bytes(TESTER)

    def catalog(self):
        return server.Catalog(self.root, self.snapshot)

    def manifest(self, **changes):
        data = dict(format="zone-rush-consolidated-release/1",
                    bot_sha256=hashlib.sha256(BOT).hexdigest(),
                    tester_bots=[dict(path="tester_bots/strong.py", label="Retained tester",
                                      sha256=hashlib.sha256(TESTER).hexdigest())],
                    recommendation="Selected using the saved comparison panel.")
        data.update(changes)
        (self.root / server.RELEASE_MANIFEST).write_text(json.dumps(data), encoding="utf-8")

    def test_zip_folder_uses_local_bot_and_testers_without_git(self):
        with mock.patch.object(subprocess, "run", side_effect=AssertionError("Git must not be called")):
            catalog = self.catalog()
            metadata, filename = catalog.resolve(catalog.recommended_id)
            server.bootstrap()
        self.assertEqual(metadata["path"], "bot.py")
        self.assertTrue(metadata["recommended"])
        self.assertEqual(Path(filename).read_bytes(), BOT)
        self.assertEqual(len(catalog.entries), 2)
        self.assertNotIn(str(self.root), json.dumps(catalog.public()))

    def test_manifest_selects_exact_release_and_only_named_testers(self):
        self.manifest()
        (self.root / "tester_bots/unlisted.py").write_bytes(b"def act(state):\n return 'SHIELD'\n")
        catalog = self.catalog()
        self.assertEqual(len(catalog.entries), 2)
        self.assertFalse(catalog.warnings)
        self.assertIn("saved comparison", catalog.public()["recommendation"])
        self.assertEqual({e["label"] for e in catalog.entries.values()},
                         {"Consolidated bot", "Retained tester"})

    def test_manifest_tester_without_fingerprint_is_not_exposed(self):
        self.manifest(tester_bots=[dict(path="tester_bots/strong.py", label="Unpinned tester")])
        catalog = self.catalog()
        self.assertEqual(len(catalog.entries), 1)
        self.assertTrue(catalog.entries[catalog.recommended_id]["recommended"])
        self.assertTrue(catalog.warnings)

    def test_wrong_release_fingerprint_never_recommends_unverified_code(self):
        self.manifest(bot_sha256="f" * 64)
        catalog = self.catalog()
        self.assertIsNone(catalog.recommended_id)
        self.assertTrue(catalog.warnings)
        with self.assertRaises(server.APIError):
            catalog.resolve(catalog.recommended_id)

    def test_bad_manifest_disables_new_selections_instead_of_falling_back(self):
        (self.root / server.RELEASE_MANIFEST).write_text("null", encoding="utf-8")
        catalog = self.catalog()
        self.assertEqual(catalog.entries, {})
        self.assertIsNone(catalog.recommended_id)
        self.assertTrue(catalog.warnings)

    def test_snapshot_cannot_change_when_original_file_is_updated(self):
        catalog = self.catalog()
        metadata, filename = catalog.resolve(catalog.recommended_id)
        (self.root / "bot.py").write_bytes(TESTER)
        self.assertEqual(Path(filename).read_bytes(), BOT)
        self.assertEqual(metadata["sha256"], hashlib.sha256(BOT).hexdigest())
        with self.assertRaises(RuntimeError):
            catalog.resolve(catalog.recommended_id)

    def test_tampered_snapshot_is_rejected(self):
        catalog = self.catalog()
        _, filename = catalog.resolve(catalog.recommended_id)
        Path(filename).write_bytes(TESTER)
        with self.assertRaises(RuntimeError):
            catalog.resolve(catalog.recommended_id)

    def test_manifest_cannot_select_parent_or_arbitrary_python_files(self):
        for path in ("../outside.py", "simulator/server.py", "tester_bots/../outside.py"):
            with self.subTest(path=path):
                self.manifest(tester_bots=[dict(path=path, label="Bad path",
                                              sha256=hashlib.sha256(TESTER).hexdigest())])
                catalog = self.catalog()
                self.assertEqual(len(catalog.entries), 1)
                self.assertTrue(catalog.warnings)

    def test_duplicate_exact_sources_are_listed_once(self):
        (self.root / "tester_bots/duplicate.py").write_bytes(BOT)
        catalog = self.catalog()
        self.assertEqual(len(catalog.entries), 2)
        self.assertEqual(catalog.entries[catalog.recommended_id]["path"], "bot.py")

    def test_bootstrap_restores_other_tools_module_aliases(self):
        prior = types.ModuleType("referee")
        with mock.patch.dict(sys.modules, {"referee": prior}):
            with mock.patch.object(server, "_BOOTSTRAP", None):
                match, referee, _, _ = server.bootstrap()
                self.assertIs(match.Referee, referee.Referee)
            self.assertIs(sys.modules["referee"], prior)

    def test_changed_bundled_harness_is_rejected_even_after_cached_load(self):
        vendor = self.root / "vendor"
        shutil.copytree(server.VENDOR, vendor, ignore=shutil.ignore_patterns("__pycache__", ".cache"))
        (vendor / "referee.py").write_bytes(b"# different source\n")
        with mock.patch.object(server, "VENDOR", vendor):
            with self.assertRaisesRegex(RuntimeError, "bundled harness file changed"):
                server.bootstrap()


if __name__ == "__main__":
    unittest.main()
