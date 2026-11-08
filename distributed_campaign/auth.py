"""Private per-slot cooperative HMAC authority; never an actor capability.

The registry and owner master remain in the owner's ignored cache. A helper
receives only its own credential file, imported into a dedicated private folder.
Keys authenticate a trusted credential, not computation or physical-machine
integrity. Do not pass Registry/Credentials objects to game or audit processes.
"""
import copy
import hashlib
import hmac
import json
import math
import os
from pathlib import Path
import re
import secrets
import stat

from campaign_holdout.authority import restrict, verify_private

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT/".cache/distributed_campaign"
REGISTRY_FORMAT = "zone-rush-private-slot-registry/1"
CREDENTIAL_FORMAT = "zone-rush-private-slot-credential/1"
IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}\Z")
HEX64 = re.compile(r"[0-9a-f]{64}\Z")
HEX32 = re.compile(r"[0-9a-f]{32}\Z")
PURPOSE = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9_.:/-]{0,127}\Z")
FAILURE = "Distributed authentication unavailable or invalid"


class AuthUnavailable(ValueError):
    """Generic failure deliberately excludes paths, payloads and key material."""


def _fail():
    raise AuthUnavailable(FAILURE)


def _canonical(value):
    def inspect(item, depth=0):
        if depth > 64:
            _fail()
        kind = type(item)
        if item is None or kind in (bool, int, str):
            return
        if kind is float and math.isfinite(item):
            return
        if kind is list:
            for child in item:
                inspect(child, depth+1)
            return
        if kind is dict and all(type(key) is str for key in item):
            for child in item.values():
                inspect(child, depth+1)
            return
        _fail()
    inspect(value)
    body = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf8")
    if len(body) > 16*1024*1024:
        _fail()
    return body


def _loads(body):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                _fail()
            result[key] = value
        return result
    value = json.loads(body, object_pairs_hook=pairs, parse_constant=lambda _: _fail())
    _canonical(value)
    return value


def _identifier(value):
    if type(value) is not str or not IDENTIFIER.fullmatch(value):
        _fail()
    return value


def _hex(value, pattern=HEX64):
    if type(value) is not str or not pattern.fullmatch(value):
        _fail()
    return value


def _path(value, owner=False):
    """Reject links/reparse points BEFORE resolving or touching private data."""
    path = Path(os.path.abspath(value))
    if owner and not path.is_relative_to(CACHE):
        _fail()
    current = Path(path.anchor)
    for part in path.parts[1:]:
        current /= part
        try:
            info = current.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            _fail()
    if path.resolve() != path:
        _fail()
    return path


def _read_private(path, maximum=512*1024):
    path = _path(path)
    verify_private(path.parent, directory=True)
    before = path.lstat()
    if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or before.st_size > maximum:
        _fail()
    verify_private(path)
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags)
    try:
        opened = os.fstat(descriptor)
        with os.fdopen(descriptor, "rb", closefd=False) as handle:
            body = handle.read(maximum+1)
        after = path.lstat()
        if (len(body) > maximum or (before.st_dev, before.st_ino) != (opened.st_dev, opened.st_ino)
                or (opened.st_dev, opened.st_ino) != (after.st_dev, after.st_ino)
                or opened.st_nlink != 1 or after.st_nlink != 1):
            _fail()
        _path(path)
        verify_private(path)
        return body
    finally:
        os.close(descriptor)


def _write_private(path, body):
    path = _path(path)
    verify_private(path.parent, directory=True)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0), 0o600)
    try:
        # Restrict the empty file before any secret reaches the filesystem.
        restrict(path)
        with os.fdopen(descriptor, "wb", closefd=False) as handle:
            handle.write(body)
            handle.flush()
            os.fsync(handle.fileno())
    finally:
        os.close(descriptor)
    _read_private(path)


def _private_directory(path):
    path = _path(path)
    path.mkdir(parents=True, exist_ok=False)
    restrict(path, directory=True)
    verify_private(path, directory=True)
    return path


def _credential_record(value):
    if type(value) is not dict or set(value) != {
        "format", "authority_id", "slot_id", "physical_slot_id", "key_sha256", "key_hex"
    } or value["format"] != CREDENTIAL_FORMAT:
        _fail()
    _hex(value["authority_id"], HEX32)
    _identifier(value["slot_id"])
    _identifier(value["physical_slot_id"])
    expected, encoded = _hex(value["key_sha256"]), _hex(value["key_hex"])
    secret = bytes.fromhex(encoded)
    if len(secret) != 32 or not hmac.compare_digest(hashlib.sha256(secret).hexdigest(), expected):
        _fail()
    return value


class _PrivateObject:
    __slots__ = ()

    def __repr__(self):
        return "<private distributed authentication capability>"

    def __reduce_ex__(self, protocol):
        raise TypeError("Private authentication capabilities cannot be serialized")

    def __copy__(self):
        raise TypeError("Private authentication capabilities cannot be copied")

    def __deepcopy__(self, memo):
        raise TypeError("Private authentication capabilities cannot be copied")


class _Registry(_PrivateObject):
    __slots__ = ("_path", "_fingerprint", "_record")

    def __init__(self, path, body, record):
        self._path = path
        self._fingerprint = hashlib.sha256(body).hexdigest()
        self._record = record

    def _check(self):
        _path(self._path, owner=True)
        body = _read_private(self._path)
        if not hmac.compare_digest(hashlib.sha256(body).hexdigest(), self._fingerprint):
            _fail()
        if _canonical(_loads(body)) != _canonical(self._record):
            _fail()

    def _secret(self, slot=None):
        self._check()
        record = self._record["owner_key"] if slot is None else self._record["slots"][slot]
        path = _path(self._path.parent/record["key_file"], owner=True)
        body = _read_private(path, maximum=32)
        if len(body) != 32 or not hmac.compare_digest(hashlib.sha256(body).hexdigest(), record["key_sha256"]):
            _fail()
        return body


class _Credentials(_PrivateObject):
    __slots__ = ("_path", "_fingerprint", "_identity", "_authority_id", "_registry")

    def __init__(self, *, path=None, body=None, record=None, registry=None, slot=None):
        self._registry = registry
        if registry is not None:
            row = registry._record["slots"][slot]
            self._path = None
            self._fingerprint = None
            self._authority_id = registry._record["authority_id"]
            self._identity = dict(slot_id=slot, physical_slot_id=row["physical_slot_id"])
        else:
            self._path = path
            self._fingerprint = hashlib.sha256(body).hexdigest()
            self._authority_id = record["authority_id"]
            self._identity = {key: record[key] for key in ("slot_id", "physical_slot_id")}

    def _secret(self):
        if self._registry is not None:
            return self._registry._secret(self._identity["slot_id"])
        body = _read_private(self._path)
        if not hmac.compare_digest(hashlib.sha256(body).hexdigest(), self._fingerprint):
            _fail()
        record = _credential_record(_loads(body))
        if record["authority_id"] != self._authority_id or public_identity_from_record(record) != self._identity:
            _fail()
        return bytes.fromhex(record["key_hex"])


def public_identity_from_record(record):
    return {key: record[key] for key in ("slot_id", "physical_slot_id")}


def provision(directory, slots):
    """Create a NEW owner-private authority and one private file per helper.

    The directory must be fresh and inside ROOT/.cache/distributed_campaign.
    Existing or partial authorities are never overwritten or regenerated.
    Returned metadata contains paths and public identities, never keys.
    """
    try:
        if type(slots) is not dict or not 1 <= len(slots) <= 1024:
            _fail()
        normalized = {_identifier(slot): _identifier(physical) for slot, physical in slots.items()}
        if (len({value.casefold() for value in normalized.values()}) != len(normalized)
                or len({slot.casefold() for slot in normalized}) != len(normalized)):
            _fail()
        directory = _path(directory, owner=True)
        if directory == CACHE or directory.exists():
            _fail()
        _private_directory(directory)
        _private_directory(directory/"keys")
        _private_directory(directory/"credentials")
        authority_id = secrets.token_hex(16)
        used = set()
        def new_secret():
            for _ in range(16):
                value = secrets.token_bytes(32)
                fingerprint = hashlib.sha256(value).hexdigest()
                if fingerprint not in used:
                    used.add(fingerprint)
                    return value, fingerprint
            _fail()
        master, master_sha = new_secret()
        _write_private(directory/"keys/owner.key", master)
        record = dict(format=REGISTRY_FORMAT, authority_id=authority_id,
                      owner_key=dict(key_file="keys/owner.key", key_sha256=master_sha), slots={})
        exports = {}
        for slot, physical in sorted(normalized.items()):
            secret, fingerprint = new_secret()
            key_file = "keys/slot-"+slot+".key"
            credential_file = "credentials/helper-"+slot+".json"
            _write_private(directory/key_file, secret)
            credential = dict(format=CREDENTIAL_FORMAT, authority_id=authority_id,
                              slot_id=slot, physical_slot_id=physical,
                              key_sha256=fingerprint, key_hex=secret.hex())
            _write_private(directory/credential_file, _canonical(credential)+b"\n")
            record["slots"][slot] = dict(slot_id=slot, physical_slot_id=physical,
                                         key_file=key_file, key_sha256=fingerprint,
                                         credential_file=credential_file)
            exports[slot] = str(directory/credential_file)
        _write_private(directory/"registry.json", _canonical(record)+b"\n")
        load_registry(directory/"registry.json")
        return dict(registry_path=str(directory/"registry.json"), authority_id=authority_id,
                    credentials=exports, slots={slot: dict(slot_id=slot, physical_slot_id=physical)
                                               for slot, physical in normalized.items()})
    except Exception:
        raise AuthUnavailable(FAILURE) from None


def load_registry(path):
    try:
        path = _path(path, owner=True)
        body = _read_private(path)
        value = _loads(body)
        if type(value) is not dict or set(value) != {"format", "authority_id", "owner_key", "slots"} or value["format"] != REGISTRY_FORMAT:
            _fail()
        _hex(value["authority_id"], HEX32)
        owner_key = value["owner_key"]
        if type(owner_key) is not dict or set(owner_key) != {"key_file", "key_sha256"} or owner_key["key_file"] != "keys/owner.key":
            _fail()
        _hex(owner_key["key_sha256"])
        if type(value["slots"]) is not dict or not 1 <= len(value["slots"]) <= 1024:
            _fail()
        physical_ids, slot_ids, key_hashes = set(), set(), {owner_key["key_sha256"]}
        for slot, row in value["slots"].items():
            _identifier(slot)
            if type(row) is not dict or set(row) != {"slot_id", "physical_slot_id", "key_file", "key_sha256", "credential_file"}:
                _fail()
            physical = _identifier(row["physical_slot_id"])
            fingerprint = _hex(row["key_sha256"])
            if (row["slot_id"] != slot or physical.casefold() in physical_ids or slot.casefold() in slot_ids or fingerprint in key_hashes
                    or row["key_file"] != "keys/slot-"+slot+".key"
                    or row["credential_file"] != "credentials/helper-"+slot+".json"):
                _fail()
            physical_ids.add(physical.casefold())
            slot_ids.add(slot.casefold())
            key_hashes.add(fingerprint)
        registry = _Registry(path, body, value)
        registry._secret()
        for slot in value["slots"]:
            registry._secret(slot)
        return registry
    except Exception:
        raise AuthUnavailable(FAILURE) from None


def load_credentials(path):
    try:
        path = _path(path)
        body = _read_private(path)
        value = _credential_record(_loads(body))
        return _Credentials(path=path, body=body, record=value)
    except Exception:
        raise AuthUnavailable(FAILURE) from None


def secure_credentials(path):
    """Explicitly harden a copied credential in a dedicated single-file folder.

    Broad folders containing other files are refused rather than having their
    access controls changed. No key is replaced or generated by this operation.
    """
    try:
        path = _path(path)
        info = path.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            _fail()
        try:
            verify_private(path.parent, directory=True)
        except Exception:
            if {p.name for p in path.parent.iterdir()} != {path.name}:
                _fail()
            restrict(path.parent, directory=True)
        restrict(path)
        return load_credentials(path)
    except Exception:
        raise AuthUnavailable(FAILURE) from None


def import_credentials(source_path, private_directory):
    """Explicit first transfer into a FRESH dedicated helper-private folder."""
    try:
        source = _path(source_path)
        info = source.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > 512*1024:
            _fail()
        body = source.read_bytes()
        _credential_record(_loads(body))
        destination = _private_directory(_path(private_directory))
        target = destination/"credential.json"
        _write_private(target, body)
        return dict(credential_path=str(target), identity=public_identity(load_credentials(target)))
    except Exception:
        raise AuthUnavailable(FAILURE) from None


def owner_slot_credentials(registry, slot):
    try:
        if not isinstance(registry, _Registry):
            _fail()
        _identifier(slot)
        registry._secret(slot)
        return _Credentials(registry=registry, slot=slot)
    except Exception:
        raise AuthUnavailable(FAILURE) from None


def public_identity(credentials):
    try:
        if not isinstance(credentials, _Credentials):
            _fail()
        credentials._secret()
        return dict(credentials._identity)
    except Exception:
        raise AuthUnavailable(FAILURE) from None


def public_slots(registry):
    try:
        if not isinstance(registry, _Registry):
            _fail()
        registry._check()
        return {slot: dict(slot_id=slot, physical_slot_id=row["physical_slot_id"])
                for slot, row in registry._record["slots"].items()}
    except Exception:
        raise AuthUnavailable(FAILURE) from None


def _message(credentials, purpose, payload):
    if type(purpose) is not str or not PURPOSE.fullmatch(purpose):
        _fail()
    return _canonical(dict(domain="zone-rush-distributed-slot-auth/1", authority_id=credentials._authority_id,
                           purpose=purpose, **credentials._identity, payload=payload))


def sign(credentials, purpose, payload):
    try:
        if not isinstance(credentials, _Credentials):
            _fail()
        _canonical(payload)
        copied = copy.deepcopy(payload)
        mac = hmac.new(credentials._secret(), _message(credentials, purpose, copied), hashlib.sha256).hexdigest()
        return dict(**credentials._identity, payload=copied, mac=mac)
    except Exception:
        raise AuthUnavailable(FAILURE) from None


def verify(registry_or_credentials, purpose, envelope, expected_slot=None):
    try:
        if type(envelope) is not dict or set(envelope) != {"slot_id", "physical_slot_id", "payload", "mac"}:
            _fail()
        slot, physical, provided = _identifier(envelope["slot_id"]), _identifier(envelope["physical_slot_id"]), _hex(envelope["mac"])
        if expected_slot is not None and slot != _identifier(expected_slot):
            _fail()
        if isinstance(registry_or_credentials, _Registry):
            credentials = owner_slot_credentials(registry_or_credentials, slot)
        elif isinstance(registry_or_credentials, _Credentials):
            credentials = registry_or_credentials
        else:
            _fail()
        if credentials._identity != dict(slot_id=slot, physical_slot_id=physical):
            _fail()
        _canonical(envelope["payload"])
        payload = copy.deepcopy(envelope["payload"])
        expected = hmac.new(credentials._secret(), _message(credentials, purpose, payload), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, provided):
            _fail()
        return payload
    except Exception:
        raise AuthUnavailable(FAILURE) from None


def _owner_message(registry, purpose, payload):
    if type(purpose) is not str or not PURPOSE.fullmatch(purpose):
        _fail()
    return _canonical(dict(domain="zone-rush-distributed-owner-auth/1", authority_id=registry._record["authority_id"],
                           purpose=purpose, payload=payload))


def sign_owner(registry, purpose, payload):
    try:
        if not isinstance(registry, _Registry):
            _fail()
        _canonical(payload)
        copied = copy.deepcopy(payload)
        mac = hmac.new(registry._secret(), _owner_message(registry, purpose, copied), hashlib.sha256).hexdigest()
        return dict(authority_id=registry._record["authority_id"], payload=copied, mac=mac)
    except Exception:
        raise AuthUnavailable(FAILURE) from None


def verify_owner(registry, purpose, envelope):
    try:
        if not isinstance(registry, _Registry) or type(envelope) is not dict or set(envelope) != {"authority_id", "payload", "mac"}:
            _fail()
        if envelope["authority_id"] != registry._record["authority_id"]:
            _fail()
        provided = _hex(envelope["mac"])
        _canonical(envelope["payload"])
        payload = copy.deepcopy(envelope["payload"])
        expected = hmac.new(registry._secret(), _owner_message(registry, purpose, payload), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, provided):
            _fail()
        return payload
    except Exception:
        raise AuthUnavailable(FAILURE) from None
