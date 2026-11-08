"""Reproduce sampled evolutionary games with the real per-seat worker harness."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import gzip
import json
from pathlib import Path
import random

from evolution.genomes import GenomeSpace, digest
from evolution.runner import ROOT, canonical
from tools import benchmark

LEGAL_ORDER = ("STAY", "NORTH", "SOUTH", "WEST", "EAST", "SHIELD")
TIMING = dict(benchmark.DEFAULT_TIMING, load_s=5.0, hard_s=1.0)


def isolated_game(candidate, fixture, sources):
    assignment = list(fixture["opponents"])
    assignment.insert(fixture["seat"], candidate)
    workers = [benchmark.BotProcess(str(ROOT/sources[name]["path"])) for name in assignment]
    timing = dict(TIMING)
    calls, actions, faults = [0]*4, [], []
    measurements = [dict(calls=0, total_ms=0.0, max_ms=0.0, first_ms=0.0, regular_max_ms=0.0) for _ in range(4)]
    try:
        for worker in workers:
            worker.spawn()
        for worker in workers:
            if not worker.finish_load(timing["load_s"])["ok"]:
                raise ValueError("Worker failed to load")
        game = benchmark.Referee(fixture["base"], rules={"catch_requires_stay": True}, start_token=fixture["token"])
        while not game.over():
            chosen = []
            for seat, worker in enumerate(workers):
                public = game.observation(seat+1)
                # Action-list order is part of the supplied input. Match the
                # recorded fast View exactly; random policies map RNG indices
                # to different choices when the same legal SET is reordered.
                public["legal_actions"] = [a for a in LEGAL_ORDER if a in public["legal_actions"]]
                result = worker.act(public, game.turn, timing)
                calls[seat] += 1
                ms = result.get("ms") or 0.0
                rec = measurements[seat]
                rec["calls"] += 1
                rec["total_ms"] += ms
                rec["max_ms"] = max(rec["max_ms"], ms)
                if game.turn == 1:
                    rec["first_ms"] = ms
                else:
                    rec["regular_max_ms"] = max(rec["regular_max_ms"], ms)
                if result["status"] != "ok":
                    faults.append(dict(turn=game.turn, seat=seat, status=result["status"]))
                chosen.append(result["used"])
            actions.append(chosen)
            game.step(chosen)
        return dict(candidate=candidate, fixture=fixture["id"], actions=actions, scores=game.score,
                    faults=faults, calls=calls, timing=measurements)
    finally:
        for worker in workers:
            worker.close()


def run(round_directory, output_directory, count=8, workers=4):
    output_directory.mkdir(parents=True, exist_ok=False)
    registration = json.loads((round_directory/"registration.json").read_text())
    if digest((round_directory/"registration.json").read_bytes()) != (round_directory/"registration.sha256").read_text().strip():
        raise ValueError("Changed registration")
    fast = [json.loads(line) for line in (round_directory/"games.jsonl").read_text().splitlines()]
    # Balance fields explicitly. A fixed stride can accidentally select only
    # one field because fields and episodes repeat in structured blocks.
    fixture_list = registration["fixtures"]
    rng, fixtures = random.Random(202611082319), []
    groups = {field: [f for f in fixture_list if f["field"] == field]
              for field in sorted({f["field"] for f in fixture_list})}
    for group in groups.values():
        rng.shuffle(group)
    while len(fixtures) < min(count, len(fixture_list)):
        for group in groups.values():
            if group and len(fixtures) < min(count, len(fixture_list)):
                fixtures.append(group.pop())
    sources, exported_fixtures = [], []
    candidate_names = {}
    for candidate in registration["candidates"]:
        name = candidate["sha256"]
        path = Path(candidate["path"])
        if digest(path.read_bytes()) != name:
            raise ValueError("Changed candidate")
        sources.append(dict(name=name, path=path.relative_to(ROOT).as_posix(), sha256=name))
        candidate_names[name] = candidate["name"]
    seen = set()
    for fixture in fixtures:
        opponents = []
        for spec in sorted(fixture["opponents"], key=lambda s: s["seat"]):
            identity = spec["id"]
            opponents.append(identity)
            if identity in seen:
                continue
            seen.add(identity)
            family = spec["family"]
            if family in ("planner", "research", "racer", "blocker"):
                source = registration["sources"][family]
                body = Path(source["path"]).read_bytes()
                if digest(body) != source["sha256"]:
                    raise ValueError("Changed opponent source")
                if family in ("planner", "research"):
                    body = GenomeSpace(body).export(spec["genes"])
                else:
                    cls = "RacerBot" if family == "racer" else "BlockerBot"
                    body += ("\n_CONSOLIDATED_PLAYERS[%r] = %s(seed=%r)\n" % (spec["seat"]+1, cls, spec["seed"])).encode("utf8")
            else:
                body = (ROOT/"evolution/opponents.py").read_bytes()
                body += ("\n_EVOLUTION_PLAYER = Rival(%r)\ndef act(state):\n    return _EVOLUTION_PLAYER.act(state)\n" % spec).encode("utf8")
            path = output_directory/(identity+".py")
            path.write_bytes(body)
            sources.append(dict(name=identity, path=path.relative_to(ROOT).as_posix(), sha256=digest(body)))
        exported_fixtures.append(dict(id=fixture["id"], map_group=fixture["map_id"], field=fixture["field"],
                                      base=fixture["base"], seat=fixture["seat"], token=fixture["token"], opponents=opponents))
    spec = dict(id="evolution-process-isolation-equivalence", candidates=list(candidate_names),
                sources=sources, fixtures=exported_fixtures, rules={"catch_requires_stay": True})
    path = output_directory/"spec.json"
    path.write_text(json.dumps(spec, indent=2)+"\n", encoding="utf8", newline="\n")
    source_map = {s["name"]: s for s in sources}
    guards = dict(registration["guards"])
    guards.update({str(ROOT/s["path"]): s["sha256"] for s in sources})
    guards.update({str(p): digest(p.read_bytes()) for p in (
        Path(__file__), path, round_directory/"registration.json", round_directory/"registration.sha256",
        benchmark.VENDOR/"referee.py", benchmark.VENDOR/"worker.py")})
    for source_path, sha in guards.items():
        if digest(Path(source_path).read_bytes()) != sha:
            raise ValueError("Changed source before isolated verification")
    jobs = [(candidate, fixture) for candidate in candidate_names for fixture in exported_fixtures]
    with ThreadPoolExecutor(max_workers=workers) as pool:
        games = list(pool.map(lambda task: isolated_game(task[0], task[1], source_map), jobs))
    for source_path, sha in guards.items():
        if digest(Path(source_path).read_bytes()) != sha:
            raise ValueError("Changed source during isolated verification")
    result = dict(spec=spec, games=games, legal_order=list(LEGAL_ORDER),
                  helper_sha256=digest(Path(__file__).read_bytes()),
                  referee_sha256=digest((benchmark.VENDOR/"referee.py").read_bytes()),
                  worker_sha256=digest((benchmark.VENDOR/"worker.py").read_bytes()), timing=TIMING, guards=guards)
    with gzip.open(output_directory/"results.json.gz", "wt", encoding="utf8") as handle:
        json.dump(result, handle)
    lookup = {(row["candidate"], row["fixture"]): row for row in fast}
    for row in result["games"]:
        original = lookup[(row["candidate"], row["fixture"])]
        if row["actions"] != original["actions"] or row["scores"] != original["scores"] or row["faults"]:
            raise ValueError("Isolated worker behavior differs from evolutionary evaluator")
    report = dict(round_registration_sha256=digest((round_directory/"registration.json").read_bytes()),
                  games=len(result["games"]), callbacks=sum(sum(r["calls"]) for r in result["games"]),
                  exact_action_lists=sum(len(r["actions"]) for r in result["games"]), faults=0,
                  all_actions_and_scores_exact=True, new_strength_evidence=False,
                  matched_input_legal_order=list(LEGAL_ORDER), fields={field: sum(f["field"] == field for f in fixtures) for field in groups},
                  timing=TIMING, max_ms=max(t["max_ms"] for r in result["games"] for t in r["timing"]),
                  primary_campaign_games=0, bmcts_audits=0)
    (output_directory/"equivalence.json").write_bytes(canonical(report)+b"\n")
    print(json.dumps(report, indent=2), flush=True)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("round_directory", type=Path)
    parser.add_argument("output_directory", type=Path)
    parser.add_argument("--fixtures", type=int, default=8)
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    if args.fixtures < 1 or args.workers < 1:
        parser.error("Positive sizes required")
    run(args.round_directory.resolve(), args.output_directory.resolve(), args.fixtures, args.workers)


if __name__ == "__main__":
    main()
