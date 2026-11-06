import random, engine, mybot, zoo
from collections import Counter

cat = Counter(); phase = {}
for s in range(12):
    rnd=random.Random(900+s); base=engine.make_map(seed=900+s)
    myseat=0
    ag=mybot.Agent(seed=7)
    bots=[ag if i==myseat else zoo.SpineFarmerBot(900+i) for i in range(4)]
    g=engine.Game(base=base,start_token=rnd.randint(1,4))
    while not g.over():
        vs=g.views(); turn=g.turn
        acts=[]
        for i in range(4):
            a=bots[i](vs[i])
            if a not in vs[i].legal_actions: a="STAY"
            acts.append(a)
        me=g.pos[myseat]; o=g.owner[me]; seat=myseat+1
        a=acts[myseat]
        if g.frozen[myseat]>0: k="frozen"
        elif a=="SHIELD": k="shield"
        elif a=="STAY":
            if o==0: k="stay:claim-neutral"
            elif o==seat: k="stay:upgrade" if not g.upg[me] else "stay:idle-on-done-cell"
            else: k="stay:raid"
        else: k="move"
        cat[k]+=1
        band = (turn-1)//20
        phase.setdefault(band, Counter())[k]+=1
        g.step(acts)
tot=sum(cat.values())
print("mybot action mix vs 3x spine (%d bot-turns, 12 games)" % tot)
for k,v in cat.most_common():
    print("  %-24s %5d  %5.1f%%" % (k,v,100.0*v/tot))
print("\nby phase (turns 1-20 / 21-40 / 41-60 / 61-80):")
keys=["move","stay:claim-neutral","stay:upgrade","stay:raid","shield","stay:idle-on-done-cell","frozen"]
print("  %-24s %7s %7s %7s %7s" % ("", "1-20","21-40","41-60","61-80"))
for k in keys:
    row=[phase.get(b,Counter()).get(k,0) for b in range(4)]
    print("  %-24s %7d %7d %7d %7d" % (k,*row))
