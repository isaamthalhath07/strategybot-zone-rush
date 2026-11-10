"""Opening efficiency without interference: each bot plays seat 1 against three bots that
never move. Reports, at turns 15/20/27/35/45, the annuity value score + income*(80-T)
(what the position is worth if nothing more is done), averaged over maps.
  python3 lab/scratch/opening.py IDLE_PATH bot1 bot2 ... [--maps 26]
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import sim
import multiprocessing as mp
FAMS = sim.FAMILIES + sim.NEW_FAMILIES
TS = (10, 15, 20, 27, 35, 45)

def job(t):
    fam, ms, name, idle = t
    base = sim.make_map(fam, ms)
    r = sim.play([name, idle, idle, idle], base, token=1 + ms % 4, seed=ms, record=True)
    out = []
    for T in TS:
        snap = r['log'][T][0]          # board before turn T+1 = after T turns
        inc = sum(base[c] * (2 if snap['upg'][c] else 1) for c in range(64) if snap['owner'][c] == 1)
        out.append(snap['score'][0] + inc * (80 - T))
    return name, fam, out

if __name__ == '__main__':
    args = sys.argv[1:]
    maps = 26
    if '--maps' in args:
        i = args.index('--maps'); maps = int(args[i + 1]); del args[i:i + 2]
    idle = args[0]; bots = args[1:]
    tasks = [(FAMS[m % len(FAMS)], 2000 + m, b, idle) for m in range(maps) for b in bots]
    agg = {b: [0.0] * len(TS) for b in bots}
    fam_agg = {}
    with mp.Pool(4) as pool:
        for name, fam, out in pool.imap_unordered(job, tasks):
            for k, val in enumerate(out):
                agg[name][k] += val / maps
            fam_agg.setdefault(fam, {}).setdefault(name, []).append(out[3])
    print('%-22s' % 'annuity value at turn' + ''.join('%9d' % T for T in TS))
    for b in bots:
        print('%-22s' % b[-22:] + ''.join('%9.0f' % x for x in agg[b]))
    print('\nat turn 27 by family')
    for fam in sorted(fam_agg):
        print('  %-10s' % fam + ''.join('%8.0f' % (sum(fam_agg[fam][b]) / len(fam_agg[fam][b])) for b in bots))
