"""Procedural challengers: public inputs only, never fitted against candidates.

Generated copies replace CONFIG with a frozen per-panel draw. Shared economics
are explicit; scheduling rules differ between selection and confirmation.
"""
from collections import deque
import math
import random

CONFIG = {'seed': 537595573, 'family': 'cooldown_feint', 'claim': 0.9260447959574125, 'upgrade': 1.467852183466182, 'raid': 0.7335049429319476, 'stick': 1.132681675191566, 'power': 0.9620417483228174, 'shield': 0.9430122199647373, 'period': 13, 'phase': 1}
NEIGH = []
for p in range(64):
    r,c = divmod(p,8)
    NEIGH.append(tuple(q for q,ok in ((p-8,r>0),(p+8,r<7),(p-1,c>0),(p+1,c<7)) if ok))
DIST = [[abs(a//8-b//8)+abs(a%8-b%8) for b in range(64)] for a in range(64)]


def bfs(start,closed):
    d = [99]*64
    d[start] = 0
    q = deque([start])
    while q:
        p = q.popleft()
        for w in NEIGH[p]:
            if w not in closed and d[w] > d[p]+1:
                d[w] = d[p]+1
                q.append(w)
    return d


class Player:
    def __init__(self,seat):
        self.seat = seat
        self.rng = random.Random(CONFIG["seed"]+seat*7919)
        self.turn = 0
        self.previous = None
        self.last = None
        self.progress = [0]*4
        self.cooldown = [0]*4
        self.scores = [0]*4
        self.target = None
        self.bundle = None

    def __call__(self,state):
        self.turn += 1
        cells = [c for row in state.board for c in row]
        self.base = [c.base_points for c in cells]
        self.owner = [c.owner for c in cells]
        self.upg = [bool(c.is_upgraded) for c in cells]
        self.home = [bool(c.is_home) for c in cells]
        self.occ = [c.occupant for c in cells]
        self.frz = [bool(c.is_frozen) for c in cells]
        self.pos = [self.occ.index(j) for j in range(1,5)]
        self.me = self.pos[self.seat-1]
        self.closed = set(self.pos)-{self.me}
        self.remaining = max(1,81-self.turn)
        self.observe()
        action = self.choose(state)
        self.previous = (self.owner[:],self.upg[:],self.pos[:],self.frz[:])
        self.last = action
        return action

    def observe(self):
        self.cooldown = [max(0,n-1) for n in self.cooldown]
        if self.previous is None:
            return
        old,up,positions,frozen = self.previous
        for j,p in enumerate(self.pos):
            before = positions[j]
            if p != before or self.frz[p] or frozen[before] or old[p] != self.owner[p] or up[p] != self.upg[p]:
                self.progress[j] = 0
            elif self.owner[p] == j+1 and not self.upg[p] or self.owner[p] not in (0,j+1) and self.upg[p]:
                if j != self.seat-1 or self.last == "STAY":
                    self.progress[j] = min(2,self.progress[j]+1)
            if self.frz[p] and not frozen[before] and old[p] in (0,j+1):
                self.cooldown[j] = 4  # an unambiguous own backfire
        if self.last == "SHIELD":
            self.cooldown[self.seat-1] = 4
            self.progress[self.seat-1] = 0
        for p,o in enumerate(self.owner):
            if o:
                self.scores[o-1] += self.base[p]*(2 if self.upg[p] else 1)
                if old[p] and old[p] != o and not self.home[p]:
                    self.scores[o-1] += 8*self.base[p]*(2 if up[p] else 1)

    def step(self,target):
        if self.me == target:
            return "STAY"
        d = bfs(target,self.closed)
        choices = [p for p in NEIGH[self.me] if p not in self.closed and d[p] < d[self.me]]
        if not choices:
            return "STAY"
        # Random tie breaking is seeded and private, not a raw-seat advantage.
        best = min(d[p] for p in choices)
        p = self.rng.choice([p for p in choices if d[p] == best])
        return {1:"EAST",-1:"WEST",8:"SOUTH",-8:"NORTH"}[p-self.me]

    def jobs(self):
        d = bfs(self.me,self.closed)
        out = []
        for p in range(64):
            if d[p] >= 99 or p in self.closed or self.home[p] and self.owner[p] != self.seat:
                continue
            o = self.owner[p]
            if o == self.seat and self.upg[p]:
                continue
            need = 3 if o == self.seat or o and self.upg[p] else 1
            if p == self.me:
                need = max(1,need-self.progress[self.seat-1])
            cost = d[p]+need
            if cost > self.remaining:
                continue
            weight = CONFIG["upgrade"] if o == self.seat else CONFIG["claim"] if not o else CONFIG["raid"]
            gain = self.base[p]*(self.remaining-cost+1)*weight
            if o not in (0,self.seat):
                gain += 8*self.base[p]*(2 if self.upg[p] else 1)*CONFIG["raid"]
                if self.cooldown[o-1] < cost:
                    gain *= 0.30
            out.append((p,gain,cost,d[p],need))
        return out

    def choose(self,state):
        if len(state.legal_actions)==1:
            return state.legal_actions[0]
        intruders = [(p,j) for j,p in enumerate(self.pos) if j != self.seat-1 and
                     self.owner[p] == self.seat and not self.frz[p] and not self.home[p]]
        imminent = [(p,j) for p,j in intruders if (3 if self.upg[p] else 1)-self.progress[j] <= 1]
        if imminent and not self.cooldown[self.seat-1] and "SHIELD" in state.legal_actions and self.rng.random() < CONFIG["shield"]:
            return "SHIELD"
        family = CONFIG["family"]
        if family == "cooldown_feint":
            landlord = self.owner[self.me]
            if landlord not in (0,self.seat) and not self.cooldown[landlord-1]:
                candidates = [p for p in NEIGH[self.me] if p not in self.closed]
                if candidates:
                    best = max(candidates,key=lambda p:(self.owner[p] == landlord,self.base[p],not self.upg[p]))
                    return self.step(best)
        if self.bundle is not None:
            p = self.bundle
            if self.owner[p] == self.seat and not self.upg[p] and self.me == p:
                return "STAY"
            if self.owner[p] == self.seat and self.upg[p]:
                self.bundle = None
        jobs = self.jobs()
        if not jobs:
            return "STAY"
        scores = {}
        owned = sum(o == self.seat for o in self.owner)
        upgraded = sum(o == self.seat and u for o,u in zip(self.owner,self.upg))
        income = [sum(self.base[p]*(2 if self.upg[p] else 1) for p,o in enumerate(self.owner) if o == j) for j in range(1,5)]
        projected = [s+self.remaining*i for s,i in zip(self.scores,income)]
        leader = max(range(4),key=lambda j:projected[j])+1
        for p,g,c,d,n in jobs:
            o = self.owner[p]
            row,col = divmod(p,8)
            depth = min(row,col,7-row,7-col)
            near = sum(self.base[q] for q in NEIGH[p] if not self.owner[q])
            rival = min(DIST[q][p] for j,q in enumerate(self.pos) if j != self.seat-1)
            value = g/(c**CONFIG["power"])
            if family == "district_rate":
                value *= 1+near/18
            elif family == "time_discount":
                value = g*math.exp(-0.12*c)
            elif family == "turn_budget":
                invest = upgraded < max(1,owned*0.5)
                value *= 1.5 if (o == self.seat) == invest else 0.85
            elif family == "return_schedule":
                if not o and d+4 <= self.remaining:
                    value = (g+self.base[p]*(self.remaining-d-3)*CONFIG["upgrade"])/(d+4)
            elif family == "capture_deadline":
                if not o:
                    value *= 1+0.8/max(1,rival-d+2)
            elif family == "sector_bids":
                region = [q for q in range(64) if abs(q//8-row)<=1 and abs(q%8-col)<=1]
                free = sum(self.base[q] for q in region if not self.owner[q])
                traffic = sum(DIST[q][p] <= 3 for j,q in enumerate(self.pos) if j != self.seat-1)
                value *= (1+free/12)/(1+0.25*traffic)
            elif family == "chase_income":
                if o == leader and o != self.seat:
                    value *= 1.8
            elif family == "boundary_cluster":
                value *= 1+0.15*sum(self.owner[q] not in (0,self.seat) for q in NEIGH[p])
            elif family == "periodic_switch":
                inward = (self.turn//CONFIG["period"]+CONFIG["phase"]) % 2
                value *= math.exp((0.3 if inward else -0.3)*depth)
            scores[p] = value
        if family == "local_pairs":
            top = sorted(jobs,key=lambda j:scores[j[0]],reverse=True)[:8]
            for p,g,c,d,n in top:
                continuation = max((h*max(0,self.remaining-c-DIST[p][q]-qn+1)/max(1,self.remaining-qd-qn+1)
                                    for q,h,qc,qd,qn in top if p != q and c+DIST[p][q]+qn <= min(18,self.remaining)),default=0)
                scores[p] = (g+0.5*continuation)/(c+1)
        best = max(scores,key=scores.get)
        if family == "sampling_portfolio":
            top = sorted(scores,key=scores.get,reverse=True)[:3]
            weights = [math.exp((scores[p]-scores[top[0]])/max(1,0.12*scores[top[0]])) for p in top]
            best = self.rng.choices(top,weights)[0]
        if self.target in scores and scores[self.target]*CONFIG["stick"] >= scores[best]:
            best = self.target
        self.target = best
        if family == "return_schedule" and not self.owner[best]:
            self.bundle = best
        return self.step(best)


_AGENTS = {}


def act(state):
    seat = state.bot_id
    player = _AGENTS.get(seat)
    if player is None:
        player = Player(seat)
        _AGENTS[seat] = player
    return player(state)
