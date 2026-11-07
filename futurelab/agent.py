"""Receding-horizon route choice under conditional joint game futures."""
import math
import time

import bot
from botlib import parse
from futurelab import models, rollout


VARIANTS = {
    "baseline": {},
    "prior24": {"learned":False, "horizon":24, "risk":0.0},
    "future24": {"learned":True, "horizon":24, "risk":0.0},
    "careful24": {"learned":True, "horizon":24, "risk":0.5},
    "future36": {"learned":True, "horizon":36, "risk":0.25},
    "placement24": {"learned":True, "horizon":24, "risk":0.25, "placement":True},
}


def routes(agent, owner, upg, base, home, occ, seat, me, R, kappa, care):
    """Keep the best original-value walk for each alternative first work cell.

    This only proposes routes. Their *evaluation* uses changed ownership,
    progress, captures and shields in the exact simulated game, not this board.
    """
    candidates = agent._candidates(owner,upg,base,home,occ,seat,me,R,care)
    beam = [(0.0, me, 0, frozenset(), ())]
    best = {}
    for depth in range(6):
        nxt = []
        for value, pos, elapsed, visited, path in beam:
            for _, _, p, kind, v, need in candidates:
                if p in visited:
                    continue
                travel = bot.DIST[pos][p]
                if p == me and elapsed and agent.tr.prog[seat-1]:
                    need = 4 if kind == 3 else 3 if kind == 1 or kind == 2 and upg[p] else 1
                arrival = elapsed+travel
                finished = arrival+need
                if finished > min(40,R):
                    continue
                gain = agent._work_gain(p,kind,v,need,arrival,owner,upg,occ,seat,R,kappa,care,travel)
                if gain is None:
                    continue
                level = 0 if kind == 4 else 2 if kind in (1,3) else 1
                route = path+((p,level),)
                score = value+gain
                first = route[0][0]
                if first not in best or score > best[first][0]:
                    best[first] = (score,route)
                nxt.append((score,p,finished,visited | {p},route))
        if not nxt:
            break
        beam = sorted(nxt, key=lambda x:x[0], reverse=True)[:32]
    ordered = sorted(best, key=lambda p:best[p][0], reverse=True)
    base_target = agent.plan_target
    if base_target in ordered:
        ordered.remove(base_target)
        ordered.insert(0,base_target)
    return [best[p][1] for p in ordered[:6]]


class FutureAgent(bot.Agent):
    def __init__(self, seed=0, params=None, feature=None):
        super().__init__(seed,params)
        self.feature = feature or {}
        self.beliefs = models.Beliefs()
        self.observed = 0
        self.board = None
        self.decisions = 0
        self.changed = 0
        self.particles_done = 0
        if self.feature and self.P["throttle"]:
            self.P["budget_ms"] = 100.0

    def decide(self, view):
        if not self.feature:
            return super().decide(view)
        board = parse(view)
        if self.observed >= 80:
            self.beliefs = models.Beliefs()
            self.observed = 0
        self.observed += 1
        self.beliefs.observe(board)
        self.board = board
        action = super().decide(view)
        world = rollout.reconstruct(board,self.tr)
        self.beliefs.predict(world,board)
        return action

    def _plan_walk(self, owner,upg,base,home,occ,frz,seat,me,R,kappa,care):
        baseline_action = super()._plan_walk(owner,upg,base,home,occ,frz,seat,me,R,kappa,care)
        if not self.feature:
            return baseline_action
        baseline_target = self.plan_target
        proposals = routes(self,owner,upg,base,home,occ,seat,me,R,kappa,care)
        if len(proposals) < 2 or proposals[0][0][0] != baseline_target:
            return baseline_action
        # Replanning happens next turn. Keep one representative for each
        # distinct action now, rather than spend most compute on equivalent
        # first steps toward several different faraway goals.
        chosen, actions = [], []
        for route in proposals:
            p = route[0][0]
            action = "STAY" if p == me else self._step(me,p,occ,owner,seat)
            if action not in actions:
                chosen.append(route)
                actions.append(action)
        proposals = chosen
        if len(proposals) < 2 or actions[0] != baseline_action:
            return baseline_action
        world = rollout.reconstruct(self.board,self.tr)
        particles = 6
        values = [[] for route in proposals]
        bounded = self.P["throttle"]
        deadline = self._t_start+0.125 if bounded else float("inf")
        for sample in range(particles):
            profiles = [self.beliefs.profile(j,sample,particles,self.feature["learned"]) for j in range(4)]
            horizon = max(1,self.feature["horizon"]+4*(sample % 3-1))
            initial = world.clone()
            if not self.tr.token_known:
                options = [j for j in range(1,5) if j != seat]
                initial.token = options[sample % len(options)]
            scores = []
            for proposal, first_action in zip(proposals,actions):
                if time.perf_counter() >= deadline:
                    break
                own,pw,_ = rollout.simulate(initial,seat-1,proposal,profiles,sample,horizon,first_action=first_action)
                scores.append(pw if self.feature.get("placement") else own)
            if len(scores) != len(proposals):
                break  # discard incomplete batches; no order-dependent advantage
            for out,value in zip(values,scores):
                out.append(value)
        n = len(values[0])
        self.particles_done += n
        if n < 2:
            return baseline_action
        self.decisions += 1
        best, best_gain = 0, (0.015 if self.feature.get("placement") else 10.0)
        for k in range(1,len(proposals)):
            diff = [x-y for x,y in zip(values[k],values[0])]
            mean = sum(diff)/n
            sd = math.sqrt(sum((d-mean)**2 for d in diff)/max(1,n-1))
            gain = mean-self.feature["risk"]*sd
            if gain > best_gain:
                best,best_gain = k,gain
        if best:
            target = proposals[best][0][0]
            self.plan_target = target
            self.changed += 1
            return actions[best]
        return baseline_action
