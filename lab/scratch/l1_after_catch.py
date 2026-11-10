"""After a raider is caught on a level-1 cell, how often does it still take that cell soon?"""
import sys, os, random, collections
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import sim, fields
import multiprocessing as mp

def job(args):
    names, fam, ms, tok, seed = args
    r = sim.play(names, sim.make_map(fam, ms), token=tok, seed=seed, record=True)
    log = r['log']
    owners = [snap['owner'] for snap, _, _ in log] + [r['final']['owner']]
    out = collections.Counter()
    for t, (snap, chosen, res) in enumerate(log):
        for e in res['events']:
            if e['type'] == 'freeze' and e['why'] == 'caught':
                cell = e['cell']; raider = e['seat']; owner = e['by']
                lvl = 2 if snap['upg'][cell] else 1
                if cell in (0, 7, 63, 56): continue
                horizon = min(len(owners) - 1, t + 1 + 6)
                taken = any(owners[k][cell] == raider for k in range(t + 1, horizon + 1))
                tier = 'E' if names[raider - 1] in fields.DEV_ELITE else 'M' if names[raider - 1] in fields.DEV_MID else 'W'
                out[(lvl, tier, 'n')] += 1; out[(lvl, tier, 'taken')] += taken
                out[(lvl, 'all', 'n')] += 1; out[(lvl, 'all', 'taken')] += taken
    return out

if __name__ == '__main__':
    pool = fields.DEV_ELITE * 3 + fields.DEV_MID * 2 + fields.DEV_WEAK
    rnd = random.Random(79)
    tasks = [([rnd.choice(pool) for _ in range(4)], rnd.choice(sim.FAMILIES), rnd.randrange(10**6), rnd.randint(1, 4), rnd.randrange(10**9)) for g in range(1200)]
    tot = collections.Counter()
    with mp.Pool(4) as p:
        for c in p.imap_unordered(job, tasks, chunksize=4):
            tot.update(c)
    for lvl in (1, 2):
        for tier in ('all', 'E', 'M', 'W'):
            n = tot[(lvl, tier, 'n')]
            print('level', lvl, 'raider tier', tier, 'caught', n, 'took the cell within 6 turns anyway: %.2f' % (tot[(lvl, tier, 'taken')] / max(1, n)))
