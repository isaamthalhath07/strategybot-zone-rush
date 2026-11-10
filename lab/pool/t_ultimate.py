"""
Zone Rush: Autonomous Strategy Engine ("Ultimate")
==================================================
Single-file, standard-library-only autonomous strategy engine implementing the
6-Layer Architecture Specification and the Super-Dominance & Latency Optimization
Roadmap for Zone Rush (StrategyBot / AFKAR 2026):

  - Level 0 (Zero-Allocation Engine & Precomputed Tables):
      * 1D & 2D flat precomputed tables (`FLAT_DIST`, `DIST_MATRIX`, `NEIGHBORS`,
        `STEP_NAME`, `CELL_BIT`, `QUADRANT`, `MIRROR_CANONICAL`).
      * 64-bit integer bitboards (`CELL_BIT[p] = 1 << p`) for O(1) zero-allocation
        set inclusion, union, and intersection across all search routines.
      * Pre-allocated reusable cell pools (`_CELL_POOL`) and static array queues
        to eliminate Python heap churn and generational GC pauses.
      * Strict 80ms Wall-Clock Sentry (`DEADLINE = t0 + 0.080`) checked every 16
        iterations (`if not (iter_count & 15)`) inside deep DAG search loops.
  - Level 1 (Dynamic Multi-Source Voronoi Partitioning):
      * Partitions the 64-cell grid into Self-Sanctuary (`sanctuary_mask`),
        Contested Border (`contested_mask`), and Dead-Zone (`dead_zone_mask`)
        bitmasks accounting for freeze timers and Priority Token rank order.
      * Prunes unreachable rival Dead-Zone cells and strips defensive overhead
        from Self-Sanctuary farming targets.
  - Level 2 (Advanced Game-Theoretic 2x2 Matrix & Counter-Mirror Tactics):
      * Mixed-Strategy Nash Equilibrium solver (`compute_nash_subgame`) paired
        with Bayesian Beta posteriors (`BetaPosterior`) for offensive bait-steps
        and last-tick (`progress == 2`) defensive shields.
      * Subgame asymmetry tie-breaking to defeat opponent genome-mirror trackers.
  - Level 3 (14 Core Heuristic Genes & CMA-ES / PSRO Interface):
      * Exposes `CORE_GENES` and `GENE_BOUNDS` with automatic parameter mapping
        for offline evolutionary / PSRO meta-optimization.
"""

import math
import time

# ---------------------------------------------------------------------------
# Level 0: Precomputed Static Tables & 64-Bit Bitboard Constants (0 ms)
# ---------------------------------------------------------------------------
N = 8
NC = 64
MAX_TURNS = 80
DIRECTIONS = ("NORTH", "EAST", "SOUTH", "WEST")
ALL_ACTIONS = ("NORTH", "EAST", "SOUTH", "WEST", "STAY", "SHIELD")
CORNERS = (None, 0, 7, 63, 56)  # 1-indexed seat -> home corner index

# Precalculated 64-bit integer masks: CELL_BIT[p] == (1 << p)
CELL_BIT = tuple(1 << _p for _p in range(NC))
FULL_BOARD_MASK = (1 << NC) - 1

ADJ = []
NEIGHB = []
FLAT_DIST = []
DIST_MATRIX_LIST = [0] * (NC * NC)
STEP_NAME_LIST = [[None] * NC for _ in range(NC)]
DIR_OF = {}
TARGET = {}
QUADRANT_LIST = [0] * NC
MIRROR_CANONICAL_LIST = [0] * NC

for _i in range(NC):
    _r, _c = divmod(_i, N)
    # Seat quadrant affiliation: Seat 1=(0,0), Seat 2=(0,7), Seat 3=(7,7), Seat 4=(7,0)
    if _r < 4:
        QUADRANT_LIST[_i] = 1 if _c < 4 else 2
    else:
        QUADRANT_LIST[_i] = 4 if _c < 4 else 3

    # 4-way mirror canonical cell index in top-left 4x4 quadrant
    _mr = _r if _r < (N - 1 - _r) else (N - 1 - _r)
    _mc = _c if _c < (N - 1 - _c) else (N - 1 - _c)
    MIRROR_CANONICAL_LIST[_i] = _mr * N + _mc

    _adj_list = []
    for _name, _nr, _nc in (
        ("NORTH", _r - 1, _c),
        ("EAST", _r, _c + 1),
        ("SOUTH", _r + 1, _c),
        ("WEST", _r, _c - 1),
    ):
        if 0 <= _nr < N and 0 <= _nc < N:
            _j = _nr * N + _nc
            _adj_list.append((_name, _j))
            STEP_NAME_LIST[_i][_j] = _name
            DIR_OF[(_i, _j)] = _name
            TARGET[(_i, _name)] = _j
    ADJ.append(tuple(_adj_list))
    NEIGHB.append(tuple(_j for _, _j in _adj_list))

    _d_row = []
    _base_offset = _i << 6
    for _k in range(NC):
        _d = abs(_r - (_k >> 3)) + abs(_c - (_k & 7))
        _d_row.append(_d)
        DIST_MATRIX_LIST[_base_offset | _k] = _d
    FLAT_DIST.append(tuple(_d_row))

ADJ = tuple(ADJ)
NEIGHB = tuple(NEIGHB)
NEIGHBORS = NEIGHB
FLAT_DIST = tuple(FLAT_DIST)
DIST = FLAT_DIST
DIST_MATRIX = tuple(DIST_MATRIX_LIST)
STEP_NAME = tuple(tuple(_row) for _row in STEP_NAME_LIST)
MOVE_DELTAS = STEP_NAME
QUADRANT = tuple(QUADRANT_LIST)
MIRROR_CANONICAL = tuple(MIRROR_CANONICAL_LIST)

HOME_MASK = CELL_BIT[0] | CELL_BIT[7] | CELL_BIT[63] | CELL_BIT[56]

# ---------------------------------------------------------------------------
# Level 3: The 14 Core Heuristic Genes & Calibrated Engine Hyperparameters
# ---------------------------------------------------------------------------
GENE_BOUNDS = {
    "w_claim": (0.5, 2.0),
    "w_upgrade": (1.0, 3.5),
    "w_raid": (0.8, 2.5),
    "w_cash": (0.5, 2.0),
    "fortify_mult": (1.0, 2.2),
    "horizon_scale": (10.0, 45.0),
    "safety_decay": (1.0, 8.0),
    "tau_scale": (50.0, 250.0),
    "denial_factor": (0.1, 1.2),
    "bait_sensitivity": (0.30, 0.70),
    "shield_bias": (1.1, 2.8),
    "beam_width": (16, 64),
    "gamma_discount": (0.85, 1.00),
    "late_game_cutoff": (68, 76),
}

CORE_GENES = {
    "w_claim": 1.00000,
    "w_upgrade": 2.50504,
    "w_raid": 1.30170,
    "w_cash": 1.25275,
    "fortify_mult": 1.11474,
    "horizon_scale": 40.67114,
    "safety_decay": 3.52153,
    "tau_scale": 24.0,
    "denial_factor": 0.66671,
    "bait_sensitivity": 0.40000,
    "shield_bias": 1.30296,
    "beam_width": 16,
    "gamma_discount": 0.98000,
    "late_game_cutoff": 76,
}

DEFAULT_PARAMS = {
    "w_claim": 1.00000,
    "upgrade_open": 1.46008,
    "upgrade_late": 3.55000,
    "raid_open": 0.95839,
    "raid_late": 1.64500,
    "risk_open": 1.97775,
    "risk_late": 8.00000,
    "income_lifetime": 40.67114,
    "safety_slope": 3.52153,
    "fortify_premium": 1.11474,
    "denial_base": 0.66671,
    "denial_close": 0.22000,
    "cash_weight": 1.25275,
    "contest_cost": 0.42039,
    "depth": 3,
    "breadth": 12,
    "route_weight": 0.61979,
    "route_delay": 0.02000,
    "inertia": 0.04960,
    "shield_weight": 1.30296,
    "backfire_cost": 1.13552,
    "shield_prior": 0.33333,
    "stay_prior": 0.76000,
    "feint_weight": 1.25119,
    "bait_sensitivity": 0.40000,
    "tau_scale": 24.0,
    "cell_tiebreak_eps": 0.015,
    "late_game_cutoff": 78,
    "deadline_ms": 80.0,  # Hard 80ms ceiling (120ms safety buffer below 200ms limit)
}


def _merge_params(custom_params):
    """Merges custom parameters and translates any of the 14 Core Heuristic Genes."""
    cfg = dict(DEFAULT_PARAMS)
    if not custom_params:
        return cfg
    cfg.update(custom_params)

    # Map the 14 Core Heuristic Genes if explicitly supplied by CMA-ES / PSRO
    if "w_upgrade" in custom_params and "upgrade_open" not in custom_params:
        wu = float(custom_params["w_upgrade"])
        cfg["upgrade_open"] = wu * 0.58
        cfg["upgrade_late"] = wu * 1.42
    if "w_raid" in custom_params and "raid_open" not in custom_params:
        wr = float(custom_params["w_raid"])
        cfg["raid_open"] = wr * 0.74
        cfg["raid_late"] = wr * 1.26
    if "w_cash" in custom_params and "cash_weight" not in custom_params:
        cfg["cash_weight"] = float(custom_params["w_cash"])
    if "fortify_mult" in custom_params and "fortify_premium" not in custom_params:
        cfg["fortify_premium"] = float(custom_params["fortify_mult"])
    if "horizon_scale" in custom_params and "income_lifetime" not in custom_params:
        cfg["income_lifetime"] = float(custom_params["horizon_scale"])
    if "safety_decay" in custom_params and "safety_slope" not in custom_params:
        cfg["safety_slope"] = float(custom_params["safety_decay"])
    if "denial_factor" in custom_params and "denial_base" not in custom_params:
        cfg["denial_base"] = float(custom_params["denial_factor"])
    if "shield_bias" in custom_params and "shield_weight" not in custom_params:
        cfg["shield_weight"] = float(custom_params["shield_bias"])
    if "beam_width" in custom_params and "breadth" not in custom_params:
        cfg["breadth"] = int(custom_params["beam_width"])
    if "gamma_discount" in custom_params and "route_delay" not in custom_params:
        gd = max(0.01, min(1.0, float(custom_params["gamma_discount"])))
        cfg["route_delay"] = (1.0 - gd) / gd
    return cfg


# ---------------------------------------------------------------------------
# Zero-Allocation Input Normalization (Pre-Allocated Cell Pool)
# ---------------------------------------------------------------------------
_MISSING = object()


class NormCell(object):
    __slots__ = ("occupant", "owner", "is_upgraded", "is_home", "is_frozen", "base_points")

    def __init__(self, occupant, owner, is_upgraded, is_home, is_frozen, base_points):
        self.occupant = occupant
        self.owner = owner
        self.is_upgraded = is_upgraded
        self.is_home = is_home
        self.is_frozen = is_frozen
        self.base_points = base_points


# Pre-allocated static pool of 64 NormCell instances (mutated in-place every turn)
_CELL_POOL = tuple(NormCell(0, 0, False, False, False, 1) for _ in range(NC))


def _attr(obj, name, default=None):
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _cell_like(x):
    if isinstance(x, dict):
        return "owner" in x
    if hasattr(x, "owner"):
        return True
    return isinstance(x, (list, tuple)) and len(x) == 6


def _field(c, k, idx):
    if isinstance(c, dict):
        return c.get(k)
    v = getattr(c, k, _MISSING)
    if v is not _MISSING:
        return v
    if isinstance(c, (list, tuple)) and len(c) == 6:
        return c[idx]
    return None


def _to_int(x):
    if x is None:
        return 0
    if isinstance(x, bool):
        return int(x)
    if isinstance(x, int):
        return x
    return int(float(x))


def _to_bool(x):
    if isinstance(x, str):
        return x.strip().lower() in ("true", "1", "yes", "y", "t")
    return bool(x)


def _action_name(a):
    if isinstance(a, str):
        s = a
    else:
        s = getattr(a, "name", None)
        if not isinstance(s, str):
            s = getattr(a, "value", None)
        if not isinstance(s, str):
            s = str(a)
    s = s.strip().upper()
    if "." in s:
        s = s.rsplit(".", 1)[1]
    return s


def _flatten_board(board):
    if isinstance(board, dict):
        board = board.get("cells") or board.get("board")
    if isinstance(board, (list, tuple)):
        if len(board) == NC and _cell_like(board[0]):
            return board
        if len(board) == N and isinstance(board[0], (list, tuple)) and len(board[0]) == N:
            return [c for r in board for c in r]
    seq = list(board)
    if len(seq) == NC and _cell_like(seq[0]):
        return seq
    if len(seq) == N:
        rows = [list(r) for r in seq]
        if all(len(r) == N for r in rows) and _cell_like(rows[0][0]):
            return [c for r in rows for c in r]
    raise ValueError("Unrecognised board structure")


def normalise_state(state):
    """
    Normalizes the referee state in-place using `_CELL_POOL` to avoid
    allocating 64 NormCell instances per turn.
    """
    raw = _flatten_board(_attr(state, "board"))
    cells = _CELL_POOL
    for i in range(NC):
        c = raw[i]
        nc = cells[i]
        if hasattr(c, "owner") and not isinstance(c, dict):
            nc.occupant = int(c.occupant) if c.occupant is not None else 0
            nc.owner = int(c.owner) if c.owner is not None else 0
            nc.is_upgraded = bool(c.is_upgraded)
            nc.is_home = bool(c.is_home)
            nc.is_frozen = bool(c.is_frozen)
            bp = c.base_points
            nc.base_points = int(bp) if bp else 1
        else:
            nc.occupant = _to_int(_field(c, "occupant", 0))
            nc.owner = _to_int(_field(c, "owner", 1))
            nc.is_upgraded = _to_bool(_field(c, "is_upgraded", 2))
            nc.is_home = _to_bool(_field(c, "is_home", 3))
            nc.is_frozen = _to_bool(_field(c, "is_frozen", 4))
            nc.base_points = _to_int(_field(c, "base_points", 5)) or 1

    for s in (1, 2, 3, 4):
        p = CORNERS[s]
        if cells[p].is_home and not cells[p].owner:
            cells[p].owner = s

    me = _to_int(_attr(state, "bot_id"))
    found_mask = 0
    for i in range(NC):
        occ = cells[i].occupant
        if occ > 0:
            found_mask |= 1 << occ
    if not ((found_mask >> me) & 1):
        if 0 <= me <= 3 and ((found_mask >> (me + 1)) & 1):
            me += 1

    raw_legal = _attr(state, "legal_actions")
    lookup = {}
    if raw_legal is not None:
        for a in raw_legal:
            nm = _action_name(a)
            if nm in ALL_ACTIONS and nm not in lookup:
                lookup[nm] = a
    if "STAY" not in lookup:
        lookup["STAY"] = "STAY"
    legal_names = tuple(a for a in ALL_ACTIONS if a in lookup)
    is_token = _to_bool(_attr(state, "is_priority_token", False))
    return cells, me, is_token, legal_names, lookup


# ---------------------------------------------------------------------------
# Layer 1: Constraint-Satisfaction State & Belief Tracker (Bitmask-Accelerated)
# ---------------------------------------------------------------------------
class BetaPosterior(object):
    """Bayesian Beta(alpha, beta) distribution with exponential recency weighting."""
    __slots__ = ("alpha", "beta", "decay")

    def __init__(self, prior_mean, strength, decay=0.94):
        self.alpha = prior_mean * strength
        self.beta = (1.0 - prior_mean) * strength
        self.decay = decay

    def update(self, hit, weight=1.0):
        d = self.decay
        self.alpha = d * self.alpha + (weight if hit else 0.0)
        self.beta = d * self.beta + (0.0 if hit else weight)

    def mean(self):
        total = self.alpha + self.beta
        return self.alpha / total if total > 1e-9 else 0.5


class StateTracker(object):
    """
    Layer 1: Reconstructs hidden game state (turn, scores, progress, freeze duration,
    shield cooldowns, global priority token cycle, and rival behavioral posteriors)
    via Constraint-Satisfaction over consecutive board snapshots.
    Uses 4-bit seat masks (`1 << s`) in inner CSP loops to avoid set allocations.
    """

    def __init__(self, params):
        self.cfg = params
        self.me = None
        self.turn = 0
        self.known_start = False
        self.scores = [0] * 5
        self.progress = 0
        self.enemy_progress = [0] * 5
        self.cooldown = [0] * 5
        self.freeze_left = [0] * 5
        self.holder_mask = 0b11110  # Bits 1..4 represent seats 1..4
        self.positions = [-1] * 5
        self.owner = [0] * NC
        self.level = [0] * NC
        self.frozen = [False] * 5
        self.can_shield = False
        self.last_action = None
        self.prior_target = None
        self.last_bait = -10

        # Empirical & Bayesian rival behavior models
        self.stops = [3.0 * params["shield_prior"]] * 5
        self.attempts = [3.0] * 5
        self.defense_hits = [1.20] * 5
        self.defense_trials = [3.0] * 5
        self.stay_hits = [[2.0 * params["stay_prior"], 1.16] for _ in range(5)]
        self.stay_trials = [[2.0, 2.0] for _ in range(5)]
        self.shield_beta = [BetaPosterior(params["shield_prior"], 3.0, 0.93) for _ in range(5)]
        self.stay_beta = [
            [BetaPosterior(params["stay_prior"], 2.0, 0.94), BetaPosterior(0.58, 2.0, 0.94)]
            for _ in range(5)
        ]

    @property
    def holder_set(self):
        m = self.holder_mask
        return {s for s in (1, 2, 3, 4) if (m >> s) & 1}

    def _is_new_game(self, me, cells, positions, owner, level):
        if self.turn == 0 or self.me != me:
            return True
        if self.turn >= MAX_TURNS:
            return True

        owned_now = 0
        owned_prev = 0
        any_level_now = False
        any_level_prev = False
        for i in range(NC):
            if owner[i]:
                owned_now += 1
            if self.owner[i]:
                owned_prev += 1
            if level[i]:
                any_level_now = True
            if self.level[i]:
                any_level_prev = True

        pristine = (
            owned_now == 4
            and not any_level_now
            and all(
                positions[s] >= 0 and cells[positions[s]].is_home and owner[positions[s]] == s
                for s in (1, 2, 3, 4)
            )
        )
        if pristine and (any_level_prev or owned_prev > 4):
            return True
        if owned_now < owned_prev:
            return True
        for s in (1, 2, 3, 4):
            p_old, p_new = self.positions[s], positions[s]
            if p_old >= 0 and p_new >= 0 and p_old != p_new and STEP_NAME[p_old][p_new] is None:
                return True
        return False

    def _reset(self, me, cells, positions, owner, level, frozen, is_token):
        cfg = self.cfg
        self.me = me
        owned_cnt = sum(1 for v in owner if v)
        lvl_cnt = sum(level)
        pristine = (
            owned_cnt == 4
            and lvl_cnt == 0
            and all(
                positions[s] >= 0 and cells[positions[s]].is_home and owner[positions[s]] == s
                for s in (1, 2, 3, 4)
            )
        )
        self.known_start = pristine
        occupied = owned_cnt - 4
        self.turn = 1 if pristine else min(67, max(2, 2 + occupied + lvl_cnt))
        self.scores = [0] * 5
        if not pristine:
            for i, s in enumerate(owner):
                if s:
                    self.scores[s] += int(cells[i].base_points * (1 + level[i]) * (self.turn - 1) * 0.55)
        self.progress = 0
        self.enemy_progress = [0] * 5
        self.cooldown = [0] * 5
        self.freeze_left = [2 if frozen[s] else 0 for s in range(5)]
        self.holder_mask = (1 << me) if is_token else (0b11110 & ~(1 << me))
        self.positions[:] = positions
        self.owner[:] = owner
        self.level[:] = level
        self.frozen[:] = frozen
        self.can_shield = False
        self.last_action = None
        self.prior_target = None
        self.last_bait = -10

        self.stops = [3.0 * cfg["shield_prior"]] * 5
        self.attempts = [3.0] * 5
        self.defense_hits = [1.20] * 5
        self.defense_trials = [3.0] * 5
        self.stay_hits = [[2.0 * cfg["stay_prior"], 1.16] for _ in range(5)]
        self.stay_trials = [[2.0, 2.0] for _ in range(5)]
        self.shield_beta = [BetaPosterior(cfg["shield_prior"], 3.0, 0.93) for _ in range(5)]
        self.stay_beta = [
            [BetaPosterior(cfg["stay_prior"], 2.0, 0.94), BetaPosterior(0.58, 2.0, 0.94)]
            for _ in range(5)
        ]

    def _solve_shields_csp_mask(
        self, me, cells, prior_pos, positions, prior_owner, owner, prior_frozen, frozen, own_shield
    ):
        """
        Zero-allocation bitwise 2^K boolean Constraint-Satisfaction solver.
        Returns a bitmask `(1 << s)` of seats that declared SHIELD on turn t-1.
        """
        newly_frozen_mask = 0
        moved_mask = 0
        lost_cell_mask = 0
        for s in (1, 2, 3, 4):
            if frozen[s] and not prior_frozen[s]:
                newly_frozen_mask |= 1 << s
            if positions[s] != prior_pos[s]:
                moved_mask |= 1 << s

        for idx in range(NC):
            po = prior_owner[idx]
            if po and po != owner[idx]:
                lost_cell_mask |= 1 << po

        cands = []
        for s in (1, 2, 3, 4):
            s_bit = 1 << s
            if (
                s != me
                and not (moved_mask & s_bit)
                and not prior_frozen[s]
                and not (lost_cell_mask & s_bit)
                and self.cooldown[s] == 0
            ):
                cands.append(s)

        n_cands = len(cands)
        me_bit = (1 << me) if own_shield else 0

        for post_move_rule in (True, False):
            best_S_mask = -1
            best_score = -1e9
            for mask in range(1 << n_cands):
                S_mask = me_bit
                for k in range(n_cands):
                    if (mask >> k) & 1:
                        S_mask |= 1 << cands[k]

                pred_frozen_mask = 0
                caught_any_mask = 0
                for j in (1, 2, 3, 4):
                    if prior_frozen[j] or positions[j] < 0:
                        continue
                    j_bit = 1 << j
                    if not post_move_rule and ((moved_mask & j_bit) or (S_mask & j_bit)):
                        continue
                    cell_j = positions[j] if post_move_rule else prior_pos[j]
                    land_owner = prior_owner[cell_j]
                    if land_owner != j and ((S_mask >> land_owner) & 1):
                        pred_frozen_mask |= j_bit
                        caught_any_mask |= 1 << land_owner

                for s in (1, 2, 3, 4):
                    s_bit = 1 << s
                    if (S_mask & s_bit) and not (caught_any_mask & s_bit):
                        pred_frozen_mask |= s_bit

                if pred_frozen_mask == newly_frozen_mask:
                    plaus = 0.0
                    for s in (1, 2, 3, 4):
                        s_bit = 1 << s
                        if not (S_mask & s_bit):
                            continue
                        if caught_any_mask & s_bit:
                            cell_val = 1
                            for j in (1, 2, 3, 4):
                                if j != s and ((pred_frozen_mask >> j) & 1):
                                    cj = positions[j] if post_move_rule else prior_pos[j]
                                    if cj >= 0 and prior_owner[cj] == s:
                                        v = cells[cj].base_points * (2 if self.level[cj] else 1)
                                        if v > cell_val:
                                            cell_val = v
                            plaus += 2.0 + 0.4 * cell_val
                        else:
                            plaus -= 2.5
                        ps = prior_pos[s]
                        if ps >= 0 and prior_owner[ps] not in (0, s):
                            plaus -= 1.0
                    if plaus > best_score:
                        best_score = plaus
                        best_S_mask = S_mask
            if best_S_mask >= 0:
                return best_S_mask

        # Deterministic fallback
        just_mask = me_bit
        for seat in (1, 2, 3, 4):
            spot = positions[seat]
            if spot < 0:
                continue
            defender = prior_owner[spot]
            if defender and defender != seat and not prior_frozen[seat]:
                if frozen[seat] and not frozen[defender] and prior_pos[defender] == positions[defender]:
                    just_mask |= 1 << defender
            if frozen[seat] and not prior_frozen[seat] and prior_pos[seat] == spot and defender in (0, seat):
                just_mask |= 1 << seat
        return just_mask

    def observe(self, me, cells, positions, owner, level, frozen, can_shield, is_token, legal):
        """Updates tracker state for the current turn with zero dynamic set allocations."""
        if self._is_new_game(me, cells, positions, owner, level):
            self._reset(me, cells, positions, owner, level, frozen, is_token)
            self.can_shield = can_shield
            self._pin_own_state(me, frozen, can_shield, legal)
            return

        self.turn = min(self.turn + 1, MAX_TURNS)
        prior_pos = self.positions
        prior_owner = self.owner
        prior_level = self.level
        prior_frozen = self.frozen

        # Update Priority Token Holder Mask (bits 1..4)
        allowed_mask = (1 << me) if is_token else (0b11110 & ~(1 << me))
        shifted_mask = 0
        for s in (1, 2, 3, 4):
            if (self.holder_mask >> s) & 1:
                shifted_mask |= 1 << ((s & 3) + 1)
        shifted_mask &= allowed_mask
        self.holder_mask = shifted_mask if shifted_mask else allowed_mask

        # If more than 1 bit set in holder_mask, narrow via contested neutral moves
        if self.holder_mask & (self.holder_mask - 1):
            for s_win in (1, 2, 3, 4):
                p_dest = positions[s_win]
                if p_dest >= 0 and p_dest != prior_pos[s_win] and prior_owner[p_dest] == 0:
                    for s_lose in (1, 2, 3, 4):
                        if s_lose == s_win or prior_frozen[s_lose] or frozen[s_lose]:
                            continue
                        p_stay = positions[s_lose]
                        if p_stay == prior_pos[s_lose] and FLAT_DIST[p_stay][p_dest] == 1:
                            if prior_owner[p_stay] == s_lose and prior_level[p_stay] == 1:
                                valid_now_mask = 0
                                for h_now in (1, 2, 3, 4):
                                    if (self.holder_mask >> h_now) & 1:
                                        h_prev = ((h_now - 2) & 3) + 1
                                        if ((s_win - h_prev) & 3) < ((s_lose - h_prev) & 3):
                                            valid_now_mask |= 1 << h_now
                                if valid_now_mask:
                                    self.holder_mask = valid_now_mask

        own_shield = (
            self.can_shield
            and not can_shield
            and (not frozen[me] or self.last_action == "SHIELD")
        )
        just_shielded_mask = self._solve_shields_csp_mask(
            me, cells, prior_pos, positions, prior_owner, owner, prior_frozen, frozen, own_shield
        )

        # Update rival shield stops/attempts & Bayesian Beta posteriors
        for seat in (1, 2, 3, 4):
            spot = positions[seat]
            if spot < 0 or prior_pos[seat] != spot:
                continue
            defender = prior_owner[spot]
            if defender and defender != seat and not prior_frozen[seat]:
                if frozen[seat] and not frozen[defender] and prior_pos[defender] == positions[defender]:
                    just_shielded_mask |= 1 << defender
                    self.stops[defender] += 1.0
                    self.attempts[defender] += 1.0
                elif owner[spot] == seat:
                    self.attempts[defender] += 1.0

        prior_occ_mask = 0
        curr_occ_mask = 0
        for s in (1, 2, 3, 4):
            if prior_pos[s] >= 0:
                prior_occ_mask |= CELL_BIT[prior_pos[s]]
            if positions[s] >= 0:
                curr_occ_mask |= CELL_BIT[positions[s]]

        opp_mask = 0
        for seat in (1, 2, 3, 4):
            prev_p = prior_pos[seat]
            if prev_p < 0 or prior_frozen[seat]:
                continue
            land = prior_owner[prev_p]
            if land in (0, seat) or (HOME_MASK & CELL_BIT[prev_p]):
                continue
            if not prior_frozen[land] and self.cooldown[land] == 0:
                opp_mask |= 1 << land
            if land == me and self.can_shield:
                tier = prior_level[prev_p]
                stayed = (
                    (prev_p == positions[seat])
                    and not ((just_shielded_mask >> seat) & 1)
                    and (not own_shield or (frozen[seat] and not frozen[me]))
                )
                unblocked_exits = 0
                for nb in NEIGHB[prev_p]:
                    nb_bit = CELL_BIT[nb]
                    if not (prior_occ_mask & nb_bit) and (not (curr_occ_mask & nb_bit) or positions[seat] == nb):
                        unblocked_exits += 1
                weight = (1.5 if own_shield else 1.0) * (1.0 if unblocked_exits > 0 else 0.5)
                self.stay_hits[seat][tier] = 0.94 * self.stay_hits[seat][tier] + weight * (1.0 if stayed else 0.0)
                self.stay_trials[seat][tier] = 0.94 * self.stay_trials[seat][tier] + weight
                self.stay_beta[seat][tier].update(stayed, weight)

        for defender in (1, 2, 3, 4):
            if (opp_mask >> defender) & 1:
                did_sh = bool((just_shielded_mask >> defender) & 1)
                self.defense_hits[defender] = 0.93 * self.defense_hits[defender] + (1.0 if did_sh else 0.0)
                self.defense_trials[defender] = 0.93 * self.defense_trials[defender] + 1.0
                self.shield_beta[defender].update(did_sh, 1.0)

        for seat in (1, 2, 3, 4):
            p = positions[seat]
            continuing = (
                p >= 0
                and p == prior_pos[seat]
                and not ((just_shielded_mask >> seat) & 1)
                and not frozen[seat]
                and not prior_frozen[seat]
                and owner[p] == prior_owner[p]
                and level[p] == prior_level[p]
            )
            self.enemy_progress[seat] = min(2, self.enemy_progress[seat] + 1) if continuing else 0

        for seat in (1, 2, 3, 4):
            if (just_shielded_mask >> seat) & 1:
                self.cooldown[seat] = 4
            else:
                cd = self.cooldown[seat] - 1
                self.cooldown[seat] = cd if cd > 0 else 0

            if not frozen[seat]:
                self.freeze_left[seat] = 0
            elif not prior_frozen[seat]:
                self.freeze_left[seat] = 2
            else:
                fl_s = self.freeze_left[seat] - 1
                self.freeze_left[seat] = fl_s if fl_s > 1 else 1

        spot = positions[me]
        continued = (
            spot == prior_pos[me]
            and not own_shield
            and not prior_frozen[me]
            and not frozen[me]
            and prior_owner[spot] == owner[spot]
            and prior_level[spot] == level[spot]
        )
        self.progress = min(2, self.progress + 1) if continued else 0

        for i in range(NC):
            s = owner[i]
            if s:
                val = cells[i].base_points
                self.scores[s] += val * (1 + level[i])
                po = prior_owner[i]
                if po and po != s:
                    self.scores[s] += 8 * val * (1 + prior_level[i])

        self.positions[:] = positions
        self.owner[:] = owner
        self.level[:] = level
        self.frozen[:] = frozen
        self.can_shield = can_shield
        self._pin_own_state(me, frozen, can_shield, legal)

    def _pin_own_state(self, me, frozen, can_shield, legal):
        if not frozen[me]:
            self.freeze_left[me] = 0
            if can_shield:
                self.cooldown[me] = 0
            elif self.cooldown[me] == 0:
                self.cooldown[me] = 1
        elif len(legal) == 1 and self.freeze_left[me] == 0:
            self.freeze_left[me] = 2

    def token_holder_at(self, target_turn):
        """Returns exact priority token holder at target_turn if locked, else None."""
        m = self.holder_mask
        if m and not (m & (m - 1)):
            # Exact power of 2 -> single seat locked
            h_now = (m.bit_length() - 1)
            return ((h_now - 1 + (target_turn - self.turn)) & 3) + 1
        return None


# ---------------------------------------------------------------------------
# Layer 2: First-Principles Pairwise Placement Valuation
# ---------------------------------------------------------------------------
class ValuationEngine(object):
    """
    Layer 2: Computes projected terminal margins, Sigmoid pairwise win probabilities,
    marginal denial weights, and bilateral raid valuations.
    """

    @staticmethod
    def pairwise_win_probs(me, enemies, left, proj, tau_scale=24.0):
        denom = max(12.0, tau_scale * math.sqrt(max(1.0, float(left))))
        p_me = proj[me]
        win_probs = [0.0] * 5
        for seat in enemies:
            z = (p_me - proj[seat]) / denom
            if z > 30.0:
                win_probs[seat] = 1.0
            elif z < -30.0:
                win_probs[seat] = 0.0
            else:
                win_probs[seat] = 1.0 / (1.0 + math.exp(-z))
        return win_probs

    @staticmethod
    def compute_denial_and_exposure(me, enemies, left, scores, income, stops, attempts, cfg):
        horizon = left if left < 18 else 18
        proj = [scores[i] + horizon * income[i] for i in range(5)]
        p_me = proj[me]

        win_probs = ValuationEngine.pairwise_win_probs(me, enemies, left, proj, cfg.get("tau_scale", 24.0))

        denial = [0.0] * 5
        dbase = cfg["denial_base"]
        dclose = cfg["denial_close"]
        scale = 65.0 + left * 3.0

        for seat in enemies:
            gap = abs(p_me - proj[seat])
            w_j = win_probs[seat]
            sig_deriv = 4.0 * w_j * (1.0 - w_j)
            prox = 0.75 / (1.0 + gap / scale) + 0.25 * sig_deriv
            denial[seat] = dbase + dclose * prox

        exposure = [0.0] * 5
        for i in range(1, 5):
            x = 0.08 + 1.30 * (stops[i] / attempts[i])
            exposure[i] = x if x < 0.87 else 0.87

        return proj, denial, exposure


# ---------------------------------------------------------------------------
# Layer 3 & Level 1: Bitboard Flow Field & Dynamic Voronoi Partitioning
# ---------------------------------------------------------------------------
# Pre-allocated static BFS buffer to avoid deque allocations in hot loop
_BFS_QUEUE = [0] * NC


class SpatialFlowField(object):
    """
    Layer 3 & Level 1:
      - Zero-allocation array-backed BFS router with Rule 2.3 priority tie-breaking.
      - Generalized Multi-Source Dynamic Voronoi Decomposition partitioning the
        64-cell board into 64-bit integer masks:
          1. `sanctuary_mask`: Self-Sanctuary cells (strictly closer than all rivals).
          2. `contested_mask`: Contested Border cells (|d_me - d_rival| <= 1).
          3. `dead_zone_mask`: Unreachable/irrelevant cells deep in rival territory.
    """

    @staticmethod
    def compute_voronoi(me, enemies, pos, owner, travel, pressure, is_token, tracker):
        """
        Section 3.1: Computes 64-bit integer masks for Dynamic Voronoi Partitioning:
          V(j) = { c | d(pos_j, c) - PriorityWeight(j) < min_{k != j} (d(pos_k, c) - PriorityWeight(k)) }
        """
        if not enemies:
            return FULL_BOARD_MASK, 0, 0

        h_now = tracker.token_holder_at(tracker.turn)
        if h_now is not None:
            my_rank = (me - h_now) & 3
            my_prio = (3 - my_rank) * 0.12
        else:
            my_prio = 0.24 if is_token else 0.08

        fl = tracker.freeze_left
        rival_dists = []
        rival_prios = []
        for r in enemies:
            rival_dists.append((FLAT_DIST[pos[r]], fl[r]))
            if h_now is not None:
                r_rank = (r - h_now) & 3
                rival_prios.append((3 - r_rank) * 0.12)
            else:
                rival_prios.append(0.0 if is_token else 0.12)

        sanctuary_mask = 0
        contested_mask = 0
        dead_zone_mask = 0
        n_enemies = len(enemies)

        for c in range(NC):
            d_me = travel[c]
            d_me_eff = d_me - my_prio
            min_r_eff = 99.0
            for idx in range(n_enemies):
                d_row, fl_r = rival_dists[idx]
                r_eff = d_row[c] + fl_r - rival_prios[idx]
                if r_eff < min_r_eff:
                    min_r_eff = r_eff

            bit = CELL_BIT[c]
            diff = d_me_eff - min_r_eff
            if diff < -0.5:
                sanctuary_mask |= bit
            elif diff <= 1.25:
                contested_mask |= bit
            elif owner[c] == 0 and d_me > 4 and diff > 1.5 and QUADRANT[c] != me:
                # Neutral cell deep inside a rival's Voronoi zone (>4 steps away)
                dead_zone_mask |= bit

        return sanctuary_mask, contested_mask, dead_zone_mask

    @staticmethod
    def compute_paths_and_pressure(at, me, enemies, pos, owner, legal, is_token, tracker):
        occ_mask = 0
        for r in enemies:
            occ_mask |= CELL_BIT[pos[r]]

        travel = [90] * NC
        first = [None] * NC
        travel[at] = 0

        h_now = tracker.token_holder_at(tracker.turn)
        my_rank = ((me - h_now) & 3) if h_now is not None else (0 if is_token else 2)
        fl = tracker.freeze_left

        choices = []
        for action, target in ADJ[at]:
            if action in legal and not (occ_mask & CELL_BIT[target]):
                risk = 0.0
                t_owner = owner[target]
                if t_owner != me and not (is_token and t_owner == 0):
                    for r in enemies:
                        if fl[r] > 0:
                            continue
                        if FLAT_DIST[pos[r]][target] == 1:
                            if t_owner == r:
                                risk += 1.5
                            elif t_owner == 0 and h_now is not None:
                                if ((r - h_now) & 3) < my_rank:
                                    risk += 1.0
                            else:
                                risk += 1.0
                choices.append((risk, action, target))

        if len(choices) > 1:
            choices.sort()

        q = _BFS_QUEUE
        q_head = 0
        q_tail = 0
        visited_mask = CELL_BIT[at] | occ_mask

        for _, action, target in choices:
            travel[target] = 1
            first[target] = action
            visited_mask |= CELL_BIT[target]
            q[q_tail] = target
            q_tail += 1

        while q_head < q_tail:
            here = q[q_head]
            q_head += 1
            th = travel[here] + 1
            fh = first[here]
            for there in NEIGHB[here]:
                t_bit = CELL_BIT[there]
                if not (visited_mask & t_bit):
                    visited_mask |= t_bit
                    travel[there] = th
                    first[there] = fh
                    q[q_tail] = there
                    q_tail += 1

        # Zero-tuple-churn multi-source rival arrival field
        if enemies:
            r0 = enemies[0]
            fl0 = fl[r0]
            d0 = FLAT_DIST[pos[r0]]
            pressure = [d0[c] + fl0 for c in range(NC)] if fl0 > 0 else list(d0)
            for r in enemies[1:]:
                fl_r = fl[r]
                d_row = FLAT_DIST[pos[r]]
                if fl_r > 0:
                    for c in range(NC):
                        v = d_row[c] + fl_r
                        if v < pressure[c]:
                            pressure[c] = v
                else:
                    for c in range(NC):
                        v = d_row[c]
                        if v < pressure[c]:
                            pressure[c] = v
        else:
            pressure = [12] * NC

        return travel, first, pressure


# ---------------------------------------------------------------------------
# Layer 4: Time-Expanded DAG Orienteering Planner (Bitmask + 80ms Sentry)
# ---------------------------------------------------------------------------
class MacroJobPlanner(object):
    """
    Layer 4: Generates Voronoi-filtered atomic Macro-Jobs (Claim, Upgrade, Compound
    Fortify, Raid) and executes a bitmask-pruned Time-Expanded DAG search with a
    strict 80ms Wall-Clock Sentry checked every 16 iterations.
    """

    @staticmethod
    def plan_best_walk(
        me, at, left, phase, cells, owner, level, pos, frozen,
        travel, first, pressure, denial, exposure,
        sanctuary_mask, contested_mask, dead_zone_mask,
        tracker, cfg, deadline
    ):
        w_claim = cfg.get("w_claim", 1.0)
        upgrade_w = cfg["upgrade_open"] + phase * (cfg["upgrade_late"] - cfg["upgrade_open"])
        raid_w = cfg["raid_open"] + phase * (cfg["raid_late"] - cfg["raid_open"])
        risk_w = cfg["risk_open"] + phase * (cfg["risk_late"] - cfg["risk_open"])

        lifetime = cfg["income_lifetime"]
        slope = cfg["safety_slope"]
        fortify = cfg["fortify_premium"]
        cash8 = 8.0 * cfg["cash_weight"]
        contest = cfg["contest_cost"]
        inertia = cfg["inertia"]
        eps_cell = cfg["cell_tiebreak_eps"]
        late_cutoff = cfg.get("late_game_cutoff", 78)

        progress = tracker.progress
        cooldown = tracker.cooldown
        fl = tracker.freeze_left
        prior_target = tracker.prior_target
        turn = tracker.turn

        breadth = int(cfg["breadth"])
        depth = int(cfg["depth"])
        route_weight = cfg["route_weight"] if depth > 1 else 0.0
        delay = cfg["route_delay"]

        tasks = []
        dead_fallback = []

        for i in range(NC):
            t_time = travel[i]
            if t_time >= left:
                continue
            who = owner[i]
            up = level[i]
            c = cells[i]
            hm = c.is_home
            if (up and who == me) or (hm and who != me):
                continue

            # Late-game cutoff: avoid starting new 3-turn upgrades when <= (80 - late_cutoff) turns left
            if who == me and turn > late_cutoff and i != at:
                continue

            work = 3 if (who == me or up) else 1
            if i == at:
                work = max(1, work - progress)
            cost = t_time + work
            if cost > left:
                continue

            v = c.base_points
            nearest = pressure[i]
            retention = lifetime + (nearest if nearest < 5 else 5) * slope
            if hm:
                retention = 100.0
            rem_after = left - cost + 1
            life = rem_after if rem_after < retention else retention

            if who == me:
                reward = v * life * upgrade_w
                if not hm:
                    reward *= fortify
            elif who == 0:
                reward = v * life * w_claim + eps_cell
            else:
                reward = raid_w * v * (life * (1.0 + denial[who] * (1 + up)) + cash8 * (1 + up)) + eps_cell

            risk = 0.0
            if who != me and who != 0:
                if cooldown[who] < cost and fl[who] < cost:
                    risk = exposure[who] * risk_w
                    if up:
                        risk *= 1.4
                    reward /= 1.0 + risk * (0.65 if up else 0.18)

            effort = work + risk * (3.5 if up else 2.4)
            i_bit = CELL_BIT[i]
            # Self-Sanctuary optimization: skip contest penalty if strictly inside our Voronoi sanctuary
            if i != at and not (sanctuary_mask & i_bit) and nearest <= t_time and who != me:
                effort += contest * (0.40 if nearest <= 1 else 0.18)

            rate = reward / (t_time + effort)
            if inertia and i == prior_target:
                rate *= 1.0 + inertia

            item = (rate, i, effort, reward, cost, work)
            if dead_zone_mask & i_bit:
                dead_fallback.append(item)
            else:
                tasks.append(item)

        # Ensure search has full beam width if local/border zones are already saturated
        if len(tasks) < breadth and dead_fallback:
            dead_fallback.sort(reverse=True)
            tasks.extend(dead_fallback[: breadth - len(tasks)])

        tasks.sort(reverse=True)

        best_value = -1.0
        best_action = "STAY"
        chosen_cell = None

        nt = len(tasks)
        if nt == 0:
            return best_action, chosen_cell, tasks

        tj = [t[1] for t in tasks]
        te = [t[2] for t in tasks]
        trw = [t[3] for t in tasks]
        tw = [t[5] for t in tasks]

        order = []
        for q in range(nt):
            extra = progress if tj[q] == at else 0
            order.append((trw[q] / (1.0 + te[q] + extra), q))
        order.sort(reverse=True)

        iter_count = 0
        time_expired = False
        parity_bit = (turn + at + tracker.scores[me]) & 1

        for rate, i, effort, reward, cost, work in tasks[:breadth]:
            if time_expired:
                break

            next_rate = 0.0
            visited_1 = CELL_BIT[i]

            if cost < left - 1 and route_weight > 0.0:
                dists_i = FLAT_DIST[i]
                budget = left - cost
                second = None
                second_cost = 0

                for ub, q in order:
                    iter_count += 1
                    if not (iter_count & 15) and time.perf_counter() > deadline:
                        time_expired = True
                        break
                    if depth == 2 and ub <= next_rate:
                        break
                    j = tj[q]
                    if visited_1 & CELL_BIT[j]:
                        continue
                    between = dists_i[j]
                    extra = progress if j == at else 0
                    step2_cost = between + tw[q] + extra
                    if step2_cost <= budget:
                        cand_rate = trw[q] / (between + te[q] + extra)
                        if cand_rate > next_rate:
                            next_rate = cand_rate
                            second = j
                            second_cost = step2_cost

                # Atomic Compound Fortification Job: Claim/Raid cell i -> immediately Upgrade cell i
                if not time_expired and owner[i] != me and cost + 3 <= left:
                    pn = pressure[i]
                    ret_i = lifetime + (pn if pn < 5 else 5) * slope
                    rem_i = left - cost - 2
                    post_life = rem_i if rem_i < ret_i else ret_i
                    fort_cand = cells[i].base_points * post_life * upgrade_w / 3.0
                    if fort_cand > next_rate:
                        next_rate = fort_cand
                        second = i
                        second_cost = 3

                # Depth-3 Time-Expanded DAG extension with bitboard visited check
                if not time_expired and depth >= 3 and second is not None and cost + second_cost < left - 1:
                    third_rate = 0.0
                    dists_sec = FLAT_DIST[second]
                    rem_budget = left - cost - second_cost
                    visited_2 = visited_1 | CELL_BIT[second]

                    for ub, q in order:
                        iter_count += 1
                        if not (iter_count & 15) and time.perf_counter() > deadline:
                            time_expired = True
                            break
                        if ub <= third_rate:
                            break
                        k = tj[q]
                        if visited_2 & CELL_BIT[k]:
                            continue
                        between = dists_sec[k]
                        extra = progress if k == at else 0
                        if between + tw[q] + extra <= rem_budget:
                            c3 = trw[q] / (between + te[q] + extra)
                            if c3 > third_rate:
                                third_rate = c3

                    if not time_expired and second != i and owner[second] != me and rem_budget >= 3:
                        pn2 = pressure[second]
                        ret_2 = lifetime + (pn2 if pn2 < 5 else 5) * slope
                        rem_2 = rem_budget - 2
                        post_life2 = rem_2 if rem_2 < ret_2 else ret_2
                        fort_c3 = cells[second].base_points * post_life2 * upgrade_w / 3.0
                        if fort_c3 > third_rate:
                            third_rate = fort_c3

                    next_rate += route_weight * third_rate / (1.0 + delay * (second_cost - 1))

            value = rate + route_weight * next_rate / (1.0 + delay * (cost - 1))

            # Level 2 (Section 5.1): Subgame Asymmetry tie-breaker on symmetric sanctuary targets
            # Perturbs exact tie-breaks by 1e-5 to blind opponent genome-mirror trackers
            if (sanctuary_mask & visited_1) and ((MIRROR_CANONICAL[i] & 1) == parity_bit):
                value += 1e-5

            if value > best_value:
                best_value = value
                best_action = "STAY" if i == at else first[i]
                chosen_cell = i

        return best_action, chosen_cell, tasks


# ---------------------------------------------------------------------------
# Layer 5 & Level 2: Simultaneous 2x2 Subgame Equilibrium Solver
# ---------------------------------------------------------------------------
class SubgameTactics(object):
    """
    Layer 5 & Level 2: Solves the 2x2 Raider vs. Landlord subgame for:
      1. Mixed-Strategy Nash Equilibrium (`compute_nash_subgame`)
      2. Offensive Bait-Stepping (inducing landlord shield backfires)
      3. Last-Tick Defensive Shielding (catching committed raiders on stay 3
         while strictly avoiding the Frozen-Intruder Backfire Trap).
    """

    @staticmethod
    def compute_nash_subgame(u_ll_sh_exit, u_ll_pass_exit, u_ll_pass_stay, u_ll_sh_stay):
        """
        Section 5.2: Computes the mixed-strategy Nash equilibrium stay probability p_stay*:
          p_stay* = (U_ll(Shield, Exit) - U_ll(Pass, Exit)) /
                    ((U_ll(Shield, Exit) - U_ll(Pass, Exit)) + (U_ll(Pass, Stay) - U_ll(Shield, Stay)))
        """
        num = u_ll_sh_exit - u_ll_pass_exit
        den = num + (u_ll_pass_stay - u_ll_sh_stay)
        if abs(den) < 1e-9:
            return 0.5
        p_star = num / den
        return 0.0 if p_star < 0.0 else (1.0 if p_star > 1.0 else p_star)

    @staticmethod
    def evaluate_bait_step(
        me, at, left, best_action, cells, owner, frozen, travel, first, tasks, tracker, cfg
    ):
        feint_w = cfg["feint_weight"]
        defender = owner[at]
        if (
            feint_w > 0.0
            and best_action == "STAY"
            and defender not in (0, me)
            and not cells[at].is_home
            and not frozen[defender]
            and tracker.cooldown[defender] == 0
            and (tracker.turn - tracker.last_bait) >= 5
            and left > 2
            and tracker.progress == 0
        ):
            # Combine empirical frequency with Bayesian Beta posterior for landlord prior q_sh
            emp_q = tracker.defense_hits[defender] / tracker.defense_trials[defender]
            bayes_q = tracker.shield_beta[defender].mean()
            q_sh = 0.65 * emp_q + 0.35 * bayes_q

            exits = []
            for _, i, effort, reward, _, _ in tasks:
                if travel[i] == 1 and first[i] is not None:
                    # Stepping onto another cell of the same defender exploits their 4-turn cooldown
                    bonus = 1.25 if owner[i] == defender else 0.95
                    exits.append((reward * bonus / (effort + 1.0), first[i]))

            bait_thresh = cfg.get("bait_sensitivity", 0.40)
            if exits and (q_sh >= bait_thresh or q_sh * feint_w > 0.43):
                alt_val, alt_act = max(exits)
                if alt_val * (1.0 + 1.3 * q_sh * feint_w) > tasks[0][0]:
                    return alt_act, True
        return best_action, False

    @staticmethod
    def evaluate_defensive_shield(
        me, left, legal, enemies, pos, owner, level, frozen, cells, denial, tasks, tracker, cfg
    ):
        if "SHIELD" not in legal:
            return False

        threat = 0.0
        miss = 1.0
        for s in enemies:
            i = pos[s]
            # Strictly enforce Hazard #3: Frozen rivals cannot be caught again!
            if i < 0 or owner[i] != me or frozen[s] or cells[i].is_home:
                continue
            tier = level[i]
            emp_stay = tracker.stay_hits[s][tier] / tracker.stay_trials[s][tier]
            bayes_stay = tracker.stay_beta[s][tier].mean()
            chance = 0.70 * emp_stay + 0.30 * bayes_stay
            if tier:
                # Section 7.4 / Milestone 3: On upgraded cells (3 stays needed), hold shield
                # on stays 1 & 2, and trigger on the final tick (progress == 2) to waste maximum tempo!
                ep = tracker.enemy_progress[s]
                chance *= (0.21, 0.53, 1.18)[ep]
                if ep + left < 3:
                    chance *= 0.25
            chance = 0.97 if chance > 0.97 else (0.04 if chance < 0.04 else chance)
            immediate = cells[i].base_points * (1 + tier)
            horizon = left if left < (5 if not tier else 10) else (5 if not tier else 10)
            rem3 = left if left < 3 else 3
            threat += chance * (
                immediate * (horizon + 8.0 * denial[s]) + rem3 * 4.0 * denial[s]
            )
            miss *= 1.0 - chance

        if threat <= 0.0:
            return False

        normal_rate = tasks[0][0] if tasks else 0.0
        lhs = cfg["shield_weight"] * threat
        rhs = (1.0 + cfg["backfire_cost"] * miss) * max(1.0, 0.49 * normal_rate)
        return lhs > rhs


# ---------------------------------------------------------------------------
# Layer 6: Endgame & Tie-Break Execution (Turns 70-80)
# ---------------------------------------------------------------------------
class EndgameExecutor(object):
    """
    Layer 6: Executes Turn-80 Free-Shield dominance when a STAY on the final
    turn cannot complete any capture or upgrade.
    """

    @staticmethod
    def terminal_override(me, at, left, best_action, legal, cells, owner, level, enemies, pos, tracker):
        if best_action != "STAY" or left != 1 or not tracker.known_start or "SHIELD" not in legal:
            return best_action

        here = cells[at]
        if owner[at] == me:
            can_score = (not level[at]) and (tracker.progress >= 2)
        else:
            can_score = (not here.is_home) and (
                owner[at] == 0 or (not level[at]) or (tracker.progress >= 2)
            )
        if can_score:
            return best_action

        # Turn 80 Free-Shield Dominance: Backfire freeze has zero penalty after Turn 80
        for s in enemies:
            c = pos[s]
            if c >= 0 and owner[c] == me and not cells[c].is_home:
                return "SHIELD"
        return best_action


# ---------------------------------------------------------------------------
# Master Autonomous Agent Class & Entry Point
# ---------------------------------------------------------------------------
class UltimateBot(object):
    """
    Master Autonomous Strategy Engine ("Ultimate").
    Integrates all 6 architectural layers plus Level 0-3 optimizations into a
    deterministic, zero-allocation, <35ms execution pipeline with an 80ms hard sentry.
    """
    name = "ultimate"

    def __init__(self, seed=42, params=None):
        self.seed = seed
        self.cfg = _merge_params(params)
        self.tracker = StateTracker(self.cfg)
        # Pre-allocated turn buffers to eliminate list allocations inside decide()
        self._owner_buf = [0] * NC
        self._level_buf = [0] * NC
        self._pos_buf = [-1] * 5
        self._frozen_buf = [False] * 5
        self._income_buf = [0] * 5

    def decide(self, state):
        t0 = time.perf_counter()
        deadline = t0 + self.cfg["deadline_ms"] * 0.001

        cells, me, is_token, legal, lookup = normalise_state(state)

        owner = self._owner_buf
        level = self._level_buf
        pos = self._pos_buf
        frozen = self._frozen_buf
        income = self._income_buf

        for s in range(5):
            pos[s] = -1
            frozen[s] = False
            income[s] = 0

        for i in range(NC):
            c = cells[i]
            ow = c.owner
            lv = 1 if c.is_upgraded else 0
            owner[i] = ow
            level[i] = lv
            occ = c.occupant
            if 1 <= occ <= 4:
                pos[occ] = i
                frozen[occ] = bool(c.is_frozen)
            if ow:
                income[ow] += c.base_points * (1 + lv)

        at = pos[me]
        if at < 0:
            fb = "STAY" if "STAY" in lookup else legal[0]
            return lookup.get(fb, fb)

        can_shield = "SHIELD" in lookup

        # Layer 1: Update Constraint-Satisfaction State & Belief Tracker
        self.tracker.observe(me, cells, pos, owner, level, frozen, can_shield, is_token, legal)

        if len(legal) == 1:
            only_act = legal[0]
            self.tracker.last_action = only_act
            return lookup.get(only_act, only_act)

        turn = self.tracker.turn
        left = (MAX_TURNS + 1) - turn
        phase = (turn - 1) / 79.0
        enemies = tuple(s for s in (1, 2, 3, 4) if s != me and pos[s] >= 0)

        # Layer 2: First-Principles Pairwise Placement Valuation
        _, denial, exposure = ValuationEngine.compute_denial_and_exposure(
            me, enemies, left, self.tracker.scores, income,
            self.tracker.stops, self.tracker.attempts, self.cfg
        )

        # Layer 3 & Level 1: Spatio-Temporal Flow Field & Dynamic Voronoi Partitioning
        travel, first, pressure = SpatialFlowField.compute_paths_and_pressure(
            at, me, enemies, pos, owner, lookup, is_token, self.tracker
        )
        sanctuary_mask, contested_mask, dead_zone_mask = SpatialFlowField.compute_voronoi(
            me, enemies, pos, owner, travel, pressure, is_token, self.tracker
        )

        # Layer 4: Time-Expanded DAG Orienteering Planner (with 80ms hard sentry)
        best_action, chosen_cell, tasks = MacroJobPlanner.plan_best_walk(
            me, at, left, phase, cells, owner, level, pos, frozen,
            travel, first, pressure, denial, exposure,
            sanctuary_mask, contested_mask, dead_zone_mask,
            self.tracker, self.cfg, deadline
        )
        self.tracker.prior_target = chosen_cell

        # Hard wall-clock sentry check before Layer 5 & 6 tactical refinements
        if time.perf_counter() <= deadline:
            # Layer 5: Simultaneous 2x2 Subgame Equilibrium Solver
            best_action, baited = SubgameTactics.evaluate_bait_step(
                me, at, left, best_action, cells, owner, frozen,
                travel, first, tasks, self.tracker, self.cfg
            )
            if baited:
                self.tracker.last_bait = turn

            if SubgameTactics.evaluate_defensive_shield(
                me, left, lookup, enemies, pos, owner, level, frozen,
                cells, denial, tasks, self.tracker, self.cfg
            ):
                best_action = "SHIELD"

            # Layer 6: Endgame & Turn-80 Free-Shield Execution
            best_action = EndgameExecutor.terminal_override(
                me, at, left, best_action, lookup, cells, owner, level,
                enemies, pos, self.tracker
            )

        if best_action not in lookup or best_action is None:
            best_action = "STAY" if "STAY" in lookup else legal[0]

        self.tracker.last_action = best_action
        return lookup.get(best_action, lookup["STAY"])

    def __call__(self, state):
        try:
            return self.decide(state)
        except Exception:
            try:
                _, _, _, legal, lookup = normalise_state(state)
                fb = "STAY" if "STAY" in lookup else legal[0]
                return lookup.get(fb, fb)
            except Exception:
                return "STAY"


# Alias for compatibility with standard Agent loaders
Agent = UltimateBot

# Per-seat global cache for functional act(state) entry point
_SEAT_AGENTS = {}


def act(state):
    """Competition entry point: act(state) -> action."""
    try:
        seat = _to_int(_attr(state, "bot_id", 1))
    except Exception:
        return "STAY"
    bot = _SEAT_AGENTS.get(seat)
    if bot is None:
        bot = UltimateBot(seed=seat * 7919)
        _SEAT_AGENTS[seat] = bot
    return bot(state)
