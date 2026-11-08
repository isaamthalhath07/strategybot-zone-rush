"""Bounded open-loop beam Monte Carlo diagnostic over public-history support.

This is deliberately not a full partially observable BMCTS implementation.
It never optimizes a different focal continuation for each hidden particle.
"""
import hashlib
import math
import random
import statistics

from tests import reference_engine as engine
from .belief import PublicObservation


FAMILIES = ("economic", "pressure", "wander", "hold")


def rival_action(public, family, rng):
    """A fresh decision from public cells and own advertised legal actions only."""
    position = public.positions[public.bot_id - 1]
    cell = public.cells[position]
    choices = public.legal_actions
    # Consume the same number of independent random draws for every player and
    # turn, preserving common random numbers across candidate continuations.
    explore, pick = rng.random(), rng.random()
    if family == "wander" or explore < .12:
        return choices[min(int(pick * len(choices)), len(choices) - 1)]
    if family == "hold" and "STAY" in choices:
        return "STAY"
    if cell[1] == 0 or (cell[1] == public.bot_id and not cell[2]):
        return "STAY"
    if family == "pressure" and cell[1] not in (0, public.bot_id) and not cell[3]:
        return "STAY"
    ranked = []
    for action in choices:
        if action not in engine.MOVES:
            continue
        target = position + engine.MOVES[action]
        target_cell = public.cells[target]
        if target_cell[0]:
            continue
        owner, base = target_cell[1], target_cell[5]
        if owner == 0:
            value = 3 * base
        elif owner != public.bot_id and not target_cell[3]:
            value = (4 if family == "pressure" else 2) * base / (3 if target_cell[2] else 1)
        else:
            r, c = divmod(target, 8)
            value = .1 * (7 - abs(r - 3.5) - abs(c - 3.5))
        ranked.append((value, action))
    if not ranked:
        return "STAY"
    best = max(value for value, action in ranked)
    tied = [action for value, action in ranked if value == best]
    return tied[min(int(pick * len(tied)), len(tied) - 1)]


def evaluate_sequence(belief, sequence, *, rollouts, seed, income_tail):
    values = []
    focal = belief.focal
    public_prefix = belief.history_sha256
    for sample in range(rollouts):
        # This seed is independent of actual rival identity/seed and independent
        # of the candidate sequence. It depends only on the public prefix,
        # explicit diagnostic seed and sample index.
        digest = hashlib.sha256(f"{public_prefix}:{seed}:{sample}".encode()).digest()
        rng = random.Random(int.from_bytes(digest[:16], "big"))
        game = belief._states[rng.randrange(len(belief._states))].clone()
        families = [FAMILIES[rng.randrange(len(FAMILIES))] for _ in range(4)]
        initial_margin = game.score[focal] - sum(game.score[i] for i in range(4) if i != focal) / 3
        for requested in sequence:
            if game.over():
                break
            public = [PublicObservation.from_view(v) for v in game.views()]
            # All players decide from the SAME pre-turn public board. No rival
            # observes the hypothetical focal action before choosing its own.
            joint = [rival_action(view, families[i], rng) for i, view in enumerate(public)]
            joint[focal] = requested if requested in public[focal].legal_actions else "STAY"
            game.step(joint)
        score_margin = game.score[focal] - sum(game.score[i] for i in range(4) if i != focal) / 3
        income_margin = game.income[focal] - sum(game.income[i] for i in range(4) if i != focal) / 3
        remaining = max(0, game.max_turns - game.turn + 1)
        values.append(score_margin - initial_margin + min(income_tail, remaining) * income_margin)
    return {"mean": statistics.fmean(values),
            "sample_sd": statistics.stdev(values) if len(values) > 1 else 0.0,
            "samples": len(values)}


def recommend(belief, *, horizon=3, beam_width=3, rollouts=12, seed=0,
              income_tail=12.0, incumbent_action=None):
    """Return an offline recommendation; never replaces the deployed champion.

    Each root action retains its own continuation beam so a weak shallow score
    cannot eliminate a root before the common final horizon. Beam pruning still
    discards continuations and cannot establish optimality. Every retained plan
    uses one common open-loop requested sequence across all belief particles,
    with a publicly illegal request normalized to STAY at execution.
    """
    if (type(horizon) is not int or not 1 <= horizon <= 6 or type(beam_width) is not int
            or not 1 <= beam_width <= 12 or type(rollouts) is not int or not 1 <= rollouts <= 256
            or not isinstance(seed, int) or not math.isfinite(income_tail) or income_tail < 0):
        raise ValueError("bounded horizon 1..6, beam 1..12 and rollouts 1..256 are required")
    legal = belief.observation.legal_actions
    if incumbent_action is not None and incumbent_action not in legal:
        raise ValueError("incumbent recommendation must be publicly legal")
    evaluated = 0
    roots = []
    for root in legal:
        beams = [(root,)]
        best = None
        for depth in range(1, horizon + 1):
            sequences = beams if depth == 1 else [prefix + (action,)
                         for prefix in beams for action in engine.ACTIONS]
            ranked = []
            for sequence in sequences:
                value = evaluate_sequence(belief, sequence, rollouts=rollouts,
                                          seed=seed, income_tail=income_tail)
                evaluated += 1
                ranked.append({"sequence": sequence, **value})
            ranked.sort(key=lambda row: (-row["mean"], row["sequence"]))
            best = ranked[0]
            beams = [row["sequence"] for row in ranked[:beam_width]]
        roots.append({"action": root, **best})
    roots.sort(key=lambda row: (-row["mean"], engine.ACTIONS.index(row["action"])))
    return {
        "kind": "public_history_open_loop_beam_monte_carlo_diagnostic",
        "recommended_action": roots[0]["action"],
        "incumbent_action": incumbent_action,
        "root_estimates": roots, "horizon": horizon, "beam_width_per_root": beam_width,
        "rollouts_per_sequence": rollouts, "sequences_evaluated": evaluated,
        "income_tail_turns": income_tail, "seed": seed,
        "opponent_model_families": list(FAMILIES),
        "belief": belief.summary(), "certifies_optimality": False,
        "full_bmcts": False, "used_actual_rival_controller_or_future_tape": False,
        "used_per_particle_focal_optimization": False,
        "deployed_policy_changed": False,
    }
