"""
A strong opponent that is NOT my architecture.

Every serious opponent measured so far has been either a hand-written archetype I
invented or a frozen snapshot of my own bot. Snapshots share my planner and
therefore my blind spots, so beating them proves less than it looks. The brief
was to assume every other team also used an agentic assistant, and the honest way
to model that is a bot built on a different principle and then tuned just as hard.

So this is a RATE RANKER, not a route planner: it scores every piece of work on
the board by points per action-turn and commits to the best. That is the design a
careful assistant arrives at from the rulebook, and unopposed it already outscores
my own bot (3545 against 3276) because it is not paying for defensive habits. Its
weakness is the opposite one: it prices no risk, so it walks into shields.

Its weights are tunable (tune_rival.py), which is the point -- an untuned rival
is not a fair test of a tuned bot.

The economics it encodes, straight from the rulebook:
  * a neutral cell costs 1 stay and pays base x turns-remaining;
  * a rival's LEVEL-1 cell also costs 1 stay and additionally pays 8 x base;
  * a rival's upgraded cell costs 3 stays and pays 8 x base x 2;
  * your own cell costs 3 stays to double;
  * a raid bonus is one-off, so it does not decay with the clock the way income
    does -- which makes raiding worth far more late than early.
"""
import random

from botlib import NC, NEIGH, CORNERS, parse, bfs, first_step, man

MAX_TURNS = 80
DIST = [bfs(_a) for _a in range(NC)]
CENTRE = (27, 28, 35, 36)

WEIGHTS = {
    "w_claim": 1.00,
    "w_upgrade": 1.00,
    "w_raid": 1.00,
    "w_raid_late": 1.00,      # raid weight at the final turn, interpolated by clock
    "bonus_mult": 1.00,       # trust in the one-off raid bonus
    "compact": 0.00,          # penalty per step away from my own home
    "centre": 0.00,           # pull toward the four 3-point centre cells
    "cd_bonus": 1.00,         # multiplier when the victim's shield is on cooldown
    "cd_malus": 1.00,         # multiplier when it is not
    "squat": 0.25,            # a rival is standing on it and may never leave
    "commit": 1.25,           # how much better a new target must look
    "shield_floor": 22.0,     # points of imminent loss worth a shield
    "shield_scale": 0.00,     # how much that floor grows with turns remaining
    "upg_pref": 1.00,         # extra weight on upgrading a cell I already hold
    "home_pref": 1.00,        # extra weight on my own home, which cannot be taken
}


class ProBot(object):
    name = "pro"

    def __init__(self, seed=0, params=None):
        self.W = dict(WEIGHTS)
        if params:
            self.W.update(params)
        self.rnd = random.Random(seed)
        self.turn = 0
        self.cd = [0, 0, 0, 0]
        self.prev_frozen = [0, 0, 0, 0]
        self.squat = {}
        self.goal = None
        self.last = None

    # ------------------------------------------------------------------ entry
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

    # --------------------------------------------------------------- plumbing
    def read(self, view):
        self.base, self.owner, self.upg, self.home, self.occ, self.frz = parse(view)
        self.seat = view.bot_id
        try:
            self.me = self.occ.index(self.seat)
        except ValueError:
            return None
        self.blocked = set(p for p in range(NC) if self.occ[p] and p != self.me)
        self.R = max(1, MAX_TURNS - self.turn + 1)
        self._memory()
        return self.me

    def _memory(self):
        """Rival shield cooldowns and how long each squatter has held its ground.

        Neither is in the state object. A bot that freezes while standing on seat
        s's land was caught by s shielding, which also tells me s cannot shield
        again for four turns -- the most valuable hidden fact in the game.
        """
        for i in range(4):
            if self.cd[i] > 0:
                self.cd[i] -= 1
        pos = [None] * 4
        for p in range(NC):
            o = self.occ[p]
            if o:
                pos[o - 1] = p
        for i in range(4):
            f = 1 if (pos[i] is not None and self.frz[pos[i]]) else 0
            if f and not self.prev_frozen[i] and pos[i] is not None:
                land = self.owner[pos[i]]
                self.cd[(land - 1) if (land and land != i + 1) else i] = 4
            self.prev_frozen[i] = f
        if self.last == "SHIELD":
            self.cd[self.seat - 1] = 4
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

    def step_to(self, t):
        if t == self.me:
            return "STAY"
        a = first_step(self.me, t, self.blocked) or first_step(self.me, t)
        return a or "STAY"

    # ---------------------------------------------------------------- economy
    def need_of(self, p):
        o = self.owner[p]
        if o == self.seat:
            return None if self.upg[p] else 3
        if o == 0:
            return 1
        if self.home[p]:
            return None                        # homes can never be taken
        return 3 if self.upg[p] else 1

    def gain(self, p, d, need):
        W = self.W
        v = self.base[p]
        rem = self.R - d - need
        o = self.owner[p]
        if o == self.seat:
            if rem <= 0:
                return None
            g = v * rem * W["w_upgrade"] * W["upg_pref"]
            if self.home[p]:
                g *= W["home_pref"]
            return g
        if o == 0:
            if rem <= 0:
                return None
            return v * rem * W["w_claim"]
        if rem < 0:
            return None
        lvl = 2 if self.upg[p] else 1
        g = 8.0 * v * lvl * W["bonus_mult"] + v * rem
        # the bonus is one-off, so raiding is worth most when income has no time
        # left to pay anything back
        f = 1.0 - self.R / float(MAX_TURNS)
        g *= W["w_raid"] + (W["w_raid_late"] - W["w_raid"]) * max(0.0, min(1.0, f))
        g *= W["cd_bonus"] if self.cd[o - 1] >= d + need else W["cd_malus"]
        return g

    def threat(self):
        """Points lost at the end of this turn if I do not shield now."""
        worst = 0.0
        for p in range(NC):
            o = self.occ[p]
            if not o or o == self.seat or self.owner[p] != self.seat or self.frz[p]:
                continue
            lvl = 2 if self.upg[p] else 1
            need = 3 if lvl == 2 else 1
            w = self.squat.get(p, [0, -1])
            if w[0] != o or w[1] < need - 1:
                continue                       # arriving is not a stay
            v = self.base[p]
            x = v * lvl * self.R + 8.0 * v * lvl
            if x > worst:
                worst = x
        return worst

    # ----------------------------------------------------------------- policy
    def act(self, view):
        if self.read(view) is None:
            return "STAY"
        W = self.W
        if "SHIELD" in view.legal_actions:
            floor = W["shield_floor"] * (1.0 + W["shield_scale"] * self.R / 80.0)
            if self.threat() >= floor:
                return "SHIELD"
        home = CORNERS[self.seat - 1]
        d = bfs(self.me, self.blocked)
        best, bestr, keepr = None, 0.0, 0.0
        for p in range(NC):
            need = self.need_of(p)
            if need is None:
                continue
            dp = d[p] if d[p] < 99 else DIST[self.me][p]
            if dp >= 99:
                continue
            g = self.gain(p, dp, need)
            if g is None or g <= 0:
                continue
            if W["compact"]:
                g /= 1.0 + W["compact"] * man(p, home)
            if W["centre"]:
                g /= 1.0 + W["centre"] * min(man(p, c) for c in CENTRE)
            if self.occ[p] and p != self.me:
                g *= W["squat"]
            rate = g / float(dp + need)
            if p == self.goal:
                keepr = rate
            if rate > bestr:
                bestr, best = rate, p
        if self.goal is not None and keepr > 0.0 and keepr * W["commit"] >= bestr:
            best = self.goal
        if best is None:
            return "STAY"
        self.goal = best
        return "STAY" if best == self.me else self.step_to(best)


def factory(params=None, name="pro"):
    def make(seed):
        b = ProBot(seed=seed, params=params)
        b.name = name
        return b
    return make
