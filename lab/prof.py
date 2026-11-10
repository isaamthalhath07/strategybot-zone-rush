"""Profile candidates on a fixture list: python3 lab/prof.py cand1 cand2 ... [--maps N] [--field ELITE]"""
import sys, os, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sim, diag, arena, fields
import multiprocessing as mp

def job(t):
    names = list(t['opponents']); names.insert(t['seat'], t['cand'])
    r = sim.play(names, sim.make_map(t['family'], t['mapseed']), token=t['token'], seed=t['seed'], record=True)
    return t['cand'], dict(diag.profile(r, t['seat'])), r['pw'][t['seat']]

def run(cands, field, maps=30, seed=21, keys=None):
    fx = arena.fixtures(field, maps=maps, seed=seed)
    tasks = [dict(f, cand=c) for f in fx for c in cands]
    agg = {c: [0, collections.Counter(), 0.0] for c in cands}
    with mp.Pool(4) as pool:
        for cand, c, pw in pool.imap_unordered(job, tasks, chunksize=4):
            a = agg[cand]; a[0] += 1; a[1].update(c); a[2] += pw
    print('%-20s' % 'key', ' '.join('%12s' % n[-12:] for n in cands))
    print('%-20s' % 'PW', ' '.join('%12.3f' % (agg[n][2] / agg[n][0]) for n in cands))
    for k in (keys or diag.KEYS):
        print('%-20s' % k, ' '.join('%12.1f' % (agg[n][1][k] / agg[n][0]) for n in cands))
    return agg

if __name__ == '__main__':
    args = sys.argv[1:]
    maps = 30; field = fields.ELITE
    if '--maps' in args:
        i = args.index('--maps'); maps = int(args[i+1]); del args[i:i+2]
    if '--field' in args:
        i = args.index('--field'); field = getattr(fields, args[i+1]); del args[i:i+2]
    run(args, field, maps)
