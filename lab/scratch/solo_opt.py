"""Offline: how good can pure economics get? Time-bucketed beam search for one bot alone."""
import sys, os, heapq
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import sim

def solve(base, home, allowed, T=80, K=3000, verbose=False):
    D = [[abs(a//8-b//8)+abs(a%8-b%8) for b in range(64)] for a in range(64)]
    cells = sorted(allowed)
    # state tuple: (score, income, pos, owned, upg, plan)
    buckets = [dict() for _ in range(T+2)]
    start = (0, base[home], home, 1 << home, 0, ())
    buckets[0][(home, 1 << home, 0)] = start
    best = None
    for t in range(T+1):
        states = buckets[t]
        if not states:
            continue
        # rank by projected final if idle + optimism
        items = sorted(states.values(), key=lambda s: -(s[0] + s[1]*(T-t)))[:K]
        for score, income, pos, owned, upg, plan in items:
            fin = score + income*(T-t)
            if best is None or fin > best[0]:
                best = (fin, plan, owned, upg)
            for c in cells:
                bit = 1 << c
                if upg & bit:
                    continue
                d = D[pos][c]
                if owned & bit:
                    work = 3; v = base[c]
                    done = t + d + work
                    if done > T: continue
                    ns = score + income*(d+work-1) + (income+v)   # completes on turn index done (1-based), scored that turn
                    key = (c, owned, upg | bit)
                    st = (ns, income+v, c, owned, upg | bit, plan + (('U', c, done),))
                else:
                    work = 1; v = base[c]
                    done = t + d + work
                    if done > T: continue
                    ns = score + income*(d+work-1) + (income+v)
                    key = (c, owned | bit, upg)
                    st = (ns, income+v, c, owned | bit, upg, plan + (('C', c, done),))
                b = buckets[done]
                old = b.get(key)
                if old is None or old[0] < st[0]:
                    b[key] = st
    return best

if __name__ == '__main__':
    base = sim.make_map('example', 0)
    K = int(sys.argv[1]) if len(sys.argv) > 1 else 2000
    quad = [r*8+c for r in range(4) for c in range(4)]
    b = solve(base, 0, quad, K=K)
    print('quadrant-only optimum ~', b[0], 'cells', bin(b[2]).count('1'), 'upg', bin(b[3]).count('1'))
    print(' '.join('%s%d,%d@%d' % (k, c//8, c%8, t) for k, c, t in b[1]))
    region = [r*8+c for r in range(5) for c in range(5)]
    b = solve(base, 0, region, K=K)
    print('5x5 region optimum ~', b[0], 'cells', bin(b[2]).count('1'), 'upg', bin(b[3]).count('1'))
    print(' '.join('%s%d,%d@%d' % (k, c//8, c%8, t) for k, c, t in b[1]))
    b = solve(base, 0, list(range(64)), K=K)
    print('whole-board solo optimum ~', b[0], 'cells', bin(b[2]).count('1'), 'upg', bin(b[3]).count('1'))
    print(' '.join('%s%d,%d@%d' % (k, c//8, c%8, t) for k, c, t in b[1]))
