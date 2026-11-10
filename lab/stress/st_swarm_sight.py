"""Stress opponent for Zone Rush: one competent economy, configurable Shield and raid habits.

Written from the rulebook only, after the candidate was frozen in design, to probe the
assumptions an adaptive bot is most likely to lean on: when landlords shield, whether
raiders stay on the decisive turn, and how often un-upgraded land gets raided. Each
generated copy differs only in CONFIG. Standard library only; public inputs only.
"""
import random

CONFIG = {'name': 'swarm_sight', 'shield': 'sight', 'raid': 'l1', 'w_raid': 2.5, 'w_upgrade': 0.6, 'seed': 14}

ADJ = []
for _p in range(64):
    _r, _c = divmod(_p, 8)
    ADJ.append(tuple((a, q) for a, q, ok in (("NORTH", _p - 8, _r > 0), ("EAST", _p + 1, _c < 7),
                                             ("SOUTH", _p + 8, _r < 7), ("WEST", _p - 1, _c > 0)) if ok))


class Bot(object):
    def __init__(self, seat):
        self.seat = seat
        self.rng = random.Random(CONFIG["seed"] * 7919 + seat * 101)
        self.turn = 0
        self.prev_pos = {}
        self.prev_frozen = {}
        self.prev_owner = None
        self.banked = {}            # rival -> stays banked on my land
        self.prog = 0               # my own banked stays on the current cell
        self.last = None
        self.last_cell = None
        self.sh_turn = {}           # seat -> last turn it is known to have cast SHIELD
        self.grudge = {}
        self.failed = set()
        self.target = None
        self.feinted = None         # (cell, turn) of my last sidestep

    def act(self, state):
        self.turn += 1
        turn = self.turn
        me = self.seat
        cells = [c for row in state.board for c in row] if len(state.board) == 8 else list(state.board)
        legal = list(state.legal_actions)
        pos, frozen = {}, {}
        for p, c in enumerate(cells):
            if c.occupant:
                pos[c.occupant] = p
                frozen[c.occupant] = bool(c.is_frozen)
        at = pos[me]
        owner = [c.owner for c in cells]
        upg = [bool(c.is_upgraded) for c in cells]
        base = [c.base_points for c in cells]
        home = [bool(c.is_home) for c in cells]

        # ---- memory: who shielded (a new freeze is a catch on someone's land or a backfire)
        for r, p in pos.items():
            if frozen.get(r) and not self.prev_frozen.get(r):
                land = self.prev_owner[p] if self.prev_owner else owner[p]
                if land and land != r and self.prev_pos.get(r) == p:
                    self.sh_turn[land] = turn - 1
                else:
                    self.sh_turn[r] = turn - 1
        if self.prev_owner:
            for p in range(64):
                if self.prev_owner[p] == me and owner[p] not in (0, me):
                    self.grudge[owner[p]] = self.grudge.get(owner[p], 0) + 1
        for r, p in pos.items():
            if r == me:
                continue
            if owner[p] == me and not home[p]:
                if self.prev_pos.get(r) == p and not frozen.get(r) and not self.prev_frozen.get(r):
                    self.banked[r] = self.banked.get(r, 0) + 1
                else:
                    self.banked[r] = 0
            else:
                self.banked.pop(r, None)
        # ---- my own progress
        if self.last == "STAY" and self.last_cell == at and not frozen.get(me) \
                and self.prev_owner and self.prev_owner[at] == owner[at]:
            self.prog += 1
            if self.prog >= 4:
                self.failed.add(at)      # work that never completes (protected, or not allowed)
                self.prog = 0
        else:
            self.prog = 0

        action = self.choose(turn, me, at, pos, frozen, owner, upg, base, home, legal)
        if action not in legal:
            action = "STAY"
        self.last, self.last_cell = action, at
        self.prev_pos, self.prev_frozen, self.prev_owner = dict(pos), dict(frozen), list(owner)
        return action

    def can_shield(self, r, turn):
        return turn - self.sh_turn.get(r, -99) > 4

    def choose(self, turn, me, at, pos, frozen, owner, upg, base, home, legal):
        if len(legal) <= 1:
            return legal[0] if legal else "STAY"
        cfg = CONFIG
        # ---- Shield
        if "SHIELD" in legal and cfg["shield"] != "never":
            decisive = early = sight = False
            for r, p in pos.items():
                if r == me or frozen.get(r) or owner[p] != me or home[p]:
                    continue
                sight = True
                b = self.banked.get(r, 0)
                if not upg[p] or b >= 2:
                    decisive = True
                if not upg[p] or b >= 1:
                    early = True
            mode = cfg["shield"]
            if (mode == "sight" and sight) or (mode == "decisive" and decisive) or (mode == "early" and early) \
                    or (mode == "coin" and decisive and self.rng.random() < 0.5) \
                    or (mode == "mix" and (decisive or early) and self.rng.random() < 0.6):
                return "SHIELD"
        # ---- travel distances around occupied cells
        occupied = set(p for r, p in pos.items() if r != me)
        dist = {at: 0}
        first = {at: None}
        frontier = []
        for a, q in ADJ[at]:
            if a in legal and q not in occupied:
                dist[q], first[q] = 1, a
                frontier.append(q)
        while frontier:
            nxt = []
            for h in frontier:
                for _, q in ADJ[h]:
                    if q not in dist and q not in occupied:
                        dist[q], first[q] = dist[h] + 1, first[h]
                        nxt.append(q)
            frontier = nxt
        raid = cfg["raid"]
        best, best_rate = None, 0.0
        for c, d in dist.items():
            if c in self.failed:
                continue
            o = owner[c]
            done = self.prog if c == at else 0
            options = []
            if o == 0:
                options.append((1, base[c], 1.0, 0))
                options.append((4, base[c], 1.0, base[c]))        # claim and upgrade in one visit
            elif o == me:
                if not upg[c]:
                    options.append((max(1, 3 - done), base[c], cfg["w_upgrade"], 0))
            elif not home[c] and raid != "never":
                if raid == "endgame" and turn < 58:
                    continue
                if raid == "grudge" and not self.grudge.get(o):
                    continue
                if raid == "cooldown" and self.can_shield(o, turn + d) and not frozen.get(o):
                    continue
                if raid == "l1" and upg[c]:
                    continue
                if upg[c]:
                    options.append((max(1, 3 - done), base[c], 0.55 * cfg["w_raid"], 16 * base[c]))
                else:
                    options.append((1, base[c], 0.8 * cfg["w_raid"], 8 * base[c]))
            for work, income, weight, bonus in options:
                rem = 82 - turn - d - work
                if rem <= 0:
                    continue
                gain = income * rem + bonus
                if work == 4:
                    gain = income * (82 - turn - d - 1) + bonus * (82 - turn - d - 4)
                    if 82 - turn - d - 4 <= 0:
                        continue
                rate = weight * gain / float(d + work)
                if c == self.target:
                    rate *= 1.1
                rate *= 1.0 + 0.02 * self.rng.random()
                if rate > best_rate:
                    best, best_rate = c, rate
        self.target = best
        if best is None:
            return "STAY"
        if best != at:
            return first[best] or "STAY"
        # ---- standing on the job: a feinting raider steps off on the decisive turn, once
        o = owner[at]
        if raid == "feint" and o not in (0, me) and upg[at] and self.prog == 2 \
                and self.can_shield(o, turn) and not frozen.get(o) \
                and (self.feinted is None or self.feinted[0] != at or turn - self.feinted[1] > 8):
            steps = [(owner[q] not in (0, me), self.rng.random(), a) for a, q in ADJ[at]
                     if a in legal and q not in occupied]
            if steps:
                self.feinted = (at, turn)
                return min(steps)[2]
        return "STAY"


_BOTS = {}


def act(state):
    seat = state.bot_id
    bot = _BOTS.get(seat)
    if bot is None or bot.turn >= 80:
        bot = _BOTS[seat] = Bot(seat)
    return bot.act(state)
