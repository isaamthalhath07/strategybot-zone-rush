"""Corrective experiments: consistent continuation and bounded overrides.

The original rollout experiment is retained unchanged for honest comparison.
Only the first work commitment is prescribed in these simulated continuations.
"""
import math
import time

from baselines import v8 as bot
from futurelab import agent,models,rollout


VARIANTS = {
    "baseline": {},
    "one_job": {"learned":True,"horizon":24,"risk":0.25},
    "committed": {"learned":True,"horizon":24,"risk":0.25,"commit":True},
    "guarded": {"learned":True,"horizon":24,"risk":0.5,"commit":True,"guard":0.95},
    "prior_guarded": {"learned":False,"horizon":24,"risk":0.5,"commit":True,"guard":0.95},
}


def proxy(player,route,owner,upg,base,occ,seat,R,kappa,care):
    pos = player.tr.pos[seat-1]
    elapsed,value = 0,0.0
    for p,level in route:
        o = owner[p]
        kind = 4 if level == 0 else 1 if o == seat else 3 if o == 0 and level == 2 else 0 if o == 0 else 2
        need = 4 if kind == 3 else 3 if kind == 1 or kind == 2 and upg[p] else 1
        if p == player.tr.pos[seat-1] and elapsed == 0:
            need = max(1,need-player.tr.prog[seat-1])
        travel = bot.DIST[pos][p]
        g = player._work_gain(p,kind,base[p],need,elapsed+travel,owner,upg,occ,seat,R,kappa,care,travel)
        if g is not None:
            value += g
        elapsed += travel+need
        pos = p
    return value


class ConsistentAgent(agent.FutureAgent):
    def __init__(self,seed=0,params=None,feature=None):
        super().__init__(seed,params,feature)
        self.job = None
        self.job_age = 0

    def decide(self,view):
        if self.observed >= 80:
            self.job = None
            self.job_age = 0
        return super().decide(view)

    def _plan_walk(self,owner,upg,base,home,occ,frz,seat,me,R,kappa,care):
        base_action = bot.Agent._plan_walk(self,owner,upg,base,home,occ,frz,seat,me,R,kappa,care)
        if not self.feature:
            return base_action
        if self.job is not None:
            p,level = self.job
            completed = owner[p] == seat and (level == 1 or upg[p])
            unsafe = owner[p] not in (0,seat) and self._shield_risk(owner[p]-1,bot.DIST[me][p],3 if upg[p] else 1) > 0.35
            blocked = occ[p] not in (0,seat) and bot.DIST[me][p] <= 1
            if not completed and not unsafe and not blocked and self.job_age < 12:
                self.job_age += 1
                self.plan_target = p
                return "STAY" if p == me else self._step(me,p,occ,owner,seat)
            self.job = None
        proposals = agent.routes(self,owner,upg,base,home,occ,seat,me,R,kappa,care)
        if len(proposals) < 2 or proposals[0][0][0] != self.plan_target:
            return base_action
        guard = self.feature.get("guard",0)
        scores = [proxy(self,r,owner,upg,base,occ,seat,R,kappa,care) for r in proposals]
        paths,actions = [],[]
        for route,score in zip(proposals,scores):
            p = route[0][0]
            a = "STAY" if p == me else self._step(me,p,occ,owner,seat)
            if a not in actions and (not paths or score >= guard*scores[0]):
                paths.append(route[:1])
                actions.append(a)
        if len(paths) < 2 or actions[0] != base_action:
            return base_action
        world = rollout.reconstruct(self.board,self.tr)
        values = [[] for _ in paths]
        particles = 6
        deadline = self._t_start+0.125 if self.P["throttle"] else float("inf")
        for sample in range(particles):
            profiles = [self.beliefs.profile(j,sample,particles,self.feature["learned"]) for j in range(4)]
            initial = world.clone()
            if not self.tr.token_known:
                initial.token = [j for j in range(1,5) if j != seat][sample % 3]
            row = []
            for route,a in zip(paths,actions):
                if time.perf_counter() >= deadline:
                    break
                own,pw,_ = rollout.simulate(initial,seat-1,route,profiles,sample,
                                            self.feature["horizon"]+4*(sample % 3-1),first_action=a)
                row.append(own)
            if len(row) != len(paths):
                break
            for out,v in zip(values,row):
                out.append(v)
        n = len(values[0])
        self.particles_done += n
        if n < 2:
            return base_action
        self.decisions += 1
        best,gain = 0,10.0
        for k in range(1,len(paths)):
            diff = [a-b for a,b in zip(values[k],values[0])]
            if guard and sum(d>0 for d in diff) < math.ceil(2*n/3):
                continue
            mean = sum(diff)/n
            sd = math.sqrt(sum((d-mean)**2 for d in diff)/max(1,n-1))
            robust = mean-self.feature["risk"]*sd
            if robust > gain:
                best,gain = k,robust
        if best:
            self.changed += 1
            self.plan_target = paths[best][0][0]
            if self.feature.get("commit") and paths[best][0][1] > 0:
                self.job = paths[best][0]
                self.job_age = 0
            return actions[best]
        return base_action
