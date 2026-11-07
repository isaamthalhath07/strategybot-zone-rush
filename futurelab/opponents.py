"""Fresh opponent schedulers for forward-planning experiments.

No old zoo, policy snapshot, or earlier scheduling family is used. Public
parsing/bookkeeping is shared, and is explicitly not independent authorship.
"""
import math
import random

from botlib import NEIGH, first_step, man
from freshlab.population import ProceduralOpponent, specification


SPLITS = {
    "discovery": ("budget_cycle", "scarcity_bid", "moving_window", "persistent_bundle"),
    "development": ("path_exchange", "tempo_raider", "threshold_pivot"),
    "final": ("phase_response", "income_deadline", "weighted_tour", "opportunity_sampler"),
}


def sample(split, seed):
    rng = random.Random("future-opponent:%s:%d" % (split,seed))
    s = specification("train",seed)
    s.update(family=rng.choice(SPLITS[split]), cycle=rng.randrange(5,13),
             target_owned=rng.randrange(5,12), radius=rng.randrange(2,6),
             budget=rng.uniform(0.25,0.70), discount=rng.uniform(0.03,0.12),
             phase=rng.randrange(4), pivot=rng.randrange(18,45))
    return s


class FutureOpponent(ProceduralOpponent):
    def __init__(self,spec):
        super().__init__(spec)
        self.finish = None
        self.waypoints = None

    def choose(self,state):
        if len(state.legal_actions) == 1:
            return state.legal_actions[0]
        if self.shield(state):
            return "SHIELD"
        if self.finish == self.me and self.owner[self.me] == self.seat and not self.upg[self.me]:
            return "STAY"
        jobs = self.jobs()
        if not jobs:
            return "STAY"
        s, family = self.spec,self.spec["family"]
        rates = {}
        owned = sum(o == self.seat for o in self.owner)
        upgrades = sum(o == self.seat and u for o,u in zip(self.owner,self.upg))
        for p,g,c,d,n in jobs:
            value = g/c
            mine, neutral = self.owner[p] == self.seat,self.owner[p] == 0
            near = sum(self.base[q] for q in NEIGH[p] if not self.owner[q])
            if family == "budget_cycle":
                investing = (self.turn//s["cycle"]+s["phase"]) % 2 == 1
                value *= 1.6 if mine == investing else 0.8
            elif family == "scarcity_bid":
                rival = min(man(q,p) for j,q in enumerate(self.pos) if j != self.seat-1)
                deadline = max(1,rival-d+2)
                value *= 1+0.8/deadline if neutral else 1
            elif family == "moving_window":
                region = (self.turn//s["cycle"]+s["phase"]) % 4
                row,col = divmod(p,8)
                quadrant = (row>=4)*2+(col>=4)
                value *= 1.6 if quadrant == region else 0.9
            elif family == "persistent_bundle":
                if neutral and d+4 <= self.R:
                    value = (g+self.base[p]*(self.R-d-3)*s["upgrade"])/(d+4)
                value *= 1+near/18
            elif family == "path_exchange":
                continuation = max((h*math.exp(-s["discount"]*(man(p,q)+qn))/(1+man(p,q))
                                    for q,h,qc,qd,qn in jobs if q != p),default=0)
                value = (g+0.35*continuation)/(c+1)
            elif family == "tempo_raider":
                offensive = (self.turn+s["phase"]) % s["cycle"] < 3
                value *= 2.0 if self.owner[p] not in (0,self.seat) and offensive else 1
            elif family == "threshold_pivot":
                expanding = owned < s["target_owned"] and self.turn < s["pivot"]
                value *= 1.7 if neutral == expanding else 0.8
            elif family == "phase_response":
                traffic = sum(man(q,p) <= 2 for j,q in enumerate(self.pos) if j != self.seat-1)
                # Reacts to the population instead of a fixed time or region.
                value *= (1+near/12)/(1+0.5*traffic) if upgrades < owned*s["budget"] else (1.4 if not mine else 0.8)
            elif family == "income_deadline":
                # Compare doing this job now with delaying it behind another.
                loss = self.base[p]*min(c,6)
                rival = min(man(q,p) for j,q in enumerate(self.pos) if j != self.seat-1)
                value = g/(c**0.8)+loss*(1+max(0,d-rival))*0.2
            elif family == "weighted_tour":
                if self.waypoints is None:
                    self.waypoints = sorted(range(64),key=lambda q:(-self.base[q],man(self.homes[self.seat],q),q))
                order = self.waypoints.index(p)
                value *= 1+1/(1+order/8)
            rates[p] = value
        if family == "opportunity_sampler":
            top = sorted(rates,key=rates.get,reverse=True)[:4]
            weights = [math.exp((rates[p]-rates[top[0]])/max(1,0.12*rates[top[0]])) for p in top]
            best = self.rng.choices(top,weights)[0]
        else:
            best = max(rates,key=rates.get)
        if self.target in rates and rates[self.target]*s["commit"] >= rates[best]:
            best = self.target
        self.target = best
        if family == "persistent_bundle" and not self.owner[best]:
            self.finish = best
        return "STAY" if best == self.me else first_step(self.me,best,self.closed) or "STAY"
