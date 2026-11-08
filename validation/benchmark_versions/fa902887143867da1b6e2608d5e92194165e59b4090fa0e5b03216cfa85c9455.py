"""Registered, process-isolated comparison. Every player receives public input only."""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import gzip
import hashlib
import json
from pathlib import Path
import random
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
VENDOR = ROOT / "simulator/vendor_harness"
if not VENDOR.exists():
    VENDOR = ROOT / "human_arena/vendor_harness"
sys.path.insert(0, str(VENDOR))
from match import BotProcess, DEFAULT_TIMING
from referee import DEFAULT_RULES, Referee, pairwise


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def job(candidate, fixture, sources, rules, timing):
    assignment = list(fixture["opponents"])
    assignment.insert(fixture["seat"], candidate)
    workers = [BotProcess(str((ROOT / sources[name]["path"]).resolve())) for name in assignment]
    records = [dict(calls=0, total_ms=0.0, max_ms=0.0) for _ in workers]
    faults, actions = [], []
    started = time.perf_counter()
    try:
        for worker in workers:
            worker.spawn()
        for seat, worker in enumerate(workers):
            loaded = worker.finish_load(timing["load_s"])
            if not loaded["ok"]:
                faults.append(dict(turn=0, seat=seat, source=assignment[seat], status="load", error=loaded["error"]))
        game = Referee(fixture["base"], rules=rules, start_token=fixture["token"])
        while not game.over():
            chosen = []
            for seat, worker in enumerate(workers):
                observation = game.observation(seat + 1)
                assert set(observation) == {"board", "bot_id", "is_priority_token", "legal_actions"}
                result = worker.act(observation, game.turn, timing)
                rec = records[seat]
                rec["calls"] += 1
                ms = result.get("ms") or 0.0
                rec["total_ms"] += ms
                rec["max_ms"] = max(rec["max_ms"], ms)
                if result["status"] != "ok":
                    faults.append(dict(turn=game.turn, seat=seat, source=assignment[seat],
                                       status=result["status"], ms=ms, error=result.get("error")))
                chosen.append(result["used"])
            actions.append(chosen)
            game.step(chosen)
        pw = [3 * value for value in pairwise(game.score)]
        return dict(candidate=candidate, fixture=fixture["id"], map_group=fixture["map_group"],
                    field=fixture["field"], focal_seat=fixture["seat"], assignment=assignment,
                    scores=game.score, pw=pw, focal_pw=pw[fixture["seat"]],
                    focal_score=game.score[fixture["seat"]], timing=records, faults=faults,
                    actions=actions, elapsed_s=time.perf_counter() - started)
    finally:
        for worker in workers:
            worker.close()


def summarize(games):
    summary = {}
    for name in sorted({row["candidate"] for row in games}):
        rows = [row for row in games if row["candidate"] == name]
        focal = [row["timing"][row["focal_seat"]] for row in rows]
        fields = {}
        for field in sorted({row["field"] for row in rows}):
            group = [row for row in rows if row["field"] == field]
            fields[field] = sum(row["focal_pw"] for row in group) / len(group)
        summary[name] = dict(games=len(rows), mean_pw=sum(row["focal_pw"] for row in rows)/len(rows),
                             mean_score=sum(row["focal_score"] for row in rows)/len(rows), fields=fields,
                             focal_faults=sum(fault["source"] == name for row in rows for fault in row["faults"]),
                             all_faults=sum(len(row["faults"]) for row in rows),
                             max_ms=max(row["max_ms"] for row in focal),
                             mean_ms=sum(row["total_ms"] for row in focal)/sum(row["calls"] for row in focal))
    return dict(sorted(summary.items(), key=lambda item: (item[1]["focal_faults"] != 0, -item[1]["mean_pw"])))


def paired(games, names):
    output = []
    for ai, a in enumerate(names):
        for b in names[ai+1:]:
            aa = {row["fixture"]: row for row in games if row["candidate"] == a}
            bb = {row["fixture"]: row for row in games if row["candidate"] == b}
            clusters = {}
            for key in sorted(aa.keys() & bb.keys()):
                row = aa[key]
                clusters.setdefault(row["map_group"], []).append(row["focal_pw"] - bb[key]["focal_pw"])
            means = [sum(clusters[key])/len(clusters[key]) for key in sorted(clusters)]
            if not means:
                continue
            rng = random.Random(202611081801)
            boot = sorted(sum(rng.choice(means) for _ in means)/len(means) for _ in range(10000))
            output.append(dict(first=a, second=b, mean=sum(means)/len(means), clusters=len(means),
                               bootstrap_95=[boot[249], boot[9749]]))
    return output


def ordered_jobs(names, fixtures, seed):
    """Mix candidate order within shuffled fixture blocks to limit host drift."""
    if type(seed) is not int or not 0 <= seed < 2**64:
        raise ValueError("job_order_seed must be an unsigned64-bit integer")
    rng = random.Random(seed)
    blocks = list(fixtures)
    rng.shuffle(blocks)
    output = []
    for fixture in blocks:
        within = list(names)
        rng.shuffle(within)
        output.extend((name, fixture) for name in within)
    return output


def run(spec_path, out, workers):
    spec = json.loads(spec_path.read_text(encoding="utf8"))
    if out.exists() or out.with_suffix(".registration.json").exists():
        raise ValueError("Use a fresh result path; consumed evaluations are never overwritten")
    sources = {source["name"]: source for source in spec["sources"]}
    names = set(spec["candidates"]) | {name for f in spec["fixtures"] for name in f["opponents"]}
    assert names <= set(sources)
    guards = {ROOT / sources[name]["path"]: sources[name]["sha256"] for name in names}
    guards.update({Path(__file__): sha(__file__), VENDOR/"referee.py": sha(VENDOR/"referee.py"),
                   VENDOR/"worker.py": sha(VENDOR/"worker.py"), spec_path: sha(spec_path)})
    for path, expected in guards.items():
        if sha(path) != expected:
            raise AssertionError("Source hash mismatch: " + str(path))
    rules = dict(DEFAULT_RULES, **spec["rules"])
    if not isinstance(rules["catch_requires_stay"], bool):
        raise ValueError("catch_requires_stay must be an explicitly registered Boolean")
    timing = dict(DEFAULT_TIMING, hard_s=1.0, load_s=5.0)
    order_seed = spec.get("job_order_seed", 202611083001)
    jobs = ordered_jobs(spec["candidates"], spec["fixtures"], order_seed)
    order_bytes = json.dumps([(name, f["id"]) for name, f in jobs], separators=(",", ":")).encode("utf8")
    registration = dict(spec=spec, spec_sha256=sha(spec_path), benchmark_sha256=sha(__file__),
                        referee_sha256=sha(VENDOR/"referee.py"), worker_sha256=sha(VENDOR/"worker.py"),
                        timing=timing, rules=rules, job_order_seed=order_seed,
                        job_order="shuffled fixture blocks; shuffled candidate order within each block",
                        job_order_sha256=hashlib.sha256(order_bytes).hexdigest())
    out.parent.mkdir(parents=True, exist_ok=True)
    out.with_suffix(".registration.json").write_text(json.dumps(registration, indent=2), encoding="utf8", newline="\n")
    started, games = time.perf_counter(), []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        pending = [pool.submit(job, name, f, sources, rules, timing) for name, f in jobs]
        for future in as_completed(pending):
            games.append(future.result())
            if len(games) % 16 == 0 or len(games) == len(jobs):
                print("%s: %d/%d games, %.1fs" % (spec["id"], len(games), len(jobs), time.perf_counter()-started), flush=True)
    for path, expected in guards.items():
        if sha(path) != expected:
            raise AssertionError("Source changed during evaluation: " + str(path))
    games.sort(key=lambda row: (row["candidate"], row["fixture"]))
    summary = summarize(games)
    result = dict(registration=registration, summary=summary, paired=paired(games, list(summary) if len(summary)<=15 else list(summary)[:6]),
                  games=games, elapsed_s=time.perf_counter()-started,
                  caveat="Finite registered field. Screening is selection data. Confirmations are fresh maps, not proof against every possible rival. No private state or future actions reach a policy.")
    with gzip.open(out, "wt", encoding="utf8", newline="\n") as handle:
        json.dump(result, handle, separators=(",", ":"))
    concise = {key:value for key,value in result.items() if key not in ("registration", "games")}
    concise["games"] = len(games)
    concise["timed_callbacks"] = sum(t["calls"] for row in games for t in row["timing"])
    concise["all_faults"] = sum(len(row["faults"]) for row in games)
    out.with_suffix(".summary.json").write_text(json.dumps(concise, indent=2), encoding="utf8", newline="\n")
    print(json.dumps({key:value for key,value in concise.items() if key != "paired"}, indent=2), flush=True)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--spec", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=6)
    args = parser.parse_args()
    run(args.spec.resolve(), args.out.resolve(), args.workers)


if __name__ == "__main__":
    main()
