"""Describe baseline territory choices; not another selection or tuning round."""
import argparse
import json
from pathlib import Path

from baselines import v8 as bot
import engine
from botlib import NEIGH
from territorylab import evaluate, opponents
from territorylab.model import depth


def observe(task):
    seat = task["seat"]
    focal = bot.Agent(seed=task["map_seed"], params={"throttle": 0, "budget_ms": 10000, "first_turn_ms": 0})
    others = iter(opponents.SpatialOpponent(s) for s in task["specs"])
    bots = [focal if j == seat else next(others) for j in range(4)]
    game = engine.Game(base=task["base"], start_token=task["token"])
    claims = [0, 0, 0]
    values = [0, 0, 0]
    centre_visitors = set()
    snapshots = []
    first_skipped = set()
    for turn in range(1, 25):
        old = game.owner[:]
        pos = game.pos[:]
        actions = [b(v) for b, v in zip(bots, game.views())]
        game.step(actions)
        for j, p in enumerate(game.pos):
            if j == seat:
                continue
            if turn <= 12 and depth(p) >= 2:
                centre_visitors.add(j)
            if turn == 2 and pos[j] in NEIGH[engine.CORNERS[j+1]] and old[pos[j]] == 0 and p != pos[j]:
                first_skipped.add(j)
        for p in range(64):
            if not old[p] and game.owner[p] == seat+1:
                region = min(2, depth(p))
                claims[region] += 1
                values[region] += game.base[p]
        if turn in (4, 8, 12, 24):
            snapshots.append(dict(turn=turn, positions=game.pos[:], owner=game.owner[:]))
    return dict(task_id=task["id"], scenario=task["scenario"], map_kind=task["map_kind"],
                claims=claims, value_sum=values,
                actual_inner_visitors_by12=len(centre_visitors),
                first_neighbour_skippers=len(first_skipped), snapshots=snapshots)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=Path("territorylab/results/opening_observations.json"))
    args = ap.parse_args()
    if args.out.exists():
        raise SystemExit("preserve existing observations")
    sources = evaluate.hashes()
    rows = [observe(t) for t in evaluate.tasks("discovery", 112, 518137)]
    if evaluate.hashes() != sources:
        raise AssertionError("source changed")
    groups = {}
    for n in range(4):
        group = [r for r in rows if r["actual_inner_visitors_by12"] == n]
        if group:
            groups[n] = dict(n=len(group), claims=[sum(r["claims"][k] for r in group)/len(group) for k in range(3)])
    payload = dict(sources=sources, summary=groups, rows=rows,
                   caveat="Observer-only public trajectory description through turn 24. Actual visitors are an after-the-fact description, never information supplied to a played policy. No causal subgroup or strength claim.")
    args.out.write_text(json.dumps(payload, indent=1), encoding="utf-8", newline="\n")
    print(json.dumps(groups, indent=2))


if __name__ == "__main__":
    main()
