"""
Held-out opponents. These are NEVER in the tuning field, so they measure whether
the tuned weights generalise or are just overfitted to the training zoo.
"""
import random

from botlib import (N, NC, NEIGH, CORNERS, parse, bfs, first_step, man,
                    zone_of, rivals_on_my_land)
from zoo import Base


class TurtleBot(Base):
    """Claims only what is near home, upgrades everything, shields by strict rule.
    Extremely low-variance; the natural 'play it safe' design."""
    name = "turtle"
    RADIUS = 4

    def act(self, view):
        self.read(view)
        seat = self.seat
        home = CORNERS[seat - 1]
        if "SHIELD" in view.legal_actions:
            for p, o in rivals_on_my_land(self.owner, self.occ, self.frz, seat):
                if self.base[p] >= 2:
                    return "SHIELD"
        near = [p for p in range(NC)
                if man(p, home) <= self.RADIUS and not self.home[p]]
        o = self.owner[self.me]
        if o == 0 and self.me in near:
            return "STAY"
        if o == seat and not self.upg[self.me]:
            return "STAY"
        d = bfs(self.me, self.blocked)
        todo = [p for p in near if self.owner[p] != seat and d[p] < 99]
        if todo:
            todo.sort(key=lambda p: -(self.base[p] * 3.0 - d[p] * 2.0))
            t = todo[0]
            return "STAY" if t == self.me else self.step_to(t)
        todo = [p for p in near if self.owner[p] == seat and not self.upg[p]
                and d[p] < 99]
        if todo:
            todo.sort(key=lambda p: -(self.base[p] * 3.0 - d[p] * 2.0))
            t = todo[0]
            return "STAY" if t == self.me else self.step_to(t)
        return "STAY"


class LeaderHunterBot(Base):
    """Farms, but always raids whoever is currently winning. Tracks scores itself."""
    name = "hunter"

    def __init__(self, seed=0):
        Base.__init__(self, seed)
        self.score = [0, 0, 0, 0]

    def act(self, view):
        self.read(view)
        seat = self.seat
        for p in range(NC):
            if self.owner[p]:
                self.score[self.owner[p] - 1] += self.base[p] * (2 if self.upg[p] else 1)
        if "SHIELD" in view.legal_actions:
            if rivals_on_my_land(self.owner, self.occ, self.frz, seat):
                return "SHIELD"
        o = self.owner[self.me]
        if o == 0 or (o != seat and not self.home[self.me]):
            return "STAY"
        d = bfs(self.me, self.blocked)
        leader = max((j for j in range(4) if j != seat - 1),
                     key=lambda j: self.score[j]) + 1
        tgt = [p for p in range(NC)
               if self.owner[p] == leader and not self.home[p] and d[p] < 99]
        if self.turn > 20 and tgt:
            tgt.sort(key=lambda p: -((8.0 * self.base[p] * (2 if self.upg[p] else 1))
                                     / (d[p] + (3 if self.upg[p] else 1))))
            t = tgt[0]
            return "STAY" if t == self.me else self.step_to(t)
        free = [p for p in range(NC) if self.owner[p] == 0 and d[p] < 99]
        if free:
            free.sort(key=lambda p: -(self.base[p] * 3.0 - d[p] * 2.0))
            t = free[0]
            return "STAY" if t == self.me else self.step_to(t)
        if o == seat and not self.upg[self.me]:
            return "STAY"
        return "STAY"


class CentreRushBot(Base):
    """Sprints for the middle four cells, holds them, upgrades them, fights there.
    The 'contest the valuable ground' design."""
    name = "centre"

    def act(self, view):
        self.read(view)
        seat = self.seat
        if "SHIELD" in view.legal_actions:
            if rivals_on_my_land(self.owner, self.occ, self.frz, seat):
                return "SHIELD"
        o = self.owner[self.me]
        if o == 0:
            return "STAY"
        if o != seat and not self.home[self.me]:
            return "STAY"
        core = sorted(range(NC), key=lambda p: (-self.base[p], man(p, CORNERS[seat - 1])))
        core = [p for p in core if not self.home[p]][:10]
        d = bfs(self.me, self.blocked)
        todo = [p for p in core if self.owner[p] != seat and d[p] < 99]
        if todo:
            todo.sort(key=lambda p: d[p])
            t = todo[0]
            return "STAY" if t == self.me else self.step_to(t)
        if o == seat and not self.upg[self.me]:
            return "STAY"
        todo = [p for p in core if self.owner[p] == seat and not self.upg[p] and d[p] < 99]
        if todo:
            todo.sort(key=lambda p: d[p])
            t = todo[0]
            return "STAY" if t == self.me else self.step_to(t)
        free = [p for p in range(NC) if self.owner[p] == 0 and d[p] < 99]
        if free:
            free.sort(key=lambda p: -(self.base[p] * 3.0 - d[p] * 2.0))
            t = free[0]
            return "STAY" if t == self.me else self.step_to(t)
        return "STAY"


class CooldownRaiderBot(Base):
    """
    The dangerous one: it tracks shield cooldowns the same way my bot does, and
    raids only inside a rival's cooldown window. This is the design I argued is
    the strongest exploit available, written by someone else.
    """
    name = "cdraider"

    def __init__(self, seed=0):
        Base.__init__(self, seed)
        self.cd = [0, 0, 0, 0]
        self.prevfrz = [0] * NC
        self.prevown = None
        self.prevpos = [None] * 4

    def act(self, view):
        self.read(view)
        seat = self.seat
        pos = [None] * 4
        for p in range(NC):
            if self.occ[p]:
                pos[self.occ[p] - 1] = p
        if self.prevown is not None:
            newly = []
            for i in range(4):
                if pos[i] is not None and self.frz[pos[i]] and self.prevpos[i] is not None \
                        and not self.prevfrz[self.prevpos[i]]:
                    newly.append(i)
            sh = set()
            for i in newly:
                pp = self.prevpos[i]
                o = self.prevown[pp]
                sh.add(o - 1 if (o and o != i + 1) else i)
            for s in range(4):
                if s in sh:
                    self.cd[s] = 4
                elif self.cd[s] > 0:
                    self.cd[s] -= 1
        self.prevown = self.owner[:]
        self.prevfrz = self.frz[:]
        self.prevpos = pos

        if "SHIELD" in view.legal_actions:
            if rivals_on_my_land(self.owner, self.occ, self.frz, seat):
                return "SHIELD"
        o = self.owner[self.me]
        if o == 0:
            return "STAY"
        if o != seat and not self.home[self.me]:
            return "STAY"
        d = bfs(self.me, self.blocked)
        # raid only where the landlord cannot answer
        safe = []
        for p in range(NC):
            ow = self.owner[p]
            if ow and ow != seat and not self.home[p] and d[p] < 99:
                need = 3 if self.upg[p] else 1
                if self.cd[ow - 1] >= d[p] + need:
                    safe.append(p)
        if safe:
            safe.sort(key=lambda p: -((8.0 * self.base[p] * (2 if self.upg[p] else 1)
                                       + self.base[p] * 10)
                                      / (d[p] + (3 if self.upg[p] else 1))))
            t = safe[0]
            return "STAY" if t == self.me else self.step_to(t)
        free = [p for p in range(NC) if self.owner[p] == 0 and d[p] < 99]
        if free:
            free.sort(key=lambda p: -(self.base[p] * 3.0 - d[p] * 2.0))
            t = free[0]
            return "STAY" if t == self.me else self.step_to(t)
        if o == seat and not self.upg[self.me]:
            return "STAY"
        cand = [p for p in range(NC) if self.owner[p] == seat and not self.upg[p]
                and d[p] < 99]
        if cand:
            cand.sort(key=lambda p: -(self.base[p] * 3.0 - d[p] * 2.0))
            t = cand[0]
            return "STAY" if t == self.me else self.step_to(t)
        return "STAY"


HOLDOUT = [TurtleBot, LeaderHunterBot, CentreRushBot, CooldownRaiderBot]
