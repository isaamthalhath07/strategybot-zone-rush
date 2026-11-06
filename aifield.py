"""
The field, assuming every other team also used an agentic AI.

zoo.py holds archetypes I invented to have *something* to measure against. This
file is different: each bot here is a serious attempt at the strongest design a
well-prompted assistant would actually arrive at from the rulebook, including the
two rule facts my original zoo ignored entirely:

  * a rival's LEVEL-1 cell needs only ONE stay and still pays the 8 x v x 1 raid
    bonus, so cheap raids strictly dominate claiming an equal neutral cell;
  * a HOME cell can be upgraded and can never be captured, so an upgraded home is
    the only risk-free doubling on the board.

Every bot here keeps per-turn memory (the organisers confirmed that is legal) and
several reconstruct rival shield cooldowns, because that is the single most
valuable hidden quantity in the game.
"""
import random

from botlib import (N, NC, MOVES, NEIGH, CORNERS, parse, bfs, first_step, man,
                    zone_of, rivals_on_my_land)

MAX_TURNS = 80
DIST = []
for _a in range(NC):
    DIST.append(bfs(_a))


class AIBase(object):
    """Shared scaffolding: turn count, rival cooldown model, safe dispatch."""
    name = "aibase"

    shield_floor = 22.0                   # points of threat worth burning a shield

    def __init__(self, seed=0):
        self.rnd = random.Random(seed)
        self.turn = 0
        self.cd = [0, 0, 0, 0]            # my model of each seat's shield cooldown
        self.prev_frozen = [0, 0, 0, 0]
        self.prev_owner = None
        self.squat = {}                   # cell -> [rival seat, stays completed]
        self.last = None
        self.goal = None

    def __call__(self, view):
        self.turn += 1
        try:
            a = self.act(view)
        except Exception:
            a = "STAY"
        if a not in view.legal_actions:
            a = "STAY"
        self.last = a
        return a

    # -- plumbing ------------------------------------------------------------
    def read(self, view):
        self.base, self.owner, self.upg, self.home, self.occ, self.frz = parse(view)
        self.seat = view.bot_id
        try:
            self.me = self.occ.index(self.seat)
        except ValueError:
            self.me = None
            return None
        self.blocked = set(p for p in range(NC) if self.occ[p] and p != self.me)
        self.R = max(1, MAX_TURNS - self.turn + 1)
        self._update_cd()
        return self.me

    def _update_cd(self):
        """Infer who shielded last turn, then age every cooldown by one."""
        for i in range(4):
            if self.cd[i] > 0:
                self.cd[i] -= 1
        pos = [None] * 4
        for p in range(NC):
            o = self.occ[p]
            if o:
                pos[o - 1] = p
        newly = []
        for i in range(4):
            f = 1 if (pos[i] is not None and self.frz[pos[i]]) else 0
            if f and not self.prev_frozen[i]:
                newly.append(i)
            self.prev_frozen[i] = f
        # a bot that just froze while standing on seat s's land means s shielded
        for i in newly:
            if pos[i] is None:
                continue
            land = self.owner[pos[i]]
            if land and land != i + 1:
                self.cd[land - 1] = 4
            else:
                self.cd[i] = 4              # backfired on its own shield
        if self.last == "SHIELD":
            self.cd[self.seat - 1] = 4
        self.prev_owner = list(self.owner)
        # how long each rival has been sitting on one of my cells. Arriving does
        # not count, so a rival first seen on my cell has completed zero stays.
        sq = {}
        for p in range(NC):
            o = self.occ[p]
            if not o or o == self.seat or self.owner[p] != self.seat:
                continue
            was = self.squat.get(p)
            if was is not None and was[0] == o:
                sq[p] = [o, was[1] + (0 if self.frz[p] else 1)]
            else:
                sq[p] = [o, 0]
        self.squat = sq

    def step_to(self, target):
        if target == self.me:
            return "STAY"
        a = first_step(self.me, target, self.blocked)
        if a is None:
            a = first_step(self.me, target)
        return a or "STAY"

    def need_of(self, p):
        """Stays required to convert cell p, or None if it is not work."""
        o = self.owner[p]
        if o == self.seat:
            return None if self.upg[p] else 3
        if o == 0:
            return 1
        if self.home[p]:
            return None
        return 3 if self.upg[p] else 1

    def value_of(self, p, d, need):
        """Points of final score from doing the work on p, travel d away."""
        v = self.base[p]
        rem = self.R - d - need
        if rem < 0:
            return None
        o = self.owner[p]
        if o == self.seat:
            return v * rem                              # upgrade: +v per turn
        if o == 0:
            return v * rem if rem > 0 else None         # claim
        lvl = 2 if self.upg[p] else 1
        return 8.0 * v * lvl + v * rem                   # raid bonus is one-off

    def threat(self):
        """Points at risk from rivals that complete a capture at the END of this
        turn if I do nothing. A rival needs `need` stays and arriving is not one,
        so it is imminent only once it has already banked need - 1 of them."""
        worst = 0.0
        for p, o in rivals_on_my_land(self.owner, self.occ, self.frz, self.seat):
            lvl = 2 if self.upg[p] else 1
            need = 3 if lvl == 2 else 1
            done = self.squat.get(p, [0, -1])
            if done[0] != o or done[1] < need - 1:
                continue
            v = self.base[p]
            w = v * lvl * self.R + 8.0 * v * lvl
            if w > worst:
                worst = w
        return worst

    def defend(self, view):
        """Shield only when the loss this turn outweighs a turn plus 4 of cover.

        Shielding on sight is the trap: it burns the cooldown, backfires whenever
        the rival was only passing through, and is exactly what a baiting opponent
        farms. So the threat has to clear a floor first.
        """
        if "SHIELD" not in view.legal_actions:
            return None
        if self.threat() >= self.shield_floor:
            return "SHIELD"
        return None

    # -- target selection ----------------------------------------------------
    commit_ratio = 1.25                   # how much better a rival target must be

    def bias(self, p, g, d, need):
        """Per-bot taste. Returns the multiplier on cell p's raw value."""
        return 1.0

    def choose(self):
        """Best work-cell by points per action-turn, with commitment.

        Commitment is the part that is easy to leave out and expensive to leave
        out: without it the rate denominator shifts as the bot closes in, a new
        cell takes the lead, and the bot paces between the two for the whole game
        without ever banking a single stay.
        """
        d = bfs(self.me, self.blocked)
        best, bestr = None, 0.0
        keepr = 0.0
        for p in range(NC):
            need = self.need_of(p)
            if need is None:
                continue
            dp = d[p] if d[p] < 99 else DIST[self.me][p]
            if dp >= 99:
                continue
            g = self.value_of(p, dp, need)
            if g is None or g <= 0:
                continue
            g *= self.bias(p, g, dp, need)
            if self.occ[p] and p != self.me:
                g *= 0.25                      # a squatter may never leave
            rate = g / float(dp + need)
            if p == self.goal:
                keepr = rate
            if rate > bestr:
                bestr, best = rate, p
        if self.goal is not None and keepr > 0.0 and keepr * self.commit_ratio >= bestr:
            best = self.goal
        self.goal = best
        return best

    def run(self, view):
        if self.read(view) is None:
            return "STAY"
        dfd = self.defend(view)
        if dfd:
            return dfd
        t = self.choose()
        if t is None:
            return "STAY"
        return "STAY" if t == self.me else self.step_to(t)

    def act(self, view):
        return self.run(view)


class MarginalBot(AIBase):
    """
    Textbook marginal value: rank every piece of work by points per action-turn,
    where a cell is worth base x turns-remaining and a raid adds its one-off
    bonus. This is the design a careful assistant lands on from the rulebook
    alone, and it is a genuinely strong baseline.
    """
    name = "ai_marginal"


class CheapRaiderBot(AIBase):
    """
    Lives off the rule that a rival's LEVEL-1 cell costs one stay and still pays
    8 x v x 1. Strictly prefers victims whose shield it believes is on cooldown,
    because then the raid cannot be answered at all.
    """
    name = "ai_cheapraid"

    def bias(self, p, g, d, need):
        o = self.owner[p]
        if not o or o == self.seat:
            return 1.0
        m = 1.9 if self.cd[o - 1] >= d + need else 0.7
        if not self.upg[p]:
            m *= 1.25                          # one stay, full bonus
        return m


class HomeFortBot(AIBase):
    """
    Upgrades its home first -- the only doubling on the board that can never be
    raided, since homes cannot be captured -- then grows an upgraded cluster
    outward from it. Very low variance, which in a pairwise-Elo format is worth
    more than it looks.
    """
    name = "ai_homefort"
    shield_floor = 16.0

    def bias(self, p, g, d, need):
        home = CORNERS[self.seat - 1]
        m = 1.0 / (1.0 + 0.16 * man(p, home))
        if self.owner[p] == self.seat:
            m *= 1.5                           # consolidate rather than sprawl
        return m

    def act(self, view):
        if self.read(view) is None:
            return "STAY"
        dfd = self.defend(view)
        if dfd:
            return dfd
        home = CORNERS[self.seat - 1]
        if not self.upg[home] and self.R > 12 and DIST[self.me][home] + 3 < self.R:
            self.goal = home
            return "STAY" if self.me == home else self.step_to(home)
        t = self.choose()
        if t is None:
            return "STAY"
        return "STAY" if t == self.me else self.step_to(t)


class CentreLockBot(AIBase):
    """
    Takes the four 3-point centre cells early and upgrades them. The centre is
    equidistant from all four homes, so holding it earns the most and denies the
    most at the same time.
    """
    name = "ai_centre"
    CENTRE = (27, 28, 35, 36)
    commit_ratio = 2.0

    def bias(self, p, g, d, need):
        cd = min(man(p, c) for c in self.CENTRE)
        return 1.0 / (1.0 + 0.22 * cd)


class RouteBot(AIBase):
    """
    Plans a short ROUTE instead of a single target: chains the next three
    work-cells, paying the real travel between them, and commits to the first.
    Pricing travel is the main thing a rate-ranking bot gets wrong, so this is
    the strongest simple design -- provided it commits, which is the whole
    difficulty.
    """
    name = "ai_route"

    def _route(self, start, used, depth, taken):
        if depth == 0:
            return 0.0, None
        bestg, bestfirst = 0.0, None
        dd = DIST[start]
        cands = []
        for p in range(NC):
            if p in taken:
                continue
            need = self.need_of(p)
            if need is None:
                continue
            dp = dd[p]
            if dp >= 99 or used + dp + need > self.R:
                continue
            g = self.value_of(p, used + dp, need)
            if g is None or g <= 0:
                continue
            if self.occ[p] and p != start:
                g *= 0.25
            cands.append((g / float(dp + need + 1), p, g, dp, need))
        cands.sort(reverse=True)
        for _, p, g, dp, need in cands[:5]:
            taken.add(p)
            sub, _f = self._route(p, used + dp + need, depth - 1, taken)
            taken.discard(p)
            tot = g + sub
            if tot > bestg:
                bestg, bestfirst = tot, p
        return bestg, bestfirst

    def act(self, view):
        if self.read(view) is None:
            return "STAY"
        dfd = self.defend(view)
        if dfd:
            return dfd
        g = self.goal
        if g is not None and self.need_of(g) is not None and DIST[self.me][g] + self.need_of(g) <= self.R:
            # hold it. Abandoning a half-finished target is how a planner ends up
            # pacing: every step changes the rate denominator and flips the lead.
            return "STAY" if g == self.me else self.step_to(g)
        _free, first = self._route(self.me, 0, 3, set())
        if first is None:
            first = self.choose()
        if first is None:
            return "STAY"
        self.goal = first
        return "STAY" if first == self.me else self.step_to(first)


class CooldownHawkBot(AIBase):
    """
    Farms neutral ground until a rival burns its shield, then swarms that rival
    for the four turns it cannot defend. Shields only when the arithmetic is
    clearly in favour, so it is hard to bait.
    """
    name = "ai_hawk"

    def bias(self, p, g, d, need):
        o = self.owner[p]
        if not o or o == self.seat:
            return 1.0
        if self.cd[o - 1] >= d + need:
            return 2.4                         # defenceless for the whole raid
        return 0.55


class EloEndgameBot(AIBase):
    """
    Round 1 scores each game as three one-on-one results, so what matters is how
    many rivals you finish above, not by how much. This bot farms normally, then
    in the last stretch spends its actions only on the pairings it can still
    flip -- attacking the rival just above it and ignoring the one out of reach.
    """
    name = "ai_elo"

    def __init__(self, seed=0):
        AIBase.__init__(self, seed)
        self.score = [0, 0, 0, 0]
        self.care = [1.0] * 4

    def bias(self, p, g, d, need):
        o = self.owner[p]
        if o and o != self.seat:
            return self.care[o - 1]
        return 1.0

    def act(self, view):
        if self.read(view) is None:
            return "STAY"
        inc = [0] * 4
        for p in range(NC):
            o = self.owner[p]
            if o:
                inc[o - 1] += self.base[p] * (2 if self.upg[p] else 1)
        for i in range(4):
            self.score[i] += inc[i]
        proj = [self.score[i] + inc[i] * self.R for i in range(4)]
        mine = proj[self.seat - 1]
        self.care = [1.0] * 4
        if self.R <= 18:
            for j in range(4):
                if j == self.seat - 1:
                    continue
                gap = proj[j] - mine
                self.care[j] = 2.5 if -8 * self.R < gap < 8 * self.R else 0.25
        dfd = self.defend(view)
        if dfd:
            return dfd
        t = self.choose()
        if t is None:
            return "STAY"
        return "STAY" if t == self.me else self.step_to(t)


AIFIELD = [MarginalBot, CheapRaiderBot, HomeFortBot, CentreLockBot, RouteBot,
           CooldownHawkBot, EloEndgameBot]
AIFIELD_BY_NAME = dict((c.name, c) for c in AIFIELD)
