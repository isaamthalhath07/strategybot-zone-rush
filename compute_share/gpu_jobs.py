"""Offline GPU diagnostic bundles with source pins and independent return checks.

This transport never accepts executable commands in a job or counts rollouts as
primary games. The numerical worker receives public prefixes only.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import zipfile

from compute_share.doctor import atomic_json
from compute_share.offline import canonical, load_json, portable_path

ROOT = Path(__file__).resolve().parents[1]
FORMAT = "zone-rush-public-gpu-bundle/1"
FILES = (
    "compute_share/__init__.py", "compute_share/doctor.py", "compute_share/verify_cuda.py",
    "compute_share/offline.py", "compute_share/gpu_jobs.py", "compute_share/requirements-gpu.txt",
    "compute_share/setup_gpu.cmd", "compute_share/DEPENDENCIES.md",
    "search_coach/__init__.py", "search_coach/belief.py", "search_coach/beam.py",
    "search_coach/gpu_batch.py", "training_gpu/__init__.py", "training_gpu/batch_game.py",
    "tests/__init__.py", "tests/reference_engine.py",
)


def sha(body):
    return hashlib.sha256(body).hexdigest()


def validate_public_job(payload):
    from search_coach.belief import PublicBelief, PublicObservation
    if payload.get("kind") == "public_history_gpu_coach":
        jobs = [payload]
    elif set(payload) == {"schema", "kind", "jobs"} and payload["schema"] == 1 and payload["kind"] == "public_history_gpu_coach_batch":
        jobs = payload["jobs"]
    else:
        raise ValueError("Unsupported public diagnostic payload")
    if type(jobs) is not list or not 1 <= len(jobs) <= 64:
        raise ValueError("Expected one to64 public-prefix jobs")
    identities = set()
    fields = {"schema", "kind", "job_id", "initial_observation", "transitions", "search"}
    for job in jobs:
        if set(job) != fields or job["schema"] != 1 or job["kind"] != "public_history_gpu_coach":
            raise ValueError("Jobs must contain only public prefixes and search settings")
        if type(job["job_id"]) is not str or not 1 <= len(job["job_id"]) <= 128 or job["job_id"] in identities:
            raise ValueError("Duplicate/invalid diagnostic identity")
        identities.add(job["job_id"])
        if type(job["transitions"]) is not list or len(job["transitions"]) > 79:
            raise ValueError("Invalid prefix length")
        limits = {"seed": (0, 2147483646), "horizon": (1, 6), "plans_per_root": (1, 32),
                  "rollouts_per_plan": (1, 256), "support_cap": (1, 1024), "income_tail": (0, 80)}
        search = job["search"]
        if type(search) is not dict or not set(search) <= set(limits):
            raise ValueError("Unsupported search configuration")
        for name, value in search.items():
            lo, hi = limits[name]
            if type(value) is not int or not lo <= value <= hi:
                raise ValueError("Search option is outside worker limits: " + name)
        cap = search.get("support_cap", 512)
        belief = PublicBelief(job["initial_observation"], cap=cap)
        for transition in job["transitions"]:
            if set(transition) != {"own_action", "observation"}:
                raise ValueError("A prefix cannot contain joint actions or private counters")
            belief.advance(transition["own_action"], PublicObservation.from_view(transition["observation"]))
    return jobs


def prepare(payload, output):
    validate_public_job(payload)
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    for relative in FILES:
        source, destination = ROOT/relative, output/relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
    (output/"job.json").write_bytes(canonical(payload)+b"\n")
    launcher = ('@echo off\r\nsetlocal\r\ncd /d "%~dp0"\r\n'
                'if not exist "compute_share\\.venv-worker\\Scripts\\python.exe" goto missing\r\n'
                '"compute_share\\.venv-worker\\Scripts\\python.exe" -m compute_share.gpu_jobs run --root . --device cuda\r\n'
                'if errorlevel 1 goto failed\r\necho Return result.json to the owner.\r\npause\r\nexit /b 0\r\n'
                ':missing\r\necho First run setup_gpu.cmd inside the compute_share folder.\r\npause\r\nexit /b 1\r\n'
                ':failed\r\necho Job failed. Keep this window for review. No primary games were credited.\r\npause\r\nexit /b 1\r\n')
    (output/"run_gpu_job.cmd").write_bytes(launcher.encode("ascii"))
    readme = ("WINDOWS OFFLINE GPU DIAGNOSTIC\n\n"
              "1. Install 64-bit Python3.12 if needed.\n"
              "2. Open compute_share, double-click setup_gpu.cmd.\n"
              "3. Return here, double-click run_gpu_job.cmd.\n"
              "4. Return result.json and compute_share/hardware.json to the owner.\n\n"
              "This is a real GPU search diagnostic using public observations only.\n"
              "It is not a primary campaign game, a complete BMCTS or an optimality proof.\n"
              "No ports, accounts, Git, Docker or full CUDA toolkit are required.\n"
              "Keep this job within the participating team's control.\n")
    (output/"START_HERE.txt").write_text(readme, encoding="utf8")
    files = {relative: sha((output/relative).read_bytes()) for relative in (*FILES, "job.json", "run_gpu_job.cmd", "START_HERE.txt")}
    manifest = dict(format=FORMAT, files=files, input_sha256=sha(canonical(payload)),
                    primary_campaign_games=0, full_bmcts=False, transport="offline_files")
    manifest["bundle_id"] = sha(canonical(manifest))
    atomic_json(output/"manifest.json", manifest)
    archive = output.with_suffix(".zip")
    if archive.exists():
        raise ValueError("Bundle archive already exists")
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for relative in (*files, "manifest.json"):
            z.write(output/relative, relative)
    return archive


def verify_bundle(root):
    root = Path(root).resolve()
    manifest = load_json(root/"manifest.json")
    if manifest["format"] != FORMAT:
        raise ValueError("Unsupported bundle")
    unsigned = {key: value for key, value in manifest.items() if key != "bundle_id"}
    if sha(canonical(unsigned)) != manifest["bundle_id"]:
        raise ValueError("Bundle identity changed")
    for relative, expected in manifest["files"].items():
        portable_path(relative)
        path = (root/relative).resolve()
        if not path.is_relative_to(root) or sha(path.read_bytes()) != expected:
            raise ValueError("Bundle source/data hash mismatch: " + relative)
    payload = load_json(root/"job.json")
    if sha(canonical(payload)) != manifest["input_sha256"]:
        raise ValueError("Job fingerprint changed")
    jobs = validate_public_job(payload)
    return manifest, payload, jobs


def run(root, device="cuda", chunk=8192):
    root = Path(root).resolve()
    if root != ROOT:
        raise ValueError("Run this command from inside the extracted bundle so its pinned code is used")
    manifest, payload, jobs = verify_bundle(root)
    if (root/"result.json").exists():
        raise ValueError("A result already exists; return it before retrying in a new copy")
    if type(chunk) is not int or not 1 <= chunk <= 8192:
        raise ValueError("Chunk size must be1..8192")
    from search_coach.gpu_batch import run_batch
    result = run_batch(jobs, device=device, max_trajectories=chunk, verify_all=True)
    verify_bundle(root)
    envelope = dict(format=FORMAT+"/result", bundle_id=manifest["bundle_id"],
                    input_sha256=manifest["input_sha256"], max_trajectories=chunk, result=result,
                    primary_campaign_games=0, games_bmcts_audited=0)
    atomic_json(root/"result.json", envelope)
    print("Completed public-only diagnostic and independent CPU trajectory checks. Primary games:0.")
    return envelope


def receive(root, result_path):
    """Recompute returned numerical values locally; claims alone grant no credit."""
    root = Path(root).resolve()
    manifest, payload, jobs = verify_bundle(root)
    envelope = load_json(result_path, limit=128*1024*1024)
    if (envelope.get("format") != FORMAT+"/result" or envelope.get("bundle_id") != manifest["bundle_id"]
            or envelope.get("input_sha256") != manifest["input_sha256"]
            or envelope.get("primary_campaign_games") != 0 or envelope.get("games_bmcts_audited") != 0):
        raise ValueError("Returned result belongs to a different job or claims invalid credit")
    chunk = envelope["max_trajectories"]
    if type(chunk) is not int or not 1 <= chunk <= 8192:
        raise ValueError("Invalid returned chunk size")
    for relative in FILES:
        if relative.endswith('.py') and sha((ROOT/relative).read_bytes()) != manifest['files'][relative]:
            raise ValueError("Local verifier differs from the pinned bundle; use the original bundle version")
    from search_coach.gpu_batch import run_batch
    replay = run_batch(jobs, device="cpu", max_trajectories=chunk, verify_all=True)
    returned = envelope["result"]
    for field in ("jobs", "source_sha256", "synthetic_trajectories", "synthetic_game_turns",
                  "independent_cpu_verified", "independent_cpu_turn_checks", "trace_sha256",
                  "primary_campaign_games", "full_bmcts", "deployed_policy_changed"):
        if returned.get(field) != replay[field]:
            raise ValueError("Returned diagnostic does not independently reproduce: " + field)
    proof = dict(bundle_id=manifest["bundle_id"], result_sha256=sha(Path(result_path).read_bytes()),
                 diagnostics_verified=len(jobs), source_pins_passed=True,
                 independent_cpu_reproduction=True, primary_campaign_games=0,
                 games_bmcts_audited=0, promotion_allowed=False)
    path = root/"return_verified.json"
    if path.exists() and load_json(path) != proof:
        raise ValueError("This job already has a different accepted return")
    atomic_json(path, proof)
    return proof


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    prepare_parser = commands.add_parser("prepare")
    prepare_parser.add_argument("job", type=Path)
    prepare_parser.add_argument("output", type=Path)
    for name in ("run", "receive"):
        sub = commands.add_parser(name)
        sub.add_argument("--root", type=Path, required=True)
        if name == "run":
            sub.add_argument("--device", choices=("cpu", "cuda"), default="cuda")
            sub.add_argument("--chunk", type=int, default=8192)
        else:
            sub.add_argument("result", type=Path)
    args = parser.parse_args()
    if args.command == "prepare":
        print(prepare(load_json(args.job), args.output))
    elif args.command == "run":
        run(args.root, args.device, args.chunk)
    else:
        print(json.dumps(receive(args.root, args.result), indent=2))


if __name__ == "__main__":
    main()
