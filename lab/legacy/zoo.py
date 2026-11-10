"""
Opponent archetypes.

These are the field. GreedyValue / GreedyShield are my best guess at what an LLM
writes unprompted from the rulebook; the rest are the plausible deliberate designs.
Each class is instantiated once per seat per game, so instance state is per-game.
"""
import random
from botlib import (N, NC, MOVES, NEIGH, CORNERS, parse, bfs, first_step, man,
                    zone_of, rivals_on_my_land)


class Base(object):
    name = "base"

    def __init__(self, seed=0):
        self.rnd = random.Random(seed)
        self.turn = 0

    def __call__(self, view):
        self.turn += 1
        try:
            a = self.act(view)
        except Exception:
            a = "STAY"
        if a not in view.legal_actions:
            a = "STAY"
        return a

    def act(self, view):
        return "STAY"

    # -- shared utilities ----------------------------------------------------
    def read(self, view):
        self.base, self.owner, self.upg, self.home, self.occ, self.frz = parse(view)
        self.seat = view.bot_id
        self.me = self.occ.index(self.seat)
        self.blocked = set(p for p in range(NC) if self.occ[p] and p != self.me)
        return self.me

    def step_to(self, target):
        a = first_step(self.me, target, self.blocked)
        if a is None:
            a = first_step(self.me, target)          # ignore blockers if boxed in
        return a or "STAY"


class StayBot(Base):
    """The unmodified skeleton. A bot that crashes plays exactly this."""
    name = "stay"


class RandomBot(Base):
    name = "random"

    def act(self, view):
        la = [a for a in view.legal_actions if a != "SHIELD"]
        if "SHIELD" in view.legal_actions and self.rnd.random() < 0.05:
            return "SHIELD"
        return self.rnd.choice(la)


class GreedyValueBot(Base):
    """
    Nearest-highest-value greedy claiming, upgrade when idle, never shields.
    My prediction for the modal unprompted-LLM bot.
    """
    name = "greedy"
    SHIELDS = False
    RAIDS = True

    def act(self, view):
        self.read(view)
        seat = self.seat
        if self.SHIELDS and "SHIELD" in view.legal_actions:
            if rivals_on_my_land(self.owner, self.occ, self.frz, seat):
                return "SHIELD"
        d = bfs(self.me, self.blocked)
        best, bestscore = None, 0.0
        for p in range(NC):
            if d[p] >= 99 or self.home[p]:
                continue
            o = self.owner[p]
            if o == seat:
                continue
            if o != 0 and not self.RAIDS:
                continue
            cost = d[p] + (3 if (o != 0 and self.upg[p]) else 1)
            s = self.base[p] / float(cost)
            if o != 0:
                s *= 1.15
            if s > bestscore:
                bestscore, best = s, p
        if best is None:
            return "STAY"
        if best == self.me:
            return "STAY"
        # already standing on something worth finishing?
        o = self.owner[self.me]
        if o == 0 or (o != seat and not self.home[self.me]):
            return "STAY"
        if o == seat and not self.upg[self.me] and d[best] > 1:
            return "STAY"
        return self.step_to(best)


class GreedyShieldBot(GreedyValueBot):
    """Same economics, but shields the instant a rival sets foot on its land."""
    name = "greedyshield"
    SHIELDS = True


class PacifistBot(GreedyValueBot):
    """Claims only neutral ground, never raids. Shields on sight."""
    name = "pacifist"
    SHIELDS = True
    RAIDS = False


class SpineFarmerBot(Base):
    """
    The optimal-route farmer from the economic analysis: walk the high-value
    corridor out of home claiming as you go, upgrade 3-cells on arrival, backfill
    the cheap cells last. Stays in its own quadrant. Disciplined shields.
    """
    name = "spine"

    def __init__(self, seed=0):
        Base.__init__(self, seed)
        self.route = None

    def build_route(self):
        seat = self.seat
        mine = [p for p in range(NC) if zone_of(p) == seat and not self.home[p]]
        home = CORNERS[seat - 1]
        route, cur, left = [], home, set(mine)
        while left:
            d = bfs(cur)
            best, bestscore = None, -1e9
            for p in left:
                # prefer high value, close, and far from home (perishable first)
                s = self.base[p] * 3.0 - d[p] * 2.0 + man(p, home) * 0.55
                if s > bestscore:
                    bestscore, best = s, p
            route.append(best)
            left.discard(best)
            cur = best
        self.route = route

    def act(self, view):
        self.read(view)
        seat = self.seat
        if self.route is None:
            self.build_route()
        if "SHIELD" in view.legal_actions:
            intr = rivals_on_my_land(self.owner, self.occ, self.frz, seat)
            for p, o in intr:
                if self.base[p] >= 2:
                    return "SHIELD"
        # finish what I'm standing on
        o = self.owner[self.me]
        if o == 0:
            return "STAY"
        if o == seat and not self.upg[self.me] and self.base[self.me] >= 2:
            return "STAY"
        for p in self.route:
            if self.owner[p] != seat:
                if p == self.me:
                    return "STAY"
                return self.step_to(p)
        # everything claimed: upgrade the best un-upgraded cell
        cand = [p for p in range(NC) if self.owner[p] == seat and not self.upg[p]]
        if not cand:
            return "STAY"
        d = bfs(self.me, self.blocked)
        cand.sort(key=lambda p: (-self.base[p] * 4 + d[p]))
        t = cand[0]
        return "STAY" if t == self.me else self.step_to(t)


class RaiderBot(Base):
    """Farms briefly, then raids the nearest rival level-1 cell. Shields on sight."""
    name = "raider"
    SWITCH = 24

    def act(self, view):
        self.read(view)
        seat = self.seat
        if "SHIELD" in view.legal_actions:
            if rivals_on_my_land(self.owner, self.occ, self.frz, seat):
                return "SHIELD"
        o = self.owner[self.me]
        if o == 0 or (o != seat and not self.home[self.me]):
            return "STAY"
        d = bfs(self.me, self.blocked)
        if self.turn < self.SWITCH:
            cand = [p for p in range(NC) if self.owner[p] == 0 and d[p] < 99]
            if cand:
                cand.sort(key=lambda p: -(self.base[p] * 3.0 - d[p] * 2.0))
                t = cand[0]
                return "STAY" if t == self.me else self.step_to(t)
        cand = [p for p in range(NC)
                if self.owner[p] not in (0, seat) and not self.home[p] and d[p] < 99]
        if cand:
            cand.sort(key=lambda p: -((8 * self.base[p] * (2 if self.upg[p] else 1))
                                      / float(d[p] + (3 if self.upg[p] else 1))))
            t = cand[0]
            return "STAY" if t == self.me else self.step_to(t)
        if o == seat and not self.upg[self.me]:
            return "STAY"
        return "STAY"


class CamperBot(Base):
    """Grabs the best few cells, upgrades them, then squats the best one (occupancy
    is immunity) and shields hard. The natural counter to raiders."""
    name = "camper"

    def act(self, view):
        self.read(view)
        seat = self.seat
        if "SHIELD" in view.legal_actions:
            if rivals_on_my_land(self.owner, self.occ, self.frz, seat):
                return "SHIELD"
        mine_zone = [p for p in range(NC)
                     if zone_of(p) == seat and not self.home[p]]
        mine_zone.sort(key=lambda p: -self.base[p])
        target_set = mine_zone[:8]
        o = self.owner[self.me]
        if o == 0:
            return "STAY"
        if o == seat and not self.upg[self.me] and self.me in target_set:
            return "STAY"
        for p in target_set:
            if self.owner[p] != seat:
                return "STAY" if p == self.me else self.step_to(p)
        for p in target_set:
            if not self.upg[p]:
                return "STAY" if p == self.me else self.step_to(p)
        best = max(target_set, key=lambda p: self.base[p]) if target_set else self.me
        return "STAY" if best == self.me else self.step_to(best)


class BaiterBot(Base):
    """
    Deliberately draws shields: steps onto a rival border cell, then steps off
    before the take completes, and harvests while they are frozen + on cooldown.
    Included to make sure my bot is not farmable by this.
    """
    name = "baiter"

    def __init__(self, seed=0):
        Base.__init__(self, seed)
        self.standing = 0
        self.last = -1

    def act(self, view):
        self.read(view)
        seat = self.seat
        if "SHIELD" in view.legal_actions:
            if rivals_on_my_land(self.owner, self.occ, self.frz, seat):
                return "SHIELD"
        d = bfs(self.me, self.blocked)
        o = self.owner[self.me]
        if o != 0 and o != seat and not self.home[self.me]:
            self.standing = self.standing + 1 if self.me == self.last else 1
            self.last = self.me
            # commit about a fifth of the time, otherwise bail and come back
            if self.standing >= 2 and self.rnd.random() < 0.8:
                away = [p for p in NEIGH[self.me] if p not in self.blocked]
                if away:
                    self.standing = 0
                    return self.step_to(self.rnd.choice(away))
            return "STAY"
        self.standing = 0
        if o == 0:
            return "STAY"
        cand = [p for p in range(NC)
                if self.owner[p] not in (0, seat) and not self.home[p] and d[p] < 99
                and not self.upg[p]]
        if cand:
            cand.sort(key=lambda p: -(self.base[p] * 3.0 - d[p] * 2.0))
            return self.step_to(cand[0])
        cand = [p for p in range(NC) if self.owner[p] == 0 and d[p] < 99]
        if cand:
            cand.sort(key=lambda p: -(self.base[p] * 3.0 - d[p] * 2.0))
            t = cand[0]
            return "STAY" if t == self.me else self.step_to(t)
        if self.owner[self.me] == seat and not self.upg[self.me]:
            return "STAY"
        return "STAY"


ZOO = [StayBot, RandomBot, GreedyValueBot, GreedyShieldBot, PacifistBot,
       SpineFarmerBot, RaiderBot, CamperBot, BaiterBot]
ZOO_BY_NAME = dict((c.name, c) for c in ZOO)
