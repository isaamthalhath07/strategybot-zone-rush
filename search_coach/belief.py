"""Hidden-state support reconstructed exclusively from a complete public prefix.

This is a support filter, not a Bayesian posterior. Rival action likelihoods
are unknown; possible states are retained without inventing those likelihoods.
"""
from dataclasses import dataclass
import hashlib
import itertools
import json

from tests import reference_engine as engine


PUBLIC_FIELDS = frozenset(("board", "bot_id", "is_priority_token", "legal_actions"))
CELL_FIELDS = ("occupant", "owner", "is_upgraded", "is_home", "is_frozen", "base_points")
CANONICAL_RULES = {
    "frozen_stay_counts": False, "claim_resets_progress": True,
    "catch_requires_stay": True, "lost_contest_is_stay": True,
    "home_upgradable": True,
}


class InconsistentObservation(ValueError):
    """The observed prefix cannot be explained by the retained support."""


def field(obj, name):
    return obj[name] if isinstance(obj, dict) else getattr(obj, name)


def action_name(action):
    name = action if isinstance(action, str) else getattr(action, "name", None)
    if name not in engine.ACTIONS:
        raise ValueError("action must be one of the six documented action names")
    return name


@dataclass(frozen=True)
class PublicObservation:
    """An immutable copy of the four public fields; contains no referee object."""

    cells: tuple
    bot_id: int
    is_priority_token: bool
    legal_actions: tuple

    @classmethod
    def from_view(cls, view):
        if isinstance(view, cls):
            return view
        if isinstance(view, dict) and set(view) != PUBLIC_FIELDS:
            raise ValueError("a public dictionary must contain exactly the four documented fields")
        board = field(view, "board")
        if len(board) != 8 or any(len(row) != 8 for row in board):
            raise ValueError("an 8 by 8 board is required")
        cells = []
        for row in board:
            for cell in row:
                if isinstance(cell, (tuple, list)):
                    if len(cell) != len(CELL_FIELDS):
                        raise ValueError("serialized cells need six public fields")
                    values = tuple(cell)
                else:
                    values = tuple(field(cell, name) for name in CELL_FIELDS)
                occupant, owner, upgraded, home, frozen, base = values
                if (type(occupant) is not int or occupant not in range(5)
                        or type(owner) is not int or owner not in range(5)
                        or type(base) is not int or base not in (1, 2, 3)
                        or any(type(flag) is not bool for flag in (upgraded, home, frozen))):
                    raise ValueError("invalid public cell values")
                cells.append(values)
        bot_id = field(view, "bot_id")
        priority = field(view, "is_priority_token")
        legal = tuple(action_name(a) for a in field(view, "legal_actions"))
        if (type(bot_id) is not int or bot_id not in range(1, 5)
                or type(priority) is not bool or not legal or len(set(legal)) != len(legal)):
            raise ValueError("invalid public identity, priority or action list")
        if sorted(c[0] for c in cells if c[0]) != [1, 2, 3, 4]:
            raise ValueError("each player must occupy exactly one cell")
        legal = tuple(a for a in engine.ACTIONS if a in legal)
        return cls(tuple(cells), bot_id, priority, legal)

    @property
    def positions(self):
        result = [None] * 4
        for p, cell in enumerate(self.cells):
            if cell[0]:
                result[cell[0] - 1] = p
        return tuple(result)

    def serializable(self):
        return {"board": [[list(c) for c in self.cells[r * 8:(r + 1) * 8]]
                          for r in range(8)],
                "bot_id": self.bot_id, "is_priority_token": self.is_priority_token,
                "legal_actions": list(self.legal_actions)}


def state_key(game):
    """Used only for deduplicating reconstructed states, never actual-state input."""
    return (tuple(game.owner), tuple(game.upg), tuple(game.pos), tuple(game.frozen),
            tuple(game.cd), tuple(game.prog), tuple(game.score), tuple(game.income),
            game.turn, game.token)


def matches(game, observation):
    return PublicObservation.from_view(game.views()[observation.bot_id - 1]) == observation


class PublicBelief:
    """All retained canonical-rule explanations of a complete public prefix.

    Initialize at the actual opening, then advance with only own accepted action
    and the next own public view. Legal, on-time own actions are assumed accepted;
    silent server substitutions are not observable acknowledgements. The filter
    supports canonical cooldown-filtered legal lists, not an undocumented server
    variant. A cold start midway through a game is deliberately rejected.
    """

    def __init__(self, initial_view, *, cap=512):
        if type(cap) is not int or cap < 1:
            raise ValueError("cap must be a positive integer")
        self.cap = cap
        self.observation = PublicObservation.from_view(initial_view)
        self.focal = self.observation.bot_id - 1
        base = [c[5] for c in self.observation.cells]
        # A False priority flag identifies three possible holders, not one.
        states = [engine.Game(base=base, rules=CANONICAL_RULES, start_token=token)
                  for token in range(1, 5)]
        self._states = [g for g in states if matches(g, self.observation)]
        if not self._states:
            raise InconsistentObservation("opening does not match canonical initial state")
        self.transitions = 0
        self.dropped_states = 0
        self.exact_support = True
        self.trace = [{"observation": self.observation.serializable()}]
        self._apply_cap()

    def _apply_cap(self):
        self._states.sort(key=state_key)
        if len(self._states) > self.cap:
            self.dropped_states += len(self._states) - self.cap
            self.exact_support = False
            self._states = self._states[:self.cap]

    @property
    def history_sha256(self):
        data = json.dumps(self.trace, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(data).hexdigest()

    def advance(self, own_action, next_view):
        """Condition support on one observed transition, transactionally."""
        own_action = action_name(own_action)
        if own_action not in self.observation.legal_actions:
            raise ValueError("own accepted action must have been publicly legal")
        post = PublicObservation.from_view(next_view)
        if post.bot_id != self.observation.bot_id:
            raise ValueError("focal identity cannot change")
        after_positions = post.positions
        compatible = {}
        tried = 0
        for previous in self._states:
            options = []
            for seat in range(4):
                if seat == self.focal:
                    options.append((own_action,))
                elif after_positions[seat] != previous.pos[seat]:
                    delta = after_positions[seat] - previous.pos[seat]
                    move = next((a for a, d in engine.MOVES.items() if d == delta), None)
                    options.append((move,) if move in previous.legal(seat) else ())
                else:
                    # Failed movement has exactly the STAY effects under the
                    # canonical lost-contest/occupied-cell rules. A stationary
                    # available shielder is the only other hidden possibility.
                    options.append(("STAY", "SHIELD") if not previous.frozen[seat]
                                   and not previous.cd[seat] else ("STAY",))
            for joint in itertools.product(*options):
                tried += 1
                candidate = previous.clone()
                candidate.step(joint)
                if matches(candidate, post):
                    compatible.setdefault(state_key(candidate), candidate)
        if not compatible:
            suffix = " after a capped approximation" if not self.exact_support else ""
            raise InconsistentObservation("no retained canonical explanation" + suffix)
        self._states = list(compatible.values())
        self._apply_cap()
        self.observation = post
        self.transitions += 1
        self.trace.append({"own_action": own_action, "observation": post.serializable()})
        return {"candidates_tested": tried, **self.summary()}

    def summary(self):
        return {
            "transitions": self.transitions, "support_states": len(self._states),
            "cap": self.cap, "dropped_states": self.dropped_states,
            "exact_support": self.exact_support,
            "possible_tokens": sorted({g.token for g in self._states}),
            "cooldown_domains": [sorted({g.cd[i] for g in self._states}) for i in range(4)],
            "progress_domains": [sorted({g.prog[i] for g in self._states}) for i in range(4)],
            "history_sha256": self.history_sha256,
            "belief_weights": "uniform support; not calibrated action likelihoods",
        }
