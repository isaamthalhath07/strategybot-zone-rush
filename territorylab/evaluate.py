"""Paired tests of spatial opportunity against newly drawn macro opponents."""
import argparse
import hashlib
import json
import multiprocessing as mp
import random
import time
from collections import Counter
from pathlib import Path

from baselines import v8 as bot
import engine
import maps
from freshlab.evaluate import signature, summary
from territorylab import opponents, policy


ROOT = Path(__file__).resolve().parents[1]
SOURCES = ("baselines/v8.py", "engine.py", "maps.py", "botlib.py", "freshlab/population.py",
           "freshlab/evaluate.py", "territorylab/model.py", "territorylab/policy.py",
           "territorylab/opponents.py", "territorylab/evaluate.py")


def hashes():
    return {p: hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in SOURCES}


def tasks(split, count, seed):
    rng = random.Random("territory:%s:%d" % (split, seed))
    kinds = ("standard", "noise", "flat", "edge", "richhome", "richcorner", "inverted")
    scenarios = [i % 4 for i in range(count)]
    rng.shuffle(scenarios)
    result = []
    for i, scenario in enumerate(scenarios):
        s = rng.randrange(2**31)
        roles = ["centre"]*scenario + [rng.choice(("rim", "local")) for _ in range(3-scenario)]
        rng.shuffle(roles)
        specs = [opponents.sample(split, rng.randrange(2**31), role) for role in roles]
        result.append(dict(id=i, seat=i//4 % 4, token=1+i % 4,
                           map_seed=s, map_kind=kinds[i//16 % len(kinds)],
                           base=maps.make(s, kinds[i//16 % len(kinds)]),
                           scenario=scenario, specs=specs))
    return result


def play(task, variant):
    params = dict(throttle=0, budget_ms=10000.0, first_turn_ms=0)
    kwargs = dict(seed=task["map_seed"], params=params)
    focal = (bot.Agent(**kwargs) if variant == "baseline" else
             policy.SpatialAgent(**kwargs, feature=policy.VARIANTS[variant]))
    failures = []
    original = focal.decide
    def checked(view):
        try:
            return original(view)
        except Exception as error:
            failures.append(repr(error))
            raise
    focal.decide = checked
    others = iter(opponents.SpatialOpponent(s) for s in task["specs"])
    bots = [focal if j == task["seat"] else next(others) for j in range(4)]
    game = engine.Game(base=task["base"], start_token=task["token"])
    trace = hashlib.sha256()
    actions_count = Counter()
    max_ms = 0.0
    calls = 0
    while not game.over():
        actions = []
        for j, (b, view) in enumerate(zip(bots, game.views())):
            before = signature(view)
            start = time.perf_counter()
            action = b(view)
            elapsed = (time.perf_counter()-start)*1000
            if action not in view.legal_actions or before != signature(view):
                raise AssertionError("illegal output or mutated input")
            if j == task["seat"]:
                actions_count[action] += 1
                max_ms = max(max_ms, elapsed)
            calls += 1
            actions.append(action)
        game.step(actions)
        trace.update("|".join(actions).encode())
    if failures:
        raise AssertionError(failures)
    scores, seat = game.score, task["seat"]
    pw = sum(1 if scores[seat] > s else 0.5 if scores[seat] == s else 0
             for j, s in enumerate(scores) if j != seat)
    return dict(pw=pw, score=scores[seat], scores=scores, calls=calls,
                max_ms=max_ms, action_counts=dict(actions_count), action_hash=trace.hexdigest())


def job(args):
    task, variants = args
    order = variants if task["id"] % 2 else variants[::-1]
    return dict(task=task, results={v: play(task, v) for v in order})


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--split", required=True, choices=opponents.SPLITS)
    ap.add_argument("--games", type=int, default=224)
    ap.add_argument("--seed", type=int, required=True)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--variants", nargs="+", default=list(policy.VARIANTS))
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--lock", type=Path)
    args = ap.parse_args()
    if args.out.exists():
        ap.error("preserve prior experiments; use a new output file")
    if args.games < 4 or "baseline" not in args.variants or any(v not in policy.VARIANTS for v in args.variants):
        ap.error("use at least four tasks, the baseline, and defined variants")
    sources = hashes()
    if args.split == "final":
        if args.lock is None:
            ap.error("register a fixed candidate before final evaluation")
        lock = json.loads(args.lock.read_text())
        if (lock["sources"] != sources or args.variants != ["baseline", lock["candidate"]] or
            args.games != lock["games"] or args.seed != lock["seed"]):
            ap.error("final evaluation must match the locked candidate, sources, seed and sample size")
    start = time.perf_counter()
    batch = tasks(args.split, args.games, args.seed)
    rows = []
    with mp.Pool(args.workers) as pool:
        for row in pool.imap(job, [(t, args.variants) for t in batch], chunksize=1):
            rows.append(row)
            if len(rows) % 32 == 0:
                print("%d/%d %.1fs" % (len(rows), len(batch), time.perf_counter()-start), flush=True)
    if sources != hashes():
        raise AssertionError("source changed during experiment; discard results")
    report = summary(rows, args.variants)
    payload = dict(split=args.split, seed=args.seed, sources=sources,
                   variants={v: policy.VARIANTS[v] for v in args.variants},
                   summary=report, rows=rows, elapsed_seconds=time.perf_counter()-start,
                   caveat="Fresh spatial opponent parameters and disjoint scheduling families across splits. Roles are nominal test metadata, not secret information available to the focal policy. Shared observation plumbing; not independent implementations. Exploratory discovery intervals.")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=1), encoding="utf-8", newline="\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
