import sys, random, engine, mybot, zoo

def profile(opp_cls, games=30, seed0=500, params=None):
    agg = dict(score=0.0, bonus=0.0, income=0.0, cells=0.0, upg=0.0, moves=0.0,
               stays=0.0, shields=0.0, frozen=0.0, oppscore=0.0, wins=0.0, n=0)
    for s in range(games):
        rnd = random.Random(seed0+s)
        base = engine.make_map(seed=seed0+s)
        myseat = rnd.randint(0,3)
        bots = []
        ag = mybot.Agent(seed=7, params=params)
        for i in range(4):
            bots.append(ag if i==myseat else opp_cls(seed0*4+i))
        g = engine.Game(base=base, start_token=rnd.randint(1,4))
        acts_hist = []
        while not g.over():
            vs = g.views(); acts=[]
            for i in range(4):
                a = bots[i](vs[i])
                if a not in vs[i].legal_actions: a="STAY"
                acts.append(a)
            if g.frozen[myseat]>0: agg['frozen']+=1
            eff = g.step(acts)
            e = eff[myseat]
            if e=="SHIELD": agg['shields']+=1
            elif e=="STAY": agg['stays']+=1
            else: agg['moves']+=1
        pl = g.places()
        inc = sum(g.base[p]*(2 if g.upg[p] else 1) for p in range(64) if g.owner[p]==myseat+1)
        agg['score']+=g.score[myseat]; agg['income']+=inc
        agg['cells']+=g.cells_owned(myseat)
        agg['upg']+=sum(1 for p in range(64) if g.owner[p]==myseat+1 and g.upg[p])
        agg['oppscore']+=sum(g.score[j] for j in range(4) if j!=myseat)/3.0
        agg['wins']+=sum(1 for j in range(4) if j!=myseat and pl[myseat]<pl[j])
        agg['bonus']+=ag.tr.takes[myseat]
        agg['n']+=1
    n=agg['n']
    return dict((k, v/n) for k,v in agg.items() if k!='n')

for name, cls in (("spine", zoo.SpineFarmerBot), ("camper", zoo.CamperBot),
                  ("greedy", zoo.GreedyValueBot)):
    r = profile(cls)
    print("vs 3x %-8s  myscore %6.0f  opp %6.0f  PW %.2f/3  cells %4.1f upg %4.1f "
          "endinc %4.1f | takes %4.1f  moves %4.1f stays %4.1f shields %3.1f frozen %4.1f"
          % (name, r['score'], r['oppscore'], r['wins'], r['cells'], r['upg'],
             r['income'], r['bonus'], r['moves'], r['stays'], r['shields'], r['frozen']))

# what does spine itself look like under the same lens?
def profile_zoo(me_cls, opp_cls, games=30, seed0=500):
    agg=dict(score=0.0,cells=0.0,upg=0.0,income=0.0,moves=0.0,stays=0.0,
             shields=0.0,frozen=0.0,wins=0.0,n=0)
    for s in range(games):
        rnd=random.Random(seed0+s); base=engine.make_map(seed=seed0+s)
        myseat=rnd.randint(0,3)
        bots=[me_cls(1) if i==myseat else opp_cls(seed0*4+i) for i in range(4)]
        g=engine.Game(base=base,start_token=rnd.randint(1,4))
        while not g.over():
            vs=g.views(); acts=[]
            for i in range(4):
                a=bots[i](vs[i])
                if a not in vs[i].legal_actions: a="STAY"
                acts.append(a)
            if g.frozen[myseat]>0: agg['frozen']+=1
            eff=g.step(acts); e=eff[myseat]
            if e=="SHIELD": agg['shields']+=1
            elif e=="STAY": agg['stays']+=1
            else: agg['moves']+=1
        pl=g.places()
        agg['score']+=g.score[myseat]; agg['cells']+=g.cells_owned(myseat)
        agg['upg']+=sum(1 for p in range(64) if g.owner[p]==myseat+1 and g.upg[p])
        agg['income']+=sum(g.base[p]*(2 if g.upg[p] else 1) for p in range(64) if g.owner[p]==myseat+1)
        agg['wins']+=sum(1 for j in range(4) if j!=myseat and pl[myseat]<pl[j])
        agg['n']+=1
    n=agg['n']; return dict((k,v/n) for k,v in agg.items() if k!='n')

r=profile_zoo(zoo.SpineFarmerBot, zoo.SpineFarmerBot)
print("\nspine vs 3x spine   score %6.0f  PW %.2f/3  cells %4.1f upg %4.1f endinc %4.1f | "
      "moves %4.1f stays %4.1f shields %3.1f frozen %4.1f"
      % (r['score'],r['wins'],r['cells'],r['upg'],r['income'],r['moves'],r['stays'],
         r['shields'],r['frozen']))
r=profile_zoo(zoo.CamperBot, zoo.SpineFarmerBot)
print("camper vs 3x spine  score %6.0f  PW %.2f/3  cells %4.1f upg %4.1f endinc %4.1f | "
      "moves %4.1f stays %4.1f shields %3.1f frozen %4.1f"
      % (r['score'],r['wins'],r['cells'],r['upg'],r['income'],r['moves'],r['stays'],
         r['shields'],r['frozen']))
