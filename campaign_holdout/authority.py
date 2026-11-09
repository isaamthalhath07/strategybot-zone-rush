"""Owner-local HMAC authority. Keys never enter jobs, receipts, or packages."""
from functools import lru_cache
import csv
import ctypes
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import secrets
import stat
import subprocess

from evolution.runner import ROOT, canonical


class GateUnavailable(ValueError):
    pass


def location(campaign):
    campaign = Path(os.path.abspath(campaign))
    cache = ROOT/".cache"
    if not campaign.is_relative_to(cache):
        raise ValueError("Campaign authority must stay in the owner's ignored cache")
    return _without_links(campaign/"heldout", cache)


def _without_links(path, base):
    path, base = Path(path), Path(base)
    if not path.is_absolute() or not path.is_relative_to(base):
        raise ValueError("Authority path escaped its intended local directory")
    current = base
    for part in ("", *path.relative_to(base).parts):
        if part:
            current = current/part
        try:
            info = current.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            raise ValueError("Links and Windows reparse points are forbidden in authority paths")
    if path.resolve() != path:
        raise ValueError("Authority path resolution changed its target")
    return path


def safe_path(campaign, *parts):
    root = location(campaign)
    return _without_links(root.joinpath(*parts), root)


@lru_cache(maxsize=1)
def _sid():
    result = subprocess.run(["whoami", "/user", "/fo", "csv", "/nh"], check=True,
                            capture_output=True, text=True,
                            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    values = next(csv.reader(result.stdout.splitlines()))
    candidates = [v for v in values if re.fullmatch(r"S-1-\d+(?:-\d+)+", v)]
    if len(candidates) != 1:
        raise PermissionError("Cannot establish the current owner SID")
    return candidates[0]


def _windows_sddl(path, set_private=False, directory=False):
    from ctypes import wintypes as w
    adv = ctypes.WinDLL("advapi32", use_last_error=True)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    expected = "D:P(A;"+("OICI" if directory else "")+";FA;;;"+_sid()+")"
    sd = ctypes.c_void_p()
    adv.ConvertStringSecurityDescriptorToSecurityDescriptorW.argtypes = [w.LPCWSTR, w.DWORD, ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(w.DWORD)]
    adv.ConvertStringSecurityDescriptorToSecurityDescriptorW.restype = w.BOOL
    adv.GetSecurityDescriptorDacl.argtypes = [ctypes.c_void_p, ctypes.POINTER(w.BOOL), ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(w.BOOL)]
    adv.GetSecurityDescriptorDacl.restype = w.BOOL
    adv.SetNamedSecurityInfoW.argtypes = [w.LPWSTR, w.DWORD, w.DWORD, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p]
    adv.SetNamedSecurityInfoW.restype = w.DWORD
    adv.GetNamedSecurityInfoW.argtypes = [w.LPWSTR, w.DWORD, w.DWORD, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)]
    adv.GetNamedSecurityInfoW.restype = w.DWORD
    adv.ConvertSecurityDescriptorToStringSecurityDescriptorW.argtypes = [ctypes.c_void_p, w.DWORD, w.DWORD, ctypes.POINTER(w.LPWSTR), ctypes.POINTER(w.DWORD)]
    adv.ConvertSecurityDescriptorToStringSecurityDescriptorW.restype = w.BOOL
    kernel.LocalFree.argtypes = [ctypes.c_void_p]
    kernel.LocalFree.restype = ctypes.c_void_p
    if set_private:
        if not adv.ConvertStringSecurityDescriptorToSecurityDescriptorW(expected, 1, ctypes.byref(sd), None):
            raise PermissionError("Cannot construct owner-only access control")
        try:
            present, defaulted, dacl = w.BOOL(), w.BOOL(), ctypes.c_void_p()
            if not adv.GetSecurityDescriptorDacl(sd, ctypes.byref(present), ctypes.byref(dacl), ctypes.byref(defaulted)) or not present:
                raise PermissionError("Cannot read owner-only access control")
            if adv.SetNamedSecurityInfoW(str(path), 1, 0x80000004, None, None, dacl, None):
                raise PermissionError("Cannot restrict local authority to its owner")
        finally:
            kernel.LocalFree(sd)
    sd = ctypes.c_void_p()
    if adv.GetNamedSecurityInfoW(str(path), 1, 4, None, None, None, None, ctypes.byref(sd)):
        raise PermissionError("Cannot verify authority access control")
    text = w.LPWSTR()
    try:
        if not adv.ConvertSecurityDescriptorToStringSecurityDescriptorW(sd, 1, 4, ctypes.byref(text), None):
            raise PermissionError("Cannot inspect authority access control")
        actual = text.value
        pattern = r"D:((?:P|AI|AR)+)\(A;"+("OICI" if directory else "")+r";FA;;;"+re.escape(_sid())+r"\)"
        matched = re.fullmatch(pattern, actual)
        if not matched or "P" not in matched.group(1):
            redacted = re.sub(r"S-1-\d+(?:-\d+)+", "SID", actual)
            raise PermissionError("Authority access control is not owner-only: "+redacted)
    finally:
        if text:
            kernel.LocalFree(ctypes.cast(text, ctypes.c_void_p))
        kernel.LocalFree(sd)


def restrict(path, directory=False):
    if os.name == "nt":
        _windows_sddl(path, set_private=True, directory=directory)
    else:
        os.chmod(path, 0o700 if directory else 0o600)


def verify_private(path, directory=False):
    if os.name == "nt":
        _windows_sddl(path, directory=directory)
    else:
        info = path.stat()
        if stat.S_IMODE(info.st_mode) & 0o077 or info.st_uid != os.geteuid():
            raise PermissionError("Authority file must belong exclusively to the current owner")


def new_key(campaign):
    parent = safe_path(campaign, ".authority")
    parent.mkdir(parents=True, exist_ok=True)
    safe_path(campaign, ".authority")
    restrict(parent, directory=True)
    identity = secrets.token_hex(16)
    path = safe_path(campaign, ".authority", identity+".key")
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        safe_path(campaign, ".authority", identity+".key")
        restrict(path)  # Restrict the EMPTY file before writing any secret.
        with os.fdopen(descriptor, "wb", closefd=False) as stream:
            stream.write(secrets.token_bytes(32))
            stream.flush()
            os.fsync(stream.fileno())
    finally:
        os.close(descriptor)
    return identity


def key(campaign, identity):
    if type(identity) is not str or re.fullmatch(r"[0-9a-f]{32}", identity) is None:
        raise GateUnavailable("Invalid authority identifier")
    parent = safe_path(campaign, ".authority")
    path = safe_path(campaign, ".authority", identity+".key")
    if not path.is_file():
        raise GateUnavailable("Local authority is missing; explicit deep recovery is required")
    verify_private(parent, directory=True)
    verify_private(path)
    secret = path.read_bytes()
    if len(secret) != 32:
        raise GateUnavailable("Local authority is invalid; explicit deep recovery is required")
    return secret


def sign(campaign, identity, purpose, payload):
    message = canonical(dict(purpose=purpose, payload=payload))
    return dict(key_id=identity, payload=payload,
                mac=hmac.new(key(campaign, identity), message, hashlib.sha256).hexdigest())


def authenticate(campaign, purpose, envelope):
    if type(envelope) is not dict or set(envelope) != {"key_id", "payload", "mac"}:
        raise GateUnavailable("Unsigned or malformed local approval")
    if type(envelope["mac"]) is not str or re.fullmatch(r"[0-9a-f]{64}", envelope["mac"]) is None:
        raise GateUnavailable("Malformed approval signature")
    expected = sign(campaign, envelope["key_id"], purpose, envelope["payload"])["mac"]
    if not hmac.compare_digest(expected, envelope["mac"]):
        raise GateUnavailable("Local approval authentication failed")
    return envelope["payload"]
