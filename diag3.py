import json, random, engine, mybot, zoo
from collections import Counter
P=json.load(open('v1_params.json'))
FIELD=[zoo.SpineFarmerBot, zoo.CamperBot, zoo.GreedyShieldBot, zoo.GreedyValueBot,
       zoo.PacifistBot, zoo.RaiderBot, zoo.BaiterBot]
phase={}; bonus_by_phase=Counter()
for s in range(24):
    rnd=random.Random(1200+s); base=engine.make_map(seed=1200+s)
    myseat=rnd.randrange(4)
    ag=mybot.Agent(seed=s,params=P)
    bots=[ag if i==myseat else FIELD[rnd.randrange(len(FIELD))](s*4+i) for i in range(4)]
    g=engine.Game(base=base,start_token=rnd.randint(1,4))
    while not g.over():
        vs=g.views(); turn=g.turn
        prev_owner=g.owner[:]; prev_upg=g.upg[:]
        acts=[]
        for i in range(4):
            a=bots[i](vs[i])
            if a not in vs[i].legal_actions: a="STAY"
            acts.append(a)
        me=g.pos[myseat]; o=g.owner[me]; seat=myseat+1; a=acts[myseat]
        if g.frozen[myseat]>0: k="frozen"
        elif a=="SHIELD": k="shield"
        elif a=="STAY":
            if o==0: k="claim"
            elif o==seat: k="upgrade" if not g.upg[me] else "idle"
            else: k="raid"
        else: k="move"
        band=(turn-1)//20
        phase.setdefault(band,Counter())[k]+=1
        g.step(acts)
        for p in range(64):
            if prev_owner[p] and g.owner[p]==seat and prev_owner[p]!=seat and not g.home[p]:
                bonus_by_phase[band]+=8*g.base[p]*(2 if prev_upg[p] else 1)
print("tuned bot action mix by phase (24 games)")
print("  %-10s %7s %7s %7s %7s" % ("", "1-20","21-40","41-60","61-80"))
for k in ["move","claim","upgrade","raid","shield","idle","frozen"]:
    print("  %-10s %7d %7d %7d %7d" % (k,*[phase.get(b,Counter()).get(k,0) for b in range(4)]))
print("\n  raid bonus points earned per game, by phase:")
print("  %-10s %7.1f %7.1f %7.1f %7.1f" % ("bonus",*[bonus_by_phase[b]/24.0 for b in range(4)]))
