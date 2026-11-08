"""Bounded information-set history-tree search; no production/game credit.

Simulator state is used only by the trusted generative transition and return
functions. Focal tree decisions take a public-history Node, never a Game.
"""
from dataclasses import dataclass, field
import hashlib
import json
import math
import random

from search_coach.belief import PublicBelief, PublicObservation
from search_coach.beam import FAMILIES, rival_action
from tests import reference_engine as engine


MIN_ACTION_VISITS = 2
ORDER = {action: index for index, action in enumerate(engine.ACTIONS)}


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode()


def fingerprint(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def random_seed(*items):
    return int(fingerprint(items)[:32], 16)


def next_history(previous, action, observation):
    """Only public history contributes to an information-set key."""
    return fingerprint([previous, action, observation.serializable()])


@dataclass
class Estimate:
    visits: int = 0
    total: int = 0

    @property
    def mean(self):
        return self.total / self.visits if self.visits else 0.0


@dataclass
class Node:
    history: str
    observation: PublicObservation
    depth: int
    visits: int = 0
    actions: dict = field(default_factory=dict)
    children: dict = field(default_factory=dict)
    pruned: set = field(default_factory=set)
    pruning_events: int = 0

    def __post_init__(self):
        self.actions = {action: Estimate() for action in self.observation.legal_actions}
        self.children = {action: {} for action in self.observation.legal_actions}


def choose_action(node, beam_width):
    """Node-only UCT: no sampled state/model can influence this decision directly."""
    under_sampled = [action for action, value in node.actions.items()
                     if value.visits < MIN_ACTION_VISITS]
    if under_sampled:
        return min(under_sampled, key=lambda action: (node.actions[action].visits, ORDER[action]))
    ranked = sorted(node.actions, key=lambda action: (-node.actions[action].mean, ORDER[action]))
    active = ranked[:beam_width]
    discarded = set(ranked[beam_width:])
    if discarded:
        node.pruned.update(discarded)
        node.pruning_events += 1
    # Values have range 0..6; normalize to 0..1 for a fixed sqrt(2) UCT bonus.
    return max(active, key=lambda action: (
        node.actions[action].mean / 6
        + math.sqrt(2 * math.log(max(1, node.visits)) / node.actions[action].visits),
        -ORDER[action]))


def choose_root_recommendation(node):
    """Highest empirical mean, including sparsely sampled arms; no confidence claim."""
    return max(node.actions, key=lambda action: (node.actions[action].mean, -ORDER[action]))


def pairwise_numerator(scores, focal):
    """Exactly twice official pairwise points: win=2, tie=1, loss=0."""
    own = scores[focal]
    return sum(2 if own > score else 1 if own == score else 0
               for seat, score in enumerate(scores) if seat != focal)


def value(game, focal, income_tail):
    if game.over():
        return pairwise_numerator(game.score, focal), True
    remaining = game.max_turns - game.turn + 1
    tail = min(income_tail, remaining)
    projected = [score + tail * income for score, income in zip(game.score, game.income)]
    return pairwise_numerator(projected, focal), False


def rival_choices(public, focal, root_history, seed, sample, step):
    """Rivals see their own pre-turn public views, never the current focal action."""
    result = {}
    for seat, view in enumerate(public):
        if seat == focal:
            continue
        family = FAMILIES[random_seed(root_history, seed, sample, seat, "family") % len(FAMILIES)]
        rng = random.Random(random_seed(root_history, seed, sample, seat, step, "choice"))
        result[seat] = rival_action(view, family, rng)
    return result


def rollout_action(observation, history, seed):
    # This public-only continuation is shared across particles at the same
    # history. It cannot condition on the simulator's hidden counters/scores.
    rng = random.Random(random_seed(history, seed, "public_focal_rollout"))
    return rival_action(observation, "economic", rng)


def step(game, focal, action, root_history, seed, sample, depth, public):
    if action not in public[focal].legal_actions:
        raise ValueError("Search selected a publicly illegal action")
    rivals = rival_choices(public, focal, root_history, seed, sample, depth)
    joint = [rivals.get(seat, action) for seat in range(4)]
    # Every choice above used the same pre-turn immutable observations. Only
    # after all choices exist does trusted physics resolve them together.
    game.step(joint)
    return tuple(joint)


def prepare(job):
    fields = {"schema", "kind", "job_id", "initial_observation", "transitions", "search"}
    if (type(job) is not dict or set(job) != fields or type(job["schema"]) is not int
            or job["schema"] != 1 or job["kind"] != "public_history_tree_coach"
            or type(job["job_id"]) is not str or not 1 <= len(job["job_id"]) <= 128):
        raise ValueError("Expected the exact public-history tree diagnostic schema")
    options = dict(seed=0, horizon=6, simulations=256, beam_width=6,
                   support_cap=512, income_tail=12, max_nodes=4096)
    limits = dict(seed=(0, 2147483646), horizon=(1, 12), simulations=(1, 2048),
                  beam_width=(1, 6), support_cap=(1, 1024), income_tail=(0, 80), max_nodes=(1, 8192))
    if type(job["search"]) is not dict or not set(job["search"]) <= set(options):
        raise ValueError("Unsupported search options")
    options.update(job["search"])
    for name, option in options.items():
        lo, hi = limits[name]
        if type(option) is not int or not lo <= option <= hi:
            raise ValueError("Invalid bounded search option: " + name)
    if type(job["transitions"]) is not list or len(job["transitions"]) > 79:
        raise ValueError("A complete nonterminal public prefix is required")
    # Insist on serialized four-field views, rather than accepting a caller's
    # mutable PublicBelief or an actual referee object as a shortcut.
    def observation(raw):
        if type(raw) is not dict:
            raise ValueError("Public observations must be four-field dictionaries")
        board, legal = raw.get("board"), raw.get("legal_actions")
        if (type(board) is not list or len(board) != 8
                or any(type(row) is not list or len(row) != 8 for row in board)
                or any(type(cell) is not list or len(cell) != 6 for row in board for cell in row)
                or type(legal) is not list or any(type(action) is not str for action in legal)):
            raise ValueError("Only serialized six-field public cells and action strings are accepted")
        return PublicObservation.from_view(raw)
    opening = observation(job["initial_observation"])
    base = [cell[5] for cell in opening.cells]
    if any(base[r*8+c] != base[r*8+7-c] or base[r*8+c] != base[(7-r)*8+c]
           for r in range(8) for c in range(8)):
        raise ValueError("Opening map must use the official four-way mirror symmetry")
    belief = PublicBelief(opening, cap=options["support_cap"])
    for transition in job["transitions"]:
        if type(transition) is not dict or set(transition) != {"own_action", "observation"}:
            raise ValueError("A prefix contains only own action and public observation")
        if type(transition["own_action"]) is not str:
            raise ValueError("Own accepted action must be a documented string")
        belief.advance(transition["own_action"], observation(transition["observation"]))
    if options["simulations"] < MIN_ACTION_VISITS * len(belief.observation.legal_actions):
        raise ValueError("Simulation budget must explore every legal root action before pruning")
    return belief, options


def recommend(job):
    """Return a finite offline history-tree diagnostic from public JSON only."""
    belief, options = prepare(job)
    root_history, focal = belief.history_sha256, belief.focal
    horizon = min(options["horizon"], 80 - belief.transitions)
    root = Node(root_history, belief.observation, 0)
    nodes = {root_history: root}
    trace = hashlib.sha256()
    turns = terminal = cutoff = cap_events = 0
    for sample in range(options["simulations"]):
        rng = random.Random(random_seed(root_history, options["seed"], sample, "root_state"))
        game = belief._states[rng.randrange(len(belief._states))].clone()
        history, node, path = root_history, root, []
        for depth in range(horizon):
            public = [PublicObservation.from_view(view) for view in game.views()]
            if node is not None:
                if node.observation != public[focal]:
                    raise ValueError("Information-set history has inconsistent public observation")
                action = choose_action(node, options["beam_width"])
                path.append((node, action))
            else:
                action = rollout_action(public[focal], history, options["seed"])
            joint = step(game, focal, action, root_history, options["seed"], sample, depth, public)
            turns += 1
            post = PublicObservation.from_view(game.views()[focal])
            trace.update(canonical([sample, depth, history, joint, post.serializable()])+b"\n")
            child_history = next_history(history, action, post)
            if node is not None:
                obs_hash = fingerprint(post.serializable())
                known = child_history in nodes
                node.children[action][obs_hash] = child_history
                if not known and depth + 1 < horizon and not game.over():
                    if len(nodes) < options["max_nodes"]:
                        nodes[child_history] = Node(child_history, post, depth + 1)
                    else:
                        cap_events += 1
                # Expand one novel history per simulation, then use the
                # public-only rollout. On revisits, this history shares stats.
                node = nodes[child_history] if known else None
            history = child_history
            if game.over():
                break
        result, is_terminal = value(game, focal, options["income_tail"])
        trace.update(canonical([sample, "terminal" if is_terminal else "heuristic", result])+b"\n")
        terminal += int(is_terminal)
        cutoff += int(not is_terminal)
        for selected, action in path:
            selected.visits += 1
            selected.actions[action].visits += 1
            selected.actions[action].total += result
    roots = [dict(action=action, visits=estimate.visits, value_numerator_sum=estimate.total,
                  mean_pairwise_points=estimate.mean / 2,
                  observed_outcome_branches=len(root.children[action]))
             for action, estimate in root.actions.items()]
    roots.sort(key=lambda row: (-row["mean_pairwise_points"], ORDER[row["action"]]))
    summaries = []
    for key, node in sorted(nodes.items()):
        summaries.append(dict(history_sha256=key, depth=node.depth, visits=node.visits,
                              legal_actions=list(node.actions),
                              action_visits={action: item.visits for action, item in node.actions.items()},
                              observed_outcomes={action: len(values) for action, values in node.children.items()},
                              actions_ever_pruned=sorted(node.pruned, key=ORDER.__getitem__),
                              pruning_events=node.pruning_events))
    return dict(schema=1, kind="public_history_observation_branching_mcts_diagnostic", job_id=job["job_id"],
                input_sha256=fingerprint(job), recommended_action=choose_root_recommendation(root), root_estimates=roots,
                trace_sha256=trace.hexdigest(),
                root_recommendation_rule="Highest empirical mean; canonical action tie-break; no confidence bound",
                beam_pruning="Dynamic top-K after minimum action coverage; previously pruned actions may re-enter",
                search=options, effective_horizon=horizon, simulations=options["simulations"],
                synthetic_turns=turns, terminal_evaluations=terminal, heuristic_cutoffs=cutoff,
                tree_nodes=len(nodes), node_cap_events=cap_events, nodes=summaries,
                observation_branching_edges=sum(len(children) > 1 for node in nodes.values()
                                                for children in node.children.values()),
                tree_action_decisions=sum(node.visits for node in nodes.values()),
                root_minimum_action_visits=MIN_ACTION_VISITS, belief=belief.summary(),
                objective="Exact terminal pairwise points; projected-income rank at nonterminal cutoff",
                policy_model="Public-only economic/pressure/wander/hold rival mixture; public economic focal rollout",
                information_set_tree=True, private_state_node_keys=False,
                per_particle_focal_optimization=False, uniform_support_not_calibrated_posterior=True,
                uses_actual_rival_controller_or_future_tape=False, certifies_optimality=False,
                primary_campaign_games=0, completed_per_game_bmcts_audits=0, deployed_policy_changed=False)
