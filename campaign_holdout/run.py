"""Bounded heldout execution and owner-authenticated full actor audits."""
import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
from contextlib import contextmanager
import multiprocessing
import os
from pathlib import Path
import re

from evolution import runner, oversight
from primary_campaign import run as training_run
from . import authority, core


@contextmanager
def owner(stage):
    stage = Path(stage).resolve()
    core.check(stage.is_relative_to((core.ROOT/".cache").resolve()), "Executor ownership must stay in the local cache")
    stage.mkdir(parents=True, exist_ok=True)
    path = stage/".executor.lock"
    with path.open("a+b") as handle:
        if path.stat().st_size == 0:
            handle.write(b"\0")
            handle.flush()
        handle.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as error:
            raise ValueError("Another process owns this heldout stage") from error
        try:
            yield
        finally:
            handle.seek(0)
            if os.name == "nt":
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _maps(registration):
    return ({c["sha256"]: c for c in registration["candidates"]},
            {f["id"]: f for f in registration["fixtures"]})


def read_rows(stage, registration, repair=False):
    path = stage/"games.jsonl"
    if not path.exists():
        return []
    if repair:
        rows = training_run.completed_lines(path)  # Only after authenticated admission and exclusive ownership.
    else:
        body = path.read_bytes()
        core.check(not body or body.endswith(b"\n"), "Incomplete heldout game append")
        rows = [oversight.strict_loads(line) for line in body.splitlines()]
    candidates, fixtures = _maps(registration)
    seen = set()
    for row in rows:
        identity = row["fixture"]
        core.check(identity in fixtures and identity not in seen
                   and row["candidate"] == fixtures[identity]["candidate"], "Duplicate, foreign or reassigned evaluation result")
        runner.verify_row(row, candidates[row["candidate"]], fixtures[identity])
        seen.add(identity)
    return rows


def _completed_summary(stage, registration):
    rows = read_rows(stage, registration)
    core.check(len(rows) == len(registration["fixtures"]), "Incomplete actual heldout game coverage")
    summary = core.read(stage/"summary.json")
    expected = dict(format=core.FORMAT, campaign_id=registration["campaign_id"], phase=registration["phase"], block=registration["block"],
                    profile=registration["profile"], metric=core.METRIC,
                    registration_sha256=core.digest((stage/"registration.json").read_bytes()),
                    games_sha256=core.digest((stage/"games.jsonl").read_bytes()), candidates=core.summarize(rows, registration),
                    games_completed=len(rows), actual_callbacks=len(rows)*320, independent_acceptance_pending=True,
                    bmcts_audits=0, promoted=False)
    core.check(summary == expected, "Heldout summary differs from actual results")
    return summary, rows


def _pool_results(function, arguments, workers, initializer=None):
    core.check(type(workers) is int and 1 <= workers <= 24, "Require1..24 workers")
    pool = ProcessPoolExecutor(max_workers=workers, initializer=initializer,
                               mp_context=multiprocessing.get_context("spawn"))
    futures = []
    try:
        futures = [pool.submit(function, *args) for args in arguments]
        for future in as_completed(futures):
            yield future.result()
    except BaseException:
        for future in futures:
            future.cancel()
        pool.shutdown(wait=True, cancel_futures=True)
        raise
    else:
        pool.shutdown(wait=True)


def execute_stage(campaign, phase, block, workers=6):
    registration = core.prepare_stage(campaign, phase, block)
    stage = core.stage_path(campaign, phase, block)
    with owner(stage):
        if (stage/"summary.json").exists():
            return _completed_summary(stage, registration)[0]
        rows = read_rows(stage, registration, repair=True)
        done = {r["fixture"] for r in rows}
        candidates, fixtures = _maps(registration)
        tasks = [(candidates[f["candidate"]], f, registration["sources"]) for f in fixtures.values() if f["id"] not in done]
        with (stage/"games.jsonl").open("ab") as handle:
            for row in _pool_results(runner.play_game, tasks, workers, runner.init_worker):
                fixture = fixtures[row["fixture"]]
                runner.verify_row(row, candidates[fixture["candidate"]], fixture)
                core.check(row["fixture"] not in done, "Executor repeated a completed heldout task")
                training_run.append(handle, row)
                rows.append(row)
                done.add(row["fixture"])
        core.primary.check_guards(registration["source_guards"])
        core.check(done == set(fixtures), "Heldout execution did not complete every assignment")
        summary = dict(format=core.FORMAT, campaign_id=registration["campaign_id"], phase=phase, block=block,
                        profile=registration["profile"], metric=core.METRIC,
                        registration_sha256=core.digest((stage/"registration.json").read_bytes()),
                        games_sha256=core.digest((stage/"games.jsonl").read_bytes()), candidates=core.summarize(rows, registration),
                        games_completed=len(rows), actual_callbacks=len(rows)*320, independent_acceptance_pending=True,
                        bmcts_audits=0, promoted=False)
        return core.seal(stage/"summary.json", summary)


def _authority(campaign):
    campaign, manifest, _ = core._base(campaign)
    core.require_admission(campaign)
    envelope, _ = core._gate(campaign, "development", manifest)
    return envelope["key_id"]


def _audit_reference(stage):
    pointer = stage/"active_audit.json"
    core.check(pointer.exists(), "Heldout stage has no accepted independent audit")
    reference = oversight.strict_loads(pointer.read_bytes())
    core.check(type(reference) is dict and set(reference) == {"audit"}
               and type(reference["audit"]) is str and re.fullmatch(r"[0-9a-f]{32}\.json", reference["audit"]),
               "Invalid heldout audit reference")
    return stage/"audits"/reference["audit"]


def _proof_purpose(registration):
    return "actor:"+registration["campaign_id"]+":"+registration["phase"]+":"+str(registration["block"])


def _stage_purpose(registration):
    return "stage:"+registration["campaign_id"]+":"+registration["phase"]+":"+str(registration["block"])


def _validate_actor(campaign, registration, envelope, row):
    proof = authority.authenticate(campaign, _proof_purpose(registration), envelope)
    training_run.validate_actor_audit(proof, row)
    return proof


def audit_stage(campaign, phase, block, workers=6):
    registration = core.prepare_stage(campaign, phase, block)
    stage = core.stage_path(campaign, phase, block)
    key_id = _authority(campaign)
    with owner(stage):
        if (stage/"active_audit.json").exists():
            try:
                return validate_completed_stage(campaign, phase, block)
            except authority.GateUnavailable:
                # An explicitly recovered training authority may require fresh
                # regeneration; old proofs are preserved rather than blessed.
                pass
        summary, rows = _completed_summary(stage, registration)
        by_fixture = {r["fixture"]: r for r in rows}
        candidates, fixtures = _maps(registration)
        log = stage/("actor_audits."+key_id+".jsonl")
        proofs, done = [], set()
        for envelope in training_run.completed_lines(log):
            identity = envelope["payload"]["fixture"]
            core.check(identity in by_fixture and identity not in done, "Duplicate or foreign audit checkpoint")
            proof = _validate_actor(campaign, registration, envelope, by_fixture[identity])
            proofs.append(proof)
            done.add(identity)
        tasks = [(candidates[r["candidate"]], fixtures[r["fixture"]], registration["sources"], r)
                 for r in rows if r["fixture"] not in done]
        with log.open("ab") as handle:
            for proof in _pool_results(training_run.audit_task, tasks, workers):
                identity = proof["fixture"]
                core.check(identity in by_fixture and identity not in done, "Audit repeated a heldout task")
                training_run.validate_actor_audit(proof, by_fixture[identity])
                envelope = authority.sign(campaign, key_id, _proof_purpose(registration), proof)
                training_run.append(handle, envelope)  # The key stays in this owner process, not worker arguments.
                proofs.append(proof)
                done.add(identity)
        core.check(done == set(fixtures), "Incomplete independent heldout actor coverage")
        core.primary.check_guards(registration["source_guards"])
        approved = dict(format=core.FORMAT, campaign_id=registration["campaign_id"], phase=phase, block=block,
                        profile=registration["profile"], approved=True, all_actors_regenerated=True,
                        source_guards=registration["source_guards"],
                        registration_sha256=core.digest((stage/"registration.json").read_bytes()),
                        games_sha256=core.digest((stage/"games.jsonl").read_bytes()),
                        summary_sha256=core.digest((stage/"summary.json").read_bytes()),
                        actor_log=log.name, actor_audits_sha256=core.digest(log.read_bytes()),
                        games_audited=len(proofs), callbacks_regenerated=sum(p["callbacks_regenerated"] for p in proofs),
                        public_memory_oracles=sum(p["public_memory_oracles"] for p in proofs),
                        primary_games_accepted=len(rows) if registration["profile"] == "full_primary" else 0,
                        audit_replays_are_new_primary_games=False, bmcts_audits=0, promoted=False)
        envelope = authority.sign(campaign, key_id, _stage_purpose(registration), approved)
        target = authority.safe_path(campaign, stage.name, "audits", key_id+".json")
        core.seal(target, envelope)
        core.primary.atomic(stage/"active_audit.json", core.primary.canonical({"audit": target.name})+b"\n")
        return validate_completed_stage(campaign, phase, block)


def validate_completed_stage(campaign, phase, block):
    campaign, manifest, _ = core._base(campaign)
    core.require_admission(campaign)
    if phase == "final":
        core.require_final_selection(campaign)
    stage = core.stage_path(campaign, phase, block)
    registration = core.read(stage/"registration.json")
    core.check((registration["phase"], registration["block"]) == (phase, block), "Heldout directory/index substitution")
    core.validate_registration(campaign, registration)
    envelope = core.read(_audit_reference(stage))
    audit = authority.authenticate(campaign, _stage_purpose(registration), envelope)
    core.check(audit["format"] == core.FORMAT and audit["campaign_id"] == manifest["campaign_id"]
               and audit["phase"] == phase and audit["block"] == block and audit["profile"] == manifest["profile"]
               and audit["approved"] is True and audit["all_actors_regenerated"] is True
               and audit["source_guards"] == registration["source_guards"] and audit["bmcts_audits"] == 0
               and audit["promoted"] is False and audit["audit_replays_are_new_primary_games"] is False,
               "Invalid signed heldout approval")
    core.check(type(audit["actor_log"]) is str and re.fullmatch(r"actor_audits\.[0-9a-f]{32}\.jsonl", audit["actor_log"]), "Invalid audit log identity")
    log = authority.safe_path(campaign, stage.name, audit["actor_log"])
    for name, expected in (("registration.json", audit["registration_sha256"]), ("summary.json", audit["summary_sha256"]),
                           ("games.jsonl", audit["games_sha256"]), (log.name, audit["actor_audits_sha256"])):
        core.check(core.digest((stage/name).read_bytes()) == expected, "Signed heldout raw artifact changed")
    summary, rows = _completed_summary(stage, registration)
    by_fixture = {r["fixture"]: r for r in rows}
    body = log.read_bytes()
    core.check(bool(body) and body.endswith(b"\n"), "Incomplete signed actor log")
    seen, callbacks, oracles = set(), 0, 0
    for line in body.splitlines():
        item = oversight.strict_loads(line)
        identity = item["payload"]["fixture"]
        core.check(identity in by_fixture and identity not in seen, "Wrong signed actor-audit coverage")
        proof = _validate_actor(campaign, registration, item, by_fixture[identity])
        seen.add(identity)
        callbacks += proof["callbacks_regenerated"]
        oracles += proof["public_memory_oracles"]
    core.check(seen == set(by_fixture) and audit["games_audited"] == len(rows)
               and audit["callbacks_regenerated"] == callbacks == len(rows)*320
               and audit["public_memory_oracles"] == oracles
               and audit["primary_games_accepted"] == (len(rows) if manifest["profile"] == "full_primary" else 0),
               "Signed audit aggregates disagree with complete actual coverage")
    return audit


def stage_artifacts(campaign, phase, block):
    stage = core.stage_path(campaign, phase, block)
    envelope = core.read(_audit_reference(stage))
    audit = authority.authenticate(campaign, _stage_purpose(core.read(stage/"registration.json")), envelope)
    target = _audit_reference(stage)
    return [stage/name for name in ("registration.json", "registration.sha256", "summary.json", "summary.sha256",
                                   "games.jsonl", "active_audit.json", audit["actor_log"])]+[target, target.with_suffix(".sha256")]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("admit-development", "admit-final", "prepare", "execute", "audit"))
    parser.add_argument("--campaign", type=Path, required=True)
    parser.add_argument("--phase", choices=("development", "final"), default="development")
    parser.add_argument("--block", type=int, default=0)
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--recover-gate", action="store_true")
    args = parser.parse_args()
    if args.action == "admit-development":
        result = core.admit_development(args.campaign, args.recover_gate)
        print("Development shortlist frozen:", [c["sha256"] for c in result["candidates"]])
    elif args.action == "admit-final":
        result = core.admit_final(args.campaign, args.recover_gate)
        print("Final policy frozen:", result["winner_sha256"])
    elif args.action == "prepare":
        result = core.prepare_stage(args.campaign, args.phase, args.block)
        print("Prepared assignments only:", len(result["fixtures"]))
    else:
        function = execute_stage if args.action == "execute" else audit_stage
        result = function(args.campaign, args.phase, args.block, args.workers)
        print("Completed", args.action, "for", args.phase, "block", args.block,
              "; actual games", result.get("games_completed", result.get("games_audited")),
              "; primary accepted", result.get("primary_games_accepted", 0), "; BMCTS0; promotedFalse")


if __name__ == "__main__":
    main()
