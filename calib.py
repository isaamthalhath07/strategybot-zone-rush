"""Fit a turn estimator from board state alone, for the case where the server
does not keep module-level state between calls."""
import random, engine, zoo, json
rows=[]
FIELD=[zoo.SpineFarmerBot, zoo.CamperBot, zoo.GreedyShieldBot, zoo.GreedyValueBot,
       zoo.PacifistBot, zoo.RaiderBot, zoo.BaiterBot]
for s in range(60):
    rnd=random.Random(s); base=engine.make_map(seed=s)
    bots=[FIELD[rnd.randrange(len(FIELD))](s*4+i) for i in range(4)]
    g=engine.Game(base=base,start_token=rnd.randint(1,4))
    while not g.over():
        owned=sum(1 for p in range(64) if g.owner[p] and not g.home[p])
        upg=sum(1 for p in range(64) if g.upg[p])
        rows.append((owned, upg, g.turn))
        vs=g.views(); acts=[]
        for i in range(4):
            a=bots[i](vs[i])
            if a not in vs[i].legal_actions: a="STAY"
            acts.append(a)
        g.step(acts)
# least squares turn ~ a*owned + b*upg + c
n=len(rows)
import itertools
X=[[r[0],r[1],1.0] for r in rows]; y=[r[2] for r in rows]
# normal equations (3x3)
A=[[sum(X[k][i]*X[k][j] for k in range(n)) for j in range(3)] for i in range(3)]
B=[sum(X[k][i]*y[k] for k in range(n)) for i in range(3)]
# gaussian elimination
for i in range(3):
    pv=A[i][i]
    for j in range(i+1,3):
        f=A[j][i]/pv
        for k_ in range(3): A[j][k_]-=f*A[i][k_]
        B[j]-=f*B[i]
c=[0.0]*3
for i in (2,1,0):
    sdum=B[i]-sum(A[i][j]*c[j] for j in range(i+1,3))
    c[i]=sdum/A[i][i]
err=[abs(c[0]*r[0]+c[1]*r[1]+c[2]-r[2]) for r in rows]
err.sort()
print("turn ~= %.4f*owned + %.4f*upgraded + %.3f" % (c[0],c[1],c[2]))
print("abs error: median %.1f turns, p90 %.1f, max %.1f" %
      (err[n//2], err[int(n*0.9)], err[-1]))
json.dump({"a":c[0],"b":c[1],"c":c[2]}, open("turn_fit.json","w"))
