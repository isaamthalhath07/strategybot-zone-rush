"""Does "rivals have raided un-upgraded land" predict where the cautious bot beats zr6?
For each fixture: play zr6 and record how many level-1 cells rivals took (from anyone)
by turns 20/30/40, then play zr8 on the same fixture. Reports mean zr8 - zr6 by signal.
  python3 lab/scratch/raid_signal.py [--maps 40] [--seed 91]
"""
import sys, os, json, collections
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import sim, arena, suite2, fields, final_test
import multiprocessing as mp
TS = (20, 30, 40, 50)

def job(t):
    names = list(t['opponents']); names.insert(t['seat'], 'zr6')
    base = sim.make_map(t['family'], t['mapseed'])
    r = sim.play(names, base, token=t['token'], seed=t['seed'], record=True)
    me = t['seat'] + 1
    sig = {T: 0 for T in TS}; mine = {T: 0 for T in TS}
    for snap, chosen, res in r['log']:
        for e in res['events']:
            if e['type'] == 'raid' and e['level'] == 1 and e['seat'] != me:
                for T in TS:
                    if snap['turn'] <= T:
                        sig[T] += 1
                        if e['from'] == me:
                            mine[T] += 1
    names[t['seat']] = 'zr8'
    r2 = sim.play(names, base, token=t['token'], seed=t['seed'])
    return t['field'], sig, mine, r['pw'][t['seat']], r2['pw'][t['seat']]

if __name__ == '__main__':
    args = sys.argv[1:]
    opt = {'--maps': '40', '--seed': '91'}
    for k in list(opt):
        if k in args:
            i = args.index(k); opt[k] = args[i + 1]; del args[i:i + 2]
    g = suite2.groups()
    ext2 = dict(final_test.test_fields('EXT2', 'zr8'))
    plan = [('seen elite', fields.HOLDOUT_ELITE + fields.DEV_ELITE), ('seen mid', g['mid']), ('seen weak', g['weak']),
            ('ext2 generated', ext2['generated']), ('ext2 strong', ext2['other_designs']), ('ext2 pasted', ext2['ai_pasted'])]
    tasks = []
    for k, (name, field) in enumerate(plan):
        for f in arena.fixtures(field, maps=int(opt['--maps']), seed=int(opt['--seed']) + k, families=suite2.FAMS):
            tasks.append(dict(f, field=name))
    rows = []
    with mp.Pool(4) as p:
        for row in p.imap_unordered(job, tasks, chunksize=4):
            rows.append(row)
    json.dump(rows, open('/tmp/claude-0/-home-user-strategybot-zone-rush/2bf0c03c-b809-500a-af84-87522d84d019/scratchpad/signal.json', 'w'))
    for name, _ in plan:
        sub = [r for r in rows if r[0] == name]
        print('\n%s: %d games, zr6 %.3f, zr8 %.3f' % (name, len(sub), sum(r[3] for r in sub) / len(sub), sum(r[4] for r in sub) / len(sub)))
        for T in TS:
            line = '  by turn %d, level-1 raids by rivals:' % T
            for lo, hi, lab in ((0, 0, '0'), (1, 1, '1'), (2, 3, '2-3'), (4, 99, '4+')):
                s2 = [r for r in sub if lo <= r[1][T] <= hi]
                if s2:
                    line += '  %s: n=%d d=%+.2f' % (lab, len(s2), sum(r[4] - r[3] for r in s2) / len(s2))
            print(line)
        for T in (30, 40):
            line = '  by turn %d, MY level-1 cells lost:' % T
            for lo, hi, lab in ((0, 0, '0'), (1, 1, '1'), (2, 99, '2+')):
                s2 = [r for r in sub if lo <= r[2][T] <= hi]
                if s2:
                    line += '  %s: n=%d d=%+.2f' % (lab, len(s2), sum(r[4] - r[3] for r in s2) / len(s2))
            print(line)
