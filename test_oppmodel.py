"""
Does the opponent model actually adapt? Build a pure baiter -- it steps onto my
land and ALWAYS leaves before the take completes -- and check that the bot's
shield rate against it collapses over the course of a game.
"""
import json, random, engine, mybot
from botlib import NC, NEIGH, parse, bfs, first_step, rivals_on_my_land
from zoo import Base

class PureBaiter(Base):
    """Never commits. Shielding against this is always a backfire."""
    name = "purebait"
    def act(self, view):
        self.read(view); seat=self.seat
        o=self.owner[self.me]
        if o and o!=seat and not self.home[self.me]:
            away=[p for p in NEIGH[self.me] if p not in self.blocked]
            if away: return self.step_to(self.rnd.choice(away))
            return "STAY"
        d=bfs(self.me,self.blocked)
        tgt=[p for p in range(NC) if self.owner[p] not in (0,seat)
             and not self.home[p] and d[p]<99]
        if tgt:
            tgt.sort(key=lambda p:d[p]); return self.step_to(tgt[0])
        free=[p for p in range(NC) if self.owner[p]==0 and d[p]<99]
        if free:
            free.sort(key=lambda p:d[p]); t=free[0]
            return "STAY" if t==self.me else self.step_to(t)
        return "STAY"

P=dict(mybot.PARAMS); P.update(json.load(open('v4_params.json'))); P['def_kappa']=0.40
early=[0,0]; late=[0,0]; frz=0.0; games=50
for s in range(games):
    rnd=random.Random(91000+s); base=engine.make_map(seed=91000+s)
    ms=rnd.randrange(4); ag=mybot.Agent(seed=s,params=P)
    bots=[ag if i==ms else PureBaiter(s*4+i) for i in range(4)]
    g=engine.Game(base=base,start_token=rnd.randint(1,4))
    while not g.over():
        t=g.turn
        vs=g.views()
        # is a non-frozen rival standing on my land right now?
        intr = any(g.owner[g.pos[j]]==ms+1 for j in range(4)
                   if j!=ms and g.frozen[j]==0)
        acts=[]
        for i in range(4):
            a=bots[i](vs[i])
            if a not in vs[i].legal_actions: a='STAY'
            acts.append(a)
        if intr and 'SHIELD' in vs[ms].legal_actions:
            bucket = early if t<=40 else late
            bucket[1]+=1
            if acts[ms]=='SHIELD': bucket[0]+=1
        if g.frozen[ms]>0: frz+=1
        g.step(acts)
def pct(b): return 100.0*b[0]/b[1] if b[1] else float('nan')
print("against an opponent that NEVER commits (shielding is always a backfire):")
print("  turns  1-40: shielded %3d of %3d chances (%.0f%%)" % (early[0],early[1],pct(early)))
print("  turns 41-80: shielded %3d of %3d chances (%.0f%%)" % (late[0],late[1],pct(late)))
print("  turns frozen per game from backfires: %.1f" % (frz/games))
print("  -> a drop from 1-40 to 41-80 means the commit model is learning")
