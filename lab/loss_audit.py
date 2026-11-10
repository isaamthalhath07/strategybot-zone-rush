"""Which of the focal bot's cells get raided, and could it have known?
  python3 lab/loss_audit.py cand [--maps 60] [--field strong|dev|elite]
For every cell the focal bot loses: how it got the cell (claim / raid), its level and
value, the turn, how long it had been held, how far the focal bot and the eventual raider
were from it when the focal bot last left it, and what the focal bot did next.
"""
import sys, os, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sim, arena, fields, h2h_strong
import multiprocessing as mp

D = lambda a, b: abs(a // 8 - b // 8) + abs(a % 8 - b % 8)


def job(t):
    names = list(t['opponents']); names.insert(t['seat'], t['cand'])
    r = sim.play(names, sim.make_map(t['family'], t['mapseed']), token=t['token'], seed=t['seed'], record=True)
    me = t['seat'] + 1
    got = {}          # cell -> (turn, how)
    left = {}         # cell -> (turn, raider_dist_by_seat list, nearest rival dist)
    rows = []
    gains = []
    prevpos = None
    for snap, chosen, out in r['log']:
        turn = snap['turn']
        pos = snap['pos']
        mypos = pos[me - 1]
        if prevpos is not None and prevpos != mypos and snap['owner'][prevpos] == me:
            left[prevpos] = (turn - 1, [D(p, prevpos) for p in pos], snap['upg'][prevpos])
        prevpos = mypos
        for e in out['events']:
            if e['type'] == 'claim' and e['seat'] == me:
                got[e['cell']] = (turn, 'claim')
            elif e['type'] == 'raid':
                c = e['cell']
                if e['seat'] == me:
                    got[c] = (turn, 'raid')
                    gains.append((turn, e['level'], e['base'], e['bonus']))
                elif e['from'] == me:
                    g = got.get(c, (0, 'home?'))
                    lf = left.get(c)
                    rows.append(dict(turn=turn, level=e['level'], base=e['base'], how=g[1], held=turn - g[0],
                                     since_left=(turn - lf[0]) if lf else -1,
                                     raider_d_at_leave=(lf[1][e['seat'] - 1] if lf else -1),
                                     my_d=D(mypos, c), fam=t['family'], raider=names[e['seat'] - 1]))
    return rows, gains, r['pw'][t['seat']]


if __name__ == '__main__':
    args = sys.argv[1:]
    maps = 60; fname = 'strong'
    if '--maps' in args:
        i = args.index('--maps'); maps = int(args[i+1]); del args[i:i+2]
    if '--field' in args:
        i = args.index('--field'); fname = args[i+1]; del args[i:i+2]
    cand = args[0]
    field = {"strong": h2h_strong.strong_field(), "dev": fields.DEV_ALL, "elite": fields.DEV_ELITE}[fname]
    fx = arena.fixtures(field, maps=maps, seed=41, families=sim.FAMILIES + sim.NEW_FAMILIES)
    tasks = [dict(f, cand=cand) for f in fx]
    rows = []; games = 0; gains = []
    with mp.Pool(4) as pool:
        for rr, gg, pw in pool.imap_unordered(job, tasks, chunksize=4):
            rows += rr; gains += gg; games += 1
    n = float(games)
    print('%s: %d games, %.2f cells lost per game, %.2f raids made per game' % (cand, games, len(rows) / n, len(gains) / n))

    def tab(title, key, order=None):
        c = collections.Counter(key(x) for x in rows)
        pts = collections.Counter()
        for x in rows:
            pts[key(x)] += 8 * x['base'] * x['level']
        print('\n' + title)
        for k in (order or sorted(c)):
            if c[k]:
                print('  %-22s %.2f per game   bonus given %.1f per game' % (k, c[k] / n, pts[k] / n))
    tab('by level and how the cell was obtained', lambda x: 'L%d via %s' % (x['level'], x['how']))
    tab('level-1 cells that had been CLAIMED: turns since the bot last stood on them',
        lambda x: ('n/a' if x['level'] != 1 or x['how'] != 'claim' else
                   '1-3' if x['since_left'] <= 3 else '4-8' if x['since_left'] <= 8 else '9-20' if x['since_left'] <= 20 else '21+'),
        ['1-3', '4-8', '9-20', '21+'])
    tab('level-1 claimed: raider distance when the bot left the cell',
        lambda x: ('n/a' if x['level'] != 1 or x['how'] != 'claim' else 'd=%d' % min(7, x['raider_d_at_leave'])),
        ['d=%d' % k for k in range(1, 8)])
    tab('level-1 cells obtained by RAID: turns held before being retaken',
        lambda x: ('n/a' if x['level'] != 1 or x['how'] != 'raid' else
                   '1-3' if x['held'] <= 3 else '4-8' if x['held'] <= 8 else '9-20' if x['held'] <= 20 else '21+'),
        ['1-3', '4-8', '9-20', '21+'])
    tab('by game phase', lambda x: 'early' if x['turn'] <= 27 else 'mid' if x['turn'] <= 54 else 'late 55-70' if x['turn'] <= 70 else 'last ten')
    tab('by cell value', lambda x: 'base %d' % x['base'])
    c = collections.Counter(x['raider'] for x in rows)
    print('\nmost frequent raiders:', ', '.join('%s %d' % kv for kv in c.most_common(8)))
    g1 = [g for g in gains if g[1] == 1]; g2 = [g for g in gains if g[1] == 2]
    print('raids made: L1 %.2f/game (+%.1f), L2 %.2f/game (+%.1f)' % (len(g1) / n, sum(g[3] for g in g1) / n, len(g2) / n, sum(g[3] for g in g2) / n))
