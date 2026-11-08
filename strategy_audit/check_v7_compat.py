"""
Regression check: the current mybot.py, given a version's switch values, must
play EXACTLY like that version did when it shipped.

Every audit fix sits behind a PARAMS switch, so each released version is just a
set of switch values. This plays the current mybot.py against the bot it claims
to rebuild, read straight out of git history, on the same view every turn. The
game is driven by the old bot's action, and the first divergence is reported.

    v7    v7_params.json plus the v7 values of the switches added since
          (V7_SWITCHES), against bot.py at 961e729
    v8    v8_params.json, against bot.py at 1751ffb
    v9    v9_params.json, against bot.py at 7c102e3
    main  the defaults with fusion.py's ROUTE_PARAMS, against main's own
          mybot.py at 641b9ac: the fused bot's warm standby must be unchanged

One agent plays a series of three games, so new-game detection is exercised
too. Opponents are drawn from the outside designs, the strangers and the novel
bots.

    python strategy_audit/check_v7_compat.py [games] [v7|v8|v9|main|all]
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
# only the opponents are needed from the harness, not the bot it audits
os.environ.setdefault("AUDIT_BOT", "mybot")

import engine  # noqa: E402
import mybot  # noqa: E402
import edge_audit  # noqa: E402  (registers the outsiders and the novel bots)

# The switches whose defaults moved away from v7 when the cross-branch review
# was merged in (README.md, "Merged with the cross-branch review").
V7_SWITCHES = {"pay_fix": 0, "fresh_guard": 0, "shield_home": 1,
               "last_shield_value": 0, "solver_retry": 0}
PIN = {"throttle": 0, "budget_ms": 10000.0}
SERIES = 3


def _from_git(rev, path, name):
    src = subprocess.check_output(["git", "show", "%s:%s" % (rev, path)], cwd=REPO)
    d = tempfile.mkdtemp()
    fn = os.path.join(d, name + ".py")
    with open(fn, "wb") as f:
        f.write(src)
    spec = importlib.util.spec_from_file_location(name, fn)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _params(fn, extra=None):
    p = dict(mybot.PARAMS)
    p.update(json.load(open(fn)))
    p.update(extra or {})
    return p


def versions():
    """name -> (git revision, file there, its params, current mybot params)."""
    import fusion
    route = dict(mybot.PARAMS)
    route.update(fusion.ROUTE_PARAMS)
    return {
        "v7": ("961e729", "bot.py", None, _params("v7_params.json", V7_SWITCHES)),
        "v8": ("1751ffb", "bot.py", None, _params("v8_params.json")),
        "v9": ("7c102e3", "bot.py", None, _params("v9_params.json")),
        "main": ("641b9ac", "mybot.py", dict(fusion.ROUTE_PARAMS), route),
    }


def check(name, rev, path, ref_params, params, games):
    ref = _from_git(rev, path, "ref_" + name)
    pool = (sorted(edge_audit.outsiders.REGISTRY) + edge_audit.fieldmod.TIERS["strangers"]
            + sorted(edge_audit.NOVEL))
    rnd = random.Random(99)
    turns = 0
    old = new = None
    for gi in range(games):
        map_seed = rnd.randrange(1 << 30)
        myseat = rnd.randrange(4)
        opps = [pool[rnd.randrange(len(pool))] for _ in range(3)]
        if gi % SERIES == 0:
            seed = map_seed & 0xffff
            old = ref.Agent(seed=seed, params=dict(ref_params or {}, **PIN))
            new = mybot.Agent(seed=seed, params=dict(params, **PIN))
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
                print("%s DIVERGED: game %d turn %d (seat %d vs %s): old %s, mybot %s"
                      % (name, gi, g.turn, myseat + 1, opps, a_old, a_new))
                return False
            acts = []
            for i in range(4):
                a = a_old if i == myseat else bots[i](vs[i])
                acts.append(a if a in vs[i].legal_actions else "STAY")
            g.step(acts)
            turns += 1
    print("%-4s %d games, %d decisions, identical to %s at %s"
          % (name, games, turns, path, rev))
    return True


def main():
    games = int(sys.argv[1]) if len(sys.argv) > 1 else 60
    which = sys.argv[2] if len(sys.argv) > 2 else "all"
    vs = versions()
    names = sorted(vs) if which == "all" else [which]
    ok = True
    for n in names:
        rev, path, ref_params, params = vs[n]
        ok = check(n, rev, path, ref_params, params, games) and ok
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
