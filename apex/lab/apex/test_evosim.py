"""EvoSim must reproduce the original evolved bot move for move."""
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
from evosim import EvoSim, EVO_GENOMES  # noqa


def flat(view):
    return [c for row in view.board for c in row]


SOURCES = {0: "evolved", 1: "evolved_tc", 2: "economic_11c655468adf", 3: "economic_f04298fe614d"}


def run(games=60, seed=5, gi_=0):
    rnd = random.Random(seed)
    src_name = SOURCES[gi_]
    turns = mism = 0
    for gi in range(games):
        fam = rnd.choice(["slope", "balanced", "patchy", "edge", "example", "flat"])
        base = xfield.make_map(fam, rnd.randrange(1 << 30))
        names = [rnd.choice([src_name, src_name, "opp_raider_04", "opp_shield_03", "spine",
                             "baiter", "ai_cheapraid", "opp_farmer_03", "random"]) for _ in range(4)]
        names[rnd.randrange(4)] = src_name
        bots = [zarena.opponent(n)(gi * 4 + i) for i, n in enumerate(names)]
        sims = [EvoSim(EVO_GENOMES[gi_]) if n == src_name else None for n in names]
        excl = rnd.random() < 0.5
        g = engine.Game(base=base, start_token=rnd.randint(1, 4))
        random.seed(gi)
        while not g.over():
            vs = xfield._views(g, excl)
            acts = []
            for i in range(4):
                a = bots[i](vs[i])
                if a not in vs[i].legal_actions:
                    a = "STAY"
                if sims[i] is not None:
                    b = sims[i].act(flat(vs[i]), i + 1, list(vs[i].legal_actions), vs[i].is_priority_token)
                    turns += 1
                    if a != b:
                        mism += 1
                        if mism < 5:
                            print("mismatch game", gi, "turn", g.turn, "seat", i + 1, a, b)
                acts.append(a)
            g.step(acts)
    print("turns compared", turns, "mismatches", mism)
    return mism


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 60
    bad = 0
    for k in SOURCES:
        print("genome", k, SOURCES[k])
        bad += run(n, 5 + k, k)
    sys.exit(1 if bad else 0)
