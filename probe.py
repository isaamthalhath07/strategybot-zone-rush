import random, engine, mybot, zoo

def eval_params(params, games=40, seed0=2000, opps=None):
    """mean pairwise wins out of 3, vs a mixed field, seats and maps randomised"""
    if opps is None:
        opps=[zoo.SpineFarmerBot, zoo.CamperBot, zoo.GreedyShieldBot,
              zoo.GreedyValueBot, zoo.PacifistBot, zoo.RaiderBot, zoo.BaiterBot]
    tot=0.0; sc=0.0; cells=0.0; frz=0.0; sh=0.0; n=0
    for s in range(games):
        rnd=random.Random(seed0+s); base=engine.make_map(seed=seed0+s)
        myseat=rnd.randrange(4)
        ag=mybot.Agent(seed=3, params=params)
        bots=[]
        for i in range(4):
            bots.append(ag if i==myseat else opps[rnd.randrange(len(opps))]((seed0+s)*4+i))
        g=engine.Game(base=base,start_token=rnd.randint(1,4))
        while not g.over():
            vs=g.views(); acts=[]
            for i in range(4):
                a=bots[i](vs[i])
                if a not in vs[i].legal_actions: a="STAY"
                acts.append(a)
            if g.frozen[myseat]>0: frz+=1
            eff=g.step(acts)
            if eff[myseat]=="SHIELD": sh+=1
        pl=g.places()
        tot+=sum(1 for j in range(4) if j!=myseat and pl[myseat]<pl[j])
        tot+=0.5*sum(1 for j in range(4) if j!=myseat and pl[myseat]==pl[j])
        sc+=g.score[myseat]; cells+=g.cells_owned(myseat); n+=1
    return tot/n, sc/n, cells/n, frz/n, sh/n

VARIANTS = [
    ("baseline", {}),
    ("no shield", {"shield_bias": 1e9}),
    ("commit_prior .30", {"commit_prior": 0.30}),
    ("safe_disc 1.0", {"safe_discount": 1.0}),
    ("zone_bonus 1.35", {"zone_bonus": 1.35}),
    ("zone_bonus 1.0", {"zone_bonus": 1.0}),
    ("visits 6 h28", {"visits": 6, "horizon": 28}),
    ("w_upgrade 1.3", {"w_upgrade": 1.3}),
    ("perish 0.0", {"perish": 0.0}),
    ("reach 5", {"reach": 5}),
]
print("%-18s %6s %7s %6s %6s %6s" % ("variant","PW/3","score","cells","frozen","shields"))
for name, pr in VARIANTS:
    pw, sc, ce, fz, sh = eval_params(pr)
    print("%-18s %6.2f %7.0f %6.1f %6.1f %6.1f" % (name, pw, sc, ce, fz, sh))
