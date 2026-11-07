"""
Overfitting check: measure the tuned bot against opponents it has NEVER been
tuned against, and compare the gain to the gain on the training field.
If the tuned weights only beat the training zoo, they are overfitted.
"""
import json
import random
import sys

import engine
import holdout
import mybot
import zoo

TRAIN = [zoo.SpineFarmerBot, zoo.CamperBot, zoo.GreedyShieldBot, zoo.GreedyValueBot,
         zoo.PacifistBot, zoo.RaiderBot, zoo.BaiterBot]
HELD = holdout.HOLDOUT


def pw(params, field, games=160, seed0=21000):
    tot = 0.0
    sc = 0.0
    for s in range(games):
        rnd = random.Random(seed0 + s)
        base = engine.make_map(seed=seed0 + s)
        ms = rnd.randrange(4)
        ag = mybot.Agent(seed=s, params=params)
        bots = [ag if i == ms else field[rnd.randrange(len(field))](s * 4 + i)
                for i in range(4)]
        g = engine.Game(base=base, start_token=rnd.randint(1, 4))
        while not g.over():
            vs = g.views()
            acts = []
            for i in range(4):
                try:
                    a = bots[i](vs[i])
                except Exception:
                    a = "STAY"
                if a not in vs[i].legal_actions:
                    a = "STAY"
                acts.append(a)
            g.step(acts)
        pl = g.places()
        tot += sum(1.0 for j in range(4) if j != ms and pl[ms] < pl[j])
        tot += 0.5 * sum(1 for j in range(4) if j != ms and pl[ms] == pl[j])
        sc += g.score[ms]
    return tot / games, sc / games


def head_to_head(params, cls, games=80, seed0=31000):
    """candidate vs three copies of one opponent"""
    tot = 0.0
    for s in range(games):
        rnd = random.Random(seed0 + s)
        base = engine.make_map(seed=seed0 + s)
        ms = rnd.randrange(4)
        ag = mybot.Agent(seed=s, params=params)
        bots = [ag if i == ms else cls(s * 4 + i) for i in range(4)]
        g = engine.Game(base=base, start_token=rnd.randint(1, 4))
        while not g.over():
            vs = g.views()
            acts = []
            for i in range(4):
                try:
                    a = bots[i](vs[i])
                except Exception:
                    a = "STAY"
                if a not in vs[i].legal_actions:
                    a = "STAY"
                acts.append(a)
            g.step(acts)
        pl = g.places()
        tot += sum(1.0 for j in range(4) if j != ms and pl[ms] < pl[j])
        tot += 0.5 * sum(1 for j in range(4) if j != ms and pl[ms] == pl[j])
    return tot / games


if __name__ == "__main__":
    cand = sys.argv[1] if len(sys.argv) > 1 else "v7_params.json"
    P = dict(mybot.PARAMS)
    P.update(json.load(open(cand)))
    S = dict(mybot.PARAMS)             # untuned starting point

    print("                          untuned    tuned     gain")
    a1, s1 = pw(S, TRAIN)
    b1, t1 = pw(P, TRAIN)
    print("  training field  PW/3   %7.2f  %7.2f  %+7.2f" % (a1, b1, b1 - a1))
    print("                  score  %7.0f  %7.0f  %+7.0f" % (s1, t1, t1 - s1))
    a2, s2 = pw(S, HELD)
    b2, t2 = pw(P, HELD)
    print("  HELD-OUT field  PW/3   %7.2f  %7.2f  %+7.2f" % (a2, b2, b2 - a2))
    print("                  score  %7.0f  %7.0f  %+7.0f" % (s2, t2, t2 - s2))
    ratio = (b2 - a2) / (b1 - a1) if abs(b1 - a1) > 1e-9 else 0.0
    print("\n  transfer ratio (held-out gain / training gain): %.2f" % ratio)
    print("  (near 1.0 means the tuning generalised; near 0 means it overfitted)")

    print("\n  head-to-head vs three copies of each held-out opponent:")
    for cls in HELD:
        print("    vs %-10s %.2f/3" % (cls.name, head_to_head(P, cls)))
    print("\n  and vs the training archetypes, for comparison:")
    for cls in (zoo.SpineFarmerBot, zoo.CamperBot):
        print("    vs %-10s %.2f/3" % (cls.name, head_to_head(P, cls)))
