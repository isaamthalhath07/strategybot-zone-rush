"""Falsifiable mathematical diagnostics; no retrospective strength claims.

All policy comparisons use the same legitimate public prefix and copied public-
derived incumbent memory. Actual future actions are used only to replay the
recorded referee path, never to choose a counterfactual action.
"""
import argparse
import copy
import hashlib
import importlib.util
import json
from pathlib import Path

from tests import reference_engine as engine
from evolution.runner import signature

ROOT = Path(__file__).resolve().parents[1]
HERE = ROOT/"evolution/mathematical_candidates"


def load(path):
    spec = importlib.util.spec_from_file_location("mathematical_probe_policy", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def outcome(scores):
    focal = scores[0]
    return dict(scores=scores, pairwise_wins=sum(1 if focal > other else 0.5 if focal == other else 0 for other in scores[1:]),
                own_score=focal, mean_rival_margin=focal-sum(scores[1:])/3)


def terminal_contest_counterexample():
    """A constructed physics proof; no private state is an actor input."""
    game = engine.Game(base=[3]*64, start_token=1, rules={"catch_requires_stay": True})
    game.turn = 80
    game.pos = [27, 29, 63, 56]
    game.owner[27] = game.owner[28] = 1
    game.upg[27] = 1
    game.owner[29], game.upg[29] = 3, 1
    game.prog[1] = 2
    game.score = [1000, 2000, 1005, 500]
    game.income = [sum(game.base[p]*(1+game.upg[p]) for p, owner in enumerate(game.owner) if owner == seat)
                   for seat in range(1, 5)]
    output = []
    for action in ("STAY", "EAST", "SHIELD"):
        counterfactual = game.clone()
        joint = [action, "WEST", "STAY", "STAY"]
        if any(a not in counterfactual.legal(i) for i, a in enumerate(joint)):
            raise AssertionError("Constructed action must be legal")
        counterfactual.step(joint)
        output.append(dict(action=action, joint=joint, positions=counterfactual.pos,
                           owner_of_cell29=counterfactual.owner[29], **outcome(counterfactual.score)))
    return dict(kind="constructed referee counterexample, not a learned or deployed policy",
                cell_values=[3]*64, focal_position=27, focal_owned_contest_destination=28,
                rival_position=29, rival_cell_owner=3, rival_cell_upgraded=True,
                rival_progress=2, scores_before=game.score, turn=80, outcomes=output,
                conclusion="A move can improve pairwise rank by forcing a rival's blocked STAY/raid against a third player, even with unchanged own score.")


def static_proofs():
    candidate = load(HERE/"arrival_lifetime.py")
    helper = candidate._future_task_reward
    return dict(
        neutral_clock=dict(left=11, original_completion=2, delayed_completion=10, value=3,
                           parent_reward=30, corrected_reward=helper(30, 3, 10, 40, 11, 10),
                           exact_delayed_income=3*(11-10+1)),
        raid_clock=dict(original_life=10, delayed_life=2, recurring_income_per_turn=3,
                        raid_cash_after_risk_divisor=24, parent_reward=54,
                        corrected_reward=helper(54, 3, 10, 40, 11, 10), exact_delayed_reward=30),
        rank_utility_counterexample=[outcome([101, 100, 100, 100]), outcome([200, 201, 202, 1])],
        catch_correlation=dict(marginals=[0.6, 0.6], independence_miss=0.16,
                               frechet_miss_bounds=[0.0, 0.4], perfectly_correlated_miss=0.4),
        terminal_contest=terminal_contest_counterexample(),
        illustrative_local_zero_sum_mix=dict(
            attacker_payoff_rows=["STAY", "MOVE"], defender_columns=["DEVELOP", "SHIELD"],
            attacker_payoff=[[48, -18], [0, 12]],
            equilibrium_stay=12/78, equilibrium_shield=48/78, attacker_value=48*12/78,
            caveat="Illustrative local zero-sum surrogate, not an equilibrium proof for the four-player game."))


def public_prefix_probe(directory, count):
    registration = json.loads((directory/"registration.json").read_text())
    body = (ROOT/"bot.py").read_bytes()
    incumbent_sha = hashlib.sha256(body).hexdigest()
    rows = [json.loads(line) for line in (directory/"games.jsonl").read_text().splitlines()]
    rows = sorted((row for row in rows if row["candidate"] == incumbent_sha), key=lambda r: r["fixture"])
    count = min(count, len(rows))
    if count < 1:
        raise ValueError("No recorded incumbent games")
    sampled = [rows[i*len(rows)//count] for i in range(count)]
    fixtures = {f["id"]: f for f in registration["fixtures"]}
    paths = {"baseline_depth2": HERE/"baseline_depth2.py", "arrival_depth3": HERE/"arrival_lifetime.py",
             "arrival_depth2": HERE/"arrival_lifetime_depth2.py"}
    differences = {name: 0 for name in paths}
    phase_differences = {name: {"turn1_40": 0, "turn41_64": 0, "turn65_80": 0} for name in paths}
    largest, examples, checkpoints, helper_calls = [], [], 0, 0
    for row in sampled:
        fixture = fixtures[row["fixture"]]
        focal = fixture["seat"]
        game = engine.Game(base=fixture["base"], start_token=fixture["token"], rules={"catch_requires_stay": True})
        original = load(ROOT/"bot.py")
        variants = {name: load(path) for name, path in paths.items()}
        for turn, joint in enumerate(row["actions"], 1):
            public = game.views()[focal]
            before = signature(public)
            previous = copy.deepcopy(original._history)
            baseline = original.act(public)
            if baseline != joint[focal]:
                raise ValueError("Incumbent did not reproduce the registered public prefix")
            for name, variant in variants.items():
                variant._history = copy.deepcopy(previous)
                values = []
                if hasattr(variant, "_future_task_reward"):
                    helper = variant._future_task_reward
                    def instrumented(*args):
                        corrected = helper(*args)
                        values.append(dict(original=args[0], corrected=corrected, original_life=args[2],
                                           retention=args[3], turns_left=args[4], completion_cost=args[5]))
                        return corrected
                    variant._future_task_reward = instrumented
                try:
                    action = variant.act(public)
                finally:
                    if hasattr(variant, "_future_task_reward"):
                        variant._future_task_reward = helper
                if values:
                    helper_calls += len(values)
                    largest.extend(dict(value, fixture=row["fixture"], turn=turn, variant=name)
                                   for value in values if value["original"] > value["corrected"]+1e-8)
                    largest.sort(key=lambda v: v["original"]-v["corrected"], reverse=True)
                    largest = largest[:10]
                if (action not in public.legal_actions or signature(public) != before
                        or variant._input_failures or variant._policy_failures):
                    raise ValueError("Diagnostic policy contract failed")
                memory = variant._history[focal+1]
                if (memory["inference_failures"] or memory["progress"] != game.prog[focal]
                        or memory["scores"][1:] != game.score
                        or any(game.cd[s] not in memory["cooldown_possible"][s+1] for s in range(4))):
                    raise ValueError("Public-history diagnostic lost an actual possibility")
                if action != baseline:
                    differences[name] += 1
                    phase = "turn1_40" if turn <= 40 else "turn41_64" if turn <= 64 else "turn65_80"
                    phase_differences[name][phase] += 1
                    if name == "arrival_depth3" and len(examples) < 6:
                        examples.append(dict(fixture=row["fixture"], map_id=fixture["map_id"], focal_seat=focal,
                                             turn=turn, incumbent=baseline, candidate=action,
                                             current_position=game.pos[focal],
                                             original_target=original._history[focal+1]["prior_target"],
                                             candidate_target=memory["prior_target"]))
            checkpoints += 1
            game.step(joint)
        if game.score != row["scores"]:
            raise ValueError("Recorded referee scores changed")
    return dict(registration_sha256=hashlib.sha256((directory/"registration.json").read_bytes()).hexdigest(),
                games=count, public_decision_checkpoints=checkpoints, original_actions_reproduced=checkpoints,
                variant_decisions=checkpoints*len(paths), contract_failures=0,
                action_differences=differences, phase_differences=phase_differences,
                reward_recalculations=helper_calls, largest_reward_corrections=largest, examples=examples,
                inputs="Four-field public views plus copied public-history-derived incumbent memory only",
                claimed_new_games=0, claimed_strength_improvement=False,
                caveat="Fixed-prefix diagnostics differ from closed-loop games. No hindsight opponent actions enter a decision.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--round", type=Path, default=ROOT/".cache/evolution/confirmation_001")
    parser.add_argument("--games", type=int, default=16)
    parser.add_argument("--output", type=Path, default=HERE/"mathematical_probe.json")
    args = parser.parse_args()
    if args.games < 1:
        parser.error("Positive game count required")
    paths = [ROOT/"bot.py", Path(__file__), HERE/"build_arrival.py"]+list(HERE.glob("*_depth2.py"))+[HERE/"arrival_lifetime.py"]
    guards = {str(path.relative_to(ROOT)).replace("\\", "/"): hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}
    result = dict(format="zone-rush-mathematical-probes/1", sources=guards,
                  analytical=static_proofs(), public_prefix_diagnostic=public_prefix_probe(args.round, args.games))
    for relative, expected in guards.items():
        if hashlib.sha256((ROOT/relative).read_bytes()).hexdigest() != expected:
            raise ValueError("Source changed during probe")
    args.output.write_text(json.dumps(result, indent=2)+"\n", encoding="utf8", newline="\n")
    print(json.dumps(result["public_prefix_diagnostic"], indent=2), flush=True)


if __name__ == "__main__":
    main()
