"""
Comprehensive Simulation Suite comparing:
  1. v6_improved (mybot.Agent / bot.py with all 7 bug fixes + affine precomputation)
  2. v6_original (original unpatched baseline Agent before the 7 bug fixes)
  3. minimax     (minimax_bot.GreedyPrunedMinimaxBot)
  4. v3, v2, v1  (historical parameter snapshots)
  5. All 7 zoo.ZOO archetypes + all 6 holdout.HOLDOUT archetypes
"""
import json
import os
import random
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import arena
import engine
import holdout
import minimax_bot
import mybot
import zoo

BEST_PARAMS = json.load(open("best_params.json"))
SNAPS = json.load(open("snapshots.json"))


class OriginalV6Agent(mybot.Agent):
    """
    Faithful reproduction of the original unpatched v6 Agent before our 7 bug
    fixes (no corner symmetry tie-breaking, no step discount, no shield_risk
    cooldown-expiry floor, no prog_me only_t0 guard) to measure the exact
    gameplay and latency improvement of v6_improved vs v6_original.
    """

    def _candidates(self, owner, upg, base, home_of, occ, seat, me, R, care):
        P = self.P
        tr = self.tr
        dist = mybot.DIST[me]
        out = []
        maxd = P["reach"]
        for p in range(mybot.NC):
            d = dist[p]
            if d > maxd:
                continue
            o = owner[p]
            if o == seat:
                if upg[p]:
                    continue
                kind = 1
                v = base[p]
                need = 3
            elif o == 0:
                kind = 0
                v = base[p]
                need = 1
            else:
                if home_of[p]:
                    continue
                kind = 2
                v = base[p]
                need = 3 if upg[p] else 1
            if p == me and tr.prog[seat - 1]:
                need = max(1, need - tr.prog[seat - 1])
            if d + need > R:
                continue
            pri = v * (R - d - need) / float(d + need)
            if kind == 2:
                pri += 8.0 * v * (2 if upg[p] else 1) / float(d + need)
            if occ[p] and p != me:
                pri *= 0.3
            if tr.zone[p] == seat:
                pri *= P["zone_bonus"]
            out.append((pri, p, kind, v, need))
            if p == me and o == seat and P["hold"] > 0.0:
                thr = self._threat(p, owner, upg, base, occ, seat, R, care)
                if thr > 0.0:
                    out.append((thr, p, 4, v, 1))
            if kind == 0 and P["combo"] > 0.0 and d + 4 <= R:
                out.append((pri * P["combo_pri"], p, 3, v, need + 3))
        out.sort(reverse=True)
        return out[:P["ncand"]]

    def _plan_walk(self, owner, upg, base, home_of, occ, frz, seat, me, R,
                   kappa, care):
        P = self.P
        tr = self.tr
        mydist = mybot.DIST[me]
        mod = [1.0] * mybot.NC
        zone = tr.zone
        perish = 1.0 + P["perish"]
        safe = P["safe_discount"]
        zb = P["zone_bonus"]
        sq = P["squat_penalty"]
        for p in range(mybot.NC):
            m = 1.0
            rd = 99
            for j in range(4):
                if j == seat - 1 or tr.pos[j] is None:
                    continue
                dj = mybot.MANH[tr.pos[j]][p]
                if dj < rd:
                    rd = dj
            if rd < mydist[p]:
                m = perish
            elif rd > mydist[p] + 3:
                m = safe
            if zone[p] == seat:
                m *= zb
            elif (P["steal"] > 0.0 and tr.turn <= P["steal_until"]
                  and base[p] >= P["steal_min"]):
                m *= (1.0 + P["steal"])
            if occ[p] and p != me:
                m *= sq
            mod[p] = m
        self._cellmod = mod

        cands = self._candidates(owner, upg, base, home_of, occ, seat, me, R, care)
        if not cands:
            return self._idle(owner, upg, base, occ, seat, me, R, care)
        horizon = R if R < P["horizon"] else P["horizon"]

        cellbit = {}
        for (_, p, _, _, _) in cands:
            if p not in cellbit:
                cellbit[p] = len(cellbit)

        beam = {(me, 0, 0): (0.0, None)}
        bestby = {}
        tick = 0
        deadline = self._deadline
        perf = time.perf_counter
        width = max(8, int(P["beam"] * self._beam_scale))
        for _ in range(P["visits"]):
            if perf() > deadline:
                break
            nxt = {}
            for (pos, used, mask), (val, first) in beam.items():
                tick += 1
                if not (tick & 15) and perf() > deadline:
                    break
                for (_, p, kind, v, need) in cands:
                    bit = 1 << cellbit[p]
                    if mask & bit:
                        continue
                    travel = mybot.DIST[pos][p]
                    nu = used + travel + need
                    if nu > horizon or nu > R:
                        continue
                    g = self._work_gain(p, kind, v, need, used + travel, owner,
                                        upg, occ, seat, R, kappa, care, travel)
                    if g is None:
                        continue
                    nv = val + g
                    f = first if first is not None else p
                    st = (p, nu, mask | bit)
                    cur = nxt.get(st)
                    if cur is None or cur[0] < nv:
                        nxt[st] = (nv, f)
                    if bestby.get(f, -1e18) < nv:
                        bestby[f] = nv
            if not nxt:
                break
            if len(nxt) > width:
                items = sorted(nxt.items(), key=lambda kv: -kv[1][0])[:width]
                beam = dict(items)
            else:
                beam = nxt
        if not bestby:
            return self._idle(owner, upg, base, occ, seat, me, R, care)
        stick = P["stickiness"]
        target, tv = None, -1e18
        for f, v in bestby.items():
            s = v * (stick if f == self.plan_target else 1.0)
            if s > tv:
                tv, target = s, f
        self.plan_target = target
        if target == me:
            return "STAY"
        return self._step(me, target, occ, owner, seat)

    def _shield_risk(self, ridx, travel, need):
        P = self.P
        tr = self.tr
        if tr.frozen[ridx] >= travel + need:
            return 0.0
        cd = tr.cd[ridx]
        if cd >= travel + need:
            return 0.0
        exposed = need if cd <= travel else max(0, travel + need - cd)
        if exposed <= 0:
            return 0.0
        q = tr.q_shield(ridx, P["q_prior"], P["q_weight"])
        return 1.0 - (1.0 - q) ** exposed

    def _step(self, me, target, occ, owner, seat):
        tr = self.tr
        blocked = set(p for p in range(mybot.NC) if occ[p] and p != me)
        d = mybot._bfs(target, blocked)
        if d[me] >= 99:
            d = mybot.DIST[target]
        want = d[me] - 1
        cands = [w for w in mybot.NEIGH[me] if w not in blocked and d[w] == want]
        if not cands:
            cands = [w for w in mybot.NEIGH[me] if w not in blocked and d[w] < d[me]]
        if not cands:
            return "STAY"
        myrank = (seat - tr.token) % 4 if tr.token_known else 0
        bestw, bestk = None, -1e18
        for w in cands:
            k = 0.0
            if owner[w] == 0:
                k += 0.4
            elif owner[w] == seat:
                k += 0.1
            for n2 in mybot.NEIGH[w]:
                o2 = occ[n2]
                if o2 and o2 != seat:
                    if tr.token_known and (o2 - tr.token) % 4 < myrank:
                        k -= self.P["contest_penalty"]
                    else:
                        k -= self.P["contest_penalty"] * 0.3
            if k > bestk:
                bestk, bestw = k, w
        return mybot.STEP_NAME[(me, bestw)]


def run_paired_series(bot_factories, opp_pool, n_games=80, seed=100):
    """
    Run `n_games` paired games where each entrant in `bot_factories` plays the
    exact same map, seat, starting token, and 3 opponents drawn from `opp_pool`.
    """
    rnd = random.Random(seed)
    results = {name: {"pw": 0.0, "score": 0.0, "first": 0, "place": 0.0, "ms_total": 0.0, "turns": 0, "max_ms": 0.0}
               for name in bot_factories}

    specs = []
    for g_idx in range(n_games):
        map_seed = rnd.randrange(1 << 30)
        seat = g_idx % 4
        token = (g_idx % 4) + 1
        opps = [opp_pool[rnd.randrange(len(opp_pool))] for _ in range(3)]
        specs.append((map_seed, seat, token, opps, g_idx))

    for map_seed, seat, token, opps, g_idx in specs:
        base = engine.make_map(seed=map_seed)
        for name, factory in bot_factories.items():
            bots = []
            opp_iter = iter(opps)
            for i in range(4):
                if i == seat:
                    bots.append(factory(g_idx * 17 + i))
                else:
                    ocls = next(opp_iter)
                    bots.append(ocls(g_idx * 31 + i))
            g = engine.Game(base=base, start_token=token)
            while not g.over():
                vs = g.views()
                acts = [None] * 4
                for i in range(4):
                    if i == seat:
                        t0 = time.perf_counter()
                        acts[i] = bots[i](vs[i])
                        dt = (time.perf_counter() - t0) * 1000.0
                        results[name]["ms_total"] += dt
                        results[name]["turns"] += 1
                        if dt > results[name]["max_ms"]:
                            results[name]["max_ms"] = dt
                    else:
                        acts[i] = bots[i](vs[i])
                g.step(acts)
            pl = g.places()
            pws = arena.pairwise_wins(pl)
            w, d, _ = pws[seat]
            results[name]["pw"] += w + 0.5 * d
            results[name]["score"] += g.score[seat]
            results[name]["place"] += pl[seat]
            if pl[seat] == 1.0:
                results[name]["first"] += 1

    return results, n_games


def print_paired_table(title, results, n_games):
    print("\n" + "=" * 78)
    print(title)
    print("=" * 78)
    print("%-18s %7s %8s %7s %7s %9s %9s" %
          ("Bot", "PW/3", "Score", "Place", "1st%", "Mean ms", "Max ms"))
    print("-" * 78)
    rows = sorted(results.items(), key=lambda kv: (-kv[1]["pw"], -kv[1]["score"]))
    for name, r in rows:
        mean_ms = r["ms_total"] / max(1, r["turns"])
        print("%-18s %7.2f %8.0f %7.2f %6.1f%% %8.2fms %8.2fms" %
              (name, r["pw"] / n_games, r["score"] / n_games,
               r["place"] / n_games, 100.0 * r["first"] / n_games,
               mean_ms, r["max_ms"]))


def run_direct_h2h(n_games=80, seed=777):
    """
    Direct 4-bot table matchups with v6_improved, v6_original, minimax, and zoo/holdout bots.
    """
    reg = arena.Registry()
    reg.add("v6_improved", lambda s: mybot.Agent(seed=s, params=BEST_PARAMS))
    reg.add("v6_original", lambda s: OriginalV6Agent(seed=s, params=SNAPS["v6"]))
    reg.add("minimax", lambda s: minimax_bot.GreedyPrunedMinimaxBot(seed=s, params=BEST_PARAMS))
    reg.add("v3_snap", lambda s: mybot.Agent(seed=s, params=SNAPS["v3"]))
    for cls in zoo.ZOO:
        reg.add(cls.name, (lambda c: (lambda s: c(s)))(cls))
    for cls in holdout.HOLDOUT:
        reg.add("H_" + cls.name, (lambda c: (lambda s: c(s)))(cls))

    # 1. Full 17-bot All-Play-All Tournament (400 games)
    print("\n" + "=" * 78)
    print("1. FULL 17-ENTRANT TOURNAMENT (v6_improved, v6_original, minimax, v3, ZOO, HOLDOUT) — 400 GAMES")
    print("=" * 78)
    t0 = time.time()
    st_all = arena.tournament(reg, reg.names(), games=400, seed=42, verbose=False)
    print(st_all.table(sort="elo"))
    print("Completed in %.1fs" % (time.time() - t0))

    # 2. Direct 4-Bot Championship Table: [v6_improved, v6_original, minimax, top opponent] (80 games)
    print("\n" + "=" * 78)
    print("2. DIRECT 4-BOT CHAMPIONSHIP TABLE (v6_improved vs v6_original vs minimax vs rotating ZOO/HOLDOUT) — 80 GAMES")
    print("=" * 78)
    guest_pool = [cls.name for cls in zoo.ZOO] + ["H_" + cls.name for cls in holdout.HOLDOUT]
    st_direct = arena.Stats(["v6_improved", "v6_original", "minimax"] + guest_pool)
    rnd = random.Random(seed)
    for gi in range(n_games):
        guest = guest_pool[gi % len(guest_pool)]
        names = ["v6_improved", "v6_original", "minimax", guest]
        rnd.shuffle(names)
        sc, pl, pw = arena.run_game(reg, names, map_seed=2000 + gi,
                                    token=(gi % 4) + 1, game_seed=gi)
        st_direct.add_game(names, sc, pl, pw)
    # Print summary for the 3 main bots in the direct table
    print("%-16s %7s %6s %8s %6s %6s %6s" %
          ("bot", "elo", "PW/3", "score", "place", "1st%", "games"))
    print("-" * 60)
    for n in ["v6_improved", "v6_original", "minimax"]:
        g = max(1, st_direct.games[n])
        print("%-16s %7.0f %6.2f %8.0f %6.2f %5.0f%% %6d" %
              (n, st_direct.elo[n], st_direct.pw[n] / g, st_direct.score[n] / g,
               st_direct.place[n] / g, 100.0 * st_direct.firsts[n] / g, g))
    print("\n" + st_direct.h2h_table("v6_improved"))
    print("\n" + st_direct.h2h_table("minimax"))


if __name__ == "__main__":
    factories = {
        "v6_improved": lambda s: mybot.Agent(seed=s, params=BEST_PARAMS),
        "v6_original": lambda s: OriginalV6Agent(seed=s, params=SNAPS["v6"]),
        "minimax": lambda s: minimax_bot.GreedyPrunedMinimaxBot(seed=s, params=BEST_PARAMS),
        "v3_snap": lambda s: mybot.Agent(seed=s, params=SNAPS["v3"]),
    }

    # Paired benchmark 1: vs ZOO (60 games)
    res_zoo, n_z = run_paired_series(factories, zoo.ZOO, n_games=60, seed=101)
    print_paired_table("PAIRED BENCHMARK A: vs ZOO OPPONENTS (60 identical map/seat/opponent games)", res_zoo, n_z)

    # Paired benchmark 2: vs HOLDOUT (60 games)
    res_hold, n_h = run_paired_series(factories, holdout.HOLDOUT, n_games=60, seed=202)
    print_paired_table("PAIRED BENCHMARK B: vs HOLDOUT OPPONENTS (60 identical map/seat/opponent games)", res_hold, n_h)

    # Full tournament & direct head-to-head championship
    run_direct_h2h(n_games=80, seed=303)
