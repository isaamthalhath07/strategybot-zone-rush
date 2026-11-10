"""Empirical survival of owned cells vs distance to the nearest rival (offline, referee truth)."""
import sys, os, random, collections
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import sim, fields
import multiprocessing as mp
HZ = (1, 2, 3, 5, 8, 12, 20)
HOME = {0, 7, 63, 56}
def dist(a, b): return abs(a//8-b//8)+abs(a%8-b%8)

def job(args):
    names, fam, ms, tok, seed = args
    r = sim.play(names, sim.make_map(fam, ms), token=tok, seed=seed, record=True)
    log = r['log']
    owners = [snap['owner'] for snap, _, _ in log] + [r['final']['owner']]
    upgs = [snap['upg'] for snap, _, _ in log] + [r['final']['upg']]
    out = collections.Counter()
    for t, (snap, chosen, res) in enumerate(log):
        if t % 3: continue
        pos, owner, upg = snap['pos'], snap['owner'], snap['upg']
        for c in range(64):
            o = owner[c]
            if not o or c in HOME: continue
            if pos[o-1] == c: continue      # owner standing on it
            d = min(dist(pos[j], c) for j in range(4) if j != o-1)
            d = min(d, 7)
            lvl = 2 if upg[c] else 1
            phase = 0 if t < 27 else 1 if t < 54 else 2
            for h in HZ:
                if t + h > 80: break
                lost = any(owners[t+k][c] != o for k in range(1, h+1))
                out[(lvl, d, h, 'n')] += 1
                out[(lvl, d, h, 'lost')] += lost
                out[(lvl, phase, d, h, 'n')] += 1
                out[(lvl, phase, d, h, 'lost')] += lost
    return out

if __name__ == '__main__':
    which = sys.argv[1] if len(sys.argv) > 1 else 'mix'
    pool = fields.DEV_ELITE if which == 'elite' else fields.DEV_ELITE * 3 + fields.DEV_MID * 2 + fields.DEV_WEAK
    rnd = random.Random(78)
    tasks = [([rnd.choice(pool) for _ in range(4)], rnd.choice(sim.FAMILIES), rnd.randrange(10**6), rnd.randint(1, 4), rnd.randrange(10**9)) for g in range(1200)]
    tot = collections.Counter()
    with mp.Pool(4) as p:
        for c in p.imap_unordered(job, tasks, chunksize=4):
            tot.update(c)
    for lvl in (1, 2):
        print('level', lvl, ' rows: distance to nearest rival; cols: P(lost within h turns), h =', HZ)
        for d in range(1, 8):
            print('  d=%d n=%-7d' % (d, tot[(lvl, d, 1, 'n')]), ' '.join('%.3f' % (tot[(lvl, d, h, 'lost')]/max(1, tot[(lvl, d, h, 'n')])) for h in HZ))
        for phase in (0, 1, 2):
            print('  phase', phase)
            for d in range(1, 8):
                print('    d=%d n=%-7d' % (d, tot[(lvl, phase, d, 1, 'n')]), ' '.join('%.3f' % (tot[(lvl, phase, d, h, 'lost')]/max(1, tot[(lvl, phase, d, h, 'n')])) for h in HZ))
