"""
econ.Econ with every flag off must play exactly like the research branch's file,
and so must the whole fusion bot, called through act(), on the documented
interface: its failsafe layers may only act when something has gone wrong.

The original bot (crossfield/bots/evolved.py, and the transfer finalist) plays
the game; the port shadows it on the identical observation every turn, and any
single differing action fails the test. Covers random seats, tokens, all six map
families, both legal_actions conventions and a mixed cross-author field.
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
import econ  # noqa: E402
import xfield  # noqa: E402


def flat(view):
    return [c for row in view.board for c in row]


class _Port(object):
    def __init__(self, config):
        self.e = econ.Econ(config=config)

    def step(self, cells, me, legal, token):
        return self.e.step(cells, me, legal, token)


class _Fusion(object):
    """The whole fusion bot, called through act() exactly as a server would."""
    def __init__(self, spec):
        self.act = xfield.resolve(spec)(0)
        self.view = None

    def step(self, cells, me, legal, token):
        return self.act(self.view)


def check(path, config, games=24, seed=11, fusion=None):
    tasks = xfield.make_tasks(games, seed=seed)
    os.chdir(ROOT)
    turns = 0
    for t in tasks:
        orig = xfield.file_bot(path)(0)
        port = _Fusion(fusion) if fusion else _Port(config)
        me = t["seat"]
        opps = [xfield.opponent(n)(t["map_seed"] * 4 + i) for i, n in enumerate(t["opps"])]
        g = engine.Game(base=xfield.make_map(t["family"], t["map_seed"]), start_token=t["token"])
        while not g.over():
            vs = xfield._views(g, t["excl"])
            acts = []
            k = 0
            for i in range(4):
                if i == me:
                    a = orig(vs[i])
                    if fusion:
                        port.view = vs[i]
                    b = port.step(flat(vs[i]), i + 1, list(vs[i].legal_actions),
                                  vs[i].is_priority_token)
                    turns += 1
                    if a != b:
                        return False, "game %r turn %d: original %s, port %s" % (
                            t, g.turn, a, b), turns
                else:
                    a = opps[k](vs[i])
                    k += 1
                acts.append(a if a in vs[i].legal_actions else "STAY")
            g.step(acts)
    return True, "", turns


if __name__ == "__main__":
    ok_all = True
    for label, path, cfg, fus in (
            ("econ.Econ vs evolved.py", "bots/evolved.py", econ.E_EVOLVED, None),
            ("econ.Econ vs transfer", "bots/evolved_transfer.py", econ.E_TRANSFER, None),
            ("fusion.py vs evolved.py", "bots/evolved.py", None, "file:fusion.py"),
            ("fusion.py(transfer) vs it", "bots/evolved_transfer.py", None,
             "file:fusion.py+genome:transfer")):
        ok, why, n = check(path, cfg, fusion=fus)
        print("%-28s %s  (%d turns compared)%s" % (label, "IDENTICAL" if ok else "DIFFERS", n,
                                                   "" if ok else "\n  " + why))
        ok_all = ok_all and ok
    sys.exit(0 if ok_all else 1)
