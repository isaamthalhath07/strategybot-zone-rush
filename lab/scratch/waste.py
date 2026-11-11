"""Where do the focal bot's wasted turns go? Abandoned progress (by job type and why)
and unproductive STAYs (by what it was standing on), per game.
  python3 lab/scratch/waste.py cand [--field strong] [--maps 60] [--seed 52]
"""
import sys, os, collections
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import sim, arena, suite2
import multiprocessing as mp


def job(t):
    names = list(t['opponents']); names.insert(t['seat'], t['cand'])
    r = sim.play(names, sim.make_map(t['family'], t['mapseed']), token=t['token'], seed=t['seed'], record=True)
    me = t['seat'] + 1; i = me - 1
    out = collections.Counter()
    for snap, chosen, res in r['log']:
        turn = snap['turn']
        ph = 't<=27' if turn <= 27 else 't28-54' if turn <= 54 else 't55-70' if turn <= 70 else 't71-80'
        p = snap['pos'][i]; o = snap['owner'][p]; a = chosen[i]
        land = 'own L1' if o == me and not snap['upg'][p] else 'own L2' if o == me else 'neutral' if o == 0 else (
            'rival L2' if snap['upg'][p] else 'rival L1')
        prod = False; caught = False
        for e in res['events']:
            if e.get('seat') == me and e['type'] in ('claim', 'upgrade', 'progress', 'raid'):
                prod = True
            if e['type'] == 'freeze' and e['seat'] == me:
                caught = True
            if e['type'] == 'reset' and e['seat'] == me and e['why'] == 'moved' and e['lost'] > 0:
                out['abandon %s (%s)' % (land, ph)] += e['lost']
                shielded_owner = any(x['type'] == 'shield' and x['seat'] == o for x in res['events'])
                out['abandon %s: owner shielded that turn=%s' % (land, shielded_owner)] += e['lost']
        if snap['frozen'][i] == 0 and a == 'STAY' and not prod:
            out['idle on %s (%s)%s' % (land, ph, ' caught' if caught else '')] += 1
        if a == 'SHIELD':
            got = [e for e in res['events'] if e['type'] == 'shield' and e['seat'] == me]
            if got:
                out['shield %s (%s)' % ('backfire' if got[0]['backfire'] else 'catch %d' % len(got[0]['caught']), ph)] += 1
    out['games'] = 1
    return out

if __name__ == '__main__':
    args = sys.argv[1:]
    opt = {'--field': 'strong', '--maps': '60', '--seed': '52'}
    for k in list(opt):
        if k in args:
            i = args.index(k); opt[k] = args[i + 1]; del args[i:i + 2]
    field = suite2.groups()[opt['--field']]
    fx = arena.fixtures(field, maps=int(opt['--maps']), seed=int(opt['--seed']), families=suite2.FAMS)
    tot = collections.Counter()
    with mp.Pool(4) as p:
        for c in p.imap_unordered(job, [dict(f, cand=args[0]) for f in fx], chunksize=4):
            tot.update(c)
    g = tot.pop('games')
    print('%s vs %s: %d games' % (args[0], opt['--field'], g))
    for k in sorted(tot):
        print('  %-52s %.3f/game' % (k, tot[k] / g))
