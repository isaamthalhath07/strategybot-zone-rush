"""
Turn-80 raids. On the last turn a shield costs the landlord nothing, so a rational
landlord always shields. How often does the bot try to complete a raid on turn 80,
and how often is it blocked (finding B5)?

    python audit/lastturn.py [tier]
"""
import os
import sys
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO)
os.chdir(REPO)
import bot, engine, measure
import multiprocessing as mp

def one(task):
    map_seed, myseat, opps, token = task
    bots, k = [], 0
    for i in range(4):
        if i == myseat:
            bots.append(bot.Agent(seed=map_seed & 0xffff, params={"throttle": 0, "budget_ms": 10000.0}))
        else:
            bots.append(measure._make(opps[k], map_seed * 4 + i)); k += 1
    g = engine.Game(base=engine.make_map(seed=map_seed), start_token=token)
    out = {"tries": 0, "blocked": 0, "won": 0, "lost_pts": 0, "planned_r2": 0, "r2_blocked": 0}
    while not g.over():
        vs = g.views()
        acts = []
        for i in range(4):
            a = bots[i](vs[i]); acts.append(a if a in vs[i].legal_actions else "STAY")
        p = g.pos[myseat]; o = g.owner[p]
        completing = (acts[myseat] == "STAY" and o not in (0, myseat + 1) and not g.home[p]
                      and g.frozen[myseat] == 0
                      and (not g.upg[p] or g.prog[myseat] >= 2))
        if g.turn == 80 and completing:
            out["tries"] += 1
            if acts[o - 1] == "SHIELD":
                out["blocked"] += 1
                out["lost_pts"] += 8 * g.base[p] * (2 if g.upg[p] else 1) + g.base[p]
            else:
                out["won"] += 1
        g.step(acts)
    return out

if __name__ == "__main__":
    tasks = measure.make_tasks(400, sys.argv[1] if len(sys.argv) > 1 else "strangers", seed=21)
    with mp.Pool(4) as pool:
        res = pool.map(one, tasks, chunksize=10)
    tot = dict((k, sum(r[k] for r in res)) for k in res[0])
    print(len(tasks), "games:", tot)
