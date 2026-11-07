"""
How well can the bot see where its rivals are going -- and how far ahead?

An observer Tracker + Forecaster sits in the bot's seat, sees exactly the board
the bot sees, and every turn forecasts each moving rival. After the game the
forecasts are scored against what the rivals actually did:

  destination   the next cell the rival stays on (its next piece of work), for
                every turn the rival is moving. Top-1 accuracy, and the
                probability the forecast gave the true destination.
  position      where the rival actually is k turns later, k = 1..8: mean
                Manhattan error of walking it toward its forecast destination.
  arrival       when the destination was right: |forecast arrival - actual|.

Three baselines, none of which learns anything during the game:

  prior         the same rule-derived target values with NO online inference
                -- isolates what watching the rival's moves adds
  stay          the rival stays where it is
  momentum      the rival keeps moving in its last direction

    python strategy_audit/forecast_probe.py [games] [tier]

AUDIT_BOT chooses the bot that plays the seat (default: the shipped bot.py); the
forecast itself always comes from mybot.Forecaster, observing.
"""
import math
import multiprocessing as mp
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO)
sys.path.insert(0, HERE)
os.chdir(REPO)

import engine  # noqa: E402
import mybot  # noqa: E402
import edge_audit  # noqa: E402

bot = edge_audit.bot
HORIZONS = (1, 2, 3, 5, 8)


def parse(view):
    bd = view.board
    cells = [bd[r][c] for r in range(8) for c in range(8)]
    base = [c.base_points for c in cells]
    owner = [c.owner for c in cells]
    upg = [1 if c.is_upgraded else 0 for c in cells]
    occ = [c.occupant for c in cells]
    frz = [1 if c.is_frozen else 0 for c in cells]
    home_of = [(c.owner or 1) if c.is_home else 0 for c in cells]
    return base, owner, upg, occ, frz, home_of


def walk(p, g, k):
    """Position after k shortest-path steps from p toward g (stops at g)."""
    for _ in range(k):
        if p == g:
            break
        dg = mybot.MANH[p][g]
        for w in mybot.NEIGH[p]:
            if mybot.MANH[w][g] < dg:
                p = w
                break
    return p


def momentum(prev, p, k):
    if prev is None or prev == p:
        return p
    d = p - prev
    for _ in range(k):
        q = p + d
        if q < 0 or q >= 64 or q not in mybot.NEIGH[p]:
            break
        p = q
    return p


def play(task):
    map_seed, myseat, opps, token = task
    params = edge_audit.parse_variant("base")[0]
    bots, names, k = [], [None] * 4, 0
    for i in range(4):
        if i == myseat:
            bots.append(bot.Agent(seed=map_seed & 0xffff, params=params))
        else:
            bots.append(edge_audit.make_opponent(opps[k], map_seed * 4 + i))
            names[i] = opps[k]
            k += 1
    tr = mybot.Tracker()
    tr.cfg = dict(mybot.PARAMS)
    fc = mybot.Forecaster()
    seat = myseat + 1
    g = engine.Game(base=engine.make_map(seed=map_seed), start_token=token)
    rec = []            # per turn: {j: (pos, frozen, post_goal, post_dist, prior_goal, prior_dist)}
    last_act = None
    while not g.over():
        vs = g.views()
        base, owner, upg, occ, frz, home_of = parse(vs[myseat])
        tr.observe(owner, upg, occ, frz, seat, vs[myseat].is_priority_token, base,
                   home_of, last_act)
        R = max(1, mybot.MAX_TURNS - tr.turn + 1)
        fc.update(tr, owner, upg, base, home_of, seat, R)
        snap = {}
        for j in range(4):
            if j == myseat or tr.pos[j] is None or fc.belief[j] is None:
                continue
            sc, _nd = fc.scores(j + 1, tr.pos[j], owner, upg, base, home_of, R)
            pr = fc._prior(sc)
            b = fc.belief[j]
            snap[j] = (tr.pos[j], bool(frz[tr.pos[j]]), max(range(64), key=lambda c: b[c]),
                       b, max(range(64), key=lambda c: pr[c]), pr)
        rec.append(snap)
        acts = []
        for i in range(4):
            try:
                a = bots[i](vs[i])
            except Exception:
                a = "STAY"
            acts.append(a if a in vs[i].legal_actions else "STAY")
        last_act = acts[myseat]
        g.step(acts)
    # score the forecasts against what happened
    out = {}
    T = len(rec)
    for j in range(4):
        if j == myseat:
            continue
        st = out.setdefault(names[j], {"n": 0, "post_top1": 0, "prior_top1": 0,
                                       "stay_top1": 0, "post_p": 0.0, "prior_p": 0.0,
                                       "arr_n": 0, "arr_err": 0.0,
                                       "pos": dict((h, [0, 0.0, 0.0, 0.0, 0.0]) for h in HORIZONS)})
        pos = [rec[t][j][0] if j in rec[t] else None for t in range(T)]
        frz_ = [rec[t][j][1] if j in rec[t] else True for t in range(T)]
        for t in range(1, T - 1):
            if j not in rec[t] or pos[t] is None or frz_[t]:
                continue
            if pos[t + 1] == pos[t]:
                continue                     # only forecast rivals that are moving
            dest, h = None, None
            for u in range(t + 1, T - 1):
                if pos[u + 1] == pos[u] and not frz_[u]:
                    dest, h = pos[u], u - t
                    break
            if dest is None:
                continue
            _p, _f, pg, pdist, qg, qdist = rec[t][j]
            st["n"] += 1
            st["post_top1"] += pg == dest
            st["prior_top1"] += qg == dest
            st["stay_top1"] += pos[t] == dest
            st["post_p"] += pdist[dest]
            st["prior_p"] += qdist[dest]
            if pg == dest:
                st["arr_n"] += 1
                st["arr_err"] += abs(mybot.MANH[pos[t]][pg] - h)
            prev = pos[t - 1]
            for hz in HORIZONS:
                if t + hz >= T or pos[t + hz] is None:
                    continue
                truth = pos[t + hz]
                e = st["pos"][hz]
                e[0] += 1
                e[1] += mybot.MANH[walk(pos[t], pg, hz)][truth]
                e[2] += mybot.MANH[walk(pos[t], qg, hz)][truth]
                e[3] += mybot.MANH[pos[t]][truth]
                e[4] += mybot.MANH[momentum(prev, pos[t], hz)][truth]
    return out


def merge(a, b):
    for nm, s in b.items():
        t = a.setdefault(nm, None)
        if t is None:
            a[nm] = s
            continue
        for key in ("n", "post_top1", "prior_top1", "stay_top1", "post_p", "prior_p",
                    "arr_n", "arr_err"):
            t[key] += s[key]
        for hz in HORIZONS:
            for i in range(5):
                t["pos"][hz][i] += s["pos"][hz][i]
    return a


def main():
    games = int(sys.argv[1]) if len(sys.argv) > 1 else 200
    tier = sys.argv[2] if len(sys.argv) > 2 else "unknown"
    edge_audit.tee_to(edge_audit.result_path("forecast", tier, games))
    tasks = edge_audit.tasks_for(games, tier, seed=41)
    with mp.Pool(min(4, mp.cpu_count())) as pool:
        parts = pool.map(play, tasks, chunksize=5)
    tot = {}
    for p in parts:
        merge(tot, p)
    allst = {"n": 0, "post_top1": 0, "prior_top1": 0, "stay_top1": 0, "post_p": 0.0,
             "prior_p": 0.0, "arr_n": 0, "arr_err": 0.0,
             "pos": dict((h, [0, 0.0, 0.0, 0.0, 0.0]) for h in HORIZONS)}
    for s in tot.values():
        for key in ("n", "post_top1", "prior_top1", "stay_top1", "post_p", "prior_p",
                    "arr_n", "arr_err"):
            allst[key] += s[key]
        for hz in HORIZONS:
            for i in range(5):
                allst["pos"][hz][i] += s["pos"][hz][i]
    print("[%s] %d games, bot %s, forecaster constants fixed (beta 2, rho 0.9, kappa 3)"
          % (tier, games, edge_audit.bot_label()))
    print("\nNEXT DESTINATION of a moving rival (the next cell it stays on)")
    print("%-14s %6s   %-21s %-21s %s" % ("opponent", "cases", "top-1: forecast/prior/stay",
                                          "P(true): fcst/prior", "arrival err (turns)"))

    def row(nm, s):
        n = max(1, s["n"])
        print("%-14s %6d   %5.1f%% %5.1f%% %5.1f%%   %6.3f  %6.3f        %s"
              % (nm, s["n"], 100.0 * s["post_top1"] / n, 100.0 * s["prior_top1"] / n,
                 100.0 * s["stay_top1"] / n, s["post_p"] / n, s["prior_p"] / n,
                 ("%.2f" % (s["arr_err"] / s["arr_n"])) if s["arr_n"] else "-"))
    for nm in sorted(tot, key=lambda k: -tot[k]["post_top1"] / max(1, tot[k]["n"])):
        row(nm, tot[nm])
    row("ALL", allst)
    print("\nPOSITION k turns ahead: mean Manhattan error (lower is better)")
    print("%-4s %7s   %8s %8s %8s %8s" % ("k", "cases", "forecast", "prior", "stay", "momentum"))
    for hz in HORIZONS:
        e = allst["pos"][hz]
        n = max(1, e[0])
        print("%-4d %7d   %8.2f %8.2f %8.2f %8.2f"
              % (hz, e[0], e[1] / n, e[2] / n, e[3] / n, e[4] / n))


if __name__ == "__main__":
    main()
