"""Restore hash-checked comparison sources for optional benchmark reproduction."""
import hashlib
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    restored = 0
    manifests = [ROOT/"validation/source_archive_manifest.json", ROOT/"validation/official/source_archive_manifest.json"]
    for path in manifests:
        if path.exists():
            restored += restore(path)
    print("Restored %d comparison source files. The final bot and tester files are unchanged." % restored)


def restore(path):
    manifest = json.loads(path.read_text(encoding="utf8"))
    archive = ROOT/manifest["archive"]
    if hashlib.sha256(archive.read_bytes()).hexdigest() != manifest["sha256"]:
        raise ValueError("source archive changed")
    restored = 0
    with zipfile.ZipFile(archive) as z:
        for entry in manifest["files"]:
            relative = Path(entry["path"])
            if not relative.parts or relative.parts[0] != "consolidation_candidates":
                continue
            target = (ROOT/relative).resolve()
            if not target.is_relative_to(ROOT/"consolidation_candidates"):
                raise ValueError("invalid archived source path")
            body = z.read(entry["path"])
            if hashlib.sha256(body).hexdigest() != entry["sha256"]:
                raise ValueError("archived source hash mismatch")
            if target.exists():
                if target.read_bytes() != body:
                    raise ValueError("refusing to replace changed source: " + str(relative))
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(body)
            restored += 1
    return restored


if __name__ == "__main__":
    main()
