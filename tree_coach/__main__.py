"""Run one bounded public tree diagnostic; never overwrite existing evidence."""
import argparse
import hashlib
from pathlib import Path
import time

from compute_share.offline import load_json
from tree_coach.mcts import canonical, recommend


ROOT = Path(__file__).resolve().parents[1]
SOURCES = ("tree_coach/__init__.py", "tree_coach/__main__.py", "tree_coach/mcts.py",
           "search_coach/belief.py", "search_coach/beam.py", "tests/reference_engine.py")


def pins():
    return {name: hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in SOURCES}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Output exists; preserve it and choose a new evidence path")
    sources = pins()
    job = load_json(args.input, limit=4*1024*1024)
    started = time.perf_counter()
    result = recommend(job)
    result["wall_seconds"] = time.perf_counter()-started
    if sources != pins():
        raise ValueError("Source changed during diagnostic; no result accepted")
    result["source_sha256"] = sources
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("xb") as stream:
        stream.write(canonical(result)+b"\n")
    print("Saved public-history tree diagnostic. Primary games:0. Completed per-game BMCTS audits:0.")


if __name__ == "__main__":
    main()
