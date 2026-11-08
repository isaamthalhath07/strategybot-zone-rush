"""
Fusion: the strongest planner from the four branches, wrapped in every failsafe
any of them had, plus the ones none of them had.

    econ.Econ      research/evolution's economic planner -- the PRIMARY. On the
                   cross-author field (crossfield/xfield.py, 1,200 fresh paired
                   games) it beats every other branch's bot: +0.215 PW over main's
                   v7 (z = +8.0), +0.233 over v7-independent-field's (z = +8.5),
                   and it is never worse against any author's opponents.
    mybot.Agent    hardened-field-and-fixes' tracker and walk planner -- the WARM
                   STANDBY. Its tracker is updated every turn, so it can take over
                   mid-game with a correct picture of the board; it is the better
                   planner after a cold start (2462 vs 1803 points when module
                   memory is lost every turn), and its exact shield-attribution
                   solver supplies my own cooldown.
    _fallback      a policy with almost no dependencies, for when both raise.
    STAY           only if everything above raised.

Layers, each guarding against a way the real server could differ from the three
local referees (which agree with each other exactly over 32,000 turns, but none
of which is the organisers' server):

  1. Input normalisation. Any board shape (8x8 rows, flat 64, tuples, namedtuple
     cells, dict cells), int-or-string-or-bool fields, a string bot_id, a missing
     token flag, and legal actions as upper/lower-case strings or Enum-like
     objects. The returned action is always an element of the list the server
     handed over, in that list's own type.
  2. Planner isolation. Each planner is called under its own try/except. One
     that raises is replaced by the next on the same turn, so no turn is lost;
     one that raises twice in a game is retired for the rest of it.
  3. A fresh, independent planner state for every game, detected from the board
     itself rather than a turn counter. Positions revert in an opening, so they
     prove nothing; ownership and upgrades never revert within a game, so a
     starting board is a new game only once a capture or an upgrade has been
     seen (or 80 turns have passed).
  4. Cold-start rescue. If the module wakes up mid-game with no memory, the walk
     planner (which reconstructs from the board alone) plays that first turn,
     and the economic planner is handed the tracker's fitted turn estimate
     (median error 5 turns, against 9 for its own). Measured: after a single
     restart this recovers as well as any setting tried; if memory is lost on
     every turn it holds 96% of normal score, where the economic planner alone
     holds 88%.
  5. Shield sanity. A SHIELD the tracker knows to be on cooldown is never sent,
     unless the server has shown it removes SHIELD from legal_actions during
     cooldown (then legal_actions is authoritative).
  6. Direction calibration. Every move's observed displacement, and every legal
     list (a listed move that would leave the board), is checked against the
     documented NORTH = row - 1 convention. If the server's frame is a rotation
     or reflection of the documented one (three or more contradictions and an
     alternative with none), moves are translated. With the documented
     convention this layer never changes an action; against a server with NORTH
     and SOUTH swapped it recovers the full score.
  7. Unpredictable mixing. The walk planner mixes its shield decision with a
     random draw; on the server that draw is seeded from the clock, so a rival
     reading this public source cannot replay it. Measurement pins the seed.
  8. (Built, measured, and switched OFF.) Predicting exact copies of the public
     bots. Identification proved unsafe -- see FLAGS["mirror"].

On the documented interface none of this changes a single move: the shipped
file plays identically to research/evolution's bot (crossfield/test_econ.py,
and 0.0000 +/- 0.0000 over 1,200 paired games). What it changes is everything
else: every variant in crossfield/robustness.py, where each other branch's bot
falls to the skeleton's score on five or six of them.

Nothing here prints, reads files, or imports beyond the standard library.
"""
import time

# --- dev imports: ship.py inlines econ.py and mybot.py and deletes this block ---
from econ import Econ, E_EVOLVED, E_TRANSFER  # noqa: F401
from mybot import Agent, _fallback  # noqa: F401
# --- end dev imports ---

# Measurement sets "deterministic": no wall clock in any decision, fixed seeds.
SAFETY = {"deterministic": False}

# The economic planner's weights: research/evolution's recommended genome.
ECON_GENOME = dict(E_EVOLVED)

FLAGS = {
    "primary": "econ",         # "econ" or "route"
    "genome": "evolved",       # econ genome: "evolved" or "transfer"
    "sym": 0,                  # econ tie-break frame (see econ.py)
    "ext_cd": 0,               # econ reads rival cooldowns from the exact tracker
    "cold_route_turns": 1,     # walk planner plays this long after a cold start
    "max_errors": 2,           # a planner that raises this often is retired
    "calibrate": 1,            # verify the movement convention online
    "mirror": 0,               # predict and exploit exact copies of public bots.
                               # OFF: crossfield/exp_mirror.py shows near-relatives
                               # (same code, other genome) go unrefuted for 60-79
                               # turns, so identification is not safe
}

# hardened-field-and-fixes v7 weights for the walk planner (v7_params.json)
ROUTE_PARAMS = {
    "beam": 400, "budget_ms": 60.0, "care_mode": 4, "combo": 0.3372851530026109,
    "combo_pri": 0.5130215791090991, "commit_prior": 0.738408561698738,
    "consolidate": -0.3091790691417158, "contest_penalty": 0.04276674446676251,
    "def_kappa": 0.3, "endgame_care": 6, "endgame_denial": 1.1489375774470736,
    "first_turn_ms": 0.0, "first_turn_mult": 1.0, "free_shield_turns": 1,
    "freeze_cost": 1.9897676204898689, "hold": 0.039812395355899075,
    "home_bonus": 0.8124607638770958, "horizon": 40, "intent": 0.0, "intent_turns": 3,
    "kappa": 0.871265646873602, "lead_caution": 0.05637305117375756, "ncand": 8,
    "own_prog": 0.5638901677881061, "perish": 0.12508411521263113, "proj_care": 0.0,
    "q_prior": 0.6262098276170066, "q_weight": 4.912705682120482,
    "raid_risk": 1.5925150988216987, "reach": 5, "retake_credit": 0.5124636643323689,
    "safe_discount": 0.9496812183899669, "shield_bias": 2.351882159061404,
    "shield_certain": 0.541032334099978, "shield_cost": 1.4910998926274515,
    "squat_penalty": 0.05, "steal": 0.0, "steal_min": 3, "steal_until": 20,
    "stickiness": 1.228276644454352, "tau": 295.09465653811793, "throttle": 1,
    "tie_home": 1, "upg_risk": 0.0, "visits": 7, "w_claim": 0.9065853137369807,
    "w_denial": 0.20752972644616563, "w_raid": 1.648359402231134,
    "w_raid_late": 1.4321683445126716, "w_upgrade": 1.5842582773978768,
    "zone_bonus": 1.0, "pay_fix": 1,
}

_F_MOVES = ("NORTH", "EAST", "SOUTH", "WEST")
_F_ALL = ("NORTH", "EAST", "SOUTH", "WEST", "STAY", "SHIELD")
_F_DELTA = {"NORTH": (-1, 0), "SOUTH": (1, 0), "WEST": (0, -1), "EAST": (0, 1)}
_F_CORNER = (0, 7, 63, 56)
# the eight symmetries of the square, as maps of a (row, col) step
_F_DIHEDRAL = (
    lambda r, c: (r, c), lambda r, c: (c, -r), lambda r, c: (-r, -c),
    lambda r, c: (-c, r), lambda r, c: (r, -c), lambda r, c: (-r, c),
    lambda r, c: (c, r), lambda r, c: (-c, -r),
)
_F_FIELDS = ("occupant", "owner", "is_upgraded", "is_home", "is_frozen", "base_points")
_F_ALIASES = {
    "occupant": ("occupant", "occupied_by", "bot"), "owner": ("owner", "owned_by"),
    "is_upgraded": ("is_upgraded", "upgraded", "isUpgraded", "level"),
    "is_home": ("is_home", "home", "isHome"),
    "is_frozen": ("is_frozen", "frozen", "isFrozen"),
    "base_points": ("base_points", "points", "basePoints", "value"),
}


# ----------------------------------------------------------------- 1. input
class _FCell(object):
    __slots__ = _F_FIELDS

    def __init__(self, occupant, owner, is_upgraded, is_home, is_frozen, base_points):
        self.occupant = occupant
        self.owner = owner
        self.is_upgraded = is_upgraded
        self.is_home = is_home
        self.is_frozen = is_frozen
        self.base_points = base_points


class _FView(object):
    __slots__ = ("board", "bot_id", "is_priority_token", "legal_actions")

    def __init__(self, board, bot_id, token, legal):
        self.board = board
        self.bot_id = bot_id
        self.is_priority_token = token
        self.legal_actions = legal


def _f_get(cell, name):
    for key in _F_ALIASES[name]:
        if isinstance(cell, dict):
            if key in cell:
                return cell[key]
        elif hasattr(cell, key):
            return getattr(cell, key)
    raise KeyError(name)


def _f_int(x):
    if isinstance(x, bool):
        return int(x)
    if isinstance(x, int):
        return x
    return int(float(x))


def _f_bool(x):
    if isinstance(x, str):
        return x.strip().lower() in ("true", "1", "yes", "y", "t")
    return bool(x)


def _f_is_cell(x):
    if isinstance(x, dict):
        return "owner" in x or "owned_by" in x
    return hasattr(x, "owner") or hasattr(x, "owned_by")


def _f_flat(board):
    if isinstance(board, dict):
        board = board.get("cells") or board.get("board")
    seq = list(board)
    if len(seq) == 64 and _f_is_cell(seq[0]):
        return seq
    if len(seq) == 8 and not _f_is_cell(seq[0]):
        rows = [list(r) for r in seq]
        if all(len(r) == 8 for r in rows):
            return [c for r in rows for c in r]
    raise ValueError("unrecognised board shape")


def _f_name(x):
    """An action's canonical upper-case name, whatever type the server uses."""
    if isinstance(x, str):
        s = x
    else:
        s = getattr(x, "name", None)
        if not isinstance(s, str):
            s = getattr(x, "value", None)
        if not isinstance(s, str):
            s = str(x)
    s = s.strip().upper()
    if "." in s:
        s = s.rsplit(".", 1)[1]
    return s


def _f_attr(state, name, default=None):
    if isinstance(state, dict):
        return state.get(name, default)
    return getattr(state, name, default)


class _FObs(object):
    __slots__ = ("cells", "rows", "seat", "token", "names", "lookup", "pos", "fresh")


def _f_normalize(state):
    raw_cells = _f_flat(_f_attr(state, "board"))
    cells = []
    for c in raw_cells:
        cells.append(_FCell(_f_int(_f_get(c, "occupant") or 0),
                            _f_int(_f_get(c, "owner") or 0),
                            _f_bool(_f_get(c, "is_upgraded")),
                            _f_bool(_f_get(c, "is_home")),
                            _f_bool(_f_get(c, "is_frozen")),
                            _f_int(_f_get(c, "base_points"))))
    for p in _F_CORNER:                  # a home reported unowned keeps its seat
        if cells[p].is_home and not cells[p].owner:
            cells[p].owner = _F_CORNER.index(p) + 1
    seat = _f_int(_f_attr(state, "bot_id"))
    pos = [-1] * 5
    for i, c in enumerate(cells):
        if 1 <= c.occupant <= 4:
            pos[c.occupant] = i
    if not (1 <= seat <= 4) or pos[seat] < 0:
        if 0 <= seat <= 3 and pos[seat + 1] >= 0:
            seat += 1                    # a 0-indexed seat
        else:
            raise ValueError("cannot find my own bot on the board")
    raw_legal = _f_attr(state, "legal_actions")
    raw_legal = list(raw_legal) if raw_legal is not None else []
    lookup = {}
    for a in raw_legal:
        nm = _f_name(a)
        if nm in _F_ALL and nm not in lookup:
            lookup[nm] = a
    if "STAY" not in lookup:
        lookup["STAY"] = "STAY"          # documented as always legal
    o = _FObs()
    o.cells = cells
    o.rows = [cells[r * 8:(r + 1) * 8] for r in range(8)]
    o.seat = seat
    o.token = _f_bool(_f_attr(state, "is_priority_token", False))
    o.names = [a for a in _F_ALL if a in lookup]
    o.lookup = lookup
    o.pos = pos
    # A starting board: every bot on a corner, only the corners owned, nothing
    # upgraded. Any bot on any corner: neither the rulebook nor the starter kit
    # fixes which seat starts in which corner.
    o.fresh = all(pos[s] in _F_CORNER for s in range(1, 5)) and all(
        (c.owner == 0) != (i in _F_CORNER) for i, c in enumerate(cells)) and not any(
        c.is_upgraded for c in cells)
    return o


def _f_emergency(state):
    """The server's own STAY object if it can be found, else the first legal."""
    try:
        legal = list(_f_attr(state, "legal_actions") or [])
        for a in legal:
            if _f_name(a) == "STAY":
                return a
        if legal:
            return legal[0]
    except Exception:
        pass
    return "STAY"


# ----------------------------------------------------------------- 6. frame
class _FCalib(object):
    """Learns whether NORTH really is row - 1, from my own observed moves."""

    def __init__(self):
        self.agree = [0] * 8
        self.disagree = [0] * 8
        self.active = 0

    def observe(self, sent, before, after):
        """Evidence from my own last move: where did it actually take me?"""
        if sent not in _F_DELTA or before < 0 or after < 0 or before == after:
            return
        dr = after // 8 - before // 8
        dc = after % 8 - before % 8
        if abs(dr) + abs(dc) != 1:
            return
        r0, c0 = _F_DELTA[sent]
        for k, t in enumerate(_F_DIHEDRAL):
            if t(r0, c0) == (dr, dc):
                self.agree[k] += 1
            else:
                self.disagree[k] += 1
        self._decide()

    def observe_legal(self, here, names):
        """Evidence from legal_actions: a listed move that would leave the board
        in some frame contradicts that frame. Only inclusion counts -- a server
        may legitimately omit moves (into occupied cells, say) -- and a list
        holding all four moves carries no information at all.

        This matters because displacement evidence alone can never start: in a
        flipped frame at my corner the server offers NORTH (meaning down) and not
        SOUTH, and a planner that only proposes documented in-bounds moves would
        slide along the edge forever without producing a contradiction.
        """
        if here < 0:
            return
        moves = [a for a in names if a in _F_DELTA]
        if not moves or len(moves) == 4:
            return
        r, c = divmod(here, 8)
        for k, t in enumerate(_F_DIHEDRAL):
            fits = True
            for a in moves:
                dr, dc = t(*_F_DELTA[a])
                if not (0 <= r + dr < 8 and 0 <= c + dc < 8):
                    fits = False
                    break
            if fits:
                self.agree[k] += 1
            else:
                self.disagree[k] += 1
        self._decide()

    def _decide(self):
        self.active = 0
        if self.disagree[0] >= 3:
            for k in range(1, 8):
                if self.disagree[k] == 0 and self.agree[k] >= 3:
                    self.active = k
                    break

    def to_server(self, name):
        """Server action that moves me by `name`'s documented board step."""
        if not self.active or name not in _F_DELTA:
            return name
        want = _F_DELTA[name]
        t = _F_DIHEDRAL[self.active]
        for a in _F_MOVES:
            if t(*_F_DELTA[a]) == want:
                return a
        return name

    def from_server(self, names):
        """Legal names re-expressed as documented board steps."""
        if not self.active:
            return list(names)
        out = []
        t = _F_DIHEDRAL[self.active]
        for a in names:
            if a in _F_DELTA:
                step = t(*_F_DELTA[a])
                for b in _F_MOVES:
                    if _F_DELTA[b] == step:
                        out.append(b)
            else:
                out.append(a)
        return out


# ----------------------------------------------------------------- 8. copies
class _FMirror(object):
    """Recognises rivals that are exact copies of a public econ-family bot.

    This repository is public, and its strongest bot is deterministic. A rival
    running a copy of it sees the same board I do, and I can reconstruct every
    other input it gets -- its seat, whether it holds the token (it rotates),
    its legal actions and its cooldown (the exact tracker). It also moves
    simultaneously with me, so its choice this turn cannot depend on mine. One
    simulator per public genome therefore predicts such a rival's action this
    turn, before I choose mine.

    Identification is strict, so the option is inert against everybody else:
    every prediction is scored against what the rival actually did next turn
    (a blocked or contested move is inconclusive, never a match), one mismatch
    retires that hypothesis for the rest of the game, and nothing is acted on
    until NEED informative turns have matched. Observations from before the
    token holder is known (at most four turns) are buffered and replayed, so the
    simulator's memory starts on turn 1 exactly as the copy's did.
    """
    NEED = 10

    def __init__(self, seat):
        self.seat = seat
        self.rivals = [s for s in (1, 2, 3, 4) if s != seat]
        self.sims = dict((s, [Econ(config=E_EVOLVED), Econ(config=E_TRANSFER)])
                         for s in self.rivals)
        self.ok = dict((s, [True, True]) for s in self.rivals)
        self.hits = dict((s, [0, 0]) for s in self.rivals)
        self.pred = dict((s, [None, None]) for s in self.rivals)
        self.buf = []
        self.prev_pos = None
        self.live = False
        self.k = 0

    @staticmethod
    def _legal(s, pos, frozen, cd):
        if frozen[s]:
            return ["STAY"]
        occ = set(p for p in pos[1:] if p >= 0)
        r, c = divmod(pos[s], 8)
        out = []
        for a in _F_MOVES:
            dr, dc = _F_DELTA[a]
            if 0 <= r + dr < 8 and 0 <= c + dc < 8 and (r + dr) * 8 + c + dc not in occ:
                out.append(a)
        out.append("STAY")
        if cd[s - 1] == 0:
            out.append("SHIELD")
        return out

    def _predict(self, cells, pos, frozen, cd, holder):
        for s in self.rivals:
            if pos[s] < 0:
                continue
            legal = self._legal(s, pos, frozen, cd)
            for g in (0, 1):
                if not self.ok[s][g]:
                    self.pred[s][g] = None
                    continue
                try:
                    a = self.sims[s][g].step(cells, s, legal, holder == s)
                    self.pred[s][g] = (a, len(legal) > 1)
                except Exception:
                    self.ok[s][g] = False
                    self.pred[s][g] = None

    @staticmethod
    def _score(s, pred, before, after, shielded):
        """+1 a match, 0 inconclusive, -1 a mismatch."""
        a, b = before[s], after[s]
        if a < 0 or b < 0:
            return 0
        if a != b:
            step = (b // 8 - a // 8, b % 8 - a % 8)
            for nm in _F_MOVES:
                if _F_DELTA[nm] == step:
                    return 1 if pred == nm else -1
            return 0
        if s in shielded:
            return 1 if pred == "SHIELD" else -1
        if pred == "STAY":
            return 1
        if pred == "SHIELD":
            return -1
        dr, dc = _F_DELTA[pred]
        t = (a // 8 + dr) * 8 + a % 8 + dc
        if t in before[1:] or t in after[1:]:
            return 0                     # blocked, or lost a contest
        return -1

    def _check(self, before, after, shielded):
        for s in self.rivals:
            for g in (0, 1):
                p = self.pred[s][g]
                if p is None or not self.ok[s][g] or not p[1]:
                    continue
                r = self._score(s, p[0], before, after, shielded)
                if r < 0:
                    self.ok[s][g] = False
                elif r > 0:
                    self.hits[s][g] += 1

    def update(self, cells, pos, frozen, cd, shielded_last, holder):
        """One turn. cd: cooldowns by seat index 0-3; shielded_last: seats
        (1-4) that shielded last turn; holder: token seat, or None if unknown."""
        self.k += 1
        if not self.live:
            self.buf.append((cells, list(pos), list(frozen), list(cd), set(shielded_last)))
            if holder is None:
                return
            n = len(self.buf)
            for idx, (c_, p_, f_, cd_, sh_) in enumerate(self.buf):
                if idx:
                    self._check(self.buf[idx - 1][1], p_, sh_)
                self._predict(c_, p_, f_, cd_, (holder - 1 - (n - 1 - idx)) % 4 + 1)
            self.buf = []
            self.live = True
            self.prev_pos = list(pos)
            return
        self._check(self.prev_pos, pos, shielded_last)
        self._predict(cells, pos, frozen, cd, holder)
        self.prev_pos = list(pos)

    def predicted(self, s):
        """This turn's action of rival s, if it is an identified copy."""
        if not self.live or s not in self.ok:
            return None
        acts = set(self.pred[s][g][0] for g in (0, 1)
                   if self.ok[s][g] and self.hits[s][g] >= self.NEED
                   and self.pred[s][g] is not None)
        return acts.pop() if len(acts) == 1 else None


# ----------------------------------------------------------------- 2-5. seat
class _FBrain(object):
    """Everything one seat knows. Rebuilt from scratch at every new game."""

    def __init__(self, seat):
        self.seat = seat
        self.calib = _FCalib()           # the server's frame does not change per game
        self.removes_shield = False      # server drops SHIELD during cooldown?
        self.seen = False                # any observation yet?
        self.progressed = False          # any capture or upgrade this game?
        self.turns = 0
        self._new_game(cold=False)

    def _new_game(self, cold):
        genome = E_TRANSFER if FLAGS["genome"] == "transfer" else ECON_GENOME
        self.econ = Econ(config=genome, flags={"sym": FLAGS["sym"]})
        params = dict(ROUTE_PARAMS)
        if SAFETY["deterministic"]:
            params["throttle"] = 0
            params["budget_ms"] = 1e6
            seed = self.seat * 7919
        else:
            seed = (int(time.time() * 1e6) ^ (self.seat * 7919)) & 0x7fffffff
        self.route = Agent(seed=seed, params=params)
        self.errors = {"econ": 0, "route": 0}
        self.cold_left = FLAGS["cold_route_turns"] if cold else 0
        self.turns = 0
        self.last_sent = None
        self.last_pos = -1
        self.used = {"econ": 0, "route": 0, "fallback": 0, "stay": 0}
        # A copy can only be simulated from turn 1, so never after a cold start
        self.mirror = _FMirror(self.seat) if FLAGS["mirror"] and not cold else None
        self.exploits = 0

    def _alive(self, who):
        return self.errors[who] < FLAGS["max_errors"]

    def turn(self, obs):
        # -- 3. new game? Positions revert all the time in an opening, so they
        #    prove nothing; ownership and upgrades never revert within a game. So
        #    a starting board is a new game only once a capture or an upgrade has
        #    been seen (or the clock has run out), and a module that wakes up on
        #    a non-starting board has lost its memory mid-game.
        if not self.seen:
            self.seen = True
            if not obs.fresh:
                self._new_game(cold=True)
        elif obs.fresh and (self.progressed or self.turns >= 80):
            self._new_game(cold=False)
            self.progressed = False
        if not self.progressed and not obs.fresh and any(
                c.is_upgraded or (c.owner and not c.is_home) for c in obs.cells):
            self.progressed = True
        self.turns += 1
        me = obs.seat
        here = obs.pos[me]

        # -- 6. movement convention, from my own last move
        if FLAGS["calibrate"]:
            if self.turns > 1:
                self.calib.observe(self.last_sent, self.last_pos, here)
            self.calib.observe_legal(here, obs.names)
        names = self.calib.from_server(obs.names)

        # -- 5. SHIELD availability: legal_actions and the exact tracker
        if "SHIELD" not in names and len(names) > 1:
            self.removes_shield = True       # seen SHIELD withheld while free to act
        view = _FView(obs.rows, me, obs.token, names)
        route_ok = False
        if self._alive("route"):
            try:
                route_ok = self.route.ingest(view)
            except Exception:
                self.errors["route"] += 1
        if (route_ok and "SHIELD" in names and not self.removes_shield
                and self.route.tr.cd[me - 1] > 0):
            names = [a for a in names if a != "SHIELD"]
            view = _FView(obs.rows, me, obs.token, names)
            self.route._cur = self.route._cur[:7] + (list(names),)

        # -- 8. predict rivals that are exact copies of a public bot
        if self.mirror is not None:
            if not route_ok:
                self.mirror = None
            else:
                try:
                    tr = self.route.tr
                    frozen = [False] + [obs.pos[k] >= 0 and obs.cells[obs.pos[k]].is_frozen
                                        for k in (1, 2, 3, 4)]
                    self.mirror.update(obs.cells, obs.pos, frozen, tr.cd,
                                       set(i + 1 for i in tr.last_shielders),
                                       tr.token if tr.token_known else None)
                except Exception:
                    self.mirror = None

        action = None
        who = None
        econ_tried = False
        econ_first = FLAGS["primary"] == "econ" and self.cold_left <= 0
        order = ("econ", "route") if econ_first else ("route", "econ")
        for planner in order:
            if action is not None or not self._alive(planner):
                continue
            try:
                if planner == "econ":
                    econ_tried = True
                    a = self._econ_step(obs, names, route_ok)
                elif route_ok:
                    a = self.route.plan()
                else:
                    continue
                if a in names:
                    action, who = a, planner
            except Exception:
                self.errors[planner] += 1
        # The econ planner keeps its memory current even on turns it does not
        # play, so that it can take over with the right clock and scores. It
        # must observe each turn exactly once, so not if it already ran (or
        # raised part-way) above.
        if not econ_tried and self._alive("econ"):
            try:
                self._econ_step(obs, names, route_ok)
            except Exception:
                self.errors["econ"] += 1

        if who == "econ" and self.mirror is not None:
            try:
                a = self._exploit(obs, names, action)
                if a in names and a != action:
                    action = a
                    self.exploits += 1
            except Exception:
                self.mirror = None
        if action is None:
            try:
                a = _fallback(view)
                if a in names:
                    action, who = a, "fallback"
            except Exception:
                pass
        if action is None:
            action, who = "STAY", "stay"
        if self.cold_left > 0:
            self.cold_left -= 1

        # every planner records what was actually played, not what it proposed
        self.route.last_action = action
        if self.econ.mem is not None:
            self.econ.mem["last"] = action
        self.used[who] += 1
        sent = self.calib.to_server(action)
        if sent not in obs.lookup:
            sent = "STAY"
        self.last_sent = sent
        self.last_pos = here
        return obs.lookup[sent]

    def _exploit(self, obs, names, action):
        """Best response to rivals whose action this turn is known exactly."""
        m = self.mirror
        me = obs.seat
        cells, pos = obs.cells, obs.pos
        tr = self.route.tr
        at = pos[me]
        land = cells[at].owner
        # Offence: about to stay on a copy's land, and it is about to shield.
        # Staying gets me caught (frozen two turns, progress lost); stepping off
        # makes its shield backfire, and its land is then open for four turns.
        if (action == "STAY" and land not in (0, me) and not cells[at].is_home
                and m.predicted(land) == "SHIELD"):
            alt = self._escape(obs, names, land)
            if alt is not None:
                return alt
        # Defence: shield exactly when a copy is about to complete a take, and
        # never into a copy that is about to leave.
        intruders = [(pos[k], k) for k in (1, 2, 3, 4) if k != me and pos[k] >= 0
                     and cells[pos[k]].owner == me and not cells[pos[k]].is_home
                     and not cells[pos[k]].is_frozen]
        if not intruders:
            return action
        preds = [m.predicted(k) for _, k in intruders]
        if any(x is None for x in preds):
            return action                    # someone unpredictable is on my land
        if "SHIELD" in names:
            for (p, k), x in zip(intruders, preds):
                need = 3 if cells[p].is_upgraded else 1
                if x == "STAY" and need - tr.prog[k - 1] <= 1:
                    return "SHIELD"
        if action == "SHIELD":
            alt = getattr(self.econ, "pre_shield", None)
            if alt in names and alt != "SHIELD":
                return alt
        return action

    def _escape(self, obs, names, landlord):
        """The best one-step move off a cell I am about to be caught on."""
        e = self.econ
        best, bv = None, -1.0
        for task in getattr(e, "last_tasks", ()):
            rate, i = task[0], task[2]
            if e.last_travel[i] == 1 and e.last_first[i] in names and rate > bv:
                best, bv = e.last_first[i], rate
        if best is not None:
            return best
        at = obs.pos[obs.seat]
        occ = set(p for p in obs.pos[1:] if p >= 0)
        r, c = divmod(at, 8)
        for a in _F_MOVES:
            dr, dc = _F_DELTA[a]
            t = (r + dr) * 8 + c + dc
            if a in names and 0 <= r + dr < 8 and 0 <= c + dc < 8 and t not in occ \
                    and obs.cells[t].owner != landlord:
                return a
        return None

    def _econ_step(self, obs, names, route_ok):
        ext = None
        if FLAGS["ext_cd"] and route_ok:
            ext = [0] + list(self.route.tr.cd)
        # Woken mid-game with no memory: use the tracker's fitted turn estimate
        # (median error 5 turns) instead of the planner's own 2 + owned + upgrades
        # (median error 9). Only ever applies on that first cold observation.
        hint = self.route.tr.turn if route_ok else None
        return self.econ.step(obs.cells, obs.seat, names, obs.token, ext_cooldown=ext,
                              turn_hint=hint)


_F_BRAINS = {}


def act(state):
    """Starter-kit entry point: one action from state.legal_actions."""
    try:
        obs = _f_normalize(state)
    except Exception:
        return _f_emergency(state)
    try:
        brain = _F_BRAINS.get(obs.seat)
        if brain is None:
            brain = _FBrain(obs.seat)
            _F_BRAINS[obs.seat] = brain
        return brain.turn(obs)
    except Exception:
        return _f_emergency(state)
