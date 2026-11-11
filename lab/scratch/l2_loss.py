"""How does the focal bot lose upgraded cells? For every level-2 cell taken from it:
was its SHIELD ready on the turn the raid completed, was it frozen (and why), what did
it do instead, and how many raiders were on its land at once.
  python3 lab/scratch/l2_loss.py cand [--field strong] [--maps 60] [--seed 51]
"""
import sys, os, collections
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import sim, arena, suite2
import multiprocessing as mp


def job(t):
    names = list(t['opponents']); names.insert(t['seat'], t['cand'])
    r = sim.play(names, sim.make_map(t['family'], t['mapseed']), token=t['token'], seed=t['seed'], record=True)
    me = t['seat'] + 1
    out = collections.Counter()
    last_shield = None      # (turn, backfired, caught list)
    froze_why = None
    for snap, chosen, res in r['log']:
        turn = snap['turn']
        for e in res['events']:
            if e['type'] == 'shield' and e['seat'] == me:
                last_shield = (turn, e['backfire'], list(e['caught']))
            if e['type'] == 'freeze' and e['seat'] == me:
                froze_why = e['why']
        for e in res['events']:
            if e['type'] != 'raid' or e['from'] != me or e['level'] != 2:
                continue
            out['n'] += 1
            out['bonus'] += e['bonus']
            phase = 'turn<=54' if turn <= 54 else 'turn 55-70' if turn <= 70 else 'turn 71-77' if turn <= 77 else 'turn 78-80'
            out['phase ' + phase] += 1
            raiders = sum(1 for j in range(4) if j != me - 1 and snap['owner'][snap['pos'][j]] == me
                          and snap['pos'][j] not in (0, 7, 56, 63))
            out['raiders on my land: %d' % raiders] += 1
            if snap['frozen'][me - 1] > 0:
                out['state: I was frozen (%s)' % froze_why] += 1
            elif snap['cd'][me - 1] > 0:
                ago = turn - last_shield[0] if last_shield else -1
                tag = 'backfired' if last_shield and last_shield[1] else (
                    'caught same raider' if last_shield and e['seat'] in last_shield[2] else 'caught another')
                out['state: shield cooling (%s)' % tag] += 1
            elif chosen[me - 1] == 'SHIELD':
                out['state: I shielded yet lost (?)'] += 1
            else:
                out['state: shield READY, I played %s' % ('move' if chosen[me - 1] not in ('STAY',) else 'STAY')] += 1
                out['ready-unused in ' + phase] += 1
                out['ready-unused, raider %s' % names[e['seat'] - 1]] += 1
    out['games'] = 1
    return out

if __name__ == '__main__':
    args = sys.argv[1:]
    opt = {'--field': 'strong', '--maps': '60', '--seed': '51'}
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
    print('%s vs %s: %d games, %.2f level-2 cells lost per game, bonus given %.1f per game' % (
        args[0], opt['--field'], g, tot['n'] / g, tot['bonus'] / g))
    for k in sorted(tot):
        if k not in ('n', 'bonus'):
            print('  %-52s %5d  %.3f/game' % (k, tot[k], tot[k] / g))
