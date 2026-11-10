"""Survival of the FOCAL bot's own level-1 cells, by game phase and distance to the
nearest rival, in each development field. The earlier table (hazard_stats.py) pooled
every bot's cells; most strong bots upgrade a cell before leaving it, so their level-1
cells are short-lived and that table says little about cells left un-upgraded for long.
  python3 lab/scratch/hazard_own.py focal [maps]
"""
import sys, os, collections
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import sim, arena, suite2
import multiprocessing as mp
HZ = (2, 5, 10, 20, 40)
HOME = {0, 7, 63, 56}
def dist(a, b): return abs(a//8-b//8)+abs(a%8-b%8)

def job(t):
    names = list(t['opponents']); names.insert(t['seat'], t['cand'])
    r = sim.play(names, sim.make_map(t['family'], t['mapseed']), token=t['token'], seed=t['seed'], record=True)
    log = r['log']; me = t['seat'] + 1
    owners = [snap['owner'] for snap, _, _ in log] + [r['final']['owner']]
    out = collections.Counter()
    for k, (snap, chosen, res) in enumerate(log):
        if k % 2: continue
        pos, owner, upg = snap['pos'], snap['owner'], snap['upg']
        turn = snap['turn']
        ph = 0 if turn <= 20 else 1 if turn <= 40 else 2 if turn <= 55 else 3
        for c in range(64):
            if owner[c] != me or c in HOME or upg[c] or pos[me-1] == c: continue
            d = min(7, min(dist(pos[j], c) for j in range(4) if j != me-1))
            for h in HZ:
                hh = min(h, 80 - k)          # truncate at the end of the game
                lost = any(owners[k+q][c] != me for q in range(1, hh+1))
                out[(t['field'], ph, d, h, 'n')] += 1
                out[(t['field'], ph, d, h, 'lost')] += lost
    return out

if __name__ == '__main__':
    cand = sys.argv[1]; maps = int(sys.argv[2]) if len(sys.argv) > 2 else 40
    g = suite2.groups()
    tasks = []
    for fi, (name, field) in enumerate(sorted(g.items())):
        for f in arena.fixtures(field, maps=maps, seed=61 + fi, families=suite2.FAMS):
            tasks.append(dict(f, cand=cand, field=name))
    tot = collections.Counter()
    with mp.Pool(4) as p:
        for c in p.imap_unordered(job, tasks, chunksize=4):
            tot.update(c)
    for name in sorted(g):
        print('\nfield %s: P(own level-1 cell lost within h turns), h = %s (truncated at game end)' % (name, HZ))
        for ph, label in enumerate(('turns 1-20', 'turns 21-40', 'turns 41-55', 'turns 56-80')):
            print('  ' + label)
            for d in range(1, 8):
                n = tot[(name, ph, d, HZ[0], 'n')]
                if n < 30: continue
                print('    d=%d n=%-6d' % (d, n), ' '.join('%.3f' % (tot[(name, ph, d, h, 'lost')] / max(1, tot[(name, ph, d, h, 'n')])) for h in HZ))
