"""Zone Rush bot: exact public-state tracker, hazard-aware route planner, adaptive tactics.

Single file, standard library only, entry point act(state). Uses the four documented
inputs (board, bot_id, is_priority_token, legal_actions) plus its own memory of earlier
public boards. Nothing here reads another bot's pending action or any hidden counter.
"""
import time

# ----------------------------------------------------------------------------- geometry
_ADJ = []
_DIST = []
for _i in range(64):
    _r, _c = divmod(_i, 8)
    _row = []
    if _r > 0:
        _row.append(("NORTH", _i - 8))
    if _c < 7:
        _row.append(("EAST", _i + 1))
    if _r < 7:
        _row.append(("SOUTH", _i + 8))
    if _c > 0:
        _row.append(("WEST", _i - 1))
    _ADJ.append(tuple(_row))
    _DIST.append(tuple(abs(_r - j // 8) + abs(_c - j % 8) for j in range(64)))
_NB = [tuple(j for _, j in row) for row in _ADJ]
_ACTIONS = ("NORTH", "EAST", "SOUTH", "WEST", "STAY", "SHIELD")


# ----------------------------------------------------------------------------- reading

class _View(object):
    __slots__ = ("me", "legal", "raw", "token", "pos", "owner", "level", "frozen", "base", "home", "occ")


def _read(state):
    """Normalise the documented input into flat lists. Never mutates `state`."""
    if isinstance(state, dict):
        get = lambda o, k, d=None: o.get(k, d)
    else:
        get = lambda o, k, d=None: getattr(o, k, d)
    v = _View()
    v.me = int(get(state, "bot_id"))
    v.token = bool(get(state, "is_priority_token", False))
    legal = []
    raw = {}                              # action name -> the object the server handed us
    for a in (get(state, "legal_actions", ()) or ()):
        name = a if isinstance(a, str) else (getattr(a, "name", None) or getattr(a, "value", None))
        if isinstance(name, str):
            name = name.strip().upper()
            if name in _ACTIONS and name not in raw:
                raw[name] = a
                legal.append(name)
    if not legal:
        raise ValueError("legal_actions")
    v.legal = legal
    v.raw = raw
    board = get(state, "board")
    first = board[0]
    if isinstance(first, (list, tuple)) and len(first) == 8 and not hasattr(first, "owner"):
        cells = [c for row in board for c in row]
    else:
        cells = list(board)
    if len(cells) != 64:
        raise ValueError("board")
    if isinstance(cells[0], dict):
        cg = lambda o, k, d=None: o.get(k, d)
    else:
        cg = lambda o, k, d=None: getattr(o, k, d)
    v.pos = [-1] * 5
    v.frozen = [False] * 5
    v.owner = [0] * 64
    v.level = [0] * 64
    v.base = [1] * 64
    v.home = [False] * 64
    v.occ = [0] * 64
    for i, c in enumerate(cells):
        o = int(cg(c, "occupant", 0) or 0)
        v.owner[i] = int(cg(c, "owner", 0) or 0)
        v.level[i] = 1 if cg(c, "is_upgraded", False) else 0
        v.base[i] = int(cg(c, "base_points", 1) or 1)
        v.home[i] = bool(cg(c, "is_home", False))
        if 1 <= o <= 4:
            v.occ[i] = o
            v.pos[o] = i
            v.frozen[o] = bool(cg(c, "is_frozen", False))
    if v.pos[v.me] < 0:
        raise ValueError("self not on board")
    return v


# ----------------------------------------------------------------------------- tracker

def _need(seat, owner, level, home):
    """Stays required for `seat` to finish the job on a cell in the given state."""
    if owner == seat:
        return 0 if level else 3
    if owner == 0:
        return 1
    if home:
        return 0
    return 3 if level else 1


def _pristine(v):
    if sum(1 for o in v.owner if o) != 4 or any(v.level):
        return False
    for s in range(1, 5):
        p = v.pos[s]
        if p < 0 or not v.home[p] or v.owner[p] != s:
            return False
    return True


# How landlords use SHIELD when a rival stands on their land, as P(shield) in four
# contexts: a1 = rival on a level-1 cell (one stay takes it), b0/b1 = rival on a level-2
# cell with 0/1 stays banked, a2 = rival one stay from taking a level-2 cell.
# Rows: never shields; shields on sight; defends every imminent take; defends mostly
# level-2 takes; shields a stay early. The posterior over rows is updated from every
# stand-off anyone has with that landlord, so one or two sightings are enough to adapt.
_CTX_RANK = {"b0": 0, "b1": 1, "a1": 2, "a2": 3}
_SHIELD_TYPES = ((.02, .02, .02, .03),
                 (.90, .92, .92, .95),
                 (.08, .12, .92, .96),
                 (.06, .12, .30, .94),
                 (.10, .60, .50, .90))
_TYPE_PRIOR = (.15, .10, .25, .45, .05)


class _Mem(object):
    """Everything remembered between turns of one game."""

    def __init__(self, v):
        fresh = _pristine(v)
        self.known_start = fresh
        if fresh:
            self.turn = 1
            self.cd_sure = [True] * 5
        else:
            # Dropped into a running game: estimate the clock from how developed the board is.
            owned = sum(1 for o in v.owner if o) - 4
            self.turn = min(70, max(2, 2 + owned + 2 * sum(v.level)))
            self.cd_sure = [False] * 5
        self.pos, self.owner, self.level, self.frozen = list(v.pos), list(v.owner), list(v.level), list(v.frozen)
        self.last = None                 # action requested last turn
        self.shield_was_legal = False
        self.legal_filters = False       # the server has been seen to withhold SHIELD on cooldown
        self.scores = [0] * 5
        self.prog = [0] * 5              # banked stays toward the job on the current cell
        self.cd = [0] * 5                # turns until SHIELD is available again (0 = ready)
        self.fr = [1 if f else 0 for f in v.frozen]   # forced-STAY turns still to serve
        self.token = None                # seat holding the priority token on turn 1
        self.not_token = set()
        # Landlord model: posterior over shield habits (see _SHIELD_TYPES).
        self.typ = [None] + [list(_TYPE_PRIOR) for _ in range(4)]
        # Raider model: [stays, trials] per stand-off context, seeded with population rates.
        self.st = [None] + [{"a1": [1.5, 2.0], "b0": [1.2, 2.0], "b1": [1.8, 2.0], "a2": [1.8, 2.0]}
                            for _ in range(4)]
        self.raid_n = [0.0] * 5
        self.raid_opp = [0.0] * 5
        self.shields_seen = [0] * 5
        self.backfires_seen = [0] * 5
        self.feinted_me = [0] * 5        # times this rival sidestepped my shield
        self.presence_rule = False       # a successful mover was caught: sidesteps are unsafe
        self.failed = {}                 # cell -> (owner, level) for jobs that refused to complete
        self.unexplained = 0
        self.rng = None
        self.scale = 1.0                 # search effort; shrinks if a turn ever runs long
        self.errors = 0
        self.plan = None
        self.raid = None
        self.note_token(v)

    def q_shield(self, d, ctx):
        """P(landlord d casts SHIELD now) given what has been seen of it."""
        k = _CTX_RANK[ctx]
        post = self.typ[d]
        tot = sum(post)
        return sum(post[t] * _SHIELD_TYPES[t][k] for t in range(len(post))) / tot

    # -- priority token -------------------------------------------------------------
    def note_token(self, v):
        """The token passes 1->2->3->4 every turn; one sighting of our flag fixes the cycle."""
        if self.token is not None or not self.known_start:
            return
        start = ((v.me - 1) - (self.turn - 1)) % 4 + 1
        if v.token:
            self.token = start
        else:
            self.not_token.add(start)
            if len(self.not_token) == 3:
                self.token = ({1, 2, 3, 4} - self.not_token).pop()

    def token_holder(self, turn):
        if self.token is None:
            return None
        return (self.token - 1 + turn - 1) % 4 + 1

    # -- one turn of public evidence --------------------------------------------------
    def observe(self, v):
        me = v.me
        self.turn = min(self.turn + 1, 80)
        ppos, pown, plev, pfro = self.pos, self.owner, self.level, self.frozen
        moved = [False] * 5
        for s in range(1, 5):
            moved[s] = v.pos[s] != ppos[s]
        newly = set(s for s in range(1, 5) if v.frozen[s] and not pfro[s])
        gained = [False] * 5             # took a cell or finished an upgrade: it effectively stayed
        lost = [False] * 5
        for c in range(64):
            if v.owner[c] != pown[c]:
                if v.owner[c]:
                    gained[v.owner[c]] = True
                if pown[c]:
                    lost[pown[c]] = True
            elif v.level[c] and not plev[c] and v.owner[c]:
                gained[v.owner[c]] = True

        shielders = self._who_shielded(v, me, moved, newly, gained, lost)
        caught = set()
        for x in shielders:
            for s in newly:
                if s != x and s not in shielders and pown[ppos[s]] == x:
                    caught.add(s)

        # ---- per-opponent statistics from last turn's stand-offs
        seen_ctx = [None] * 5            # most pressing context each landlord faced
        for r in range(1, 5):
            p = ppos[r]
            d = pown[p]
            if d == 0 or d == r or pfro[r] or v.home[p]:
                continue
            pr = self.prog[r]
            ctx = "a1" if not plev[p] else ("a2" if pr >= 2 else "b1" if pr == 1 else "b0")
            if r != me:
                # only an effective STAY can be caught; a move or its own SHIELD cannot
                row = self.st[r][ctx]
                row[0] = 0.9 * row[0] + (0.0 if (moved[r] or r in shielders) else 1.0)
                row[1] = 0.9 * row[1] + 1.0
            if d != me and not pfro[d] and self.cd[d] == 0 and self.cd_sure[d]:
                old = seen_ctx[d]
                if old is None or _CTX_RANK[ctx] > _CTX_RANK[old]:
                    seen_ctx[d] = ctx
            if d == me and me in shielders and moved[r]:
                self.feinted_me[r] += 1
        for d in range(1, 5):
            ctx = seen_ctx[d]
            if ctx is None:
                continue
            k = _CTX_RANK[ctx]
            post = self.typ[d]
            hit = d in shielders
            tot = 0.0
            for t in range(len(post)):
                q = _SHIELD_TYPES[t][k]
                post[t] *= q if hit else 1.0 - q
                tot += post[t]
            for t in range(len(post)):
                post[t] = max(0.01, post[t] / tot) if tot > 0 else _TYPE_PRIOR[t]
        for s in shielders:
            self.shields_seen[s] += 1
            if s in newly:
                self.backfires_seen[s] += 1

        # ---- raid propensity: adjacent to somebody's exposed level-1 cell, did it step on?
        occupied = set(ppos[1:])
        for r in range(1, 5):
            if r == me or pfro[r]:
                continue
            chance = False
            for q in _NB[ppos[r]]:
                o = pown[q]
                if o and o != r and not plev[q] and not v.home[q] and q not in occupied:
                    chance = True
                    break
            if chance:
                self.raid_opp[r] += 1.0
                q = v.pos[r]
                if moved[r] and pown[q] and pown[q] != r and not plev[q] and not v.home[q]:
                    self.raid_n[r] += 1.0

        # ---- progress (mirrors the documented work rules)
        for s in range(1, 5):
            if moved[s] or pfro[s] or s in shielders or s in newly:
                self.prog[s] = 0
                continue
            p = v.pos[s]
            land = pown[p]
            need = _need(s, land, plev[p], v.home[p])
            if need == 0:
                continue
            if land and land != s and land in shielders:
                continue
            if (v.owner[p] == s and land != s) or (land == s and v.level[p] and not plev[p]):
                self.prog[s] = 0
            else:
                self.prog[s] += 1
                if self.prog[s] >= need:
                    # The job should have completed. Remember it so we stop retrying forever.
                    if s == me:
                        self.failed[p] = (v.owner[p], v.level[p])
                    self.prog[s] = need - 1
        # ---- cooldowns
        for s in range(1, 5):
            if s in shielders:
                self.cd[s] = 4
                self.cd_sure[s] = True
            elif self.cd[s] > 0:
                self.cd[s] -= 1
        # ---- scores: income after resolution plus raid bonuses
        for c in range(64):
            o = v.owner[c]
            if o:
                self.scores[o] += v.base[c] * (1 + v.level[c])
                po = pown[c]
                if po and po != o:
                    self.scores[o] += 8 * v.base[c] * (1 + plev[c])
        for s in range(1, 5):
            if not v.frozen[s]:
                self.fr[s] = 0
            elif s in newly:
                self.fr[s] = 2
            else:
                self.fr[s] = max(1, self.fr[s] - 1)
        self.pos, self.owner, self.level, self.frozen = list(v.pos), list(v.owner), list(v.level), list(v.frozen)
        self.note_token(v)

    def _who_shielded(self, v, me, moved, newly, gained, lost):
        """Explain the new freezes. Every SHIELD freezes somebody: its victims, or its caster."""
        ppos, pown, pfro = self.pos, self.owner, self.frozen
        mine = (self.last == "SHIELD" and self.shield_was_legal and not pfro[me])
        if not newly:
            return set()
        for s in newly:
            if moved[s]:
                # Frozen after a successful move: this server catches by presence, not by STAY.
                self.presence_rule = True
        cand = []
        for s in range(1, 5):
            if pfro[s] or moved[s] or gained[s] or lost[s]:
                continue
            if s == me:
                if mine:
                    cand.append(s)
                continue
            if self.cd[s] > 0 and self.cd_sure[s]:
                continue
            cand.append(s)
        best, best_cost = None, None
        n = len(cand)
        for mask in range(1, 1 << n):
            sh = [cand[k] for k in range(n) if mask >> k & 1]
            pred = set()
            cost = 0.0
            for x in sh:
                got = [s for s in range(1, 5)
                       if s != x and s not in sh and not pfro[s]
                       and (not moved[s] or self.presence_rule) and pown[v.pos[s]] == x]
                if got:
                    pred.update(got)
                    cost += 1.0             # a landlord defending: the ordinary cause
                else:
                    pred.add(x)
                    land = pown[ppos[x]]
                    # Backfiring on someone else's land is rarer than a landlord's catch.
                    cost += 1.5 if (land == 0 or land == x) else 3.0
            if pred != newly:
                continue
            if mine and me not in sh:
                cost += 5.0                 # my own accepted SHIELD should be part of the story
            if best is None or cost < best_cost:
                best, best_cost = set(sh), cost
        if best is None:
            self.unexplained += 1
            best = set()
            for s in newly:
                land = pown[ppos[s]]
                if land and land != s and not pfro[land]:
                    best.add(land)
                else:
                    best.add(s)
        return best


_M = None


def _update(v):
    global _M
    m = _M
    restart = m is None
    if not restart and _pristine(v):
        # A pristine board can also be turn 2 of a quiet opening; a new game is certain
        # once the remembered board had developed.
        if m.turn >= 80 or any(m.level) or sum(1 for o in m.owner if o) > 4:
            restart = True
    if restart:
        m = _M = _Mem(v)
    else:
        m.observe(v)
    me = v.me
    # Own cooldown: the legal list is authoritative once the server is seen to filter it.
    if not v.frozen[me]:
        if "SHIELD" not in v.legal:
            m.legal_filters = True
            if m.cd[me] == 0:
                m.cd[me] = 1
        elif m.legal_filters or not m.cd_sure[me]:
            m.cd[me] = 0
            m.cd_sure[me] = True
    return m


