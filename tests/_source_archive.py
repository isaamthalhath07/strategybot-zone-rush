"""Load an exact historical policy for evidence tests, never for live selection."""
from functools import lru_cache
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]


@lru_cache(maxsize=8)
def archived_bytes(path):
    manifest = json.loads((ROOT/"validation/source_archive_manifest.json").read_text())
    archive = ROOT/manifest["archive"]
    if hashlib.sha256(archive.read_bytes()).hexdigest() != manifest["sha256"]:
        raise ValueError("historical source archive changed")
    entry = next(entry for entry in manifest["files"] if entry["path"] == path)
    with zipfile.ZipFile(archive) as z:
        body = z.read(path)
    if hashlib.sha256(body).hexdigest() != entry["sha256"]:
        raise ValueError("historical source changed")
    return body


def load_archived(path):
    directory = ROOT/".cache/test_sources"
    directory.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=directory) as temp:
        target = Path(temp)/"bot.py"
        target.write_bytes(archived_bytes(path))
        spec = importlib.util.spec_from_file_location("archived_policy", target)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
