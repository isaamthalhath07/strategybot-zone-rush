"""Audit recorded games through a strict focal-public-prefix boundary.

This observer loads the full transcript to reconstruct the public observations.
Only each focal observation and its own past action are passed to the coach.
The coach never receives the transcript, actual opponent controllers or their
random seeds. The independent observer optionally checks the real hidden state
against an uncapped exact support; those checks are not policy/search inputs.
"""
import argparse
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import time

from tests import reference_engine as ref
from .belief import PublicBelief, state_key, CANONICAL_RULES
from .beam import recommend


ROOT = Path(__file__).resolve().parents[1]


def incumbent():
    spec = importlib.util.spec_from_file_location("public_coach_incumbent", ROOT / "bot.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run(path, output, *, game_count=4, cap=512, search_turns=(12, 34, 60),
        horizon=3, beam_width=2, rollouts=6):
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        data = json.load(handle)
    recorded_rules = data["registration"]["rules"]
    expected_rules = dict(CANONICAL_RULES, legal_excludes_occupied=False)
    if any(name not in expected_rules or type(value) is not bool or value != expected_rules[name]
           for name, value in recorded_rules.items()):
        raise ValueError("this prototype only supports the canonical STAY rule configuration")
    fixtures = {f["id"]: f for f in data["registration"]["spec"]["fixtures"]}
    rows = [g for g in data["games"] if g["candidate"] == "stay_guarded_resilient"]
    # Select round-robin by focal seat so the small audit covers every seat.
    fields = sorted({r["field"] for r in rows})
    pools = {(seat, field): [r for r in rows if r["focal_seat"] == seat and r["field"] == field]
             for seat in range(4) for field in fields}
    selected = []
    for i in range(game_count):
        pool = pools[i % 4, fields[i % len(fields)]]
        selected.append(pool[(37 * i + 11 * (i // 4)) % len(pool)])
    audited = []
    for row in selected:
        fixture = fixtures[row["fixture"]]
        game = ref.Game(base=fixture["base"], start_token=fixture["token"],
                        rules=data["registration"]["rules"])
        focal = row["focal_seat"]
        belief = PublicBelief(game.views()[focal], cap=cap)
        baseline = incumbent()
        snapshots = []
        maximum_support = len(belief._states)
        verified = 1
        start = time.perf_counter()
        for turn, recorded in enumerate(row["actions"], 1):
            public = game.views()[focal]
            baseline_action = baseline.act(public)
            if baseline_action != recorded[focal]:
                raise AssertionError("current incumbent does not reproduce selected transcript")
            if turn in search_turns:
                search_started = time.perf_counter()
                diagnostic = recommend(belief, horizon=horizon, beam_width=beam_width,
                                       rollouts=rollouts, seed=17941,
                                       incumbent_action=baseline_action)
                snapshots.append({"turn": turn, "search_seconds": time.perf_counter() - search_started,
                                  "diagnostic": diagnostic})
            # The complete joint action is used by the observer only AFTER
            # that turn's diagnostic has been produced.
            game.step(recorded)
            belief.advance(recorded[focal], game.views()[focal])
            maximum_support = max(maximum_support, len(belief._states))
            if belief.exact_support:
                if state_key(game) not in {state_key(g) for g in belief._states}:
                    raise AssertionError("exact public-prefix support lost the real state")
                verified += 1
        if game.score != row["scores"]:
            raise AssertionError("reference replay differs from archived scores")
        audited.append({"fixture": row["fixture"], "focal_seat": focal + 1,
                        "map_group": row["map_group"], "field": row["field"],
                        "transitions": len(row["actions"]), "oracle_support_checks": verified,
                        "maximum_support": maximum_support, "final_support": belief.summary(),
                        "snapshots": snapshots, "elapsed_seconds": time.perf_counter() - start})
        print(f"{row['fixture']}: seat {focal+1}, 80 public transitions, max support {maximum_support}", flush=True)
    result = {"schema": 1, "kind": "public_prefix_coach_replay_audit",
              "transcript_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
              "sources_sha256": {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                                 for p in (Path(__file__), Path(__file__).with_name("belief.py"),
                                           Path(__file__).with_name("beam.py"), ROOT / "bot.py",
                                           Path(ref.__file__))},
              "games": audited, "primary_campaign_games": 0,
              "new_champion_claimed": False,
              "coach_inputs": ["initial focal four-field observation", "own past accepted actions",
                               "subsequent focal four-field observations", "explicit diagnostic seed"],
              "limitations": ["uniform support is not a calibrated posterior",
                              "bounded open-loop beam, not full BMCTS",
                              "handwritten rival rollout families are approximations",
                              "short-horizon cutoff value is heuristic",
                              "offline diagnostic has no 200ms deployment guarantee"]}
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    temporary.replace(output)
    print(f"Saved {output}", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=ROOT / "validation/official/followup_results.json.gz")
    parser.add_argument("--output", type=Path, default=ROOT / "search_coach/replay_audit.json")
    parser.add_argument("--games", type=int, default=4)
    parser.add_argument("--cap", type=int, default=512)
    parser.add_argument("--horizon", type=int, default=3)
    parser.add_argument("--beam-width", type=int, default=2)
    parser.add_argument("--rollouts", type=int, default=6)
    args = parser.parse_args()
    if not 1 <= args.games <= 32:
        parser.error("audit 1..32 games")
    run(args.input, args.output, game_count=args.games, cap=args.cap,
        horizon=args.horizon, beam_width=args.beam_width, rollouts=args.rollouts)


if __name__ == "__main__":
    main()
