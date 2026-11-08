"""
Behavioural audit: catch pathologies that a score table hides.

A bot can look mediocre rather than broken while doing something plainly wrong,
and the tournament will not tell you which. The two that actually happened here:

  * pacing -- re-planning from scratch every turn, walking A->B->A forever and
    never banking a stay. Shows up as a near-zero STAY share and a high reversal
    rate, not as a crash.
  * shielding on sight -- burning the cooldown and backfiring constantly. Shows
    up as a high SHIELD share and a high frozen share.

Every action in this game except STAY and a completed SHIELD produces nothing, so
a healthy farmer spends most of its turns stationary.

    python audit.py [games] [bot ...]
"""
import collections
import sys
import time

import aifield
import engine
import zoo


def make(kind, seed):
    if kind == "mybot":
        import mybot
        return mybot.Agent(seed=seed)
    import field as fieldmod
    return fieldmod.opponent(kind)(seed)


def audit(kind, games, field=None):
    cnt = collections.Counter()
    turns = 0
    rev = 0
    frozen = 0
    illegal = 0
    crashes = 0
    worst = 0.0
    score = 0
    OPP = {"NORTH": "SOUTH", "SOUTH": "NORTH", "EAST": "WEST", "WEST": "EAST"}
    for gi in range(games):
        base = engine.make_map(seed=gi + 1)
        seat = gi % 4
        bots = []
        for i in range(4):
            if i == seat:
                bots.append(make(kind, gi))
            else:
                bots.append(make(field or kind, gi * 4 + i))
        g = engine.Game(base=base, start_token=(gi % 4) + 1)
        prev = None
        while not g.over():
            vs = g.views()
            acts = []
            for i in range(4):
                if i == seat:
                    t0 = time.perf_counter()
                    try:
                        a = bots[i](vs[i])
                    except Exception:
                        crashes += 1
                        a = "STAY"
                    dt = time.perf_counter() - t0
                    if dt > worst:
                        worst = dt
                    if a not in vs[i].legal_actions:
                        illegal += 1
                        a = "STAY"
                    cnt[a] += 1
                    turns += 1
                    if g.frozen[i] > 0:
                        frozen += 1
                    if prev in OPP and OPP[prev] == a:
                        rev += 1
                    prev = a
                else:
                    a = bots[i](vs[i])
                    if a not in vs[i].legal_actions:
                        a = "STAY"
                acts.append(a)
            g.step(acts)
        score += g.score[seat]
    t = float(max(1, turns))
    return {
        "score": score / float(games),
        "stay": cnt["STAY"] / t,
        "shield": cnt["SHIELD"] / t,
        "move": sum(cnt[a] for a in ("NORTH", "SOUTH", "EAST", "WEST")) / t,
        "reversal": rev / t,
        "frozen": frozen / t,
        "illegal": illegal,
        "crashes": crashes,
        "ms": worst * 1000.0,
    }


if __name__ == "__main__":
    games = int(sys.argv[1]) if len(sys.argv) > 1 else 24
    kinds = sys.argv[2:] or (["mybot", "spine"] + [c.name for c in aifield.AIFIELD])
    print("%d games each, bot in a rotating seat against copies of itself.\n" % games)
    print("%-14s %7s %6s %6s %6s %6s %6s %5s %5s %7s"
          % ("bot", "score", "stay", "move", "shield", "revrs", "frozen",
             "ill", "crsh", "max ms"))
    print("-" * 86)
    bad = []
    for k in kinds:
        r = audit(k, games)
        notes = []
        if r["stay"] < 0.25:
            notes.append("barely stays")
        if r["reversal"] > 0.22:
            notes.append("pacing")
        if r["shield"] > 0.14:
            notes.append("shield-happy")
        if r["frozen"] > 0.20:
            notes.append("often frozen")
        if r["illegal"] or r["crashes"]:
            notes.append("ILLEGAL/CRASH")
        print("%-14s %7.0f %6.2f %6.2f %6.2f %6.2f %6.2f %5d %5d %7.1f  %s"
              % (k, r["score"], r["stay"], r["move"], r["shield"], r["reversal"],
                 r["frozen"], r["illegal"], r["crashes"], r["ms"],
                 ", ".join(notes)))
        if notes:
            bad.append(k)
    print("\n%s" % ("flagged: " + ", ".join(bad) if bad else "no pathologies"))
