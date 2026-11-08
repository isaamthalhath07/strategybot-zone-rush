import random, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "crossfield"))
import engine, xfield
from sim import SimState, sim_step, sim_legal
rnd = random.Random(1)
bad = 0
for gi in range(400):
    fam = rnd.choice(["slope", "balanced", "patchy", "edge", "example", "flat"])
    base = xfield.make_map(fam, rnd.randrange(1 << 30))
    g = engine.Game(base=base, start_token=rnd.randint(1, 4))
    st = SimState(); st.base = list(base); st.home=[0]*64
    for s,c in ((1,0),(2,7),(3,63),(4,56)): st.home[c]=s
    st.owner = list(g.owner); st.up=[0]*64; st.pos=[0]+list(g.pos); st.fl=[0]*5; st.cd=[0]*5; st.prog=[0]*5; st.score=[0]*5
    st.turn=1; st.token=g.token; st.resets=True
    while not g.over():
        acts=[]
        for i in range(4):
            lg = g.legal(i)
            w = [1,1,1,1,4,0.3]
            a = rnd.choices(["NORTH","EAST","SOUTH","WEST","STAY","SHIELD"], weights=w)[0]
            if rnd.random()<0.05: a = "SHIELD"
            acts.append(a)
        assert sorted(sim_legal(st, 1)) == sorted(g.legal(0))
        g.step(acts)
        sim_step(st, [None]+acts)
        if (st.owner != g.owner or st.up != g.upg or st.pos[1:] != g.pos or st.fl[1:] != g.frozen
            or st.cd[1:] != g.cd or st.prog[1:] != g.prog or st.score[1:] != g.score or st.token != g.token):
            bad += 1
            break
print("games", 400, "divergent", bad)
