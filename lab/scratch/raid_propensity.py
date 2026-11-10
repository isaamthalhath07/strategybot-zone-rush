"""Per bot: how often does it step onto an exposed level-1 rival cell when adjacent to
one, how many such chances arise per game and by what turn, and how many level-1 and
level-2 raids it completes. Referee truth, offline analysis only.
  python3 lab/scratch/raid_propensity.py [games]
"""
import sys, os, random, collections
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import sim, suite2
import multiprocessing as mp
HOME = {0, 7, 63, 56}

def job(args):
    names, fam, ms, tok, seed = args
    r = sim.play(names, sim.make_map(fam, ms), token=tok, seed=seed, record=True)
    out = collections.Counter()
    for snap, chosen, res in r['log']:
        pos, owner, upg, frozen, turn = snap['pos'], snap['owner'], snap['upg'], snap['frozen'], snap['turn']
        occ = set(pos)
        for i in range(4):
            if frozen[i]: continue
            p = pos[i]
            near = []
            for dq in (-8, 8, -1, 1):
                q = p + dq
                if 0 <= q < 64 and abs(q % 8 - p % 8) + abs(q // 8 - p // 8) == 1 and q not in occ and q not in HOME:
                    if owner[q] and owner[q] != i + 1 and not upg[q]:
                        near.append(q)
            if near:
                a = chosen[i]
                dq = {'NORTH': -8, 'SOUTH': 8, 'WEST': -1, 'EAST': 1}.get(a)
                on = dq is not None and (p + dq) in near
                out[(names[i], 'opp')] += 1
                out[(names[i], 'step')] += on
                if turn <= 40:
                    out[(names[i], 'opp40')] += 1
        for e in res['events']:
            if e['type'] == 'raid':
                out[(names[e['seat'] - 1], 'raidL%d' % e['level'])] += 1
    for n in names:
        out[(n, 'games')] += 1
    return out

if __name__ == '__main__':
    games = int(sys.argv[1]) if len(sys.argv) > 1 else 600
    g = suite2.groups()
    pool = g['strong'] + g['mid'] + g['weak']
    rnd = random.Random(91)
    tasks = [([rnd.choice(pool) for _ in range(4)], rnd.choice(suite2.FAMS), rnd.randrange(10**6), rnd.randint(1, 4), rnd.randrange(10**9)) for _ in range(games)]
    tot = collections.Counter()
    with mp.Pool(4) as p:
        for c in p.imap_unordered(job, tasks, chunksize=4):
            tot.update(c)
    for name in ('strong', 'mid', 'weak'):
        print('\n%s: bot, step-on rate when adjacent to an exposed L1 rival cell, chances per game (by turn 40), L1 raids/game, L2 raids/game' % name)
        rows = []
        for b in sorted(set(g[name])):
            n = max(1, tot[(b, 'games')])
            opp = tot[(b, 'opp')]
            rows.append((tot[(b, 'step')] / max(1, opp), b, opp / n, tot[(b, 'opp40')] / n, tot[(b, 'raidL1')] / n, tot[(b, 'raidL2')] / n))
        rows.sort()
        for rate, b, o, o40, r1, r2 in rows:
            print('  %-34s %.2f   %5.1f (%4.1f)   %4.1f  %4.1f' % (b[:33], rate, o, o40, r1, r2))
        import statistics
        print('  median step-on rate %.2f, quartiles %.2f / %.2f' % (statistics.median([r[0] for r in rows]), rows[len(rows)//4][0], rows[3*len(rows)//4][0]))
