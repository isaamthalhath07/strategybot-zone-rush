"""Behavioural audit of one bot: crashes, illegal actions, idling, pacing, timing.
  python3 lab/audit.py BOT [games]
Plays BOT in every seat against random development opponents (slow ones included).
"""
import sys, os, random, types, time, json, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sim, fields
import multiprocessing as mp
from referee import Referee

SLOW = ['a_apex_bot_641c90', 'a_bot_d2bef4', 'a_forward_fixed_95da83']
REV = {"NORTH": "SOUTH", "SOUTH": "NORTH", "EAST": "WEST", "WEST": "EAST"}

def job(args):
    bot, names, fam, ms, tok, seed, seat = args
    random.seed(seed)
    kind, ref = sim.resolve(bot)
    mod = types.ModuleType('bot'); exec(compile(open(ref).read(), ref, 'exec'), mod.__dict__)
    actors = [sim.make_actor(n, seed + i) for i, n in enumerate(names)]
    actors[seat] = mod.act
    g = Referee(sim.make_map(fam, ms), start_token=tok)
    c = collections.Counter()
    last = None
    worst = 0.0
    while not g.over():
        st = sim.build_states(g)
        acts = []
        for i in range(4):
            t0 = time.perf_counter()
            try:
                a = actors[i](st[i])
            except Exception:
                a = 'STAY'
                if i == seat: c['raised'] += 1
            dt = (time.perf_counter() - t0) * 1000
            if i == seat:
                worst = max(worst, dt)
                if a not in st[i].legal_actions:
                    c['illegal'] += 1
            if a not in st[i].legal_actions:
                a = 'STAY'
            acts.append(a)
        a = acts[seat]
        frozen = g.frozen[seat] > 0
        out = g.step(acts)
        if not frozen:
            c['turns'] += 1
            productive = any(e.get('seat') == seat + 1 and e['type'] in ('claim', 'upgrade', 'progress', 'raid') for e in out['events'])
            if a == 'STAY' and not productive: c['idle'] += 1
            if a in REV and last == REV[a]: c['reversal'] += 1
            if a in REV: c['moves'] += 1
            last = a if a in REV else None
    m = getattr(mod, '_M', None)
    c['errors'] = getattr(m, 'errors', 0) if m is not None else 0
    c['scaled'] = int(getattr(m, 'scale', 1.0) < 1.0) if m is not None else 0
    c['unexplained'] = getattr(m, 'unexplained', 0) if m is not None else 0
    c['games'] = 1
    c['pw'] = sum(1.0 if g.score[seat] > s else 0.5 if g.score[seat] == s else 0 for j, s in enumerate(g.score) if j != seat)
    return c, worst

if __name__ == '__main__':
    bot = sys.argv[1]
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 300
    pool = fields.DEV_ALL + SLOW
    rnd = random.Random(31)
    tasks = []
    for k in range(n):
        names = [rnd.choice(pool) for _ in range(4)]
        tasks.append((bot, names, rnd.choice(sim.FAMILIES), rnd.randrange(10**6), rnd.randint(1, 4), rnd.randrange(10**9), k % 4))
    tot = collections.Counter(); worst = 0.0
    with mp.Pool(4) as p:
        for c, w in p.imap_unordered(job, tasks, chunksize=2):
            tot.update(c); worst = max(worst, w)
    g = tot['games']
    print('%s: %d games, mean PW %.3f' % (bot, g, tot['pw'] / g))
    print('raised %d  illegal %d  internal errors %d  search scaled down in %d games  unexplained freezes %d' % (tot['raised'], tot['illegal'], tot['errors'], tot['scaled'], tot['unexplained']))
    print('idle stays %.1f%% of free turns, reversals %.1f%% of moves, worst call %.1f ms' % (100.0 * tot['idle'] / tot['turns'], 100.0 * tot['reversal'] / max(1, tot['moves']), worst))
