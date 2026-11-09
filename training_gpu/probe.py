"""Reproducible CPU/CUDA physics parity and throughput measurements.

Run from the repository root with the desired PyTorch environment:
    python -m training_gpu.probe --device cuda --output training_gpu/probe_cuda.json
The timed work is synthetic action replay, not real bot games or BMCTS audits.
"""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import random
import time

import torch

from tests import reference_engine as ref
from .batch_game import BatchGame


FIELDS = ("base", "owner", "upg", "home", "pos", "frozen", "cd", "prog",
          "score", "income", "token")
ACT = {a: i for i, a in enumerate(ref.ACTIONS)}
RULESETS = (
    ("official_stay", {}),
    ("frozen_stay_counts", {"frozen_stay_counts": True}),
    ("no_claim_reset", {"claim_resets_progress": False}),
    ("historic_presence", {"catch_requires_stay": False}),
    ("no_home_upgrade", {"home_upgradable": False}),
    ("lost_contest_not_stay", {"lost_contest_is_stay": False}),
)


def sync(device):
    if str(device).startswith("cuda"):
        torch.cuda.synchronize()


def tensor_state(games, device):
    batch = BatchGame([g.base for g in games], n=len(games), device=device,
                      start_token=torch.tensor([g.token for g in games]),
                      rules=games[0].rules)
    for field in FIELDS:
        old = getattr(batch, field)
        value = torch.tensor([getattr(g, field) for g in games],
                             dtype=old.dtype, device=device)
        old.copy_(value)
    return batch


def compare(batch, games, context):
    for field in FIELDS:
        actual = getattr(batch, field).cpu().tolist()
        expected = [getattr(g, field) for g in games]
        if actual != expected:
            index = next(i for i, (a, e) in enumerate(zip(actual, expected)) if a != e)
            raise AssertionError(f"{context}: {field} game {index}: "
                                 f"tensor={actual[index]} reference={expected[index]}")
    if any(batch.turn != g.turn for g in games):
        raise AssertionError(f"{context}: turn mismatch")
    mask = batch.legal_mask().cpu().tolist()
    for k, g in enumerate(games):
        expected = [[a in g.legal(i) for a in ref.ACTIONS] for i in range(4)]
        if mask[k] != expected:
            raise AssertionError(f"{context}: legal_mask game {k}")
    for round_number in (1, 2):
        actual = batch.places(round_number).cpu().tolist()
        expected = [g.places(round_number) for g in games]
        if actual != expected:
            raise AssertionError(f"{context}: places round {round_number}")
    ranks = [4, 1, 3, 2]
    if batch.places(2, ranks).cpu().tolist() != [g.places(2, ranks) for g in games]:
        raise AssertionError(f"{context}: knockout tiebreak")


def random_state(rnd, seed, rules):
    g = ref.Game(base=ref.make_map(seed=seed), rules=rules, start_token=rnd.randint(1, 4))
    g.owner = [rnd.randint(0, 4) for _ in range(64)]
    for seat, p in ref.CORNERS.items():
        g.owner[p] = seat
    g.upg = [rnd.randint(0, 1) if owner else 0 for owner in g.owner]
    g.pos = rnd.sample(range(64), 4)
    g.frozen = [rnd.randrange(3) if rnd.random() < .25 else 0 for _ in range(4)]
    g.cd = [rnd.randrange(5) for _ in range(4)]
    g.prog = [rnd.randrange(3) for _ in range(4)]
    g.score = [rnd.randrange(100) for _ in range(4)]
    g.income = [sum(g.base[p] * (1 + g.upg[p]) for p in range(64)
                    if g.owner[p] == seat) for seat in range(1, 5)]
    return g


def targeted(device):
    cases = []

    def add(name, positions, owner, actions, *, expected_frozen=None, token=1):
        g = ref.Game(start_token=token)
        g.pos = list(positions)
        for p, seat in owner.items():
            g.owner[p] = seat
        g.income = [sum(g.base[p] for p in range(64) if g.owner[p] == seat)
                    for seat in range(1, 5)]
        b = tensor_state([g], device)
        g.step(actions)
        b.step(torch.tensor([[ACT.get(a, 17) for a in actions]], device=device))
        compare(b, [g], name)
        if expected_frozen is not None and g.frozen != expected_frozen:
            raise AssertionError(f"{name}: independent rule contract expected {expected_frozen}")
        cases.append(name)
        return g, b

    add("owned_to_owned_escape", [0, 27, 63, 56], {27: 1, 26: 1},
        ["SHIELD", "WEST", "STAY", "STAY"], expected_frozen=[2, 0, 0, 0])
    add("blocked_move_is_caught", [0, 27, 26, 56], {27: 1, 26: 1},
        ["SHIELD", "WEST", "NORTH", "STAY"], expected_frozen=[0, 2, 0, 0])
    add("contest_loser_is_caught", [0, 27, 25, 56], {27: 1, 26: 3},
        ["SHIELD", "WEST", "EAST", "STAY"], expected_frozen=[0, 2, 0, 0])
    add("mutual_shields_backfire", [18, 27, 63, 56], {18: 2, 27: 1},
        ["SHIELD", "SHIELD", "STAY", "STAY"], expected_frozen=[2, 2, 0, 0])
    g, b = add("shield_catch_and_timing", [0, 27, 63, 56], {27: 1},
               ["SHIELD", "STAY", "STAY", "STAY"], expected_frozen=[0, 2, 0, 0])
    if g.cd[0] != 4:
        raise AssertionError("cast must leave 4 cooldown turns")
    expected = [(1, 3), (0, 2), (0, 1), (0, 0)]
    for turn, (frozen, cd) in enumerate(expected, 1):
        actions = ["STAY"] * 4
        g.step(actions)
        b.step(torch.tensor([[4] * 4], device=device))
        compare(b, [g], f"cooldown_step_{turn}")
        if (g.frozen[1], g.cd[0]) != (frozen, cd):
            raise AssertionError("freeze/cooldown timing contract")
    add("unknown_action_becomes_stay", [0, 7, 63, 56], {},
        ["UNKNOWN"] * 4)
    # Deliberately force a three/four-way tie: old averaging gave unequal ranks.
    tie = ref.Game()
    bt = tensor_state([tie], device)
    compare(bt, [tie], "four_way_tie")
    tie.score = [7, 7, 7, 1]
    bt.score.copy_(torch.tensor([tie.score], device=device))
    compare(bt, [tie], "three_way_tie")
    return cases + ["four_way_tie", "three_way_tie"]


def parity(device, n, turns):
    records = []
    for rule_name, rules in RULESETS:
        for state_kind in ("reachable_start", "diverse_state"):
            rnd = random.Random(981742)
            games = [ref.Game(base=ref.make_map(seed=i + 40091), rules=rules,
                              start_token=i % 4 + 1) if state_kind == "reachable_start"
                     else random_state(rnd, i + 40091, rules) for i in range(n)]
            batch = tensor_state(games, device)
            compare(batch, games, "initial")
            catches = backfires = ownership_changes = 0
            for turn in range(turns):
                strings = []
                for g in games:
                    row = [rnd.choice(g.legal(i)) if rnd.random() < .85
                           else rnd.choice(ref.ACTIONS) for i in range(4)]
                    strings.append(row)
                codes = torch.tensor([[ACT[a] for a in row] for row in strings], device=device)
                for g, actions in zip(games, strings):
                    previous_frozen = list(g.frozen)
                    previous_owner = list(g.owner)
                    effective = g.step(actions)
                    for i in range(4):
                        if g.frozen[i] == 2 and previous_frozen[i] == 0:
                            backfires += int(effective[i] == "SHIELD")
                            catches += int(effective[i] != "SHIELD")
                    ownership_changes += sum(a != b for a, b in zip(previous_owner, g.owner))
                batch.step(codes)
                compare(batch, games, f"{rule_name}/{state_kind}/turn{turn+1}")
            records.append({"rules": rule_name, "state_kind": state_kind,
                            "games": n, "turns": turns,
                            "state_comparisons": n * (turns + 1),
                            "new_catches": catches, "backfires": backfires,
                            "ownership_changes": ownership_changes})
    return records


def throughput(device, batch_sizes, turns, repeats):
    records = []
    generator = torch.Generator(device=device).manual_seed(40491)
    for n in batch_sizes:
        base = ref.make_map(canonical=True)
        actions = torch.randint(6, (turns, n, 4), generator=generator, device=device)
        warm = BatchGame(base, n=n, device=device)
        for k in range(min(turns, 8)):
            warm.step(actions[k])
        sync(device)
        durations = []
        for _ in range(repeats):
            batch = BatchGame(base, n=n, device=device)
            sync(device)
            started = time.perf_counter()
            for k in range(turns):
                batch.step(actions[k])
            sync(device)
            durations.append(time.perf_counter() - started)
        duration = min(durations)
        records.append({"batch_games": n, "turns_per_game": turns,
                        "elapsed_seconds_all_repeats": durations,
                        "best_seconds": duration,
                        "synthetic_full_games_per_second": n / duration,
                        "game_turns_per_second": n * turns / duration,
                        "peak_torch_allocated_bytes": torch.cuda.max_memory_allocated()
                        if str(device).startswith("cuda") else None,
                        "includes_real_bot_decisions": False,
                        "includes_bmcts": False,
                        "actions": "prebuilt uniform random codes, normalized by physics"})
    return records


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cpu")
    parser.add_argument("--games", type=int, default=32)
    parser.add_argument("--turns", type=int, default=80)
    parser.add_argument("--batches", type=int, nargs="+", default=[64, 1024, 8192])
    parser.add_argument("--repeats", type=int, default=2)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.games < 1 or not 1 <= args.turns <= 80 or args.repeats < 1:
        parser.error("positive games/repeats and 1..80 turns required")
    if any(not 1 <= n <= 32768 for n in args.batches):
        parser.error("batch size must be 1..32768 to bound memory")
    torch.set_num_threads(1)
    hardware = {"platform": platform.platform(), "python": platform.python_version(),
                "torch": torch.__version__, "torch_cuda": torch.version.cuda,
                "device": args.device}
    if args.device == "cuda":
        # Device detection alone is not a kernel compatibility check.
        if torch.ones(16, device="cuda").sum().item() != 16:
            raise AssertionError("CUDA smoke kernel failed")
        hardware.update({"gpu": torch.cuda.get_device_name(),
                         "capability": list(torch.cuda.get_device_capability()),
                         "compiled_arches": torch.cuda.get_arch_list()})
    result = {"schema": 1, "kind": "offline_physics_parity_and_throughput",
              "not_primary_campaign_games": True,
              "hardware": hardware,
              "source_sha256": {str(p): hashlib.sha256(p.read_bytes()).hexdigest()
                                for p in (Path(__file__), Path(__file__).with_name("batch_game.py"),
                                          Path(ref.__file__))},
              "targeted_cases": targeted(args.device),
              "parity": parity(args.device, args.games, args.turns)}
    print("Full private-state, legal-mask and placement parity passed", flush=True)
    result["throughput"] = throughput(args.device, args.batches, args.turns, args.repeats)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(args.output.suffix + ".tmp")
    temporary.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    temporary.replace(args.output)
    for row in result["throughput"]:
        print(f"batch={row['batch_games']}: {row['synthetic_full_games_per_second']:.2f} "
              "synthetic 80-turn games/s (no bot decisions/BMCTS)", flush=True)
    print(f"Saved {args.output}", flush=True)


if __name__ == "__main__":
    main()
