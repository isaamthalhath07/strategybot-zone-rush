"""Scoring, statistics and the written report for harness/simulate.py.

Everything here is a pure function of the files a simulation session writes
(session.json and games.jsonl), so a report can be rebuilt at any time:

    python harness/simulate.py --report harness/simulations/<session>

How results are scored follows the official rulebook:

  2.7  Places run 1st to 4th by final score, and equal totals share a place.
  3.2  Round 1 is an Elo rating in which every four-bot game counts as three
       one-on-one results per bot: finishing above a bot is a win against it,
       below it a loss, and equal final scores a draw (cells do not matter).
       Every bot starts on the same rating; bots on the same rating are separated
       by head-to-head results, then by more 1st-place finishes.
  5.3  Round 2 ranks a game by score, then by cells owned at the end; a pool game
  5.4  pays 3/2/1/0 and teams sharing a place split those points.
"""
import datetime
import json
import math
import os
import random
import statistics

POOL_POINTS = (3, 2, 1, 0)
ACTIONS = ("NORTH", "EAST", "SOUTH", "WEST", "STAY", "SHIELD")
FAULTS = ("crash", "illegal", "late", "killed", "died", "load-failed")
FAULT_HELP = {
    "crash": "act() raised an exception",
    "illegal": "act() returned something not in state.legal_actions",
    "late": "act() answered after the time limit (200 ms, 2 s on turn 1)",
    "killed": "act() did not answer within the harness's hard limit, so the worker was killed and restarted",
    "died": "the bot's process exited (for example sys.exit or os._exit)",
    "load-failed": "the file could not be imported, so the bot never ran",
}
CHECKPOINTS = (20, 40, 60)
COUNTERS = ("free", "frozen", "idle", "moves", "blocked", "contests_won", "contests_lost", "claims",
            "claim_value", "upgrades", "raids", "raids_l2", "raid_bonus", "cells_lost", "bonus_conceded",
            "shields", "shield_hits", "catches", "backfires", "caught", "income", "bonus", "printed")


# -- scoring rules ---------------------------------------------------------------------

def round1_places(scores):
    """Rulebook 2.7: places 1st-4th by score; equal totals share a place."""
    return [1 + sum(1 for o in scores if o > s) for s in scores]


def round2_places(scores, cells):
    """Rulebook 5.3: score first, then cells owned at the end; still level shares the place."""
    keys = list(zip(scores, cells))
    return [1 + sum(1 for o in keys if o > k) for k in keys]


def pool_points(places):
    """Rulebook 5.4: 3/2/1/0, and teams sharing a place split the points of the places they cover."""
    out = []
    for p in places:
        k = places.count(p)
        out.append(sum(POOL_POINTS[p - 1:p - 1 + k]) / float(k))
    return out


def one_on_one(a, b):
    """Rulebook 3.2: above is a win (1), below a loss (0), equal final scores a draw (0.5)."""
    return 1.0 if a > b else 0.5 if a == b else 0.0


# -- compressing a replay into one row -----------------------------------------------------

def _last_line(text, limit=300):
    lines = (text or "").strip().splitlines()
    return lines[-1][:limit] if lines else ""


def game_record(rp, meta):
    """One finished replay (from match.Match) -> the compact row kept in games.jsonl.

    meta carries the scheduling facts: n, block, rot, seats (entrant codes in seat order),
    map (the spec), token, seconds, replay, notable."""
    res = rp.get("result") or {}
    turns = rp.get("turns") or []
    base = rp.get("base") or []
    scores = list(res.get("score") or [0, 0, 0, 0])
    cells = list(res.get("cells") or [0, 0, 0, 0])
    upgraded = list(res.get("upgraded") or [0, 0, 0, 0])
    r1 = round1_places(scores)
    r2 = round2_places(scores, cells)
    pts = pool_points(r2)
    per = []
    for i in range(4):
        load = (rp.get("seats") or [{}] * 4)[i].get("load") or {}
        row = {"seat": i + 1, "entrant": meta["seats"][i], "score": scores[i], "cells": cells[i],
               "upgraded": upgraded[i], "place": r1[i], "place2": r2[i], "pool": pts[i],
               "load_ok": bool(load.get("ok")), "load_ms": load.get("ms"), "load_error": _last_line(load.get("error")),
               "restarts": (rp.get("seats") or [{}] * 4)[i].get("restarts", 0),
               "turns": 0, "status": {}, "ms_max": None, "ms_sum": 0.0, "ms_n": 0, "ms_first": None,
               "half": 0, "three_q": 0, "over": 0, "error": "", "actions": dict((a, 0) for a in ACTIONS)}
        for k in COUNTERS:
            row[k] = 0
        for t in CHECKPOINTS:
            row["at%d" % t] = None
        per.append(row)
    prev = rp.get("initial") or {}
    for rec in turns:
        turn = rec.get("turn")
        frozen_before = prev.get("frozen") or [0, 0, 0, 0]
        need_before = prev.get("need") or [1, 1, 1, 1]
        for i in range(4):
            b = rec["bots"][i]
            s = per[i]
            s["turns"] += 1
            s["status"][b["status"]] = s["status"].get(b["status"], 0) + 1
            if b.get("ms") is not None and b["status"] != "killed":
                ms = float(b["ms"])
                s["ms_sum"] += ms
                s["ms_n"] += 1
                s["ms_max"] = ms if s["ms_max"] is None else max(s["ms_max"], ms)
                if turn == 1:
                    s["ms_first"] = ms
                limit = float(b.get("limit_ms") or 200)
                if ms > 0.5 * limit:
                    s["half"] += 1
                if ms > 0.75 * limit:
                    s["three_q"] += 1
            if b.get("over"):
                s["over"] += 1
            if b.get("out"):
                s["printed"] += 1
            if b.get("error") and not s["error"]:
                s["error"] = _last_line(b["error"])
            if frozen_before[i] > 0:
                s["frozen"] += 1                 # forced STAY; the bot's choice is ignored
            else:
                s["free"] += 1
                used = b.get("used") if b.get("used") in ACTIONS else "STAY"
                s["actions"][used] += 1
                if used == "STAY" and need_before[i] == 0:
                    s["idle"] += 1               # a stay on a cell with nothing left to gain
        for e in rec.get("events") or []:
            kind = e.get("type")
            seat = e.get("seat")
            s = per[seat - 1] if seat in (1, 2, 3, 4) else None
            if kind == "move":
                s["moves"] += 1
            elif kind == "blocked":
                s["blocked"] += 1
            elif kind == "contest":
                per[e["winner"] - 1]["contests_won"] += 1
            elif kind == "lost":
                s["contests_lost"] += 1
            elif kind == "claim":
                s["claims"] += 1
                s["claim_value"] += e.get("base", 0)
            elif kind == "upgrade":
                s["upgrades"] += 1
            elif kind == "raid":
                s["raids"] += 1
                s["raid_bonus"] += e.get("bonus", 0)
                if e.get("level") == 2:
                    s["raids_l2"] += 1
                victim = per[e["from"] - 1]
                victim["cells_lost"] += 1
                victim["bonus_conceded"] += e.get("bonus", 0)
            elif kind == "shield":
                s["shields"] += 1
                caught = e.get("caught") or []
                s["catches"] += len(caught)
                if caught:
                    s["shield_hits"] += 1
                if e.get("backfire"):
                    s["backfires"] += 1
            elif kind == "freeze" and e.get("why") == "caught":
                s["caught"] += 1
        for i in range(4):
            per[i]["income"] += (rec.get("income") or [0] * 4)[i]
            per[i]["bonus"] += (rec.get("bonus") or [0] * 4)[i]
            if turn in CHECKPOINTS:
                per[i]["at%d" % turn] = rec["state"]["score"][i]
        prev = rec.get("state") or prev
    for s in per:
        # every point is either income or a raid bonus; anything else is a referee bug
        s["consistent"] = s["income"] + s["bonus"] == s["score"]
    quadrant = None
    if len(base) == 64:
        quadrant = "/".join("".join(str(base[r * 8 + c]) for c in range(4)) for r in range(4))
    return {"n": meta["n"], "block": meta.get("block"), "rot": meta.get("rot"), "status": rp.get("status"),
            "error": rp.get("error"), "map": meta["map"], "quadrant": quadrant,
            "home": base[0] if base else None, "token": meta["token"], "turns": len(turns),
            "seconds": meta.get("seconds"), "finished": meta.get("finished"), "replay": meta.get("replay"),
            "notable": meta.get("notable") or [], "seats": per}


def notable_reasons(row):
    """Why a game is worth keeping as a replay: anything that broke the normal flow."""
    out = []
    if row["status"] != "done":
        out.append("game %s%s" % (row["status"], ": " + row["error"] if row.get("error") else ""))
    for s in row["seats"]:
        bad = ["%s x%d" % (k, v) for k, v in sorted(s["status"].items()) if k != "ok"]
        if bad:
            out.append("seat %d (%s): %s" % (s["seat"], s["entrant"], ", ".join(bad)))
        elif s["restarts"]:
            out.append("seat %d (%s): %d restart(s)" % (s["seat"], s["entrant"], s["restarts"]))
        if not s.get("consistent", True):
            out.append("seat %d: score is not income + bonuses" % s["seat"])
    return out


# -- ratings -------------------------------------------------------------------------------

def pair_results(game, index):
    """The game's one-on-one results as (a, b, score of a) between different entrants."""
    seats = game["seats"]
    out = []
    for i in range(4):
        for j in range(i + 1, 4):
            a, b = index[seats[i]["entrant"]], index[seats[j]["entrant"]]
            if a == b:
                continue                  # two copies of one bot say nothing about either
            out.append((a, b, one_on_one(seats[i]["score"], seats[j]["score"])))
    return out


def sequential_elo(results, n, k, start):
    """Chess-style Elo over the games in order; each game's three-per-bot updates are
    computed from the ratings before that game and applied together."""
    r = [float(start)] * n
    for pairs in results:
        delta = [0.0] * n
        for a, b, s in pairs:
            e = 1.0 / (1.0 + 10.0 ** ((r[b] - r[a]) / 400.0))
            delta[a] += k * (s - e)
            delta[b] += k * ((1.0 - s) - (1.0 - e))
        for i in range(n):
            r[i] += delta[i]
    return r


def tally(results, n, weights=None):
    w = [[0.0] * n for _ in range(n)]
    g = [[0.0] * n for _ in range(n)]
    for idx, pairs in enumerate(results):
        m = 1.0 if weights is None else weights[idx]
        if not m:
            continue
        for a, b, s in pairs:
            w[a][b] += m * s
            w[b][a] += m * (1.0 - s)
            g[a][b] += m
            g[b][a] += m
    return w, g


MAX_UNITS = 1000
MIN_DRAWS = 20          # fewer usable bootstrap draws than this and an interval is not reported


def resampling_units(games, results):
    """Group each game's one-on-one results by schedule block (games are listed in order), merging
    neighbouring blocks if there are more than MAX_UNITS, and pre-add each unit into
    (a, b, points of a, meetings) with a < b."""
    blocks = {}
    for g, pairs in zip(games, results):
        key = g.get("block")
        blocks.setdefault(("b", key) if key is not None else ("n", g["n"]), []).append(pairs)
    groups = list(blocks.values())
    if len(groups) > MAX_UNITS:
        size = int(math.ceil(len(groups) / float(MAX_UNITS)))
        groups = [sum(groups[i:i + size], []) for i in range(0, len(groups), size)]
    units = []
    for group in groups:
        d = {}
        for pairs in group:
            for a, b, s in pairs:
                if a > b:
                    a, b, s = b, a, 1.0 - s
                cell = d.setdefault((a, b), [0.0, 0])
                cell[0] += s
                cell[1] += 1
        units.append([(a, b, ws, gs) for (a, b), (ws, gs) in d.items()])
    return units


def bradley_terry(w, g, start, prior=1.0, init=None, tol=1e-9, iters=20000):
    """Maximum-likelihood ratings on the Elo scale, P(a beats b) = 1 / (1 + 10^((Rb-Ra)/400)),
    draws counting half. This is the rating vector at which every bot's expected Elo change
    is zero, i.e. where sequential Elo settles. A weak prior (one win and one loss against an
    average opponent) keeps an unbeaten or winless bot finite. Returns ratings centred on start."""
    n = len(w)
    if n == 0:
        return [], []
    p = list(init) if init else [1.0] * n
    for _ in range(iters):
        worst = 0.0
        for i in range(n):
            wins = sum(w[i]) + prior
            den = 2.0 * prior / (p[i] + 1.0)
            for j in range(n):
                if g[i][j]:
                    den += g[i][j] / (p[i] + p[j])
            new = wins / den
            worst = max(worst, abs(math.log(new / p[i])))
            p[i] = new
        if worst < tol:
            break
    r = [400.0 * math.log10(x) for x in p]
    mean = sum(r) / n
    return [x - mean + start for x in r], p


def wilson(points, n, z=1.96):
    if n <= 0:
        return (0.0, 1.0)
    phat = points / float(n)
    den = 1.0 + z * z / n
    centre = (phat + z * z / (2.0 * n)) / den
    half = z * math.sqrt(phat * (1.0 - phat) / n + z * z / (4.0 * n * n)) / den
    return (max(0.0, centre - half), min(1.0, centre + half))


def percentile(sorted_values, q):
    if not sorted_values:
        return None
    pos = q * (len(sorted_values) - 1)
    lo = int(math.floor(pos))
    hi = min(lo + 1, len(sorted_values) - 1)
    return sorted_values[lo] + (sorted_values[hi] - sorted_values[lo]) * (pos - lo)


# -- analysis ------------------------------------------------------------------------------

def _acc():
    return {"apps": 0, "games": set(), "scores": [], "cells": [], "upgraded": [], "margins": [],
            "places": [0, 0, 0, 0, 0], "outright": 0, "r2places": [0, 0, 0, 0, 0], "pool": 0.0,
            "W": 0, "D": 0, "L": 0, "beaten": 0.0,
            "seat": {}, "offset": {}, "mapkind": {}, "home": {},
            "status": {}, "turns": 0, "ms_max": None, "ms_sum": 0.0, "ms_n": 0, "first_max": None,
            "half": 0, "three_q": 0, "over": 0, "load_max": None, "load_fail_games": 0, "restarts": 0,
            "errors": {}, "actions": dict((a, 0) for a in ACTIONS), "c": dict((k, 0) for k in COUNTERS),
            "at": dict((t, []) for t in CHECKPOINTS), "inconsistent": 0, "worst": None}


def _bucket(d, key, pts, k):
    cell = d.setdefault(key, [0.0, 0])
    cell[0] += pts
    cell[1] += k


def map_label(spec):
    kind = (spec or {}).get("kind", "example")
    if kind == "random":
        return "random:%s" % spec.get("seed")
    if kind == "custom":
        return "custom:%s" % spec.get("quadrant")
    return "example"


def analyze(session, games, bootstrap=200, seed=12345):
    entrants = session["entrants"]
    codes = [e["code"] for e in entrants]
    index = dict((c, i) for i, c in enumerate(codes))
    n = len(codes)
    settings = session.get("settings") or {}
    k_factor = float(settings.get("elo_k", 16))
    start = float(settings.get("elo_start", 1500))
    seen = set()
    unique = []
    for g in sorted(games, key=lambda g: g["n"]):
        if g["n"] in seen:
            continue
        seen.add(g["n"])
        unique.append(g)
    counted, excluded = [], []
    for g in unique:
        ok = g["status"] == "done" and len(g["seats"]) == 4 and all(s["entrant"] in index for s in g["seats"])
        (counted if ok else excluded).append(g)

    acc = [_acc() for _ in range(n)]
    h2h = [[[0, 0, 0] for _ in range(n)] for _ in range(n)]       # W, D, L of row against column
    results = []
    duplicates = 0
    map_counts = {}
    token_counts = {}
    cell_tiebreak_games = 0
    for g in counted:
        seats = g["seats"]
        pairs = pair_results(g, index)
        results.append(pairs)
        if len(set(s["entrant"] for s in seats)) < 4:
            duplicates += 1
        kind = (g["map"] or {}).get("kind", "example")
        map_counts[kind] = map_counts.get(kind, 0) + 1
        token_counts[g["token"]] = token_counts.get(g["token"], 0) + 1
        if round1_places([s["score"] for s in seats]) != [s["place2"] for s in seats]:
            cell_tiebreak_games += 1
        top = max(s["score"] for s in seats)
        firsts = sum(1 for s in seats if s["place"] == 1)
        for i, s in enumerate(seats):
            e = index[s["entrant"]]
            a = acc[e]
            a["apps"] += 1
            a["games"].add(g["n"])
            a["scores"].append(s["score"])
            a["cells"].append(s["cells"])
            a["upgraded"].append(s["upgraded"])
            a["margins"].append(s["score"] - top)
            a["places"][s["place"]] += 1
            if s["place"] == 1 and firsts == 1:
                a["outright"] += 1
            a["r2places"][s["place2"]] += 1
            a["pool"] += s["pool"]
            a["beaten"] += sum(one_on_one(s["score"], o["score"]) for j, o in enumerate(seats) if j != i)
            pts, k = 0.0, 0
            for j, o in enumerate(seats):
                if j == i or o["entrant"] == s["entrant"]:
                    continue
                v = one_on_one(s["score"], o["score"])
                pts += v
                k += 1
                cell = h2h[e][index[o["entrant"]]]
                cell[0 if v == 1.0 else 1 if v == 0.5 else 2] += 1
                a["W" if v == 1.0 else "D" if v == 0.5 else "L"] += 1
            if k:
                _bucket(a["seat"], s["seat"], pts, k)
                _bucket(a["offset"], (s["seat"] - g["token"]) % 4, pts, k)
                _bucket(a["mapkind"], kind, pts, k)
                _bucket(a["home"], g.get("home"), pts, k)
                key = (pts / k, s["score"] - top)
                if a["worst"] is None or key < a["worst"][0]:
                    a["worst"] = (key, g["n"], s["seat"])
            for st, v in s["status"].items():
                a["status"][st] = a["status"].get(st, 0) + v
            a["turns"] += s["turns"]
            if s["ms_max"] is not None:
                a["ms_max"] = s["ms_max"] if a["ms_max"] is None else max(a["ms_max"], s["ms_max"])
            a["ms_sum"] += s["ms_sum"]
            a["ms_n"] += s["ms_n"]
            if s["ms_first"] is not None:
                a["first_max"] = s["ms_first"] if a["first_max"] is None else max(a["first_max"], s["ms_first"])
            a["half"] += s["half"]
            a["three_q"] += s["three_q"]
            a["over"] += s["over"]
            if s["load_ms"] is not None and s["load_ok"]:
                a["load_max"] = s["load_ms"] if a["load_max"] is None else max(a["load_max"], s["load_ms"])
            if not s["load_ok"]:
                a["load_fail_games"] += 1
            a["restarts"] += s["restarts"]
            if s["error"]:
                a["errors"][s["error"]] = a["errors"].get(s["error"], 0) + 1
            for act in ACTIONS:
                a["actions"][act] += s["actions"].get(act, 0)
            for c in COUNTERS:
                a["c"][c] += s.get(c, 0)
            for t in CHECKPOINTS:
                if s.get("at%d" % t) is not None:
                    a["at"][t].append(s["at%d" % t])
            if not s.get("consistent", True):
                a["inconsistent"] += 1

    elo = sequential_elo(results, n, k_factor, start)
    w, gm = tally(results, n)
    if n:
        bt, strengths = bradley_terry(w, gm, start)
    else:
        bt, strengths = [], []

    # How sure is the order? Resample whole schedule blocks: the four games of a block share a
    # line-up and a map, so they are not independent of each other.
    boot = []
    units = resampling_units(counted, results)
    if bootstrap and units and n > 1:
        rng = random.Random(seed)
        U = len(units)
        for _ in range(bootstrap):
            weights = [0] * U
            for _ in range(U):
                weights[rng.randrange(U)] += 1
            bw = [[0.0] * n for _ in range(n)]
            bg = [[0.0] * n for _ in range(n)]
            for u, m in enumerate(weights):
                if not m:
                    continue
                for a, b, ws, gs in units[u]:
                    bw[a][b] += m * ws
                    bw[b][a] += m * (gs - ws)
                    bg[a][b] += m * gs
                    bg[b][a] += m * gs
            played = [any(row) for row in bg]
            boot.append((bradley_terry(bw, bg, start, init=strengths, tol=1e-7)[0], played))

    def draws(*who):
        """Resampled ratings, keeping only resamples in which every bot asked about played: in the
        others a bot just sits at the prior, which says nothing about it."""
        return [r for r, played in boot if all(played[i] for i in who)]

    rows = []
    for i, e in enumerate(entrants):
        a = acc[i]
        played = a["W"] + a["D"] + a["L"]
        mine = draws(i)
        samples = sorted(r[i] for r in mine) if len(mine) >= MIN_DRAWS else []
        rows.append({
            "code": e["code"], "name": e["name"], "submission": bool(e.get("submission")),
            "builtin": e.get("source") == "builtin",
            "games": len(a["games"]), "appearances": a["apps"],
            "rating": bt[i] if bt else start, "rating_lo": percentile(samples, 0.025),
            "rating_hi": percentile(samples, 0.975), "elo": elo[i] if elo else start,
            "W": a["W"], "D": a["D"], "L": a["L"], "pairings": played,
            "pairwise": (a["W"] + 0.5 * a["D"]) / played if played else None,
            "beaten_of_3": a["beaten"] / a["apps"] if a["apps"] else None,
            "firsts": a["places"][1], "outright": a["outright"],
            "places": a["places"][1:], "r2places": a["r2places"][1:],
            "mean_place": (sum(p * c for p, c in enumerate(a["places"]) if p) / a["apps"]) if a["apps"] else None,
            "pool": a["pool"] / a["apps"] if a["apps"] else None,
            "r2_first": a["r2places"][1] / a["apps"] if a["apps"] else None,
            "r2_top2": (a["r2places"][1] + a["r2places"][2]) / a["apps"] if a["apps"] else None,
            "score": statistics.mean(a["scores"]) if a["scores"] else None,
            "score_se": (statistics.stdev(a["scores"]) / math.sqrt(len(a["scores"]))) if len(a["scores"]) > 1 else None,
            "score_median": statistics.median(a["scores"]) if a["scores"] else None,
            "score_min": min(a["scores"]) if a["scores"] else None,
            "score_max": max(a["scores"]) if a["scores"] else None,
            "margin": statistics.mean(a["margins"]) if a["margins"] else None,
            "cells": statistics.mean(a["cells"]) if a["cells"] else None,
            "upgraded": statistics.mean(a["upgraded"]) if a["upgraded"] else None,
            "at": dict((t, statistics.mean(v) if v else None) for t, v in a["at"].items()),
            "seat": dict((k, v[0] / v[1]) for k, v in a["seat"].items() if v[1]),
            "seat_n": dict((k, v[1]) for k, v in a["seat"].items()),
            "offset": dict((k, v[0] / v[1]) for k, v in a["offset"].items() if v[1]),
            "mapkind": dict((k, (v[0] / v[1], v[1])) for k, v in a["mapkind"].items() if v[1]),
            "home": dict((k, (v[0] / v[1], v[1])) for k, v in a["home"].items() if v[1]),
            "status": a["status"], "turns": a["turns"], "ms_max": a["ms_max"],
            "ms_mean": a["ms_sum"] / a["ms_n"] if a["ms_n"] else None, "first_max": a["first_max"],
            "half": a["half"], "three_q": a["three_q"], "over": a["over"], "load_max": a["load_max"],
            "load_fail_games": a["load_fail_games"], "restarts": a["restarts"],
            "errors": sorted(a["errors"].items(), key=lambda kv: -kv[1])[:3],
            "actions": a["actions"], "c": a["c"], "inconsistent": a["inconsistent"],
            "worst": a["worst"],
        })

    order = leaderboard_order(rows, h2h, index)
    for rank, i in enumerate(order):
        rows[i]["rank"] = rank + 1
    for pos, i in enumerate(order):
        nxt = order[pos + 1] if pos + 1 < len(order) else None
        both = draws(i, nxt) if nxt is not None else []
        if len(both) >= MIN_DRAWS:
            diffs = [r[i] - r[nxt] for r in both]
            rows[i]["p_next"] = sum(1 for d in diffs if d > 0) / float(len(diffs))
            rows[i]["gap_next"] = rows[i]["rating"] - rows[nxt]["rating"]
            rows[i]["gap_sd"] = statistics.pstdev(diffs)
        else:
            rows[i]["p_next"] = rows[i]["gap_next"] = rows[i]["gap_sd"] = None
    elo_order = sorted(range(n), key=lambda i: -rows[i]["elo"])
    for rank, i in enumerate(elo_order):
        rows[i]["elo_rank"] = rank + 1

    seconds = [g["seconds"] for g in counted if g.get("seconds")]
    return {"session": session, "rows": rows, "order": order, "h2h": h2h, "index": index,
            "counted": counted, "excluded": excluded, "duplicates": duplicates,
            "map_counts": map_counts, "token_counts": token_counts,
            "cell_tiebreak_games": cell_tiebreak_games, "bootstrap": len(boot),
            "mean_seconds": statistics.mean(seconds) if seconds else None}


def leaderboard_order(rows, h2h, index):
    """Rulebook 3.2: by rating; bots on the same (displayed, whole-number) rating are separated by
    head-to-head results among themselves, then by more 1st-place finishes; if still level the
    organisers decide, which here is left as a recorded tie."""
    n = len(rows)
    by_rating = {}
    for i in range(n):
        by_rating.setdefault(int(round(rows[i]["rating"])), []).append(i)
    order = []
    for rating in sorted(by_rating, reverse=True):
        group = by_rating[rating]
        for i in group:
            rows[i]["tiebreak"] = None
            rows[i]["tie_group"] = None
        if len(group) == 1:
            order.extend(group)
            continue

        def h2h_rate(i):
            pts = tot = 0.0
            for j in group:
                if j != i:
                    w, d, l = h2h[i][j]
                    pts += w + 0.5 * d
                    tot += w + d + l
            return pts / tot if tot else 0.5

        rates = dict((i, h2h_rate(i)) for i in group)
        group.sort(key=lambda i: (-round(rates[i], 9), -rows[i]["firsts"], rows[i]["code"]))
        codes = tuple(rows[i]["code"] for i in group)
        for i in group:
            rows[i]["tie_group"] = codes
            same_h2h = [j for j in group if round(rates[j], 9) == round(rates[i], 9)]
            if len(same_h2h) == 1:
                rows[i]["tiebreak"] = "by head-to-head (%.1f%% against the others tied)" % (100 * rates[i])
            elif len([j for j in same_h2h if rows[j]["firsts"] == rows[i]["firsts"]]) == 1:
                rows[i]["tiebreak"] = "by 1st places (%d), head-to-head being level" % rows[i]["firsts"]
            else:
                rows[i]["tiebreak"] = ("level on head-to-head and 1st places too, which the rulebook leaves "
                                       "to the organisers (listed alphabetically)")
        order.extend(group)
    return order


# -- rendering -----------------------------------------------------------------------------

def _esc(text):
    return str(text).replace("|", "\\|").replace("\n", " ")


def _pct(x, digits=1):
    return "-" if x is None else ("%." + str(digits) + "f%%") % (100.0 * x)


def _num(x, digits=0):
    if x is None:
        return "-"
    return ("{:,.%df}" % digits).format(x)


def _table(head, rows, align=None):
    align = align or ["l"] + ["r"] * (len(head) - 1)
    marks = {"l": ":--", "r": "--:", "c": ":-:"}
    out = ["| " + " | ".join(_esc(h) for h in head) + " |",
           "|" + "|".join(marks[a] for a in align) + "|"]
    for r in rows:
        out.append("| " + " | ".join(_esc(c) for c in r) + " |")
    return "\n".join(out)


def _per_game(total, games):
    return "-" if not games else "%.2f" % (total / float(games))


def _dur(seconds):
    seconds = int(round(seconds or 0))
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return ("%dh %02dm %02ds" % (h, m, s)) if h else ("%dm %02ds" % (m, s))


def repro_command(session, game):
    """A harness/match.py command that replays the same seats, map and token."""
    ent = dict((e["code"], e) for e in session["entrants"])
    seats = []
    for s in game["seats"]:
        e = ent.get(s["entrant"], {})
        seats.append(e.get("repro") or "?")
    m = game["map"] or {}
    kind = m.get("kind", "example")
    mp = "random:%s" % m.get("seed") if kind == "random" else "custom:%s" % m.get("quadrant") if kind == "custom" else "example"
    st = session.get("settings") or {}
    extra = []
    for k, v in sorted((st.get("rule_overrides") or {}).items()):
        extra.append("--rule %s=%d" % (k, 1 if v else 0))
    if st.get("turns", 80) != 80:
        extra.append("--turns %d" % st["turns"])
    if not (st.get("timing") or {}).get("enforce", True):
        extra.append("--no-timing")
    return "python harness/match.py %s --map %s --token %d%s" % (
        " ".join(seats), mp, game["token"], (" " + " ".join(extra)) if extra else "")


def render(an):
    se = an["session"]
    st = se.get("settings") or {}
    rows = an["rows"]
    order = an["order"]
    counted = an["counted"]
    G = len(counted)
    by_code = dict((r["code"], r) for r in rows)
    ent = dict((e["code"], e) for e in se["entrants"])
    L = []
    add = L.append

    def name(r, star=True):
        return "%s %s%s" % (r["code"], r["name"], " ★" if star and r["submission"] else "")

    add("# Zone Rush simulation report")
    add("")
    started = se.get("created")
    elapsed = se.get("elapsed_s")
    ended = se.get("ended")
    if not ended:          # still running, or killed outright: go by the last game that finished
        last = max([g["finished"] for g in counted + an["excluded"] if g.get("finished")] or [None],
                   key=lambda x: x or "")
        ended = last or datetime.datetime.now().isoformat(timespec="seconds")
        try:
            elapsed = (datetime.datetime.fromisoformat(ended) - datetime.datetime.fromisoformat(started)).total_seconds()
        except (TypeError, ValueError):
            elapsed = None
    add("Session `%s` · started %s · ended %s · ran %s" % (se.get("id"), started, ended, _dur(elapsed)))
    add("")
    add("**%d complete games** counted (%d one-on-one results)%s. Stopped because: %s." % (
        G, sum(r["pairings"] for r in rows) // 2,
        "; %d game(s) not counted" % len(an["excluded"]) if an["excluded"] else "",
        se.get("stop_reason") or "the run is still in progress"))
    if G and elapsed:
        add("Throughput %.2f games/s with %s parallel game(s); a game took %.1f s on average." % (
            G / float(elapsed), st.get("jobs"), an["mean_seconds"] or 0))
    add("")
    add("★ marks a branch's root `bot.py`, which is what that branch would submit (rulebook 3.1).")
    add("")

    # ---- verdict
    warnings = collect_warnings(an)
    add("## Verdict")
    add("")
    if G == 0 or not order:
        add("No complete games yet, so there is nothing to rank.")
    else:
        top = rows[order[0]]
        line = "**Strongest bot: %s**, settled rating %s" % (name(top), _num(top["rating"]))
        if top.get("rating_lo") is not None:
            line += " (95%% interval %s-%s)" % (_num(top["rating_lo"]), _num(top["rating_hi"]))
        line += ", pairwise score %s over %d games." % (_pct(top["pairwise"]), top["games"])
        add(line)
        if len(order) > 1:
            second = rows[order[1]]
            p = top.get("p_next")
            if p is not None:
                verdict = ("decisive" if p >= 0.975 else "likely" if p >= 0.9 else "not yet decisive")
                add("")
                add("It outranks the runner-up, %s, in %s of %d bootstrap resamples: **%s**." % (
                    name(second), _pct(p), an["bootstrap"], verdict))
                gap, sd = top.get("gap_next"), top.get("gap_sd")
                if p < 0.975 and gap and sd and gap > 0:
                    factor = (1.96 * sd / gap) ** 2
                    if factor > 1:
                        add("At the current gap of %.0f rating points, roughly %s more games would make it "
                            "clear at 95%% (a rough estimate; the gap itself will move)." % (
                                gap, _num(G * (factor - 1))))
        subs = [i for i in order if rows[i]["submission"]]
        if subs and subs[0] != order[0]:
            s = rows[subs[0]]
            add("")
            add("Best branch submission (`bot.py`): **%s**, ranked #%d." % (name(s), s["rank"]))
        elif subs:
            add("")
            add("It is also the best branch submission (`bot.py`).")
    add("")
    if warnings:
        add("### Things to check")
        add("")
        for w in warnings:
            add("- " + w)
        add("")

    # ---- leaderboard
    add("## 1. Round 1 leaderboard (rulebook 3.2)")
    add("")
    add("Each game counts as three one-on-one results per bot: above a bot is a win, below it a loss, "
        "equal final scores a draw. **Settled rating** is the Elo-scale rating at which every bot's "
        "expected Elo change is zero, i.e. where the organisers' ratings settle; it does not depend on "
        "the order games were played in. **Elo as played** runs ordinary chess Elo (K=%s per result, "
        "everyone starting at %s) through the games in schedule order, as a live server would. Ties on "
        "the whole-number rating are broken by head-to-head, then 1st places, as the rulebook says." % (
            _num(st.get("elo_k", 16), 0), _num(st.get("elo_start", 1500), 0)))
    add("")
    head = ["#", "Bot", "Settled rating", "95% interval", "Elo as played", "Games", "W-D-L", "Pairwise",
            "1st places", "Outright 1st", "Mean place", "Mean score", "Outranks next"]
    body = []
    for i in order:
        r = rows[i]
        body.append([r["rank"], name(r), _num(r["rating"]),
                     "-" if r["rating_lo"] is None else "%s-%s" % (_num(r["rating_lo"]), _num(r["rating_hi"])),
                     "%s (#%d)" % (_num(r["elo"]), r["elo_rank"]), r["games"],
                     "%d-%d-%d" % (r["W"], r["D"], r["L"]), _pct(r["pairwise"]),
                     "%d (%s)" % (r["firsts"], _pct(r["firsts"] / float(r["appearances"]) if r["appearances"] else None)),
                     r["outright"], _num(r["mean_place"], 2), _num(r["score"]),
                     _pct(r["p_next"], 0) if r.get("p_next") is not None else "-"])
    add(_table(head, body))
    groups = []
    for i in order:
        grp = rows[i].get("tie_group")
        if grp and grp not in groups:
            groups.append(grp)
    if groups:
        add("")
        add("Bots level on the whole-number rating, ordered by the rulebook's tie-breaks:")
        add("")
        for grp in groups:
            members = [by_code[c] for c in grp]
            if len(set(r["tiebreak"] for r in members)) == 1:
                add("- rating %s: %s, %s." % (_num(members[0]["rating"]), ", ".join(grp), members[0]["tiebreak"]))
            else:
                add("- rating %s: %s." % (_num(members[0]["rating"]), "; ".join(
                    "%s %s" % (r["code"], r["tiebreak"]) for r in members)))
    add("")
    add("The settled rating weighs who each bot played (rulebook 3.2: beating a higher-rated bot gains more), "
        "so early in a run a bot can win more of its pairings than another and still rate lower, if its "
        "opponents were weaker. The head-to-head table below shows who actually met whom.")
    add("")
    add("*Outranks next* is the share of bootstrap resamples (whole schedule blocks, %d draws) in which the bot "
        "rates above the one listed below it. *1st places* include shared firsts (equal top scores share "
        "1st, rulebook 2.7); *outright* counts only sole winners." % an["bootstrap"])
    add("")

    # ---- head to head
    add("## 2. Head-to-head")
    add("")
    add("Row bot's one-on-one score against the column bot, over every game in which both played "
        "(win 1, draw 0.5), with the number of meetings.")
    add("")
    codes = [rows[i]["code"] for i in order]
    body = []
    for i in order:
        line = [name(rows[i], star=False)]
        for j in order:
            if i == j:
                line.append("—")
                continue
            w, d, l = an["h2h"][i][j]
            tot = w + d + l
            line.append("-" if not tot else "%s (%d)" % (_pct((w + 0.5 * d) / tot, 0), tot))
        body.append(line)
    add(_table(["vs"] + codes, body))
    add("")
    sig = []
    for a in range(len(order)):
        for b in range(a + 1, len(order)):
            i, j = order[a], order[b]
            w, d, l = an["h2h"][i][j]
            tot = w + d + l
            if tot < 10:
                continue
            lo, hi = wilson(w + 0.5 * d, tot)
            if lo > 0.5:
                sig.append("%s beats %s: %s, 95%% interval %s-%s, %d-%d-%d" % (
                    rows[i]["code"], rows[j]["code"], _pct((w + 0.5 * d) / tot), _pct(lo), _pct(hi), w, d, l))
            elif hi < 0.5:
                sig.append("**upset** - %s beats %s: %s, 95%% interval %s-%s, %d-%d-%d" % (
                    rows[j]["code"], rows[i]["code"], _pct((l + 0.5 * d) / tot), _pct(1 - hi), _pct(1 - lo), l, d, w))
    if sig:
        add("Clear head-to-head results (95% interval excludes 50%, at least 10 meetings):")
        add("")
        for s in sig:
            add("- " + s)
    else:
        add("No head-to-head result is clear at 95% yet.")
    add("")
    add("The game is non-transitive (see `EXPLAINED.md` 3.3), so a bot can rate higher overall and still "
        "lose a particular pairing; an *upset* above is exactly that.")
    add("")

    # ---- placements and scores
    add("## 3. Placements and scores (rulebook 2.7)")
    add("")
    head = ["Bot", "1st", "2nd", "3rd", "4th", "Mean score", "± s.e.", "Median", "Min", "Max",
            "Behind the winner", "Cells at end", "Upgraded at end"]
    body = []
    for i in order:
        r = rows[i]
        ap = float(r["appearances"]) or 1.0
        body.append([name(r, star=False)] + [_pct(c / ap, 1) for c in r["places"]] +
                    [_num(r["score"]), _num(r["score_se"], 1), _num(r["score_median"]), _num(r["score_min"]),
                     _num(r["score_max"]), _num(r["margin"]), _num(r["cells"], 1), _num(r["upgraded"], 1)])
    add(_table(head, body))
    add("")
    add("Shared places are counted at the shared place (two bots tied for 2nd both count as 2nd, and nobody "
        "is 3rd). *Behind the winner* is the mean of (own score - top score), 0 when winning.")
    add("")
    add("Mean score at checkpoints, to show when each bot builds its lead:")
    add("")
    head = ["Bot"] + ["Turn %d" % t for t in CHECKPOINTS] + ["Turn %d" % st.get("turns", 80)]
    add(_table(head, [[name(rows[i], star=False)] + [_num(rows[i]["at"][t]) for t in CHECKPOINTS] +
                      [_num(rows[i]["score"])] for i in order]))
    add("")

    # ---- round 2
    add("## 4. Round 2 view (rulebook 5.3-5.4)")
    add("")
    add("The same bot plays Round 2, where a game is ranked by score, then by cells owned at the end, and "
        "pool games pay 3/2/1/0 with shared places splitting the points. Robot faults and time penalties "
        "(rulebook 4.4) are not simulated.")
    add("")
    head = ["Bot", "Pool points / game", "1st", "2nd", "3rd", "4th", "Top 2 (advances)"]
    body = []
    for i in sorted(order, key=lambda i: -(rows[i]["pool"] or 0)):
        r = rows[i]
        ap = float(r["appearances"]) or 1.0
        body.append([name(r, star=False), _num(r["pool"], 3)] + [_pct(c / ap) for c in r["r2places"]] +
                    [_pct(r["r2_top2"])])
    add(_table(head, body))
    add("")
    add("%d of %d games had a score tie that the cell count changed. Places still level after cells are "
        "shared here; in the Semi-finals and Final the Round 1 position would break them." % (
            an["cell_tiebreak_games"], G))
    add("")

    # ---- seats, tokens, maps
    add("## 5. Seats, priority token and maps")
    add("")
    add("Maps are mirrored, so every seat plays the same game (rulebook 2.1): a large spread across seats "
        "points at a corner-dependent bug in that bot, not at the seat. Values are the bot's pairwise score.")
    add("")
    head = ["Bot", "Seat 1", "Seat 2", "Seat 3", "Seat 4", "Spread",
            "Token turn 1", "Token turn 2", "Token turn 3", "Token turn 4"]
    body = []
    for i in order:
        r = rows[i]
        vals = [r["seat"].get(k) for k in (1, 2, 3, 4)]
        have = [v for v in vals if v is not None]
        body.append([name(r, star=False)] + [_pct(v) for v in vals] +
                    [_pct(max(have) - min(have)) if len(have) > 1 else "-"] +
                    [_pct(r["offset"].get(k)) for k in (0, 1, 2, 3)])
    add(_table(head, body))
    add("")
    add("*Token turn k*: the seat first holds the priority token on turn k (it then holds it every fourth "
        "turn). The token only decides contested empty cells (rulebook 2.3).")
    add("")
    kinds = sorted(an["map_counts"])
    homes = sorted(set(h for r in rows for h in r["home"] if h is not None))
    if len(kinds) > 1 or len(homes) > 1:
        head = ["Bot"] + ["%s maps" % k for k in kinds] + ["home worth %s" % h for h in homes]
        body = []
        for i in order:
            r = rows[i]
            body.append([name(r, star=False)] +
                        ["%s (%d)" % (_pct(r["mapkind"][k][0]), r["mapkind"][k][1]) if k in r["mapkind"] else "-"
                         for k in kinds] +
                        ["%s (%d)" % (_pct(r["home"][h][0]), r["home"][h][1]) if h in r["home"] else "-"
                         for h in homes])
        add(_table(head, body))
        add("")
    add("Games per map kind: %s. Games per starting token holder: %s." % (
        ", ".join("%s %d" % kv for kv in sorted(an["map_counts"].items())) or "-",
        ", ".join("seat %s %d" % kv for kv in sorted(an["token_counts"].items())) or "-"))
    add("")

    # ---- strategy profile
    add("## 6. What each bot actually does")
    add("")
    add("Per game averages over every game the bot played. Action shares are over turns on which the bot "
        "was free to choose (frozen turns are forced STAY and listed separately).")
    add("")
    head = ["Bot", "NORTH", "EAST", "SOUTH", "WEST", "STAY", "SHIELD", "Frozen turns", "Idle stays",
            "Moves", "Blocked", "Contests won", "Contests lost"]
    body = []
    for i in order:
        r = rows[i]
        c = r["c"]
        free = float(c["free"]) or 1.0
        ap = r["appearances"]
        body.append([name(r, star=False)] + [_pct(r["actions"][a] / free) for a in ACTIONS] +
                    [_per_game(c["frozen"], ap), _per_game(c["idle"], ap), _per_game(c["moves"], ap),
                     _per_game(c["blocked"], ap), _per_game(c["contests_won"], ap), _per_game(c["contests_lost"], ap)])
    add(_table(head, body))
    add("")
    add("*Idle stays*: STAY on a cell with nothing left to gain (own upgraded cell, own upgraded home, a "
        "rival's home). Sometimes deliberate (an occupied cell cannot be entered), often wasted. *Blocked*: "
        "moved into a cell occupied at the start of the turn (rulebook 2.3), which counts as STAY.")
    add("")
    head = ["Bot", "Claims", "Upgrades", "Raids", "of which on level 2", "Raid bonus", "Cells lost to raids",
            "Bonus conceded", "Income share"]
    body = []
    for i in order:
        r = rows[i]
        c = r["c"]
        ap = r["appearances"]
        total = c["income"] + c["bonus"]
        body.append([name(r, star=False), _per_game(c["claims"], ap), _per_game(c["upgrades"], ap),
                     _per_game(c["raids"], ap), _per_game(c["raids_l2"], ap), _per_game(c["raid_bonus"], ap),
                     _per_game(c["cells_lost"], ap), _per_game(c["bonus_conceded"], ap),
                     _pct(c["income"] / float(total)) if total else "-"])
    add(_table(head, body))
    add("")
    head = ["Bot", "Shields", "Shields that caught", "Rivals caught", "Backfires", "Times caught by a rival"]
    body = []
    for i in order:
        r = rows[i]
        c = r["c"]
        ap = r["appearances"]
        body.append([name(r, star=False), _per_game(c["shields"], ap),
                     _pct(c["shield_hits"] / float(c["shields"])) if c["shields"] else "-",
                     _per_game(c["catches"], ap), _per_game(c["backfires"], ap), _per_game(c["caught"], ap)])
    add(_table(head, body))
    add("")
    add("Raid bonus is `8 x value x level` (rulebook 2.4). A shield that catches nobody backfires and "
        "freezes the shielder for 2 turns (rulebook 2.6).")
    add("")

    # ---- compliance
    add("## 7. Rule compliance and reliability (rulebook 2.8 and 6)")
    add("")
    add("A bot that crashes, is late or returns an illegal action plays STAY that turn, exactly as the "
        "server does; those turns are already in every score above. Limits: %d ms per turn, %d ms on turn 1%s." % (
            int((st.get("timing") or {}).get("turn_ms", 200)), int((st.get("timing") or {}).get("first_ms", 2000)),
            "" if (st.get("timing") or {}).get("enforce", True) else " (**not enforced in this run**)"))
    add("")
    head = ["Bot", "Turns", "OK"] + [f for f in FAULTS] + ["Restarts", "Mean ms", "Max ms", "Max turn-1 ms",
                                                         ">50% of limit", ">75% of limit", "Max load ms"]
    body = []
    for i in order:
        r = rows[i]
        t = float(r["turns"]) or 1.0
        body.append([name(r, star=False), r["turns"], _pct(r["status"].get("ok", 0) / t, 2)] +
                    [r["status"].get(f, 0) for f in FAULTS] +
                    [r["restarts"], _num(r["ms_mean"], 2), _num(r["ms_max"], 1), _num(r["first_max"], 1),
                     r["half"], r["three_q"], _num(r["load_max"], 0)])
    add(_table(head, body))
    add("")
    for f in FAULTS:
        add("- **%s**: %s." % (f, FAULT_HELP[f]))
    add("")
    errs = [(rows[i], e) for i in order for e in rows[i]["errors"]]
    if errs:
        add("Most frequent errors:")
        add("")
        for r, (text, count) in errs:
            add("- %s, %d game(s): `%s`" % (r["code"], count, text.replace("`", "'")))
        add("")
    add("Static checks of each file against the submission rules (rulebook 2.8, starter README rules 1-6):")
    add("")
    head = ["Bot", "File", "Standard library only", "Self-contained", "act(state) signature", "Named bot.py"]
    body = []
    for i in order:
        r = rows[i]
        e = ent.get(r["code"], {})
        ck = e.get("checks") or {}
        if r["builtin"]:
            body.append([name(r, star=False), e.get("path", ""), "harness built-in", "-", "-", "-"])
            continue
        body.append([name(r, star=False), e.get("path", ""),
                     "yes" if ck.get("stdlib_only") else "**no: %s**" % ", ".join(ck.get("nonstdlib") or ["?"]),
                     ("yes" + (" (has a dynamic import, not checked)" if ck.get("dynamic_import") else ""))
                     if ck.get("self_contained") else "**no: %s**" % ", ".join(
                         (ck.get("local_imports") or []) + (ck.get("data_files") or []) or ["?"]),
                     "yes" if ck.get("signature_ok") else "**%s**" % (ck.get("signature") or "missing"),
                     "yes" if os.path.basename(e.get("path", "")) == "bot.py" else "no (rename to submit)"])
    add(_table(head, body, ["l"] * len(head)))
    add("")

    # ---- notable games
    add("## 8. Notable games")
    add("")
    saved = [g for g in counted + an["excluded"] if g.get("replay")]
    if saved:
        add("Saved replays (open `python harness/server.py`, then **Replays**):")
        add("")
        for g in saved[:50]:
            add("- game %d `%s`: %s" % (g["n"], g["replay"], "; ".join(g.get("notable") or ["saved"])))
        if len(saved) > 50:
            add("- ... and %d more in `harness/replays/`." % (len(saved) - 50))
    else:
        add("No replays were saved (mode `%s`)." % st.get("replays", "notable"))
    add("")
    add("Each bot's worst game (lowest pairwise score, then furthest behind the winner). Run the command "
        "from the repository root to replay it as a saved harness game; bots that budget by wall-clock time "
        "may not repeat move for move:")
    add("")
    games_by_n = dict((g["n"], g) for g in counted)
    for i in order:
        r = rows[i]
        if not r["worst"]:
            continue
        (rate, margin), gn, seat = r["worst"]
        g = games_by_n.get(gn)
        if not g:
            continue
        lineup = ", ".join("S%d %s %d" % (s["seat"], s["entrant"], s["score"]) for s in g["seats"])
        add("- **%s** game %d, seat %d, %s of rivals beaten, %s behind the winner (%s):" % (
            r["code"], gn, seat, _pct(rate, 0), _num(-margin), lineup))
        add("  `%s`" % repro_command(se, g))
    add("")
    if an["excluded"]:
        add("Games not counted (stopped part-way when the run was abandoned, or failed in the harness):")
        add("")
        for g in an["excluded"][:30]:
            add("- game %d: %s after %d turns%s" % (g["n"], g["status"], g["turns"],
                                                    (" - " + g["error"]) if g.get("error") else ""))
        add("")

    # ---- entrants
    add("## 9. Entrants")
    add("")
    head = ["Code", "Bot", "Source", "Commit", "SHA-256", "Lines", "Also found at"]
    body = []
    for i in order:
        r = rows[i]
        e = ent.get(r["code"], {})
        others = [a for a in e.get("aliases") or [] if a != e.get("primary")]
        body.append([r["code"], e.get("name", ""), e.get("source", ""), (e.get("commit") or "")[:10] or "-",
                     (e.get("sha256") or "")[:12], e.get("lines") or "-",
                     ", ".join(others[:6]) + (" (+%d)" % (len(others) - 6) if len(others) > 6 else "") or "-"])
    add(_table(head, body, ["l", "l", "l", "l", "l", "r", "l"]))
    add("")
    skipped = se.get("skipped") or []
    if skipped:
        add("Files found but not entered:")
        add("")
        for s in skipped[:40]:
            add("- `%s`: %s" % (s.get("alias"), s.get("reason")))
        if len(skipped) > 40:
            add("- ... and %d more." % (len(skipped) - 40))
        add("")

    # ---- method
    add("## 10. How the games were run")
    add("")
    rules = st.get("rules") or {}
    overrides = st.get("rule_overrides") or {}
    add("- **Referee**: `harness/referee.py`, the visual harness's implementation of rulebook section 2, "
        "checked turn by turn against `engine.py` by `harness/test_referee.py`. Every game is %d turns." % st.get("turns", 80))
    add("- **Rule readings** (flags where the rulebook leaves a detail open; the defaults are the readings "
        "confirmed in `README.md`): " + ", ".join("`%s=%s`%s" % (k, "on" if v else "off", " **(changed)**" if k in overrides else "")
                                                  for k, v in sorted(rules.items())) + ".")
    add("- **Bots** run exactly as the server runs them: one process per seat for the whole game, so "
        "module memory persists between turns (allowed by the organisers) and is private to the seat; "
        "`act(state)` receives the starter kit's `Game`/`Cell` objects with an 8x8 board; the time "
        "limit is measured around `act()` alone. Every game starts fresh processes.")
    add("- **Schedule**: games come in blocks of four on one map and one starting token, with the four bots "
        "rotated through all four seats, so every bot plays every corner and every token position equally "
        "(the server mixes opponents and seats, rulebook 3.2). Line-ups are chosen to even out how often each "
        "bot plays and how often each pair meets%s." % (
            "; fewer than four bots were entered, so some games seat a bot more than once and those "
            "self-pairings are ignored by the ratings" if an["duplicates"] else ""))
    add("- **Maps**: drawn from `%s`. `example` is the rulebook's example map (section 2.2); `random` is the "
        "harness generator (`referee.random_map`, the same as `engine.make_map`): mirrored, values 1-3, rising "
        "toward the middle, as rulebook 2.1 describes. The official generator is not published." % ",".join(st.get("maps") or []))
    add("- **Ratings**: settled rating = Bradley-Terry maximum likelihood on the Elo scale, with a prior of one "
        "win and one loss against an average opponent; intervals from %d bootstrap resamples of whole "
        "schedule blocks (a block's four games share a line-up and map, so they are resampled together). "
        "The organisers' K-factor and starting rating are not published, so Elo as played uses K=%s from %s." % (
            an["bootstrap"], _num(st.get("elo_k", 16)), _num(st.get("elo_start", 1500))))
    add("- **Parallelism**: %s game(s) at a time on %s CPU(s). Each game runs its four bots one after another, "
        "so at most one bot per game is computing at any moment." % (st.get("jobs"), (se.get("environment") or {}).get("cpus")))
    env = se.get("environment") or {}
    add("- **Environment**: Python %s on %s. Schedule seed %s." % (env.get("python"), env.get("platform"), st.get("seed")))
    add("")
    add("Not modelled: the organisers' actual opponents, their map generator, their Elo constants, "
        "whether their server lists moves into occupied cells in `legal_actions` (flag "
        "`legal_excludes_occupied`), and Round 2's robot penalties. Results describe this simulated field only.")
    add("")
    return "\n".join(L) + "\n"


def collect_warnings(an):
    se = an["session"]
    st = se.get("settings") or {}
    rows = an["rows"]
    out = []
    G = len(an["counted"])
    if 0 < G < 100:
        out.append("Only %d games so far: ratings and percentages are still noisy." % G)
    late = [(r["code"], r["status"].get("late", 0)) for r in rows if r["status"].get("late", 0)]
    if late:
        out.append("%d late turn(s) were played as STAY (%s). Late turns concentrated in one bot mean that bot "
                   "is slow; spread across several bots, they suggest an overloaded machine, so try fewer "
                   "`--jobs`." % (sum(v for _, v in late), ", ".join("%s %d" % kv for kv in late)))
    for r in rows:
        bad = dict((f, r["status"].get(f, 0)) for f in FAULTS if r["status"].get(f, 0))
        if bad:
            out.append("%s had %s." % (r["code"], ", ".join("%d %s" % (v, k) for k, v in sorted(bad.items()))))
        if r["load_fail_games"]:
            out.append("%s failed to load in %d game(s) and played STAY throughout them." % (r["code"], r["load_fail_games"]))
        if r["inconsistent"]:
            out.append("%s: %d game(s) where score != income + bonuses, which would be a referee bug." % (
                r["code"], r["inconsistent"]))
        if r["first_max"] is not None and r["load_max"] is not None and r["first_max"] + r["load_max"] > 2000:
            out.append("%s: import plus first turn reached %.0f ms; that is over 2 s if the server counts "
                       "import time against the first turn." % (r["code"], r["first_max"] + r["load_max"]))
    for e in se.get("entrants") or []:
        ck = e.get("checks") or {}
        if e.get("source") != "builtin" and ck and not (ck.get("stdlib_only") and ck.get("self_contained")):
            out.append("%s is not a valid single-file standard-library bot (rulebook 2.8)." % e["code"])
    if st.get("rule_overrides"):
        out.append("Rule flags were changed from the confirmed readings: %s." % ", ".join(
            "%s=%s" % kv for kv in sorted(st["rule_overrides"].items())))
    if st.get("turns", 80) != 80:
        out.append("Games were %d turns, not the rulebook's 80." % st["turns"])
    if not (st.get("timing") or {}).get("enforce", True):
        out.append("Time limits were not enforced, unlike the server.")
    if an["duplicates"]:
        out.append("%d game(s) seated the same bot twice (fewer than four bots entered); Round 1 never does "
                   "that, as every team enters one bot." % an["duplicates"])
    if an["excluded"]:
        out.append("%d game(s) were not counted (see section 8)." % len(an["excluded"]))
    return out


def summary_json(an):
    keep = ("code", "name", "submission", "rank", "rating", "rating_lo", "rating_hi", "elo", "elo_rank",
            "games", "appearances", "W", "D", "L", "pairwise", "beaten_of_3", "firsts", "outright", "places",
            "mean_place", "pool", "r2places", "r2_top2", "score", "score_se", "score_median", "score_min",
            "score_max", "margin", "cells", "upgraded", "status", "turns", "ms_max", "ms_mean", "first_max",
            "over", "restarts", "p_next", "tiebreak")
    order = an["order"]
    rows = an["rows"]
    codes = [rows[i]["code"] for i in order]
    return {"format": "zone-rush-simulation-summary/1", "session": an["session"].get("id"),
            "games": len(an["counted"]), "excluded": len(an["excluded"]),
            "leaderboard": [dict((k, rows[i].get(k)) for k in keep) for i in order],
            "head_to_head": dict((rows[i]["code"], dict((rows[j]["code"], an["h2h"][i][j]) for j in order if j != i))
                                 for i in order),
            "order": codes, "warnings": collect_warnings(an)}


def write_report(folder, games=None, session=None, bootstrap=200):
    """Rebuild report.md and summary.json in a session folder. Returns (path, analysis)."""
    if session is None or games is None:
        session, games, _bad = load_session(folder)
    an = analyze(session, games, bootstrap=bootstrap)
    text = render(an)
    path = os.path.join(folder, "report.md")
    with open(path + ".tmp", "w", encoding="utf-8") as f:
        f.write(text)
    os.replace(path + ".tmp", path)
    with open(os.path.join(folder, "summary.json.tmp"), "w", encoding="utf-8") as f:
        json.dump(summary_json(an), f, indent=1)
    os.replace(os.path.join(folder, "summary.json.tmp"), os.path.join(folder, "summary.json"))
    return path, an


def load_session(folder):
    with open(os.path.join(folder, "session.json"), encoding="utf-8") as f:
        session = json.load(f)
    games, bad = [], 0
    path = os.path.join(folder, "games.jsonl")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    games.append(json.loads(line))
                except ValueError:
                    bad += 1          # a line cut short by a hard kill; the rest is intact
    return session, games, bad
