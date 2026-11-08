"""Strict paired audit of current source against a frozen implementation.

    python audit_compare.py --games 160 --map-games 40 --workers 4

Both sides use the same v7 parameters. Frozen-snapshot opponents always use the
old implementation, so editing mybot.py cannot silently change their policy.
Clock guards are disabled for this policy comparison. Shipping timing must be
tested separately; measured >200 ms calls here are diagnostics, not substituted.
"""
import argparse
from collections import Counter
import hashlib
import importlib.util
import json
import math
import multiprocessing as mp
import os
from pathlib import Path
import platform
import random
import time

import engine
import field
import rivals


ROOT = Path(__file__).resolve().parent
BASELINE_PATH = ROOT / "audit" / "baseline_mybot.py"
CURRENT = None
BASELINE = None
PARAMS = None
CHECK_INPUT = False
FROZEN_NAMES = set()


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def initialize(params, provenance, check_input, current_source, baseline_source):
    global CURRENT, BASELINE, PARAMS, CHECK_INPUT, FROZEN_NAMES
    os.chdir(ROOT)
    for filename, expected in provenance.items():
        if digest(ROOT / filename) != expected:
            raise RuntimeError("source changed before worker initialization: " + filename)
    CURRENT = load_module("audit_current", current_source)
    BASELINE = load_module("audit_frozen", baseline_source)
    rivals.mybot = BASELINE
    FROZEN_NAMES = set(rivals.names())
    PARAMS = dict(params, throttle=0, budget_ms=10000.0, first_turn_ms=0.0)
    CHECK_INPUT = check_input


def signature(view):
    return (view.bot_id, view.is_priority_token, tuple(view.legal_actions),
            tuple((c.occupant, c.owner, c.is_upgraded, c.is_home, c.is_frozen,
                   c.base_points) for row in view.board for c in row))


def observed(bot, seat, faults, clock):
    """Surface planner exceptions even if the public wrapper uses a fallback."""
    if hasattr(bot, "decide"):
        original = bot.decide

        def checked(view):
            try:
                return original(view)
            except Exception as exc:
                faults.append(dict(turn=clock[0], seat=seat, kind="internal_exception",
                                   detail=type(exc).__name__ + ": " + str(exc)))
                raise

        bot.decide = checked
    return bot


def play(task, variant):
    module = CURRENT if variant == "current" else BASELINE
    seed, myseat = task["map_seed"], task["seat"]
    bots, faults, clock = [], [], [0]
    j = 0
    for i in range(4):
        if i == myseat:
            bot = module.Agent(seed=seed & 0xffff, params=PARAMS)
        else:
            name = task["opponents"][j]
            bot = field.opponent(name)(seed * 4 + i)
            if name in FROZEN_NAMES:
                if not isinstance(bot, BASELINE.Agent):
                    raise RuntimeError("snapshot opponent did not use frozen implementation: " + name)
            j += 1
        bots.append(observed(bot, i + 1, faults, clock))
    game = engine.Game(base=task["base"], start_token=task["token"])
    max_ms = [0.0] * 4
    n_calls = [0] * 4
    # Trace action hashes make reproducibility checkable without dumping 320
    # redundant action strings into every result record.
    action_hash = hashlib.sha256()
    while not game.over():
        clock[0] = game.turn
        views = game.views()
        actions = []
        for i, (bot, view) in enumerate(zip(bots, views)):
            before = signature(view) if CHECK_INPUT else None
            legal = tuple(view.legal_actions)
            started = time.perf_counter()
            try:
                action = bot(view)
            except Exception as exc:
                faults.append(dict(turn=game.turn, seat=i + 1, kind="exception",
                                   detail=type(exc).__name__ + ": " + str(exc)))
                action = "STAY"
            ms = (time.perf_counter() - started) * 1000.0
            max_ms[i] = max(max_ms[i], ms)
            n_calls[i] += 1
            if CHECK_INPUT and signature(view) != before:
                faults.append(dict(turn=game.turn, seat=i + 1, kind="input_mutation"))
            if action not in legal:
                faults.append(dict(turn=game.turn, seat=i + 1, kind="illegal", detail=repr(action)))
                action = "STAY"
            if ms > (2000 if game.turn == 1 else 200):
                faults.append(dict(turn=game.turn, seat=i + 1, kind="timing_diagnostic", ms=ms))
            actions.append(action)
        action_hash.update("|".join(actions).encode())
        game.step(actions)
    scores, places = game.score, game.places()
    pw = sum(1.0 if scores[myseat] > scores[i] else 0.5 if scores[myseat] == scores[i]
             else 0.0 for i in range(4) if i != myseat)
    return dict(pw=pw, score=scores[myseat], place=places[myseat], scores=scores,
                places=places, final_cells=[game.cells_owned(i) for i in range(4)],
                faults=faults, max_ms=[round(x, 3) for x in max_ms], calls=n_calls,
                action_sha256=action_hash.hexdigest())


def compare(task):
    # Alternate execution order to avoid giving one implementation systematically
    # warmer caches; it cannot change policy with clock guards pinned.
    order = ("baseline", "current") if task["id"] % 2 == 0 else ("current", "baseline")
    results = {name: play(task, name) for name in order}
    return dict(task=task, **results)


def pool_for(name):
    if name in ("strangers", "peer"):
        return [(n, 1.0) for n in field.tier(name)]
    if name == "mixed":
        # Match the documented historical mixed field exactly: original zoo
        # weights plus each frozen snapshot at weight 2.5.
        import tune
        return tune.get_field("mixed")
    raise ValueError(name)


def arbitrary_mirror(seed):
    rnd = random.Random(seed)
    base = [0] * 64
    for r in range(4):
        for c in range(4):
            v = rnd.randint(1, 3)
            for rr, cc in ((r, c), (r, 7-c), (7-r, c), (7-r, 7-c)):
                base[rr * 8 + cc] = v
    return base


def make_tasks(n, map_games, seed):
    tasks = []
    for fi, field_name in enumerate(("strangers", "peer", "mixed")):
        rnd = random.Random(seed + fi * 1000003)
        names, weights = zip(*pool_for(field_name))
        for subset, count in (("main", n), ("map_stress", map_games)):
            # Main tasks cover all 16 seat/token pairs each block. Stress tasks
            # balance each map kind as closely as their count allows, without
            # confounding its k%4 map kind with one fixed seat.
            seats, tokens = list(range(4)), list(range(1, 5))
            rnd.shuffle(seats)
            rnd.shuffle(tokens)
            for k in range(count):
                if subset == "main":
                    seat = seats[k % 4]
                    token = tokens[(k // 4 + k % 4) % 4]
                else:
                    j, m = divmod(k, 4)
                    seat = seats[(j + m) % 4]
                    token = tokens[(j // 4 + j % 4 + m) % 4]
                map_seed = rnd.randrange(1 << 30)
                kind = "local_random" if subset == "main" else (
                    "canonical", "independent_mirror", "flat1", "flat3")[k % 4]
                if kind == "local_random":
                    base = engine.make_map(seed=map_seed)
                elif kind == "canonical":
                    base = engine.make_map(canonical=True)
                elif kind == "independent_mirror":
                    base = arbitrary_mirror(map_seed)
                else:
                    base = [int(kind[-1])] * 64
                tasks.append(dict(id=len(tasks), field=field_name, subset=subset,
                                  map_kind=kind, map_seed=map_seed, base=base, seat=seat,
                                  token=token, opponents=rnd.choices(names, weights=weights, k=3)))
    return tasks


def t95(df):
    # Cornish-Fisher expansion of the 97.5% Student-t quantile. Accurate to <.001
    # for the report's groups of at least ten independent paired tasks.
    z = 1.959963984540054
    if df < 2:
        return 12.706204736 if df == 1 else float("inf")
    return (z + (z**3 + z)/(4*df) + (5*z**5 + 16*z**3 + 3*z)/(96*df**2)
            + (3*z**7 + 19*z**5 + 17*z**3 - 15*z)/(384*df**3))


def summarize(rows):
    n = len(rows)
    out = {"n": n}
    for metric in ("pw", "score", "place"):
        differences = [r["current"][metric] - r["baseline"][metric] for r in rows]
        mean = sum(differences) / n
        se = math.sqrt(sum((d - mean)**2 for d in differences) / (n-1) / n) if n > 1 else 0
        radius = t95(n-1) * se if n > 1 else None
        out[metric] = dict(baseline=sum(r["baseline"][metric] for r in rows)/n,
                           current=sum(r["current"][metric] for r in rows)/n,
                           difference=mean, paired_se=se,
                           ci95=[mean-radius, mean+radius] if radius is not None else None)
    for variant in ("baseline", "current"):
        faults = [f for r in rows for f in r[variant]["faults"]]
        out[variant + "_faults"] = dict(Counter(f["kind"] for f in faults))
        out[variant + "_max_ms"] = max(max(r[variant]["max_ms"]) for r in rows)
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--games", type=int, default=160, help="main paired tasks per field")
    parser.add_argument("--map-games", type=int, default=40, help="stress paired tasks per field")
    parser.add_argument("--workers", type=int, choices=range(1, 5), default=4)
    parser.add_argument("--seed", type=int, default=202611071)
    parser.add_argument("--check-input", action="store_true")
    parser.add_argument("--current-source", type=Path, default=ROOT / "mybot.py",
                        help="candidate implementation; use an exact copied snapshot for a final audit")
    parser.add_argument("--baseline-source", type=Path, default=BASELINE_PATH)
    parser.add_argument("--out", type=Path, default=ROOT / "audit" / "comparison.json")
    args = parser.parse_args()
    if args.games < 1 or args.map_games < 0:
        parser.error("--games must be positive and --map-games nonnegative")
    args.out = args.out.resolve()
    args.current_source = args.current_source.resolve()
    args.baseline_source = args.baseline_source.resolve()
    os.chdir(ROOT)
    params = dict(load_module("audit_current_defaults", args.current_source).PARAMS)
    params.update(json.loads((ROOT / "v7_params.json").read_text()))
    files = ["engine.py", "rivals.py", "field.py",
             "zoo.py", "holdout.py", "aifield.py", "probot.py", "snapshots.json",
             "pro_params_v1.json", "v7_params.json", "tune.py"]
    for source in (args.current_source, args.baseline_source):
        try:
            files.append(source.relative_to(ROOT).as_posix())
        except ValueError:
            files.append(str(source))
    provenance = {name: digest(ROOT / name) for name in files}
    # Record the live source for context only. It is not imported as a contestant
    # or guarded when an explicit immutable candidate snapshot is selected.
    live_hash_at_start = digest(ROOT / "mybot.py")
    print("Candidate snapshot: %s SHA256=%s" % (args.current_source, digest(args.current_source)), flush=True)
    print("Baseline snapshot: %s SHA256=%s" % (args.baseline_source, digest(args.baseline_source)), flush=True)
    tasks = make_tasks(args.games, args.map_games, args.seed)
    started = time.perf_counter()
    rows = []
    with mp.Pool(args.workers, initializer=initialize,
                 initargs=(params, provenance, args.check_input,
                           args.current_source, args.baseline_source)) as workers:
        for row in workers.imap(compare, tasks, chunksize=1):
            rows.append(row)
            if len(rows) % 40 == 0 or len(rows) == len(tasks):
                print("%d/%d paired tasks, %.1fs" % (len(rows), len(tasks), time.perf_counter()-started), flush=True)
    summaries = {}
    for field_name in ("strangers", "peer", "mixed"):
        for subset in ("main", "map_stress"):
            group = [r for r in rows if r["task"]["field"] == field_name and r["task"]["subset"] == subset]
            if not group:
                continue
            key = field_name + "/" + subset
            summaries[key] = summarize(group)
            s = summaries[key]
            pw = s["pw"]
            interval = "[%+.4f,%+.4f]" % tuple(pw["ci95"]) if pw["ci95"] else "undefined (one task)"
            print("%-22s n=%d PW %.4f -> %.4f delta=%+.4f SE=%.4f CI95=%s" %
                  (key, s["n"], pw["baseline"], pw["current"], pw["difference"], pw["paired_se"], interval), flush=True)
            if subset == "map_stress":
                for kind in ("canonical", "independent_mirror", "flat1", "flat3"):
                    sample = [r for r in group if r["task"]["map_kind"] == kind]
                    if sample:
                        summaries[key + "/" + kind] = summarize(sample)
    changed = [name for name, expected in provenance.items() if digest(ROOT / name) != expected]
    payload = dict(seed=args.seed, workers=args.workers, main_games_per_field=args.games,
                   stress_games_per_field=args.map_games, python=platform.python_version(),
                   elapsed_seconds=round(time.perf_counter()-started, 3), params=params,
                   clocks="pinned: throttle=0, budget_ms=10000, first_turn_ms=0",
                   source_sha256=provenance, changed_sources=changed,
                   current_source=str(args.current_source), baseline_source=str(args.baseline_source),
                   current_snapshot_sha256=digest(args.current_source),
                   live_mybot_sha256_at_start=live_hash_at_start,
                   frozen_snapshot_opponents=str(args.baseline_source) + " via rivals.mybot",
                   caveat="Paired descriptive task-level t intervals; subsets not corrected for multiple comparisons. Synthetic local maps and opponents cannot establish performance against unknown teams or the official server.",
                   input_mutation_checked=args.check_input, summary=summaries, results=rows)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print("Raw paired results: " + str(args.out), flush=True)
    if changed:
        raise SystemExit("Source changed during comparison: " + ", ".join(changed))
    fatal = [f for r in rows for v in ("baseline", "current") for f in r[v]["faults"]
             if f["kind"] != "timing_diagnostic"]
    if fatal:
        raise SystemExit("Comparison surfaced %d policy/contract failures; inspect raw results" % len(fatal))


if __name__ == "__main__":
    main()
