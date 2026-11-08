"""Independent all-game audit. Never selects, edits, or promotes a candidate.

Replays physical states in TWO separately maintained referees and optionally
regenerates EVERY decision with fresh actors receiving only copied public Views.
This is trusted-source inspection/reproduction, not a security sandbox proof.
"""
import argparse
import ast
import copy
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import random
import time

from tests import reference_engine as engine
from evolution.opponents import Rival

ROOT = Path(__file__).resolve().parents[1]
INCUMBENT = "e8b3682d8b39d3fc4d22cdcd8927161290a90cd472d3ede4132ae716f8c6f8f5"
REFEREE_SHA = "f1125e8ceee664781827c670c0c4481da41a7ef41a4e5276d6b3b118274af337"
ENGINE_SHA = "8f7b89995cad0f724fb8ac7c7bc8311a6fa9b3b722f2204097031ba2333726f4"
_spec = importlib.util.spec_from_file_location("_independent_pinned_referee", ROOT/"simulator/vendor_harness/referee.py")
referee = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(referee)
_COMPILED = {}


def sha(body):
    return hashlib.sha256(body).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf8")


def strict_loads(body):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("Duplicate JSON key: " + key)
            result[key] = value
        return result

    def reject(value):
        raise ValueError("Nonfinite JSON number: " + value)

    return json.loads(body, object_pairs_hook=pairs, parse_constant=reject)


def check(condition, message):
    if not condition:
        raise ValueError(message)


def signature(view):
    return (view.bot_id, bool(view.is_priority_token), tuple(view.legal_actions),
            tuple((c.occupant, c.owner, c.is_upgraded, c.is_home, c.is_frozen, c.base_points)
                  for row in view.board for c in row))


def state_equal(game, official):
    for key in ("base", "owner", "upg", "home", "pos", "frozen", "cd", "prog", "score", "turn", "token"):
        check(getattr(game, key) == getattr(official, key), "Referee divergence: " + key)
    check(game.income == official.income(), "Referee divergence: income")
    for seat in range(4):
        check(set(game.legal(seat)) == set(official.legal(seat)), "Referee divergence: legal actions")


def player_namespace(entry):
    body = Path(entry["path"]).read_bytes()
    check(sha(body) == entry["sha256"], "Actor source changed")
    code = _COMPILED.get(entry["sha256"])
    if code is None:
        code = compile(body, entry["path"], "exec")
        _COMPILED[entry["sha256"]] = code
    namespace = {"__name__": "_independent_replay_actor", "__file__": entry["path"]}
    exec(code, namespace)
    return namespace


def make_actors(candidate, fixture, sources):
    actors, namespaces = [], []
    specs = {spec["seat"]: spec for spec in fixture["opponents"]}
    for seat in range(4):
        if seat == fixture["seat"]:
            ns = player_namespace(candidate)
            actors.append(ns["act"])
            namespaces.append(ns)
            continue
        spec = specs[seat]
        family = spec["family"]
        if family in ("planner", "research", "racer", "blocker"):
            ns = player_namespace(sources[family])
            if family in ("planner", "research"):
                ns["CONFIG"] = copy.deepcopy(spec["genes"])
            else:
                name = "RacerBot" if family == "racer" else "BlockerBot"
                ns["_CONSOLIDATED_PLAYERS"][seat+1] = ns[name](seed=spec["seed"])
            actors.append(ns["act"])
            namespaces.append(ns)
        else:
            actor = Rival(copy.deepcopy(spec))
            actors.append(actor.act)
            namespaces.append(None)
    return actors, namespaces


def audit_game(candidate, fixture, sources, row, regenerate):
    check(row["candidate"] == candidate["sha256"] and row["fixture"] == fixture["id"], "Task identity mismatch")
    check(row["map_id"] == fixture["map_id"] and row["focal_seat"] == fixture["seat"] and row["field"] == fixture["field"], "Task metadata mismatch")
    check(row["faults"] == [], "Recorded actor fault")
    check(row["opponent_ids"] == [s["id"] for s in fixture["opponents"]], "Opponent identities mismatch")
    check(len(row["actions"]) == 80 and all(len(a) == 4 for a in row["actions"]), "Incomplete actions")
    check(len(row["timing"]) == 4, "Missing timing records")
    for rec in row["timing"]:
        check(type(rec["calls"]) is int and rec["calls"] == 80, "Missing callbacks")
        for key in ("first_ms", "regular_max_ms", "max_ms", "total_ms"):
            check(type(rec[key]) in (int, float) and math.isfinite(rec[key]) and rec[key] >= 0, "Invalid duration")
        check(rec["first_ms"] <= 2000 and rec["regular_max_ms"] <= 200, "Late recorded decision")
        check(rec["max_ms"] == max(rec["first_ms"], rec["regular_max_ms"]), "Inconsistent maximum timing")
        check(rec["max_ms"] <= rec["total_ms"] <= rec["first_ms"] + 79*rec["regular_max_ms"] + 1e-6,
              "Inconsistent total timing")
    g = engine.Game(base=fixture["base"], start_token=fixture["token"], rules={"catch_requires_stay": True})
    official = referee.Referee(fixture["base"], start_token=fixture["token"], rules={"catch_requires_stay": True})
    actors, namespaces = make_actors(candidate, fixture, sources) if regenerate else (None, None)
    state_equal(g, official)
    callbacks, oracle_checks = 0, 0
    for turn, recorded in enumerate(row["actions"], 1):
        if regenerate:
            views = g.views()  # All four views are from the same PRE-action turn.
            for seat, raw_view in enumerate(views):
                public = copy.deepcopy(raw_view)
                check(set(public.__slots__) == {"board", "bot_id", "is_priority_token", "legal_actions"}, "Extra actor inputs")
                before = signature(public)
                action = actors[seat](public)
                check(signature(public) == before, "Actor mutated public input")
                check(action == recorded[seat], "Recorded decision does not regenerate: turn %s seat %s" % (turn, seat+1))
                ns = namespaces[seat]
                if ns is not None:
                    check(not ns.get("_input_failures", 0) and not ns.get("_policy_failures", 0), "Silent fallback")
                    memory = ns.get("_history", {}).get(seat+1, {})
                    if "cooldown_possible" in memory:
                        # Referee truth is used solely by the auditor AFTER act.
                        check(not memory.get("inference_failures", 0), "Inference fallback")
                        check(memory["progress"] == g.prog[seat] and memory["scores"][1:] == g.score, "Incorrect public memory")
                        check(all(g.cd[i] in memory["cooldown_possible"][i+1] for i in range(4)), "Lost feasible cooldown")
                        oracle_checks += 1
                callbacks += 1
        for seat, action in enumerate(recorded):
            check(type(action) is str and action in g.legal(seat) and action in official.legal(seat), "Illegal recorded action")
        g.step(recorded)
        official.step(recorded)
        state_equal(g, official)
    check(g.over() and official.over(), "Not a full game")
    check(all(type(s) is int for s in row["scores"]) and row["scores"] == g.score, "Final score mismatch")
    seat = fixture["seat"]
    pw = sum(1 if g.score[seat] > x else .5 if g.score[seat] == x else 0 for i, x in enumerate(g.score) if i != seat)
    check(row["focal_pw"] == pw and row["focal_score"] == g.score[seat], "Round1 result mismatch")
    return dict(callbacks_regenerated=callbacks, public_memory_oracles=oracle_checks)


def stripped_tree(body):
    tree = ast.parse(body)
    config = None
    kept = []
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "CONFIG" for t in node.targets):
            check(config is None, "Multiple CONFIG assignments")
            config = ast.literal_eval(node.value)
        else:
            kept.append(node)
    tree.body = kept
    return ast.dump(tree), config


def audit_registration(directory):
    body = (directory/"registration.json").read_bytes()
    check(sha(body) == (directory/"registration.sha256").read_text().strip(), "Registration fingerprint mismatch")
    reg = strict_loads(body)
    check(reg["format"] == "zone-rush-existing-policy-evolution/1", "Unknown registration format")
    check(reg["rules"] == {"catch_requires_stay": True}, "Unexpected registered rules")
    check(reg["promotion_allowed"] is False, "Research stage may not promote")
    checks = dict(reg["guards"])
    checks.update({s["path"]: s["sha256"] for s in reg["sources"].values()})
    checks.update({c["path"]: c["sha256"] for c in reg["candidates"]})
    for path, expected in checks.items():
        check(sha(Path(path).read_bytes()) == expected, "Pinned source changed: " + path)
    base_body = (ROOT/"bot.py").read_bytes()
    check(sha(base_body) == INCUMBENT, "Champion changed during research")
    reference_ast, _ = stripped_tree(base_body)
    check(reg["candidates"][0]["sha256"] == INCUMBENT, "Incumbent control missing")
    candidate_ids = []
    for candidate in reg["candidates"]:
        code_ast, genes = stripped_tree(Path(candidate["path"]).read_bytes())
        check(code_ast == reference_ast and genes == candidate["genes"], "Candidate changed code outside CONFIG")
        candidate_ids.append(candidate["sha256"])
    check(len(set(candidate_ids)) == len(candidate_ids), "Duplicate candidate")
    fixture_ids, opponent_ids, boards = set(), set(), {}
    crossing = Counter()
    by_map = {}
    for fixture in reg["fixtures"]:
        check(fixture["id"] == sha(canonical({k: v for k, v in fixture.items() if k != "id"})), "Fixture fingerprint mismatch")
        check(fixture["id"] not in fixture_ids, "Duplicate fixture")
        fixture_ids.add(fixture["id"])
        base = fixture["base"]
        check(len(base) == 64 and all(type(v) is int and 1 <= v <= 3 for v in base), "Invalid map values")
        check(all(base[r*8+c] == base[r*8+7-c] == base[(7-r)*8+c] for r in range(8) for c in range(8)), "Unmirrored map")
        check(sha(bytes(base)) == fixture["map_id"], "Map content identity mismatch")
        check(type(fixture["seat"]) is int and 0 <= fixture["seat"] < 4 and type(fixture["token"]) is int and 1 <= fixture["token"] <= 4, "Invalid seat/token")
        boards[fixture["map_id"]] = tuple(base)
        by_map.setdefault(fixture["map_id"], Counter()).update([(fixture["seat"], fixture["token"])])
        crossing.update([(fixture["field"], fixture["seat"], fixture["token"])])
        specs = fixture["opponents"]
        check(len(specs) == 3 and {s["seat"] for s in specs} == set(range(4))-{fixture["seat"]}, "Invalid rival seats")
        for spec in specs:
            expected = sha(canonical(dict(campaign=reg["seed"], map=fixture["map_id"], episode=fixture["episode"], spec={k: v for k, v in spec.items() if k != "id"})))
            check(spec["id"] == expected and spec["id"] not in opponent_ids, "Duplicate or changed opponent instance")
            opponent_ids.add(spec["id"])
    check(all(len(c) == 16 and set(c.values()) == {1} for c in by_map.values()), "Within-map seat/token imbalance")
    if len(boards) % 4 == 0:
        check(len(crossing) == 64 and len(set(crossing.values())) == 1, "Field/seat/token confounding")
    return reg, boards, opponent_ids


def audit_stage(directory, workers=6, regenerate=True):
    directory = Path(directory).resolve()
    started = time.perf_counter()
    reg, boards, opponent_ids = audit_registration(directory)
    summary = strict_loads((directory/"summary.json").read_bytes())
    check(summary["registration_sha256"] == sha((directory/"registration.json").read_bytes()), "Summary registration mismatch")
    check(summary["promoted"] is False and summary["primary_campaign_games"] == 0 and summary["games_bmcts_audited"] == 0, "False promotion/campaign/search credit")
    candidates = {c["sha256"]: c for c in reg["candidates"]}
    fixtures = {f["id"]: f for f in reg["fixtures"]}
    raw_rows = (directory/"games.jsonl").read_bytes()
    check(raw_rows.endswith(b"\n"), "Interrupted trailing result")
    rows = [strict_loads(line) for line in raw_rows.splitlines()]
    keys = [(r["candidate"], r["fixture"]) for r in rows]
    expected = {(c, f) for c in candidates for f in fixtures}
    check(len(keys) == len(set(keys)) and set(keys) == expected, "Incomplete/duplicate/foreign result tasks")
    totals = Counter()
    with ProcessPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(audit_game, candidates[r["candidate"]], fixtures[r["fixture"]], reg["sources"], r, regenerate) for r in rows]
        for index, future in enumerate(as_completed(futures), 1):
            totals.update(future.result())
            if index % 128 == 0 or index == len(futures):
                print("Independent audit %s: %d/%d games" % (directory.name, index, len(futures)), flush=True)
    check(summary["games_completed"] == len(rows) and summary["callbacks"] == len(rows)*320, "Incorrect totals")
    for item in summary["summary"]:
        group = [row for row in rows if row["candidate"] == item["sha256"]]
        check(item["games"] == len(group), "Incorrect per-candidate count")
        check(item["mean_pw"] == sum(r["focal_pw"] for r in group)/len(group), "Incorrect mean pairwise score")
        check(item["mean_score"] == sum(r["focal_score"] for r in group)/len(group), "Incorrect mean game score")
        check(item["max_ms"] == max(r["timing"][r["focal_seat"]]["max_ms"] for r in group), "Incorrect focal timing")
        for field, mean in item["fields"].items():
            subgroup = [row for row in group if row["field"] == field]
            check(mean == sum(r["focal_pw"] for r in subgroup)/len(subgroup), "Incorrect field mean")
    # Pre/post source verification prevents a mid-audit version mixture.
    audit_registration(directory)
    return dict(directory=str(directory), role=reg["role"], registration_sha256=sha((directory/"registration.json").read_bytes()),
                transcripts_sha256=sha(raw_rows), games=len(rows), turns=len(rows)*80, recorded_callbacks=len(rows)*320,
                regenerated_callbacks=totals["callbacks_regenerated"], public_memory_oracles=totals["public_memory_oracles"],
                candidates=len(candidates), maps=len(boards), unique_opponent_instances=len(opponent_ids),
                zero_faults=True, two_referees_every_turn=True, field_seat_token_balance=True,
                summary_recomputed=True, map_ids=sorted(boards), opponent_ids=sorted(opponent_ids),
                elapsed_s=time.perf_counter()-started, summary=summary)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directories", nargs="+", type=Path)
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--physics-only", action="store_true")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if not 1 <= args.workers <= 24:
        parser.error("Workers must be1..24")
    check(sha((ROOT/"simulator/vendor_harness/referee.py").read_bytes()) == REFEREE_SHA, "Vendor referee pin changed")
    check(sha((ROOT/"tests/reference_engine.py").read_bytes()) == ENGINE_SHA, "Independent engine pin changed")
    results = [audit_stage(path, args.workers, not args.physics_only) for path in args.directories]
    seen_maps, seen_opponents = set(), set()
    for result in results:
        check(not seen_maps.intersection(result["map_ids"]), "Holdout map reused")
        check(not seen_opponents.intersection(result["opponent_ids"]), "Holdout opponent instance reused")
        seen_maps.update(result.pop("map_ids"))
        seen_opponents.update(result.pop("opponent_ids"))
    reasons = ["Process-isolated promotion gate has not evaluated any mutant.",
               "Research is finite; distribution coverage and generalization are unproven."]
    for result in results:
        if result["role"] == "confirmation":
            for comparison in result["summary"]["paired"]:
                if comparison["mean"] <= 0 or comparison["bootstrap_95"][0] <= 0:
                    reasons.append("Confirmation does not establish an improvement over incumbent.")
    output = dict(format="zone-rush-independent-oversight/1", validity="passed_for_recorded_games",
                  promotion="BLOCKED", promotion_blockers=sorted(set(reasons)),
                  games=sum(r["games"] for r in results), turns=sum(r["turns"] for r in results),
                  recorded_callbacks=sum(r["recorded_callbacks"] for r in results),
                  regenerated_callbacks=sum(r["regenerated_callbacks"] for r in results),
                  primary_campaign_games=0, games_bmcts_audited=0, incumbent_sha256=INCUMBENT,
                  referee_sha256=REFEREE_SHA, independent_engine_sha256=ENGINE_SHA,
                  auditor_sha256=sha(Path(__file__).read_bytes()), results=results,
                  caveat="All recorded games checked, not proof of zero bugs or all possible opponents. Trusted-source actor replay is not an adversarial code sandbox.")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2)+"\n", encoding="utf8", newline="\n")
    print(json.dumps({k: v for k, v in output.items() if k != "results"}, indent=2), flush=True)


if __name__ == "__main__":
    main()
