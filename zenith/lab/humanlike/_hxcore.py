"""Shared core of the human-like exploiters (hx_*.py exec this file, then set STYLE).

Each style is how a person who has watched these bots play might beat them.
Nothing here reads more than the server exposes (board, bot_id, token flag,
legal_actions); everything else is reconstructed from board diffs, the way a
human keeps track at the table.

    steady   solid farmer: claims the best cells near home first, upgrades the
             2s and 3s, shields only on the turn a raid would complete, and
             snipes rival level-1 cells in the last turns
    bait     shield baiter: sits on a rival's upgraded cell for two turns and
             steps off on the turn the owner shields, so the shield backfires;
             then walks back and takes the cell inside the four-turn cooldown.
             If the owner stopped answering baits, it just commits
    cdsnipe  cooldown sniper: raids only cells whose owner cannot shield before
             the take completes (on cooldown or frozen), upgraded cells first
    aggro    early aggression: lives off one-stay raids on the leader's
             level-1 cells from turn one, farms only when nothing is in reach
    sniper   endgame raider: farms, then spends the last fifteen turns on raids,
             whose bonus does not decay, and shields for free on the last turn
    mixed    picks one of the above per game (a person adapting between games)
"""
import os as _hos
import random as _random

_EVO_SRC = _hos.path.join(_hos.path.dirname(_hos.path.abspath(__file__)), "..", "..", "..",
                          "apex", "src", "evosim.py")
with open(_EVO_SRC) as _ef:
    exec(compile(_ef.read(), _EVO_SRC, "exec"))
_GENOME = {
    "steady": dict(EVO_GENOMES[0], denial_base=0.0, denial_close=0.0, raid_open=0.6),
    "bait": dict(EVO_GENOMES[0]),
    "cdsnipe": dict(EVO_GENOMES[0], raid_open=0.7, raid_late=1.2),
    "aggro": dict(EVO_GENOMES[0], raid_open=1.8, raid_late=2.2, risk_open=1.0),
    "sniper": dict(EVO_GENOMES[0], raid_open=0.7, raid_late=3.5),
}

_N = 8
_ADJ = []
for _p in range(64):
    _r, _c = divmod(_p, 8)
    _ADJ.append([(nm, q) for nm, q, ok in (
        ("NORTH", _p - 8, _r > 0), ("SOUTH", _p + 8, _r < 7),
        ("WEST", _p - 1, _c > 0), ("EAST", _p + 1, _c < 7)) if ok])
_MD = [[abs(a // 8 - b // 8) + abs(a % 8 - b % 8) for b in range(64)] for a in range(64)]
_HOMES = (0, 7, 63, 56)
STYLES = ("steady", "bait", "cdsnipe", "aggro", "sniper")


def _cells(board):
    seq = list(board)
    if len(seq) == 8 and isinstance(seq[0], (list, tuple)) and len(seq[0]) == 8:
        return [c for row in seq for c in row]
    return seq


class _Mind(object):
    def __init__(self, me, style, seed):
        self.me = me
        self.style = style
        self.rnd = _random.Random(seed)
        self.turn = 0
        self.prev = None
        self.cd = [0] * 5
        self.score = [0] * 5
        self.prog = 0                 # my consecutive stays on this cell
        self.rstay = [0] * 5          # each rival's consecutive stays on its cell
        self.last = None
        self.bait = None              # (cell, owner, phase, turn)
        self.answered = {}            # owner -> [baits answered, baits tried]
        self.target = None
        self.evo = EvoSim(_GENOME.get(style, EVO_GENOMES[0]))

    # ---------------------------------------------------------- observation
    def observe(self, cells):
        pos = [-1] * 5
        frz = [False] * 5
        for i, c in enumerate(cells):
            o = int(c.occupant or 0)
            if 1 <= o <= 4:
                pos[o] = i
                frz[o] = bool(c.is_frozen)
        owner = [int(c.owner or 0) for c in cells]
        up = [bool(c.is_upgraded) for c in cells]
        base = [int(c.base_points or 1) for c in cells]
        home = [bool(c.is_home) for c in cells]
        cur = {"pos": pos, "frz": frz, "owner": owner, "up": up}
        fresh = (sum(1 for o in owner if o) == 4 and not any(up) and
                 all(pos[s] >= 0 and home[pos[s]] for s in (1, 2, 3, 4)))
        p = self.prev
        if p is None or (fresh and self.turn > 6):
            self.turn = 1
            self.cd = [0] * 5
            self.score = [0] * 5
            self.prog = 0
            self.rstay = [0] * 5
        else:
            self.turn += 1
            for s in (1, 2, 3, 4):
                self.cd[s] = max(0, self.cd[s] - 1)
            # shields, read off the freezes
            for s in (1, 2, 3, 4):
                if frz[s] and not p["frz"][s]:
                    c = pos[s]
                    o = p["owner"][c]
                    if o not in (0, s) and pos[s] == p["pos"][s] and not p["frz"][o]:
                        self.cd[o] = 4            # the landlord caught it
                    else:
                        self.cd[s] = 4            # its own shield backfired
            if self.last == "SHIELD" and not frz[self.me]:
                self.cd[self.me] = 4
            # scores: raid bonuses, then income
            for i in range(64):
                o, po = owner[i], p["owner"][i]
                if o and po and o != po:
                    self.score[o] += 8 * base[i] * (2 if p["up"][i] else 1)
            for i in range(64):
                if owner[i]:
                    self.score[owner[i]] += base[i] * (2 if up[i] else 1)
            for s in (1, 2, 3, 4):
                c = pos[s]
                same = c == p["pos"][s] and not frz[s] and not p["frz"][s]
                changed = owner[c] != p["owner"][c] or up[c] != p["up"][c]
                if s == self.me:
                    self.prog = 0 if (not same or changed or self.last == "SHIELD") else self.prog + 1
                else:
                    self.rstay[s] = 0 if (not same or changed) else self.rstay[s] + 1
        self.prev = cur
        return pos, frz, owner, up, base, home

    # ---------------------------------------------------------- helpers
    def bfs(self, src, blocked):
        dist = [99] * 64
        first = [None] * 64
        dist[src] = 0
        q = [src]
        k = 0
        while k < len(q):
            x = q[k]
            k += 1
            for nm, y in _ADJ[x]:
                if dist[y] == 99 and y not in blocked:
                    dist[y] = dist[x] + 1
                    first[y] = nm if x == src else first[x]
                    q.append(y)
        return dist, first

    def window(self, o, frz):
        """Turns from now during which owner o cannot shield."""
        f = 2 if frz[o] else 0
        return max(self.cd[o], f)

    # ---------------------------------------------------------- policy
    def choose(self, cells, legal):
        me = self.me
        pos, frz, owner, up, base, home = self.observe(cells)
        at = pos[me]
        left = 81 - self.turn
        if at < 0:
            return "STAY"
        # the evolved planner observes every turn, so its memory follows the game
        income = [0] * 5
        for c in range(64):
            if owner[c]:
                income[owner[c]] += base[c] * (2 if up[c] else 1)
        lvl = [1 if u else 0 for u in up]
        try:
            ev = self.evo.step(me, legal, bool(self.token), base, home, owner, lvl, pos, frz, income)
        except Exception:
            ev = "STAY"
        a = self.layer(ev, at, pos, frz, owner, up, base, home, legal, left)
        if a not in legal:
            a = "STAY"
        if self.evo.mem is not None:
            self.evo.mem["last"] = a
        return a

    def layer(self, ev, at, pos, frz, owner, up, base, home, legal, left):
        me = self.me
        if len(legal) == 1:
            return legal[0]
        can_shield = "SHIELD" in legal and self.cd[me] == 0
        style = self.style
        threat = 0.0
        # -------- defence: shield on the turn a raid would complete
        if can_shield:
            for s in (1, 2, 3, 4):
                if s == me or frz[s] or pos[s] < 0:
                    continue
                c = pos[s]
                if owner[c] != me or home[c]:
                    continue
                if up[c]:
                    if self.rstay[s] >= 2:
                        threat += 16 * base[c] + 2 * base[c] * min(left, 20)
                else:
                    threat += (8 * base[c] + base[c] * min(left, 15)) * 0.7
            if left <= 1 and threat > 0:
                return "SHIELD"
            if threat >= (40 if style != "aggro" else 55):
                return "SHIELD"
        blocked = set(pos[s] for s in (1, 2, 3, 4) if s != me and pos[s] >= 0)
        dist, first = self.bfs(at, blocked)
        # -------- the bait state machine
        if style == "bait":
            a = self.bait_move(at, pos, frz, owner, up, base, home, dist, first, legal, left)
            if a is not None:
                return a
        # -------- style opportunities, else the evolved planner's economy
        opp = self.opportunity(at, pos, frz, owner, up, base, home, dist, first, left)
        a = opp if opp is not None else ev
        if a == "SHIELD" and threat <= 0:
            a = "STAY"
        return a

    def opportunity(self, at, pos, frz, owner, up, base, home, dist, first, left):
        """A raid this style would take over the planner's choice, or None."""
        style = self.style
        me = self.me
        if style in ("steady", "bait"):
            if left > 12:
                return None
        lead = max(range(1, 5), key=lambda s: (self.score[s] if s != me else -1, s))
        best, bi = 0.0, -1
        for i in range(64):
            o = owner[i]
            if o in (0, me) or home[i] or dist[i] >= 99:
                continue
            d = dist[i]
            v = base[i]
            work = 3 if up[i] else 1
            if i == at:
                work = max(1, work - self.prog)
            if d + work > left or d > 4:
                continue
            safe = self.window(o, frz) >= d + work
            bonus = 8 * v * (2 if up[i] else 1)
            val = bonus + v * (left - d - work + 1) * (0.5 if left > 20 else 1.0)
            if style == "cdsnipe":
                if not safe:
                    continue
            elif style == "aggro":
                if up[i] and not safe:
                    continue
                if o == lead:
                    val *= 1.3
            elif style in ("sniper", "steady", "bait"):
                if left > (15 if style == "sniper" else 12):
                    continue
                if up[i] and not safe:
                    continue
            rate = val / (d + work)
            if rate > best:
                best, bi = rate, i
        need = {"cdsnipe": 9.0, "aggro": 7.0, "sniper": 6.0, "steady": 8.0, "bait": 8.0}[style]
        if bi < 0 or best < need:
            return None
        if bi == at:
            return "STAY"
        return first[bi]

    def bait_move(self, at, pos, frz, owner, up, base, home, dist, first, legal, left):
        me = self.me
        b = self.bait
        if b is not None:
            cell, o, phase, t0 = b
            if self.turn - t0 > 14 or owner[cell] == me or left < 6:
                self.bait = None
                b = None
        if b is not None:
            cell, o, phase, t0 = b
            if phase == "go":
                if at == cell:
                    self.bait = (cell, o, "sit", self.turn)
                    return "STAY"
                if dist[cell] >= 99:
                    self.bait = None
                    return None
                return first[cell] if first[cell] in legal else "STAY"
            if phase == "sit":
                rec = self.answered.setdefault(o, [1.0, 2.0])
                commit = rec[0] / rec[1] < 0.35 or self.window(o, frz) >= 3 - self.prog
                if at != cell:
                    self.bait = None
                    return None
                if commit:
                    return "STAY"
                if self.prog >= 2:                    # owner should shield now: step off
                    for nm, q in _ADJ[at]:
                        if nm in legal and q not in set(pos):
                            self.bait = (cell, o, "off", self.turn)
                            return nm
                return "STAY"
            if phase == "off":
                rec = self.answered.setdefault(o, [1.0, 2.0])
                rec[1] += 1
                if self.cd[o] >= 3 or frz[o]:
                    rec[0] += 1
                    self.bait = (cell, o, "take", self.turn)
                else:
                    self.bait = (cell, o, "sit", self.turn) if dist[cell] < 99 else None
                if self.bait is not None and dist[cell] < 99:
                    return first[cell] if first[cell] in legal else "STAY"
                return None
            if phase == "take":
                if at == cell:
                    return "STAY"
                if dist[cell] >= 99:
                    self.bait = None
                    return None
                return first[cell] if first[cell] in legal else "STAY"
        # pick a new bait: a rival's upgraded cell close by, owner able to shield;
        # a person baits now and then, not every turn
        if self.turn < 16 or left < 10 or self.turn - getattr(self, "last_bait", -99) < 15:
            return None
        best, bc = 0.0, None
        for i in range(64):
            o = owner[i]
            if o in (0, me) or not up[i] or home[i] or dist[i] > 3 or base[i] < 2:
                continue
            if frz[o] or self.cd[o] > 0:
                continue
            val = 16 * base[i] / (dist[i] + 4)
            if val > best:
                best, bc = val, i
        if bc is not None and best >= 5.0:
            self.bait = (bc, owner[bc], "go", self.turn)
            self.last_bait = self.turn
            return first[bc] if first[bc] in legal else None
        return None


_MINDS = {}


def act(state):
    try:
        cells = _cells(state.board)
        me = int(state.bot_id)
        legal = list(state.legal_actions)
        m = _MINDS.get(me)
        fresh = (sum(1 for c in cells if c.owner) == 4 and not any(c.is_upgraded for c in cells))
        if m is None or (fresh and m.turn > 6):
            style = STYLE
            if style == "mixed":
                style = STYLES[(sum(c.base_points for c in cells) * 7 + me) % len(STYLES)]
            m = _MINDS[me] = _Mind(me, style, me * 977 + sum(c.base_points for c in cells))
        m.token = bool(getattr(state, "is_priority_token", False))
        a = m.choose(cells, legal)
        if a not in legal:
            a = "STAY"
        m.last = a
        return a
    except Exception:
        return "STAY"


STYLE = "steady"
