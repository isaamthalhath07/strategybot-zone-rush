"""Procedural opponents with held-out scheduling algorithms, never old snapshots.

Only public observations enter these policies. Parameters are sampled afresh
for each game, not optimised against the submission. Split membership is by
decision algorithm as well as seed; shared plumbing is explicitly not an
independent codebase. Never infer how actual competitors play from these bots.
"""
import math
import random

from botlib import NEIGH, bfs, first_step, man, parse


SPLITS = {
    "train": ("rate", "cluster", "sweep", "switch", "risk", "bounty"),
    "development": ("lookahead", "regime", "pressure"),
    "final": ("auction", "denier", "trickster"),
}


def specification(split, seed):
    """Stable, reconstructable style; no result-dependent rejection/sampling."""
    rng = random.Random("fresh-style:%s:%d" % (split, seed))
    family = rng.choice(SPLITS[split])
    return dict(seed=seed, family=family,
                claim=math.exp(rng.uniform(-0.35, 0.35)),
                upgrade=math.exp(rng.uniform(-0.25, 0.65)),
                raid=math.exp(rng.uniform(-1.35, 0.30)),
                commit=rng.uniform(1.05, 1.65), radius=rng.choice((4, 5, 7, 10)),
                shelter=rng.uniform(0.0, 0.22), travel=rng.uniform(0.75, 1.25),
                shield=rng.choice(("never", "imminent", "imminent", "value",
                                   "always", "mixed", "delayed")),
                shield_p=rng.uniform(0.2, 0.9), threshold=rng.uniform(10, 75),
                raider=rng.choice(("patient", "patient", "flee", "feint", "cooldown")),
                switch_turn=rng.randint(24, 58), temperature=rng.uniform(0.0, 0.08))


class ProceduralOpponent:
    """Several planning principles over common public-state parsing/rules."""

    def __init__(self, spec):
        self.spec = dict(spec)
        self.rng = random.Random(spec["seed"])
        self.turn = 0
        self.prev = None
        self.progress = [0] * 4
        self.cd = [0] * 4
        self.target = None
        self.scores = [0] * 4
        self.calls = 0
        self.moves = 0

    def __call__(self, state):
        # Do not swallow failures: the experiment must surface broken opponents.
        self.turn += 1
        self.calls += 1
        self.base, self.owner, self.upg, self.home, self.occ, self.frozen = parse(state)
        self.seat = state.bot_id
        self.me = self.occ.index(self.seat)
        self.pos = [self.occ.index(j) if j in self.occ else None for j in range(1, 5)]
        self.homes = {self.owner[p]: p for p in range(64) if self.home[p]}
        self.closed = {p for p in range(64) if self.occ[p] and p != self.me}
        self.R = 81 - self.turn
        self.observe()
        action = self.choose(state)
        if action not in state.legal_actions:
            raise AssertionError("procedural opponent returned illegal %r" % action)
        self.prev = (self.owner[:], self.upg[:], self.pos[:], self.frozen[:], action)
        self.moves += action in ("NORTH", "SOUTH", "EAST", "WEST")
        return action

    def observe(self):
        old = self.prev
        self.cd = [max(0, c - 1) for c in self.cd]
        if old is None:
            return
        own, up, pos, frz, last = old
        for j, p in enumerate(self.pos):
            pp = pos[j]
            if pp is None or p is None:
                continue
            if self.frozen[p] and not frz[pp]:
                landlord = own[pp]
                shielder = landlord - 1 if landlord and landlord != j + 1 else j
                self.cd[shielder] = 4
            if p != pp or self.frozen[p] or frz[pp] or (j == self.seat - 1 and last == "SHIELD"):
                self.progress[j] = 0
            elif own[p] != self.owner[p] or up[p] != self.upg[p]:
                self.progress[j] = 0
            else:
                self.progress[j] = min(2, self.progress[j] + 1)
        for p in range(64):
            o = self.owner[p]
            if o:
                self.scores[o - 1] += self.base[p] * (2 if self.upg[p] else 1)
                if own[p] and own[p] != o and not self.home[p]:
                    self.scores[o - 1] += 8 * self.base[p] * (2 if up[p] else 1)
        if last == "SHIELD":
            self.cd[self.seat - 1] = 4

    def need(self, p):
        o = self.owner[p]
        if self.home[p] and o != self.seat:
            return None
        if o == self.seat:
            n = None if self.upg[p] else 3
        else:
            n = 3 if o and self.upg[p] else 1
        if n is not None and p == self.me:
            n = max(1, n - self.progress[self.seat - 1])
        return n

    def shield(self, state):
        if "SHIELD" not in state.legal_actions:
            return False
        eligible = [(p, o - 1) for p, o in enumerate(self.occ)
                    if o and o != self.seat and self.owner[p] == self.seat
                    and not self.frozen[p] and not self.home[p]]
        if not eligible:
            return False
        style = self.spec["shield"]
        if self.spec["family"] == "regime" and self.turn > self.spec["switch_turn"]:
            style = "mixed" if style == "never" else "imminent"
        if style == "never":
            return False
        imminent = [(p, j) for p, j in eligible
                    if (3 if self.upg[p] else 1) - self.progress[j] <= 1]
        if style == "always":
            return True
        if not imminent:
            return False
        if style == "mixed":
            return self.rng.random() < self.spec["shield_p"]
        if style == "delayed":
            return self.turn % 3 != 0
        if style == "value":
            return sum(self.base[p] * ((2 if self.upg[p] else 1) * self.R + 8)
                       for p, j in imminent) >= self.spec["threshold"]
        return True

    def jobs(self):
        d = bfs(self.me, self.closed)
        jobs = []
        s = self.spec
        home = self.homes[self.seat]
        for p in range(64):
            n = self.need(p)
            if n is None or d[p] + n > self.R or d[p] >= 99:
                continue
            if self.occ[p] and p != self.me:
                continue
            o, v, travel = self.owner[p], self.base[p], d[p]
            rem = self.R - travel - n + 1
            if o == self.seat:
                gain = v * rem * s["upgrade"]
            elif not o:
                gain = v * rem * s["claim"]
            else:
                gain = (v * rem + 8 * v * (2 if self.upg[p] else 1)) * s["raid"]
                if self.cd[o - 1] <= travel + n - 1:
                    gain *= 0.15 if s["family"] == "risk" else 0.55
            gain /= 1 + s["shelter"] * man(home, p)
            cost = travel * s["travel"] + n
            jobs.append((p, gain, cost, travel, n))
        return jobs

    def choose(self, state):
        if len(state.legal_actions) == 1:
            return state.legal_actions[0]
        if self.shield(state):
            return "SHIELD"
        o = self.owner[self.me]
        if o and o != self.seat and not self.home[self.me]:
            safe = self.cd[o - 1] > 0
            style = self.spec["raider"]
            if (style in ("flee", "feint") and not safe) or (style == "cooldown" and not safe):
                exits = [p for p in NEIGH[self.me] if p not in self.closed
                         and self.owner[p] != o]
                if exits:
                    return first_step(self.me, self.rng.choice(exits), self.closed) or "STAY"
        jobs = self.jobs()
        if not jobs:
            return "STAY"
        family, s = self.spec["family"], self.spec
        rates = {}
        for p, g, c, d, n in jobs:
            score = g / max(1, c)
            if family == "sweep":
                score *= 1.5 if man(p, self.homes[self.seat]) <= s["radius"] else 0.65
            elif family == "cluster":
                score *= 1 + 0.10 * sum(self.owner[q] == self.seat for q in NEIGH[p])
            elif family in ("switch", "regime"):
                expand = self.turn < s["switch_turn"]
                score *= 1.4 if (self.owner[p] == 0) == expand else 0.85
            elif family == "bounty":
                score *= 1.6 if self.owner[p] not in (0, self.seat) and self.R < 25 else 1.0
            elif family == "pressure":
                score *= 1.5 if self.owner[p] not in (0, self.seat) else 0.9
            elif family == "denier":
                if self.owner[p] not in (0, self.seat):
                    score *= 1.4 + 0.6 * (self.scores[self.owner[p] - 1] > self.scores[self.seat - 1])
            elif family == "trickster":
                # Changes offensive style as well as economic priorities midgame.
                score *= 1.5 if self.owner[p] not in (0, self.seat) and self.turn % 12 < 6 else 1.0
            rates[p] = score
        if family in ("lookahead", "auction"):
            # Different scheduling objectives reserved for development / final.
            top = sorted(jobs, key=lambda j: rates[j[0]], reverse=True)[:8]
            for p, g, c, d, n in top:
                continuations = []
                for q, h, qc, qd, qn in jobs:
                    if q == p:
                        continue
                    reach = man(p, q) + qn
                    if c + reach > self.R:
                        continue
                    h = h * max(0, self.R - c - reach + 1) / max(1, self.R - qd - qn + 1)
                    continuations.append((h, reach))
                if continuations:
                    h, reach = max(continuations, key=lambda a: a[0] / a[1])
                    rates[p] = (g + h) / (c + reach) if family == "lookahead" else (g + 0.65 * h) / (c ** 0.8 + reach ** 0.8)
        best = max(rates, key=rates.get)
        if self.target in rates and rates[self.target] * s["commit"] >= rates[best]:
            best = self.target
        self.target = best
        if best == self.me:
            return "STAY"
        return first_step(self.me, best, self.closed) or "STAY"


def make(split, seed):
    return ProceduralOpponent(specification(split, seed))
