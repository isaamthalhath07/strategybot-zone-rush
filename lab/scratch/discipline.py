"""Is "a rival keeps its own land upgraded" an early sign of the groups where caution pays?
For every rival seat: share of its non-home cells that sit un-upgraded and unattended at
turns 12/16/20/26 (averaged), by opponent group.
  python3 lab/scratch/discipline.py [--maps 20] [--seed 95]
"""
import sys, os, collections
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import sim, arena, suite3
import multiprocessing as mp
HOME = (0, 7, 56, 63)
TS = (12, 16, 20, 26)

def job(t):
    names = list(t['opponents']); names.insert(t['seat'], 'zr6')
    r = sim.play(names, sim.make_map(t['family'], t['mapseed']), token=t['token'], seed=t['seed'], record=True)
    out = []
    for j in range(4):
        if j == t['seat']:
            continue
        row = []
        for T in TS:
            snap = r['log'][T][0]
            own = [c for c in range(64) if snap['owner'][c] == j + 1 and c not in HOME]
            bare = [c for c in own if not snap['upg'][c] and snap['pos'][j] != c]
            row.append((len(own), len(bare)))
        out.append((names[j], row))
    return t['group'], out

if __name__ == '__main__':
    args = sys.argv[1:]
    opt = {'--maps': '20', '--seed': '95'}
    for k in list(opt):
        if k in args:
            i = args.index(k); opt[k] = args[i + 1]; del args[i:i + 2]
    tasks = []
    for k, (name, field) in enumerate(suite3.groups()[:-1]):
        for f in arena.fixtures(field, maps=int(opt['--maps']), seed=int(opt['--seed']) + k, families=suite3.FAMS):
            tasks.append(dict(f, group=name))
    agg = collections.defaultdict(list)
    bybot = collections.defaultdict(list)
    with mp.Pool(4) as p:
        for group, out in p.imap_unordered(job, tasks, chunksize=4):
            for name, row in out:
                agg[group].append(row); bybot[(group, name)].append(row)
    print('%-12s' % 'group' + ''.join('  t%-2d: cells bare  ' % T for T in TS) + '   rivals with <=1 bare cell at t20')
    for group, _ in suite3.groups()[:-1]:
        rows = agg[group]
        line = '%-12s' % group
        for k in range(len(TS)):
            line += '       %4.1f %4.1f   ' % (sum(r[k][0] for r in rows) / len(rows), sum(r[k][1] for r in rows) / len(rows))
        line += '    %.2f' % (sum(1 for r in rows if r[2][1] <= 1) / len(rows))
        print(line)
    print('\nper bot at turn 20: mean bare cells (n)')
    for group, _ in suite3.groups()[:-1]:
        items = sorted((sum(r[2][1] for r in rows) / len(rows), name) for (g, name), rows in bybot.items() if g == group)
        print('%-12s' % group + ' '.join('%s=%.1f' % (n.replace('legacy:', '')[:14], v) for v, n in items))
