"""Deterministic offline work allocation and structural result inventory.

This module does not execute games or certify result claims. Submitted games are
not credited until a separate trusted referee/replay validator is connected.
"""

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re

try:
    from .doctor import atomic_json
except ImportError:
    from doctor import atomic_json


HEX = re.compile(r"[0-9a-f]{64}\Z")
PLAN_SCHEMA = "zone-rush-offline-plan-v1"
RESULT_SCHEMA = "zone-rush-offline-result-v1"


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def integer(value, low, high, label):
    if type(value) is not int or not low <= value <= high:
        raise ValueError(f"Invalid {label}")
    return value


def sha(value):
    if not isinstance(value, str) or HEX.fullmatch(value) is None:
        raise ValueError("Expected lowercase SHA-256")
    return value


def portable_path(value):
    if not isinstance(value, str) or "\\" in value or ":" in value:
        raise ValueError("Input paths must be portable relative paths")
    path = PurePosixPath(value)
    if not value or path.is_absolute() or any(part in ("", ".", "..") for part in value.split("/")):
        raise ValueError("Input paths must stay inside the bundle")
    return value


def file_hashes(root, paths):
    root = Path(root).resolve()
    result = {}
    for relative in paths:
        portable_path(relative)
        target = (root / relative).resolve()
        if not target.is_relative_to(root) or not target.is_file():
            raise ValueError(f"Input is not a regular file inside the bundle: {relative}")
        result[relative] = hashlib.sha256(target.read_bytes()).hexdigest()
    return result


def task_id(campaign_id, map_index, start, end):
    return digest([campaign_id, map_index, start, end])


def map_seed(campaign_id, index):
    # String storage preserves all 64 bits in JavaScript/JSON consumers.
    return digest([campaign_id, "map", index])[:16]


def opponents(campaign_id, map_index, episode, focal_seat):
    return [digest([campaign_id, "opponent-instance", map_index, episode, seat])
            for seat in range(4) if seat != focal_seat]


def seating(map_index, episode):
    seat = episode % 4
    return seat, ((episode // 4) + seat + map_index) % 4


def make_plan(inputs, policy_path, evaluator_path, *, maps=10000, games_per_map=200,
              episodes_per_task=25, campaign_seed=0):
    integer(maps, 1, 100000, "map count")
    integer(games_per_map, 1, 10000, "games per map")
    integer(episodes_per_task, 1, games_per_map, "task size")
    integer(campaign_seed, 0, 2**63 - 1, "campaign seed")
    if maps * ((games_per_map + episodes_per_task - 1) // episodes_per_task) > 1000000:
        raise ValueError("Plan exceeds one million tasks")
    if not isinstance(inputs, dict) or not inputs:
        raise ValueError("Pinned input files are required")
    inputs = dict(sorted((portable_path(path), sha(value)) for path, value in inputs.items()))
    if policy_path not in inputs or evaluator_path not in inputs:
        raise ValueError("Policy and evaluator must both be pinned")
    specification = {
        "schema": PLAN_SCHEMA, "campaign_seed": campaign_seed,
        "maps": maps, "games_per_map": games_per_map,
        "episodes_per_task": episodes_per_task, "inputs": inputs,
        "policy_path": policy_path, "evaluator_path": evaluator_path,
        "status": "schedule_only_not_validated_for_execution",
        "map_generation": "requires_rule_validated_generator_and_unique_board_catalog",
        "opponents": "three_unique_instance_ids_per_game; controllers_not_yet_generated",
        "search": "requires_public_history_only_BMCTS_adapter",
    }
    campaign_id = digest(specification)
    tasks = []
    for index in range(maps):
        for start in range(0, games_per_map, episodes_per_task):
            end = min(start + episodes_per_task, games_per_map)
            tasks.append({"id": task_id(campaign_id, index, start, end), "map_index": index,
                          "map_seed_hex": map_seed(campaign_id, index),
                          "episode_start": start, "episode_end": end, "games": end - start})
    plan = {**specification, "campaign_id": campaign_id,
            "total_games": maps * games_per_map, "tasks": tasks}
    plan["manifest_sha256"] = digest(plan)
    return plan


def validate_plan(plan):
    if not isinstance(plan, dict):
        raise ValueError("Plan must be an object")
    try:
        expected = make_plan(plan["inputs"], plan["policy_path"], plan["evaluator_path"],
                             maps=plan["maps"], games_per_map=plan["games_per_map"],
                             episodes_per_task=plan["episodes_per_task"],
                             campaign_seed=plan["campaign_seed"])
    except (KeyError, TypeError) as exc:
        raise ValueError("Invalid plan structure") from exc
    if canonical(plan) != canonical(expected):
        raise ValueError("Manifest was altered or tasks do not cover the campaign exactly")
    return plan


def partition(plan, workers):
    validate_plan(plan)
    integer(workers, 1, 1000, "worker count")
    allocations = [{"schema": "zone-rush-offline-allocation-v1", "campaign_id": plan["campaign_id"],
                    "manifest_sha256": plan["manifest_sha256"], "worker_slot": i,
                    "tasks": [], "scheduled_games": 0} for i in range(workers)]
    for index, task in enumerate(plan["tasks"]):
        item = allocations[index % workers]
        item["tasks"].append(task["id"])
        item["scheduled_games"] += task["games"]
    return allocations


def inventory(plan, results):
    """Reject malformed/duplicate claims; report ZERO verified games by design."""
    validate_plan(plan)
    known = {task["id"]: task for task in plan["tasks"]}
    seen = set()
    claimed_games = claimed_audits = 0
    artifacts = []
    fields = {"schema", "campaign_id", "manifest_sha256", "task_id", "policy_sha256",
              "evaluator_sha256", "games"}
    game_fields = {"episode", "completed", "turns", "transcript_sha256", "bmcts_audited",
                   "planner_seed", "opponent_ids"}
    for result in results:
        if not isinstance(result, dict) or set(result) != fields:
            raise ValueError("Invalid result structure")
        if (result["schema"] != RESULT_SCHEMA or result["campaign_id"] != plan["campaign_id"]
                or result["manifest_sha256"] != plan["manifest_sha256"]):
            raise ValueError("Result belongs to another campaign or manifest")
        identity = result["task_id"]
        if not isinstance(identity, str) or identity not in known or identity in seen:
            raise ValueError("Unknown or duplicate task result")
        if (result["policy_sha256"] != plan["inputs"][plan["policy_path"]]
                or result["evaluator_sha256"] != plan["inputs"][plan["evaluator_path"]]):
            raise ValueError("Result source hashes do not match the plan")
        task = known[identity]
        games = result["games"]
        if not isinstance(games, list) or len(games) != task["games"]:
            raise ValueError("Result omits or adds episodes")
        for episode, game in zip(range(task["episode_start"], task["episode_end"]), games):
            if not isinstance(game, dict) or set(game) != game_fields:
                raise ValueError("Invalid game result structure")
            if type(game["episode"]) is not int or game["episode"] != episode or game["completed"] is not True:
                raise ValueError("Episode order/completion does not match its task")
            integer(game["turns"], 1, 80, "turn count")
            integer(game["planner_seed"], 0, 2**63 - 1, "planner seed")
            sha(game["transcript_sha256"])
            if type(game["bmcts_audited"]) is not bool:
                raise ValueError("BMCTS audit flag must be Boolean")
            seat, _ = seating(task["map_index"], episode)
            expected_opponents = opponents(plan["campaign_id"], task["map_index"], episode, seat)
            if game["opponent_ids"] != expected_opponents:
                raise ValueError("Opponent instance IDs do not match this game")
            claimed_audits += int(game["bmcts_audited"])
        claimed_games += len(games)
        artifacts.append({"task_id": identity, "result_sha256": digest(result)})
        seen.add(identity)
    return {"schema": "zone-rush-offline-inventory-v1", "campaign_id": plan["campaign_id"],
            "manifest_sha256": plan["manifest_sha256"], "scheduled_games": plan["total_games"],
            "structurally_accepted_tasks": len(seen), "claimed_completed_games": claimed_games,
            "claimed_bmcts_audits": claimed_audits,
            "verified_games": 0, "verified_bmcts_audits": 0,
            "missing_tasks": len(known) - len(seen), "artifacts": artifacts,
            "note": "Claims require trusted referee replay, source validation and public-input audit before credit."}


def load_json(path, limit=64 * 1024 * 1024):
    path = Path(path)
    if path.stat().st_size > limit:
        raise ValueError("JSON file exceeds size limit")
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("Duplicate JSON key")
            result[key] = value
        return result
    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique,
                      parse_constant=lambda value: (_ for _ in ()).throw(ValueError("Non-finite JSON number")))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    create = commands.add_parser("plan", help="Create a schedule only; does not run games")
    create.add_argument("--root", required=True)
    create.add_argument("--pin", action="append", default=[])
    create.add_argument("--policy", required=True)
    create.add_argument("--evaluator", required=True)
    create.add_argument("--maps", type=int, default=10000)
    create.add_argument("--games-per-map", type=int, default=200)
    create.add_argument("--episodes-per-task", type=int, default=25)
    create.add_argument("--seed", type=int, default=0)
    create.add_argument("--workers", type=int, default=6)
    create.add_argument("--output", required=True)
    inspect = commands.add_parser("inspect", help="Check schedule integrity and optional input files")
    inspect.add_argument("manifest")
    inspect.add_argument("--root")
    collect = commands.add_parser("inventory", help="Validate result claims; no completed-game credit")
    collect.add_argument("manifest")
    collect.add_argument("results", nargs="+")
    collect.add_argument("--output", required=True)
    args = parser.parse_args()
    if args.command == "plan":
        paths = list(dict.fromkeys(args.pin + [args.policy, args.evaluator]))
        plan = make_plan(file_hashes(args.root, paths), args.policy, args.evaluator,
                         maps=args.maps, games_per_map=args.games_per_map,
                         episodes_per_task=args.episodes_per_task, campaign_seed=args.seed)
        allocations = partition(plan, args.workers)
        output = Path(args.output)
        output.mkdir(parents=True, exist_ok=True)
        if any(output.glob("*.json")):
            raise ValueError("Output folder already contains JSON; choose a new campaign folder")
        atomic_json(output / "manifest.json", plan)
        for item in allocations:
            atomic_json(output / f"worker-{item['worker_slot']:03d}.json", item)
        print(f"Scheduled {plan['total_games']} games in {len(plan['tasks'])} tasks; no games executed.")
    elif args.command == "inspect":
        plan = validate_plan(load_json(args.manifest))
        if args.root and file_hashes(args.root, plan["inputs"]) != plan["inputs"]:
            raise ValueError("Bundle input files do not match pinned hashes")
        print(f"Schedule valid: {plan['total_games']} games; execution adapter still required.")
    else:
        result = inventory(load_json(args.manifest), [load_json(path) for path in args.results])
        atomic_json(args.output, result)
        print(f"Accepted {result['structurally_accepted_tasks']} result claims; 0 verified games credited.")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, KeyError) as exc:
        raise SystemExit(f"Error: {exc}")
