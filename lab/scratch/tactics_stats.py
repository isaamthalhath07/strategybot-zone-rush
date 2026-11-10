"""Population statistics for raid/shield behaviour (uses referee truth; offline analysis only)."""
import sys, os, random, collections, json
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import sim, fields
import multiprocessing as mp

def job(args):
    names, fam, ms, tok, seed = args
    r = sim.play(names, sim.make_map(fam, ms), token=tok, seed=seed, record=True)
    out = []
    home = {0, 7, 63, 56}
    for snap, chosen, res in r['log']:
        pos, owner, upg, frozen, cd, prog, turn = snap['pos'], snap['owner'], snap['upg'], snap['frozen'], snap['cd'], snap['prog'], snap['turn']
        for i in range(4):
            p = pos[i]; o = owner[p]
            if o and o != i+1 and p not in home and not frozen[i]:
                d = o-1
                # raider i is on defender d's (non-home) cell at start of turn
                lvl = 2 if upg[p] else 1
                can = (cd[d] == 0 and not frozen[d])
                out.append(('enc', names[i], names[d], lvl, prog[i], can, chosen[i] == 'STAY', chosen[i] in ('NORTH','EAST','SOUTH','WEST'),
                            chosen[d] == 'SHIELD', turn))
        # raid opportunity: bot i adjacent (dist 1) to a rival L1 non-home empty cell
        occ = set(pos)
        for i in range(4):
            if frozen[i]: continue
            p = pos[i]
            near = False
            for q in (p-8, p+8, p-1, p+1):
                if 0 <= q < 64 and abs(q%8 - p%8) + abs(q//8 - p//8) == 1 and q not in occ and q not in home:
                    if owner[q] and owner[q] != i+1 and not upg[q]:
                        near = True
                        went = False
            if near:
                # did it move onto a rival L1 cell?
                tgt = None
                a = chosen[i]
                dq = {'NORTH': -8, 'SOUTH': 8, 'WEST': -1, 'EAST': 1}.get(a)
                moved_on = False
                if dq is not None:
                    q = p + dq
                    if 0 <= q < 64 and owner[q] and owner[q] != i+1 and not upg[q] and q not in home:
                        moved_on = True
                out.append(('opp', names[i], moved_on, turn))
    return out

if __name__ == '__main__':
    pool = fields.DEV_ELITE * 3 + fields.DEV_MID * 2 + fields.DEV_WEAK
    rnd = random.Random(77)
    tasks = []
    for g in range(1500):
        names = [rnd.choice(pool) for _ in range(4)]
        tasks.append((names, rnd.choice(sim.FAMILIES), rnd.randrange(10**6), rnd.randint(1, 4), rnd.randrange(10**9)))
    enc = collections.defaultdict(lambda: [0, 0, 0, 0])   # key -> n, stay, move, shield
    opp = collections.defaultdict(lambda: [0, 0])
    with mp.Pool(4) as p:
        for rows in p.imap_unordered(job, tasks, chunksize=4):
            for row in rows:
                if row[0] == 'enc':
                    _, rn, dn, lvl, prog, can, stay, move, shield, turn = row
                    for key in (('raider', rn, lvl, min(prog, 2)), ('ALLraider', lvl, min(prog, 2))):
                        e = enc[key]; e[0] += 1; e[1] += stay; e[2] += move
                    if can:
                        for key in (('defender', dn, lvl, min(prog, 2)), ('ALLdefender', lvl, min(prog, 2))):
                            e = enc[key]; e[0] += 1; e[3] += shield
                else:
                    _, n, moved, turn = row
                    o = opp[n]; o[0] += 1; o[1] += moved
                    o = opp['ALL']; o[0] += 1; o[1] += moved
    def tier(n):
        return 'E' if n in fields.DEV_ELITE else 'M' if n in fields.DEV_MID else 'W'
    print('== population: raider on rival cell: P(stay), P(move) by (level, progress)')
    for k in sorted(k for k in enc if k[0] == 'ALLraider'):
        e = enc[k]; print(k, e[0], 'stay %.2f move %.2f' % (e[1]/e[0], e[2]/e[0]))
    print('== population: defender able to shield: P(shield) by (level, raider progress)')
    for k in sorted(k for k in enc if k[0] == 'ALLdefender'):
        e = enc[k]; print(k, e[0], 'shield %.2f' % (e[3]/e[0]))
    print('== per bot defender P(shield): L1 prog0 | L2 prog0 | L2 prog1 | L2 prog2   and raider P(stay) same keys; raid-take rate')
    names = sorted(set(k[1] for k in enc if k[0] in ('raider', 'defender')), key=lambda n: (tier(n), n))
    for n in names:
        def f(kind, lvl, pr, idx):
            e = enc.get((kind, n, lvl, pr))
            return '  -  ' if not e or e[0] < 5 else '%.2f(%d)' % (e[idx]/e[0], e[0])
        o = opp.get(n, [0, 0])
        print('%s %-34s D: %9s %9s %9s %9s | R: %9s %9s %9s %9s | adjL1 take %s' % (
            tier(n), n[:34], f('defender', 1, 0, 3), f('defender', 2, 0, 3), f('defender', 2, 1, 3), f('defender', 2, 2, 3),
            f('raider', 1, 0, 1), f('raider', 2, 0, 1), f('raider', 2, 1, 1), f('raider', 2, 2, 1),
            ('%.2f(%d)' % (o[1]/o[0], o[0])) if o[0] else '-'))
