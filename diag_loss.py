"""
Where do my points actually go?

The audit shows the bot shields on 1% of turns and is frozen on 2%. That is
either a correct read of the game -- upgraded cells take three stays to steal, so
a compact upgraded cluster defends itself -- or a blind spot that a raid-heavy
field will punish. The difference matters, and it is measurable: count the cells
taken off me, the points that cost, and how many of those losses a shield I was
actually allowed to play would have prevented.

The "preventable" column is the ceiling on what better defence could be worth. If
it is small, no amount of shield tuning will help.

    python diag_loss.py [games] [opponent ...]
"""
import json
import sys

import engine
import mybot

OPPS = sys.argv[2:] or ["ai_cheapraid", "cdraider", "raider", "ai_hawk",
                        "spine", "ai_homefort"]
GAMES = int(sys.argv[1]) if len(sys.argv) > 1 else 12
P = dict(mybot.PARAMS)
P.update(json.load(open("v6_params.json")))
P["throttle"] = 0


def make(name, seed):
    import field as fieldmod
    return fieldmod.opponent(name)(seed)


print("v6 in seat 1 against three copies of each opponent, %d games each.\n" % GAMES)
print("%-14s %7s %7s %7s %7s %7s %7s"
      % ("opponent", "score", "lost", "pts", "bonus", "prvnt", "shields"))
print("-" * 68)
for opp in OPPS:
    tot = lost = pts = bonus = prevent = shields = 0
    for gi in range(GAMES):
        base = engine.make_map(seed=gi + 1)
        ag = mybot.Agent(seed=gi, params=P)
        bots = [ag] + [make(opp, gi * 4 + i) for i in range(1, 4)]
        g = engine.Game(base=base, start_token=(gi % 4) + 1)
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
            if acts[0] == "SHIELD":
                shields += 1
            # Would a shield this turn have saved anything? A rival standing on
            # one of my cells, not already frozen, with my cooldown clear.
            could = g.cd[0] == 0 and g.frozen[0] == 0
            before = set(p for p in range(64) if g.owner[p] == 1)
            at_risk = 0
            if could:
                for p in before:
                    o = g.pos.index(p) + 1 if p in g.pos else 0
                    if o and o != 1 and g.frozen[o - 1] == 0:
                        at_risk += g.base[p] * (2 if g.upg[p] else 1)
            upg_before = dict((p, g.upg[p]) for p in before)
            g.step(acts)
            for p in before:
                if g.owner[p] != 1:
                    lost += 1
                    lvl = 2 if upg_before[p] else 1
                    pts += g.base[p] * lvl * max(0, 81 - g.turn)
                    bonus += 8 * g.base[p] * lvl
                    if could and acts[0] != "SHIELD":
                        prevent += 1
        tot += g.score[0]
    print("%-14s %7.0f %7.1f %7.0f %7.0f %7.1f %7.1f"
          % (opp, tot / GAMES, lost / float(GAMES), pts / float(GAMES),
             bonus / float(GAMES), prevent / float(GAMES), shields / float(GAMES)))
print("\nlost    = my cells taken off me per game")
print("pts     = income those cells would still have paid, had I kept them")
print("bonus   = raid bonuses I handed the taker")
print("prvnt   = of those losses, how many happened on a turn I could have shielded")
print("shields = shields I actually played")
