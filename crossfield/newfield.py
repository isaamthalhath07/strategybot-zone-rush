"""
A second, independently written opponent field.

Everything in zoo.py and holdout.py was written alongside the bot, so it shares the
bot's assumptions. These agents were written afterwards from the rules alone, each
in a different style another team (or another AI model) might plausibly ship, and
several are deliberately stronger than anything in the original zoo.

They see only what the real server exposes: board, bot_id, is_priority_token and
legal_actions. Each instance plays one game.
"""
import random

from botlib import MOVES, NC, NEIGH, bfs, parse, zone_of

MAX_TURNS = 80

DIST = [bfs(s) for s in range(NC)]
STEP = {}
for _p in range(NC):
    for _name, _d in MOVES:
        _q = _p + _d
        if _q in NEIGH[_p]:
            STEP[(_p, _q)] = _name
DELTA = dict(MOVES)


class Agent(object):
    """Shared bookkeeping every agent below builds on: turn, consecutive stays,
    freezes, shield cooldowns, a score estimate, and my own take/upgrade progress."""
    name = "agent"

    def __init__(self, seed=0):
        self.rnd = random.Random(seed)
        self.turn = 0
        self.pos = None
        self.still = [0] * 4
        self.cd = [0] * 4
        self.frozen = [False] * 4
        self.score = [0] * 4
        self.prev_owner = None
        self.prev_upg = None
        self.myprog = 0
        self.last = None
        self.baits = [0] * 4
        self.commits = [0] * 4

    def __call__(self, view):
        try:
            self.observe(view)
            if len(view.legal_actions) == 1:
                a = view.legal_actions[0]
            else:
                a = self.act(view)
        except Exception:
            a = "STAY"
        if a not in view.legal_actions:
            a = "STAY"
        self.last = a
        return a

    def act(self, view):
        return "STAY"

    # ------------------------------------------------------------ bookkeeping
    def observe(self, view):
        base, owner, upg, home, occ, frz = parse(view)
        self.base, self.owner, self.upg, self.home, self.occ = base, owner, upg, home, occ
        self.seat = seat = view.bot_id
        self.legal = view.legal_actions
        pos = [None] * 4
        for p in range(NC):
            if occ[p]:
                pos[occ[p] - 1] = p
        frozen = [pos[i] is not None and bool(frz[pos[i]]) for i in range(4)]
        self.turn += 1
        self.R = max(1, MAX_TURNS - self.turn + 1)
        if self.pos is not None:
            po = self.prev_owner
            for i in range(4):
                if pos[i] == self.pos[i] and not frozen[i] and not self.frozen[i]:
                    self.still[i] += 1
                else:
                    self.still[i] = 0
            # every shield is visible: it freezes either its victims or itself
            sh = set()
            for i in range(4):
                if frozen[i] and not self.frozen[i]:
                    pp = self.pos[i]
                    o = po[pp] if pp is not None else 0
                    sh.add(o - 1 if (o and o != i + 1 and pos[i] == pp) else i)
            for s in range(4):
                if s in sh:
                    self.cd[s] = 4
                elif self.cd[s] > 0:
                    self.cd[s] -= 1
            # raider behaviour on rival land: commit or walk away?
            for i in range(4):
                pp = self.pos[i]
                if pp is None or self.frozen[i]:
                    continue
                o = po[pp]
                if o and o != i + 1 and not home[pp]:
                    if pos[i] == pp:
                        self.commits[i] += 1
                    else:
                        self.baits[i] += 1
            for p in range(NC):
                a, b = po[p], owner[p]
                if a and b and a != b and not home[p]:
                    self.score[b - 1] += 8 * base[p] * (2 if self.prev_upg[p] else 1)
            for p in range(NC):
                if owner[p]:
                    self.score[owner[p] - 1] += base[p] * (2 if upg[p] else 1)
            me, mp = pos[seat - 1], self.pos[seat - 1]
            if (me != mp or self.last != "STAY" or frozen[seat - 1]
                    or self.frozen[seat - 1]
                    or owner[me] != po[me] or upg[me] != self.prev_upg[me]):
                self.myprog = 0
            else:
                self.myprog += 1
        self.pos = pos
        self.frozen = frozen
        self.prev_owner = owner[:]
        self.prev_upg = upg[:]
        self.me = pos[seat - 1]
        self.blocked = set(p for p in range(NC) if occ[p] and p != self.me)

    # -------------------------------------------------------------- economics
    def need(self, p):
        """Stays needed to finish the work available on p (0 = nothing to do)."""
        o = self.owner[p]
        if o == self.seat:
            return 0 if self.upg[p] else 3
        if o == 0:
            return 1
        if self.home[p]:
            return 0
        return 3 if self.upg[p] else 1

    def gain(self, p, cost, denial=0.0):
        """Points from finishing the work on p after `cost` turns."""
        pay = self.R - cost + 1
        if pay <= 0:
            return 0.0
        o = self.owner[p]
        v = self.base[p]
        if o == self.seat or o == 0:
            return float(v * pay)
        lvl = 2 if self.upg[p] else 1
        return 8.0 * v * lvl + v * pay + denial * v * lvl * pay

    def intruders(self):
        """(cell, seat index, stays left before they take it) for rivals on my land."""
        out = []
        for i in range(4):
            if i == self.seat - 1:
                continue
            p = self.pos[i]
            if p is None or self.frozen[i] or self.owner[p] != self.seat or self.home[p]:
                continue
            need = 3 if self.upg[p] else 1
            out.append((p, i, need - self.still[i]))
        return out

    def shield_imminent(self, minval=2, bait_guard=False):
        if "SHIELD" not in self.legal:
            return False
        for p, i, left in self.intruders():
            if left > 1:
                continue
            if not (self.upg[p] or self.base[p] >= minval):
                continue
            if bait_guard:
                b, c = self.baits[i], self.commits[i]
                if b + c >= 3 and b > 2 * c and self.rnd.random() < 0.75:
                    continue
            return True
        return False

    def dist_from_me(self):
        return bfs(self.me, self.blocked)

    def step_to(self, target):
        me = self.me
        if target is None or target == me:
            return "STAY"
        d = bfs(target, self.blocked)
        if d[me] >= 99:
            d = DIST[target]
        opts = [w for w in NEIGH[me] if w not in self.blocked and d[w] == d[me] - 1]
        if not opts:
            return "STAY"
        # among equal routes, prefer walking over cells that still need claiming
        opts.sort(key=lambda w: (self.owner[w] != 0, w))
        return STEP[(me, opts[0])]

    def rate_target(self, raids=True, risk=0.4, denial=0.0, commit=1.15,
                    maxd=99, zone_w=1.0):
        """Best cell by points-per-turn, pricing travel and stays."""
        d = self.dist_from_me()
        best, br = None, 0.0
        for p in range(NC):
            dp = d[p]
            if dp >= 99 or dp > maxd:
                continue
            nd = self.need(p)
            if nd == 0:
                continue
            o = self.owner[p]
            raid = o and o != self.seat
            if raid and not raids:
                continue
            if p == self.me:
                nd = max(1, nd - self.myprog)
            cost = dp + nd
            if cost > self.R:
                continue
            g = self.gain(p, cost, denial)
            if raid and not (self.frozen[o - 1] or self.cd[o - 1] >= cost):
                g *= 1.0 - risk
            if zone_w != 1.0 and zone_of(p) == self.seat:
                g *= zone_w
            r = g / cost
            if p == self.me:
                r *= commit
            if r > br:
                br, best = r, p
        return best


class RateGreedy(Agent):
    """Points-per-turn greedy over every claim, upgrade and raid, with shields on
    imminent takes. The most likely shape of a competent single-file LLM bot."""
    name = "rate"

    def act(self, view):
        if self.shield_imminent():
            return "SHIELD"
        return self.step_to(self.rate_target())


class RouteFarmer(Agent):
    """Claims and upgrades the good cells in one visit, works outward through its
    quadrant, refuses to be baited, and raids only near the end."""
    name = "route"

    def act(self, view):
        if self.shield_imminent(bait_guard=True):
            return "SHIELD"
        me, seat = self.me, self.seat
        o = self.owner[me]
        if o == 0 and self.R >= 1:
            return "STAY"
        if o == seat and not self.upg[me] and self.base[me] >= 2 \
                and self.R > 3 - self.myprog + 2:
            return "STAY"
        if o and o != seat and not self.home[me] and self.R >= 1:
            return "STAY"
        if self.R <= 14:
            t = self.rate_target(raids=True, risk=0.3, maxd=3)
            if t is not None:
                return self.step_to(t)
        d = self.dist_from_me()
        best, bs = None, -1e9
        for p in range(NC):
            if d[p] >= 99 or self.owner[p] != 0 or d[p] + 1 > self.R:
                continue
            s = self.base[p] * 3.0 - d[p] * 2.2
            if zone_of(p) == seat:
                s += 1.5
            if s > bs:
                bs, best = s, p
        if best is not None and bs > 0:
            return self.step_to(best)
        return self.step_to(self.rate_target(raids=self.R <= 30, risk=0.4))


class Vulture(Agent):
    """Farms by rate, but pounces on any rival that is frozen or on shield
    cooldown -- the windows in which a landlord cannot defend."""
    name = "vulture"

    def act(self, view):
        if self.shield_imminent():
            return "SHIELD"
        me, seat = self.me, self.seat
        o = self.owner[me]
        if o and o != seat and not self.home[me]:
            return "STAY"                        # finish the raid
        d = self.dist_from_me()
        best, br = None, 0.0
        for p in range(NC):
            o = self.owner[p]
            if not o or o == seat or self.home[p] or d[p] >= 99 or d[p] > 6:
                continue
            need = 3 if self.upg[p] else 1
            cost = d[p] + need
            if cost > self.R:
                continue
            safe = self.cd[o - 1] >= cost or self.frozen[o - 1]
            if not safe:
                continue
            r = self.gain(p, cost) / cost
            if r > br:
                br, best = r, p
        rt = self.rate_target(raids=False)
        if best is not None:
            if rt is None or br > 0.8 * self._rate_of(rt, d):
                return self.step_to(best)
        return self.step_to(rt)

    def _rate_of(self, p, d):
        nd = self.need(p)
        if p == self.me:
            nd = max(1, nd - self.myprog)
        c = d[p] + nd
        return self.gain(p, c) / c


class Guardian(Agent):
    """Rate farmer that physically guards its best upgraded cells when a rival is
    close -- a cell with a bot standing on it cannot be entered."""
    name = "guard"

    def act(self, view):
        if self.shield_imminent(minval=1):
            return "SHIELD"
        me, seat = self.me, self.seat
        d = self.dist_from_me()
        threat_cell, tv = None, 0.0
        for p in range(NC):
            if self.owner[p] != seat or not self.upg[p] or self.home[p] or self.base[p] < 2:
                continue
            for i in range(4):
                q = self.pos[i]
                if i == seat - 1 or q is None or self.frozen[i]:
                    continue
                dr = DIST[q][p]
                if dr <= 2 and d[p] <= dr + 1:
                    v = self.base[p] * 2 * self.R / (1 + d[p])
                    if v > tv:
                        tv, threat_cell = v, p
        if threat_cell is not None and self.R > 4:
            return self.step_to(threat_cell)
        return self.step_to(self.rate_target(risk=0.5))


class CentreGrab(Agent):
    """Sprints for the valuable middle ground first, claims and upgrades it in one
    visit, then backfills toward home."""
    name = "grab"

    def __init__(self, seed=0):
        Agent.__init__(self, seed)
        self.core = None

    def act(self, view):
        if self.shield_imminent():
            return "SHIELD"
        me, seat = self.me, self.seat
        if self.core is None:
            mine = [p for p in range(NC) if zone_of(p) == seat and not self.home[p]]
            mine.sort(key=lambda p: (-self.base[p], DIST[p][self.me] * -1))
            self.core = mine[:5]
        o = self.owner[me]
        if o == 0:
            return "STAY"
        if o == seat and not self.upg[me] and me in self.core and self.R > 4:
            return "STAY"
        if o and o != seat and not self.home[me]:
            return "STAY"
        d = self.dist_from_me()
        todo = [p for p in self.core if (self.owner[p] != seat or not self.upg[p])
                and d[p] < 99 and not (self.owner[p] and self.owner[p] != seat
                                       and self.upg[p])]
        if todo and self.turn < 45:
            todo.sort(key=lambda p: d[p] - self.base[p])
            return self.step_to(todo[0])
        return self.step_to(self.rate_target(risk=0.4))


class Harasser(Agent):
    """Farms early, then goes after whoever is leading -- preferably while the
    leader is frozen or on cooldown."""
    name = "harass"

    def act(self, view):
        if self.shield_imminent():
            return "SHIELD"
        me, seat = self.me, self.seat
        o = self.owner[me]
        if o and o != seat and not self.home[me]:
            return "STAY"
        if self.turn > 25:
            rivals = [j for j in range(4) if j != seat - 1]
            lead = max(rivals, key=lambda j: self.score[j])
            if self.score[lead] > self.score[seat - 1] - 40:
                d = self.dist_from_me()
                best, br = None, 0.0
                for p in range(NC):
                    if self.owner[p] != lead + 1 or self.home[p] or d[p] > 5:
                        continue
                    need = 3 if self.upg[p] else 1
                    cost = d[p] + need
                    if cost > self.R:
                        continue
                    g = self.gain(p, cost, denial=1.0)
                    if not (self.frozen[lead] or self.cd[lead] >= cost):
                        g *= 0.5
                    if g / cost > br:
                        br, best = g / cost, p
                if best is not None:
                    return self.step_to(best)
        return self.step_to(self.rate_target(raids=False))


class Rollout(Agent):
    """Monte-Carlo: tries each first move, plays the rest out with a randomised
    greedy policy in its own simplified model of the game, and keeps the move with
    the best average. Rival shields are sampled from a fixed risk."""
    name = "rollout"
    H = 24
    M = 5
    SHIELD_P = 0.45
    OVERHEAD = 2.0

    def act(self, view):
        if self.shield_imminent():
            return "SHIELD"
        me = self.me
        firsts = ["STAY"]
        for w in NEIGH[me]:
            if w not in self.blocked:
                firsts.append(STEP[(me, w)])
        # common random numbers: every first move faces the same rollout luck
        seeds = [self.rnd.randrange(1 << 30) for _ in range(self.M)]
        best, bv = "STAY", -1e18
        for a in firsts:
            tot = 0.0
            for sd in seeds:
                tot += self._sim(a, random.Random(sd))
            if tot > bv:
                bv, best = tot, a
        return best

    def _sim(self, first, rnd):
        seat = self.seat
        owner = self.owner[:]
        upg = self.upg[:]
        base = self.base
        blocked = self.blocked
        pos = self.me
        prog = self.myprog
        inc = 0
        for p in range(NC):
            if owner[p] == seat:
                inc += base[p] * (2 if upg[p] else 1)
        score = 0.0
        R = self.R
        H = min(self.H, R)
        frozen = 0
        target = None
        for t in range(H):
            left = R - t
            if frozen:
                frozen -= 1
                score += inc
                continue
            if t == 0:
                a = first
            else:
                if target is None or (target == pos and self._need(owner, upg, pos) == 0):
                    target = self._pick(owner, upg, pos, prog, left, rnd)
                if target is None or target == pos:
                    a = "STAY"
                else:
                    a = None
                    for w in NEIGH[pos]:
                        if w not in blocked and DIST[w][target] < DIST[pos][target]:
                            a = STEP[(pos, w)]
                            break
                    if a is None:
                        a = "STAY"
            if a != "STAY":
                q = pos + DELTA[a]
                if q not in blocked:
                    pos = q
                prog = 0
            else:
                nd = self._need(owner, upg, pos)
                if nd:
                    o = owner[pos]
                    if o and o != seat and self.cd[o - 1] == 0 \
                            and rnd.random() < self.SHIELD_P:
                        frozen = 2
                        prog = 0
                        score += inc
                        continue
                    prog += 1
                    if prog >= nd:
                        prog = 0
                        v = base[pos]
                        if o == seat:
                            upg[pos] = 1
                            inc += v
                        elif o == 0:
                            owner[pos] = seat
                            inc += v
                        else:
                            lvl = 2 if upg[pos] else 1
                            score += 8 * v * lvl
                            owner[pos] = seat
                            upg[pos] = 0
                            inc += v
                        target = None
            score += inc
        return score + inc * (R - H)

    def _need(self, owner, upg, p):
        o = owner[p]
        if o == self.seat:
            return 0 if upg[p] else 3
        if o == 0:
            return 1
        if self.home[p]:
            return 0
        return 3 if upg[p] else 1

    def _pick(self, owner, upg, pos, prog, left, rnd):
        nd = self._need(owner, upg, pos)
        if nd and max(1, nd - prog) <= left and (owner[pos] == self.seat or owner[pos] == 0):
            return pos                            # finish what I started
        cands = []
        for p in range(NC):
            if p in self.blocked:
                continue
            nd = self._need(owner, upg, p)
            if not nd:
                continue
            if p == pos:
                nd = max(1, nd - prog)
            c = DIST[pos][p] + nd
            if c > left:
                continue
            pay = left - c + 1
            o = owner[p]
            v = self.base[p]
            if o and o != self.seat:
                g = (8.0 * v * (2 if upg[p] else 1) + v * pay) * (1.0 - self.SHIELD_P)
            else:
                g = float(v * pay)
            cands.append((g / (c + self.OVERHEAD), p))
        if not cands:
            return None
        cands.sort(reverse=True)
        k = min(3, len(cands))
        x = rnd.random()
        return cands[0][1] if x < 0.6 or k == 1 else cands[1 + int(rnd.random() * (k - 1))][1]


class Sequencer(Agent):
    """Exhaustive three-deep search over the best ten jobs: which ORDER of claims,
    upgrades and raids pays most by the end of the game? Refuses to be baited."""
    name = "seq"
    K = 10
    DEPTH = 3
    RISK = 0.45

    def act(self, view):
        if self.shield_imminent(bait_guard=True):
            return "SHIELD"
        d = self.dist_from_me()
        R = self.R
        jobs = []
        for p in range(NC):
            if d[p] >= 99:
                continue
            nd = self.need(p)
            if not nd:
                continue
            if p == self.me:
                nd = max(1, nd - self.myprog)
            c = d[p] + nd
            if c > R:
                continue
            o = self.owner[p]
            risk = 0.0
            if o and o != self.seat and not (self.frozen[o - 1] or self.cd[o - 1] >= c):
                risk = self.RISK
            jobs.append((self.gain(p, c) * (1.0 - risk) / c, p, nd, risk))
        if not jobs:
            return "STAY"
        jobs.sort(reverse=True)
        jobs = jobs[:self.K]
        rest = jobs[len(jobs) // 2][0]          # what a turn is worth afterwards
        best = [None, -1e18]
        base, upg, owner, seat = self.base, self.upg, self.owner, self.seat

        def dfs(pos, t, mask, val, depth, first):
            done = True
            if depth < self.DEPTH:
                for k in range(len(jobs)):
                    if (mask >> k) & 1:
                        continue
                    _, p, nd, risk = jobs[k]
                    if p != self.me:
                        nd = self.need(p)
                    c = t + (DIST[pos][p] if pos != p else 0) + nd
                    if c > R:
                        continue
                    pay = R - c + 1
                    v = base[p]
                    o = owner[p]
                    if o and o != seat:
                        g = (8.0 * v * (2 if upg[p] else 1) + v * pay) * (1.0 - risk)                             - risk * 2.0 * rest
                    else:
                        g = float(v * pay)
                    done = False
                    dfs(p, c, mask | (1 << k), val + g, depth + 1,
                        first if first is not None else p)
            if done:
                tot = val + rest * (R - t) * 0.5
                if tot > best[1]:
                    best[0], best[1] = first, tot

        dfs(self.me, 0, 0, 0.0, 0, None)
        return self.step_to(best[0])


NEWFIELD = [RateGreedy, RouteFarmer, Vulture, Guardian, CentreGrab, Harasser, Rollout,
            Sequencer]
NEW_BY_NAME = dict((c.name, c) for c in NEWFIELD)
