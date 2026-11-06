"""
Field-sensitivity analysis.

Everything is tuned against an assumed field. If that guess is wrong, how much
strength is lost? This scores the candidate under several very different
assumptions about what the other teams actually ship.
"""
import json
import random
import sys

import engine
import holdout
import mybot
import rivals
import zoo

FIELDS = {
    "my predicted field": [zoo.GreedyValueBot, zoo.GreedyValueBot, zoo.GreedyShieldBot,
                           zoo.GreedyShieldBot, zoo.PacifistBot, zoo.SpineFarmerBot,
                           zoo.CamperBot, zoo.RaiderBot, zoo.BaiterBot],
    "all strong farmers": [zoo.SpineFarmerBot, zoo.CamperBot, holdout.TurtleBot],
    "all aggressive": [zoo.RaiderBot, zoo.BaiterBot, holdout.LeaderHunterBot,
                       holdout.CooldownRaiderBot],
    "all naive LLM bots": [zoo.GreedyValueBot, zoo.GreedyShieldBot, zoo.PacifistBot],
    "all centre-contesting": [holdout.CentreRushBot, zoo.CamperBot, zoo.SpineFarmerBot],
    "weak / broken field": [zoo.RandomBot, zoo.StayBot, zoo.GreedyValueBot],
    "the dangerous one": [holdout.CooldownRaiderBot, zoo.SpineFarmerBot, zoo.CamperBot],
}


def pw(params, field, games=140, seed0=41000):
    tot = 0.0
    sc = 0.0
    firsts = 0
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
        if pl[ms] == 1:
            firsts += 1
    return tot / games, sc / games, firsts / float(games)


if __name__ == "__main__":
    cand = sys.argv[1] if len(sys.argv) > 1 else "best_params.json"
    P = dict(mybot.PARAMS)
    P.update(json.load(open(cand)))
    print("candidate: %s" % cand)
    print("%-26s %8s %8s %7s" % ("assumed field", "PW/3", "score", "1st%"))
    print("-" * 52)
    rows = []
    for name, field in FIELDS.items():
        a, b, f = pw(P, field)
        rows.append((name, a, b, f))
        print("%-26s %8.2f %8.0f %6.0f%%" % (name, a, b, 100 * f))
    worst = min(rows, key=lambda r: r[1])
    best = max(rows, key=lambda r: r[1])
    print("-" * 52)
    print("  best  : %-22s %.2f" % (best[0], best[1]))
    print("  worst : %-22s %.2f" % (worst[0], worst[1]))
    print("  spread across field assumptions: %.2f PW" % (best[1] - worst[1]))
    print("  (1.50 = exactly average. Staying above 1.50 everywhere means the")
    print("   bot does not depend on my guess about what other teams ship.)")
