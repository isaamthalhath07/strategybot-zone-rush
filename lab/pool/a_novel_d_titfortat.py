"""
novel_d -- three Zone Rush opponents from the "in-game learning and social" family.

    nv_d_titfortat    reciprocal farmer: never raids an innocent, retaliates in kind, forgives.
    nv_d_antileader   rebuilds every score from the board and gangs up on the leader.
    nv_d_shieldmaster defence-and-tempo: models shields and cooldowns, baits, raids in windows.

All three share one observation layer (_Core) that reconstructs, from consecutive
views only: the turn number, every bot's score, raids (who took what from whom),
shield events and therefore every bot's shield cooldown (from the freezes they
cause), every bot's consecutive-stay count (progress) and simple behaviour
statistics (does a bot that steps onto rival land stay to raid?  does an owner
shield when an intruder is about to complete?).  They also share a farming
planner: a two-step orienteering search over claim / upgrade / raid targets that
maximises points gained per turn spent.  Each bot plugs its own social policy
into the raid valuation, the shield decision and a few special moves.

Standard library only; the bots never import the repository.
"""
import random

_N = 8
_NC = 64
_T = 80
_RIVAL_SEATS = (1, 2, 3, 4)


def _build_nb():
    nb = []
    for p in range(_NC):
        r, c = divmod(p, _N)
        lst = []
        if r > 0:
            lst.append(("NORTH", p - _N))
        if r < _N - 1:
            lst.append(("SOUTH", p + _N))
        if c > 0:
            lst.append(("WEST", p - 1))
        if c < _N - 1:
            lst.append(("EAST", p + 1))
        nb.append(tuple(lst))
    return tuple(nb)


_NB = _build_nb()
_MAN = tuple(tuple(abs(p // _N - q // _N) + abs(p % _N - q % _N) for q in range(_NC))
             for p in range(_NC))


class _Core(object):
    """Shared observation layer + farming planner.  Not a bot by itself."""
    name = "nv_d_core"
    KFIRST = 6            # first targets expanded by the two-step search
    LAM_DEF = 0.5         # weight of a rival's gain when valuing my defence
    SHIELD_MARGIN = 0.0   # extra benefit required before shielding

    def __init__(self, seed=0):
        self.rng = random.Random(seed)
        self.t = 0
        self.me = 0
        self.base = None
        self.home = None
        self.prev = None
        self.score = [0] * 5
        self.income = [0] * 5
        self.sc = [0] * 5            # consecutive progress-counting stays per seat
        self.last_shield = [-99] * 5
        self.frz_age = [0] * 5
        self.my_prog = 0
        self.last_act = "STAY"
        self.last_target = -1
        self.raids_by = [0] * 5
        self.attempts_by = [0] * 5   # times caught by a shield while on rival land
        self.hz = [0.0] * _NC
        self.raid_val = [[0] * 5 for _ in range(5)]   # raid_val[a][b]: bonus a took from b
        self.stay_opp = [0] * 5      # intruder just arrived on rival land ...
        self.stay_yes = [0] * 5      # ... and stayed
        self.r1_opp = [0] * 5        # owner could shield at a level-1 completing stay
        self.r1_yes = [0] * 5
        self.ru_opp = [0] * 5        # owner could shield at an early stay on an upgraded cell
        self.ru_yes = [0] * 5
        self.rl_opp = [0] * 5        # owner could shield at the last stay on an upgraded cell
        self.rl_yes = [0] * 5
        self.newly = [False] * 5
        self.shielded = ()
        self.owner = self.upg = self.occ = None
        self.pos = [-1] * 5
        self.frz = [False] * 5

    # ------------------------------------------------------------------ API
    def __call__(self, view):
        try:
            a = self.act(view)
        except Exception:
            a = "STAY"
        return a if a in view.legal_actions else "STAY"

    def act(self, view):
        self.t += 1
        self._observe(view)
        self._tick()
        legal = view.legal_actions
        me = self.me
        if len(legal) <= 1 or self.frz[me]:
            a = "STAY"
        else:
            a = self._decide(legal)
            if a not in legal:
                a = "STAY"
        self.last_act = a
        if a == "SHIELD":
            self.last_shield[me] = self.t
        return a

    # --------------------------------------------------------- observation
    def _observe(self, view):
        bd = view.board
        first = self.base is None
        if first:
            self.me = view.bot_id
            self.base = [0] * _NC
            self.home = [0] * _NC
        base = self.base
        home = self.home
        owner = [0] * _NC
        upg = [False] * _NC
        occ = [0] * _NC
        pos = [-1] * 5
        frz = [False] * 5
        p = 0
        for row in bd:
            for cell in row:
                o = cell.owner
                owner[p] = o
                if cell.is_upgraded:
                    upg[p] = True
                oc = cell.occupant
                if oc:
                    occ[p] = oc
                    pos[oc] = p
                    if cell.is_frozen:
                        frz[oc] = True
                if first:
                    base[p] = cell.base_points
                    if cell.is_home:
                        home[p] = o
                p += 1
        me = self.me
        newly = [False] * 5
        shielded = set()
        if self.prev is not None:
            po, pu, pp, pf = self.prev
            prev_turn = self.t - 1
            changed = set()
            for q in range(_NC):
                if po[q] != owner[q]:
                    changed.add(q)
                    x = owner[q]
                    v = po[q]
                    if v and x:
                        lvl = 2 if pu[q] else 1
                        bonus = 8 * base[q] * lvl
                        self.score[x] += bonus
                        self.raids_by[x] += 1
                        self.raid_val[x][v] += bonus
                        self._on_raid(x, v, q, lvl, bonus)
                elif pu[q] != upg[q]:
                    changed.add(q)
            inc = [0] * 5
            for q in range(_NC):
                o = owner[q]
                if o:
                    inc[o] += base[q] * (2 if upg[q] else 1)
            for s in _RIVAL_SEATS:
                self.score[s] += inc[s]
            self.income = inc
            # --- freezes -> shield events
            for s in _RIVAL_SEATS:
                if frz[s] and not pf[s]:
                    newly[s] = True
            if self.last_act == "SHIELD" and not pf[me]:
                shielded.add(me)
            for s in _RIVAL_SEATS:
                if not newly[s]:
                    continue
                if s == me:
                    if me not in shielded:
                        o = owner[pos[s]]
                        if o and o != me:
                            shielded.add(o)
                    continue
                o = owner[pos[s]]
                if o == me:
                    if me in shielded:
                        self.attempts_by[s] += 1
                        self._on_attempt(s, pos[s])
                    else:
                        shielded.add(s)
                elif o and o != s and not pf[o] and prev_turn >= self.last_shield[o] + 5:
                    shielded.add(o)
                    self.attempts_by[s] += 1
                else:
                    shielded.add(s)
            prev_sc = list(self.sc)
            # --- behaviour learning (uses pre-update cooldowns)
            for s in _RIVAL_SEATS:
                q0 = pp[s]
                if q0 < 0 or pf[s]:
                    continue
                v = po[q0]
                if v == 0 or v == s or home[q0]:
                    continue
                moved = pos[s] != q0
                k = prev_sc[s] if s != me else self.my_prog
                if s != me and k == 0:
                    self.stay_opp[s] += 1
                    if not moved:
                        self.stay_yes[s] += 1
                if v != me and not pf[v] and prev_turn >= self.last_shield[v] + 5:
                    did = 1 if v in shielded else 0
                    if not pu[q0]:
                        self.r1_opp[v] += 1
                        self.r1_yes[v] += did
                    elif k >= 2:
                        self.rl_opp[v] += 1
                        self.rl_yes[v] += did
                    else:
                        self.ru_opp[v] += 1
                        self.ru_yes[v] += did
            for x in shielded:
                self.last_shield[x] = prev_turn
            # --- stay counts
            for s in _RIVAL_SEATS:
                if s == me:
                    continue
                q = pos[s]
                if q != pp[s]:
                    self.sc[s] = 0
                elif newly[s] or pf[s] or s in shielded or q in changed:
                    self.sc[s] = 0
                else:
                    self.sc[s] += 1
            # --- my own progress (exact)
            q = pos[me]
            if q != pp[me] or pf[me] or newly[me] or self.last_act == "SHIELD":
                self.my_prog = 0
            elif q in changed:
                self.my_prog = 0
            else:
                o = po[q]
                if o == me:
                    if not pu[q]:
                        self.my_prog += 1
                elif o == 0:
                    self.my_prog = 0
                elif not home[q]:
                    self.my_prog += 1
            self.sc[me] = self.my_prog
        else:
            inc = [0] * 5
            for q in range(_NC):
                o = owner[q]
                if o:
                    inc[o] += base[q] * (2 if upg[q] else 1)
            self.income = inc
        for s in _RIVAL_SEATS:
            if frz[s]:
                self.frz_age[s] = self.frz_age[s] + 1 if (self.prev is not None and self.prev[3][s]) else 1
            else:
                self.frz_age[s] = 0
        self.owner, self.upg, self.occ, self.pos, self.frz = owner, upg, occ, pos, frz
        self.newly = newly
        self.shielded = shielded
        self.prev = (owner, upg, pos, frz)

    # ------------------------------------------------------- model helpers
    def can_shield_at(self, s, u):
        """Could seat s shield at offset u turns from now (0 = this turn)?"""
        if self.t + u < self.last_shield[s] + 5:
            return False
        if self.frz[s]:
            if u == 0:
                return False
            if u == 1 and self.frz_age[s] == 1:
                return False
        return True

    def p_stay(self, y):
        """Probability that rival y, standing on rival land with no progress, stays."""
        return (self.stay_yes[y] + 2.0 + min(self.raids_by[y], 4) * 0.5) / \
               (self.stay_opp[y] + 3.0 + min(self.raids_by[y], 4) * 0.5)

    def p_resp(self, v, kind):
        if kind == 1:
            return (self.r1_yes[v] + 0.9) / (self.r1_opp[v] + 2.0)
        if kind == 2:
            return (self.rl_yes[v] + 1.2) / (self.rl_opp[v] + 2.0)
        return (self.ru_yes[v] + 0.6) / (self.ru_opp[v] + 2.0)

    def rivals(self):
        return [s for s in _RIVAL_SEATS if s != self.me]

    # --------------------------------------------------------------- hooks
    def _tick(self):
        pass

    def _on_raid(self, raider, victim, q, lvl, bonus):
        pass

    def _on_attempt(self, raider, q):
        pass

    def _catch_prob(self, o, q, off, s):
        """Chance that owner o's shield catches me during my s stays starting at
        offset off.  Default: visible information only (a frozen owner cannot
        shield) plus the learned shield-response rates."""
        if self.frz[o]:
            fr = 2 if self.frz_age[o] == 1 else 1
            if off + s - 1 < fr:
                return 0.0
        if not self.upg[q]:
            return 0.85 * self.p_resp(o, 1)
        pl = self.p_resp(o, 2)
        pe = self.p_resp(o, 0)
        return 1.0 - (1.0 - pe) ** max(0, s - 1) * (1.0 - pl)

    def _raid_params(self, o, q, off, prog):
        """(weight, lambda, p_caught) for raiding owner o's cell q, or None."""
        s = max(1, 3 - prog) if self.upg[q] else 1
        return (1.0, 0.3, self._catch_prob(o, q, off, s))

    def _avoid(self, blk):
        pass

    def _lam_def(self, y):
        return self.LAM_DEF

    def _special(self, legal, act, rate, tgt):
        return None

    def _shield_filter(self, y, q, lvl):
        return True

    def _reserve_cost(self, rate):
        return 0.0

    # ------------------------------------------------------------ planner
    _W = (0.10, 0.10, 0.07, 0.045, 0.03, 0.018, 0.01, 0.005, 0.002, 0.001,
          0.0, 0.0, 0.0, 0.0, 0.0)
    UPG_HZ = 0.35        # hazard multiplier of an upgraded cell
    HZ_MULT = 1.0
    HZ_BASE = 0.0005
    AGG_PRIOR = 0.35

    def aggression(self, y):
        a = (self.raids_by[y] + 0.5 * self.attempts_by[y] + self.AGG_PRIOR) / (1.0 + 0.08 * self.t)
        return a if a < 2.0 else 2.0

    def _hazard(self):
        """Per-cell chance per turn that a level-1 cell there gets raided."""
        hz = [self.HZ_BASE] * _NC
        W = self._W
        for y in _RIVAL_SEATS:
            if y == self.me:
                continue
            p = self.pos[y]
            if p < 0:
                continue
            a = self.aggression(y) * self.HZ_MULT
            if a <= 0.0:
                continue
            row = _MAN[p]
            for q in range(_NC):
                hz[q] += a * W[row[q]]
        return hz

    def _value(self, q, prog, off, hz):
        """(stays, extra_time, A, c1, h1, c2, h2): gain(rem) = A + c1*E(h1) + c2*E(h2)
        with E(h) = rem / (1 + h*rem) the expected number of income turns."""
        o = self.owner[q]
        b = float(self.base[q])
        me = self.me
        h = hz[q]
        if o == 0:
            return (1, 0.0, 0.0, b, h, 0.0, 0.0)
        if o == me:
            if self.upg[q]:
                return None
            if self.home[q]:
                return (3 - prog, 0.0, 0.0, b, 0.0, 0.0, 0.0)
            return (3 - prog, 0.0, 0.0, 2.0 * b, h * self.UPG_HZ, -b, h)
        if self.home[q]:
            return None
        rp = self._raid_params(o, q, off, prog)
        if rp is None:
            return None
        w, lam, pc = rp
        if w <= 0:
            return None
        if self.upg[q]:
            s = max(1, 3 - prog)
            f = w * (1.0 - pc)
            return (s, 2.0 * pc, 16.0 * b * f, (b + 2.0 * lam * b) * f, h, 0.0, 0.0)
        return (1, 3.0 * pc, 8.0 * b * w, (b + lam * b) * w, h, 0.0, 0.0)

    def _plan(self):
        me = self.me
        R = _T + 1 - self.t
        owner = self.owner
        base = self.base
        pos = self.pos
        p0 = pos[me]
        blk = [False] * _NC
        rpos = []
        for s in _RIVAL_SEATS:
            if s != me and pos[s] >= 0:
                blk[pos[s]] = True
                rpos.append((pos[s], 2 if self.frz[s] else 0))
        self._avoid(blk)
        blk[p0] = False
        dist = [-1] * _NC
        firsta = [None] * _NC
        dist[p0] = 0
        order = [p0]
        nbs = _NB
        i = 0
        while i < len(order):
            p = order[i]
            i += 1
            dp = dist[p] + 1
            nb = nbs[p]
            if p == p0 and len(nb) > 1:
                nb = list(nb)
                self.rng.shuffle(nb)
            for a, q in nb:
                if dist[q] < 0 and not blk[q]:
                    dist[q] = dp
                    firsta[q] = a if p == p0 else firsta[p]
                    order.append(q)
        man = _MAN
        mrd = [99] * _NC
        for rp, pen in rpos:
            row = man[rp]
            for q in range(_NC):
                v = row[q] + pen
                if v < mrd[q]:
                    mrd[q] = v
        hz = self._hazard()
        self.hz = hz
        UH = self.UPG_HZ
        stat = []
        for q in range(_NC):
            if blk[q] or dist[q] < 0:
                continue
            v = self._value(q, 0, 3, hz)
            if v is not None:
                stat.append((q, v, owner[q] == 0))
        cands = []
        lt = self.last_target
        myp = self.my_prog
        for q in order:
            d = dist[q]
            v = self._value(q, myp if q == p0 else 0, d, hz)
            if v is None:
                continue
            s, xT, A, c1, h1, c2, h2 = v
            Tn = d + s
            if Tn > R:
                continue
            rem = R - Tn + 1
            g = A + c1 * rem / (1.0 + h1 * rem)
            if c2:
                g += c2 * rem / (1.0 + h2 * rem)
            if owner[q] == 0 and d > 0:
                m = mrd[q]
                if m < d:
                    g *= 0.6
                elif m == d:
                    g *= 0.85
            if q == lt:
                g *= 1.08
            if g <= 0:
                continue
            T = Tn + xT
            cands.append((g / T, q, d, Tn, T, g))
        if not cands:
            return self._fallback(dist, firsta), 0.0, -1
        cands.sort(reverse=True)
        best = None
        for rate, q, d, Tn, T, g in cands[:self.KFIRST]:
            R1 = R - Tn
            bestc = rate
            if R1 >= 3 and owner[q] != me:
                b = base[q]
                h = hz[q]
                n = R1 - 2
                g2 = 2.0 * b * n / (1.0 + h * UH * n) - b * n / (1.0 + h * n)
                c = (g + g2) / (T + 3)
                if c > bestc:
                    bestc = c
            row = man[q]
            for q2, v2, neu in stat:
                if q2 == q:
                    continue
                s2, xT2, A2, c12, h12, c22, h22 = v2
                T2n = row[q2] + s2
                rem2 = R1 - T2n + 1
                if rem2 <= 0:
                    continue
                g2 = A2 + c12 * rem2 / (1.0 + h12 * rem2)
                if c22:
                    g2 += c22 * rem2 / (1.0 + h22 * rem2)
                if neu:
                    m = mrd[q2]
                    arr = Tn + row[q2]
                    if m < arr:
                        g2 *= 0.6
                    elif m == arr:
                        g2 *= 0.85
                c = (g + g2) / (T + T2n + xT2)
                if c > bestc:
                    bestc = c
            if best is None or bestc > best[0]:
                best = (bestc, q, d, rate)
        bestc, q, d, rate = best
        self.last_target = q
        act = "STAY" if d == 0 else firsta[q]
        return act, bestc, q

    def _fallback(self, dist, firsta):
        """Nothing worth doing: stand still, unless standing on forbidden rival land."""
        me = self.me
        p0 = self.pos[me]
        o = self.owner[p0]
        if o and o != me and not self.home[p0]:
            for a, q in _NB[p0]:
                if not self.occ[q] and self.owner[q] in (0, me):
                    return a
            for a, q in _NB[p0]:
                if not self.occ[q]:
                    return a
        return "STAY"

    # ------------------------------------------------------------- shields
    def _shield_value(self, rate):
        me = self.me
        R = _T + 1 - self.t
        owner = self.owner
        none_p = 1.0
        benefit = 0.0
        threat = False
        for y in _RIVAL_SEATS:
            if y == me:
                continue
            q = self.pos[y]
            if q < 0 or self.frz[y] or owner[q] != me:
                continue
            if self.home[q]:
                ps = 0.3
                none_p *= (1.0 - ps)
                continue
            b = self.base[q]
            if self.upg[q]:
                lvl, need = 2, 3
            else:
                lvl, need = 1, 1
            k = self.sc[y]
            if k >= need - 1:
                ps = self.p_stay(y) if need == 1 else 0.93
                if not self._shield_filter(y, q, lvl):
                    none_p *= (1.0 - ps)
                    continue
                lam = self._lam_def(y)
                h = self.hz[q] * (self.UPG_HZ if lvl == 2 else 1.0)
                er = R / (1.0 + h * R)
                loss = b * lvl * er + lam * (8 * b * lvl + b * er)
                if lvl == 2:
                    ben = 0.85 * loss + lam * 3 * rate
                elif R <= 3:
                    ben = loss
                else:
                    ben = 3 * b * (1 + lam) + lam * 3 * rate + 0.2 * loss
                benefit += ps * ben
                threat = True
            else:
                ps = 0.9
            none_p *= (1.0 - ps)
        if not threat:
            return -1.0
        cost = rate * (1 + self.my_prog) + none_p * rate * min(2, R - 1) + self._reserve_cost(rate)
        return benefit - cost - self.SHIELD_MARGIN

    def _decide(self, legal):
        act, rate, tgt = self._plan()
        if "SHIELD" in legal:
            if self._shield_value(max(rate, 1.0)) > 0:
                return "SHIELD"
        sp = self._special(legal, act, rate, tgt)
        if sp is not None:
            return sp
        return act


# ===================================================================== bots
class TitForTatBot(_Core):
    """Reciprocal farmer.  Farms with the shared planner and never raids (nor stops
    on, nor risks a lost move contest on) the land of a rival that has not raided
    it.  Every cell a rival takes (or tries to take) opens a grudge worth ~1.25x the
    bonus lost; it raids that rival preferentially until the grudge is repaid and
    forgives after a quiet spell.  Defends with timed shields, harder vs aggressors."""
    name = "nv_d_titfortat"
    GRUDGE_MULT = 1.25
    FORGIVE_AFTER = 14

    def __init__(self, seed=0):
        _Core.__init__(self, seed)
        self.grudge = [0.0] * 5
        self.last_hit = [-99] * 5

    def _on_raid(self, raider, victim, q, lvl, bonus):
        me = self.me
        if victim == me:
            self.grudge[raider] += self.GRUDGE_MULT * bonus + 2.0 * self.base[q]
            self.last_hit[raider] = self.t - 1
        elif raider == me:
            self.grudge[victim] -= bonus
            if self.grudge[victim] < 0:
                self.grudge[victim] = 0.0

    def _on_attempt(self, raider, q):
        # caught red-handed on my land: an attempted raid is still aggression
        self.grudge[raider] += 4.0 * self.base[q]
        self.last_hit[raider] = self.t - 1

    def _tick(self):
        for s in _RIVAL_SEATS:
            if self.grudge[s] > 0:
                if self.t - self.last_hit[s] > self.FORGIVE_AFTER:
                    self.grudge[s] = 0.0
                else:
                    self.grudge[s] *= 0.98

    def _raid_params(self, o, q, off, prog):
        if self.grudge[o] <= 0:
            return None
        s = max(1, 3 - prog) if self.upg[q] else 1
        return (1.25, 0.6, self._catch_prob(o, q, off, s))

    AVOID = False     # walking over innocent land is allowed; stopping there is not

    def _special(self, legal, act, rate, tgt):
        # On an innocent rival's land a lost move contest would count as a STAY and
        # take the cell: pick a move nobody else can contest.
        me = self.me
        p0 = self.pos[me]
        o = self.owner[p0]
        if not o or o == me or self.home[p0] or self.grudge[o] > 0:
            return None
        def contested(q):
            for a2, q2 in _NB[q]:
                oc = self.occ[q2]
                if oc and oc != me and not self.frz[oc]:
                    return True
            return False
        if act in ("NORTH", "SOUTH", "WEST", "EAST"):
            for a, q in _NB[p0]:
                if a == act and not contested(q):
                    return None
        best, bv = None, -1e9
        for a, q in _NB[p0]:
            if self.occ[q] or contested(q):
                continue
            oq = self.owner[q]
            v = (2.0 if oq in (0, me) else 0.0) - 0.1 * _MAN[q][tgt if tgt >= 0 else q]
            if v > bv:
                best, bv = a, v
        return best if best is not None else (act if act != "STAY" else None)

    def _avoid(self, blk):
        if not self.AVOID:
            return
        owner = self.owner
        me = self.me
        g = self.grudge
        home = self.home
        for q in range(_NC):
            o = owner[q]
            if o and o != me and not home[q] and g[o] <= 0:
                blk[q] = True

    def _lam_def(self, y):
        return 0.9 if self.grudge[y] > 0 else 0.5


class AntiLeaderBot(_Core):
    """Score-reconstructing balancer.  Rebuilds every bot's score each turn (income
    from the cells it owns plus raid bonuses inferred from ownership changes),
    projects it forward, and names the leading rival.  Raids are concentrated on
    the leader's most valuable reachable cells (high weight, its losses counted as
    my gains); other rivals are raided only when it is unusually cheap.  Shields
    mainly against the leader; others only when an upgraded cell is at stake."""
    name = "nv_d_antileader"
    LW = 1.25        # raid weight on the leader
    LL = 0.4         # how much the leader's losses count as my gain
    OW = 0.85        # raid weight on everybody else (level-1 cells only)

    def __init__(self, seed=0):
        _Core.__init__(self, seed)
        self.leader = 0

    def _tick(self):
        R = _T + 1 - self.t
        best, bs = 0, -1.0
        cur = -1.0
        for s in self.rivals():
            proj = self.score[s] + 0.6 * self.income[s] * R
            if s == self.leader:
                cur = proj
            if proj > bs:
                best, bs = s, proj
        if self.leader == 0 or bs > cur * 1.04 + 5:
            self.leader = best

    def _raid_params(self, o, q, off, prog):
        upg = self.upg[q]
        s = max(1, 3 - prog) if upg else 1
        pc = self._catch_prob(o, q, off, s)
        if o == self.leader:
            return (self.LW, self.LL, pc)
        if upg:
            return None
        return (self.OW, 0.0, pc)

    def _lam_def(self, y):
        return 1.0 if y == self.leader else 0.15

    def _shield_filter(self, y, q, lvl):
        return y == self.leader or lvl == 2 or self.base[q] >= 3


class ShieldMasterBot(_Core):
    """Defence-and-tempo specialist.  Learns, per rival, how often it stays to raid
    and how it shields, and tracks every shield cooldown from observed freezes.
    It shields only on the stay that would complete a take (the last stay on an
    upgraded cell), keeps its shield in reserve when upgraded land is threatened,
    upgrades its frontier, raids a rival only while that rival cannot shield, and
    baits reactive shielders by stepping onto their land and straight off again."""
    name = "nv_d_shieldmaster"
    LAM_DEF = 0.6
    UPG_HZ = 0.2      # an upgraded cell is held by timed shields

    def __init__(self, seed=0):
        _Core.__init__(self, seed)
        self.bait_from = -1

    def _window_open(self, o, off, s):
        for u in range(off, off + s):
            if self.can_shield_at(o, u):
                return False
        return True

    def _raid_params(self, o, q, off, prog):
        upg = self.upg[q]
        s = max(1, 3 - prog) if upg else 1
        if self._window_open(o, off, s):
            return (1.1, 0.3, 0.0)
        pr = self.p_resp(o, 2 if upg else 1)
        if upg:
            if pr < 0.25:
                return (1.0, 0.5, pr)
            return None
        if pr < 0.3:
            return (1.0, 0.5, pr)
        # reactive shielder: worth approaching for a bait (one extra step)
        return (0.75 * pr, 0.5, 0.0)

    def _reserve_cost(self, rate):
        # keep the shield for upgraded land when raiders are close to it
        me = self.me
        best = 0.0
        R = _T + 1 - self.t
        for q in range(_NC):
            if self.owner[q] != me or not self.upg[q] or self.home[q]:
                continue
            row = _MAN[q]
            for s in _RIVAL_SEATS:
                if s == me or self.pos[s] < 0 or self.frz[s]:
                    continue
                if 1 <= row[self.pos[s]] <= 2:
                    v = 0.35 * self.base[q] * 2 * min(R, 20)
                    if v > best:
                        best = v
        return best

    def _special(self, legal, act, rate, tgt):
        """Bait: on a rival's level-1 cell with no progress while that rival can shield
        and is a reactive shielder -> step to another of its cells (or off)."""
        me = self.me
        p0 = self.pos[me]
        o = self.owner[p0]
        if act != "STAY" or not o or o == me or self.home[p0] or self.upg[p0]:
            return None
        if self.my_prog != 0 or not self.can_shield_at(o, 0):
            return None
        R = _T + 1 - self.t
        if R <= 2:
            return None
        pr = self.p_resp(o, 1)
        if pr < 0.45:
            return None
        best, bv = None, -1.0
        for a, q in _NB[p0]:
            if self.occ[q]:
                continue
            oq = self.owner[q]
            if oq == o and not self.home[q]:
                v = 10.0 + self.base[q] * (2 if self.upg[q] else 1)
            elif oq == 0:
                v = 3.0 + self.base[q]
            elif oq == me:
                v = 2.0
            else:
                v = 0.0
            if v > bv:
                best, bv = a, v
        if best is None:
            return None
        self.bait_from = p0
        return best


BOTS = [TitForTatBot, AntiLeaderBot, ShieldMasterBot]

# Standalone entry point: the unchanged research policy receives only its public view.
_CONSOLIDATED_PLAYERS = {}
def act(state):
    seat = state.bot_id
    player = _CONSOLIDATED_PLAYERS.get(seat)
    if player is None:
        player = TitForTatBot(seed=seat * 7919)
        _CONSOLIDATED_PLAYERS[seat] = player
    return player.act(state)
