"""How badly does the bot play if the server throws away module state every turn?"""
import json, random, engine, mybot, zoo
P=json.load(open('v1_params.json'))
FIELD=[zoo.SpineFarmerBot, zoo.CamperBot, zoo.GreedyShieldBot, zoo.GreedyValueBot,
       zoo.PacifistBot, zoo.RaiderBot, zoo.BaiterBot]
def run(amnesia, games=60, seed0=11000):
    tot=0.0; sc=0.0
    for s in range(games):
        rnd=random.Random(seed0+s); base=engine.make_map(seed=seed0+s)
        myseat=rnd.randrange(4)
        ag=mybot.Agent(seed=s, params=P)
        bots=[ag if i==myseat else FIELD[rnd.randrange(len(FIELD))](s*4+i) for i in range(4)]
        g=engine.Game(base=base,start_token=rnd.randint(1,4))
        while not g.over():
            vs=g.views(); acts=[]
            for i in range(4):
                if i==myseat and amnesia:
                    ag.tr.reset(); ag.last_action=None; ag.plan_target=None
                a=bots[i](vs[i])
                if a not in vs[i].legal_actions: a="STAY"
                acts.append(a)
            g.step(acts)
        pl=g.places()
        tot+=sum(1.0 for j in range(4) if j!=myseat and pl[myseat]<pl[j])
        tot+=0.5*sum(1 for j in range(4) if j!=myseat and pl[myseat]==pl[j])
        sc+=g.score[myseat]
    return tot/games, sc/games
a,b=run(False); print("state kept between turns   : PW %.2f/3  score %.0f" % (a,b))
c,d=run(True);  print("state wiped every turn     : PW %.2f/3  score %.0f" % (c,d))
print("cost of losing module state: %.2f PW, %.0f points" % (a-c, b-d))
