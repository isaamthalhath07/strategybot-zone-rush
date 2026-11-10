"""Profile focal bots on chosen map families against the strong known field.
  python3 lab/prof_fam.py edges,flat cand1 cand2 ... [--maps 24] [--field strong|dev|all]
"""
import sys, os, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sim, diag, arena, fields, h2h_strong, prof
import multiprocessing as mp

if __name__ == '__main__':
    args = sys.argv[1:]
    maps = 24; fname = "strong"
    if '--maps' in args:
        i = args.index('--maps'); maps = int(args[i+1]); del args[i:i+2]
    if '--field' in args:
        i = args.index('--field'); fname = args[i+1]; del args[i:i+2]
    fams = tuple(args[0].split(',')); cands = args[1:]
    import suite2
    g = suite2.groups()
    field = {"strong": g["strong"], "mid": g["mid"], "weak": g["weak"], "dev": fields.DEV_ALL,
             "elite": fields.DEV_ELITE}[fname]
    fx = arena.fixtures(field, maps=maps, seed=31, families=fams)
    tasks = [dict(f, cand=c) for f in fx for c in cands]
    agg = {c: [0, collections.Counter(), 0.0] for c in cands}
    with mp.Pool(4) as pool:
        for cand, c, pw in pool.imap_unordered(prof.job, tasks, chunksize=4):
            a = agg[cand]; a[0] += 1; a[1].update(c); a[2] += pw
    print('%-20s' % 'key', ' '.join('%12s' % n[-12:] for n in cands))
    print('%-20s' % 'PW', ' '.join('%12.3f' % (agg[n][2] / agg[n][0]) for n in cands))
    for k in diag.KEYS:
        print('%-20s' % k, ' '.join('%12.1f' % (agg[n][1][k] / agg[n][0]) for n in cands))
