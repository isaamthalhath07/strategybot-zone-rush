"""Print a compact timeline for one seat: python3 lab/trace.py seat name1 name2 name3 name4 [family mapseed token seed]"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sim
def trace(names, seat=0, family='example', mapseed=0, token=1, seed=3, full=True):
    base = sim.make_map(family, mapseed)
    r = sim.play(names, base, token=token, seed=seed, record=True)
    print(names, r['scores'], 'pw', r['pw'])
    for snap, chosen, out in r['log']:
        t = snap['turn']; p = snap['pos'][seat]
        ev = []
        for e in out['events']:
            ty = e['type']
            if ty in ('claim', 'upgrade') and e['seat'] == seat + 1: ev.append(ty[0].upper())
            elif ty == 'raid' and e['seat'] == seat + 1: ev.append('RAID+%d(from %d)' % (e['bonus'], e['from']))
            elif ty == 'raid' and e['from'] == seat + 1: ev.append('LOST %d,%d L%d to %d' % (e['cell'] // 8, e['cell'] % 8, e['level'], e['seat']))
            elif ty == 'shield': ev.append('shield by %d caught %s%s' % (e['seat'], e['caught'], ' BACKFIRE' if e['backfire'] else ''))
            elif ty == 'reset' and e['seat'] == seat + 1 and e['why'] == 'moved': ev.append('abandon%d' % e['lost'])
        o = snap['owner'][p]
        print('%2d %-6s @%d,%d own=%d%s prog=%d cd=%s fr=%s inc=%s  %s' % (
            t, chosen[seat], p // 8, p % 8, o, 'U' if snap['upg'][p] else '.', snap['prog'][seat], snap['cd'], snap['frozen'],
            snap['income'], '; '.join(ev)))
    fin = r['final']
    for rr in range(8):
        print(' '.join('%d%s%d' % (fin['owner'][rr * 8 + c], 'U' if fin['upg'][rr * 8 + c] else '.', base[rr * 8 + c]) for c in range(8)))
    return r
if __name__ == '__main__':
    a = sys.argv[1:]
    seat = int(a[0]); names = a[1:5]
    extra = a[5:]
    kw = {}
    if len(extra) >= 1: kw['family'] = extra[0]
    if len(extra) >= 2: kw['mapseed'] = int(extra[1])
    if len(extra) >= 3: kw['token'] = int(extra[2])
    if len(extra) >= 4: kw['seed'] = int(extra[3])
    trace(names, seat, **kw)
