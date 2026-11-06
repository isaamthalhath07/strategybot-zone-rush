"""Where do the points go in a given matchup? Candidate vs 3 copies of an opponent."""
import multiprocessing
import random
import sys

import engine
from bench2 import factory


def one(arg):
    cand, opp, s = arg
    rnd = random.Random(50000 + s)
    base = engine.make_map(seed=50000 + s)
    ms = rnd.randrange(4)
    bots = [factory(cand)(s) if i == ms else factory(opp)(s * 4 + i) for i in range(4)]
    g = engine.Game(base=base, start_token=rnd.randint(1, 4))
    st = dict(move=0, claim=0, upgrade=0, raid=0, idle=0, shield=0, frozen=0,
              backfire=0, caught=0, lost_cells=0, lost_pts=0, bonus=0,
              opp_bonus=0)
    while not g.over():
        vs = g.views()
        acts = []
        for i in range(4):
            a = bots[i](vs[i])
            if a not in vs[i].legal_actions:
                a = "STAY"
            acts.append(a)
        me = g.pos[ms]
        o = g.owner[me]
        seat = ms + 1
        a = acts[ms]
        if g.frozen[ms] > 0:
            st["frozen"] += 1
        elif a == "SHIELD":
            st["shield"] += 1
        elif a == "STAY":
            if o == 0:
                st["claim"] += 1
            elif o == seat:
                st["upgrade" if not g.upg[me] else "idle"] += 1
            elif g.home[me]:
                st["idle"] += 1
            else:
                st["raid"] += 1
        else:
            st["move"] += 1
        pre_owner = g.owner[:]
        pre_upg = g.upg[:]
        pre_fr = g.frozen[:]
        g.step(acts)
        if acts[ms] == "SHIELD" and pre_fr[ms] == 0:
            if g.frozen[ms] == 2:
                st["backfire"] += 1
            else:
                st["caught"] += 1
        for p in range(64):
            if pre_owner[p] == seat and g.owner[p] != seat:
                st["lost_cells"] += 1
                st["lost_pts"] += g.base[p] * (2 if pre_upg[p] else 1) * (81 - g.turn)
            if pre_owner[p] and pre_owner[p] != g.owner[p] and not g.home[p]:
                b = 8 * g.base[p] * (2 if pre_upg[p] else 1)
                if g.owner[p] == seat:
                    st["bonus"] += b
                else:
                    st["opp_bonus"] += b
    pl = g.places()
    my = g.score[ms]
    others = sorted([g.score[j] for j in range(4) if j != ms], reverse=True)
    inc = sum(g.base[p] * (2 if g.upg[p] else 1) for p in range(64) if g.owner[p] == ms + 1)
    pw = sum(1 for j in range(4) if j != ms and pl[ms] < pl[j])
    return my, others, pw, st, inc, g.cells_owned(ms)


if __name__ == "__main__":
    cand = sys.argv[1]
    opps = sys.argv[2].split(",")
    n = int(sys.argv[3]) if len(sys.argv) > 3 else 60
    pool = multiprocessing.Pool(20)
    for opp in opps:
        rows = pool.map(one, [(cand, opp, s) for s in range(n)])
        my = sum(r[0] for r in rows) / n
        o = [sum(r[1][k] for r in rows) / n for k in range(3)]
        pw = sum(r[2] for r in rows) / n
        keys = rows[0][3].keys()
        agg = dict((k, sum(r[3][k] for r in rows) / n) for k in keys)
        print("%s vs 3x %s: my %.0f  rivals best/mid/worst %.0f/%.0f/%.0f  PW %.2f  "
              "end income %.1f  cells %.1f"
              % (cand, opp, my, o[0], o[1], o[2], pw, sum(r[4] for r in rows) / n,
                 sum(r[5] for r in rows) / n))
        print("   " + "  ".join("%s %.1f" % (k, v) for k, v in agg.items()))
    pool.close()
