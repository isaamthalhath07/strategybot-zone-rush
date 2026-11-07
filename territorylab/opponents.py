"""New spatial scheduling families, including lookalikes and changing goals.

Shared parsing/bookkeeping with freshlab; no old zoo, snapshot or competitor
is played. Role is metadata for the observer only, never read by our policy.
"""
import random

from botlib import first_step, man
from freshlab.population import ProceduralOpponent, specification
from territorylab.model import depth, centre_distance


SPLITS = {
    "discovery": ("express", "breadcrumb", "reserve_patch"),
    "development": ("density", "tour", "patient_launch"),
    "final": ("economic_gate", "phase_band", "decoy"),
}


def sample(split, seed, role):
    rng = random.Random("spatial:%s:%d" % (split, seed))
    spec = specification("train", seed)
    spec.update(family=rng.choice(SPLITS[split]), role=role,
                launch=rng.randrange(2, 7), pivot=rng.randrange(10, 25),
                region_weight=rng.uniform(0.8, 1.8), destination_seed=rng.randrange(2**31))
    return spec


class SpatialOpponent(ProceduralOpponent):
    def region(self, p, role):
        if role == "centre":
            return depth(p)/3.0
        if role == "rim":
            return 1-depth(p)/3.0
        return max(0, 1-man(self.homes[self.seat], p)/8.0)

    def choose(self, state):
        if len(state.legal_actions) == 1:
            return state.legal_actions[0]
        if self.shield(state):
            return "SHIELD"
        s = self.spec
        family, role = s["family"], s["role"]
        jobs = self.jobs()
        if not jobs:
            return "STAY"
        if family == "decoy" and self.turn >= s["launch"]:
            role = "rim" if role == "centre" else "centre"
        elif family == "phase_band" and self.turn >= s["pivot"]:
            role = "centre" if role != "centre" else "rim"
        regional = {p: (0.35+self.region(p, role)*s["region_weight"]) for p, g, c, d, n in jobs}
        rates = {p: g/c*regional[p] for p, g, c, d, n in jobs}
        if family in ("express", "breadcrumb", "tour", "decoy"):
            # Different openings can share the same first skipped claim. Rim
            # travellers are a deliberate counterexample to that shortcut.
            rng = random.Random(s["destination_seed"])
            goal_set = [p for p in range(64) if not self.home[p] and
                        (depth(p) == 3 if role == "centre" else
                         depth(p) == 0 and 4 <= man(self.homes[self.seat], p) <= 8
                         if role == "rim" else man(self.homes[self.seat], p) <= 2)]
            destination = rng.choice(goal_set)
            travel_phase = self.turn <= (12 if family == "tour" else 9)
            if travel_phase and self.me != destination:
                if family == "breadcrumb" and self.owner[self.me] == 0 and self.turn % 3 == 2:
                    return "STAY"
                if self.owner[self.me] == self.seat and not self.upg[self.me] and self.progress[self.seat-1]:
                    return "STAY"
                action = first_step(self.me, destination, self.closed)
                if action:
                    return action
        if family in ("reserve_patch", "patient_launch") and self.turn <= s["launch"]:
            home = self.homes[self.seat]
            if self.me == home and not self.upg[home]:
                return "STAY"
        if family == "density":
            # Pick a work cluster using total regional continuation income.
            for p, g, c, d, n in jobs:
                neighbours = [h*regional[q]/(1+man(p, q)) for q, h, qc, qd, qn in jobs if q != p and man(p, q) <= 2]
                rates[p] = (g*regional[p] + 0.25*sum(neighbours))/(c+2)
        if family == "economic_gate":
            # Value can outweigh nominal role; rushing is conditional on the map.
            rates = {p: g/c*(regional[p] if self.base[p] >= 2 else 0.75) for p, g, c, d, n in jobs}
        best = max(rates, key=rates.get)
        if self.target in rates and rates[self.target]*s["commit"] >= rates[best]:
            best = self.target
        self.target = best
        return "STAY" if best == self.me else first_step(self.me, best, self.closed) or "STAY"
