"""Bounded independent audit: compare two economics corrections to shipped v7."""
import inspect
import importlib.util
import json
import math
import multiprocessing as mp
import os
import textwrap

import engine
import field
import measure
import mybot

_spec = importlib.util.spec_from_file_location("audit_baseline_mybot", "audit/baseline_mybot.py")
baseline = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(baseline)


def candidate_class(kind):
    source = textwrap.dedent(inspect.getsource(baseline.Agent._work_gain))
    if kind in ("income", "both"):
        source = source.replace("rem = R - used - need", "rem = R - used - need + 1")
        source = source.replace("rem1 = R - used - 1", "rem1 = R - used")
    if kind in ("cooldown", "both"):
        source = source.replace("self._shield_risk(o - 1, travel, need)",
                                "self._shield_risk(o - 1, used, need)")
    if kind == "endgame":
        source = source.replace("rem = R - used - need", "rem = R - used - need + (1 if R == 1 else 0)")
        source = source.replace("rem1 = R - used - 1", "rem1 = R - used - 1 + (1 if R == 1 else 0)")
    scope = dict(vars(baseline))
    exec(source, scope)
    return type("AuditAgent", (baseline.Agent,), {"_work_gain": scope["_work_gain"]})


def play(arg):
    kind, params, task = arg
    cls = candidate_class(kind)
    map_seed, seat, opponents, token = task
    params = dict(params, throttle=0, budget_ms=10000.0)
    bots, k = [], 0
    for i in range(4):
        if i == seat:
            bots.append(cls(seed=map_seed & 0xffff, params=params))
        else:
            bots.append(field.opponent(opponents[k])(map_seed * 4 + i))
            k += 1
    game = engine.Game(base=engine.make_map(seed=map_seed), start_token=token)
    while not game.over():
        views = game.views()
        actions = [bot(view) for bot, view in zip(bots, views)]
        assert all(a in v.legal_actions for a, v in zip(actions, views))
        game.step(actions)
    score = game.score
    place = 1 + sum(score[j] > score[seat] for j in range(4) if j != seat)
    wins = sum(1.0 if score[seat] > score[j] else
               0.5 if score[seat] == score[j] else 0.0
               for j in range(4) if j != seat)
    return kind, (wins, game.score[seat], place, score[:])


def main():
    import sys
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 80
    tier = sys.argv[2] if len(sys.argv) > 2 else "strangers"
    seed = int(sys.argv[3]) if len(sys.argv) > 3 else 631779
    kinds = sys.argv[4:] or ["base", "income", "cooldown", "both"]
    p = dict(mybot.PARAMS)
    p.update(json.load(open("v7_params.json")))
    tasks = measure.make_tasks(n, tier, seed=seed)
    jobs = [(kind, p, task) for task in tasks for kind in kinds]
    results = {kind: [] for kind in kinds}
    with mp.Pool(int(os.environ.get("PROCS", "2"))) as pool:
        for kind, result in pool.imap(play, jobs, chunksize=4):
            results[kind].append(result)
    measure.report([(k, p) for k in kinds], results,
                   label="audit %s seed=%d" % (tier, seed))
    path = "audit_strategy_%s_%d_%d.json" % (tier, seed, n)
    with open(path, "w") as out:
        json.dump({"tier": tier, "seed": seed, "n": n,
                   "kinds": kinds, "results": results}, out, indent=2)
    print("Raw per-game results saved to", path)


if __name__ == "__main__":
    main()
