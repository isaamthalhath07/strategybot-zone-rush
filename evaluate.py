"""
Final evaluation: a full Elo tournament including the zoo, every frozen snapshot
of this bot, and the candidate, plus an exploitability check and a mirror match.
"""
import json
import random
import sys

import arena
import engine
import mybot
import rivals
import zoo


def registry(extra=None):
    reg = arena.Registry()
    for cls in zoo.ZOO:
        reg.add(cls.name, (lambda c: (lambda seed: c(seed)))(cls))
    for name in rivals.names():
        reg.add(name, rivals.factory(name))
    for name, pf in (extra or {}).items():
        params = json.load(open(pf))
        reg.add(name, (lambda p: (lambda seed: mybot.Agent(seed=seed, params=p)))(params))
    return reg


def mirror(params, games=60, seed0=6000):
    """Four identical copies: what decides a game when the field converges?"""
    spreads = []
    for s in range(games):
        base = engine.make_map(seed=seed0 + s)
        bots = [mybot.Agent(seed=i * 97 + s, params=params) for i in range(4)]
        g = engine.Game(base=base, start_token=(s % 4) + 1)
        while not g.over():
            vs = g.views()
            acts = []
            for i in range(4):
                a = bots[i](vs[i])
                if a not in vs[i].legal_actions:
                    a = "STAY"
                acts.append(a)
            g.step(acts)
        sc = sorted(g.score, reverse=True)
        spreads.append((sc[0] - sc[3]) / float(sc[0]))
    return sum(spreads) / len(spreads)


def exploitability(reg, cand, counter, games=240, seed=77):
    """How well does the bot tuned to beat us actually do? 1.50 = no edge."""
    st = arena.tournament(reg, [cand, counter], games=games, seed=seed,
                          focus=counter, opponents=[cand])
    g = max(1, st.games[counter])
    return st.pw[counter] / g


if __name__ == "__main__":
    games = int(sys.argv[1]) if len(sys.argv) > 1 else 600
    cand_file = sys.argv[2] if len(sys.argv) > 2 else "best_params.json"
    reg = registry({"candidate": cand_file})
    names = [c.name for c in zoo.ZOO] + rivals.names() + ["candidate"]

    print("=== full-field Elo tournament (%d games) ===" % games)
    st = arena.tournament(reg, names, games=games, seed=5, focus="candidate")
    print(st.table(sort="pw"))
    print()
    print(st.h2h_table("candidate"))

    P = json.load(open(cand_file))
    print("\n=== mirror match ===")
    sp = mirror(P)
    print("  4 identical copies: mean 1st-vs-4th score spread %.1f%%" % (100 * sp))

    for ctr in [n for n in rivals.names() if n.startswith("nemesis")]:
        pw = exploitability(reg, "candidate", ctr)
        print("\n=== exploitability vs %s ===" % ctr)
        print("  %s scores %.2f/3 against 3 copies of the candidate "
              "(1.50 = no edge at all)" % (ctr, pw))
