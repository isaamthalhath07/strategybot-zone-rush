"""How much of the server's time limit does a bot use?
  python3 lab/timing.py bot.py [games]
The server allows 2 s for the first call and 200 ms for every later one; a late answer
counts as STAY. Reports the module load time, the first call, and the distribution of
later calls, measured single-threaded against strong opponents (which produce the
busiest boards), and how much slower a server could be before a call would be late.
"""
import sys, os, time, types, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sim, fields
from referee import Referee

if __name__ == "__main__":
    path = sim.resolve(sys.argv[1])[1]
    games = int(sys.argv[2]) if len(sys.argv) > 2 else 40
    src = open(path, "rb").read()
    t0 = time.perf_counter()
    code = compile(src, path, "exec")
    mod = types.ModuleType("bot"); exec(code, mod.__dict__)
    load_ms = (time.perf_counter() - t0) * 1000
    rnd = random.Random(5)
    opp = fields.HOLDOUT_ELITE + fields.DEV_ELITE
    fam = sim.FAMILIES + sim.NEW_FAMILIES
    first, later = [], []
    for g in range(games):
        names = [rnd.choice(opp) for _ in range(3)]
        seat = g % 4
        actors = [sim.make_actor(n, g * 4 + i) for i, n in enumerate(names)]
        m = types.ModuleType("bot"); exec(code, m.__dict__)
        actors.insert(seat, m.act)
        game = Referee(sim.make_map(fam[g % len(fam)], 900 + g), start_token=1 + g % 4)
        while not game.over():
            states = sim.build_states(game)
            chosen = []
            for i in range(4):
                if i == seat:
                    t = time.perf_counter()
                    a = actors[i](states[i])
                    dt = (time.perf_counter() - t) * 1000
                    (first if game.turn == 1 else later).append(dt)
                else:
                    try:
                        a = actors[i](states[i])
                    except Exception:
                        a = "STAY"
                chosen.append(a if a in states[i].legal_actions else "STAY")
            game.step(chosen)
    later.sort()
    n = len(later)
    print("%s: %d games, %d timed calls" % (os.path.basename(path), games, n + len(first)))
    print("  module load        %.1f ms" % load_ms)
    print("  first call         worst %.1f ms   (limit 2000: a server %.0fx slower is still in time)" % (max(first), 2000.0 / (max(first) + load_ms)))
    print("  later calls        median %.2f  99%% %.2f  99.9%% %.2f  worst %.2f ms" % (later[n // 2], later[int(n * 0.99)], later[int(n * 0.999)], later[-1]))
    print("  headroom           a server %.0fx slower than this machine still answers every call within 200 ms" % (200.0 / later[-1]))
