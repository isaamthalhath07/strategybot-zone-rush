"""Resumable CPU evolution of the actual bot, with fresh public-input rivals.

Discovery/confirmation controls are EXTRA games, not the planned 2m campaign.
Every action sees only an independently copied four-field starter View. This is
a fast trusted-code evaluator, not the separate process-isolated promotion gate.
"""
import argparse
import copy
from concurrent.futures import ProcessPoolExecutor, as_completed
import hashlib
import json
import math
import os
from pathlib import Path
import random
import time

from evolution.genomes import GenomeSpace, digest
from evolution.maps import generate, seat_token
from evolution.opponents import Rival
from tests import reference_engine as engine

ROOT = Path(__file__).resolve().parents[1]
FORMAT = "zone-rush-existing-policy-evolution/1"
_CODE = {}


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf8")


def signature(v):
    return (v.bot_id, v.is_priority_token, tuple(v.legal_actions),
            tuple((c.occupant, c.owner, c.is_upgraded, c.is_home, c.is_frozen, c.base_points)
                  for row in v.board for c in row))


def namespace(path, expected):
    path = Path(path)
    body = path.read_bytes()
    if digest(body) != expected:
        raise ValueError("Worker source hash mismatch")
    if expected not in _CODE:
        _CODE[expected] = compile(body, str(path), "exec")
    ns = {"__name__": "_trusted_evolution_player", "__file__": str(path)}
    exec(_CODE[expected], ns)  # Only locally pinned code; never code from results.
    return ns


def init_worker():
    # Keep the worker independent of parent module state, including resume runs.
    _CODE.clear()


def opponent(spec, sources):
    family = spec["family"]
    if family in ("planner", "research", "racer", "blocker"):
        source = sources[family]
        ns = namespace(source["path"], source["sha256"])
        if family in ("planner", "research"):
            ns["CONFIG"] = dict(spec["genes"])
        else:
            cls = ns["RacerBot" if family == "racer" else "BlockerBot"]
            ns["_CONSOLIDATED_PLAYERS"][spec["seat"]+1] = cls(seed=spec["seed"])
        return ns["act"], ns
    player = Rival(spec)
    return player.act, None


def play_game(candidate, fixture, sources):
    started = time.perf_counter()
    focal_ns = namespace(candidate["path"], candidate["sha256"])
    players, namespaces = [], []
    by_seat = {spec["seat"]: spec for spec in fixture["opponents"]}
    for seat in range(4):
        if seat == fixture["seat"]:
            players.append(focal_ns["act"])
            namespaces.append(focal_ns)
        else:
            act, ns = opponent(by_seat[seat], sources)
            players.append(act)
            namespaces.append(ns)
    game = engine.Game(base=fixture["base"], start_token=fixture["token"], rules={"catch_requires_stay": True})
    actions, timing = [], [{"calls": 0, "total_ms": 0.0, "max_ms": 0.0,
                           "first_ms": 0.0, "regular_max_ms": 0.0} for _ in range(4)]
    while not game.over():
        chosen = []
        for seat, view in enumerate(game.views()):
            view = copy.deepcopy(view)
            if set(view.__slots__) != {"board", "bot_id", "is_priority_token", "legal_actions"}:
                raise ValueError("Actor observation contract changed")
            before = signature(view)
            call_start = time.perf_counter()
            action = players[seat](view)
            ms = (time.perf_counter()-call_start)*1000
            rec = timing[seat]
            rec["calls"] += 1
            rec["total_ms"] += ms
            rec["max_ms"] = max(rec["max_ms"], ms)
            if game.turn == 1:
                rec["first_ms"] = ms
            else:
                rec["regular_max_ms"] = max(rec["regular_max_ms"], ms)
            if action not in view.legal_actions or signature(view) != before:
                raise ValueError("Illegal action or input mutation")
            if ms > (2000 if game.turn == 1 else 200):
                raise ValueError("Decision deadline exceeded; reject this comparison")
            ns = namespaces[seat]
            if ns and (ns.get("_input_failures", 0) or ns.get("_policy_failures", 0)):
                raise ValueError("Policy used a hidden failure fallback")
            # Referee-only oracle audit AFTER the public-input decision. Private
            # counters never reach an actor, candidate genome, or search feature.
            memory = ns.get("_history", {}).get(seat+1, {}) if ns else {}
            if "cooldown_possible" in memory:
                if (memory.get("inference_failures", 0) or memory["progress"] != game.prog[seat]
                        or memory["scores"][1:] != game.score
                        or any(game.cd[i] not in memory["cooldown_possible"][i+1] for i in range(4))):
                    raise ValueError("Public-history tracker lost referee-consistent possibilities")
            chosen.append(action)
        actions.append(chosen)
        game.step(chosen)
    seat = fixture["seat"]
    pw = sum(1 if game.score[seat] > other else 0.5 if game.score[seat] == other else 0
             for j, other in enumerate(game.score) if j != seat)
    return dict(candidate=candidate["sha256"], fixture=fixture["id"], map_id=fixture["map_id"], focal_seat=seat,
                field=fixture["field"], scores=game.score, focal_pw=pw, focal_score=game.score[seat],
                opponent_ids=[s["id"] for s in fixture["opponents"]], actions=actions,
                timing=timing, faults=[], elapsed_s=time.perf_counter()-started)


def verify_row(row, candidate, fixture):
    if row["candidate"] != candidate["sha256"] or row["fixture"] != fixture["id"]:
        raise ValueError("Result belongs to another registered task")
    if row["map_id"] != fixture["map_id"] or row["field"] != fixture["field"] or row["focal_seat"] != fixture["seat"]:
        raise ValueError("Result map/field mismatch")
    if row["opponent_ids"] != [s["id"] for s in fixture["opponents"]] or row["faults"]:
        raise ValueError("Opponent identities changed or faults occurred")
    if len(row["actions"]) != 80 or any(len(a) != 4 for a in row["actions"]):
        raise ValueError("Incomplete game")
    g = engine.Game(base=fixture["base"], start_token=fixture["token"], rules={"catch_requires_stay": True})
    for actions in row["actions"]:
        if any(action not in g.legal(i) for i, action in enumerate(actions)):
            raise ValueError("Recorded illegal action")
        g.step(actions)
    seat = fixture["seat"]
    pw = sum(1 if g.score[seat] > x else 0.5 if g.score[seat] == x else 0 for i, x in enumerate(g.score) if i != seat)
    if row["scores"] != g.score or row["focal_pw"] != pw or row["focal_score"] != g.score[seat]:
        raise ValueError("Score does not replay")
    if len(row["timing"]) != 4:
        raise ValueError("Invalid callback records")
    for timing in row["timing"]:
        if type(timing["calls"]) is not int or timing["calls"] != 80:
            raise ValueError("Invalid callback count")
        for key in ("max_ms", "total_ms", "first_ms", "regular_max_ms"):
            if type(timing[key]) not in (float, int) or not math.isfinite(timing[key]) or timing[key] < 0:
                raise ValueError("Invalid callback duration")
        if (timing["first_ms"] > 2000 or timing["regular_max_ms"] > 200
                or timing["max_ms"] != max(timing["first_ms"], timing["regular_max_ms"])
                or timing["total_ms"] < timing["max_ms"]):
            raise ValueError("Invalid or late callback record")


def summarize(rows, candidates):
    output = []
    for candidate in candidates:
        games = [r for r in rows if r["candidate"] == candidate["sha256"]]
        fields = {}
        for field in sorted({r["field"] for r in games}):
            group = [r for r in games if r["field"] == field]
            fields[field] = sum(r["focal_pw"] for r in group)/len(group)
        output.append(dict(name=candidate["name"], sha256=candidate["sha256"], games=len(games),
                           mean_pw=sum(r["focal_pw"] for r in games)/len(games),
                           mean_score=sum(r["focal_score"] for r in games)/len(games), fields=fields,
                           max_ms=max(r["timing"][r["focal_seat"]]["max_ms"] for r in games),
                           all_player_max_ms=max(t["max_ms"] for r in games for t in r["timing"])))
    return sorted(output, key=lambda r: (-r["mean_pw"], -r["mean_score"], r["sha256"]))


def paired(rows, first, second):
    a = {r["fixture"]: r for r in rows if r["candidate"] == first}
    b = {r["fixture"]: r for r in rows if r["candidate"] == second}
    groups = {}
    for key in sorted(a.keys() & b.keys()):
        groups.setdefault(a[key]["map_id"], []).append(a[key]["focal_pw"]-b[key]["focal_pw"])
    means = [sum(v)/len(v) for _, v in sorted(groups.items())]
    if not means:
        raise ValueError("No paired comparison")
    rng = random.Random(202611082101)
    boot = sorted(sum(rng.choice(means) for _ in means)/len(means) for _ in range(10000))
    return dict(first=first, second=second, maps=len(means), games=len(a.keys() & b.keys()),
                mean=sum(means)/len(means), bootstrap_95=[boot[249], boot[9749]],
                caveat="Descriptive map-cluster bootstrap; selection and repeated testing require fresh independent confirmation.")


def source_entry(path):
    return dict(path=str(path.resolve()), sha256=digest(path.read_bytes()))


def create_registration(directory, seed, map_count, population, confirmation=False, selected=None):
    directory.mkdir(parents=True, exist_ok=False)
    body = (ROOT/"bot.py").read_bytes()
    space = GenomeSpace(body)
    sources = {name: source_entry(ROOT/path) for name, path in {
        "planner": "bot.py", "research": "tester_bots/research_alternative.py",
        "racer": "tester_bots/racer.py", "blocker": "tester_bots/blocker.py"}.items()}
    candidates, seen = [], set()
    genes = [("incumbent", space.genes)]
    if selected:
        genes.append(("discovery_finalist", GenomeSpace(Path(selected).read_bytes()).genes))
    else:
        research = GenomeSpace((ROOT/"tester_bots/research_alternative.py").read_bytes()).genes
        for i in range(1, population):
            if i % 7 == 0:
                genome = space.mutate(research, seed+i, scale=0.05, grouped=True)
            elif i % 5 == 0:
                genome = space.crossover(space.genes, research, seed+i)
            else:
                genome = space.mutate(space.genes, seed+i, scale=0.05 if i % 2 else 0.12, grouped=(i % 3 == 0))
            genes.append(("mutation_%02d" % i, genome))
    for name, genome in genes:
        exported = space.export(genome)
        sha = digest(exported)
        if sha in seen:
            continue
        seen.add(sha)
        path = directory/(name+".py")
        path.write_bytes(exported)
        candidates.append(dict(name=name, path=str(path.resolve()), sha256=sha, genes=genome))
    excluded = []
    for path in (ROOT/"validation/official").glob("*_spec.json"):
        excluded.extend(f["base"] for f in json.loads(path.read_text())["fixtures"])
    for path in directory.parent.glob("*/registration.json"):
        excluded.extend(f["base"] for f in json.loads(path.read_text())["fixtures"])
    maps = generate(map_count, seed, excluded)
    rng = random.Random(seed ^ 0x47E972)
    fields = {
        "economic": ("planner", "planner", "farmer"),
        "independent": ("racer", "blocker", "raider"),
        "erratic": ("wanderer", "mixed", "planner"),
        "pressure": ("interceptor", "feinter", "research") if confirmation else ("raider", "farmer", "blocker"),
    }
    fixtures = []
    research_genes = GenomeSpace((ROOT/"tester_bots/research_alternative.py").read_bytes()).genes
    for index, board in enumerate(maps):
        for episode in range(16):
            seat, token = seat_token(index, episode)
            # Across four maps each field gets every seat/token crossing. Using
            # +index here would permanently confound field with token offset.
            field = list(fields)[(episode//4+2*index) % len(fields)]
            families = list(fields[field])
            rng.shuffle(families)
            specs = []
            for rival_seat in range(4):
                if rival_seat == seat:
                    continue
                family = families.pop()
                spec = dict(seat=rival_seat, family=family, seed=rng.getrandbits(63),
                            epsilon=rng.uniform(0.01, 0.45), commitment=rng.uniform(0.2, 0.95))
                if family in ("planner", "research"):
                    base_genes = research_genes if family == "research" else space.genes
                    spec["genes"] = space.mutate(base_genes, spec["seed"], scale=0.16, grouped=True)
                spec["id"] = digest(canonical(dict(campaign=seed, map=board["id"], episode=episode, spec=spec)))
                specs.append(spec)
            fixture = dict(map_id=board["id"], map_family=board["family"], base=board["base"],
                           seat=seat, token=token, episode=episode, field=field, opponents=specs)
            fixture["id"] = digest(canonical(fixture))
            fixtures.append(fixture)
    guards = {str(path.resolve()): digest(path.read_bytes()) for path in (
        ROOT/"evolution/runner.py", ROOT/"evolution/maps.py", ROOT/"evolution/genomes.py",
        ROOT/"evolution/opponents.py", ROOT/"tests/reference_engine.py")}
    registration = dict(format=FORMAT, role="confirmation" if confirmation else "discovery",
                        counting="Extra evolutionary controls, outside the primary 2m budget. No BMCTS audits claimed.",
                        seed=seed, rules={"catch_requires_stay": True}, candidates=candidates,
                        sources=sources, fixtures=fixtures, guards=guards, promotion_allowed=False)
    path = directory/"registration.json"
    path.write_text(json.dumps(registration, indent=2)+"\n", encoding="utf8", newline="\n")
    (directory/"registration.sha256").write_text(digest(path.read_bytes())+"\n", encoding="ascii")
    return registration


def evaluate(directory, workers):
    registration_path = directory/"registration.json"
    registration_body = registration_path.read_bytes()
    if digest(registration_body) != (directory/"registration.sha256").read_text().strip():
        raise ValueError("Registration fingerprint changed")
    registration = json.loads(registration_body)
    if registration["format"] != FORMAT:
        raise ValueError("Unsupported registration")
    guards = dict(registration["guards"])
    guards.update({s["path"]: s["sha256"] for s in registration["sources"].values()})
    guards.update({s["path"]: s["sha256"] for s in registration["candidates"]})
    for path, sha in guards.items():
        if digest(Path(path).read_bytes()) != sha:
            raise ValueError("Registered code changed: " + path)
    candidates = {c["sha256"]: c for c in registration["candidates"]}
    fixtures = {f["id"]: f for f in registration["fixtures"]}
    if len(candidates) != len(registration["candidates"]) or len(fixtures) != len(registration["fixtures"]):
        raise ValueError("Duplicate registered tasks")
    for fixture in fixtures.values():
        content = {key: value for key, value in fixture.items() if key != "id"}
        if digest(canonical(content)) != fixture["id"] or digest(bytes(fixture["base"])) != fixture["map_id"]:
            raise ValueError("Fixture identity mismatch")
    rows, done = [], set()
    result_path = directory/"games.jsonl"
    if result_path.exists():
        body = result_path.read_bytes()
        if body and not body.endswith(b"\n"):
            # A crash can tear the final append. Preserve it before retrying its
            # task; a malformed complete line is always an error.
            split = body.rfind(b"\n")+1
            recovery = directory/("interrupted-tail-"+digest(body[split:])+".bin")
            recovery.write_bytes(body[split:])
            with result_path.open("r+b") as handle:
                handle.truncate(split)
            body = body[:split]
        for line in body.decode("utf8").splitlines():
            row = json.loads(line)
            key = row["candidate"], row["fixture"]
            if key in done:
                raise ValueError("Duplicate completed task")
            verify_row(row, candidates[key[0]], fixtures[key[1]])
            rows.append(row)
            done.add(key)
    pending = [(c, f) for c in candidates.values() for f in fixtures.values() if (c["sha256"], f["id"]) not in done]
    started = time.perf_counter()
    with result_path.open("a", encoding="utf8", newline="\n") as handle:
        with ProcessPoolExecutor(max_workers=workers, initializer=init_worker) as pool:
            futures = {pool.submit(play_game, c, f, registration["sources"]): (c, f) for c, f in pending}
            for future in as_completed(futures):
                candidate, fixture = futures[future]
                row = future.result()  # Exceptions invalidate evaluation; no silent STAY fallback.
                verify_row(row, candidate, fixture)
                handle.write(canonical(row).decode("utf8")+"\n")
                handle.flush()
                os.fsync(handle.fileno())
                rows.append(row)
                if len(rows) % 32 == 0 or len(rows) == len(candidates)*len(fixtures):
                    print("Evolution %d/%d complete (%.1fs)" % (len(rows), len(candidates)*len(fixtures), time.perf_counter()-started), flush=True)
    for path, sha in guards.items():
        if digest(Path(path).read_bytes()) != sha:
            raise ValueError("Code changed during evaluation: " + path)
    if registration_path.read_bytes() != registration_body:
        raise ValueError("Registration changed during evaluation")
    summary = summarize(rows, registration["candidates"])
    baseline = registration["candidates"][0]["sha256"]
    output = dict(registration_sha256=digest(registration_body), summary=summary,
                  paired=[paired(rows, c["sha256"], baseline) for c in registration["candidates"][1:]],
                  games_completed=len(rows), callbacks=sum(t["calls"] for r in rows for t in r["timing"]),
                  games_bmcts_audited=0, primary_campaign_games=0, promoted=False)
    (directory/"summary.json").write_text(json.dumps(output, indent=2)+"\n", encoding="utf8", newline="\n")
    print(json.dumps(output, indent=2), flush=True)
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=202611082201)
    parser.add_argument("--maps", type=int, default=8)
    parser.add_argument("--population", type=int, default=8)
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--selected", type=Path)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    if min(args.maps, args.population, args.workers) < 1 or args.workers > 24:
        parser.error("Positive sizes required; at most24 workers")
    directory = args.directory.resolve()
    if not args.resume:
        create_registration(directory, args.seed, args.maps, args.population,
                            confirmation=bool(args.selected), selected=args.selected)
    evaluate(directory, args.workers)


if __name__ == "__main__":
    main()
