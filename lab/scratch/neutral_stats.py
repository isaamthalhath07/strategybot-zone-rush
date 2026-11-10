"""P(a neutral cell is claimed by a rival within h turns) by distance to the nearest rival."""
import sys, os, random, collections
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import sim, fields
import multiprocessing as mp
HZ = (1, 2, 3, 4, 6, 8, 12, 20)
def dist(a, b): return abs(a//8-b//8)+abs(a%8-b%8)

def job(args):
    names, fam, ms, tok, seed = args
    r = sim.play(names, sim.make_map(fam, ms), token=tok, seed=seed, record=True)
    log = r['log']
    owners = [snap['owner'] for snap, _, _ in log] + [r['final']['owner']]
    out = collections.Counter()
    me = 0   # view of seat 1: rivals are seats 2..4
    for t, (snap, chosen, res) in enumerate(log):
        if t % 3: continue
        pos, owner = snap['pos'], snap['owner']
        for c in range(64):
            if owner[c]: continue
            d = min(7, min(dist(pos[j], c) for j in (1, 2, 3)))
            phase = 0 if t < 20 else 1 if t < 45 else 2
            for h in HZ:
                if t + h > 80: break
                got = any(owners[t+k][c] not in (0, me + 1) for k in range(1, h+1))
                for key in ((d, h), (phase, d, h)):
                    out[key + ('n',)] += 1
                    out[key + ('got',)] += got
    return out

if __name__ == '__main__':
    pool = fields.DEV_ELITE * 3 + fields.DEV_MID * 2 + fields.DEV_WEAK
    rnd = random.Random(80)
    tasks = [([rnd.choice(pool) for _ in range(4)], rnd.choice(sim.FAMILIES), rnd.randrange(10**6), rnd.randint(1, 4), rnd.randrange(10**9)) for g in range(1000)]
    tot = collections.Counter()
    with mp.Pool(4) as p:
        for c in p.imap_unordered(job, tasks, chunksize=4):
            tot.update(c)
    print('rows: distance of nearest rival (0 = standing on it); cols h =', HZ)
    for d in range(0, 8):
        print('  d=%d n=%-7d' % (d, tot[(d, 1, 'n')]), ' '.join('%.3f' % (tot[(d, h, 'got')]/max(1, tot[(d, h, 'n')])) for h in HZ))
    for phase in (0, 1, 2):
        print(' phase', phase)
        for d in range(0, 8):
            print('  d=%d n=%-7d' % (d, tot[(phase, d, 1, 'n')]), ' '.join('%.3f' % (tot[(phase, d, h, 'got')]/max(1, tot[(phase, d, h, 'n')])) for h in HZ))
