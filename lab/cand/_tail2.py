# ----------------------------------------------------------------------------- priors
# P(an owned, unoccupied cell is lost within h turns) by distance to the nearest rival,
# measured over a broad mixed population of independent bots (lab/scratch/hazard_stats.py).
# Knots at h = 0,1,2,3,5,8,12,20. These are priors; the planner rescales them per rival
# from the raiding it actually observes during the game.
_KNOTS = (0, 1, 2, 3, 5, 8, 12, 20)
_LOSS1 = ((0, 0, .077, .129, .230, .337, .403, .487),
          (0, 0, 0, .010, .043, .101, .175, .281),
          (0, 0, 0, 0, .006, .028, .067, .160),
          (0, 0, 0, 0, .001, .007, .026, .086),
          (0, 0, 0, 0, 0, .001, .010, .047),
          (0, 0, 0, 0, 0, 0, .005, .029),
          (0, 0, 0, 0, 0, 0, .001, .012))
_LOSS2 = ((0, 0, 0, 0, .012, .025, .037, .059),
          (0, 0, 0, 0, .001, .005, .011, .025),
          (0, 0, 0, 0, 0, .001, .004, .013),
          (0, 0, 0, 0, 0, 0, .001, .005),
          (0, 0, 0, 0, 0, 0, 0, .003),
          (0, 0, 0, 0, 0, 0, 0, .001),
          (0, 0, 0, 0, 0, 0, 0, 0))


def _curve(loss):
    out = [0.0] * 83
    for k in range(len(_KNOTS) - 1):
        a, b = _KNOTS[k], _KNOTS[k + 1]
        for h in range(a, b + 1):
            out[h] = loss[k] + (loss[k + 1] - loss[k]) * (h - a) / float(b - a)
    slope = (loss[-1] - loss[-2]) / 8.0
    for h in range(21, 83):
        slope *= 0.97
        out[h] = min(0.95, out[h - 1] + slope)
    return out


def _tables(rows):
    """PL[d][R]: P(lost within R turns);  SL[d][R]: expected turns of income lost out of R."""
    pl, sl = [None], [None]
    for row in rows:
        c = _curve(row)
        acc, s = 0.0, [0.0]
        for h in range(82):
            acc += c[h]
            s.append(acc)
        pl.append(c)
        sl.append(s)
    return pl, sl


_PL1, _SL1 = _tables(_LOSS1)
_PL2, _SL2 = _tables(_LOSS2)

# Tunables. Each is a quantity with a meaning, set from the population measurements or
# simple reasoning and then sanity-checked on development opponents (never on hold-outs).
_P = {
    "beam": 14,            # plans kept per depth
    "jobs": 16,            # candidate jobs per turn
    "depth": 10,           # most jobs in one plan
    "horizon": 16,         # turns of lookahead the plans are compared at
    "tail": 0.6,           # value of time left after the plan, relative to today's best rate
    "raid_exec": 0.85,     # discount for everything a raid model cannot see
    "denial_floor": 0.10,
    "hazard": 0.8,         # multiplier on the population loss curves. Development is flat
                           # from 0.6 to 1.0 and falls steeply above, so sit inside the
                           # plateau, not on its edge (lab/PROGRESS.md section 7)
    "l1_delay": 0.3,       # share of a level-1 cell's value a shield really saves mid-game
    "shield_margin": 1.0,  # shield when benefit exceeds margin * cost
    "raids": 1,            # switches for ablation
    "shields": 1,
    "feints": 1,
    "early_shield": 0.5,   # chance of shielding one stay early when both timings look equal
}


def _ratio(row):
    return row[0] / row[1] if row[1] > 0 else 0.5


class _Ctx(object):
    pass


def _context(v, m):
    """Everything the planner and the tactics share for this turn."""
    x = _Ctx()
    me = v.me
    x.me = me
    x.at = v.pos[me]
    x.left = left = 81 - m.turn
    owner, level, base = v.owner, v.level, v.base
    x.rivals = rivals = [s for s in range(1, 5) if s != me and v.pos[s] >= 0]
    x.occupied = set(v.pos[s] for s in rivals)

    # how much each rival's points matter to my placement (pairwise objective)
    income = [0] * 5
    for c in range(64):
        if owner[c]:
            income[owner[c]] += base[c] * (1 + level[c])
    x.income = income
    proj = [m.scores[s] + income[s] * left for s in range(5)]
    sigma = 25.0 + 4.0 * left
    phi = [0.0] * 5
    tot = 0.0
    for r in rivals:
        g = (proj[me] - proj[r]) / sigma
        phi[r] = 2.718281828 ** (-0.5 * g * g)
        tot += phi[r]
    floor = _P["denial_floor"]
    x.w = w = [0.33] * 5
    for r in rivals:
        w[r] = floor + (1.0 - floor) * (phi[r] / tot if tot > 1e-9 else 1.0 / 3)

    # nearest rival to each cell, and how eagerly that rival raids
    x.rho = rho = [1.0] * 5
    for r in rivals:
        est = (m.raid_n[r] + 0.18 * 6.0) / (m.raid_opp[r] + 6.0)
        rho[r] = max(0.35, min(2.2, est / 0.18)) * _P["hazard"]
    rd = [7] * 64
    rr = [0] * 64
    for r in rivals:
        dr = _DIST[v.pos[r]]
        wait = m.fr[r]
        for c in range(64):
            d = dr[c] + wait
            if d < rd[c]:
                rd[c] = d
                rr[c] = r
    for c in range(64):
        if rd[c] < 1:
            rd[c] = 1
    x.rd, x.rr = rd, rr

    # travel from here; a cell occupied at the start of a turn cannot be entered
    travel = [99] * 64
    first = [None] * 64
    travel[x.at] = 0
    frontier = []
    opts = []
    legal = v.legal
    for a, t in _ADJ[x.at]:
        if a in legal and t not in x.occupied:
            risk = 0
            if owner[t] != me:
                for r in rivals:
                    if _DIST[v.pos[r]][t] == 1 and not v.frozen[r]:
                        risk += 1
            opts.append((risk, a, t))
    opts.sort()
    for _, a, t in opts:
        travel[t] = 1
        first[t] = a
        frontier.append(t)
    while frontier:
        nxt = []
        for h in frontier:
            th = travel[h] + 1
            fh = first[h]
            for t in _NB[h]:
                if travel[t] == 99 and t not in x.occupied:
                    travel[t] = th
                    first[t] = fh
                    nxt.append(t)
        frontier = nxt
    x.travel, x.first = travel, first
    return x


def _hold1(v, x, c, R):
    d = x.rd[c]
    r = x.rr[c]
    k = x.rho[r] if r else 1.0
    wv = x.w[r] if r else 0.33
    return v.base[c] * (R - k * (_SL1[d][R] * (1.0 + wv) + 8.0 * wv * _PL1[d][R]))


def _hold2(v, x, c, R):
    d = x.rd[c]
    r = x.rr[c]
    k = x.rho[r] if r else 1.0
    wv = x.w[r] if r else 0.33
    return v.base[c] * (2.0 * R - k * (_SL2[d][R] * (2.0 + wv) + 16.0 * wv * _PL2[d][R]))


def _shield_ready_in(m, v, d):
    """Steps from now (0 = this turn) until rival d could first cast SHIELD."""
    if not m.cd_sure[d]:
        return m.fr[d]
    return max(m.cd[d], m.fr[d])


def _sidestep(v, m, x, cell, d):
    """Where to slip to instead of staying on landlord d's cell.

    Returns (action, target, extra_turns, kind): 'own' is another capturable cell of the
    same landlord (legal under the STAY-only catch rule), 'off' leaves the land for one
    turn and comes back. Both leave a SHIELD cast this turn with nobody to catch.
    """
    best = None
    lvl_here = v.level[cell]
    for a, t in _ADJ[cell]:
        if a not in v.legal or t in x.occupied:
            continue
        if v.owner[t] == d and not v.home[t] and not m.presence_rule \
                and m.failed.get(t) != (d, v.level[t]):
            extra = 3 if v.level[t] else 1
            score = 10.0 + v.base[t] * (2.0 if v.level[t] else 1.2)
            if _DIST[v.pos[d]][t] == 1:
                score -= 1.0        # the landlord could step onto it and win the contest
            kind = "own"
        elif v.owner[t] == d:
            continue                # its home, or presence rule: no escape there
        else:
            extra = 1 + (3 if lvl_here else 1)
            score = 1.0
            o = v.owner[t]
            if o == x.me or o == 0:
                score += 1.0
            for r in x.rivals:
                if r != d and _DIST[v.pos[r]][t] == 1:
                    score -= 0.5
            kind = "off"
        if best is None or score > best[0]:
            best = (score, a, t, extra, kind)
    return None if best is None else best[1:]


def _take_value(v, x, c, R, d):
    """Points from taking rival d's cell c with R scoring turns left (mine + what d loses)."""
    lvl = v.level[c]
    return (8.0 * v.base[c] * (1 + lvl) + _hold1(v, x, c, R)
            + x.w[d] * v.base[c] * (1 + lvl) * R)


def _plan(v, m, x):
    """Beam search over sequences of jobs. Returns (target, kind, best_rate, stay_gain)."""
    me, at, left = x.me, x.at, x.left
    owner, level, base, home = v.owner, v.level, v.base, v.home
    travel = x.travel
    myprog = m.prog[me]
    w = x.w
    raid_exec = _P["raid_exec"]
    # jobs: [cell, kind, work, prerequisite, extra]
    jobs = []
    for c in range(64):
        if c in x.occupied or travel[c] >= left:
            continue
        o = owner[c]
        if m.failed.get(c) == (o, level[c]):
            continue
        if o == me:
            if not level[c]:
                jobs.append([c, "U", max(1, 3 - (myprog if c == at else 0)), -1, None])
        elif o == 0:
            jobs.append([c, "C", 1, -1, None])
        elif not home[c] and _P["raids"]:
            lvl = level[c]
            need = (3 if lvl else 1) - (myprog if c == at else 0)
            if need < 1:
                need = 1
            ready = _shield_ready_in(m, v, o)
            if travel[c] + need - 1 < ready:
                jobs.append([c, "R", need, -1, (1.0, 0.0, 0, c, o)])
                continue
            q = m.q_shield(o, "a2" if lvl else "a1")
            early = 1.0
            if need >= 3:
                early *= 1.0 - m.q_shield(o, "b0")
            if need >= 2:
                early *= 1.0 - m.q_shield(o, "b1")
            side = _sidestep(v, m, x, c, o) if _P["feints"] else None
            if lvl:
                p_stay = (1.0 - q) * early
                p_feint = q * early if side is not None else 0.0
                if p_feint * (travel[c] + need) > p_stay * (travel[c] + need + (side[2] if side else 0)):
                    tgt = side[1] if side[3] == "own" else c
                    jobs.append([c, "R", need + side[2], -1, (p_feint, 0.0, 0, tgt, o)])
                else:
                    jobs.append([c, "R", need, -1, (p_stay, 0.0, 0, c, o)])
            else:
                # caught on a level-1 cell: thaw and finish while its SHIELD recharges
                jobs.append([c, "R", need, -1, (1.0 - q, q * 0.8, 3, c, o)])
    n0 = len(jobs)
    for k in range(n0):
        if jobs[k][1] == "C":
            jobs.append([jobs[k][0], "U", 3, k, None])

    def gain(job, k_used):
        """Value of finishing `job` after k_used steps (this turn counts as step 1)."""
        c, kind = job[0], job[1]
        R = left - k_used + 1
        if R <= 0:
            return -1.0
        if kind == "C":
            return _hold1(v, x, c, R)
        if kind == "U":
            d = x.rd[c]
            r = x.rr[c]
            kk = x.rho[r] if r else 1.0
            wait = k_used if job[3] < 0 else 3
            keep = 1.0 - kk * _PL1[d][wait]
            if keep < 0.05:
                keep = 0.05
            return keep * (_hold2(v, x, c, R) - _hold1(v, x, c, R))
        p_now, p_late, delay, tgt, d = job[4]
        g = p_now * _take_value(v, x, tgt, R, d)
        if p_late > 0.0 and R - delay > 0:
            g += p_late * _take_value(v, x, tgt, R - delay, d)
        return g * raid_exec

    if not jobs:
        return None, None, 0.0, 0.0
    scored = []
    best_rate = 0.0
    stay_gain = 0.0
    for k in range(n0):
        job = jobs[k]
        c = job[0]
        cost = travel[c] + job[2]
        if cost > left:
            continue
        g = gain(job, cost)
        if g <= 0.0:
            continue
        rate = g / cost
        if rate > best_rate:
            best_rate = rate
        if c == at and job[2] == 1:
            stay_gain = max(stay_gain, g)
        scored.append((rate + (1e6 if c == at else 0.0), k))
    if not scored:
        return None, None, 0.0, 0.0
    scored.sort(reverse=True)
    index = {}
    short = []
    for _, k in scored[:_P["jobs"]]:
        index[k] = len(short)
        short.append(jobs[k])
    for k in range(n0, len(jobs)):
        pre = jobs[k][3]
        if pre in index:
            j = list(jobs[k])
            j[3] = index[pre]
            short.append(j)
    nj = len(short)
    tail_k = _P["tail"] * best_rate / (2.0 * left)
    # A turn that ran long (slow or busy grading machine) narrows every later search.
    shrink = min(m.slow, 2)
    # Plans are compared at a common time horizon, not a common number of jobs: a fixed
    # job count would rate "six big jobs" above "one small job on the way plus five big".
    horizon = min(left, _P["horizon"])
    beam = [(0.0, 0.0, 0, at, 0, -1)]
    best = None
    width = max(3, _P["beam"] >> shrink)
    for depth in range(max(4, _P["depth"] >> shrink)):
        seen = {}
        for state in beam:
            _, value, used, pos, mask, f0 = state
            if used >= horizon:
                if best is None or state[0] > best[0]:
                    best = state
                continue
            drow = _DIST[pos]
            grew = False
            for j in range(nj):
                bit = 1 << j
                if mask & bit:
                    continue
                job = short[j]
                pre = job[3]
                if pre >= 0 and not (mask >> pre) & 1:
                    continue
                c = job[0]
                k_used = used + (travel[c] if used == 0 else drow[c]) + job[2]
                if k_used > left:
                    continue
                g = gain(job, k_used)
                if g <= 0.0:
                    continue
                grew = True
                nv = value + g
                rem = left - k_used
                sc = nv + tail_k * rem * rem
                key = (c, mask | bit)
                old = seen.get(key)
                if old is None or old[0] < sc:
                    seen[key] = (sc, nv, k_used, c, mask | bit, j if f0 < 0 else f0)
            if not grew and f0 >= 0 and (best is None or state[0] > best[0]):
                best = state
        if not seen:
            break
        beam = sorted(seen.values(), reverse=True)[:width]
    else:
        for state in beam:
            if best is None or state[0] > best[0]:
                best = state
    if best is None:
        return None, None, best_rate, stay_gain
    job = short[best[5]]
    return job[0], job[1], best_rate, stay_gain


def _stay_prob(m, r, ctx):
    ps = _ratio(m.st[r][ctx])
    if m.feinted_me[r]:
        ps *= 0.5 ** m.feinted_me[r]
    return min(0.97, max(0.03, ps))


def _shield_call(v, m, x, rate, stay_gain):
    """Is SHIELD worth more than carrying on? Compares expected points, not reflexes."""
    me, left = x.me, x.left
    benefit = 0.0           # expected points saved or denied by casting now
    miss = 1.0              # chance nobody eligible stays: the cast backfires
    worst = 0.0
    imminent = False
    early = None            # a raider one stay short of the decisive turn
    for r in x.rivals:
        if v.frozen[r]:
            continue
        cell = v.pos[r]
        if v.owner[cell] != me:
            continue
        lvl = v.level[cell]
        pr = m.prog[r]
        if v.home[cell]:
            ps = _stay_prob(m, r, "b0")
            miss *= 1.0 - ps
            benefit += ps * x.w[r] * 2.0 * rate
            continue
        ctx = "a1" if not lvl else ("a2" if pr >= 2 else "b1" if pr == 1 else "b0")
        ps = _stay_prob(m, r, ctx)
        miss *= 1.0 - ps
        benefit += ps * x.w[r] * 2.0 * rate          # a caught rival loses two turns
        keep = _hold2(v, x, cell, left) if lvl else _hold1(v, x, cell, left)
        loss = keep + x.w[r] * (8.0 * v.base[cell] * (1 + lvl) + v.base[cell] * left)
        if ctx == "b1" and left >= 3:
            if early is None or loss > early[1]:
                early = (r, loss, ps)
            continue
        if ctx == "b0":
            continue
        imminent = True
        if not lvl and left > 3:
            loss *= _P["l1_delay"]                   # it thaws and takes the cell anyway
        benefit += ps * loss
        if loss > worst:
            worst = loss
    cost = rate + m.prog[me] * rate * 0.5
    if imminent:
        if left <= 1:
            return benefit > stay_gain
        backfire = rate if left == 2 else 2.0 * rate + worst
        return benefit > _P["shield_margin"] * (cost + miss * backfire)
    if early is not None and _P["early_shield"] > 0.0:
        # Catching a raider one stay before the decisive turn costs the same and denies it
        # the chance to dodge on that turn. Do it when it is the likelier catch, or at
        # random so the timing cannot be read.
        r, loss, ps1 = early
        ps2 = _stay_prob(m, r, "a2")
        gain_now = benefit + ps1 * loss
        if gain_now <= _P["shield_margin"] * (cost + miss * (2.0 * rate + loss)):
            return False
        if m.prog[me] >= 2 and ps2 > 0.5:
            return False                             # finish my own job first
        if ps1 > ps2 + 0.15:
            return True
        return _rng(m).random() < _P["early_shield"]
    return False


def _rng(m):
    if m.rng is None:
        import random
        m.rng = random.Random(random.getrandbits(64))
    return m.rng


def _raid_step(v, m, x, rate):
    """Standing on a rival's cell with the plan saying STAY: stay, or slip sideways?"""
    me, at, left = x.me, x.at, x.left
    d = v.owner[at]
    lvl = v.level[at]
    if _shield_ready_in(m, v, d) > 0 or not _P["feints"]:
        return "STAY"
    pr = m.prog[me]
    need = 1 if not lvl else 3 - pr
    side = _sidestep(v, m, x, at, d)
    if side is None:
        return "STAY"
    action, tgt, extra, kind = side
    ex = _P["raid_exec"]
    here = ex * _take_value(v, x, at, left, d)
    there = ex * _take_value(v, x, tgt if kind == "own" else at, max(1, left - extra), d)
    freeze = x.w[d] * 2.0 * rate
    if not lvl:
        q = m.q_shield(d, "a1")
        ev_stay = here - q * 3.0 * rate
        ev_side = q * (there + freeze + (0.8 * here if kind == "own" else 0.0)) - (1.0 - q) * rate
    elif need == 1:
        q = m.q_shield(d, "a2")
        ev_stay = (1.0 - q) * here - q * 2.0 * rate
        ev_side = q * (there + freeze) - (1.0 - q) * 3.0 * rate
    else:
        q = m.q_shield(d, "b1" if pr == 1 else "b0")
        q2 = m.q_shield(d, "a2")
        later = max(q2, 1.0 - q2) * here * 0.8
        ev_stay = (1.0 - q) * later - q * (2.0 + pr) * rate
        ev_side = q * (there + freeze) + (1.0 - q) * (later * 0.8 - (pr + 1.0) * rate)
    return action if ev_side > ev_stay else "STAY"


def _decide(v, m):
    me = v.me
    legal = v.legal
    stay = "STAY" if "STAY" in legal else legal[0]
    if v.frozen[me] or len(legal) <= 1:
        return stay
    x = _context(v, m)
    target, kind, rate, stay_gain = _plan(v, m, x)
    action = stay
    if target is not None:
        action = "STAY" if target == x.at else (x.first[target] or stay)
    can_shield = ("SHIELD" in legal) and m.cd[me] == 0
    if can_shield and _P["shields"] and _shield_call(v, m, x, rate, stay_gain if action == "STAY" else 0.0):
        return "SHIELD"
    if action == "STAY" and kind == "R":
        action = _raid_step(v, m, x, rate)
    if action not in legal:
        action = stay
    return action


def _fallback(v):
    """Stateless greedy policy, used only if the planner itself raises: work the cell we
    stand on if there is work, else walk to the nearest claimable or upgradable cell."""
    me = v.me
    at = v.pos[me]
    legal = v.legal
    stay = "STAY" if "STAY" in legal else legal[0]
    if v.frozen[me] or len(legal) <= 1:
        return stay
    owner, level, home = v.owner, v.level, v.home

    def work(c):
        o = owner[c]
        if home[c]:
            return False
        return o == 0 or (o == me and not level[c]) or (o != me and not level[c])

    if work(at):
        return stay
    occupied = set(p for p in v.pos[1:] if p >= 0 and p != at)
    seen = {at: None}
    frontier = []
    for a, t in _ADJ[at]:
        if a in legal and t not in occupied:
            seen[t] = a
            frontier.append(t)
    while frontier:
        nxt = []
        for h in frontier:
            if work(h):
                return seen[h]
            for t in _NB[h]:
                if t not in seen and t not in occupied:
                    seen[t] = seen[h]
                    nxt.append(t)
        frontier = nxt
    return stay


_clock = None


def act(state):
    global _clock
    if _clock is None:
        import time
        _clock = time.perf_counter
    t0 = _clock()
    try:
        v = _read(state)
    except Exception:
        try:
            legal = list(getattr(state, "legal_actions", None) or state["legal_actions"])
        except Exception:
            legal = []
        for a in legal:
            if a == "STAY":
                return a
        return legal[0] if legal else "STAY"
    m = None
    try:
        m = _update(v)
        action = _decide(v, m)
    except Exception:
        # Never let one bad assumption cost the game: drop this seat's memory (it is
        # rebuilt from the board next turn) and play a safe greedy move now.
        _MEMS.pop(v.me, None)
        m = None
        try:
            action = _fallback(v)
        except Exception:
            action = "STAY"
    if action not in v.legal:
        action = "STAY" if "STAY" in v.legal else (v.legal[0] if v.legal else "STAY")
    if m is not None:
        m.last = action
        m.shield_was_legal = "SHIELD" in v.legal
        if _clock() - t0 > 0.06:
            m.slow += 1
    return v.raw.get(action, action)
