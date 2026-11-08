"""Prepare first offline GPU diagnostics from public prefixes of archived games.

The observer uses a transcript to reconstruct the past. Joint actions, opponent
identities, private counters and future turns are excluded from every job.
These tasks do not count toward the primary two-million-game campaign.
"""
import argparse
import gzip
import hashlib
import json
from pathlib import Path

from compute_share.gpu_jobs import ROOT, canonical, prepare, sha
from compute_share.doctor import atomic_json
from search_coach.belief import PublicObservation
from tests import reference_engine as engine


def make(output, laptops=5, per_laptop=4, *, start_index=0, horizon=3, plans=8, rollouts=16):
    options = ((laptops, 1, 6), (per_laptop, 1, 16), (horizon, 1, 6),
               (plans, 1, 32), (rollouts, 1, 256))
    if (type(start_index) is not int or start_index < 0
            or any(type(value) is not int or not lo <= value <= hi for value, lo, hi in options)):
        raise ValueError('Invalid diagnostic budget')
    output = Path(output).resolve()
    if output.exists():
        raise FileExistsError('Diagnostic output already exists')
    transcript = ROOT/"validation/official/followup_results.json.gz"
    with gzip.open(transcript, "rt", encoding="utf8") as handle:
        data = json.load(handle)
    fixtures = {f["id"]: f for f in data["registration"]["spec"]["fixtures"]}
    rows = [row for row in data["games"] if row["candidate"] == "stay_guarded_resilient"]
    bundles, origins, seen, payloads = [], [], set(), []
    for laptop in range(laptops):
        jobs = []
        for offset in range(per_laptop):
            index = start_index+laptop*per_laptop+offset
            row = rows[(index*29+7) % len(rows)]
            fixture = fixtures[row["fixture"]]
            focal = row["focal_seat"]
            turn = (12, 34, 60)[index % 3]
            game = engine.Game(base=fixture["base"], start_token=fixture["token"], rules={"catch_requires_stay": True})
            initial = PublicObservation.from_view(game.views()[focal]).serializable()
            transitions = []
            for actions in row["actions"][:turn-1]:
                game.step(actions)
                transitions.append(dict(own_action=actions[focal],
                                        observation=PublicObservation.from_view(game.views()[focal]).serializable()))
            job = dict(schema=1, kind="public_history_gpu_coach", initial_observation=initial,
                       transitions=transitions, search=dict(seed=(202611082601+index) % 2147483647, horizon=horizon,
                           plans_per_root=plans, rollouts_per_plan=rollouts, support_cap=512, income_tail=12))
            identity = sha(canonical(job))
            if identity in seen:
                raise ValueError("Duplicate diagnostic task")
            seen.add(identity)
            job["job_id"] = identity
            jobs.append(job)
            origins.append(dict(job_id=identity, fixture=row["fixture"], focal_seat=focal,
                                prefix_turns=turn-1, laptop=laptop+1))
        trajectories = 0
        for job in jobs:
            final_view = job['transitions'][-1]['observation'] if job['transitions'] else job['initial_observation']
            effective_horizon = min(horizon, 80-len(job['transitions']))
            trajectories += len(final_view['legal_actions'])*min(plans, 6**(effective_horizon-1))*rollouts
        if trajectories > 65536:
            raise ValueError('Diagnostic batch exceeds 65,536 trajectories; reduce its budget')
        payloads.append(dict(schema=1, kind="public_history_gpu_coach_batch", jobs=jobs))
    # Validate all resource budgets before creating any output packages.
    output.mkdir(parents=True, exist_ok=False)
    for laptop, payload in enumerate(payloads):
        directory = output/("laptop_%02d" % (laptop+1))
        archive = prepare(payload, directory)
        bundles.append(dict(laptop=laptop+1, archive=str(archive), sha256=sha(archive.read_bytes()),
                            diagnostics=per_laptop, job_ids=[j["job_id"] for j in payload['jobs']]))
    atomic_json(output/"owner_inventory.json", dict(bundles=bundles, origins=origins,
        original_transcript_sha256=sha(transcript.read_bytes()), disjoint_diagnostic_ids=True,
        primary_campaign_games=0, games_bmcts_audited=0,
        note="Observer-only origin metadata is excluded from worker ZIPs. Diagnostic rollouts, not game executions."))
    return bundles


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--laptops", type=int, default=5)
    parser.add_argument("--jobs-per-laptop", type=int, default=4)
    parser.add_argument("--start-index", type=int, default=0)
    parser.add_argument("--horizon", type=int, default=3)
    parser.add_argument("--plans-per-root", type=int, default=8)
    parser.add_argument("--rollouts-per-plan", type=int, default=16)
    args = parser.parse_args()
    if not 1 <= args.laptops <= 6 or not 1 <= args.jobs_per_laptop <= 16:
        parser.error("Expected1..6 laptops and1..16 diagnostics each")
    print(json.dumps(make(args.output, args.laptops, args.jobs_per_laptop,
                         start_index=args.start_index, horizon=args.horizon,
                         plans=args.plans_per_root, rollouts=args.rollouts_per_plan), indent=2))


if __name__ == "__main__":
    main()
