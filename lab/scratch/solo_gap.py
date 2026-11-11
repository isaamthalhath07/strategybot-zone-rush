"""How close does a bot get to the best possible undisturbed economy?
  python3 lab/scratch/solo_gap.py IDLE_BOT_PATH bot1 bot2 ... [--maps 13]
Each bot plays seat 1 against three bots that never move. The offline beam search
(solo_opt.solve) gives a lower bound on the best score from the home quadrant alone and
from the whole board. Shows mean score per bot next to both bounds.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sim, solo_opt
import multiprocessing as mp

FAMS = sim.FAMILIES + sim.NEW_FAMILIES

def job(t):
    kind, fam, ms, name, idle = t
    base = sim.make_map(fam, ms)
    if kind == 'opt':
        quad = [r * 8 + c for r in range(4) for c in range(4)]
        q = solo_opt.solve(base, 0, quad, K=1200)[0]
        return ('opt', fam, ms, q)
    r = sim.play([name, idle, idle, idle], base, token=1, seed=ms)
    return (name, fam, ms, r['scores'][0])

if __name__ == '__main__':
    args = sys.argv[1:]
    maps = 13
    if '--maps' in args:
        i = args.index('--maps'); maps = int(args[i + 1]); del args[i:i + 2]
    idle = args[0]; bots = args[1:]
    tasks = []
    for m in range(maps):
        fam = FAMS[m % len(FAMS)]
        tasks.append(('opt', fam, 1000 + m, None, idle))
        for b in bots:
            tasks.append(('bot', fam, 1000 + m, b, idle))
    res = {}
    with mp.Pool(4) as pool:
        for name, fam, ms, sc in pool.imap_unordered(job, tasks):
            res.setdefault((fam, ms), {})[name] = sc
    print('%-16s %8s' % ('map', 'quadOpt') + ''.join('%14s' % b[-13:] for b in bots))
    tot = {b: 0.0 for b in bots}; n = 0
    for key in sorted(res):
        row = res[key]
        print('%-16s %8d' % ('%s/%d' % key, row['opt']) + ''.join('%14d' % row[b] for b in bots))
        for b in bots:
            tot[b] += row[b] - row['opt']
        n += 1
    print('%-16s %8s' % ('mean vs quadOpt', '') + ''.join('%+14.0f' % (tot[b] / n) for b in bots))
