"""
Outsiders: opponent designs that are NOT in this repository.

Every bot the shipped bot was tuned and measured against was written inside this
repository, by the same hand that wrote the bot. These eight were written for the
audit from the rulebook and the starter-kit README alone, share no code with
zoo.py / aifield.py / holdout.py / probot.py, and each one is built around an idea
the existing field does not contain:

  x_fort      Perfect-timing defender. Claims AND upgrades a compact cluster, and
              shields only at the one moment that matters: a rival's third stay on
              an UPGRADED cell. (2 frozen turns + 3 stays = 5 > 4-turn cooldown, so
              an upgraded cell can be held forever this way.) Never raids.
  x_leech     Patient level-1 raider. Takes rival level-1 cells (1 stay, 8 x v
              bonus) and never bails -- not even after being frozen, because the
              freeze (2) plus its single stay (1) is shorter than the cooldown (4).
  x_homebait  Home baiter. Farms, then steps onto a rival's HOME (which can never be
              taken) and straight off again to make the rival's shield backfire;
              raids that rival during the cooldown window. If baits stop working it
              raids directly.
  x_jackal    Trails the leader and steals its fresh level-1 claims, preferring
              owners that are on cooldown or frozen.
  x_vulture   Farms for 58 turns, then raids upgraded rival cells (16 x v bonus,
              which never decays) and shields for free on the last turn.
  x_flaky     A decent farmer that behaves like a real broken entry: 20% of turns
              lost to timeouts, occasional illegal strings, and a 30% chance of
              crashing for good partway through.
  x_literal   The single-prompt "first attempt": scores every target by points per
              turn of effort with the raid bonus included, raids eagerly, and
              shields on sight whenever a rival stands on a non-home cell it owns.
  x_sim       A different architecture: no hand-written plan at all. For each legal
              action it runs short random rollouts through a rules simulator and
              picks the action with the best simulated outcome.

All of them follow the starter-kit contract exactly: act on `view` (board,
bot_id, is_priority_token, legal_actions), return one string from legal_actions.
"""
import random

N = 8
NC = 64
NB = []
for _p in range(NC):
    _r, _c = divmod(_p, N)
    _o = []
    if _r > 0:
        _o.append(("NORTH", _p - N))
    if _r < N - 1:
        _o.append(("SOUTH", _p + N))
    if _c > 0:
        _o.append(("WEST", _p - 1))
    if _c < N - 1:
        _o.append(("EAST", _p + 1))
    NB.append(tuple(_o))


def manh(a, b):
    ar, ac = divmod(a, N)
    br, bc = divmod(b, N)
    return abs(ar - br) + abs(ac - bc)


class Board(object):
    """The view, flattened. Reads only the six documented Cell attributes."""

    def __init__(self, view):
        bd = view.board
        if bd and isinstance(bd[0], (list, tuple)):
            cells = [bd[r][c] for r in range(N) for c in range(N)]
        else:
            cells = list(bd)
        self.base = [c.base_points for c in cells]
        self.owner = [c.owner for c in cells]
        self.upg = [bool(c.is_upgraded) for c in cells]
        self.home = [bool(c.is_home) for c in cells]
        self.occ = [c.occupant for c in cells]
        self.frz = [bool(c.is_frozen) for c in cells]
        self.seat = view.bot_id
        self.pos = [None] * 4
        for p in range(NC):
            if self.occ[p]:
                self.pos[self.occ[p] - 1] = p
        self.me = self.pos[self.seat - 1]
        self.homes = [None] * 4
        for p in range(NC):
            if self.home[p] and self.owner[p]:
                self.homes[self.owner[p] - 1] = p

    def blocked(self):
        return set(p for p in range(NC) if self.occ[p] and p != self.me)

    def dist(self, src, avoid=None):
        avoid = self.blocked() if avoid is None else avoid
        d = [99] * NC
        d[src] = 0
        q = [src]
        i = 0
        while i < len(q):
            u = q[i]
            i += 1
            for _nm, w in NB[u]:
                if d[w] == 99 and w not in avoid:
                    d[w] = d[u] + 1
                    q.append(w)
        return d

    def step_to(self, target, rnd=None):
        if target is None or target == self.me:
            return "STAY"
        blk = self.blocked()
        d = self.dist(target, blk - {target})
        opts = [(d[w], nm) for nm, w in NB[self.me] if w not in blk and d[w] < 99]
        if not opts:
            opts = [(manh(w, target), nm) for nm, w in NB[self.me] if w not in blk]
        if not opts:
            return "STAY"
        best = min(o[0] for o in opts)
        names = [nm for dd, nm in opts if dd == best]
        if rnd is not None and len(names) > 1:
            return rnd.choice(names)
        return names[0]

    def zone(self, p):
        """Seat (1-4) whose home is nearest to p."""
        best, bd = 0, 99
        for s in range(4):
            h = self.homes[s]
            if h is None:
                continue
            dd = manh(p, h)
            if dd < bd:
                bd, best = dd, s + 1
        return best

    def rivals_on_my_land(self):
        out = []
        for j in range(4):
            p = self.pos[j]
            if j == self.seat - 1 or p is None or self.frz[p]:
                continue
            if self.owner[p] == self.seat:
                out.append((j, p))
        return out


class Watch(object):
    """Shield cooldowns and consecutive stays, rebuilt from board diffs."""

    def __init__(self):
        self.prev = None
        self.cd = [0] * 4
        self.stays = [0] * 4

    def update(self, b):
        if self.prev is not None:
            ppos, powner, pfrz = self.prev
            for i in range(4):
                if self.cd[i] > 0:
                    self.cd[i] -= 1
            for j in range(4):
                p, pp = b.pos[j], ppos[j]
                if p is None or pp is None:
                    continue
                was = pfrz[j]
                now = b.frz[p]
                if now and not was:
                    o = powner[pp]
                    if pp == p and o and o != j + 1:
                        self.cd[o - 1] = 4          # landlord caught j
                    else:
                        self.cd[j] = 4              # j's own shield backfired
                if p == pp and not was and not now:
                    self.stays[j] += 1
                else:
                    self.stays[j] = 0
        self.prev = (b.pos[:], b.owner[:],
                     [b.frz[b.pos[j]] if b.pos[j] is not None else False
                      for j in range(4)])

    def ready(self, b, j):
        """Can seat index j shield this turn?"""
        p = b.pos[j]
        return self.cd[j] == 0 and not (p is not None and b.frz[p])


class Outsider(object):
    name = "x_base"

    def __init__(self, seed=0):
        self.rnd = random.Random(seed)
        self.t = 0
        self.watch = Watch()

    def __call__(self, view):
        self.t += 1
        try:
            a = self.act(view)
        except Exception:
            a = "STAY"
        return a if a in view.legal_actions else "STAY"

    def R(self):
        return 81 - self.t                          # turns left including this one

    # A plain rate farmer several designs fall back on.
    def farm(self, b, upgrade_min=3):
        me, seat, R = b.me, b.seat, self.R()
        o = b.owner[me]
        if o == 0 and not b.home[me]:
            return "STAY"
        if o == seat and not b.upg[me] and b.base[me] >= upgrade_min and R > 3:
            return "STAY"
        d = b.dist(me)
        best, bs = None, 0.0
        for p in range(NC):
            if d[p] >= 99 or b.occ[p] or b.home[p] or b.owner[p] != 0:
                continue
            s = b.base[p] * max(0, R - d[p] - 1) / float(d[p] + 1)
            if s > bs:
                bs, best = s, p
        if best is None:
            for p in range(NC):
                if d[p] >= 99 or b.occ[p] or b.owner[p] != seat or b.upg[p]:
                    continue
                s = b.base[p] * max(0, R - d[p] - 3) / float(d[p] + 3)
                if s > bs:
                    bs, best = s, p
        return b.step_to(best, self.rnd)

    def timed_shield(self, b, legal, on_l1=False):
        """Shield only when it decides something: a third stay on an upgraded
        cell, (optionally) any stay on a level-1 cell, or anything on turn 80."""
        if "SHIELD" not in legal:
            return False
        for j, p in b.rivals_on_my_land():
            if self.R() <= 1 and not b.home[p]:
                return True
            if b.home[p]:
                continue
            if b.upg[p] and self.watch.stays[j] >= 2:
                return True
            if on_l1 and not b.upg[p]:
                return True
        return False


class Fort(Outsider):
    name = "x_fort"

    def act(self, view):
        b = Board(view)
        self.watch.update(b)
        if self.timed_shield(b, view.legal_actions):
            return "SHIELD"
        me, seat, R = b.me, b.seat, self.R()
        o = b.owner[me]
        if o == 0 and not b.home[me] and b.zone(me) == seat:
            return "STAY"
        if o == seat and not b.upg[me] and R > 3:
            return "STAY"                           # claim then upgrade, every cell
        d = b.dist(me)
        best, bs = None, 0.0
        for p in range(NC):
            if d[p] >= 99 or b.occ[p] or b.zone(p) != seat:
                continue
            if b.owner[p] == 0 and not b.home[p]:
                need = 4
            elif b.owner[p] == seat and not b.upg[p]:
                need = 3
            else:
                continue
            s = b.base[p] * max(0, R - d[p] - need) / float(d[p] + need)
            if s > bs:
                bs, best = s, p
        if best is None:                            # all done: sit on the best cell
            best = max((p for p in range(NC) if b.owner[p] == seat),
                       key=lambda p: (b.base[p] * (2 if b.upg[p] else 1), -d[p]))
        return b.step_to(best, self.rnd)


class Leech(Outsider):
    name = "x_leech"

    def act(self, view):
        b = Board(view)
        self.watch.update(b)
        me, seat, R = b.me, b.seat, self.R()
        o = b.owner[me]
        if o and o != seat and not b.home[me] and not b.upg[me]:
            return "STAY"                           # committed: never bail
        if o == 0 and not b.home[me]:
            return "STAY"
        d = b.dist(me)
        best, bs = None, 0.0
        for p in range(NC):
            if d[p] >= 99 or b.occ[p] or b.home[p]:
                continue
            op = b.owner[p]
            if op == seat or (op and b.upg[p]):
                continue
            rem = max(0, R - d[p] - 1)
            val = (8 * b.base[p] + b.base[p] * rem) if op else 0.6 * b.base[p] * rem
            s = val / float(d[p] + 1)
            if s > bs:
                bs, best = s, p
        return b.step_to(best, self.rnd)


class HomeBait(Outsider):
    name = "x_homebait"

    def __init__(self, seed=0):
        Outsider.__init__(self, seed)
        self.victim = None
        self.fails = 0
        self.pending = False
        self.arrived = False
        self.last_pos = None

    def act(self, view):
        b = Board(view)
        self.watch.update(b)
        me, seat, R = b.me, b.seat, self.R()
        just_moved = self.last_pos is not None and me != self.last_pos
        self.last_pos = me
        if self.timed_shield(b, view.legal_actions):
            return "SHIELD"
        if self.t <= 20 or R <= 2:
            return self.farm(b)
        if self.victim is None:
            rivals = [j for j in range(4) if j != seat - 1 and b.homes[j] is not None]
            self.victim = min(rivals, key=lambda j: manh(me, b.homes[j]))
        v = self.victim
        if self.pending:                            # did the last bait land?
            self.pending = False
            if self.watch.ready(b, v):
                self.fails += 1
        open_window = not self.watch.ready(b, v)
        on_v = b.owner[me] == v + 1
        if open_window or self.fails >= 2:
            # raid the victim's cells while it cannot shield (or never does)
            if on_v and not b.home[me]:
                return "STAY"
            d = b.dist(me)
            best, bs = None, 0.0
            for p in range(NC):
                if d[p] >= 99 or b.occ[p] or b.home[p] or b.owner[p] != v + 1:
                    continue
                need = 3 if b.upg[p] else 1
                if open_window and d[p] + need > self.watch.cd[v] + 1 and self.fails < 2:
                    continue
                s = (8.0 * b.base[p] * (2 if b.upg[p] else 1)) / (d[p] + need)
                if s > bs:
                    bs, best = s, p
            if best is not None and (open_window or d[best] <= 4):
                return b.step_to(best, self.rnd)
            return self.farm(b)
        # bait: stand on the victim's land -- its home if it is close -- then leave
        if on_v and just_moved:
            for nm, w in NB[me]:
                if not b.occ[w] and b.owner[w] != v + 1:
                    self.pending = True
                    return nm
            return "STAY"
        vh = b.homes[v]
        spot = vh if (vh is not None and manh(me, vh) <= 3 and not b.occ[vh]) else None
        if spot is None:
            d = b.dist(me)
            cands = [p for p in range(NC) if b.owner[p] == v + 1 and not b.occ[p]
                     and d[p] <= 4]
            if not cands:
                return self.farm(b)
            spot = min(cands, key=lambda p: d[p])
        return b.step_to(spot, self.rnd)


class Jackal(Outsider):
    name = "x_jackal"

    def act(self, view):
        b = Board(view)
        self.watch.update(b)
        legal = view.legal_actions
        if self.timed_shield(b, legal):
            return "SHIELD"
        if "SHIELD" in legal and b.rivals_on_my_land() and self.rnd.random() < 0.3:
            return "SHIELD"
        me, seat, R = b.me, b.seat, self.R()
        inc = [0] * 4
        for p in range(NC):
            if b.owner[p]:
                inc[b.owner[p] - 1] += b.base[p] * (2 if b.upg[p] else 1)
        leader = max((j for j in range(4) if j != seat - 1), key=lambda j: inc[j])
        o = b.owner[me]
        if o and o != seat and not b.home[me] and not b.upg[me]:
            return "STAY"
        d = b.dist(me)
        best, bs = None, 0.0
        for p in range(NC):
            op = b.owner[p]
            if d[p] >= 99 or b.occ[p] or b.home[p] or not op or op == seat or b.upg[p]:
                continue
            s = (8.0 * b.base[p] + b.base[p] * max(0, R - d[p] - 1)) / (d[p] + 1)
            if op - 1 == leader:
                s *= 1.5
            if not self.watch.ready(b, op - 1):
                s *= 2.0
            lp = b.pos[op - 1]
            if lp is not None and manh(lp, p) <= 1:
                s *= 0.5
            if s > bs:
                bs, best = s, p
        if o == 0 and not b.home[me]:
            return "STAY"
        claim = 0.0
        for p in range(NC):
            if d[p] < 99 and not b.occ[p] and not b.home[p] and b.owner[p] == 0:
                claim = max(claim, b.base[p] * max(0, R - d[p] - 1) / float(d[p] + 1))
        if best is not None and d[best] <= 6 and bs >= claim:
            return b.step_to(best, self.rnd)
        if claim > 0.0:
            return self.farm(b)
        lp = b.pos[leader]
        if lp is not None and manh(me, lp) > 2:
            return b.step_to(lp, self.rnd)
        return self.farm(b)


class Vulture(Outsider):
    name = "x_vulture"

    def act(self, view):
        b = Board(view)
        self.watch.update(b)
        if self.timed_shield(b, view.legal_actions):
            return "SHIELD"
        if self.t <= 58:
            return self.farm(b)
        me, seat, R = b.me, b.seat, self.R()
        o = b.owner[me]
        if o and o != seat and not b.home[me]:
            return "STAY"
        d = b.dist(me)
        best, bs = None, 0.0
        for p in range(NC):
            op = b.owner[p]
            if d[p] >= 99 or b.occ[p] or b.home[p] or not op or op == seat:
                continue
            lvl = 2 if b.upg[p] else 1
            need = 3 if b.upg[p] else 1
            if d[p] + need > R:
                continue
            s = (8.0 * b.base[p] * lvl + b.base[p] * (R - d[p] - need)) / (d[p] + need)
            if not self.watch.ready(b, op - 1):
                s *= 1.5
            if s > bs:
                bs, best = s, p
        if best is not None:
            return b.step_to(best, self.rnd)
        return self.farm(b)


class Flaky(Outsider):
    name = "x_flaky"

    def __init__(self, seed=0):
        Outsider.__init__(self, seed)
        self.dead_at = self.rnd.randint(20, 80) if self.rnd.random() < 0.3 else 999

    def act(self, view):
        if self.t >= self.dead_at:
            return "STAY"                           # crashed for good
        x = self.rnd.random()
        if x < 0.20:
            return "STAY"                           # timed out
        if x < 0.25:
            return "north"                          # illegal string -> STAY
        b = Board(view)
        if "SHIELD" in view.legal_actions and b.rivals_on_my_land():
            return "SHIELD"
        return self.farm(b, upgrade_min=2)


class Literal(Outsider):
    name = "x_literal"

    def act(self, view):
        b = Board(view)
        me, seat, R = b.me, b.seat, self.R()
        if "SHIELD" in view.legal_actions:
            for _j, p in b.rivals_on_my_land():
                if not b.home[p]:
                    return "SHIELD"
        o = b.owner[me]
        if o != seat and not b.home[me]:
            return "STAY"
        if o == seat and not b.upg[me] and b.base[me] == 3 and R > 3:
            return "STAY"
        d = b.dist(me)
        best, bs = None, 0.0
        for p in range(NC):
            op = b.owner[p]
            if d[p] >= 99 or b.occ[p] or b.home[p] or op == seat:
                continue
            need = 3 if (op and b.upg[p]) else 1
            rem = max(0, R - d[p] - need)
            val = b.base[p] * rem
            if op:
                val += 8 * b.base[p] * (2 if b.upg[p] else 1)
            s = val / float(d[p] + need)
            if s > bs:
                bs, best = s, p
        return b.step_to(best, self.rnd)


class Sim(Outsider):
    """Rollout planner on top of a rules simulator (engine.py stands in for the
    server). Hidden state it cannot see -- other bots' progress -- is set to 0."""
    name = "x_sim"
    ROLLOUTS = 2
    DEPTH = 6

    def __init__(self, seed=0):
        Outsider.__init__(self, seed)
        self.myprog = 0
        self.last_pos = None
        self.token = None

    @staticmethod
    def _policy(g, i, rnd):
        if g.frozen[i] > 0:
            return "STAY"
        p = g.pos[i]
        seat = i + 1
        o = g.owner[p]
        if (o != seat and not g.home[p]) or (o == seat and not g.upg[p] and g.base[p] >= 2):
            return "STAY"
        best, bs = None, -1.0
        pr, pc = divmod(p, N)
        for q in range(NC):
            if g.owner[q] == seat or g.home[q]:
                continue
            qr, qc = divmod(q, N)
            dd = abs(pr - qr) + abs(pc - qc)
            s = g.base[q] / (dd + 1.0) + rnd.random() * 0.3
            if s > bs:
                bs, best = s, q
        if best is None:
            return "STAY"
        br, bc = divmod(best, N)
        opts = []
        if br < pr:
            opts.append("NORTH")
        if br > pr:
            opts.append("SOUTH")
        if bc < pc:
            opts.append("WEST")
        if bc > pc:
            opts.append("EAST")
        return rnd.choice(opts) if opts else "STAY"

    def act(self, view):
        import engine
        b = Board(view)
        self.watch.update(b)
        me, seat = b.me, b.seat
        self.myprog = self.myprog + 1 if me == self.last_pos else 0
        self.last_pos = me
        if view.is_priority_token:
            self.token = seat
        elif self.token is not None:
            self.token = self.token % 4 + 1
        legal = list(view.legal_actions)
        if len(legal) == 1:
            return legal[0]
        g = engine.Game(base=b.base, start_token=self.token or 1)
        g.owner = b.owner[:]
        g.upg = [1 if u else 0 for u in b.upg]
        g.home = [b.owner[p] if b.home[p] else 0 for p in range(NC)]
        g.pos = [b.pos[j] if b.pos[j] is not None else 0 for j in range(4)]
        g.frozen = [1 if (b.pos[j] is not None and b.frz[b.pos[j]]) else 0 for j in range(4)]
        g.cd = self.watch.cd[:]
        g.cd[seat - 1] = 0 if "SHIELD" in legal else 1
        g.prog = [0] * 4
        o = b.owner[me]
        if o == seat and not b.upg[me]:
            g.prog[seat - 1] = min(2, self.myprog)
        g.income = [0] * 4
        for p in range(NC):
            if b.owner[p]:
                g.income[b.owner[p] - 1] += b.base[p] * (2 if b.upg[p] else 1)
        g.turn = self.t
        cands = [a for a in legal if a != "SHIELD"]
        if "SHIELD" in legal and b.rivals_on_my_land():
            cands.append("SHIELD")
        rem_after = max(0, 80 - self.t - self.DEPTH)
        best, bv = "STAY", -1e18
        for a in cands:
            tot = 0.0
            for _k in range(self.ROLLOUTS):
                gg = g.clone()
                for step in range(min(self.DEPTH, 81 - self.t)):
                    acts = [self._policy(gg, i, self.rnd) for i in range(4)]
                    if step == 0:
                        acts[seat - 1] = a
                    gg.step(acts)
                tot += gg.score[seat - 1] + gg.income[seat - 1] * rem_after
            v = tot / self.ROLLOUTS + self.rnd.random() * 1e-6
            if v > bv:
                bv, best = v, a
        return best


ALL = (Fort, Leech, HomeBait, Jackal, Vulture, Flaky, Literal, Sim)
REGISTRY = dict((c.name, c) for c in ALL)
