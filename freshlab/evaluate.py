"""Reproducible paired tests on newly sampled opponents, no old opponent zoo.

python -m freshlab.evaluate --split train --games 96 --variants baseline observe_only context_commit context_defence guarded context_both future_window dwell
python -m freshlab.evaluate --split development --games 192 --variants baseline guarded
Final evaluation is permitted only for a pre-registered locked candidate.
"""
import argparse
import hashlib
import json
import math
import multiprocessing as mp
import random
import time
from collections import Counter
from pathlib import Path

import engine
import maps
from freshlab import baseline, candidate, population

ROOT = Path(__file__).resolve().parents[1]
SOURCES = ("engine.py", "maps.py", "botlib.py", "v7_params.json", "freshlab/baseline.py",
           "freshlab/model.py", "freshlab/candidate.py", "freshlab/population.py",
           "freshlab/evaluate.py", "freshlab/terminal.py")


def hashes():
    return {s: hashlib.sha256((ROOT / s).read_bytes()).hexdigest() for s in SOURCES}


def tasks(split, n, seed):
    rng = random.Random("fresh-tasks:%s:%d" % (split, seed))
    # All common map distributions occur during discovery. Entire additional
    # distributions (richcorner, inverted) are reserved for the final stress set.
    kinds = ("standard", "standard", "noise", "flat", "edge", "richhome")
    if split == "final":
        kinds += ("richcorner", "inverted")
    result = []
    for k in range(n):
        map_seed = rng.randrange(2 ** 31)
        map_kind = kinds[k % len(kinds)]
        specifications = [population.specification(split, rng.randrange(2 ** 31)) for _ in range(3)]
        result.append(dict(id=k, seat=k % 4, token=1 + (k // 4) % 4,
                           map_kind=map_kind, base=maps.make(map_seed, map_kind),
                           map_seed=map_seed, specs=specifications))
    return result


def signature(state):
    return (state.bot_id, state.is_priority_token, tuple(state.legal_actions),
            tuple((c.owner, c.occupant, c.is_upgraded, c.is_home, c.is_frozen,
                   c.base_points) for row in state.board for c in row))


def play(task, variant, params):
    seed, seat = task["map_seed"], task["seat"]
    policy = (baseline.Agent(seed=seed, params=params) if variant == "baseline"
              else candidate.AdaptiveAgent(seed=seed, params=params,
                                           features=candidate.VARIANTS[variant]))
    # Expose failures the shipping wrapper would normally turn into fallback.
    errors = []
    decide = policy.decide
    def checked(view):
        try:
            return decide(view)
        except Exception as e:
            errors.append(repr(e))
            raise
    policy.decide = checked
    others = iter(population.ProceduralOpponent(s) for s in task["specs"])
    bots = [policy if j == seat else next(others) for j in range(4)]
    game = engine.Game(base=task["base"], start_token=task["token"])
    transcript = hashlib.sha256()
    calls = 0
    max_ms = 0.0
    actions_count = Counter()
    while not game.over():
        states = game.views()
        actions = []
        for j, (bot, state) in enumerate(zip(bots, states)):
            before = signature(state)
            start = time.perf_counter()
            action = bot(state)
            elapsed = 1000 * (time.perf_counter() - start)
            if action not in state.legal_actions or before != signature(state):
                raise AssertionError("input mutation or illegal output")
            if j == seat:
                max_ms = max(max_ms, elapsed)
                actions_count[action] += 1
            calls += 1
            actions.append(action)
        game.step(actions)
        transcript.update("|".join(actions).encode())
    if errors:
        raise AssertionError("swallowed planner exceptions: %s" % errors)
    score = game.score
    pw = sum(1.0 if score[seat] > score[j] else 0.5 if score[seat] == score[j]
             else 0.0 for j in range(4) if j != seat)
    learning = {}
    if hasattr(policy.tr, "styles"):
        styles = policy.tr.styles
        for name in ("defence", "commit", "finish"):
            learning[name] = getattr(styles, name).brier
        learning["ambiguous"] = styles.ambiguous
        learning["inconsistent"] = styles.inconsistent
    return dict(pw=pw, score=score[seat], scores=score[:], calls=calls,
                action_hash=transcript.hexdigest(), max_ms=max_ms,
                action_counts=dict(actions_count), learning=learning)


def job(arg):
    task, variants, params = arg
    order = variants if task["id"] % 2 else variants[::-1]
    return dict(task=task, results={v: play(task, v, params) for v in order})


def summary(rows, variants):
    report = {}
    for v in variants:
        d = [r["results"][v]["pw"] - r["results"]["baseline"]["pw"] for r in rows]
        n = len(d)
        mean = sum(d) / n
        se = math.sqrt(sum((x - mean) ** 2 for x in d) / (n - 1) / n) if n > 1 else 0
        report[v] = dict(n=n, pw=sum(r["results"][v]["pw"] for r in rows)/n,
                         score=sum(r["results"][v]["score"] for r in rows)/n,
                         difference=mean, se=se, ci95=[mean - 1.98*se, mean + 1.98*se],
                         worst_ms=max(r["results"][v]["max_ms"] for r in rows))
    return report


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--split", choices=population.SPLITS, required=True)
    ap.add_argument("--games", type=int, default=96)
    ap.add_argument("--seed", type=int, default=183711)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--variants", nargs="+", default=["baseline", "guarded"])
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--lock", type=Path)
    args = ap.parse_args()
    variants = args.variants
    if "baseline" not in variants or any(v not in candidate.VARIANTS for v in variants):
        ap.error("include baseline; use defined variants")
    provenance = hashes()
    if args.split == "final":
        if args.lock is None:
            ap.error("final needs a candidate registration written before seeing final games")
        registration = json.loads(args.lock.read_text())
        if variants != ["baseline", registration["candidate"]] or provenance != registration["sources"]:
            ap.error("candidate or source differs from its pre-registered version")
        if args.seed != registration["final_seed"] or args.games != registration["final_games"]:
            ap.error("final seed and sample size must match the pre-registration")
        if args.out.exists():
            ap.error("do not overwrite a held-out result")
    if args.games < 4:
        ap.error("at least four games required")
    params = dict(baseline.PARAMS)
    params.update(json.loads((ROOT / "v7_params.json").read_text()))
    params.update(throttle=0, budget_ms=10000.0, first_turn_ms=0)
    all_tasks = tasks(args.split, args.games, args.seed)
    rows = []
    start = time.perf_counter()
    with mp.Pool(args.workers) as pool:
        for row in pool.imap(job, [(t, variants, params) for t in all_tasks], chunksize=1):
            rows.append(row)
            if len(rows) % 32 == 0:
                print("%d/%d tasks (%.1fs)" % (len(rows), len(all_tasks), time.perf_counter() - start), flush=True)
    if hashes() != provenance:
        raise RuntimeError("source changed mid-experiment; discard these results")
    report = summary(rows, variants)
    print("Split %s: only newly generated %s opponents" % (args.split, population.SPLITS[args.split]))
    for v, r in report.items():
        print("%-18s PW %.4f score %.0f delta %+.4f CI95 [%+.4f,%+.4f]" %
              (v, r["pw"], r["score"], r["difference"], *r["ci95"]), flush=True)
    payload = dict(split=args.split, seed=args.seed, params=params, sources=provenance,
                   variants={v: candidate.VARIANTS[v] for v in variants}, summary=report,
                   caveat="Synthetic opponents; shared public-state plumbing across families. Descriptive task-level intervals; training comparisons exploratory. No known competitors used.",
                   elapsed_seconds=time.perf_counter()-start, rows=rows)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
