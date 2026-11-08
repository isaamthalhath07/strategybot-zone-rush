"""Authenticated, fixed-policy development/final evaluation of the frozen campaign."""
from collections import Counter, defaultdict
from contextlib import closing
from fractions import Fraction
import json
from pathlib import Path
import re
import secrets
import sqlite3

from evolution import league, runner, oversight
from evolution.genomes import GenomeSpace, digest
from primary_campaign import core as primary
from . import authority

ROOT = primary.ROOT
FORMAT = "zone-rush-heldout/1"
RUNTIME = ("__init__.py", "authority.py", "core.py", "run.py")
METRIC = {"cells": ["seat", "token", "field"], "primary": "equal mean of64 Round1 pairwise cell means",
          "ties": ["raw mean score descending", "source SHA256 ascending"], "arithmetic": "exact rational; floats are display only"}
SHORTLIST_RECIPE = "Exactly8 registered candidates of the FINAL SCHEDULED training stage, in registered order, including incumbent."
TRAIN_FILES = ("registration.json", "registration.sha256", "summary.json", "summary.sha256",
               "audit.json", "audit.sha256", "games.jsonl", "actor_audits.jsonl")


def check(value, message):
    if not value:
        raise ValueError(message)


def read(path):
    path = Path(path)
    body = path.read_bytes()
    check(digest(body) == path.with_suffix(".sha256").read_text().strip(), "Sealed artifact changed: "+path.name)
    return oversight.strict_loads(body)


def seal(path, value):
    return primary.seal(path, value)


def pins(manifest):
    result = dict(manifest["guards"])
    result.update({str((Path(__file__).parent/name).resolve()): digest((Path(__file__).parent/name).read_bytes())
                   for name in RUNTIME})
    return result


def _base(campaign):
    campaign = authority.location(campaign).parent
    return campaign, *primary.load_catalog(campaign)


def _bind(bindings, paths):
    for item in paths:
        path = Path(item).resolve()
        check(path.is_relative_to(ROOT), "Artifact escaped the reviewed workspace")
        check(path.is_file(), "Missing required artifact: "+path.name)
        value = digest(path.read_bytes())
        if str(path) in bindings:
            check(bindings[str(path)] == value, "Artifact changed during admission")
        bindings[str(path)] = value


def _base_bindings(campaign, manifest):
    result = {}
    _bind(result, [campaign/name for name in ("manifest.json", "manifest.sha256", "catalog.json", "catalog.sha256")])
    _bind(result, pins(manifest))
    return result


def _check_bindings(bindings):
    check(type(bindings) is dict and bool(bindings), "Missing artifact bindings")
    for name, expected in bindings.items():
        path = Path(name).resolve()
        check(path.is_relative_to(ROOT) and path.is_file() and digest(path.read_bytes()) == expected,
              "Authenticated raw artifact changed: "+path.name)


def _write_gate(campaign, purpose, payload, key_id):
    root = authority.location(campaign)
    envelope = authority.sign(campaign, key_id, purpose, payload)
    identity = digest(primary.canonical(envelope))
    path = authority.safe_path(campaign, "gates", purpose+"-"+identity+".json")
    seal(path, envelope)
    primary.atomic(root/("active_"+purpose+"_gate.json"), primary.canonical({"gate": path.name})+b"\n")
    return envelope


def _gate(campaign, purpose, manifest):
    root = authority.location(campaign)
    pointer = root/("active_"+purpose+"_gate.json")
    if not pointer.exists():
        raise authority.GateUnavailable("Heldout admission is missing")
    reference = oversight.strict_loads(pointer.read_bytes())
    check(type(reference) is dict and set(reference) == {"gate"}, "Invalid local gate reference")
    name = reference["gate"]
    check(type(name) is str and re.fullmatch(re.escape(purpose)+r"-[0-9a-f]{64}\.json", name), "Invalid gate identity")
    path = authority.safe_path(campaign, "gates", name)
    check(path.stat().st_size <= 8*1024*1024, "Oversized local gate")
    envelope = read(path)
    check(name == purpose+"-"+digest(primary.canonical(envelope))+".json", "Gate name does not bind its contents")
    payload = authority.authenticate(campaign, purpose, envelope)  # BEFORE repair, reseal, or artifact use.
    check(payload["campaign_id"] == manifest["campaign_id"] and payload["profile"] == manifest["profile"], "Gate belongs to another campaign")
    check(payload["source_guards"] == pins(manifest), "Heldout evaluator changed after admission")
    primary.check_guards(payload["source_guards"])
    _check_bindings(payload["bindings"])
    shortlist = read(root/"shortlist.json")
    check(payload["shortlist_sha256"] == digest((root/"shortlist.json").read_bytes()), "Frozen shortlist differs from approval")
    _validate_shortlist(shortlist, manifest)
    return envelope, shortlist


def _validate_shortlist(shortlist, manifest):
    check(shortlist["format"] == FORMAT and shortlist["campaign_id"] == manifest["campaign_id"]
          and shortlist["profile"] == manifest["profile"] and shortlist["recipe"] == SHORTLIST_RECIPE
          and shortlist["metric"] == METRIC and shortlist["source_guards"] == pins(manifest)
          and shortlist["final_training_generation"] == manifest["training_generations"]-1,
          "Shortlist protocol changed")
    candidates = shortlist["candidates"]
    check(len(candidates) == 8 and len({c["sha256"] for c in candidates}) == 8
          and candidates[0]["sha256"] == primary.INCUMBENT, "Require8 distinct audited policies including incumbent")
    space, _ = primary.sources_space()
    for candidate in candidates:
        path = Path(candidate["path"]).resolve()
        check(path.is_relative_to(authority.location(Path(shortlist["campaign_path"])).resolve()), "Shortlist export escaped heldout storage")
        body = path.read_bytes()
        check(body == space.export(candidate["genes"]) and digest(body) == candidate["sha256"], "Shortlist policy drift or non-CONFIG change")


def _deep_training(campaign, manifest, catalog):
    count, size = manifest["training_generations"], manifest["shape"]["maps_per_generation"]
    check(count == manifest["shape"]["train_maps"]//size, "Training count changed")
    # Fail quickly on an unfinished campaign instead of replaying its prefix.
    for index in range(count):
        stage = campaign/("train_%03d" % index)
        check((stage/"audit.json").is_file(), "All scheduled training audits are required")
        audit = read(stage/"audit.json")
        check(audit["approved"] is True and audit["phase"] == "train" and audit["generation"] == index
              and audit["profile"] == manifest["profile"], "Training audit is missing or copied from another generation")
    bindings, stages, seen_maps, last = _base_bindings(campaign, manifest), [], set(), None
    scratch = authority.safe_path(campaign, "admission_checks", secrets.token_hex(16)+".sqlite")
    scratch.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(scratch)) as db:
        db.execute("CREATE TABLE identities(kind INTEGER,id TEXT,PRIMARY KEY(kind,id)) WITHOUT ROWID")
        for index in range(count):
            stage = campaign/("train_%03d" % index)
            registration = read(stage/"registration.json")
            check(registration["phase"] == "train" and registration["generation"] == index
                  and registration["profile"] == manifest["profile"], "Training directory/index substitution")
            audit = primary.validated_audit(stage)  # Actual full evidence, not an aggregate flag.
            summary = read(stage/"summary.json")
            check(summary["generation"] == audit["generation"] == index and audit["games_audited"] == size*200,
                  "Training stage has the wrong scope")
            expected = set(range(index*size, (index+1)*size))
            actual = {f["map_index"] for f in registration["fixtures"]}
            check(actual == expected and not actual.intersection(seen_maps), "Training map slice reused")
            seen_maps.update(actual)
            try:
                db.executemany("INSERT INTO identities VALUES (0,?)", [(f["id"],) for f in registration["fixtures"]])
                db.executemany("INSERT INTO identities VALUES (1,?)", [(s["id"],) for f in registration["fixtures"] for s in f["opponents"]])
                db.commit()
            except sqlite3.IntegrityError as error:
                raise ValueError("Training tasks or rival identities were reused across stages") from error
            _bind(bindings, [stage/name for name in TRAIN_FILES])
            for candidate in registration["candidates"]:
                check(Path(candidate["path"]).resolve().is_relative_to(stage.resolve()), "Training export belongs to another stage")
                _bind(bindings, [candidate["path"]])
            stages.append(dict(index=index, directory=str(stage), registration_sha256=digest((stage/"registration.json").read_bytes()),
                               audit_sha256=digest((stage/"audit.json").read_bytes()), games=size*200,
                               primary_games=audit["primary_games_accepted"], candidate_paths=[c["path"] for c in registration["candidates"]]))
            last = registration
    check(seen_maps == set(range(manifest["shape"]["train_maps"])), "Training coverage is incomplete")
    check(sum(s["primary_games"] for s in stages) == (manifest["shape"]["train_maps"]*200 if manifest["profile"] == "full_primary" else 0),
          "Incorrect training primary credit")
    return bindings, stages, last


def admit_development(campaign, recover=False):
    campaign, manifest, catalog = _base(campaign)
    root = authority.location(campaign)
    pointer = root/"active_development_gate.json"
    if pointer.exists() and not recover:
        return require_admission(campaign)
    check(recover or not (root/"shortlist.json").exists(), "Missing authority requires explicit deep recovery")
    if not (root/"shortlist.json").exists():
        check(not any(root.glob("development_*/*games*.jsonl")), "Development outcomes predate the frozen shortlist")
    bindings, stages, last = _deep_training(campaign, manifest, catalog)
    space, _ = primary.sources_space()
    candidates = []
    for original in last["candidates"]:
        body = space.export(original["genes"])
        check(digest(body) == original["sha256"] and Path(original["path"]).read_bytes() == body, "Final training candidate drift")
        path = authority.safe_path(campaign, "policies", original["sha256"]+".py")
        if path.exists():
            check(path.read_bytes() == body, "Frozen heldout policy changed")
        else:
            primary.atomic(path, body)
        candidates.append(dict(name=original["name"], sha256=original["sha256"], genes=original["genes"],
                               path=str(path.resolve()), training_path=original["path"]))
    shortlist = dict(format=FORMAT, campaign_id=manifest["campaign_id"], campaign_path=str(campaign), profile=manifest["profile"],
                     recipe=SHORTLIST_RECIPE, metric=METRIC, source_guards=pins(manifest),
                     final_training_generation=manifest["training_generations"]-1, candidates=candidates)
    _validate_shortlist(shortlist, manifest)
    seal(root/"shortlist.json", shortlist)  # Existing choices are NEVER replaced.
    _bind(bindings, [root/"shortlist.json", root/"shortlist.sha256", *(c["path"] for c in candidates)])
    _check_bindings(bindings)
    payload = dict(campaign_id=manifest["campaign_id"], profile=manifest["profile"],
                   shortlist_sha256=digest((root/"shortlist.json").read_bytes()), source_guards=pins(manifest),
                   stages=stages, bindings=bindings)
    _write_gate(campaign, "development", payload, authority.new_key(campaign))
    return require_admission(campaign)


def require_admission(campaign):
    campaign, manifest, _ = _base(campaign)
    envelope, shortlist = _gate(campaign, "development", manifest)
    stages = envelope["payload"]["stages"]
    check([s["index"] for s in stages] == list(range(manifest["training_generations"])), "Authenticated gate has incomplete training coverage")
    check(all(s["directory"] == str(campaign/("train_%03d" % s["index"]))
              and s["games"] == manifest["shape"]["maps_per_generation"]*200 for s in stages), "Gate stage identity changed")
    required = set(_base_bindings(campaign, manifest))
    for stage in stages:
        directory = Path(stage["directory"])
        check(len(stage["candidate_paths"]) == 8 and len(set(stage["candidate_paths"])) == 8
              and all(Path(p).resolve().is_relative_to(directory) and Path(p).suffix == ".py" for p in stage["candidate_paths"]),
              "Incomplete gate candidate export coverage")
        required.update(str((directory/name).resolve()) for name in TRAIN_FILES)
        required.update(str(Path(p).resolve()) for p in stage["candidate_paths"])
        check(stage["registration_sha256"] == envelope["payload"]["bindings"][str(directory/"registration.json")]
              and stage["audit_sha256"] == envelope["payload"]["bindings"][str(directory/"audit.json")], "Gate stage hashes changed")
    root = authority.location(campaign)
    required.update(str((root/name).resolve()) for name in ("shortlist.json", "shortlist.sha256"))
    required.update(c["path"] for c in shortlist["candidates"])
    check(set(envelope["payload"]["bindings"]) == required, "Incomplete or unexpected authenticated training artifact manifest")
    return shortlist


def block_count(manifest, phase):
    check(phase in ("development", "final"), "Unknown heldout phase")
    count = manifest["shape"][phase+"_maps"]
    return (count+99)//100


def stage_path(campaign, phase, block):
    check(phase in ("development", "final") and type(block) is int and block >= 0, "Invalid heldout stage")
    return authority.safe_path(campaign, phase+"_%03d" % block)


def _candidate_set(campaign, phase, shortlist):
    if phase == "development":
        return shortlist["candidates"]
    selection = require_final_selection(campaign)
    return [next(c for c in shortlist["candidates"] if c["sha256"] == selection["winner_sha256"])]


def _fixtures(manifest, catalog, phase, block, candidates):
    all_boards = [b for b in catalog if b["phase"] == phase]
    boards = all_boards[block*100:(block+1)*100]
    check(bool(boards), "Heldout block is outside its catalog phase")
    # Both full phases are1000 maps; test profiles may use smaller counts.
    # Prior full100-map blocks each contribute1250 occurrences per seat/token.
    occurrence = Counter({(seat, token): block*1250 for seat in range(4) for token in range(1, 5)})
    space, research = primary.sources_space()
    output = []
    for board in boards:
        for episode in range(200):
            seat, token = primary.maps.seat_token(board["map_index"], episode)
            n = occurrence[seat, token]
            occurrence[seat, token] += 1
            candidate = candidates[(n+4*seat+token-1) % 8] if len(candidates) == 8 else candidates[0]
            field = list(primary.FIELDS)[(n//8+n%8+2*seat+token-1) % 4]
            fixture = dict(map_id=board["id"], map_index=board["map_index"], base=board["base"], map_family=board["family"],
                           episode=episode, seat=seat, token=token, field=field, candidate=candidate["sha256"],
                           opponents=primary.expected_opponents(manifest, board, episode, seat, field, space, research))
            fixture["id"] = digest(primary.canonical(fixture))
            output.append(fixture)
    return output


def prepare_stage(campaign, phase, block):
    campaign, manifest, catalog = _base(campaign)
    shortlist = require_admission(campaign)
    check(type(block) is int and 0 <= block < block_count(manifest, phase), "Invalid heldout block")
    candidates = _candidate_set(campaign, phase, shortlist)
    if block:
        validated_stage(campaign, phase, block-1)
    stage = stage_path(campaign, phase, block)
    stage.mkdir(parents=True, exist_ok=True)
    lock = authority.safe_path(campaign, stage.name, ".executor.lock")
    if not lock.exists():
        try:
            with lock.open("xb") as handle:
                handle.write(b"\0")
        except FileExistsError:
            pass
    if (stage/"registration.json").exists():
        registration = read(stage/"registration.json")
        validate_registration(campaign, registration)
        return registration
    registration = dict(format=FORMAT, campaign_id=manifest["campaign_id"], profile=manifest["profile"], phase=phase, block=block,
                        metric=METRIC, shortlist_sha256=digest((authority.location(campaign)/"shortlist.json").read_bytes()),
                        source_guards=pins(manifest), sources=manifest["sources"], rules={"catch_requires_stay": True},
                        candidates=candidates, fixtures=_fixtures(manifest, catalog, phase, block, candidates),
                        promoted=False, bmcts_audits=0)
    validate_registration(campaign, registration)
    return seal(stage/"registration.json", registration)


def validate_registration(campaign, registration):
    campaign, manifest, catalog = _base(campaign)
    shortlist = require_admission(campaign)
    phase, block = registration["phase"], registration["block"]
    check(phase in ("development", "final") and type(block) is int and 0 <= block < block_count(manifest, phase), "Wrong evaluation phase/block")
    candidates = _candidate_set(campaign, phase, shortlist)
    check(registration["format"] == FORMAT and registration["campaign_id"] == manifest["campaign_id"]
          and registration["profile"] == manifest["profile"] and registration["metric"] == METRIC
          and registration["source_guards"] == pins(manifest) and registration["sources"] == manifest["sources"]
          and registration["candidates"] == candidates and registration["rules"] == {"catch_requires_stay": True}
          and registration["promoted"] is False and registration["bmcts_audits"] == 0
          and registration["shortlist_sha256"] == digest((authority.location(campaign)/"shortlist.json").read_bytes()),
          "Frozen heldout protocol or policy changed")
    expected = _fixtures(manifest, catalog, phase, block, candidates)
    check(registration["fixtures"] == expected, "Heldout map, assignment or opponent substitution")
    return dict(games=len(expected), candidates=len(candidates), maps=len({f["map_id"] for f in expected}))


def summarize(rows, registration):
    fixtures = {f["id"]: f for f in registration["fixtures"]}
    statistics = {}
    for candidate in registration["candidates"]:
        group = [r for r in rows if r["candidate"] == candidate["sha256"]]
        cells = defaultdict(lambda: [0.0, 0])
        for row in group:
            fixture = fixtures[row["fixture"]]
            cell = cells[(fixture["seat"], fixture["token"], fixture["field"])]
            cell[0] += row["focal_pw"]
            cell[1] += 1
        check(len(cells) == 64 and all(n for _, n in cells.values()), "Incomplete heldout outcome cells")
        exact = _exact_metric(cells)
        statistics[candidate["sha256"]] = dict(name=candidate["name"], sha256=candidate["sha256"], games=len(group),
            standardized_pw=float(exact), standardized_pw_fraction=[exact.numerator, exact.denominator],
            mean_pw=sum(r["focal_pw"] for r in group)/len(group), mean_score=sum(r["focal_score"] for r in group)/len(group),
            score_sum=sum(r["focal_score"] for r in group),
            cells={json.dumps(key): {"sum": value[0], "count": value[1]} for key, value in sorted(cells.items())})
    return _rank(statistics.values())


def _exact_metric(cells):
    check(len(cells) == 64, "Incomplete outcome cells")
    total = Fraction(0)
    for _, (value, count) in sorted(cells.items()):
        check(type(count) is int and count > 0 and value*2 == int(value*2), "Invalid pairwise cell sum")
        total += Fraction(int(value*2), 2*count)
    return total/64


def _rank(entries):
    return sorted(entries, key=lambda r: (-Fraction(*r["standardized_pw_fraction"]),
                                         -Fraction(r["score_sum"], r["games"]), r["sha256"]))


def validated_stage(campaign, phase, block):
    from . import run
    return run.validate_completed_stage(campaign, phase, block)


def admit_final(campaign, recover=False):
    from . import run
    campaign, manifest, _ = _base(campaign)
    shortlist = require_admission(campaign)
    root = authority.location(campaign)
    if (root/"active_final_gate.json").exists() and not recover:
        return require_final_selection(campaign)
    if not (root/"final_selection.json").exists():
        check(not any(p.stat().st_size for p in root.glob("final_*/games.jsonl")), "Final outcomes predate the frozen final policy")
    # Full declared phase, never merely the latest completed development block.
    for block in range(block_count(manifest, "development")):
        check((stage_path(campaign, "development", block)/"active_audit.json").exists(), "All development stages must be audited before final")
    admission, _ = _gate(campaign, "development", manifest)
    bindings = dict(admission["payload"]["bindings"])
    totals = {c["sha256"]: dict(cells=defaultdict(lambda: [0.0, 0]), score=0, games=0, name=c["name"]) for c in shortlist["candidates"]}
    stages = []
    for block in range(block_count(manifest, "development")):
        audit = validated_stage(campaign, "development", block)
        stage = stage_path(campaign, "development", block)
        registration = read(stage/"registration.json")
        fixtures = {f["id"]: f for f in registration["fixtures"]}
        with (stage/"games.jsonl").open(encoding="utf8") as stream:
            for line in stream:
                row = oversight.strict_loads(line)
                fixture, entry = fixtures[row["fixture"]], totals[row["candidate"]]
                cell = entry["cells"][(fixture["seat"], fixture["token"], fixture["field"])]
                cell[0] += row["focal_pw"]
                cell[1] += 1
                entry["score"] += row["focal_score"]
                entry["games"] += 1
        _bind(bindings, run.stage_artifacts(campaign, "development", block))
        stages.append(dict(block=block, games=audit["games_audited"], primary_games=audit["primary_games_accepted"]))
    ranking = []
    expected_games = manifest["shape"]["development_maps"]*200//8
    for sha, entry in totals.items():
        check(entry["games"] == expected_games and len(entry["cells"]) == 64, "Development comparison is incomplete")
        exact = _exact_metric(entry["cells"])
        ranking.append(dict(sha256=sha, name=entry["name"], games=entry["games"],
                            standardized_pw=float(exact), standardized_pw_fraction=[exact.numerator, exact.denominator],
                            score_sum=entry["score"], mean_score=entry["score"]/entry["games"]))
    ranking = _rank(ranking)
    selection = dict(format=FORMAT, campaign_id=manifest["campaign_id"], profile=manifest["profile"], metric=METRIC,
                     shortlist_sha256=digest((root/"shortlist.json").read_bytes()), winner_sha256=ranking[0]["sha256"],
                     ranking=ranking, development_games=sum(s["games"] for s in stages), final_feedback_used=False,
                     promoted=False, bmcts_audits=0)
    seal(root/"final_selection.json", selection)
    _bind(bindings, [root/"final_selection.json", root/"final_selection.sha256"])
    payload = dict(campaign_id=manifest["campaign_id"], profile=manifest["profile"],
                   shortlist_sha256=selection["shortlist_sha256"], selection_sha256=digest((root/"final_selection.json").read_bytes()),
                   source_guards=pins(manifest), stages=stages, bindings=bindings)
    _write_gate(campaign, "final", payload, admission["key_id"])
    return require_final_selection(campaign)


def require_final_selection(campaign):
    campaign, manifest, _ = _base(campaign)
    require_admission(campaign)
    envelope, shortlist = _gate(campaign, "final", manifest)
    payload = envelope["payload"]
    check([s["block"] for s in payload["stages"]] == list(range(block_count(manifest, "development"))), "Incomplete final admission")
    root = authority.location(campaign)
    selection = read(root/"final_selection.json")
    check(payload["selection_sha256"] == digest((root/"final_selection.json").read_bytes())
          and selection["metric"] == METRIC and selection["final_feedback_used"] is False and selection["promoted"] is False
          and selection["winner_sha256"] in {c["sha256"] for c in shortlist["candidates"]}, "Final policy selection changed")
    return selection
