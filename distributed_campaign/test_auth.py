"""Private cooperative authority, source-independent of campaign/actor code."""
import copy
import hashlib
import json
import os
from pathlib import Path
import pickle
import subprocess
import tempfile
import unittest
from unittest import mock

from distributed_campaign import auth


class AuthTests(unittest.TestCase):
    def setUp(self):
        auth.CACHE.mkdir(parents=True, exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(prefix="auth-tests-", dir=auth.CACHE)
        self.base = Path(self.temporary.name)
        self.meta = auth.provision(self.base/"private", {"creator": "physical-A", "auditor": "physical-B"})
        self.registry = auth.load_registry(self.meta["registry_path"])
        self.creator = auth.load_credentials(self.meta["credentials"]["creator"])
        self.auditor = auth.load_credentials(self.meta["credentials"]["auditor"])

    def tearDown(self):
        self.temporary.cleanup()

    def rejects(self, callback):
        with self.assertRaises(auth.AuthUnavailable) as raised:
            callback()
        self.assertEqual(str(raised.exception), auth.FAILURE)

    def test_unique_private_keys_and_secret_free_public_metadata(self):
        directory = Path(self.meta["registry_path"]).parent
        files = list((directory/"keys").glob("*.key"))
        secrets = [p.read_bytes() for p in files]
        self.assertTrue(len(files) == 3 and all(len(value) == 32 for value in secrets))
        self.assertTrue(len(set(secrets)) == 3)
        public = json.dumps(self.meta)
        for value in secrets:
            self.assertTrue(value.hex() not in public)
        helper_body = Path(self.meta["credentials"]["creator"]).read_bytes()
        owner = (directory/"keys/owner.key").read_bytes()
        auditor = (directory/"keys/slot-auditor.key").read_bytes()
        self.assertTrue(owner.hex().encode() not in helper_body and auditor.hex().encode() not in helper_body)
        self.assertEqual(auth.public_identity(self.creator), dict(slot_id="creator", physical_slot_id="physical-A"))
        self.assertEqual(auth.public_slots(self.registry)["auditor"], dict(slot_id="auditor", physical_slot_id="physical-B"))
        for path in files+[Path(self.meta["registry_path"]), Path(self.meta["credentials"]["creator"])]:
            auth.verify_private(path)
            auth.verify_private(path.parent, directory=True)

    def test_slot_signatures_roundtrip_and_defensive_payload_copies(self):
        payload = {"game": "game-1", "scores": [1, 2, 3, 4], "timing": 1.25}
        envelope = auth.sign(self.creator, "game-result", payload)
        self.assertEqual(set(envelope), {"slot_id", "physical_slot_id", "payload", "mac"})
        payload["scores"][0] = 99
        returned = auth.verify(self.registry, "game-result", envelope, expected_slot="creator")
        self.assertEqual(returned["scores"], [1, 2, 3, 4])
        returned["scores"][0] = 88
        self.assertEqual(auth.verify(self.creator, "game-result", envelope)["scores"], [1, 2, 3, 4])
        ordered = {"timing": 1.25, "scores": [1, 2, 3, 4], "game": "game-1"}
        self.assertEqual(auth.sign(self.creator, "game-result", ordered)["mac"], envelope["mac"])

    def test_purpose_payload_mac_shape_and_physical_binding(self):
        envelope = auth.sign(self.creator, "game-result", {"turns": 80})
        self.rejects(lambda: auth.verify(self.registry, "game-audit", envelope))
        self.rejects(lambda: auth.verify(self.registry, "game-result", envelope, expected_slot="auditor"))
        for changed in (
            dict(envelope, payload={"turns": 79}), dict(envelope, physical_slot_id="physical-B"),
            dict(envelope, slot_id="auditor"), dict(envelope, mac="0"*63),
            dict(envelope, mac=("1" if envelope["mac"][0] == "0" else "0")+envelope["mac"][1:]),
            dict(envelope, secret="unexpected"), {k: v for k, v in envelope.items() if k != "mac"},
        ):
            self.rejects(lambda changed=changed: auth.verify(self.registry, "game-result", changed))
        self.rejects(lambda: auth.verify(self.auditor, "game-result", envelope))

    def test_owner_assignment_credential_matches_only_that_helper(self):
        owner_slot = auth.owner_slot_credentials(self.registry, "creator")
        envelope = auth.sign(owner_slot, "assignment", {"task": "task-1"})
        self.assertEqual(auth.verify(self.creator, "assignment", envelope), {"task": "task-1"})
        self.rejects(lambda: auth.verify(self.auditor, "assignment", envelope))
        self.rejects(lambda: auth.owner_slot_credentials(self.registry, "unknown"))

    def test_owner_master_is_separate_from_every_helper_and_purpose(self):
        envelope = auth.sign_owner(self.registry, "runtime-approval", {"slot": "creator", "runtime": "fixed"})
        self.assertEqual(auth.verify_owner(self.registry, "runtime-approval", envelope)["slot"], "creator")
        self.rejects(lambda: auth.verify_owner(self.registry, "another-purpose", envelope))
        self.rejects(lambda: auth.sign_owner(self.creator, "runtime-approval", {}))
        self.rejects(lambda: auth.verify(self.creator, "runtime-approval", envelope))
        self.rejects(lambda: auth.verify_owner(self.registry, "runtime-approval", auth.sign(self.creator, "runtime-approval", {})))
        altered = copy.deepcopy(envelope)
        altered["payload"]["runtime"] = "different"
        self.rejects(lambda: auth.verify_owner(self.registry, "runtime-approval", altered))

    def test_foreign_registry_and_authority_fail(self):
        other_meta = auth.provision(self.base/"other", {"creator": "physical-A"})
        other = auth.load_registry(other_meta["registry_path"])
        envelope = auth.sign(self.creator, "result", {})
        self.rejects(lambda: auth.verify(other, "result", envelope))
        approval = auth.sign_owner(self.registry, "approval", {})
        self.rejects(lambda: auth.verify_owner(other, "approval", approval))

    def test_provision_refuses_duplicate_physical_slots_and_existing_authorities(self):
        for slots in ({"a": "same", "b": "same"}, {"a": "Same", "b": "same"}, {"a": "A", "A": "B"}):
            target = self.base/"duplicate"
            self.rejects(lambda slots=slots: auth.provision(target, slots))
            self.assertFalse(target.exists())
        self.rejects(lambda: auth.provision(self.base/"private", {"other": "physical-C"}))
        self.assertEqual(auth.public_identity(self.creator)["slot_id"], "creator")

    def test_missing_or_replaced_slot_key_is_never_regenerated(self):
        key = Path(self.meta["registry_path"]).parent/"keys/slot-creator.key"
        original = key.read_bytes()
        key.write_bytes(bytes([original[0] ^ 1])+original[1:])
        self.rejects(lambda: auth.owner_slot_credentials(self.registry, "creator"))
        self.rejects(lambda: auth.load_registry(self.meta["registry_path"]))
        key.unlink()
        self.rejects(lambda: auth.owner_slot_credentials(self.registry, "creator"))
        self.assertFalse(key.exists())
        self.rejects(lambda: auth.provision(self.base/"private", {"creator": "physical-A"}))
        self.assertFalse(key.exists())

    def test_master_key_replacement_and_registry_edits_fail(self):
        root = Path(self.meta["registry_path"]).parent
        path = root/"keys/owner.key"
        path.write_bytes(b"x"*32)
        self.rejects(lambda: auth.sign_owner(self.registry, "approval", {}))
        self.rejects(lambda: auth.load_registry(root/"registry.json"))
        registry = root/"registry.json"
        registry.write_bytes(registry.read_bytes()+b" ")
        self.rejects(lambda: auth.public_slots(self.registry))

    def test_replaced_helper_file_is_detected_and_cannot_authenticate_to_owner(self):
        path = Path(self.meta["credentials"]["creator"])
        record = json.loads(path.read_bytes())
        secret = b"z"*32
        record["key_hex"] = secret.hex()
        record["key_sha256"] = hashlib.sha256(secret).hexdigest()
        path.write_bytes(auth._canonical(record))
        self.rejects(lambda: auth.sign(self.creator, "result", {}))
        replacement = auth.load_credentials(path)
        self.rejects(lambda: auth.verify(self.registry, "result", auth.sign(replacement, "result", {})))

    def test_capabilities_never_serialize_and_invalid_objects_are_not_executed(self):
        for capability in (self.registry, self.creator, self.auditor):
            self.assertNotIn("key_hex", repr(capability))
            with self.assertRaises(TypeError):
                json.dumps(capability)
            with self.assertRaises(TypeError):
                pickle.dumps(capability)
            with self.assertRaises(TypeError):
                copy.deepcopy(capability)
            self.rejects(lambda: auth.sign(self.creator, "result", {"credential": capability}))
        class Trap:
            def __deepcopy__(self, memo):
                raise AssertionError("Untrusted object code must not execute")
        self.rejects(lambda: auth.sign(self.creator, "result", {"trap": Trap()}))
        for payload in ({"bad": float("nan")}, {"bad": float("inf")}, {1: "non-string key"}, ("tuple",)):
            self.rejects(lambda payload=payload: auth.sign(self.creator, "result", payload))

    def test_duplicate_json_and_wrong_secret_fingerprint_rejected(self):
        path = Path(self.meta["credentials"]["creator"])
        original = path.read_bytes()
        path.write_bytes(original.replace(b'"slot_id":', b'"slot_id":"duplicate","slot_id":', 1))
        self.rejects(lambda: auth.load_credentials(path))
        record = json.loads(original)
        record["key_sha256"] = "0"*64
        path.write_bytes(auth._canonical(record))
        self.rejects(lambda: auth.load_credentials(path))

    def test_explicit_helper_import_outside_owner_cache(self):
        with tempfile.TemporaryDirectory(prefix="foreign-helper-", dir=auth.ROOT/".cache") as outside:
            target = Path(outside)/"private"
            result = auth.import_credentials(self.meta["credentials"]["creator"], target)
            credentials = auth.load_credentials(result["credential_path"])
            self.assertEqual(auth.verify(self.registry, "result", auth.sign(credentials, "result", {"x": 1})), {"x": 1})
            self.rejects(lambda: auth.load_registry(result["credential_path"]))
            self.rejects(lambda: auth.import_credentials(self.meta["credentials"]["creator"], target))

    def test_private_acl_failure_is_not_ignored(self):
        path = Path(self.meta["credentials"]["creator"])
        try:
            if os.name == "nt":
                result = subprocess.run(["icacls", str(path), "/grant", "*S-1-1-0:(R)"], capture_output=True,
                                        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                self.assertEqual(result.returncode, 0)
            else:
                path.chmod(0o644)
            self.rejects(lambda: auth.load_credentials(path))
        finally:
            auth.restrict(path)
        self.assertEqual(auth.public_identity(auth.load_credentials(path))["slot_id"], "creator")

    def test_links_and_hardlinks_are_rejected(self):
        real = self.base/"real"
        real.mkdir()
        link = self.base/"linked"
        if os.name == "nt":
            result = subprocess.run(["cmd", "/d", "/c", "mklink", "/J", str(link), str(real)],
                                    capture_output=True, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            self.assertEqual(result.returncode, 0)
        else:
            link.symlink_to(real, target_is_directory=True)
        try:
            self.rejects(lambda: auth.provision(link/"authority", {"s": "p"}))
            self.assertFalse((real/"authority").exists())
        finally:
            if os.name == "nt":
                link.rmdir()
            else:
                link.unlink()
        key = Path(self.meta["registry_path"]).parent/"keys/slot-creator.key"
        alias = self.base/"key-alias"
        os.link(key, alias)
        try:
            self.rejects(lambda: auth.owner_slot_credentials(self.registry, "creator"))
        finally:
            alias.unlink()

    def test_safe_hardening_refuses_a_broad_folder(self):
        folder = self.base/"broad"
        folder.mkdir()
        path = folder/"credential.json"
        path.write_bytes(Path(self.meta["credentials"]["creator"]).read_bytes())
        (folder/"unrelated.txt").write_text("unrelated")
        with mock.patch.object(auth, "verify_private", side_effect=PermissionError("not private")):
            self.rejects(lambda: auth.secure_credentials(path))
        self.assertTrue((folder/"unrelated.txt").exists())


if __name__ == "__main__":
    unittest.main()
