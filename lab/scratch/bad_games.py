"""Compare the candidate's profile in games it wins vs games it finishes 3rd/4th."""
import sys, os, collections
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import sim, diag, arena, fields
import multiprocessing as mp

def job(t):
    names = list(t['opponents']); names.insert(t['seat'], t['cand'])
    r = sim.play(names, sim.make_map(t['family'], t['mapseed']), token=t['token'], seed=t['seed'], record=True)
    c = dict(diag.profile(r, t['seat']))
    # failed feints: abandoned progress events on rival land not followed by a backfire
    return r['pw'][t['seat']], c, t['family'], t['seat'], [n for n in t['opponents']], r['scores']

if __name__ == '__main__':
    cand = sys.argv[1]
    fx = arena.fixtures(fields.DEV_ELITE, maps=100, seed=4242)
    tasks = [dict(f, cand=cand) for f in fx]
    groups = {'win(3)': [], '2nd(2)': [], 'bad(<=1)': []}
    fam = collections.defaultdict(lambda: [0, 0.0])
    seatpw = collections.defaultdict(lambda: [0, 0.0])
    with mp.Pool(4) as p:
        for pw, c, family, seat, opp, scores in p.imap_unordered(job, tasks, chunksize=4):
            key = 'win(3)' if pw >= 2.5 else '2nd(2)' if pw >= 1.5 else 'bad(<=1)'
            groups[key].append(c)
            fam[family][0] += 1; fam[family][1] += pw
            seatpw[seat][0] += 1; seatpw[seat][1] += pw
    print('share:', {k: len(v) for k, v in groups.items()})
    print('by map family:', {k: round(v[1]/v[0], 2) for k, v in fam.items()})
    print('by seat:', {k: round(v[1]/v[0], 2) for k, v in sorted(seatpw.items())})
    keys = ['score', 'income_early', 'income_mid', 'income_late', 'final_cells', 'final_upgraded', 'claims', 'upgrades', 'raids', 'raid_bonus',
            'raids_L1', 'raids_L2', 'lost_cells', 'lost_bonus', 'lost_L1', 'lost_L2', 'shield', 'catches', 'backfires', 'got_caught',
            'frozen_turns', 'move', 'idle_stay', 'abandoned_progress']
    print('%-20s' % 'key', ' '.join('%10s' % k for k in groups))
    for k in keys:
        print('%-20s' % k, ' '.join('%10.1f' % (sum(c.get(k, 0) for c in g) / max(1, len(g))) for g in groups.values()))
