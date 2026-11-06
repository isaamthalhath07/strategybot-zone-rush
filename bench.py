import sys, time, arena, zoo
games = int(sys.argv[1]) if len(sys.argv)>1 else 400
reg = arena.default_registry()
pool = [c.name for c in zoo.ZOO if c.name not in ("stay",)]
t0=time.time()
st = arena.tournament(reg, ["mybot"]+pool, games=games, seed=11, focus="mybot")
dt=time.time()-t0
print(st.table())
print()
print(st.h2h_table("mybot"))
print("\n%.1fs for %d games (%.0f games/s)" % (dt, games, games/dt))
