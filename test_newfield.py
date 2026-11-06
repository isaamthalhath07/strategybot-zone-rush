"""
The newfield agents wrap act() in try/except and fall back to STAY, so a broken
agent looks healthy and just plays badly -- which would quietly make the benchmark
easier. Call each one directly, without the wrapper, and fail on any exception or
illegal action.
"""
import random

import engine
import newfield
import zoo

bad = 0
for cls in newfield.NEWFIELD:
    errs = illegal = 0
    for s in range(6):
        rnd = random.Random(s)
        ms = rnd.randrange(4)
        g = engine.Game(base=engine.make_map(seed=900 + s), start_token=rnd.randint(1, 4))
        others = [zoo.SpineFarmerBot, zoo.RaiderBot, zoo.BaiterBot]
        bots = [cls(s) if i == ms else others[i % 3](s * 4 + i) for i in range(4)]
        while not g.over():
            vs = g.views()
            acts = []
            for i in range(4):
                if i == ms:
                    b = bots[i]
                    try:
                        b.observe(vs[i])
                        a = vs[i].legal_actions[0] if len(vs[i].legal_actions) == 1 \
                            else b.act(vs[i])
                    except Exception as e:
                        errs += 1
                        a = "STAY"
                    b.last = a
                    if a not in vs[i].legal_actions:
                        illegal += 1
                        a = "STAY"
                else:
                    a = bots[i](vs[i])
                acts.append(a)
            g.step(acts)
    ok = errs == 0 and illegal == 0
    bad += 0 if ok else 1
    print("  %-8s %s  (%d exceptions, %d illegal actions)"
          % (cls.name, "OK " if ok else "BAD", errs, illegal))
print("ALL NEWFIELD AGENTS OK" if not bad else "%d AGENTS BROKEN" % bad)
