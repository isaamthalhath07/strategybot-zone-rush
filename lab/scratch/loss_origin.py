"""Where do the candidate's lost cells come from? (offline analysis with referee truth)"""
import sys, os, collections
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import sim, arena, fields
import multiprocessing as mp

def job(t):
    names = list(t['opponents']); names.insert(t['seat'], t['cand'])
    r = sim.play(names, sim.make_map(t['family'], t['mapseed']), token=t['token'], seed=t['seed'], record=True)
    me = t['seat'] + 1
    acquired = {}
    out = collections.Counter()
    for snap, chosen, res in r['log']:
        turn = snap['turn']
        for e in res['events']:
            if e['type'] == 'claim' and e['seat'] == me:
                acquired[e['cell']] = ('claim', turn)
            elif e['type'] == 'raid' and e['seat'] == me:
                acquired[e['cell']] = ('raid', turn)
            elif e['type'] == 'raid' and e['from'] == me:
                how, t0 = acquired.get(e['cell'], ('?', 0))
                age = turn - t0
                lvl = e['level']
                phase = 'early' if turn <= 27 else 'mid' if turn <= 54 else 'late' if turn <= 72 else 'end'
                out[('L%d' % lvl, how, 'age<=3' if age <= 3 else 'age<=8' if age <= 8 else 'age>8')] += 1
                out[('L%d' % lvl, 'phase', phase)] += 1
                # could I shield? where was I?
                d = abs(snap['pos'][me-1]//8 - e['cell']//8) + abs(snap['pos'][me-1]%8 - e['cell']%8)
                out[('L%d' % lvl, 'mycd', 'ready' if snap['cd'][me-1] == 0 and not snap['frozen'][me-1] else 'notready')] += 1
                out[('L%d' % lvl, 'mydist', min(d, 4))] += 1
                out[('L%d' % lvl, 'bonus')] += e['bonus']
    out['games'] = 1
    return out

if __name__ == '__main__':
    cand = sys.argv[1]
    field = getattr(fields, sys.argv[2]) if len(sys.argv) > 2 else fields.DEV_ELITE
    fx = arena.fixtures(field, maps=40, seed=21)
    tasks = [dict(f, cand=cand) for f in fx]
    tot = collections.Counter()
    with mp.Pool(4) as p:
        for c in p.imap_unordered(job, tasks, chunksize=4):
            tot.update(c)
    g = tot.pop('games')
    for k in sorted(tot, key=str):
        print('%-40s %.2f per game' % (str(k), tot[k] / g))
