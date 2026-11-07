"""
Regression check for the v8 refactor: with every v8 switch at its default,
mybot.py must play EXACTLY like the v7 bot.py that shipped before the audit.

Every v8 fix sits behind a PARAMS flag whose default reproduces v7, so this is
the guarantee that the refactor changed nothing until a flag is switched on --
and that `python ship.py v7_params.json` still rebuilds the old bot's play.

The v7 file is read straight out of git history (commit 961e729), so the check
needs no stored copy. Both bots see the same view every turn; the game is driven
by the v7 action, and the first divergence is reported.

    python audit/check_v7_compat.py [games]
"""
import importlib.util
import json
import os
import random
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO)
sys.path.insert(0, HERE)
os.chdir(REPO)

import engine  # noqa: E402
import mybot  # noqa: E402
import edge_audit  # noqa: E402  (registers the outsiders)

V7_COMMIT = "961e729"


def load_v7():
    src = subprocess.check_output(["git", "show", V7_COMMIT + ":bot.py"], cwd=REPO)
    d = tempfile.mkdtemp()
    path = os.path.join(d, "bot_v7.py")
    with open(path, "wb") as f:
        f.write(src)
    spec = importlib.util.spec_from_file_location("bot_v7", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main():
    games = int(sys.argv[1]) if len(sys.argv) > 1 else 60
    v7 = load_v7()
    params = dict(mybot.PARAMS)
    params.update(json.load(open("v7_params.json")))
    pin = {"throttle": 0, "budget_ms": 10000.0}
    pool = sorted(edge_audit.outsiders.REGISTRY) + edge_audit.fieldmod.TIERS["strangers"]
    rnd = random.Random(99)
    turns = 0
    for gi in range(games):
        map_seed = rnd.randrange(1 << 30)
        myseat = rnd.randrange(4)
        opps = [pool[rnd.randrange(len(pool))] for _ in range(3)]
        old = v7.Agent(seed=map_seed & 0xffff, params=pin)
        new = mybot.Agent(seed=map_seed & 0xffff, params=dict(params, **pin))
        bots, k = [], 0
        for i in range(4):
            if i == myseat:
                bots.append(None)
            else:
                bots.append(edge_audit.make_opponent(opps[k], map_seed * 4 + i))
                k += 1
        g = engine.Game(base=engine.make_map(seed=map_seed), start_token=rnd.randint(1, 4))
        while not g.over():
            vs = g.views()
            a_old = old(vs[myseat])
            a_new = new(vs[myseat])
            if a_old != a_new:
                print("DIVERGED: game %d turn %d (seat %d vs %s): v7 %s, mybot %s"
                      % (gi, g.turn, myseat + 1, opps, a_old, a_new))
                sys.exit(1)
            acts = []
            for i in range(4):
                a = a_old if i == myseat else bots[i](vs[i])
                acts.append(a if a in vs[i].legal_actions else "STAY")
            g.step(acts)
            turns += 1
    print("v7-compatible defaults: %d games, %d decisions, identical to v7 bot.py (%s)"
          % (games, turns, V7_COMMIT))


if __name__ == "__main__":
    main()
