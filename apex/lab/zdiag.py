"""Instrumented games: per-seat event accounting.

    python zdiag.py <games> <mode> [--seed=N] spec
Prints, for the focus bot and for each opponent name, average events per game.
"""
import multiprocessing as mp
import os
import random
import sys
import time

LAB = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, LAB)
import zarena  # noqa
import engine  # noqa
import xfield  # noqa

KEYS = ("score", "bonus", "claims", "upgrades", "raids", "raids_up", "lost", "lost_up",
        "lost_bonus", "sh_catch", "sh_back", "caught", "frozen", "blocked", "stays",
        "moves", "raid_wait", "pw", "endinc", "cells")


def play_diag(focus_factory, task, cache):
    base = xfield.make_map(task["family"], task["map_seed"])
    random.seed(task["rseed"])
    bots, names = [], []
    for i, nm in enumerate(task["lineup"]):
        if nm == "*":
            bots.append(focus_factory(1))
        else:
            fac = cache.get(nm)
            if fac is None:
                fac = zarena.opponent(nm)
                cache[nm] = fac
            bots.append(fac(task["map_seed"] * 4 + i))
        names.append(nm)
    g = engine.Game(base=base, start_token=task["token"])
    st = [dict((k, 0) for k in KEYS) for _ in range(4)]
    while not g.over():
        vs = xfield._views(g, task["excl"])
        acts = []
        for i in range(4):
            try:
                a = bots[i](vs[i])
            except Exception:
                a = "STAY"
            if a not in vs[i].legal_actions:
                a = "STAY"
            acts.append(a)
        ow0, up0, pos0, fr0, sc0 = g.owner[:], g.upg[:], g.pos[:], g.frozen[:], g.score[:]
        eff = g.step(acts)
        for i in range(4):
            s = st[i]
            if fr0[i] > 0:
                s["frozen"] += 1
                continue
            if acts[i] in engine.MOVES:
                if g.pos[i] == pos0[i]:
                    s["blocked"] += 1
                else:
                    s["moves"] += 1
            elif acts[i] == "SHIELD":
                if g.frozen[i] > 0:
                    s["sh_back"] += 1
                else:
                    s["sh_catch"] += 1
            else:
                s["stays"] += 1
            if g.frozen[i] > 0 and acts[i] != "SHIELD":
                s["caught"] += 1
        for p in range(64):
            if ow0[p] != g.owner[p]:
                new, old = g.owner[p], ow0[p]
                if old == 0:
                    st[new - 1]["claims"] += 1
                else:
                    b = 8 * g.base[p] * (2 if up0[p] else 1)
                    st[new - 1]["raids"] += 1
                    st[new - 1].setdefault("_raid_on", {}).setdefault(old - 1, [0, 0])
                    st[new - 1]["_raid_on"][old - 1][0] += 1
                    st[new - 1]["_raid_on"][old - 1][1] += b
                    st[new - 1]["bonus"] += b
                    st[old - 1]["lost"] += 1
                    st[old - 1]["lost_bonus"] += b
                    if up0[p]:
                        st[new - 1]["raids_up"] += 1
                        st[old - 1]["lost_up"] += 1
            elif g.upg[p] and not up0[p]:
                st[g.owner[p] - 1]["upgrades"] += 1
    sc = g.score
    for i in range(4):
        st[i]["score"] = sc[i]
        st[i]["pw"] = sum(1.0 if sc[i] > sc[j] else (0.5 if sc[i] == sc[j] else 0) for j in range(4) if j != i)
        st[i]["endinc"] = g.income[i]
        st[i]["cells"] = g.cells_owned(i)
    flows = []
    for i in range(4):
        for j, (n, b) in st[i].get("_raid_on", {}).items():
            flows.append((names[i], names[j], n, b))
    for i in range(4):
        st[i].pop("_raid_on", None)
    return [(names[i], st[i]) for i in range(4)], flows


def _worker(arg):
    os.chdir(LAB)
    spec, tasks = arg
    fac = zarena.resolve(spec)
    cache = {}
    return [play_diag(fac, t, cache) for t in tasks]


def main(argv):
    games, mode = int(argv[1]), argv[2]
    seed = 1
    spec = None
    groups = None
    for a in argv[3:]:
        if a.startswith("--seed="):
            seed = int(a.split("=")[1])
        elif a.startswith("--groups="):
            groups = a.split("=", 1)[1].split(",")
        else:
            spec = a
    tasks = zarena.make_tasks(games, mode, seed=seed, groups=groups)
    jobs = [(spec, tasks[i:i + 4]) for i in range(0, len(tasks), 4)]
    pool = mp.Pool(mp.cpu_count())
    res = pool.map(_worker, jobs, chunksize=1)
    pool.close()
    agg = {}
    fl = {}
    for chunk in res:
        for game, flows in chunk:
            for a, b, n, bb in flows:
                k = (a, b)
                fl.setdefault(k, [0, 0])
                fl[k][0] += n
                fl[k][1] += bb
            for nm, s in game:
                a = agg.setdefault(nm, [0, dict((k, 0.0) for k in KEYS)])
                a[0] += 1
                for k in KEYS:
                    a[1][k] += s[k]
    G = len(tasks)
    print("raid flows involving the focus bot and evolved (per game): raider -> victim  cells  bonus")
    for (a, b), (n, bb) in sorted(fl.items(), key=lambda x: -x[1][1]):
        if a in ("*", "evolved") or b in ("*", "evolved"):
            if n / G >= 0.05:
                print("  %-22s -> %-22s %5.2f %6.1f" % (a, b, n / G, bb / G))
    order = sorted(agg, key=lambda n: (n != "*", n != "evolved", -agg[n][0]))
    print("%-22s %4s " % ("bot", "n") + " ".join("%7s" % k[:7] for k in KEYS))
    for nm in order[:40]:
        n, s = agg[nm]
        print("%-22s %4d " % (nm[:22], n) + " ".join("%7.1f" % (s[k] / n) for k in KEYS))


if __name__ == "__main__":
    main(sys.argv)
