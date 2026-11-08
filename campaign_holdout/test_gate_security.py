"""Adversarial local authority tests, with explicit mocked training admission."""
import copy
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from evolution.genomes import digest
from primary_campaign import core as primary
from campaign_holdout import authority, core
from campaign_holdout.test_holdout import admitted_fixture


class GateSecurityTests(unittest.TestCase):
    def setUp(self):
        self.cache = (primary.ROOT/".cache").resolve()
        self.temp = tempfile.TemporaryDirectory(prefix="heldout-security-", dir=self.cache)
        self.directory = Path(self.temp.name).resolve()
        self.assertTrue(self.directory.is_relative_to(self.cache))
        self.addCleanup(self.temp.cleanup)

    def admitted(self):
        return admitted_fixture(self.directory)

    def active(self):
        root = authority.location(self.directory)
        pointer = core.oversight.strict_loads((root/"active_development_gate.json").read_bytes())
        path = root/"gates"/pointer["gate"]
        return path, core.read(path)

    def publish_forgery(self, envelope):
        root = authority.location(self.directory)
        name = "development-"+digest(primary.canonical(envelope))+".json"
        core.seal(root/"gates"/name, envelope)
        primary.atomic(root/"active_development_gate.json", primary.canonical({"gate": name})+b"\n")

    def test_rehashed_approval_does_not_replace_the_owner_mac(self):
        self.admitted()
        old_path, envelope = self.active()
        changed = copy.deepcopy(envelope)
        changed["payload"]["stages"][0]["games"] += 1
        self.publish_forgery(changed)  # Correct filename, JSON hash, sidecar and pointer; WRONG MAC.
        with self.assertRaises(authority.GateUnavailable):
            core.require_admission(self.directory)
        self.assertTrue(old_path.exists())

    def test_unsigned_preapproval_is_rejected(self):
        self.admitted()
        _, envelope = self.active()
        changed = copy.deepcopy(envelope)
        changed["mac"] = "0"*64
        self.publish_forgery(changed)
        with self.assertRaises(authority.GateUnavailable):
            core.require_admission(self.directory)

    def test_missing_or_replaced_key_never_silently_blesses_old_gate(self):
        self.admitted()
        _, envelope = self.active()
        path = authority.safe_path(self.directory, ".authority", envelope["key_id"]+".key")
        path.write_bytes(b"\0"*32)
        with self.assertRaises(authority.GateUnavailable):
            core.require_admission(self.directory)
        path.unlink()
        with patch.object(core, "_deep_training", side_effect=AssertionError("Silent recovery")):
            with self.assertRaises(authority.GateUnavailable):
                core.admit_development(self.directory)
        self.assertFalse(list(path.parent.glob("*.key")))

    def test_explicit_recovery_revalidates_and_preserves_original_gate_and_shortlist(self):
        _, _, training, shortlist = self.admitted()
        old_path, envelope = self.active()
        old_key = authority.safe_path(self.directory, ".authority", envelope["key_id"]+".key")
        old_key.unlink()
        payload = envelope["payload"]
        # Revalidation is mocked only in this mechanics fixture. The production
        # recovery path calls all scheduled primary.validated_audit operations.
        with patch.object(core, "_deep_training", return_value=(payload["bindings"], payload["stages"], training)) as deep:
            recovered = core.admit_development(self.directory, recover=True)
        self.assertEqual(deep.call_count, 1)
        self.assertEqual(recovered, shortlist)
        new_path, new_envelope = self.active()
        self.assertNotEqual(new_envelope["key_id"], envelope["key_id"])
        self.assertNotEqual(new_path, old_path)
        self.assertTrue(old_path.is_file())

    def test_raw_log_rewrite_with_same_size_and_mtime_invalidates_cache(self):
        self.admitted()
        path = self.directory/"train_000/games.jsonl"
        before, info = path.read_bytes(), path.stat()
        path.write_bytes(b"["+before[1:])
        os.utime(path, ns=(info.st_atime_ns, info.st_mtime_ns))
        self.assertEqual(path.stat().st_size, len(before))
        self.assertEqual(path.stat().st_mtime_ns, info.st_mtime_ns)
        with self.assertRaises(ValueError):
            core.require_admission(self.directory)

    def test_shortlist_export_drift_invalidates_admission(self):
        _, _, _, shortlist = self.admitted()
        path = Path(shortlist["candidates"][1]["path"])
        path.write_bytes(path.read_bytes()+b"\n# changed\n")
        with self.assertRaises(ValueError):
            core.require_admission(self.directory)

    def test_purpose_binding_blocks_actor_or_final_signature_reuse(self):
        self.admitted()
        _, envelope = self.active()
        with self.assertRaises(authority.GateUnavailable):
            authority.authenticate(self.directory, "final", envelope)
        with self.assertRaises(authority.GateUnavailable):
            authority.authenticate(self.directory, "actor:unrelated", envelope)

    def test_copied_train000_cannot_stand_in_for_all_scheduled_stages(self):
        shape = dict(train_maps=8, development_maps=4, final_maps=4,
                     maps_per_generation=4, episodes_per_map=200, population=8)
        primary.create_catalog(self.directory, 202611090822, shape)
        primary.prepare_generation(self.directory, 0)
        first, copied = self.directory/"train_000", self.directory/"train_001"
        core.seal(first/"audit.json", dict(approved=True, phase="train", generation=0, profile="mechanics_test"))
        copied.mkdir()
        for name in ("audit.json", "audit.sha256"):
            shutil.copyfile(first/name, copied/name)
        with patch.object(primary, "validated_audit", side_effect=AssertionError("Copied-stage preflight failed")):
            with self.assertRaisesRegex(ValueError, "another generation"):
                core.admit_development(self.directory)

    def test_junction_or_symlink_cannot_redirect_private_acl_or_key_creation(self):
        campaign, outside = self.directory/"campaign", self.directory/"outside-campaign"
        campaign.mkdir(); outside.mkdir(); (campaign/"heldout").mkdir()
        link = campaign/"heldout/.authority"
        if os.name == "nt":
            result = subprocess.run(["cmd", "/d", "/c", "mklink", "/J", str(link), str(outside)], capture_output=True)
            if result.returncode:
                self.skipTest("This Windows host cannot create a test junction")
        else:
            link.symlink_to(outside, target_is_directory=True)
        try:
            with patch.object(authority, "restrict", side_effect=AssertionError("ACL write reached redirected target")):
                with self.assertRaises(ValueError):
                    authority.new_key(campaign)
            self.assertFalse(list(outside.iterdir()))
        finally:
            if os.name == "nt":
                os.rmdir(link)  # Remove only this verified test junction, never its target.
            else:
                link.unlink()


if __name__ == "__main__":
    unittest.main()
