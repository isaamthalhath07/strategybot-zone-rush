"""Small fixed panel of distinct committed root submissions; never tunes them."""
import hashlib
import itertools
import json
import math
from pathlib import Path
import random
import subprocess
import sys
import time
import types

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import engine

PANEL = {
    "origin/codex-audit-and-robustness": "3e787a9828e83e864f99e2f3241ddf2e3df96e68",
    "origin/hardened-field-and-fixes": "961e729a30736f41f272f3ecc8a2f9e033ca1d57",
    "origin/main": "b75dec072b025b4e28bc21a07b6ab7be83a16a34",
    "origin/research/evolution-2026-11-07": "0796039f42f0113d7c4f51b2f8e1409835f2c519",
    "origin/v7-independent-field": "c7cbaa97e226738934401ad33a8cda12c7c680bc",
    "origin/visual-harness": "6d7b7fd5d8d2e6f82500165c519e145faae02e84",
}


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT)


def sources():
    groups = {}
    for alias, commit in PANEL.items():
        source = git("show", commit + ":bot.py")
        digest = hashlib.sha256(source).hexdigest()
        group = groups.setdefault(digest, {"aliases": [], "source_sha256": digest,
                                           "commits": {}, "source": source})
        group["aliases"].append(alias)
        group["commits"][alias] = commit
    return list(groups.values())


def snapshot(view):
    return (view.bot_id, view.is_priority_token, tuple(view.legal_actions),
            tuple((c.occupant, c.owner, c.is_upgraded, c.is_home, c.is_frozen, c.base_points)
                  for row in view.board for c in row))


def main():
    contestants = sources()
    if len(contestants) != 5:
        raise SystemExit("Expected five distinct root bot.py blobs in the pinned six-branch panel")
    codes = [compile(c["source"], "committed:" + c["aliases"][0] + ":bot.py", "exec") for c in contestants]
    stats = [{"games": 0, "pw": 0, "score": 0, "sole_firsts": 0,
              "timeouts": 0, "exceptions": 0, "illegal": 0, "input_mutations": 0,
              "calls": 0, "max_ms": 0, "total_ms": 0, "map_pw": []} for _ in contestants]
    rnd = random.Random(2026110701)
    map_seeds = [None] + [rnd.randrange(1 << 30) for _ in range(2)]
    lineups = list(itertools.combinations(range(5), 4))
    games = []
    start_run = time.perf_counter()
    for mi, map_seed in enumerate(map_seeds):
        map_pws = [0.0] * 5
        for lineup_index, rotation in itertools.product(range(5), range(4)):
            lineup = lineups[lineup_index]
            assignment = [lineup[(seat + rotation) % 4] for seat in range(4)]
            modules = []
            for seat, ci in enumerate(assignment):
                module = types.ModuleType("screen_policy_%d_%d_%d" % (mi, rotation, seat))
                exec(codes[ci], module.__dict__)
                modules.append(module)
            token = (mi + lineup_index + rotation) % 4 + 1
            g = engine.Game(base=engine.make_map(seed=map_seed, canonical=map_seed is None), start_token=token)
            while not g.over():
                actions = []
                for seat, (ci, module) in enumerate(zip(assignment, modules)):
                    # Rebuild each isolated view from the same unchanged game.
                    # Input mutations cannot alter another player's observation.
                    view = g.views()[seat]
                    before = snapshot(view)
                    started = time.perf_counter()
                    fault = False
                    try:
                        action = module.act(view)
                    except Exception:
                        stats[ci]["exceptions"] += 1
                        action, fault = "STAY", True
                    elapsed = (time.perf_counter() - started) * 1000
                    record = stats[ci]
                    record["calls"] += 1
                    record["total_ms"] += elapsed
                    record["max_ms"] = max(record["max_ms"], elapsed)
                    if elapsed > (2000 if g.turn == 1 else 200):
                        record["timeouts"] += 1
                        action, fault = "STAY", True
                    if snapshot(view) != before:
                        record["input_mutations"] += 1
                        action, fault = "STAY", True
                    if action not in before[2]:
                        record["illegal"] += 1
                        action = "STAY"
                    actions.append(action)
                g.step(actions)
            places = g.places(round_number=1)
            pw = [sum((1.0 if g.score[i] > g.score[j] else
                       0.5 if g.score[i] == g.score[j] else 0.0)
                      for j in range(4) if j != i) for i in range(4)]
            for seat, ci in enumerate(assignment):
                record = stats[ci]
                record["games"] += 1
                record["pw"] += pw[seat]
                record["score"] += g.score[seat]
                record["sole_firsts"] += int(places[seat] == 1)
                map_pws[ci] += pw[seat] / 16
            games.append({"map_seed": map_seed, "lineup_index": lineup_index,
                          "rotation": rotation, "token": token,
                          "contestant_by_seat": assignment, "scores": g.score[:],
                          "places": places, "pw": pw})
        for ci, value in enumerate(map_pws):
            stats[ci]["map_pw"].append(value)
        print("Completed map %d/3 (%d/60 games, %.1fs)" %
              (mi + 1, (mi + 1) * 20, time.perf_counter() - start_run), flush=True)
    for ci, record in enumerate(stats):
        record["mean_pw"] = record["pw"] / record["games"]
        record["mean_score"] = record["score"] / record["games"]
        record["mean_ms"] = record["total_ms"] / record["calls"]
        contestants[ci].pop("source")
        contestants[ci]["results"] = record
    order = sorted(range(5), key=lambda ci: -stats[ci]["mean_pw"])
    first, second = order[:2]
    diffs = [a - b for a, b in zip(stats[first]["map_pw"], stats[second]["map_pw"])]
    gap = sum(diffs) / len(diffs)
    se = math.sqrt(sum((d - gap) ** 2 for d in diffs) / (len(diffs) - 1) / len(diffs))
    result = {
        "scope": "Small fixed panel of five distinct root bot.py blobs across six actual origin branches: five lineups (all combinations of four of five policies) x four cyclic seat rotations x three mirrored maps (canonical plus two fresh seeds), 60 total games. Each policy plays 48 games. No tuning or alternate-file champion search.",
        "rules": "Local corrected engine, Round 1 final-score ties draw; calls over 200ms (2s turn 1), exceptions, illegal output, and input mutations become STAY. Known bounded sources run sequentially; timing rejection is after a call returns, not hard preemption.",
        "seed": 2026110701, "map_seeds": map_seeds, "games": games,
        "contestants": contestants, "descriptive_order": order,
        "top_two_map_paired_gap": {"first": first, "second": second, "mean_pw_gap": gap,
                                    "map_cluster_standard_error": se, "map_clusters": 3},
        "elapsed_s": time.perf_counter() - start_run,
        "caveat": "Descriptive screen, not proof of an all-branch champion. Cyclic rotations balance seats but are not all 24 permutations. Opponents are this five-policy panel. Only three map clusters make uncertainty estimates particularly weak; this cannot establish a general ranking or justify tuning.",
    }
    output = Path(__file__).with_name("branch_screen.json")
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf8")
    for ci in order:
        record = stats[ci]
        print("%s: %.3f PW/3, %.1f score, %.3fms max, faults %d" %
              (" / ".join(contestants[ci]["aliases"]), record["mean_pw"], record["mean_score"],
               record["max_ms"], sum(record[k] for k in ("exceptions", "timeouts", "illegal", "input_mutations"))))
    print("Top gap %.4f +/- %.4f map-cluster SE" % (gap, se))
    print("Saved", output)


if __name__ == "__main__":
    main()
