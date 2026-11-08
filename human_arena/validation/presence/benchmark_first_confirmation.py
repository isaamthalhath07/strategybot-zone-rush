"""Presence-based Shield comparison through the isolated human-play workers.

Screening selects candidates; confirmation uses fresh maps without retuning.
Every game starts four new processes and passes only official observations.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
from pathlib import Path
import random
import sys
import time

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "vendor_harness"))
from match import BotProcess, DEFAULT_TIMING
from referee import Referee, DEFAULT_RULES, example_map, random_map, pairwise, mirror

CANDIDATES = HERE / "candidates"
VALIDATION = HERE / "validation" / "presence"
TIMING = dict(DEFAULT_TIMING, hard_s=1, load_s=5)
RULES = dict(DEFAULT_RULES, catch_requires_stay=False)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def register(names, stage):
    records = []
    for name in names:
        path = (CANDIDATES / name).resolve()
        if not path.is_relative_to(CANDIDATES.resolve()):
            raise ValueError("candidate outside directory")
        records.append(dict(path=name, sha256=digest(path), bytes=path.stat().st_size))
    # The fixture registration is written before any games start.
    fixture = fixtures(stage)
    opponent_names = {n for f in fixture for n in f["opponents"]}
    data = dict(format="zone-rush-champion-validation/1", stage=stage,
                benchmark_sha256=digest(Path(__file__)),
                sources=records, rules=RULES, referee_sha256=digest(HERE / "vendor_harness/referee.py"),
                workers_sha256=digest(HERE / "vendor_harness/worker.py"), fixtures=fixture,
                opponent_hashes={n:digest(CANDIDATES/n) for n in sorted(opponent_names)},
                timing=TIMING, selection="Screen ranks by mean rivals outscored; confirmation compares frozen finalists on fresh maps. No policy tuning in this tool.")
    VALIDATION.mkdir(parents=True, exist_ok=True)
    path = VALIDATION / (stage + "_registration.json")
    if path.exists() and json.loads(path.read_text()) != data:
        raise ValueError("existing registration differs; use a new stage name")
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf8")
    return data


def fixtures(stage):
    # Fixed opponents cover both cheap economic policies and the beam planner.
    fields = [["branch_1dca0c916af4.py", "branch_cefe2fa7bce1.py", "branch_31965e1412c6.py"],
              ["baseline_v8.py", "branch_5457b5fdf4ca.py", "branch_f6b4385da8e0.py"]]
    confirm = stage.startswith("confirm")
    if confirm:
        fields = [["branch_1dca0c916af4.py", "branch_5457b5fdf4ca.py", "branch_cefe2fa7bce1.py"],
                  ["research_presence.py", "transfer_presence.py", "forward_presence.py"]]
    rnd = random.Random(202611080953 if confirm else 202611080947)
    seeds = [rnd.randrange(1 << 30) for _ in range(8 if confirm else 4)]
    if not confirm:
        seeds[0] = None
    result = []
    for mi, seed in enumerate(seeds):
        stress = {4: ("flat-one", [[1]*4 for _ in range(4)]),
                  5: ("flat-three", [[3]*4 for _ in range(4)]),
                  6: ("rich-corners", [[3,3,2,1],[3,2,1,1],[2,1,1,1],[1,1,1,1]]),
                  7: ("rich-edges", [[3,3,3,3],[3,2,1,1],[3,1,1,1],[3,1,1,1]])}
        for seat in range(4):
            # Confirmation balances all 16 seat/token crossings in every map.
            for tk in (range(4) if confirm else [(mi + seat) % 4]):
                result.append(dict(id=len(result), map_seed=seed, map_index=mi,
                                   seat=seat, token=tk + 1,
                                   opponents=fields[((mi + seat + tk) if confirm else (mi + seat)) % len(fields)]))
                if confirm and mi in stress:
                    name, quadrant = stress[mi]
                    result[-1].update(map_kind=name, base=mirror(quadrant))
    if stage.startswith("confirm_followup"):
        # The first confirmation selected a different parameter variant. Its
        # boards are now consumed selection data. Reserve new board contents,
        # including new corner/edge/uniform quadrants, for this final check.
        prior = fixtures("confirm_release") + fixtures("screen_balanced")
        seen = {tuple(f.get("base") or (example_map() if f["map_seed"] is None else random_map(f["map_seed"]))) for f in prior}
        fresh = random.Random(202611080629)
        for mi in range(8):
            while True:
                seed = fresh.randrange(1 << 30)
                if mi < 4 or mi == 7:
                    base, kind = random_map(seed), "fresh-random"
                elif mi == 4:
                    base = mirror([[max(1,min(3,3-(r+c)//2+fresh.choice([-1,0,0,1]))) for c in range(4)] for r in range(4)])
                    kind = "fresh-rich-corners"
                elif mi == 5:
                    base = mirror([[3 if min(r,c)==0 else fresh.choice([1,1,2,3]) for c in range(4)] for r in range(4)])
                    kind = "fresh-rich-edges"
                else:
                    base = mirror([[fresh.randint(1,3) for _ in range(4)] for _ in range(4)])
                    kind = "fresh-uniform-quadrant"
                if tuple(base) not in seen:
                    seen.add(tuple(base))
                    break
            for row in result:
                if row["map_index"] == mi:
                    row.update(map_seed=seed, map_kind=kind, base=base)
    return result


def game_job(candidate, fixture):
    assignment = list(fixture["opponents"])
    assignment.insert(fixture["seat"], candidate["path"])
    workers = [BotProcess(str((CANDIDATES / name).resolve())) for name in assignment]
    faults, actions, records = [], [], [dict(calls=0, total_ms=0, max_ms=0) for _ in workers]
    start = time.perf_counter()
    try:
        for worker in workers:
            worker.spawn()
        for seat, worker in enumerate(workers):
            loaded = worker.finish_load(5)
            if not loaded["ok"]:
                raise RuntimeError("worker load failed: " + str(loaded))
        base = fixture.get("base") or (example_map() if fixture["map_seed"] is None else random_map(fixture["map_seed"]))
        game = Referee(base, rules=RULES, start_token=fixture["token"])
        while not game.over():
            chosen = []
            for seat, worker in enumerate(workers):
                result = worker.act(game.observation(seat + 1), game.turn, TIMING)
                rec = records[seat]
                rec["calls"] += 1
                ms = result.get("ms") or 0
                rec["total_ms"] += ms
                rec["max_ms"] = max(rec["max_ms"], ms)
                if result["status"] != "ok":
                    faults.append(dict(turn=game.turn, seat=seat, source=assignment[seat],
                                       status=result["status"], ms=ms, error=result.get("error")))
                chosen.append(result["used"])
            actions.append(chosen)
            game.step(chosen)
        return dict(candidate=candidate["path"], fixture=fixture["id"], focal_seat=fixture["seat"],
                    map_index=fixture["map_index"], assignment=assignment,
                    scores=game.score, pw=[3 * p for p in pairwise(game.score)],
                    focal_pw=3 * pairwise(game.score)[fixture["seat"]],
                    focal_score=game.score[fixture["seat"]],
                    timing=records, faults=faults, actions=actions,
                    elapsed_s=time.perf_counter() - start)
    finally:
        for worker in workers:
            worker.close()


def summaries(games):
    output = {}
    for name in sorted({g["candidate"] for g in games}):
        rows = [g for g in games if g["candidate"] == name]
        fault = [f for g in rows for f in g["faults"]]
        own = [g["timing"][g["focal_seat"]] for g in rows]
        output[name] = dict(games=len(rows), mean_pw=sum(g["focal_pw"] for g in rows)/len(rows),
                            mean_score=sum(g["focal_score"] for g in rows)/len(rows),
                            faults=len(fault), focal_faults=sum(f["source"] == name for f in fault),
                            max_ms=max(t["max_ms"] for t in own),
                            mean_ms=sum(t["total_ms"] for t in own)/sum(t["calls"] for t in own))
    return dict(sorted(output.items(), key=lambda item: -item[1]["mean_pw"]))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", required=True)
    parser.add_argument("--sources", nargs="+", required=True)
    parser.add_argument("--workers", type=int, default=2)
    args = parser.parse_args()
    registration = register(args.sources, args.stage)
    names = set(args.sources) | {n for f in registration["fixtures"] for n in f["opponents"]}
    source_hashes = {n: digest(CANDIDATES/n) for n in names}
    registration["opponent_hashes"] = source_hashes
    path = VALIDATION/(args.stage+"_results.json")
    if path.exists():
        raise ValueError("results already exist; never silently overwrite a consumed test")
    jobs = [(c, f) for c in registration["sources"] for f in registration["fixtures"]]
    start, games = time.perf_counter(), []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = [pool.submit(game_job, c, f) for c, f in jobs]
        for future in as_completed(futures):
            games.append(future.result())
            if len(games) % 16 == 0 or len(games) == len(jobs):
                print("%s: %d/%d games, %.1fs" % (args.stage,len(games),len(jobs),time.perf_counter()-start),flush=True)
    for name, expected in source_hashes.items():
        if digest(CANDIDATES/name) != expected:
            raise RuntimeError("source changed during measurement: " + name)
    if digest(HERE/"vendor_harness/referee.py") != registration["referee_sha256"]:
        raise RuntimeError("referee changed during measurement")
    if digest(Path(__file__)) != registration["benchmark_sha256"]:
        raise RuntimeError("measurement tool changed during run")
    summary = summaries(games)
    result = dict(registration=registration, summary=summary, games=sorted(games,key=lambda g:(g["candidate"],g["fixture"])),elapsed_s=time.perf_counter()-start,
                  caveat="Conditional on this finite frozen field and map generator. Screening is descriptive; confirmation is fresh but cannot prove universal strongest play. Actual process-isolated 200ms deadlines enforced. Public inputs only; timing is measured inside workers.")
    if len(summary) == 2 and args.stage.startswith("confirm"):
        a,b=summary
        aa={g["fixture"]:g for g in games if g["candidate"]==a}
        bb={g["fixture"]:g for g in games if g["candidate"]==b}
        maps={}
        for k,g in aa.items():maps.setdefault(g["map_index"],[]).append(g["focal_pw"]-bb[k]["focal_pw"])
        diffs=[sum(x)/len(x) for x in maps.values()]
        rng=random.Random(202611080351)
        boot=sorted(sum(rng.choice(diffs) for _ in diffs)/len(diffs) for _ in range(10000))
        result["paired_difference"]=dict(first=a,second=b,mean=sum(diffs)/len(diffs),map_clusters=len(diffs),bootstrap_95=[boot[249],boot[9749]])
    path.write_text(json.dumps(result,indent=2)+"\n",encoding="utf8")
    print(json.dumps(summary,indent=2),flush=True)
    if "paired_difference" in result:print(json.dumps(result["paired_difference"]),flush=True)


if __name__ == "__main__":
    main()
