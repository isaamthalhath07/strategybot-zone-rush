"""
Open league: every entrant (original zoo, original holdouts, the independently
written newfield agents, frozen versions of the bot, and any candidates) plays
random four-bot games with random seats, maps and starting token. Reports Elo,
pairwise wins out of 3, mean score and first-place rate, the way arena.py does,
but in parallel.

    python league.py <games> [candidate ...]      (candidate specs as in bench2.py)
"""
import multiprocessing
import random
import sys
import time

import arena
import bench2


def _job(arg):
    out = []
    for names, map_seed, token in arg:
        out.append((names, ) + _play(names, map_seed, token))
    return out


def _play(names, map_seed, token):
    import engine
    base = engine.make_map(seed=map_seed)
    bots = [bench2.factory(n)(map_seed * 4 + i) for i, n in enumerate(names)]
    g = engine.play(bots, base=base, start_token=token)
    pl = g.places()
    return g.score[:], pl, arena.pairwise_wins(pl)


def main():
    games = int(sys.argv[1]) if len(sys.argv) > 1 else 1200
    cands = sys.argv[2:]
    entrants = (list(bench2.OPP.keys()) + ["snap:v1", "snap:v3", "snap:v6"] + cands)
    rnd = random.Random(2026)
    tasks = []
    for _ in range(games):
        names = [entrants[rnd.randrange(len(entrants))] for _ in range(4)]
        tasks.append((names, rnd.randrange(1 << 30), rnd.randint(1, 4)))
    pool = multiprocessing.Pool(processes=min(20, multiprocessing.cpu_count()))
    t0 = time.time()
    chunks = [tasks[i:i + 10] for i in range(0, len(tasks), 10)]
    rows = [r for part in pool.map(_job, chunks, chunksize=1) for r in part]
    pool.close()
    st = arena.Stats(entrants)
    # Elo depends on order; replaying the same results in several shuffled orders
    # and averaging removes most of that noise
    elo = dict((n, 0.0) for n in entrants)
    reps = 8
    for r in range(reps):
        s2 = arena.Stats(entrants)
        order = list(range(len(rows)))
        random.Random(r).shuffle(order)
        for k in order:
            names, sc, pl, pw = rows[k]
            s2.add_game(names, sc, pl, pw)
        for n in entrants:
            elo[n] += s2.elo[n] / reps
        if r == 0:
            st = s2
    st.elo = elo
    print("%d games, %d entrants, %.0fs\n" % (games, len(entrants), time.time() - t0))
    print(st.table(sort="elo"))


if __name__ == "__main__":
    main()
