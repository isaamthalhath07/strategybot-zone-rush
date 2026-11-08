"""Independent audit of explicitly approved macro-clock experiments.

Every game/turn replays in two referees. Focal and deterministic rival decisions
regenerate from public input. Wall-clock/random-seeded rival implementations
remain covered by original process logs plus complete physical replay.
"""
import argparse
import ast
import copy
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
import gzip
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import random
import time

from tests import reference_engine as engine

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
PARENT = "e8b3682d8b39d3fc4d22cdcd8927161290a90cd472d3ede4132ae716f8c6f8f5"
BUILDER = "9f088b7760ff853a648ec5e143253e7e3f65b60506af5e8f0ddbd921c73ea33f"
APPROVED = {
    "current_depth3": PARENT,
    "arrival_depth3": "801e12ab60631ec1c16bf358a9d3d2db96f9a1e572b51f0f18e902f317881134",
    "current_depth2": "747b732ef32a0a50e0ea76dd16b3f89f018ffced3ae99f3e211c09c7fce1d4ab",
    "arrival_depth2": "3a64f9d476a1021349a3aef2088e97995eacabbe9327e008e62305c5c5aa3ab2",
}
NONDETERMINISTIC = {
    "720e5a3daf7b848e8a25038c20bda47e8fb0433495aaa7bdbff9b285b8ba5a2d": "Fusion uses wall-clock seed/beam budgets",
    "641c909b7ef188f3ba4dfa7fe0ccb935fe3dde2e23f99c07f83fbc1d7b9f7d4d": "Apex uses wall-clock search guards",
}
PINS = {
    "simulator/vendor_harness/referee.py": "f1125e8ceee664781827c670c0c4481da41a7ef41a4e5276d6b3b118274af337",
    "simulator/vendor_harness/worker.py": "9ae8c11c7bbcc0696a6c1fd4d1cc66684bb546d9db2c604a72b161c336d8db5f",
    "tests/reference_engine.py": "8f7b89995cad0f724fb8ac7c7bc8311a6fa9b3b722f2204097031ba2333726f4",
}
_spec = importlib.util.spec_from_file_location("_arrival_independent_referee", ROOT/"simulator/vendor_harness/referee.py")
referee = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(referee)
_CODE = {}


def sha(body):
    return hashlib.sha256(body).hexdigest()


def check(condition, message):
    if not condition:
        raise ValueError(message)


def strict(body):
    def pairs(items):
        result = {}
        for key, value in items:
            check(key not in result, "Duplicate JSON key")
            result[key] = value
        return result
    def constant(value):
        raise ValueError("Invalid JSON constant: " + value)
    return json.loads(body, object_pairs_hook=pairs, parse_constant=constant)


def equal_states(g, r):
    for field in ("base", "owner", "upg", "home", "pos", "frozen", "cd", "prog", "score", "turn", "token"):
        check(getattr(g, field) == getattr(r, field), "Referee divergence: " + field)
    check(g.income == r.income(), "Income divergence")
    for seat in range(4):
        check(set(g.legal(seat)) == set(r.legal(seat)), "Legal-set divergence")


def sig(view):
    return (view.bot_id, view.is_priority_token, tuple(view.legal_actions),
            tuple((c.occupant, c.owner, c.is_upgraded, c.is_home, c.is_frozen, c.base_points)
                  for row in view.board for c in row))


def load_actor(entry):
    path = (ROOT/entry["path"]).resolve()
    check(path.is_relative_to(ROOT), "Actor source escaped workspace")
    body = path.read_bytes()
    check(sha(body) == entry["sha256"], "Actor source changed")
    code = _CODE.get(entry["sha256"])
    if code is None:
        code = compile(body, str(path), "exec")
        _CODE[entry["sha256"]] = code
    namespace = {"__name__": "_arrival_audited_actor", "__file__": str(path)}
    exec(code, namespace)
    return namespace


def audit_game(row, fixture, sources, regenerate_rivals=True):
    check(row["fixture"] == fixture["id"], "Fixture identity mismatch")
    assignment = list(fixture["opponents"])
    assignment.insert(fixture["seat"], row["candidate"])
    check(assignment == row["assignment"], "Player assignment mismatch")
    check(row["map_group"] == fixture["map_group"] and row["field"] == fixture["field"] and row["focal_seat"] == fixture["seat"], "Fixture metadata mismatch")
    check(not row["faults"], "Recorded worker fault")
    check(len(row["actions"]) == 80 and all(len(a) == 4 for a in row["actions"]), "Incomplete game")
    check(len(row["timing"]) == 4, "Incomplete timing")
    for item in row["timing"]:
        check(type(item["calls"]) is int and item["calls"] == 80, "Incomplete callbacks")
        for name in ("max_ms", "total_ms"):
            check(type(item[name]) in (int, float) and math.isfinite(item[name]) and item[name] >= 0, "Invalid timing")
        check(item["max_ms"] <= 2000 and item["max_ms"] <= item["total_ms"] <= 80*item["max_ms"]+1e-6, "Inconsistent timing")
    namespaces = []
    for seat, name in enumerate(assignment):
        entry = sources[name]
        if seat == fixture["seat"] or (regenerate_rivals and entry["sha256"] not in NONDETERMINISTIC):
            namespaces.append(load_actor(entry))
        else:
            namespaces.append(None)
    g = engine.Game(base=fixture["base"], start_token=fixture["token"], rules={"catch_requires_stay": True})
    r = referee.Referee(fixture["base"], start_token=fixture["token"], rules={"catch_requires_stay": True})
    regenerated, focal_oracles = 0, 0
    equal_states(g, r)
    for turn, chosen in enumerate(row["actions"], 1):
        views = g.views()  # Every actor gets the same pre-action turn.
        for seat, action in enumerate(chosen):
            check(type(action) is str and action in g.legal(seat) and action in r.legal(seat), "Illegal action")
            namespace = namespaces[seat]
            if namespace is None:
                continue
            public = copy.deepcopy(views[seat])
            public.legal_actions = list(r.legal(seat))  # Match actual worker input order.
            check(set(public.__slots__) == {"board", "bot_id", "is_priority_token", "legal_actions"}, "Unexpected actor fields")
            before = sig(public)
            actual = namespace["act"](public)
            check(sig(public) == before, "Actor changed public input")
            check(actual == action, "Action fails independent regeneration: turn%d seat%d %s != %s" % (turn, seat+1, actual, action))
            regenerated += 1
            if seat == fixture["seat"]:
                check(not namespace.get("_input_failures", 0) and not namespace.get("_policy_failures", 0), "Focal fallback")
                memory = namespace["_history"][seat+1]
                check(not memory.get("inference_failures", 0), "Focal inference fallback")
                check(memory["progress"] == g.prog[seat] and memory["scores"][1:] == g.score, "Incorrect focal public memory")
                check(all(g.cd[i] in memory["cooldown_possible"][i+1] for i in range(4)), "Actual cooldown lost from public belief")
                focal_oracles += 1
        g.step(chosen)
        r.step(chosen)
        equal_states(g, r)
    check(g.over() and r.over() and all(type(v) is int for v in row["scores"])
          and row["scores"] == g.score, "Final score divergence")
    pw = [sum(1 if own > other else .5 if own == other else 0 for j, other in enumerate(g.score) if i != j) for i, own in enumerate(g.score)]
    check(row["pw"] == pw and row["focal_pw"] == pw[fixture["seat"]] and row["focal_score"] == g.score[fixture["seat"]], "Incorrect Round1 outcome")
    return dict(regenerated_callbacks=regenerated, focal_public_oracles=focal_oracles)


def approved_patch():
    from evolution.genomes import GenomeSpace
    from evolution.mathematical_candidates import build_arrival
    body = (ROOT/"bot.py").read_bytes()
    check(sha(body) == PARENT, "Production parent changed")
    check(sha((HERE/"build_arrival.py").read_bytes()) == BUILDER, "Approved builder changed")
    manifest = strict((HERE/"arrival_manifest.json").read_bytes())
    check(manifest["parent_sha256"] == PARENT and manifest["source_builder_sha256"] == BUILDER and manifest["production_changed"] is False, "Approved patch manifest changed")
    parent_space = GenomeSpace(body)
    corrected = build_arrival.transform(body)
    expected = {
        "arrival_lifetime.py": corrected,
        "arrival_lifetime_depth2.py": GenomeSpace(corrected).export(dict(parent_space.genes, depth=2)),
        "baseline_depth2.py": parent_space.export(dict(parent_space.genes, depth=2)),
    }
    entries = {Path(e["path"]).name: e for e in manifest["artifacts"]}
    check(set(entries) == set(expected), "Unexpected candidate artifacts")
    for filename, payload in expected.items():
        entry = entries[filename]
        check((ROOT/entry["path"]).read_bytes() == payload and sha(payload) == entry["sha256"] and len(payload) == entry["bytes"], "Candidate is not the exact approved transformation")
        tree = ast.parse(payload)
        imports = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imports.add(node.module)
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                check(node.func.id not in {"open", "eval", "exec", "compile", "__import__", "input", "globals", "locals"}, "Disallowed dynamic/I/O call")
        check(imports == {"collections"}, "Unexpected candidate imports")
    return manifest


def independent_paired(rows, first, second):
    a = {r["fixture"]: r for r in rows if r["candidate"] == first}
    b = {r["fixture"]: r for r in rows if r["candidate"] == second}
    groups = {}
    for key in sorted(set(a).intersection(b)):
        groups.setdefault(a[key]["map_group"], []).append(a[key]["focal_pw"]-b[key]["focal_pw"])
    means = [sum(values)/len(values) for _, values in sorted(groups.items())]
    rng = random.Random(202611081801)
    boot = sorted(sum(rng.choice(means) for _ in means)/len(means) for _ in range(10000))
    return dict(first=first, second=second, clusters=len(means), mean=sum(means)/len(means),
                bootstrap_95=[boot[249], boot[9749]], bootstrap_order="Canonical sorted map hashes")


def registered_benchmark_source(expected):
    """An advanced live tool must not erase historical source reproducibility."""
    live = ROOT/"tools/benchmark.py"
    if sha(live.read_bytes()) == expected:
        return live
    archived = ROOT/"validation/benchmark_versions"/(expected+".py")
    check(archived.is_file() and sha(archived.read_bytes()) == expected, "Registered benchmark source unavailable")
    return archived


def audit(directory, output, workers=6, regenerate_rivals=True, disjoint_with=()):
    directory = Path(directory).resolve()
    started = time.perf_counter()
    approved_patch()
    raw = (directory/"results.json.gz").read_bytes()
    data = strict(gzip.decompress(raw))
    registration = data["registration"]
    check(registration["referee_sha256"] == PINS["simulator/vendor_harness/referee.py"], "Registered referee pin mismatch")
    check(registration["worker_sha256"] == PINS["simulator/vendor_harness/worker.py"], "Registered worker pin mismatch")
    spec_body = (directory/"registration.json").read_bytes()
    check(sha(spec_body) == registration["spec_sha256"] and strict(spec_body) == registration["spec"], "Registered spec changed")
    check(strict((directory/"results.json.registration.json").read_bytes()) == registration, "Registration copies differ")
    spec = registration["spec"]
    check(registration["rules"] == referee.DEFAULT_RULES and registration["rules"]["catch_requires_stay"] is True, "Unexpected physics")
    check(registration["timing"] == {"enforce": True, "turn_ms": 200, "first_ms": 2000, "hard_s": 1.0, "load_s": 5.0}, "Timing contract changed")
    check(spec["primary_campaign_games"] == 0 and spec["bmcts_audits"] == 0, "False campaign/audit credit")
    sources = {s["name"]: s for s in spec["sources"]}
    check(len(sources) == len(spec["sources"]), "Duplicate source name")
    guards = {str(ROOT/path): expected for path, expected in PINS.items()}
    for entry in sources.values():
        path = (ROOT/entry["path"]).resolve()
        check(path.is_relative_to(ROOT), "Source path escaped workspace")
        guards[str(path)] = entry["sha256"]
    for name in spec["candidates"]:
        check(name in APPROVED and sources[name]["sha256"] == APPROVED[name], "Unapproved candidate")
    guards.update({str(registered_benchmark_source(registration["benchmark_sha256"])): registration["benchmark_sha256"],
                   str(directory/"registration.json"): registration["spec_sha256"],
                   str(directory/"results.json.gz"): sha(raw),
                   str(HERE/"build_arrival.py"): BUILDER,
                   str(HERE/"arrival_manifest.json"): sha((HERE/"arrival_manifest.json").read_bytes()),
                   str(Path(__file__).resolve()): sha(Path(__file__).read_bytes())})
    for path, expected in guards.items():
        check(sha(Path(path).read_bytes()) == expected, "Pinned source mismatch: " + path)
    fixtures, maps = {}, {}
    counts = Counter()
    for fixture in spec["fixtures"]:
        check(fixture["id"] not in fixtures, "Duplicate fixture")
        fixtures[fixture["id"]] = fixture
        base = fixture["base"]
        check(len(base) == 64 and all(type(v) is int and 1 <= v <= 3 for v in base), "Invalid map values")
        check(all(base[r*8+c] == base[r*8+7-c] == base[(7-r)*8+c] for r in range(8) for c in range(8)), "Unmirrored map")
        check(sha(bytes(base)) == fixture["map_group"], "Map content hash changed")
        maps[fixture["map_group"]] = tuple(base)
        check(type(fixture["seat"]) is int and 0 <= fixture["seat"] < 4 and type(fixture["token"]) is int and 1 <= fixture["token"] <= 4, "Invalid seat/token")
        check(len(fixture["opponents"]) == 3 and set(fixture["opponents"]) <= set(sources), "Invalid opponent set")
        counts.update([(fixture["map_group"], fixture["field"], fixture["seat"], fixture["token"])])
    fields = sorted({f["field"] for f in fixtures.values()})
    check(len(counts) == len(maps)*len(fields)*16 and set(counts.values()) == {1}, "Map/field/seat/token imbalance")
    for other in disjoint_with:
        other_spec = strict(Path(other).read_bytes())
        other_spec = other_spec.get("spec", other_spec)
        other_boards = {tuple(f["base"]) for f in other_spec["fixtures"]}
        check(not set(maps.values()).intersection(other_boards), "Held-out map content reused")
    rows = data["games"]
    keys = [(r["candidate"], r["fixture"]) for r in rows]
    check(len(keys) == len(set(keys)) and set(keys) == {(c, f) for c in spec["candidates"] for f in fixtures}, "Incomplete/duplicate/foreign result tasks")
    totals = Counter()
    with ProcessPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(audit_game, row, fixtures[row["fixture"]], sources, regenerate_rivals) for row in rows]
        for number, future in enumerate(as_completed(futures), 1):
            totals.update(future.result())
            if number % 128 == 0 or number == len(rows):
                print("Independent arrival audit: %d/%d games" % (number, len(rows)), flush=True)
    for candidate, summary in data["summary"].items():
        group = [r for r in rows if r["candidate"] == candidate]
        check(summary["games"] == len(group) and summary["focal_faults"] == summary["all_faults"] == 0, "Incorrect summary count/faults")
        check(math.isclose(summary["mean_pw"], sum(r["focal_pw"] for r in group)/len(group), abs_tol=1e-12), "Incorrect mean outcome")
        check(math.isclose(summary["mean_score"], sum(r["focal_score"] for r in group)/len(group), abs_tol=1e-12), "Incorrect mean score")
        focal = [r["timing"][r["focal_seat"]] for r in group]
        check(summary["max_ms"] == max(t["max_ms"] for t in focal), "Incorrect maximum timing")
        check(math.isclose(summary["mean_ms"], sum(t["total_ms"] for t in focal)/sum(t["calls"] for t in focal), abs_tol=1e-12), "Incorrect mean timing")
        for field in fields:
            subgroup = [r for r in group if r["field"] == field]
            check(math.isclose(summary["fields"][field], sum(r["focal_pw"] for r in subgroup)/len(subgroup), abs_tol=1e-12), "Incorrect field mean")
    comparisons = []
    for reported in data["paired"]:
        actual = independent_paired(rows, reported["first"], reported["second"])
        check(math.isclose(actual["mean"], reported["mean"], abs_tol=1e-12) and actual["clusters"] == reported["clusters"], "Incorrect paired comparison")
        actual["original_reported_bootstrap_95"] = reported["bootstrap_95"]
        comparisons.append(actual)
    for path, expected in guards.items():
        check(sha(Path(path).read_bytes()) == expected, "Source changed during audit: " + path)
    report = dict(format="zone-rush-approved-logic-comparison-audit/1", validity="PASSED", promotion="BLOCKED_PENDING_REVIEW",
                  role=spec.get("role"), games=len(rows), turns=len(rows)*80, original_worker_callbacks=len(rows)*320,
                  regenerated_callbacks=totals["regenerated_callbacks"], focal_public_oracles=totals["focal_public_oracles"],
                  two_referees_every_turn=True, zero_worker_faults=True, input_immutable=True,
                  public_only_focal_regeneration=True, all_focal_actions_exact=True,
                  map_field_seat_token_balanced=True, maps=len(maps), map_ids=sorted(maps),
                  disjoint_map_checks=[str(Path(p).resolve()) for p in disjoint_with],
                  source_guards=guards, paired_canonical_recomputation=comparisons,
                  original_summary=data["summary"], primary_campaign_games=0, bmcts_audits=0,
                  skipped_rival_regeneration=NONDETERMINISTIC if regenerate_rivals else "All rivals omitted by explicit focal-only mode",
                  elapsed_s=time.perf_counter()-started,
                  limitations=["Selection data cannot establish an improvement without fresh confirmation.",
                               "Timing aggregates plus pinned zero-fault worker records validate original deadlines; audit reruns do not recreate original wall-clock conditions.",
                               "Archived stochastic/time-budget rivals cannot have their original private random streams reconstructed.",
                               "Canonical independent bootstrap may differ slightly from historical unsorted-set bootstrap due to Monte Carlo ordering.",
                               "Macro clock correction does not make static route/opponent approximations optimal."])
    Path(output).parent.mkdir(parents=True, exist_ok=True)
    Path(output).write_text(json.dumps(report, indent=2)+"\n", encoding="utf8", newline="\n")
    print(json.dumps({k: v for k, v in report.items() if k not in {"source_guards", "map_ids", "original_summary", "paired_canonical_recomputation"}}, indent=2), flush=True)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--focal-only", action="store_true")
    parser.add_argument("--disjoint-with", type=Path, nargs="*", default=[])
    args = parser.parse_args()
    if not 1 <= args.workers <= 24:
        parser.error("Workers must be1..24")
    audit(args.directory, args.output, args.workers, not args.focal_only, args.disjoint_with)


if __name__ == "__main__":
    main()
