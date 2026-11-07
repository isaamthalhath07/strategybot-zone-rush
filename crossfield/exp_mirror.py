"""
Experiment: can a bot safely recognise exact copies of the public econ-family
bots by predicting them? (fusion.py FLAGS["mirror"]; result: NO, so it is off.)

Why try: this repository is public and its strongest bot is deterministic, so a
copy's action this turn can be computed exactly -- it sees the same board, and
its seat, token, legal actions and cooldown can all be reconstructed. Knowing it
would make the shield/raid stand-off against a copy a solved game.

Why it is off: a false identification is the dangerous failure (acting on a
"certain" prediction of a rival that is not what it seems: stepping off a cell
for a shield that never comes, cancelling a shield against a take that does).
This plays mixed lineups that include near-relatives and counts how often a
non-copy is taken for a copy. Requiring 10 matching informative turns, every
true copy was recognised (50/50) but so were 25 of 70 non-copies; with no
threshold at all, some near-relatives (economic_f04298..., same code and a
slightly different genome; incumbent) matched one public genome for 63-79 turns
before diverging -- and they diverge exactly at close shield and raid decisions,
which is where the exploit would act. No match count separates them.

    python crossfield/exp_mirror.py
"""
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
for _p in (ROOT, HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import engine  # noqa: E402
import xfield  # noqa: E402

COPIES = {"evolved", "evolved_tc", "economic_b9fdc45f4957"}   # the same code + genome
OTHERS = ["main_v7", "indep_v7", "v6", "economic_f04298fe614d", "economic_11c655468adf",
          "user_route_5a9c915442d7", "incumbent", "tactical_9d8c8555d2a9", "macro",
          "action_beam_1ea33eef3561", "fortress", "lure", "reserved_adversary",
          "pro_tuned", "spine", "camper", "route", "seq", "rate", "vulture", "greedy",
          "random", "stay"]


def main(games=40, seed=7):
    os.chdir(ROOT)
    rnd = random.Random(seed)
    fac = xfield.resolve("file:fusion.py+mirror:1")
    true_pos = true_n = false_pos = false_n = 0
    first_turn = []
    exploits = 0
    for gi in range(games):
        me = rnd.randrange(4)
        names = []
        for _ in range(3):
            names.append(rnd.choice(sorted(COPIES)) if rnd.random() < 0.4 else rnd.choice(OTHERS))
        fam = rnd.choice(["slope", "balanced", "patchy", "edge"])
        base = xfield.make_map(fam, 500 + gi)
        act = fac(0)
        ns = act.__globals__
        bots, k = [], 0
        for i in range(4):
            if i == me:
                bots.append(act)
            else:
                bots.append(xfield.opponent(names[k])(gi * 4 + i))
                k += 1
        g = engine.Game(base=base, start_token=rnd.randint(1, 4))
        seen = {}
        excl = gi % 2 == 1
        while not g.over():
            vs = xfield._views(g, excl)
            acts = []
            for i in range(4):
                a = bots[i](vs[i])
                acts.append(a if a in vs[i].legal_actions else "STAY")
            brain = ns["_F_BRAINS"].get(me + 1)
            if brain is not None and brain.mirror is not None:
                m = brain.mirror
                for s in m.rivals:
                    ident = any(m.ok[s][x] and m.hits[s][x] >= m.NEED for x in (0, 1))
                    if ident and s not in seen:
                        seen[s] = g.turn
            g.step(acts)
        brain = ns["_F_BRAINS"][me + 1]
        exploits += brain.exploits
        k = 0
        for i in range(4):
            if i == me:
                continue
            nm = names[k]
            k += 1
            s = i + 1
            if nm in COPIES:
                true_n += 1
                if s in seen:
                    true_pos += 1
                    first_turn.append(seen[s])
            else:
                false_n += 1
                if s in seen:
                    false_pos += 1
                    print("  FALSE IDENTIFICATION: %s in seat %d (game %d, turn %d)"
                          % (nm, s, gi, seen[s]))
    print("copies recognised: %d of %d (median by turn %s)" % (
        true_pos, true_n, sorted(first_turn)[len(first_turn) // 2] if first_turn else "-"))
    print("non-copies mistaken for copies: %d of %d" % (false_pos, false_n))
    print("exploit actions taken: %d" % exploits)
    safe = false_pos == 0 and true_n > 0 and true_pos >= 0.8 * true_n
    print("verdict: %s" % ("identification is safe" if safe else
                           "identification is NOT safe -- keep FLAGS['mirror'] = 0"))
    return safe


if __name__ == "__main__":
    main()
