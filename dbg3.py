import random, engine, mybot, zoo
base=engine.make_map(seed=901); rnd=random.Random(901)
ag=mybot.Agent(seed=7)
bots=[ag]+[zoo.SpineFarmerBot(900+i) for i in range(3)]
g=engine.Game(base=base,start_token=1)
# wrap the planner to see what target it picks
orig_plan = mybot.Agent._plan_walk
info={}
def spy(self, owner,upg,base_,home_of,occ,frz,seat,me,R,kappa,care):
    cands = self._candidates(owner,upg,base_,home_of,occ,seat,me,R,care)
    a = orig_plan(self, owner,upg,base_,home_of,occ,frz,seat,me,R,kappa,care)
    info['ncand']=len(cands); info['me']=me; info['act']=a
    info['top']=[(p,k,round(pr,1)) for pr,p,k,v,n in cands[:4]]
    return a
mybot.Agent._plan_walk = spy
for t in range(1,19):
    vs=g.views()
    acts=[]
    for i in range(4):
        a=bots[i](vs[i])
        if a not in vs[i].legal_actions: a="STAY"
        acts.append(a)
    print("t%-3d me=%s(%d,%d) act=%-6s ncand=%2d top=%s"
          % (t, g.pos[0], g.pos[0]//8, g.pos[0]%8, acts[0], info.get('ncand',0),
             info.get('top')))
    g.step(acts)
print("owner count after 18 turns:", g.cells_owned(0))
