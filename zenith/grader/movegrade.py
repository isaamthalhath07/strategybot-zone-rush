"""Move grading for Zone Rush.

Every decision a seat makes is graded by what it does to that seat's chance of
finishing above its rivals, measured to the end of the game:

    Q(a) = expected pairwise result (0..3) if the seat plays `a` now and every
           bot at the table, the seat's own continuation included, then plays
           on to turn 80.

Q is estimated by forking the whole table -- the engine and the four live bots,
module memory and all -- once per candidate action and per sample. Sample 0 is
the exact future (no noise). Samples 1..K-1 add a little noise to every seat
after the decision (each turn, each bot plays a random legal action with
probability `eps`), so a move is not rated on one butterfly-effect future. All
candidates of a sample share one noise stream (common random numbers), so the
differences between candidates are far less noisy than the values themselves.

The value of one finished game for seat i is the soft pairwise score

    sum over rivals r of 1 / (1 + exp(-(S_i - S_r) / tau))

which is the hard pairwise result (1 / 0.5 / 0 per rival) smoothed by tau
points, so a 5-point win and a 500-point win are told apart while a decided game
is still worth almost the same whatever the seat does. Loss is in the same
units as the Round 1 ranking: pairwise wins out of 3. "Win share" is Q / 3.

Categories (loss = Q(best) - Q(played), pairwise wins out of 3):

    Brilliant  !!  the only good move by >= 0.30, and it gives up something now
                   (a shield, progress walked away from, or fewer points this
                   turn than an alternative) for what it wins later
    Great      !   the only good move: every alternative loses >= 0.30
    Best           loss <= 0.02
    Excellent      loss <= 0.06
    Good           loss <= 0.15
    Inaccuracy ?!  loss <= 0.30
    Mistake    ?   loss <= 0.60
    Blunder    ??  loss >  0.60
    Forced         one legal choice (frozen, or every move blocked)

Accuracy per move uses the lichess/chess.com curve on win-share percentage
points lost: 103.1668 * exp(-0.04354 * L) - 3.1669, clipped to 0..100.

The grader works for any line-up the engine can run in-process: bot games, and
recorded games with a human seat, whose continuation after a graded decision
is played by a reference bot (a strong engine finishing the game for them, the
way a chess engine grades a human's moves).
"""
import json
import math
import os
import random
import select
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
for _p in (ROOT, os.path.join(ROOT, "crossfield")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import engine  # noqa: E402

MOVES = engine.MOVES

CATEGORIES = ("Brilliant", "Great", "Best", "Excellent", "Good", "Inaccuracy",
              "Mistake", "Blunder", "Forced")
SYMBOL = {"Brilliant": "!!", "Great": "!", "Best": "", "Excellent": "", "Good": "",
          "Inaccuracy": "?!", "Mistake": "?", "Blunder": "??", "Forced": ""}
THRESH = (("Best", 0.02), ("Excellent", 0.06), ("Good", 0.15), ("Inaccuracy", 0.30),
          ("Mistake", 0.60))
ONLY_MOVE = 0.30


# ---------------------------------------------------------------- the table
def views(g, excl):
    """engine views with either legal_actions convention."""
    occ = set(g.pos)
    bd = g.board_view()
    out = []
    for i in range(4):
        legal = g.legal(i)
        if excl:
            legal = [a for a in legal if a not in MOVES or g.pos[i] + MOVES[a] not in occ]
        out.append(engine.View(bd, i + 1, g.token == i + 1, legal))
    return out


def candidates(g, i, legal):
    """Distinct effective actions for seat i: a move into a cell occupied at the
    start of the turn is blocked and plays exactly like STAY."""
    if g.frozen[i] > 0:
        return ["STAY"]
    occ = set(g.pos)
    out = ["STAY"]
    for a in ("NORTH", "EAST", "SOUTH", "WEST"):
        if a in legal and g.pos[i] + MOVES[a] not in occ:
            out.append(a)
    if "SHIELD" in legal:
        out.append("SHIELD")
    return out


def notify(bot, seat, action):
    """Tell a bot what it actually played when the grader forced a different
    action, for the bot families in this repository that remember their own
    last action. Best effort: an unknown bot re-derives it from the board."""
    gl = getattr(bot, "__globals__", None)
    if gl is None:
        if hasattr(bot, "last"):
            try:
                bot.last = action
            except Exception:
                pass
        return
    try:
        seats = gl.get("_SEATS")                     # Apex, Zenith
        if isinstance(seats, dict) and seat in seats:
            st = seats[seat]
            if hasattr(st, "agent"):
                st.agent.last = action
            bk = getattr(st, "backup", None)
            if bk is not None and getattr(bk, "mem", None):
                bk.mem["last"] = action
        brains = gl.get("_F_BRAINS")                 # the fused bot.py
        if isinstance(brains, dict) and seat in brains:
            br = brains[seat]
            br.route.last_action = action
            if br.econ.mem is not None:
                br.econ.mem["last"] = action
            br.last_sent = br.calib.to_server(action)
        agents = gl.get("_AGENTS")                   # the walk planners
        if isinstance(agents, dict) and seat in agents:
            agents[seat].last_action = action
        hist = gl.get("_history")                    # the evolved planner
        if isinstance(hist, dict) and seat in hist:
            hist[seat]["last"] = action
    except Exception:
        pass


def snapshot(bot, seat):
    """The evolved planner's memory for `seat` at this moment (start of a turn),
    for the bot families that run it: the evolved bot, the fused bot.py, Apex
    and Zenith. JSON-able; None for any other bot."""
    gl = getattr(bot, "__globals__", None)
    if gl is None:
        return None
    mem = None
    try:
        hist = gl.get("_history")
        if isinstance(hist, dict) and seat in hist:
            mem = hist[seat]
        seats = gl.get("_SEATS")
        if mem is None and isinstance(seats, dict) and seat in seats:
            own = getattr(seats[seat].agent, "own", None)
            mem = getattr(own, "mem", None)
        brains = gl.get("_F_BRAINS")
        if mem is None and isinstance(brains, dict) and seat in brains:
            mem = brains[seat].econ.mem
        return json.loads(json.dumps(mem)) if mem is not None else None
    except Exception:
        return None


def position(g, i, view):
    """Everything needed to replay a decision for seat i offline."""
    pos = [-1] + list(g.pos)
    frz = [False] + [g.frozen[k] > 0 for k in range(4)]
    return {"owner": list(g.owner), "up": list(g.upg), "pos": pos, "frz": frz,
            "cd": list(g.cd), "prog": list(g.prog), "score": list(g.score),
            "base": list(g.base), "home": list(g.home), "token": g.token,
            "legal": list(view.legal_actions), "turn": g.turn}


def soft_value(scores, i, tau):
    v = 0.0
    for r in range(4):
        if r != i:
            x = (scores[i] - scores[r]) / tau
            v += 1.0 / (1.0 + math.exp(-max(-60.0, min(60.0, x))))
    return v


def hard_value(scores, i):
    v = 0.0
    for r in range(4):
        if r != i:
            v += 1.0 if scores[i] > scores[r] else (0.5 if scores[i] == scores[r] else 0.0)
    return v


def _call(bot, view):
    try:
        a = bot(view)
    except Exception:
        a = None
    if a not in view.legal_actions:
        a = "STAY"
    return a


# ---------------------------------------------------------------- forking
def fork_map(fn, jobs, workers):
    """Run fn(job) for each job in a forked child of this process (so every
    child starts from this exact interpreter state) and return the results."""
    results = [None] * len(jobs)
    running = {}
    nxt = 0
    sys.stdout.flush()
    sys.stderr.flush()
    while nxt < len(jobs) or running:
        while nxt < len(jobs) and len(running) < max(1, workers):
            r, w = os.pipe()
            pid = os.fork()
            if pid == 0:                                         # child
                os.close(r)
                try:
                    data = json.dumps(fn(jobs[nxt])).encode()
                except BaseException as e:                       # noqa: B902
                    data = json.dumps({"error": repr(e)}).encode()
                view = memoryview(data)
                while view:
                    n = os.write(w, view)
                    view = view[n:]
                os.close(w)
                os._exit(0)
            os.close(w)
            running[r] = (pid, nxt, [])
            nxt += 1
        ready, _, _ = select.select(list(running), [], [])
        for r in ready:
            pid, idx, buf = running[r]
            chunk = os.read(r, 65536)
            if chunk:
                buf.append(chunk)
                continue
            os.close(r)
            os.waitpid(pid, 0)
            del running[r]
            try:
                results[idx] = json.loads(b"".join(buf).decode())
            except ValueError:
                results[idx] = {"error": "no result"}
    return results


class Table(object):
    """One game in progress with four live, in-process bots."""

    def __init__(self, base, token, excl, bots, rseed=0, rules=None):
        self.g = engine.Game(base=base, start_token=token, rules=rules)
        self.excl = excl
        self.bots = bots
        self.rseed = rseed

    def rollout(self, seat, action, sample, eps, tau, own=None):
        """Child side: play `action` for `seat` this turn, then everyone to the end."""
        g = self.g
        random.seed((self.rseed * 1000003 + g.turn * 7919 + sample * 104729) & 0x7fffffff)
        vs = views(g, self.excl)
        acts = [_call(self.bots[i], vs[i]) for i in range(4)]
        if own is not None:
            for j, a in own.items():                    # recorded actions of other seats
                acts[j] = a
        if acts[seat] != action:
            notify(self.bots[seat], seat + 1, action)
            acts[seat] = action
        prog0 = g.prog[seat]
        s0 = g.score[seat]
        g.step(acts)
        imm = g.score[seat] - s0
        noise = random.Random((self.rseed * 31 + g.turn * 131 + sample * 9973) & 0x7fffffff)
        while not g.over():
            vs = views(g, self.excl)
            acts = []
            for i in range(4):
                a = _call(self.bots[i], vs[i])
                if sample and eps and noise.random() < eps and len(vs[i].legal_actions) > 1:
                    b = vs[i].legal_actions[noise.randrange(len(vs[i].legal_actions))]
                    if b != a:
                        notify(self.bots[i], i + 1, b)
                        a = b
                acts.append(a)
            g.step(acts)
        sc = list(g.score)
        return {"soft": soft_value(sc, seat, tau), "hard": hard_value(sc, seat),
                "score": sc[seat], "imm": imm, "prog0": prog0}


# ---------------------------------------------------------------- grading
def classify(q, played, others_best, n_cand, sacrifice):
    """q: {action: Q}, played: action. Returns (category, loss)."""
    if n_cand <= 1:
        return "Forced", 0.0
    best = max(q.values())
    loss = max(0.0, best - q[played])
    if loss <= 1e-9 and others_best is not None and best - others_best >= ONLY_MOVE:
        return ("Brilliant" if sacrifice else "Great"), 0.0
    for name, t in THRESH:
        if loss <= t:
            return name, loss
    return "Blunder", loss


def accuracy(loss):
    """Per-move accuracy from pairwise-win loss (0..3)."""
    pct = 100.0 * loss / 3.0
    a = 103.1668 * math.exp(-0.04354 * pct) - 3.1669
    return max(0.0, min(100.0, a))


def context(g, i, played):
    """What the seat was doing when it moved, for aggregate analysis."""
    p = g.pos[i]
    seat = i + 1
    o = g.owner[p]
    if g.home[p]:
        where = "home" if o == seat else "rival_home"
    elif o == seat:
        where = "own_up" if g.upg[p] else "own"
    elif o == 0:
        where = "neutral"
    else:
        where = "rival_up" if g.upg[p] else "rival"
    intruders = 0
    for j in range(4):
        if j != i and g.owner[g.pos[j]] == seat and not g.home[g.pos[j]]:
            intruders += 1
    order = sorted(range(4), key=lambda k: -g.score[k])
    return {"turn": g.turn, "where": where, "prog": g.prog[i], "cd": g.cd[i],
            "base": g.base[p], "intruders": intruders, "rank": order.index(i) + 1,
            "lead": g.score[i] - max(g.score[k] for k in range(4) if k != i)}


def _mean(xs):
    return sum(xs) / len(xs) if xs else 0.0


def _se(xs):
    n = len(xs)
    if n < 2:
        return float("inf")
    m = _mean(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / (n - 1) / n)


def debiased_loss(per, played):
    """per[a] = list of soft values, sample-aligned across actions.

    Picking the best action and measuring how much better it is on the same
    samples overstates the loss (a maximum of noisy estimates). So the samples
    are split in two folds: the best action is chosen on one fold and its
    advantage over the played action measured on the other, both ways round.
    Returns (debiased loss, naive loss, standard error of the best's advantage,
    best action on all samples)."""
    acts = list(per)
    k = min(len(v) for v in per.values())
    full = dict((a, _mean(per[a][:k])) for a in acts)
    best = max(acts, key=lambda a: (full[a], a == played))
    naive = full[best] - full[played]
    d_best = [per[best][j] - per[played][j] for j in range(k)]
    se = _se(d_best)
    if k < 2:
        return max(0.0, naive), naive, se, best
    folds = ([j for j in range(k) if j % 2 == 0], [j for j in range(k) if j % 2 == 1])
    est = []
    for fa, fb in (folds, folds[::-1]):
        ma = dict((a, _mean([per[a][j] for j in fa])) for a in acts)
        ba = max(acts, key=lambda a: (ma[a], a == played))
        est.append(_mean([per[ba][j] - per[played][j] for j in fb]))
    return _mean(est), naive, se, best


def grade_decision(table, seat, played, samples=4, eps=0.04, tau=60.0, workers=4,
                   own=None):
    g = table.g
    vs = views(g, table.excl)
    cands = candidates(g, seat, vs[seat].legal_actions)
    if played not in cands:
        played = "STAY"
    ctx = context(g, seat, played)
    if len(cands) <= 1:
        return {"turn": g.turn, "seat": seat + 1, "played": played, "cands": cands,
                "q": {played: None}, "best": played, "loss": 0.0, "category": "Forced",
                "acc": None, "ctx": ctx}
    jobs = [(a, k) for a in cands for k in range(samples)]
    res = fork_map(lambda j: table.rollout(seat, j[0], j[1], eps, tau, own), jobs, workers)
    per, perh, sc, imm = {}, {}, {}, {}
    bad = set()
    for (a, k), r in zip(jobs, res):
        if r is None or "error" in r:
            bad.add(k)
            continue
        per.setdefault(a, {})[k] = r["soft"]
        perh.setdefault(a, {})[k] = r["hard"]
        sc.setdefault(a, {})[k] = r["score"]
        if k == 0:
            imm[a] = r["imm"]
    good = [k for k in range(samples) if k not in bad]
    if played not in per or not good:
        return {"turn": g.turn, "seat": seat + 1, "played": played, "cands": cands,
                "q": {}, "best": played, "loss": 0.0, "category": "Forced", "acc": None,
                "ctx": ctx}
    per = dict((a, [v[k] for k in good]) for a, v in per.items() if all(k in v for k in good))
    q = dict((a, _mean(v)) for a, v in per.items())
    qh = dict((a, _mean([perh[a][k] for k in good])) for a in per)
    qs = dict((a, _mean([sc[a][k] for k in good])) for a in per)
    loss_raw, naive, se, best = debiased_loss(per, played)
    loss = max(0.0, loss_raw)
    sure = se == 0.0 or loss > 2.0 * se
    others = [v for a, v in q.items() if a != played]
    gap = (q[played] - max(others)) if others else 0.0
    gap_se = _se([per[played][j] - max(per[a][j] for a in per if a != played)
                  for j in range(len(good))]) if others else 0.0
    sacrifice = (played == "SHIELD" or
                 (played in MOVES and g.prog[seat] > 0) or
                 any(imm.get(a, 0) > imm.get(played, 0) for a in q if a != played))
    if best == played and gap >= ONLY_MOVE and (gap_se == 0.0 or gap > 2.0 * gap_se):
        cat = "Brilliant" if sacrifice else "Great"
    else:
        cat = "Blunder"
        for name, t in THRESH:
            if loss <= t:
                cat = name
                break
        if cat in ("Mistake", "Blunder") and not sure:
            cat = "Inaccuracy"                    # large but within the noise
    return {"turn": g.turn, "seat": seat + 1, "played": played, "cands": cands,
            "q": dict((a, round(v, 4)) for a, v in q.items()),
            "q_hard": dict((a, round(v, 3)) for a, v in qh.items()),
            "q_score": dict((a, round(v, 1)) for a, v in qs.items()),
            "best": best, "loss": round(loss, 4), "loss_raw": round(loss_raw, 4),
            "loss_naive": round(naive, 4), "se": round(se, 4) if se != float("inf") else None,
            "sure": sure, "category": cat, "acc": round(accuracy(loss), 2), "ctx": ctx,
            "samples": len(good)}


def grade_game(bots, base, token, excl, graded, rseed=0, actions=None, samples=4,
               eps=0.04, tau=60.0, workers=4, turns=None, log=None, store=False):
    """Play (or replay) one game and grade every decision of the seats in `graded`
    (0-based). `actions[t][i]` replays recorded actions (a human's, say); bots
    still see every turn so their memory follows the real game, and `bots[i]`
    for a recorded seat is the continuation that finishes the game for it."""
    table = Table(base, token, excl, bots, rseed)
    g = table.g
    out = []
    random.seed(rseed)
    while not g.over():
        t = g.turn
        rec = actions[t - 1] if actions is not None else None
        forced = {}
        if turns is None or t in turns:
            for i in graded:
                if rec is not None:
                    played = rec[i]
                    own = dict((j, rec[j]) for j in range(4) if j != i)
                else:
                    # ask the bot in a throwaway child what it would play, so the
                    # parent's bots are untouched until the real turn below
                    played = fork_map(lambda _x: _call(bots[i], views(g, excl)[i]), [0], 1)[0]
                    own = None
                d = grade_decision(table, i, played, samples, eps, tau, workers, own)
                if store:
                    d["snap"] = snapshot(bots[i], i + 1)
                    d["state"] = position(g, i, views(g, excl)[i])
                    d["raw_played"] = played
                forced[i] = d["played"]
                out.append(d)
                if log:
                    log(d)
        vs = views(g, excl)
        acts = [_call(bots[i], vs[i]) for i in range(4)]
        if rec is not None:
            for i in range(4):
                a = rec[i]
                if a not in vs[i].legal_actions:
                    a = "STAY"
                if a != acts[i]:
                    notify(bots[i], i + 1, a)
                    acts[i] = a
        else:
            # a bot with a wall clock or an RNG may answer differently the second
            # time: the move graded is the move played
            for i, a in forced.items():
                if a != acts[i] and not (a == "STAY" and acts[i] in MOVES):
                    notify(bots[i], i + 1, a)
                    acts[i] = a
        g.step(acts)
    return out, list(g.score)


# ---------------------------------------------------------------- summaries
CRITICAL = 0.15      # a move "mattered" when its candidates' values spread this much


def spread(d):
    vals = [v for v in d.get("q", {}).values() if v is not None]
    return (max(vals) - min(vals)) if len(vals) > 1 else 0.0


def summarise(decisions):
    """Counts per category, accuracy over every graded move, and accuracy over the
    critical moves only: in a decided game every move is worth the same, so a
    player who has already lost scores near 100% on the rest."""
    by_cat = dict((c, 0) for c in CATEGORIES)
    acc, loss, crit = [], [], []
    for d in decisions:
        by_cat[d["category"]] += 1
        if d["acc"] is not None:
            acc.append(d["acc"])
            loss.append(d["loss"])
            if spread(d) >= CRITICAL:
                crit.append(d["acc"])
    n = len(acc)
    return {"moves": len(decisions), "graded": n, "categories": by_cat,
            "accuracy": (sum(acc) / n) if n else None,
            "critical": len(crit),
            "critical_accuracy": (sum(crit) / len(crit)) if crit else None,
            "avg_loss": (sum(loss) / n) if n else None,
            "total_loss": sum(loss)}


def describe(d):
    q = d["q"]
    parts = []
    for a in sorted(q, key=lambda x: -(q[x] if q[x] is not None else -1)):
        if q[a] is None:
            continue
        parts.append("%s %.2f" % (a, q[a]))
    sym = SYMBOL.get(d["category"], "")
    s = "t%02d seat%d %-6s%-2s %-10s" % (d["turn"], d["seat"], d["played"], sym, d["category"])
    if d["category"] not in ("Forced",):
        s += " loss %.3f  best %-6s | %s" % (d["loss"], d["best"], ", ".join(parts))
    return s
