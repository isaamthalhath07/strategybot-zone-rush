# ----------------------------------------------------------------------------- priors
# Risk of losing land.
#
# Level-1 cells (one stay takes them, and SHIELD only delays it). Measured on this bot's
# own cells (lab/scratch/hazard_own.py): the chance that a cell left un-upgraded is gone
# within h turns is 1 - exp(-L), where L grows at a roughly constant rate per turn once
# a rival has had time to wander over, about three turns per step of distance. The
# earlier table came from every bot's cells, most of them upgraded within three turns
# of being claimed, and under-stated long exposure about threefold.
#   exposure to rival r after h turns:  g = max(0, h - 3*(d_r - 1))  [+ 3*min(h, 10) if adjacent]
#   P(cell survives rival r) = sum over raider types t of  P(r is t) * exp(-rate_t * g)
# How hard a rival raids is not known in advance and differs several-fold between bots
# (lab/scratch/raid_propensity.py), so each rival carries a posterior over three types,
# updated from how often it takes an exposed level-1 cell when it is next to one.
_GRACE = 3            # turns of grace per step of distance
_NEAR = 3             # extra pressure from an adjacent rival over the next ten turns
_G = []               # _G[d][h] for d = 0..17 (distance plus frozen turns), h = 0..82
for _d in range(18):
    _row = []
    for _h in range(83):
        _g = max(0, _h - _GRACE * (max(_d, 1) - 1))
        if _d <= 1:
            _g += _NEAR * min(_h, 10)
        _row.append(_g)
    _G.append(_row)
# Raider types: passive, ordinary, aggressive.
_RAID_Q = (0.03, 0.18, 0.42)        # P(takes an exposed level-1 cell | a turn next to one)
_RAID_PRIOR = (0.30, 0.50, 0.20)
_RAID_MULT = (0.2, 1.0, 2.2)        # hazard rate relative to _P["l1_rate"]
_SURV = []                          # _SURV[t][g] = exp(-rate_t * g), filled on first use

# Level-2 cells: P(lost within h turns) by distance to the nearest rival, measured over a
# broad mixed population (lab/scratch/hazard_stats.py). Knots at h = 0,1,2,3,5,8,12,20.
_KNOTS = (0, 1, 2, 3, 5, 8, 12, 20)
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
    "hazard": 0.8,         # multiplier on the level-2 population loss curve
    "l1_rate": 0.014,      # per turn: hazard an ordinary raider puts on an un-upgraded
                           # cell once it is in range
    "raid_hold": 1.0,      # the same hazard as applied to a cell I am about to take
    "routes": 0,           # among shortest paths, walk through claimable cells
    "homefix": 1,          # the home cell cannot be taken: no risk on it
    "fresh_rate": 1,       # tactics price a turn without counting stays already banked
    "fresh_tail": 0,       # the same for the planner's tail term
    "end_backfire": 1,     # near the end a side-stepping raider has no time to come back
    "bank_shield": 0,      # catch one stay early when waiting would cost me a banked stay
    "feint_pen": 0.5,      # trust in "it will stay" after each side-step of my shield
    "lag": 0,              # turns a claimed cell is assumed to wait for its upgrade;
                           # 0 = priced as never upgraded (generation 3 behaviour)
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

    # nearest rival to each cell, and how eagerly each rival raids
    x.rho = rho = [1.0] * 5
    x.post = post = [None] * 5          # per rival: posterior over raider types
    x.gd = gd = [None] * 5              # per rival: _G row index for every cell
    x.sr = [None, {}, {}, {}, {}]       # per rival: distance -> survival curve
    for r in rivals:
        n = m.took1[r]
        idle = m.raid_opp[r] - n
        if idle < 0.0:
            idle = 0.0
        pt = [_RAID_PRIOR[t] * _RAID_Q[t] ** n * (1.0 - _RAID_Q[t]) ** idle for t in range(3)]
        tot_p = pt[0] + pt[1] + pt[2]
        pt = [max(0.02, q / tot_p) for q in pt]
        tot_p = pt[0] + pt[1] + pt[2]
        post[r] = pt = [q / tot_p for q in pt]
        est = pt[0] * _RAID_Q[0] + pt[1] * _RAID_Q[1] + pt[2] * _RAID_Q[2]
        rho[r] = max(0.35, min(2.2, est / 0.18)) * _P["hazard"]
    x.h1 = {}
    rd = [7] * 64
    rr = [0] * 64
    for r in rivals:
        dr = _DIST[v.pos[r]]
        wait = m.fr[r]
        gd[r] = [min(17, dr[c] + wait) for c in range(64)]
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


def _first_step(v, x, target):
    """First move of a shortest path to `target` that passes the most claimable value.

    Many shortest paths exist on a grid. Walking through neutral cells keeps the option
    of claiming them on the way; hugging an edge of cheap cells throws it away.
    """
    at = x.at
    need = x.travel[target]
    if need <= 1 or need >= 99:
        return x.first[target]
    dist_t = _DIST[target]
    if dist_t[at] != need:
        return x.first[target]          # the direct box is blocked: keep the detour BFS found
    me = x.me
    owner, base, level, occupied = v.owner, v.base, v.level, x.occupied
    memo = {target: 0.0}

    def best(c):
        got = memo.get(c)
        if got is not None:
            return got
        dc = dist_t[c]
        top = -1e9
        for t in _NB[c]:
            if dist_t[t] == dc - 1 and (t not in occupied or t == target):
                val = best(t)
                if val > top:
                    top = val
        worth = 0.0
        if owner[c] == 0:
            worth = base[c]
        elif owner[c] == me and not level[c]:
            worth = 0.3 * base[c]
        memo[c] = top + worth
        return memo[c]

    choice, top = None, -1e9
    for a, t in _ADJ[at]:
        if a in v.legal and t not in occupied and dist_t[t] == need - 1:
            val = best(t)
            if val > top:
                choice, top = a, val
    return choice or x.first[target]


_EXP = 2.718281828459045


def _risk1(x, c, taken=False):
    """For cell c held at level 1 from now: (P(lost within h), expected turns lost of the
    first h, weight of the likely raider's points), for h up to the turns left. Cached
    per turn. `taken` prices a cell I would take from a rival, not one I already hold."""
    key = c + 64 if taken else c
    t = x.h1.get(key)
    if t is None:
        if not _SURV:
            for mult in _RAID_MULT:
                lam = _P["l1_rate"] * mult
                _SURV.append([_EXP ** (-lam * g) for g in range(_G[0][82] + 1)])
        n = x.left + 2
        s0, s1, s2 = _SURV
        surv = None
        wsum = 0.0
        tot = 0.0
        hk = 20 if n > 20 else n - 1
        for r in x.rivals:
            d = x.gd[r][c]
            row = x.sr[r].get(d)
            if row is None:
                p0, p1, p2 = x.post[r]
                row = x.sr[r][d] = [p0 * s0[g] + p1 * s1[g] + p2 * s2[g] for g in _G[d][:n]]
            surv = row if surv is None else [a * b for a, b in zip(surv, row)]
            share = 1.0 - row[hk]
            wsum += share * x.w[r]
            tot += share
        if surv is None:
            surv = [1.0] * n
        if taken and _P["raid_hold"] != 1.0:
            k = _P["raid_hold"]
            surv = [q ** k for q in surv]
        pl = [1.0 - q for q in surv]
        sl = [0.0] * (n + 1)
        run = 0.0
        for h in range(n):
            run += pl[h]
            sl[h + 1] = run
        t = x.h1[key] = (pl, sl, wsum / tot if tot > 1e-12 else 0.33)
    return t


def _hold1(v, x, c, R, taken=False):
    if v.home[c] and _P["homefix"]:
        return v.base[c] * float(R)
    pl, sl, wv = _risk1(x, c, taken)
    return v.base[c] * (R - sl[R] * (1.0 + wv) - 8.0 * wv * pl[R])


def _hold2(v, x, c, R):
    if v.home[c] and _P["homefix"]:
        return v.base[c] * 2.0 * R
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
    return (8.0 * v.base[c] * (1 + lvl) + _hold1(v, x, c, R, True)
            + x.w[d] * v.base[c] * (1 + lvl) * R)


def _plan(v, m, x):
    """Beam search over sequences of jobs.
    Returns (target, kind, best_rate, stay_gain, turn_rate)."""
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
            # claim and upgrade without leaving: the cell is never exposed at level 1
            jobs.append([jobs[k][0], "CU", 4, -1, k])
    n1 = len(jobs)
    for k in range(n0):
        if jobs[k][1] == "C":
            jobs.append([jobs[k][0], "U", 3, k, None])

    # A claimed cell is not left un-upgraded for the rest of the game: sooner or later it
    # gets its upgrade and is then nearly safe. So a level-1 cell is priced as exposed for
    # `lag` turns and protected after that, instead of exposed to the end. The upgrade's
    # own gain is what it adds on top of that. lag = 0 keeps the old "exposed for ever".
    lag = _P["lag"]
    own_cache = {}

    def own1(c, R):
        """Value of holding c at level 1 from now with R turns left."""
        if lag <= 0 or R <= lag or home[c]:
            return _hold1(v, x, c, R)
        val = own_cache.get(c * 128 + R)
        if val is None:
            pl, sl, wv = _risk1(x, c)
            gone = sl[lag] + (R - lag) * pl[lag]        # expected turns without the cell
            val = own_cache[c * 128 + R] = base[c] * (R - gone * (1.0 + wv) - 8.0 * wv * pl[lag])
        return val

    def gain(job, k_used):
        """Value of finishing `job` after k_used steps (this turn counts as step 1)."""
        c, kind = job[0], job[1]
        R = left - k_used + 1
        if R <= 0:
            return -1.0
        if kind == "C":
            return own1(c, R)
        if kind == "CU":
            # three turns of level-1 income while standing on it, then level 2
            return 3.0 * base[c] + _hold2(v, x, c, R)
        if kind == "U":
            # exposed until I am back on it: from now for a cell I already own, a few
            # turns for one claimed earlier in this plan
            wait = k_used - job[2] if job[3] < 0 else 3
            keep = 1.0 - _risk1(x, c)[0][wait if wait > 0 else 0]
            if keep < 0.05:
                keep = 0.05
            # A cell claimed earlier in this plan was credited own1; one I already hold
            # is compared with never upgrading it, which keeps upgrades from being put off.
            return keep * (_hold2(v, x, c, R) - (_hold1(v, x, c, R) if job[3] < 0 else own1(c, R)))
        p_now, p_late, delay, tgt, d = job[4]
        g = p_now * _take_value(v, x, tgt, R, d)
        if p_late > 0.0 and R - delay > 0:
            g += p_late * _take_value(v, x, tgt, R - delay, d)
        return g * raid_exec

    if not jobs:
        return None, None, 0.0, 0.0, 0.0
    scored = []
    best_rate = 0.0
    turn_rate = 0.0             # best rate when banked stays are not credited to this turn
    stay_gain = 0.0
    cu_of = {}
    for k in range(n0, n1):
        cu_of[jobs[k][4]] = k
    for k in range(n0):
        job = jobs[k]
        c = job[0]
        cost = travel[c] + job[2]
        if cost > left:
            continue
        g = gain(job, cost)
        rate = g / cost
        kc = cu_of.get(k)
        if kc is not None and cost + 3 <= left:
            g2 = gain(jobs[kc], cost + 3)
            if g2 > 0.0 and g2 / (cost + 3) > rate:
                rate = g2 / (cost + 3)
                if g <= 0.0:
                    g = 1e-9            # worth claiming only together with its upgrade
        if g <= 0.0:
            continue
        if rate > best_rate:
            best_rate = rate
        # a job I am part-way through is not a measure of what one turn is worth
        fresh = g / (cost + myprog) if (c == at and myprog and job[1] != "C") else rate
        if fresh > turn_rate:
            turn_rate = fresh
        if c == at and job[2] == 1:
            stay_gain = max(stay_gain, g)
        scored.append((rate + (1e6 if c == at else 0.0), k))
    if not scored:
        return None, None, 0.0, 0.0, 0.0
    scored.sort(reverse=True)
    index = {}
    short = []
    for _, k in scored[:_P["jobs"]]:
        index[k] = len(short)
        short.append(jobs[k])
    excl = [0] * len(short)             # jobs that cannot both be in one plan
    for k in range(n0, n1):             # claim-and-upgrade twins of shortlisted claims
        pre = jobs[k][4]
        if pre in index:
            j = list(jobs[k])
            excl.append(1 << index[pre])
            excl[index[pre]] |= 1 << len(short)
            short.append(j)
    for k in range(n1, len(jobs)):      # later upgrades of shortlisted claims
        pre = jobs[k][3]
        if pre in index:
            j = list(jobs[k])
            j[3] = index[pre]
            twin = excl[index[pre]]
            excl.append(twin)
            short.append(j)
    nj = len(short)
    tail_k = _P["tail"] * (turn_rate if _P["fresh_tail"] else best_rate) / (2.0 * left)
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
                if mask & bit or mask & excl[j]:
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
        return None, None, best_rate, stay_gain, turn_rate
    job = short[best[5]]
    return job[0], job[1], best_rate, stay_gain, turn_rate


def _stay_prob(m, r, ctx):
    ps = _ratio(m.st[r][ctx])
    if m.feinted_me[r]:
        ps *= _P["feint_pen"] ** m.feinted_me[r]
    return min(0.97, max(0.03, ps))


def _shield_call(v, m, x, rate, stay_gain, banking=False):
    """Is SHIELD worth more than carrying on? Compares expected points, not reflexes."""
    me, left = x.me, x.left
    benefit = 0.0           # expected points saved or denied by casting now
    miss = 1.0              # chance nobody eligible stays: the cast backfires
    worst = 0.0
    worst_l1 = False
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
            worst_l1 = not lvl
    cost = rate + m.prog[me] * rate * 0.5
    if imminent:
        if left <= 1:
            return benefit > stay_gain
        if _P["end_backfire"] and left < 5:
            # frozen for what is left of the game at most; the raider that stepped aside
            # needs a move and three stays to come back for an upgraded cell
            backfire = min(2, left - 1) * rate + (worst if worst_l1 else 0.0)
        else:
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
        if banking and _P["bank_shield"]:
            return True         # the stay I would bank now is wiped by a shield next turn
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
    target, kind, rate, stay_gain, turn_rate = _plan(v, m, x)
    if _P["fresh_rate"]:
        rate = turn_rate
    action = stay
    if target is not None:
        if target == x.at:
            action = "STAY"
        elif _P["routes"]:
            action = _first_step(v, x, target) or stay
        else:
            action = x.first[target] or stay
    can_shield = ("SHIELD" in legal) and m.cd[me] == 0
    if can_shield and _P["shields"]:
        banking = False
        if action == "STAY" and m.prog[me] <= 1:
            o = v.owner[x.at]
            banking = (not v.level[x.at]) if o == me else (o != 0 and bool(v.level[x.at]))
        if _shield_call(v, m, x, rate, stay_gain if action == "STAY" else 0.0, banking):
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
