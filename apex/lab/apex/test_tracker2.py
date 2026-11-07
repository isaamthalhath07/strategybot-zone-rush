"""Tracker reconstruction vs the engine's hidden state."""
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
LAB = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, LAB)
sys.path.insert(0, os.path.join(LAB, "crossfield"))
import engine  # noqa
import xfield  # noqa
import zarena  # noqa
from tracker import Tracker, Obs  # noqa

POOL = ["evolved", "evolved", "opp_raider_04", "opp_shield_03", "opp_shield_01", "spine",
        "baiter", "ai_cheapraid", "opp_farmer_03", "random", "main_v7", "greedyshield",
        "opp_raider_gpt1", "cdraider", "ai_hawk", "opp_bait_01", "lure"]


def run(games=60, seed=11, rules=None):
    rnd = random.Random(seed)
    err = dict(turn=0, score=0, prog=0, fl=0, cd=0, cd_me=0, holder=0, shield=0)
    n = 0
    for gi in range(games):
        fam = rnd.choice(["slope", "balanced", "patchy", "edge", "example", "flat"])
        base = xfield.make_map(fam, rnd.randrange(1 << 30))
        names = [rnd.choice(POOL) for _ in range(4)]
        bots = [zarena.opponent(nm)(gi * 4 + i) for i, nm in enumerate(names)]
        excl = rnd.random() < 0.5
        tok = rnd.randint(1, 4)
        g = engine.Game(base=base, start_token=tok, rules=rules)
        trs = [Tracker() for _ in range(4)]
        last = [None] * 4
        random.seed(gi)
        prev_cd = None
        while not g.over():
            vs = xfield._views(g, excl)
            for i in range(4):
                cells = [c for row in vs[i].board for c in row]
                tr = trs[i]
                tr.update(Obs(cells), i + 1, vs[i].is_priority_token, list(vs[i].legal_actions), last[i])
                n += 1
                if tr.turn != g.turn:
                    err["turn"] += 1
                for s in range(4):
                    if tr.score[s + 1] != g.score[s]:
                        err["score"] += 1
                    if tr.prog[s + 1] != min(g.prog[s], 2):
                        err["prog"] += 1
                    if tr.fl[s + 1] != g.frozen[s]:
                        err["fl"] += 1
                    if tr.cd[s + 1] != g.cd[s]:
                        if s == i:
                            err["cd_me"] += 1
                        else:
                            err["cd"] += 1
                if tr.holder() is not None and tr.holder() != g.token:
                    err["holder"] += 1
            acts = []
            for i in range(4):
                a = bots[i](vs[i])
                if a not in vs[i].legal_actions:
                    a = "STAY"
                acts.append(a)
                last[i] = a
            g.step(acts)
    print("observations", n, err)
    return err


if __name__ == "__main__":
    run(int(sys.argv[1]) if len(sys.argv) > 1 else 60)
    print("carry rule:")
    run(20, seed=3, rules={"claim_resets_progress": False})
