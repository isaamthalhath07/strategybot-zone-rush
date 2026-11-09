"""Freeze the mathematical experiment and its replayable diagnostic inputs."""
import hashlib
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent


def main():
    registration_path = ROOT/".cache/evolution/confirmation_001/registration.json"
    registration = json.loads(registration_path.read_text())
    root_sha = hashlib.sha256((ROOT/"bot.py").read_bytes()).hexdigest()
    records = [json.loads(line) for line in (registration_path.parent/"games.jsonl").read_text().splitlines()]
    records = sorted((r for r in records if r["candidate"] == root_sha), key=lambda r: r["fixture"])
    sampled = [records[i*len(records)//32] for i in range(32)]
    replay = HERE/"replay_fixture"
    replay.mkdir(exist_ok=True)
    (replay/"registration.json").write_bytes(registration_path.read_bytes())
    (replay/"registration.sha256").write_bytes(registration_path.with_name("registration.sha256").read_bytes())
    (replay/"games.jsonl").write_text("".join(json.dumps(r, sort_keys=True, separators=(",", ":"))+"\n" for r in sampled),
                                     encoding="utf8", newline="\n")
    relative = ["bot.py", "tests/__init__.py", "tests/reference_engine.py", "evolution/__init__.py",
                "evolution/genomes.py", "evolution/maps.py", "evolution/opponents.py", "evolution/runner.py",
                "evolution/GAME_THEORY_REVIEW.md", "evolution/mathematical_probes.py",
                "simulator/vendor_harness/referee.py"]
    files = [ROOT/path for path in relative]
    files.extend(path for path in HERE.iterdir() if path.is_file() and path.suffix in (".py", ".json", ".txt"))
    files.extend(replay.iterdir())
    archive = HERE/"source_archive.zip"
    entries = []
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as output:
        for path in sorted(set(files)):
            if path.name == "source_archive_manifest.json":
                continue
            body = path.read_bytes()
            name = path.relative_to(ROOT).as_posix()
            entry = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            entry.compress_type = zipfile.ZIP_DEFLATED
            output.writestr(entry, body)
            entries.append(dict(path=name, sha256=hashlib.sha256(body).hexdigest(), bytes=len(body)))
    manifest = dict(format="zone-rush-mathematical-source-archive/1", parent_sha256=root_sha,
                    archive=archive.relative_to(ROOT).as_posix(), sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),
                    files=entries, source_registration_sha256=hashlib.sha256(registration_path.read_bytes()).hexdigest(),
                    replay_subset_games=32, source_files_frozen=True, production_changed=False)
    (HERE/"source_archive_manifest.json").write_text(json.dumps(manifest, indent=2)+"\n", encoding="utf8", newline="\n")
    print(json.dumps({"archive": manifest["archive"], "sha256": manifest["sha256"], "files": len(entries)}))


if __name__ == "__main__":
    main()
