"""Interruptible runtime for the selected single-job continuation policy.

Deterministic comparisons use the identical unbounded research policy. Actual
play checks budgets inside each simulated player turn and each model update.
"""
import math
import time

from baselines import v8 as bot
from botlib import parse
from futurelab import agent,alternatives,models,rollout


def proposals(player,owner,upg,base,home,occ,seat,me,R,kappa,care,deadline):
    if time.perf_counter() >= deadline:
        return []
    candidates = player._candidates(owner,upg,base,home,occ,seat,me,R,care)
    beam = [(0.0,me,0,frozenset(),())]
    best = {}
    for depth in range(6):
        nxt = []
        for value,pos,elapsed,visited,path in beam:
            if time.perf_counter() >= deadline:
                break
            for _,_,p,kind,v,need in candidates:
                if p in visited:
                    continue
                travel = bot.DIST[pos][p]
                if p == me and elapsed and player.tr.prog[seat-1]:
                    need = 4 if kind == 3 else 3 if kind == 1 or kind == 2 and upg[p] else 1
                arrival = elapsed+travel
                finished = arrival+need
                if finished>min(40,R):
                    continue
                gain = player._work_gain(p,kind,v,need,arrival,owner,upg,occ,seat,R,kappa,care,travel)
                if gain is None:
                    continue
                level = 0 if kind == 4 else 2 if kind in (1,3) else 1
                route = path+((p,level),)
                score = value+gain
                first = route[0][0]
                if first not in best or score>best[first][0]:
                    best[first] = (score,route)
                nxt.append((score,p,finished,visited | {p},route))
        if not nxt:
            break
        beam = sorted(nxt,key=lambda x:x[0],reverse=True)[:32]
    ordered = sorted(best,key=lambda p:best[p][0],reverse=True)
    if player.plan_target in ordered:
        ordered.remove(player.plan_target)
        ordered.insert(0,player.plan_target)
    return [best[p][1] for p in ordered[:6]]


def simulate(initial,seat,route,profiles,particle,horizon,deadline,first_action):
    game = initial.clone()
    route = list(route)
    targets = [None]*4
    own_profile = (0.91,1.58,1.40,0.0,1.0,0.75)
    blocked = 0
    for elapsed in range(min(horizon,81-game.turn)):
        if time.perf_counter() >= deadline:
            return None
        actions = []
        for j in range(4):
            if time.perf_counter() >= deadline:
                return None
            draw = rollout.noise(particle,game.turn,j)
            if j != seat:
                action,targets[j] = models.action(game,j,profiles[j],targets[j],draw)
            elif elapsed == 0:
                action = first_action
            elif game.frozen[j]:
                action = "STAY"
            elif models.should_shield(game,j,own_profile[5],draw):
                action = "SHIELD"
            else:
                while route:
                    p,level = route[0]
                    complete = level > 0 and game.owner[p] == j+1 and (level == 1 or game.upg[p])
                    if complete or game.home[p] and game.owner[p] != j+1:
                        route.pop(0)
                    else:
                        break
                if route:
                    goal = route[0][0]
                    action = models.step(game,j,goal)
                    if route[0][1] == 0 and game.pos[j] == goal:
                        route.pop(0)
                    if action == "STAY" and game.pos[j] != goal:
                        blocked += 1
                        if blocked >= 2:
                            route.pop(0)
                            blocked = 0
                    else:
                        blocked = 0
                else:
                    action,targets[j] = models.action(game,j,own_profile,targets[j],draw)
            actions.append(action)
        game.step(actions)
    tail = max(0,81-game.turn)
    projected = [s+tail*i for s,i in zip(game.score,game.income)]
    own = projected[seat]
    pw = sum(1/(1+math.exp(max(-20,min(20,(projected[j]-own)/180)))) for j in range(4) if j != seat)
    return own,pw,[]


def predict(beliefs,game,board,deadline):
    rows = []
    for j in range(4):
        row = []
        for k,profile in enumerate(models.PROFILES):
            if time.perf_counter() >= deadline:
                beliefs.prediction = None
                beliefs.previous = board
                return
            probs,target = models.distribution(game,j,profile,beliefs.goals[j][k])
            beliefs.goals[j][k] = target
            row.append(probs)
        rows.append(row)
    beliefs.prediction = rows
    beliefs.previous = board


class BoundedAgent(alternatives.ConsistentAgent):
    def __init__(self,seed=0,params=None,feature=None):
        if feature and (feature.get("commit") or feature.get("guard")):
            raise ValueError("bounded export supports the single-job policy only")
        super().__init__(seed,params,feature)
        self.overall_start = 0.0

    def decide(self,view):
        if not self.feature or not self.P["throttle"]:
            return super().decide(view)
        self.overall_start = time.perf_counter()
        board = parse(view)
        if self.observed >= 80:
            self.beliefs = models.Beliefs()
            self.observed = 0
        self.observed += 1
        self.beliefs.observe(board)
        self.board = board
        action = bot.Agent.decide(self,view)
        predict(self.beliefs,rollout.reconstruct(board,self.tr),board,self.overall_start+0.150)
        return action

    def _plan_walk(self,owner,upg,base,home,occ,frz,seat,me,R,kappa,care):
        if not self.feature or not self.P["throttle"]:
            return super()._plan_walk(owner,upg,base,home,occ,frz,seat,me,R,kappa,care)
        base_action = bot.Agent._plan_walk(self,owner,upg,base,home,occ,frz,seat,me,R,kappa,care)
        options = proposals(self,owner,upg,base,home,occ,seat,me,R,kappa,care,self.overall_start+0.120)
        if len(options)<2 or options[0][0][0] != self.plan_target:
            return base_action
        paths,actions = [],[]
        for route in options:
            p = route[0][0]
            action = "STAY" if p == me else self._step(me,p,occ,owner,seat)
            if action not in actions:
                paths.append(route[:1])
                actions.append(action)
        if len(paths)<2 or actions[0] != base_action:
            return base_action
        world = rollout.reconstruct(self.board,self.tr)
        values = [[] for _ in paths]
        deadline = self.overall_start+0.125
        for sample in range(6):
            profiles = [self.beliefs.profile(j,sample,6,self.feature["learned"]) for j in range(4)]
            initial = world.clone()
            if not self.tr.token_known:
                initial.token = [j for j in range(1,5) if j != seat][sample % 3]
            row = []
            for route,action in zip(paths,actions):
                result = simulate(initial,seat-1,route,profiles,sample,
                                  self.feature["horizon"]+4*(sample % 3-1),deadline,action)
                if result is None:
                    break
                row.append(result[0])
            if len(row) != len(paths):
                break
            for out,value in zip(values,row):
                out.append(value)
        n = len(values[0])
        self.particles_done += n
        if n<2:
            return base_action
        self.decisions += 1
        best,gain = 0,10.0
        for k in range(1,len(paths)):
            diff = [a-b for a,b in zip(values[k],values[0])]
            mean = sum(diff)/n
            sd = math.sqrt(sum((d-mean)**2 for d in diff)/max(1,n-1))
            robust = mean-self.feature["risk"]*sd
            if robust>gain:
                best,gain = k,robust
        if best:
            self.changed += 1
            self.plan_target = paths[best][0][0]
            return actions[best]
        return base_action
