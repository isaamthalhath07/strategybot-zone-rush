"""Zone Rush bot: exact public-state tracker, hazard-aware route planner, adaptive tactics.

Single file, standard library only, entry point act(state). Uses the four documented
inputs (board, bot_id, is_priority_token, legal_actions) plus its own memory of earlier
public boards. Nothing here reads another bot's pending action or any hidden counter.
"""

# ----------------------------------------------------------------------------- geometry
_ADJ = []
_DIST = []
for _i in range(64):
    _r, _c = divmod(_i, 8)
    _row = []
    if _r > 0:
        _row.append(("NORTH", _i - 8))
    if _c < 7:
        _row.append(("EAST", _i + 1))
    if _r < 7:
        _row.append(("SOUTH", _i + 8))
    if _c > 0:
        _row.append(("WEST", _i - 1))
    _ADJ.append(tuple(_row))
    _DIST.append(tuple(abs(_r - j // 8) + abs(_c - j % 8) for j in range(64)))
_NB = [tuple(j for _, j in row) for row in _ADJ]


# ----------------------------------------------------------------------------- reading

class _View(object):
    __slots__ = ("me", "legal", "token", "pos", "owner", "level", "frozen", "base", "home", "occ")


def _read(state):
    """Normalise the documented input into flat lists. Never mutates `state`."""
    if isinstance(state, dict):
        get = lambda o, k, d=None: o.get(k, d)
    else:
        get = lambda o, k, d=None: getattr(o, k, d)
    v = _View()
    v.me = int(get(state, "bot_id"))
    v.token = bool(get(state, "is_priority_token", False))
    legal = []
    for a in (get(state, "legal_actions", ()) or ()):
        name = a if isinstance(a, str) else (getattr(a, "name", None) or getattr(a, "value", None))
        if isinstance(name, str):
            legal.append(name.upper())
    v.legal = legal
    board = get(state, "board")
    first = board[0]
    if isinstance(first, (list, tuple)) and len(first) == 8 and not hasattr(first, "owner"):
        cells = [c for row in board for c in row]
    else:
        cells = list(board)
    if len(cells) != 64:
        raise ValueError("board")
    if isinstance(cells[0], dict):
        cg = lambda o, k, d=None: o.get(k, d)
    else:
        cg = lambda o, k, d=None: getattr(o, k, d)
    v.pos = [-1] * 5
    v.frozen = [False] * 5
    v.owner = [0] * 64
    v.level = [0] * 64
    v.base = [1] * 64
    v.home = [False] * 64
    v.occ = [0] * 64
    for i, c in enumerate(cells):
        o = int(cg(c, "occupant", 0) or 0)
        v.owner[i] = int(cg(c, "owner", 0) or 0)
        v.level[i] = 1 if cg(c, "is_upgraded", False) else 0
        v.base[i] = int(cg(c, "base_points", 1) or 1)
        v.home[i] = bool(cg(c, "is_home", False))
        if 1 <= o <= 4:
            v.occ[i] = o
            v.pos[o] = i
            v.frozen[o] = bool(cg(c, "is_frozen", False))
    if v.pos[v.me] < 0:
        raise ValueError("self not on board")
    return v


# ----------------------------------------------------------------------------- tracker

def _need(seat, owner, level, home):
    """Stays required for `seat` to finish the job on a cell in the given state."""
    if owner == seat:
        return 0 if level else 3
    if owner == 0:
        return 1
    if home:
        return 0
    return 3 if level else 1


def _pristine(v):
    if sum(1 for o in v.owner if o) != 4 or any(v.level):
        return False
    for s in range(1, 5):
        p = v.pos[s]
        if p < 0 or not v.home[p] or v.owner[p] != s:
            return False
    return True


class _Mem(object):
    """Everything remembered between turns of one game."""

    def __init__(self, v):
        fresh = _pristine(v)
        self.known_start = fresh
        if fresh:
            self.turn = 1
            self.cd_sure = [True] * 5
        else:
            # Dropped into a running game: estimate the clock from how developed the board is.
            owned = sum(1 for o in v.owner if o) - 4
            self.turn = min(70, max(2, 2 + owned + 2 * sum(v.level)))
            self.cd_sure = [False] * 5
        self.pos, self.owner, self.level, self.frozen = list(v.pos), list(v.owner), list(v.level), list(v.frozen)
        self.last = None                 # action requested last turn
        self.shield_was_legal = False
        self.legal_filters = False       # the server has been seen to withhold SHIELD on cooldown
        self.scores = [0] * 5
        self.prog = [0] * 5              # banked stays toward the job on the current cell
        self.cd = [0] * 5                # turns until SHIELD is available again (0 = ready)
        self.fr = [1 if f else 0 for f in v.frozen]   # forced-STAY turns still to serve
        self.token = None                # seat holding the priority token on turn 1
        self.not_token = set()
        # opponent models as [hits, trials], seeded with population priors
        self.sh = [None] + [{"a1": [0.8, 2.0], "a2": [1.7, 2.0], "b": [0.25, 2.0]} for _ in range(4)]
        self.st = [None] + [{"a1": [1.5, 2.0], "a2": [1.8, 2.0], "b": [1.5, 2.0]} for _ in range(4)]
        self.raid_n = [0.0] * 5
        self.raid_opp = [0.0] * 5
        self.shields_seen = [0] * 5
        self.backfires_seen = [0] * 5
        self.feinted_me = [0] * 5        # times this rival sidestepped my shield
        self.presence_rule = False       # a successful mover was caught: sidesteps are unsafe
        self.failed = {}                 # cell -> (owner, level) for jobs that refused to complete
        self.unexplained = 0
        self.plan = None
        self.raid = None
        self.note_token(v)

    # -- priority token -------------------------------------------------------------
    def note_token(self, v):
        """The token passes 1->2->3->4 every turn; one sighting of our flag fixes the cycle."""
        if self.token is not None or not self.known_start:
            return
        start = ((v.me - 1) - (self.turn - 1)) % 4 + 1
        if v.token:
            self.token = start
        else:
            self.not_token.add(start)
            if len(self.not_token) == 3:
                self.token = ({1, 2, 3, 4} - self.not_token).pop()

    def token_holder(self, turn):
        if self.token is None:
            return None
        return (self.token - 1 + turn - 1) % 4 + 1

    # -- one turn of public evidence --------------------------------------------------
    def observe(self, v):
        me = v.me
        self.turn = min(self.turn + 1, 80)
        ppos, pown, plev, pfro = self.pos, self.owner, self.level, self.frozen
        moved = [False] * 5
        for s in range(1, 5):
            moved[s] = v.pos[s] != ppos[s]
        newly = set(s for s in range(1, 5) if v.frozen[s] and not pfro[s])
        gained = [False] * 5             # took a cell or finished an upgrade: it effectively stayed
        lost = [False] * 5
        for c in range(64):
            if v.owner[c] != pown[c]:
                if v.owner[c]:
                    gained[v.owner[c]] = True
                if pown[c]:
                    lost[pown[c]] = True
            elif v.level[c] and not plev[c] and v.owner[c]:
                gained[v.owner[c]] = True

        shielders = self._who_shielded(v, me, moved, newly, gained, lost)
        caught = set()
        for x in shielders:
            for s in newly:
                if s != x and s not in shielders and pown[ppos[s]] == x:
                    caught.add(s)

        # ---- per-opponent statistics from last turn's stand-offs
        for r in range(1, 5):
            p = ppos[r]
            d = pown[p]
            if d == 0 or d == r or pfro[r] or v.home[p]:
                continue
            ctx = "a1" if not plev[p] else ("a2" if self.prog[r] >= 2 else "b")
            if r != me and r not in shielders:
                row = self.st[r][ctx]
                row[0] = 0.9 * row[0] + (0.0 if moved[r] else 1.0)
                row[1] = 0.9 * row[1] + 1.0
            if d != me and not pfro[d] and self.cd[d] == 0:
                row = self.sh[d][ctx]
                row[0] = 0.9 * row[0] + (1.0 if d in shielders else 0.0)
                row[1] = 0.9 * row[1] + 1.0
            if d == me and me in shielders and moved[r]:
                self.feinted_me[r] += 1
        for s in shielders:
            self.shields_seen[s] += 1
            if s in newly:
                self.backfires_seen[s] += 1

        # ---- raid propensity: adjacent to somebody's exposed level-1 cell, did it step on?
        occupied = set(ppos[1:])
        for r in range(1, 5):
            if r == me or pfro[r]:
                continue
            chance = False
            for q in _NB[ppos[r]]:
                o = pown[q]
                if o and o != r and not plev[q] and not v.home[q] and q not in occupied:
                    chance = True
                    break
            if chance:
                self.raid_opp[r] += 1.0
                q = v.pos[r]
                if moved[r] and pown[q] and pown[q] != r and not plev[q] and not v.home[q]:
                    self.raid_n[r] += 1.0

        # ---- progress (mirrors the documented work rules)
        for s in range(1, 5):
            if moved[s] or pfro[s] or s in shielders or s in newly:
                self.prog[s] = 0
                continue
            p = v.pos[s]
            land = pown[p]
            need = _need(s, land, plev[p], v.home[p])
            if need == 0:
                continue
            if land and land != s and land in shielders:
                continue
            if (v.owner[p] == s and land != s) or (land == s and v.level[p] and not plev[p]):
                self.prog[s] = 0
            else:
                self.prog[s] += 1
                if self.prog[s] >= need:
                    # The job should have completed. Remember it so we stop retrying forever.
                    if s == me:
                        self.failed[p] = (v.owner[p], v.level[p])
                    self.prog[s] = need - 1
        # ---- cooldowns
        for s in range(1, 5):
            if s in shielders:
                self.cd[s] = 4
                self.cd_sure[s] = True
            elif self.cd[s] > 0:
                self.cd[s] -= 1
        # ---- scores: income after resolution plus raid bonuses
        for c in range(64):
            o = v.owner[c]
            if o:
                self.scores[o] += v.base[c] * (1 + v.level[c])
                po = pown[c]
                if po and po != o:
                    self.scores[o] += 8 * v.base[c] * (1 + plev[c])
        for s in range(1, 5):
            if not v.frozen[s]:
                self.fr[s] = 0
            elif s in newly:
                self.fr[s] = 2
            else:
                self.fr[s] = max(1, self.fr[s] - 1)
        self.pos, self.owner, self.level, self.frozen = list(v.pos), list(v.owner), list(v.level), list(v.frozen)
        self.note_token(v)

    def _who_shielded(self, v, me, moved, newly, gained, lost):
        """Explain the new freezes. Every SHIELD freezes somebody: its victims, or its caster."""
        ppos, pown, pfro = self.pos, self.owner, self.frozen
        mine = (self.last == "SHIELD" and self.shield_was_legal and not pfro[me])
        if not newly:
            return set()
        for s in newly:
            if moved[s]:
                # Frozen after a successful move: this server catches by presence, not by STAY.
                self.presence_rule = True
        cand = []
        for s in range(1, 5):
            if pfro[s] or moved[s] or gained[s] or lost[s]:
                continue
            if s == me:
                if mine:
                    cand.append(s)
                continue
            if self.cd[s] > 0 and self.cd_sure[s]:
                continue
            cand.append(s)
        best, best_cost = None, None
        n = len(cand)
        for mask in range(1, 1 << n):
            sh = [cand[k] for k in range(n) if mask >> k & 1]
            pred = set()
            cost = 0.0
            for x in sh:
                got = [s for s in range(1, 5)
                       if s != x and s not in sh and not pfro[s]
                       and (not moved[s] or self.presence_rule) and pown[v.pos[s]] == x]
                if got:
                    pred.update(got)
                    cost += 1.0             # a landlord defending: the ordinary cause
                else:
                    pred.add(x)
                    land = pown[ppos[x]]
                    # Backfiring on someone else's land is rarer than a landlord's catch.
                    cost += 1.5 if (land == 0 or land == x) else 3.0
            if pred != newly:
                continue
            if mine and me not in sh:
                cost += 5.0                 # my own accepted SHIELD should be part of the story
            if best is None or cost < best_cost:
                best, best_cost = set(sh), cost
        if best is None:
            self.unexplained += 1
            best = set()
            for s in newly:
                land = pown[ppos[s]]
                if land and land != s and not pfro[land]:
                    best.add(land)
                else:
                    best.add(s)
        return best


_M = None


def _update(v):
    global _M
    m = _M
    restart = m is None
    if not restart and _pristine(v):
        # A pristine board can also be turn 2 of a quiet opening; a new game is certain
        # once the remembered board had developed.
        if m.turn >= 80 or any(m.level) or sum(1 for o in m.owner if o) > 4:
            restart = True
    if restart:
        m = _M = _Mem(v)
    else:
        m.observe(v)
    me = v.me
    # Own cooldown: the legal list is authoritative once the server is seen to filter it.
    if not v.frozen[me]:
        if "SHIELD" not in v.legal:
            m.legal_filters = True
            if m.cd[me] == 0:
                m.cd[me] = 1
        elif m.legal_filters or not m.cd_sure[me]:
            m.cd[me] = 0
            m.cd_sure[me] = True
    return m


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
    "depth": 6,            # jobs per plan
    "tail": 0.6,           # value of time left after the plan, relative to today's best rate
    "raid_exec": 0.85,     # discount for everything a raid model cannot see
    "denial_floor": 0.10,
    "hazard": 1.0,         # global multiplier on the population loss curves
    "l1_delay": 0.3,       # share of a level-1 cell's value a shield really saves mid-game
    "shield_margin": 1.0,  # shield when benefit exceeds margin * cost
    "raids": 0,            # switches for ablation
    "shields": 1,
    "feints": 1,
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
    """Best neighbouring cell of the same landlord to slip onto, or None."""
    if m.presence_rule:
        return None
    best = None
    for a, t in _ADJ[cell]:
        if a not in v.legal or t in x.occupied or v.owner[t] != d or v.home[t]:
            continue
        if m.failed.get(t) == (d, v.level[t]):
            continue
        # the landlord stepping onto its own cell would win the contest
        score = v.base[t] * (2.0 if v.level[t] else 1.0)
        if _DIST[v.pos[d]][t] == 1:
            score *= 0.6
        if best is None or score > best[0]:
            best = (score, a, t)
    return best


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
            last_stay = travel[c] + need - 1
            v8 = 8.0 * base[c] * (1 + lvl)
            if last_stay < ready:
                jobs.append([c, "R", need, -1, (1.0, 0.0, 0, v8, o)])
            elif not lvl:
                q = _ratio(m.sh[o]["a1"])
                # caught: thaw and finish three turns later while its SHIELD recharges
                jobs.append([c, "R", need, -1, (1.0 - q, q * 0.8, 3, v8, o)])
            else:
                q = _ratio(m.sh[o]["a2"])
                qb = _ratio(m.sh[o]["b"])
                early = (1.0 - qb) ** max(0, need - 1)
                side = _sidestep(v, m, x, c, o) if _P["feints"] else None
                p_stay = (1.0 - q) * early
                if side is not None and q * early > p_stay:
                    t = side[2]
                    extra = 1 + (3 if level[t] else 1)
                    jobs.append([c, "R", need + extra, -1, (q * early, 0.0, 0,
                                                             8.0 * base[t] * (1 + level[t]), o)])
                else:
                    jobs.append([c, "R", need, -1, (p_stay, 0.0, 0, v8, o)])
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
        p_now, p_late, delay, bonus, d = job[4]
        lvl = level[c]
        g = p_now * (bonus + _hold1(v, x, c, R) + w[d] * base[c] * (1 + lvl) * R)
        if p_late > 0.0 and R - delay > 0:
            R2 = R - delay
            g += p_late * (bonus + _hold1(v, x, c, R2) + w[d] * base[c] * (1 + lvl) * R2)
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
    beam = [(0.0, 0.0, 0, at, 0, -1)]
    best = None
    width = _P["beam"]
    for depth in range(_P["depth"]):
        seen = {}
        for _, value, used, pos, mask, f0 in beam:
            drow = _DIST[pos]
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
                nv = value + g
                rem = left - k_used
                sc = nv + tail_k * rem * rem
                key = (c, mask | bit)
                old = seen.get(key)
                if old is None or old[0] < sc:
                    seen[key] = (sc, nv, k_used, c, mask | bit, j if f0 < 0 else f0)
        if not seen:
            break
        beam = sorted(seen.values(), reverse=True)[:width]
        if best is None or beam[0][0] > best[0]:
            best = beam[0]
    if best is None:
        return None, None, best_rate, stay_gain
    job = short[best[5]]
    return job[0], job[1], best_rate, stay_gain


def _shield_call(v, m, x, rate, stay_gain):
    """Is SHIELD worth more than carrying on? Compares expected points, not reflexes."""
    me, left = x.me, x.left
    benefit = 0.0
    miss = 1.0
    worst = 0.0
    imminent = False
    for r in x.rivals:
        if v.frozen[r]:
            continue
        cell = v.pos[r]
        if v.owner[cell] != me:
            continue
        lvl = v.level[cell]
        pr = m.prog[r]
        is_home = v.home[cell]
        ctx = "a1" if (not lvl and not is_home) else ("a2" if pr >= 2 else "b")
        ps = _ratio(m.st[r][ctx])
        if m.feinted_me[r]:
            ps *= 0.5 ** m.feinted_me[r]
        ps = min(0.97, max(0.03, ps))
        miss *= 1.0 - ps
        benefit += ps * x.w[r] * 2.0 * rate          # a caught rival loses two turns
        if is_home:
            continue
        need = 1 if not lvl else 3 - pr
        if need > 1:
            continue
        imminent = True
        keep = _hold2(v, x, cell, left) if lvl else _hold1(v, x, cell, left)
        loss = keep + x.w[r] * (8.0 * v.base[cell] * (1 + lvl) + v.base[cell] * left)
        if not lvl and left > 3:
            loss *= _P["l1_delay"]                   # it thaws and takes the cell anyway
        benefit += ps * loss
        if loss > worst:
            worst = loss
    if not imminent:
        return False
    if left <= 1:
        return benefit > stay_gain
    cost = rate + m.prog[me] * rate * 0.5
    backfire = 2.0 * rate + worst
    if left == 2:
        backfire = rate
    return benefit > _P["shield_margin"] * (cost + miss * backfire)


def _raid_step(v, m, x, rate):
    """Standing on a rival's cell with the plan saying STAY: stay, or slip sideways?"""
    me, at = x.me, x.at
    d = v.owner[at]
    lvl = v.level[at]
    ready = _shield_ready_in(m, v, d)
    if ready > 0:
        return "STAY"
    need = 1 if not lvl else 3 - m.prog[me]
    side = _sidestep(v, m, x, at, d) if _P["feints"] else None
    if side is None:
        return "STAY"
    base = v.base
    left = x.left
    if need > 1:
        # only a landlord that shields on sight is worth dodging this early
        if _ratio(m.sh[d]["b"]) > 0.6 and m.sh[d]["b"][1] > 3.0:
            return side[1]
        return "STAY"
    t = side[2]
    win_here = 8.0 * base[at] * (1 + lvl) + base[at] * left * (1.0 + x.w[d] * (1 + lvl))
    win_there = 8.0 * base[t] * (1 + v.level[t]) + base[t] * left * (1.0 + x.w[d] * (1 + v.level[t]))
    freeze_bonus = x.w[d] * 2.0 * rate
    if not lvl:
        q = _ratio(m.sh[d]["a1"])
        ev_stay = win_here - q * 3.0 * rate
        ev_side = q * (win_there + win_here * 0.8 + freeze_bonus) - (1.0 - q) * rate
    else:
        q = _ratio(m.sh[d]["a2"])
        ev_stay = (1.0 - q) * win_here - q * 2.0 * rate
        ev_side = q * (win_there + freeze_bonus) - (1.0 - q) * 3.0 * rate
    return side[1] if ev_side > ev_stay else "STAY"


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


def act(state):
    try:
        v = _read(state)
    except Exception:
        legal = getattr(state, "legal_actions", None) or ["STAY"]
        return "STAY" if "STAY" in legal else legal[0]
    m = None
    try:
        m = _update(v)
        action = _decide(v, m)
    except Exception:
        action = "STAY"
        m = _M
    if action not in v.legal:
        action = "STAY" if "STAY" in v.legal else v.legal[0]
    if m is not None:
        m.last = action
        m.shield_was_legal = "SHIELD" in v.legal
    return action
