"""Compare the candidate's public-history tracker with the referee's private counters.

The tracker under test is attached as a passive observer to every seat of games played
by pool bots: it sees exactly what that seat saw and is told that seat's own requested
action, nothing else. Referee truth is used only here, to grade it.
"""
import sys, os, random, types, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sim, fields
import multiprocessing as mp

CAND = None

def load(path):
    mod = types.ModuleType('cand')
    exec(compile(open(path).read(), path, 'exec'), mod.__dict__)
    return mod

def job(args):
    path, names, fam, ms, tok, seed = args
    base = sim.make_map(fam, ms)
    r = sim.play(names, base, token=tok, seed=seed, record=True)
    err = collections.Counter()
    for seat in range(4):
        mod = load(path)
        me = seat + 1
        for k, (snap, chosen, res) in enumerate(r['log']):
            # rebuild the observation this seat received
            class G: pass
            game = G()
            occ = {p: i + 1 for i, p in enumerate(snap['pos'])}
            board = []
            for rr in range(8):
                row = []
                for cc in range(8):
                    p = rr * 8 + cc
                    o = occ.get(p, 0)
                    row.append(sim.Cell(o, snap['owner'][p], bool(snap['upg'][p]), p in (0, 7, 63, 56),
                                        bool(o and snap['frozen'][o - 1] > 0), base[p]))
                board.append(row)
            legal = ['STAY'] if snap['frozen'][seat] > 0 else (['NORTH', 'EAST', 'SOUTH', 'WEST', 'STAY'] + (['SHIELD'] if snap['cd'][seat] == 0 else []))
            st = sim.Game(board, me, snap['token'] == me, legal)
            v = mod._read(st)
            m = mod._update(v)
            err['turns'] += 1
            if m.turn != snap['turn']:
                err['turn'] += 1
            for s in range(1, 5):
                err['seat_turns'] += 1
                if m.scores[s] != snap['score'][s - 1]:
                    err['score'] += 1
                if m.prog[s] != snap['prog'][s - 1]:
                    err['prog'] += 1
                    if s == me: err['prog_self'] += 1
                if m.cd[s] != snap['cd'][s - 1]:
                    err['cd'] += 1
                    if s == me: err['cd_self'] += 1
            if m.token is not None:
                err['token_known'] += 1
                if m.token_holder(m.turn) != snap['token']:
                    err['token_bad'] += 1
            err['unexplained'] = max(err['unexplained'], 0)
            m.last = chosen[seat]
            m.shield_was_legal = 'SHIELD' in legal
        err['unexplained_total'] += m.unexplained
        err['presence_flag'] += m.presence_rule
    return err

if __name__ == '__main__':
    path = os.path.abspath(sys.argv[1])
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 300
    pool = fields.DEV_ELITE * 2 + fields.DEV_MID + fields.DEV_WEAK
    rnd = random.Random(5)
    tasks = [(path, [rnd.choice(pool) for _ in range(4)], rnd.choice(sim.FAMILIES), rnd.randrange(10**6), rnd.randint(1, 4), rnd.randrange(10**9)) for _ in range(n)]
    tot = collections.Counter()
    with mp.Pool(4) as p:
        for e in p.imap_unordered(job, tasks, chunksize=2):
            tot.update(e)
    for k in sorted(tot):
        print('%-20s %d' % (k, tot[k]))
    st = tot['seat_turns']
    print('error rates: score %.5f prog %.5f cd %.5f turn %.5f' % (tot['score']/st, tot['prog']/st, tot['cd']/st, tot['turn']/max(1, tot['turns'])))
