"""
Is any bot seat-biased?

The map is 4-fold mirrored, so four copies of the SAME bot must average exactly
1.50 pairwise wins in every seat. Any systematic deviation is a bug in that bot
(or in the engine), not variance. Mixed-field numbers cannot tell the two apart,
which is why the earlier test_robust result was ambiguous.

    python diag_seat.py [games] [bot ...]

`mybot` can carry a parameter file (SEAT_PARAMS=v6_params.json) and inline
overrides (`mybot:tie_home=0`), so the two tie-breaking rules can be compared
in the one place where the right answer is known in advance.
"""
import multiprocessing as mp
import os
import random
import sys

import arena
import engine


def _one(args):
    kind, gi, pfile = args
    rnd = random.Random(90000 + gi)
    base = engine.make_map(seed=gi + 1)
    if kind.startswith("mybot"):
        import json
        import mybot
        p = dict(mybot.PARAMS)
        if pfile:
            p.update(json.load(open(pfile)))
        # the deadline and the adaptive beam both make play depend on wall-clock
        # time; a symmetry test has to be reproducible
        p["throttle"] = 0
        p["budget_ms"] = 10000.0
        if ":" in kind:
            for kv in kind.split(":", 1)[1].split(","):
                k, _, v = kv.partition("=")
                p[k] = int(v) if isinstance(p[k], int) and "." not in v else float(v)
        bots = [mybot.Agent(seed=gi * 4 + i, params=p) for i in range(4)]
    else:
        import zoo
        import aifield
        cls = (zoo.ZOO_BY_NAME.get(kind) or aifield.AIFIELD_BY_NAME[kind])
        bots = [cls(gi * 4 + i) for i in range(4)]
    g = engine.play(bots, base=base, start_token=rnd.randint(1, 4))
    pl = g.places()
    pw = arena.pairwise_wins(pl)
    return [pw[i][0] + 0.5 * pw[i][1] for i in range(4)], g.score[:]


def sweep(kind, games, pool, pfile=None):
    res = pool.map(_one, [(kind, i, pfile) for i in range(games)], chunksize=4)
    tot = [0.0] * 4
    sc = [0.0] * 4
    for pw, s in res:
        for i in range(4):
            tot[i] += pw[i]
            sc[i] += s[i]
    return [t / games for t in tot], [x / games for x in sc]


if __name__ == "__main__":
    games = int(sys.argv[1]) if len(sys.argv) > 1 else 240
    kinds = sys.argv[2:] or ["mybot", "spine", "ai_route", "ai_marginal"]
    pfile = os.environ.get("SEAT_PARAMS") or None
    if pfile:
        print("my own bot uses %s\n" % pfile)
    pool = mp.Pool(min(12, mp.cpu_count()))
    print("four identical copies, %d games each. PW must be 1.50 per seat.\n" % games)
    print("%-14s %34s   %s" % ("bot", "PW by seat 1..4", "mean score by seat"))
    print("-" * 86)
    for k in kinds:
        pw, sc = sweep(k, games, pool, pfile)
        spread = max(pw) - min(pw)
        flag = "  <-- SEAT BIAS" if spread > 0.18 else ""
        print("%-14s %s   %s%s"
              % (k, " ".join("%7.2f" % x for x in pw),
                 " ".join("%6.0f" % x for x in sc), flag))
    pool.close()
