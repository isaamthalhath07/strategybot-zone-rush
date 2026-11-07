"""
Alternative referees: the server is the one "model" nobody here can inspect.

The repository already tests five ambiguous rules (engine.RULES). It does not test
the two durations bot.py hard-codes -- the shield cooldown (4, bot.py:353) and the
freeze (2, bot.py:279) -- although "can't shield again for the next 4 turns" and
"frozen for 2 turns" can each be counted one turn differently by an implementer.
This plays identical tasks under several referee readings and reports, for each:

  * how often the tracker's rival-cooldown estimate is UNSAFE (it believes a rival
    cannot shield on a turn when the referee would let it), and
  * the bot's pairwise wins and score, paired against the standard reading.

    python audit/referee.py [games] [tier]
"""
import math
import multiprocessing as mp
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO)
sys.path.insert(0, HERE)
os.chdir(REPO)

import bot  # noqa: E402
import engine  # noqa: E402
import edge_audit  # noqa: E402  (registers the outsiders and extra tiers)

# (label, cooldown length, freeze length)
REFEREES = [
    ("standard  cd4 frz2", 4, 2),
    ("cooldown 3 (off by one, shorter)", 3, 2),
    ("cooldown 5 (off by one, longer)", 5, 2),
    ("freeze 1 (current turn counted)", 4, 1),
    ("freeze 3", 4, 3),
]


def play(args):
    task, cd_len, frz_len = args
    map_seed, myseat, opps, token = task
    bots, k = [], 0
    ag = None
    for i in range(4):
        if i == myseat:
            ag = bot.Agent(seed=map_seed & 0xffff,
                           params={"throttle": 0, "budget_ms": 10000.0})
            bots.append(ag)
        else:
            bots.append(edge_audit.make_opponent(opps[k], map_seed * 4 + i))
            k += 1
    g = engine.Game(base=engine.make_map(seed=map_seed), start_token=token)
    unsafe = total = 0
    while not g.over():
        vs = g.views()
        acts = []
        for i in range(4):
            try:
                a = bots[i](vs[i])
            except Exception:
                a = "STAY"
            acts.append(a if a in vs[i].legal_actions else "STAY")
        if g.turn > 2:
            for j in range(4):
                if j != myseat:
                    total += 1
                    # unsafe: tracker says "cannot shield", referee says it can
                    if ag.tr.cd[j] > 0 and g.cd[j] == 0 and g.frozen[j] == 0:
                        unsafe += 1
        prev_frozen = g.frozen[:]
        eff = g.step(acts)
        for i in range(4):
            if eff[i] == "SHIELD":
                g.cd[i] = cd_len
            if prev_frozen[i] == 0 and g.frozen[i] == 2:
                g.frozen[i] = frz_len           # newly frozen this turn
    pl = g.places()
    pw = sum(1.0 if pl[myseat] < pl[j] else (0.5 if pl[myseat] == pl[j] else 0.0)
             for j in range(4) if j != myseat)
    return pw, g.score[myseat], unsafe, total


def main():
    games = int(sys.argv[1]) if len(sys.argv) > 1 else 300
    tier = sys.argv[2] if len(sys.argv) > 2 else "strangers"
    tasks = edge_audit.tasks_for(games, tier, seed=31)
    pool = mp.Pool(min(4, mp.cpu_count()))
    res = {}
    for label, cd_len, frz_len in REFEREES:
        res[label] = pool.map(play, [(t, cd_len, frz_len) for t in tasks], chunksize=5)
    pool.close()
    ref = res[REFEREES[0][0]]
    n = len(ref)
    lines = ["[%s] %d paired games per referee" % (tier, n)]
    for label, _c, _f in REFEREES:
        r = res[label]
        pw = sum(x[0] for x in r) / n
        sc = sum(x[1] for x in r) / n
        uns = sum(x[2] for x in r) / float(max(1, sum(x[3] for x in r)))
        line = "%-34s PW %.3f  score %6.0f  unsafe cooldown belief %5.2f%%" % (
            label, pw, sc, 100 * uns)
        if r is not ref:
            d = [r[i][0] - ref[i][0] for i in range(n)]
            md = sum(d) / n
            se = math.sqrt(sum((x - md) ** 2 for x in d) / (n - 1) / n)
            line += "   dPW %+.3f +/- %.3f (z %+.2f)" % (md, se, md / se if se else 0)
        lines.append(line)
    txt = "\n".join(lines)
    print(txt)
    with open(os.path.join(HERE, "results", "referee_%s_%d.txt" % (tier, games)),
              "w", encoding="utf-8") as f:
        f.write(txt + "\n")


if __name__ == "__main__":
    main()
