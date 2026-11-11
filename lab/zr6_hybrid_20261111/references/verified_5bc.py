"""
Novel adversarial opponent bots for Zone Rush (set B).

All three share one economic core (state reconstruction from the visible board, a
depth-3 job-sequence planner, shield-cooldown tracking from observed freezes,
priority-token schedule, contest-aware stepping and an EV-based shield defence) and
differ in the adversarial idea layered on top:

  nv_b_feint    zero-cost deceptive approach paths (keep a decoy and as much rival-
                visible goal mass consistent as possible), tie-break targets that a
                forecaster is least likely to call, raid feints that bait reactive
                shields into backfiring.
  nv_b_blocker  leader-focused spatial denial: takes and fortifies what the leader is
                about to want, parks on its routes, snipes its next steps with the token.
  nv_b_racer    forecasts every rival's destination, races only where it wins the
                arrival contest, otherwise works where nobody is heading; steals fresh
                level-1 cells when the owner cannot shield or is far away.

Standard library only; never imports anything from the repository.
"""
import random

_SEATS = (1, 2, 3, 4)
_MD = [[abs((a >> 3) - (b >> 3)) + abs((a & 7) - (b & 7)) for b in range(64)]
       for a in range(64)]
_NB = []
for _p in range(64):
    _r, _c = _p >> 3, _p & 7
    _l = []
    if _r > 0:
        _l.append(("NORTH", _p - 8))
    if _c < 7:
        _l.append(("EAST", _p + 1))
    if _r < 7:
        _l.append(("SOUTH", _p + 8))
    if _c > 0:
        _l.append(("WEST", _p - 1))
    _NB.append(tuple(_l))
# neighbours of p that reduce the distance to g
_RED = [[tuple(q for (_a, q) in _NB[_p] if _MD[q][_g] < _MD[_p][_g]) for _g in range(64)]
        for _p in range(64)]
# raid threat by distance from a mobile rival
_TH = [1.0, 0.75, 0.5, 0.32, 0.18, 0.09, 0.04] + [0.0] * 12
# forecast likelihood factors by transition age (0 = most recent)
_AWAY = (0.15, 0.25, 0.4, 0.55, 0.7)
_STAYO = (0.35, 0.5, 0.65, 0.8, 0.9)


class _Core(object):
    """Shared economic core; subclasses add the adversarial idea."""
    name = "nv_b_core"
    ALPHA = 0.34        # weight of damage dealt to a rival relative to own gain
    POOL = 22
    K1 = 8
    K2 = 5
    RHO0 = 0.5          # prior: a rival shields when someone stands on its land
    STAY0 = 0.8         # prior: a raider that arrives on level-1 land stays
    HOP_RISK = 0.45     # shield risk above which a raider hops instead of staying
    BAIT = False        # may step off rival land just to bait a shield
    PROT = 0.6
    KEEP = 0.8
    CLAIM_THR = 0.35    # discount of a fresh level-1 claim per unit of raid threat
    SHW = 1.0           # multiplier on shield-defence benefit
    AGG0 = 0.35         # prior raid aggression of a mobile rival
    CONF = 1.0          # strength of the forecast-conflict discount
    DYN = True          # margin-based rival weights instead of a flat ALPHA
    CLAIM_BONUS_SHARE = 1.0   # share of a neutral-cell bonus that a bare claim gets

    def __init__(self, seed=0):
        self.rng = random.Random(seed)
        self.t = 0
        self.me = 0
        self.base = None
        self.home = None
        self.prev = None
        self.pfrz = dict((s, False) for s in _SEATS)
        self.hist = dict((s, []) for s in _SEATS)
        self.streak = dict((s, 0) for s in _SEATS)
        self.mob = dict((s, 0.5) for s in _SEATS)
        self.last_shield = dict((s, -99) for s in _SEATS)
        self.sh_opp = dict((s, 0.0) for s in _SEATS)
        self.sh_hit = dict((s, 0.0) for s in _SEATS)
        self.arr_tot = dict((s, 0.0) for s in _SEATS)
        self.arr_stay = dict((s, 0.0) for s in _SEATS)
        self.raids = dict((s, 0) for s in _SEATS)
        self.score = dict((s, 0.0) for s in _SEATS)
        self.income = dict((s, 0.0) for s in _SEATS)
        self.ctime = [0] * 64
        self.tok = [0, 1, 2, 3]
        self.prog = 0
        self.last = "STAY"
        self.lam = 40.0
        self.target = None
        self.post = {}
        self.goal = {}
        self.stepp = {}
        self.riv = ()
        self.dyn_alpha = {}

    # ------------------------------------------------------------------ api
    def __call__(self, view):
        try:
            a = self.act(view)
        except Exception:
            a = "STAY"
        return a if a in view.legal_actions else "STAY"

    def act(self, view):
        self._observe(view)
        legal = view.legal_actions
        a = self._decide(view)
        if a not in legal:
            a = "STAY"
        self.last = a
        return a

    # ------------------------------------------------------------ observing
    def _observe(self, view):
        self.t += 1
        t = self.t
        me = view.bot_id
        self.me = me
        self.riv = tuple(s for s in _SEATS if s != me)
        own = [0] * 64
        upg = [False] * 64
        occ = [0] * 64
        first = self.base is None
        if first:
            base = [1] * 64
            home = [False] * 64
        pos = {}
        frz = {}
        p = 0
        for row in view.board:
            for cell in row:
                own[p] = cell.owner
                if cell.is_upgraded:
                    upg[p] = True
                o = cell.occupant
                if o:
                    occ[p] = o
                    pos[o] = p
                    frz[o] = bool(cell.is_frozen)
                if first:
                    base[p] = cell.base_points
                    home[p] = bool(cell.is_home)
                p += 1
        if first:
            self.base = base
            self.home = home
        prev = self.prev
        corner = {1: 0, 2: 7, 3: 63, 4: 56}
        for s in _SEATS:
            if s not in pos:
                pos[s] = prev[2][s] if prev is not None else corner[s]
                frz[s] = False
        # priority-token schedule: holder(t) = ((t - 1 + k) % 4) + 1
        ip = bool(view.is_priority_token)
        tk = [k for k in self.tok if ((((t - 1 + k) % 4) + 1) == me) == ip]
        if not tk:
            tk = [k for k in range(4) if ((((t - 1 + k) % 4) + 1) == me) == ip]
        self.tok = tk
        pfrz = dict((s, False) for s in _SEATS)
        if prev is not None:
            pown, pupg, ppos, pfrz = prev
            self._events(t, me, own, upg, pos, frz, pown, pupg, ppos, pfrz)
        for s in _SEATS:
            h = self.hist[s]
            h.append(pos[s])
            if len(h) > 7:
                del h[0]
        self.own, self.upg, self.occ, self.pos, self.frz = own, upg, occ, pos, frz
        self.pfrz = pfrz
        self.prev = (own, upg, pos, frz)

    def _events(self, t, me, own, upg, pos, frz, pown, pupg, ppos, pfrz):
        tp = t - 1
        base = self.base
        home = self.home
        moved = dict((s, pos[s] != ppos[s]) for s in _SEATS)
        newf = [s for s in _SEATS if frz[s] and not pfrz[s]]
        shs = set()
        if self.last == "SHIELD":
            shs.add(me)
        for j in newf:
            if j == me and me in shs:
                continue
            q = pos[j]
            o = own[q]
            if o and o != j and not pfrz[o] and tp - self.last_shield[o] > 4:
                shs.add(o)
            else:
                shs.add(j)
        # shield opportunities (someone stood on r's land while r could shield)
        for r in _SEATS:
            if r == me or pfrz[r] or tp - self.last_shield[r] <= 4:
                continue
            inv = False
            for j in _SEATS:
                if j == r or pfrz[j]:
                    continue
                q = ppos[j]
                if pown[q] == r and not home[q]:
                    inv = True
                    break
            if inv:
                self.sh_opp[r] += 1.0
                if r in shs:
                    self.sh_hit[r] += 1.0
        for s in shs:
            self.last_shield[s] = tp
        # does a raider that just arrived on level-1 land stay?
        for j in _SEATS:
            if j == me or pfrz[j]:
                continue
            h = self.hist[j]
            if len(h) < 2 or h[-1] == h[-2]:
                continue
            q = ppos[j]
            if pown[q] not in (0, j) and not home[q] and not pupg[q]:
                self.arr_tot[j] += 1.0
                if not moved[j]:
                    self.arr_stay[j] += 1.0
        # scores, ownership changes, raids
        inc = dict((s, 0.0) for s in _SEATS)
        for q in range(64):
            o = own[q]
            if o:
                inc[o] += base[q] * (2 if upg[q] else 1)
            po = pown[q]
            if po != o:
                self.ctime[q] = tp
                if po and o:
                    self.score[o] += 8 * base[q] * (2 if pupg[q] else 1)
                    self.raids[o] += 1
        for s in _SEATS:
            self.score[s] += inc[s]
            self.income[s] = inc[s]
            if moved[s] or s in newf:
                self.streak[s] = 0
            elif not pfrz[s]:
                self.streak[s] += 1
            self.mob[s] = 0.85 * self.mob[s] + (0.15 if moved[s] else 0.0)
        # own progress, replicating the engine
        P = pos[me]
        if moved[me] or me in newf:
            self.prog = 0
        elif pfrz[me]:
            pass
        elif self.last == "SHIELD":
            self.prog = 0
        else:
            o = pown[P]
            if o == me:
                if not pupg[P]:
                    self.prog += 1
                    if upg[P] or self.prog >= 3:
                        self.prog = 0
            elif o == 0:
                self.prog = 0
            elif home[P] or o in shs:
                pass
            else:
                self.prog += 1
                if own[P] == me:
                    self.prog = 0

    # -------------------------------------------------------------- helpers
    def _holder(self, k):
        off = self.tok[0] if self.tok else 0
        return ((k - 1 + off) % 4) + 1

    def _rank(self, s, k):
        return (s - self._holder(k)) % 4

    def _beats(self, a, b, q, k):
        o = self.own[q]
        if o == a:
            return True
        if o == b:
            return False
        return self._rank(a, k) < self._rank(b, k)

    def _frz_left(self, s):
        if not self.frz[s]:
            return 0
        return 1 if self.pfrz.get(s) else 2

    def _can_shield(self, s, k):
        if k < self.t + self._frz_left(s):
            return False
        return k - self.last_shield[s] > 4

    def _rho(self, r):
        return (self.sh_hit[r] + self.RHO0 * 2.5) / (self.sh_opp[r] + 2.5)

    def _pstay(self, r):
        return (self.arr_stay[r] + self.STAY0 * 3.0) / (self.arr_tot[r] + 3.0)

    def _aggr(self, r):
        a = self.AGG0 + 0.2 * self.raids[r]
        if a > 1.4:
            a = 1.4
        m = 0.15 + 2.0 * self.mob[r]
        if m > 1.0:
            m = 1.0
        return a * m

    def _alpha(self, r):
        if self.DYN:
            return self.dyn_alpha.get(r, self.ALPHA)
        return self.ALPHA

    def _update_alpha(self):
        """Marginal pairwise weights: d(expected pairwise wins)/d(damage to r) is the
        density of my projected final margin over r at zero; normalised against
        d/d(own score), which is the sum of those densities."""
        rem = 80 - self.t
        me = self.me
        mine = self.score[me] + self.income[me] * rem
        sig = 120.0 + 6.0 * rem
        ph = {}
        tot = 0.0
        for r in self.riv:
            z = (mine - (self.score[r] + self.income[r] * rem)) / sig
            v = 2.718281828 ** (-0.5 * z * z) + 0.05
            ph[r] = v
            tot += v
        da = {}
        for r in self.riv:
            a = ph[r] / tot
            da[r] = 0.1 if a < 0.1 else (0.8 if a > 0.8 else a)
        self.dyn_alpha = da

    def _value_for(self, s, g):
        """How attractive cell g looks for seat s (naive model, also used to deceive)."""
        o = self.own[g]
        b = self.base[g]
        if o == 0:
            return float(b)
        if o == s:
            return 0.0 if self.upg[g] else 0.6 * b
        if self.home[g]:
            return 0.0
        if self.upg[g]:
            return 0.6 * b
        return 2.5 * b

    # ------------------------------------------------------------- forecast
    def _forecast(self):
        own, upg, home, base, occ = self.own, self.upg, self.home, self.base, self.occ
        self.post = {}
        self.goal = {}
        self.stepp = {}
        for r in self.riv:
            pr = self.pos[r]
            h = self.hist[r]
            trans = []
            n = len(h)
            for i in range(n - 1, max(0, n - 6), -1):
                trans.append((h[i - 1], h[i]))      # most recent first
            MDr = _MD[pr]
            post = [0.0] * 64
            tot = 0.0
            bestg, bestw = pr, -1.0
            for g in range(64):
                o = own[g]
                b = base[g]
                if o == 0:
                    v = float(b)
                elif o == r:
                    if upg[g]:
                        continue
                    v = 0.6 * b
                elif home[g]:
                    continue
                elif upg[g]:
                    v = 0.6 * b
                else:
                    v = 2.5 * b
                oc = occ[g]
                if oc and oc != r:
                    v *= 0.3
                w = v / (MDr[g] + 1.0)
                age = 0
                for (a, c) in trans:
                    if a == c:
                        if g != a:
                            w *= _STAYO[age]
                    elif _MD[c][g] >= _MD[a][g]:
                        w *= _AWAY[age]
                    age += 1
                post[g] = w
                tot += w
                if w > bestw:
                    bestw, bestg = w, g
            if tot > 0:
                inv = 1.0 / tot
                for g in range(64):
                    if post[g]:
                        post[g] *= inv
            self.post[r] = post
            self.goal[r] = bestg
            sp = {}
            if not self.frz[r]:
                for g in range(64):
                    m = post[g]
                    if m < 0.003 or g == pr:
                        continue
                    red = [q for q in _RED[pr][g] if not occ[q]]
                    if not red:
                        continue
                    sh = m / len(red)
                    for q in red:
                        sp[q] = sp.get(q, 0.0) + sh
            self.stepp[r] = sp

    # ----------------------------------------------------------------- jobs
    def _prot(self, b, thr, rem0):
        a = self.ALPHA
        return self.PROT * thr * (b * 0.5 * rem0 * (1.0 + a) + a * 8.0 * b)

    def _conflict(self, p, de):
        f = 1.0
        pos = self.pos
        for r in self.riv:
            m = self.post[r][p]
            if m < 0.02:
                continue
            e = _MD[pos[r]][p] + self._frz_left(r)
            if e < de - 0.01:
                lo = 0.9
            elif e < de + 0.01:
                lo = 0.5
            else:
                lo = 0.15
            m *= 1.5
            if m > 1.0:
                m = 1.0
            f *= 1.0 - m * lo * self.CONF
        return f

    def _bonus_neutral(self, p, de, f):
        return 0.0

    def _bonus_own(self, p, de):
        return 0.0

    def _bonus_raid(self, p, o, de):
        return 0.0

    def _fresh(self, p, o):
        return 1.0

    def _jobs(self):
        me, t = self.me, self.t
        own, upg, home, base, occ, pos, frz = (self.own, self.upg, self.home, self.base,
                                               self.occ, self.pos, self.frz)
        P = pos[me]
        MDP = _MD[P]
        rem0 = 81 - t
        riv = self.riv
        aggr = dict((r, self._aggr(r)) for r in riv)
        alpha = dict((r, self._alpha(r)) for r in riv)
        rho = dict((r, self._rho(r)) for r in riv)
        rpos = [(aggr[r], _MD[pos[r]]) for r in riv]
        jobs = []
        for p in range(64):
            o = own[p]
            if o and o != me and home[p]:
                continue
            if o == me and upg[p]:
                continue
            b = base[p]
            d = MDP[p]
            oc = occ[p]
            wait = 0.0
            if oc and oc != me:
                if frz[oc]:
                    wait = 1.0 + self._frz_left(oc)
                elif self.streak[oc]:
                    wait = 2.5
                else:
                    wait = 1.5
            de = d + wait
            thr = 0.0
            for (ag, mr) in rpos:
                thr += ag * _TH[mr[p]]
            if thr > 0.9:
                thr = 0.9
            if o == 0:
                f = self._conflict(p, de)
                if f <= 0.05:
                    continue
                C1 = self._bonus_neutral(p, de, f)
                C0 = C1 * self.CLAIM_BONUS_SHARE
                jobs.append((p, 1.0, C0, b * f * (1.0 - self.CLAIM_THR * thr), 0.0, 0.0, 0.0, wait, 0))
                prot = self._prot(b, thr, rem0)
                jobs.append((p, 4.0, C1 + prot, b * f, 0.0, b * f, 3.0, wait, 1))
            elif o == me:
                s = 3.0 - (self.prog if p == P else 0)
                if s < 1.0:
                    s = 1.0
                prot = 0.0 if home[p] else self._prot(b, thr, rem0)
                C = prot + self._bonus_own(p, de)
                jobs.append((p, s, C, float(b), s - 1.0, 0.0, 0.0, wait, 2))
            else:
                if oc == o and self.streak[o] > 0 and not upg[p]:
                    continue        # owner is sitting on it, upgrading
                kst = t + int(de + 0.5)
                a = alpha[o]
                if not upg[p]:
                    risk = rho[o] if self._can_shield(o, kst) else 0.0
                    ex = 3.0 * risk
                    back = 1.0 - 0.3 * aggr[o] * _TH[_MD[pos[o]][p]]
                    C = 8.0 * b * self._fresh(p, o) + self._bonus_raid(p, o, de)
                    w1 = b * (1.0 + a) * back
                    jobs.append((p, 1.0 + ex, C, w1, ex, 0.0, 0.0, wait, 3))
                    prot = self._prot(b, thr, rem0)
                    jobs.append((p, 4.0 + ex, C + prot, w1, ex, float(b), ex + 3.0, wait, 4))
                else:
                    pno = 1.0
                    for k in range(3):
                        if self._can_shield(o, kst + k):
                            pno *= (1.0 - rho[o])
                    if pno < 0.25:
                        continue
                    C = 16.0 * b * pno + self._bonus_raid(p, o, de)
                    w1 = b * (1.0 + 2.0 * a) * pno
                    ex = 3.0 * (1.0 - pno)
                    jobs.append((p, 3.0 + ex, C, w1, 2.0 + ex, 0.0, 0.0, wait, 5))
        return jobs

    # --------------------------------------------------------------- search
    def _search(self, jobs):
        t = self.t
        P = self.pos[self.me]
        MDP = _MD[P]
        sc = []
        for j in jobs:
            de = MDP[j[0]] + j[7]
            ta = t + de - 1.0
            st = j[1]
            if ta + st > 80.5:
                continue
            x1 = 80.0 - ta - j[4]
            x2 = 80.0 - ta - j[6]
            g = j[2] + (j[3] * x1 if x1 > 0 else 0.0) + (j[5] * x2 if x2 > 0 else 0.0)
            if g <= 0:
                continue
            sc.append((g / (de + st), g, ta + st, j))
        if not sc:
            return []
        sc.sort(key=lambda x: -x[0])
        pool = sc[:self.POOL]
        out = []
        for (r1, g1, te1, j1) in pool[:self.K1]:
            p1 = j1[0]
            M1 = _MD[p1]
            lvl2 = []
            for (_r, _g, _te, j2) in pool:
                p2 = j2[0]
                if p2 == p1:
                    continue
                ta2 = te1 + M1[p2] + 0.5 * j2[7]
                st2 = j2[1]
                if ta2 + st2 > 80.5:
                    continue
                x1 = 80.0 - ta2 - j2[4]
                x2 = 80.0 - ta2 - j2[6]
                g2 = j2[2] + (j2[3] * x1 if x1 > 0 else 0.0) + (j2[5] * x2 if x2 > 0 else 0.0)
                if g2 <= 0:
                    continue
                te2 = ta2 + st2
                lvl2.append(((g1 + g2) / (te2 - t + 1.0), g2, te2, j2))
            if not lvl2:
                out.append((r1, j1))
                continue
            lvl2.sort(key=lambda x: -x[0])
            best1 = -1.0
            for (r2, g2, te2, j2) in lvl2[:self.K2]:
                p2 = j2[0]
                M2 = _MD[p2]
                b3 = -1.0
                g12 = g1 + g2
                for (_r, _g, _te, j3) in pool:
                    p3 = j3[0]
                    if p3 == p1 or p3 == p2:
                        continue
                    ta3 = te2 + M2[p3] + 0.5 * j3[7]
                    st3 = j3[1]
                    if ta3 + st3 > 80.5:
                        continue
                    x1 = 80.0 - ta3 - j3[4]
                    x2 = 80.0 - ta3 - j3[6]
                    g3 = j3[2] + (j3[3] * x1 if x1 > 0 else 0.0) + (j3[5] * x2 if x2 > 0 else 0.0)
                    if g3 <= 0:
                        continue
                    rr = (g12 + g3) / (ta3 + st3 - t + 1.0)
                    if rr > b3:
                        b3 = rr
                if b3 < 0:
                    b3 = r2
                if b3 > best1:
                    best1 = b3
            out.append((best1, j1))
        out.sort(key=lambda x: -x[0])
        return out

    def _pick(self, best):
        top = best[0][0]
        if self.target is not None:
            for (r, j) in best:
                if j[0] == self.target and r >= self.KEEP * top:
                    return j
        return best[0][1]

    # -------------------------------------------------------------- defence
    def _defend(self, legal):
        if "SHIELD" not in legal:
            return False
        me, t = self.me, self.t
        rem = 81 - t
        lam = self.lam
        cands = []
        for r in self.riv:
            if self.frz[r]:
                continue
            q = self.pos[r]
            if self.own[q] != me:
                continue
            b = self.base[q]
            st = self.streak[r]
            a = self._alpha(r)
            if self.home[q]:
                ps = 0.1 if st == 0 else 0.4
                ben = 3.0 * lam * a
            elif not self.upg[q]:
                ps = self._pstay(r)
                if rem <= 3:
                    ben = b * rem + a * (8.0 * b + b * rem) + a * 3.0 * lam
                else:
                    rr = rem - 3
                    ben = ((1.0 + a) * 3.0 * b + a * 3.0 * lam +
                           0.15 * (b * rr + a * (8.0 * b + b * rr)))
            else:
                ps = 0.9 if st >= 2 else (0.7 if st == 1 else 0.4)
                if st >= 2 or rem <= 3 - st:
                    ben = 2.0 * b * rem + a * (16.0 * b + b * rem) + a * 3.0 * lam
                else:
                    ben = a * (st + 3.0) * lam * 0.5
            ben *= self._shield_weight(r) * self.SHW
            cands.append((ps, ben))
        if not cands:
            return False
        pn = 1.0
        gain = 0.0
        for ps, ben in cands:
            gain += ps * ben
            pn *= (1.0 - ps)
        left = 80 - t
        cost = lam * (1.0 + 0.5 * self.prog) + pn * lam * min(2, left)
        return gain > cost

    def _shield_weight(self, r):
        return 1.0

    # --------------------------------------------------------------- acting
    def _decide(self, view):
        legal = view.legal_actions
        if len(legal) == 1:
            return legal[0]
        self._forecast()
        self._update_alpha()
        self._pre()
        jobs = self._jobs()
        best = self._search(jobs)
        if best:
            self.lam = 0.5 * self.lam + 0.5 * max(best[0][0], 1.0)
        if self._defend(legal):
            return "SHIELD"
        if not best:
            return "STAY"
        job = self._pick(best)
        X = job[0]
        self.target = X
        P = self.pos[self.me]
        if X == P:
            return self._work(job, legal)
        return self._move(X, job, legal)

    def _pre(self):
        pass

    def _work(self, job, legal):
        me, t = self.me, self.t
        P = self.pos[me]
        o = self.own[P]
        if o and o != me and not self.home[P] and self._can_shield(o, t):
            risk = self._rho(o)
            if risk >= self.HOP_RISK:
                a = self._hop(P, o, legal)
                if a is not None:
                    return a
        return "STAY"

    def _hop(self, P, o, legal):
        best, ba = -1.0, None
        for (a, q) in _NB[P]:
            if a not in legal or self.occ[q]:
                continue
            if self.own[q] == o and not self.home[q]:
                v = self.base[q] * (0.5 if self.upg[q] else 2.0)
            elif self.BAIT:
                v = 0.1
            else:
                continue
            v += 0.01 * self.rng.random()
            if v > best:
                best, ba = v, a
        return ba

    def _move(self, X, job, legal):
        me, t = self.me, self.t
        P = self.pos[me]
        dP = _MD[P][X]
        opts = []
        blocked_wait = 9.0
        for (a, q) in _NB[P]:
            if a not in legal:
                continue
            dq = _MD[q][X]
            if self.occ[q]:
                if dq < dP:
                    oc = self.occ[q]
                    if self.frz[oc]:
                        w = self._frz_left(oc)
                    elif self.streak[oc]:
                        w = 2.5
                    else:
                        w = 1.0
                    if w < blocked_wait:
                        blocked_wait = w
                continue
            loss = 0.0
            for r in self.riv:
                if self.frz[r] or _MD[self.pos[r]][q] != 1:
                    continue
                if self._beats(me, r, q, t):
                    continue
                loss += self.stepp[r].get(q, 0.0)
            if loss > 1.0:
                loss = 1.0
            sc = dq + 1.2 * loss + self._step_bias(P, q, X) + 0.01 * self.rng.random()
            opts.append((sc, a, q, dq))
        if not opts:
            return "STAY"
        opts.sort()
        sc, a, q, dq = opts[0]
        if dq >= dP and blocked_wait <= 1.5:
            return "STAY"
        return a

    def _step_bias(self, P, q, X):
        return 0.0


# =============================================================================
class FeintBot(_Core):
    """Deceptive mover. It picks a real target (the less obvious one when plans tie)
    and walks a zero-cost shortest path that also approaches a valuable decoy,
    so a goal-inferring rival reads the decoy until the last branch step. Paths run
    over shield-happy rivals' land to bait backfires, and raids are feinted (hop
    instead of stay) while the owner can shield. Decoys and patterns are randomised."""
    name = "nv_b_feint"
    HOP_RISK = 0.3
    BAIT = True

    def __init__(self, seed=0):
        _Core.__init__(self, seed)
        self.decoy = None
        self.decoy_for = None
        self.honest = False
        self.mix = 0.3
        self.slack = 0.975 + 0.015 * self.rng.random()
        self._av_t = -1
        self._av = None
        self._avtot = 1.0

    def _apparent(self, P, g):
        v = self._value_for(self.me, g)
        if v <= 0:
            return 0.0
        return v / (_MD[P][g] + 1.0)

    def _avmap(self):
        if self._av_t != self.t:
            P = self.pos[self.me]
            av = [self._apparent(P, g) for g in range(64)]
            self._av = av
            self._avtot = sum(av) or 1.0
            self._av_t = self.t
        return self._av

    def _shadow(self, P, X, av):
        """1.0 when X is the most attractive cell a straight approach is consistent with;
        lower when a better-looking cell lies beyond X on the same monotone paths."""
        dX = _MD[P][X]
        best = av[X]
        MP = _MD[P]
        MX = _MD[X]
        for g in range(64):
            if av[g] > best and MP[g] == dX + MX[g]:
                best = av[g]
        return av[X] / best if best > 0 else 1.0

    def _pick(self, best):
        top = best[0][0]
        P = self.pos[self.me]
        if self.target is not None:
            for (r, j) in best:
                if j[0] == self.target and r >= self.KEEP * top:
                    return j
        near = [(r, j) for (r, j) in best[:6] if r >= self.slack * top]
        if len(near) <= 1:
            return best[0][1]
        # among (near-)tied plans take the target a forecaster is least likely to call
        av = self._avmap()
        mx = max(av) or 1.0
        bestw, bj = -1.0, best[0][1]
        for (r, j) in near:
            sh = self._shadow(P, j[0], av) if j[0] != P else 1.0
            pred = 0.5 * sh + 0.5 * av[j[0]] / mx
            w = (r / top) * (1.03 - 0.06 * pred) * (0.99 + 0.02 * self.rng.random())
            if w > bestw:
                bestw, bj = w, j
        return bj

    def _choose_decoy(self, P, X):
        dX = _MD[P][X]
        av = self._avmap()
        cands = []
        for g in range(64):
            if g == X or _MD[X][g] < 2:
                continue
            a = av[g]
            if a <= 0:
                continue
            ov = (dX + _MD[P][g] - _MD[X][g]) * 0.5
            if ov < 1:
                continue
            s = a * ((ov + 0.5) / (dX + 0.5)) ** 2
            cands.append((s, g))
        if not cands:
            return None
        cands.sort(reverse=True)
        top = cands[:3]
        tot = sum(s for s, _ in top)
        x = self.rng.random() * tot
        for s, g in top:
            x -= s
            if x <= 0:
                return g
        return top[0][1]

    def _move(self, X, job, legal):
        P = self.pos[self.me]
        if X != self.decoy_for or (self.decoy is not None and self.rng.random() < 0.1):
            self.decoy_for = X
            self.honest = self.rng.random() < 0.12
            self.decoy = None if self.honest else self._choose_decoy(P, X)
            self.mix = 0.2 + 0.3 * self.rng.random()
        return _Core._move(self, X, job, legal)

    def _step_bias(self, P, q, X):
        bias = 0.0
        if not self.honest and _MD[P][X] >= 2:
            # keep as much alternative goal mass consistent as possible (zero-cost: the
            # bias never outweighs a distance step)
            av = self._avmap()
            MP = _MD[P]
            Mq = _MD[q]
            keep = 0.0
            for g in range(64):
                a = av[g]
                if a > 0 and g != X and Mq[g] < MP[g]:
                    keep += a
            bias -= self.mix * keep / self._avtot
            D = self.decoy
            if D is not None and Mq[D] < MP[D]:
                bias -= 0.25
        o = self.own[q]
        if o and o != self.me and not self.home[q] and self._can_shield(o, self.t):
            bias -= 0.12 * self._rho(o)
        return bias


# =============================================================================
class BlockerBot(_Core):
    """Spatial-control bot aimed at the strongest rival (projected final score). It
    weights the leader's losses above the marginal pairwise weight, claims-and-upgrades
    the cells the leader is about to want, parks on cells along the leader's forecast
    route, and snipes the leader's next step whenever the rotating priority token (or
    ownership) wins the simultaneous-entry contest; it shields the leader eagerly."""
    name = "nv_b_blocker"
    LEADER_BUMP = 0.15  # extra weight on the leader's losses beyond the marginal weight
    DENY = 0.4
    CLAIM_BONUS_SHARE = 0.0   # deny by taking AND fortifying, never by bare claims

    def __init__(self, seed=0):
        _Core.__init__(self, seed)
        self.leader = None

    def _pre(self):
        rem = 80 - self.t
        best, L = -1.0, None
        for r in self.riv:
            v = self.score[r] + self.income[r] * rem
            if r == self.leader:
                v *= 1.06
            if v > best:
                best, L = v, r
        self.leader = L

    def _alpha(self, r):
        a = self.dyn_alpha.get(r, self.ALPHA)
        if r == self.leader:
            a += self.LEADER_BUMP
        return a

    def _shield_weight(self, r):
        return 1.3 if r == self.leader else 1.0

    def _lead_info(self):
        L = self.leader
        return L, self.pos[L], self.goal.get(L, self.pos[L])

    def _bonus_neutral(self, p, de, f):
        L, pl, G = self._lead_info()
        dl = _MD[pl][p] + self._frz_left(L)
        bonus = 0.0
        rem = 80.0 - self.t - de
        if rem <= 0:
            return 0.0
        b = self.base[p]
        if dl <= 5 and de <= dl + 0.01:
            pL = self.post[L][p] * 2.0 + 0.6 * _TH[dl]
            if pL > 1.0:
                pL = 1.0
            bonus += self._alpha(L) * b * rem * pL * self.DENY
        bonus += self._route_bonus(p, de, pl, G)
        return bonus

    def _route_bonus(self, p, de, pl, G):
        L = self.leader
        dL = _MD[pl][p]
        if dL < 1 or dL > 3 or de > dL + 0.01:
            return 0.0
        if _MD[pl][p] + _MD[p][G] != _MD[pl][G]:
            return 0.0
        m = self.post[L][G]
        straight = (pl >> 3) == (G >> 3) or (pl & 7) == (G & 7)
        return self._alpha(L) * self.lam * (1.5 if straight else 0.6) * m

    def _bonus_own(self, p, de):
        L, pl, G = self._lead_info()
        bonus = 0.0
        if p == self.pos[self.me]:
            # parking: the leader wants this cell (raid) or must pass it
            m = self.post[L][p]
            if _MD[pl][p] <= 2:
                bonus += self._alpha(L) * self.lam * (0.5 + 2.0 * m)
        bonus += self._route_bonus(p, de, pl, G)
        return bonus

    def _bonus_raid(self, p, o, de):
        if o != self.leader:
            return 0.0
        # raiding the leader's cells next to its expansion front also denies it
        return 2.0 * self.base[p]

    def _jobs(self):
        jobs = _Core._jobs(self)
        # snipe: a free neighbour the leader is about to step into, while we win the contest
        L = self.leader
        if L is None or self.frz[L]:
            return jobs
        me, t = self.me, self.t
        P = self.pos[me]
        sp = self.stepp.get(L, {})
        extra = []
        for (a, q) in _NB[P]:
            m = sp.get(q, 0.0)
            if m < 0.3 or self.occ[q] or not self._beats(me, L, q, t):
                continue
            o = self.own[q]
            if o == 0 or o == L or o == me:
                b = self.base[q]
                bonus = self._alpha(L) * self.lam * 1.5 * m
                if o == 0:
                    extra.append((q, 1.0, bonus, float(b), 0.0, 0.0, 0.0, 0.0, 6))
                elif o == L and not self.home[q] and not self.upg[q]:
                    extra.append((q, 1.0, bonus + 8.0 * b, b * 1.8, 0.0, 0.0, 0.0, 0.0, 6))
                else:
                    extra.append((q, 1.0, bonus, 0.0, 0.0, 0.0, 0.0, 0.0, 6))
        return jobs + extra

    def _step_bias(self, P, q, X):
        L = self.leader
        if L is None:
            return 0.0
        m = self.stepp.get(L, {}).get(q, 0.0)
        if m > 0.2 and self._beats(self.me, L, q, self.t):
            return -0.3 * m
        return 0.0


# =============================================================================
class RacerBot(_Core):
    """Forecasting racer. It infers each rival's destination from its recent steps
    and the board, races only for cells where it arrives first or wins the arrival
    contest (ownership / token schedule), and otherwise prefers work nobody is heading
    for. It steals freshly claimed level-1 cells whose owner is far away or is on
    shield cooldown (cooldowns reconstructed from observed freezes)."""
    name = "nv_b_racer"
    R_FIRST = 0.15
    R_TIEWIN = 0.25

    def _conflict(self, p, de):
        f = 1.0
        t = self.t
        pos = self.pos
        me = self.me
        for r in self.riv:
            m = self.post[r][p]
            if m < 0.015:
                continue
            e = _MD[pos[r]][p] + self._frz_left(r)
            if de < e - 0.01:
                lo = self.R_FIRST          # we arrive first; it may still raid our claim
            elif de < e + 0.01:
                k = t + int(de + 0.5) - 1  # simultaneous entry: ownership / token decides
                lo = self.R_TIEWIN if self._beats(me, r, p, k) else 0.9
            else:
                lo = 0.85
            m *= 1.6
            if m > 1.0:
                m = 1.0
            f *= 1.0 - m * lo
        return f

    def _race_bonus(self, p, de):
        bonus = 0.0
        t = self.t
        for r in self.riv:
            m = self.post[r][p]
            if m < 0.1:
                continue
            e = _MD[self.pos[r]][p] + self._frz_left(r)
            win = de < e - 0.01 or (de < e + 0.01 and
                                     self._beats(self.me, r, p, t + int(de + 0.5) - 1))
            if win:
                bonus += self._alpha(r) * self.lam * m * min(e, 3.0) * 0.4
        return bonus

    def _bonus_neutral(self, p, de, f):
        return self._race_bonus(p, de)

    def _bonus_raid(self, p, o, de):
        return self._race_bonus(p, de)

    def _fresh(self, p, o):
        f = 1.0
        if self.t - self.ctime[p] <= 6:
            f += 0.15
        do = _MD[self.pos[o]][p]
        if do >= 4:
            f += 0.1
        if not self._can_shield(o, self.t + _MD[self.pos[self.me]][p]):
            f += 0.15
        return f


BOTS = [FeintBot, BlockerBot, RacerBot]



class AdaptiveDefenseBot(BlockerBot):
    """Seat-local public outcome learning, reset with the match namespace."""
    AD_HALF_LIFE = 32.0
    AD_MIN_RAW = 3
    AD_MIN_MASS = 2.0
    AD_FINE_PRIOR = 0.5
    AD_PHASE2_MIN_RAW = 2
    AD_PHASE2_MIN_MASS = 1.3
    AD_SPLIT_MIN_RAW = 2
    AD_SPLIT_MIN_MASS = 1.3
    AD_BASE_PRIOR = 0.5

    def __init__(self, seed=0):
        BlockerBot.__init__(self, seed)
        self.ad_profiles = {}
        self.ad_work_run = dict((r, 0) for r in _SEATS)
        self.ad_work_known = dict((r, True) for r in _SEATS)
        self.ad_ready = False
        self.ad_predictions = {}
        self.ad_diagnostics = dict(identified=0, censored=0, forced=0, resyncs=0,
                                  coarse_predictions=0, fine_predictions=0, prior_predictions=0)

    def __call__(self, view):
        # Exceptions remain visible to qualification; no silent fallback here.
        return self.act(view)

    def _observe(self, view):
        BlockerBot._observe(self, view)
        self.ad_ready = "SHIELD" in view.legal_actions

    def _ad_context(self, r, own, upg, pos, frz, ready):
        p = pos[r]
        if frz[r] or own[p] != self.me or not upg[p] or self.home[p]:
            return None
        phase = self.ad_work_run[r] if self.ad_work_known[r] else "unknown"
        free = sum(not any(q == pos[s] for s in _SEATS) for _, q in _NB[p])
        opportunity = any(s != r and not frz[s] and own[pos[s]] == r for s in _SEATS)
        return (r, phase, bool(ready)), (r, phase, bool(ready), min(2, free), opportunity)

    def _ad_profile(self, key, t):
        value = self.ad_profiles.get(key)
        if value is None:
            value = [0.0, 0.0, 0.0, 0.0, 0, 0, t]  # S/M/Q/A; raw total; raw S/Q; clock.
            self.ad_profiles[key] = value
        dt = max(0, t - value[6])
        decay = 0.5 ** (dt / self.AD_HALF_LIFE)
        for i in range(4):
            value[i] *= decay
        value[6] = t
        return value

    def _ad_record(self, keys, label, t):
        for key in keys:
            value = self._ad_profile(key, t)
            value["SMQA".index(label)] += 1.0
            value[4] += 1
            if label in "SQ":
                value[5] += 1

    def _ad_estimate(self, keys, prior_s=None):
        phase = keys[0][1]
        if prior_s is None:
            prior_s = 0.9 if phase == 2 else (0.7 if phase == 1 else 0.4)
        prior_m = 0.5 * (1.0 - prior_s)
        prior_q = 0.5 * (1.0 - prior_s)
        weight = self.AD_BASE_PRIOR
        bs, bm, bq = weight * prior_s, weight * prior_m, weight * prior_q
        split_prior = prior_s / (prior_s + prior_q)
        minimum_raw = self.AD_PHASE2_MIN_RAW if phase == 2 else self.AD_MIN_RAW
        minimum_mass = self.AD_PHASE2_MIN_MASS if phase == 2 else self.AD_MIN_MASS
        coarse = self._ad_profile(keys[0], self.t)
        if coarse[4] < minimum_raw or sum(coarse[:4]) < minimum_mass:
            return None, "prior"
        s, m, q, a = coarse[:4]
        # A means stationary but S/Q censored; it is NOT discarded movement data.
        pm = (m + bm) / (s + m + q + a + weight)
        split_ok = coarse[5] >= self.AD_SPLIT_MIN_RAW and s + q >= self.AD_SPLIT_MIN_MASS
        ps_given_stationary = (s + bs) / (s + q + bs + bq) if split_ok else split_prior
        fine = self._ad_profile(keys[1], self.t)
        source = "coarse"
        if fine[4] >= minimum_raw and sum(fine[:4]) >= minimum_mass:
            fs, fm, fq, fa = fine[:4]
            # Leave this fine context out of its pooled prior: no self-data reuse.
            os, om, oq, oa = (max(0.0, total - part) for total, part in zip((s,m,q,a),(fs,fm,fq,fa)))
            pooled_m = (om + bm) / (os + om + oq + oa + weight)
            outside_split_ok = coarse[5] - fine[5] >= self.AD_SPLIT_MIN_RAW and os + oq >= self.AD_SPLIT_MIN_MASS
            pooled_s = (os + bs) / (os + oq + bs + bq) if outside_split_ok else split_prior
            strength = self.AD_FINE_PRIOR
            pm = (fm + strength * pooled_m) / (fs + fm + fq + fa + strength)
            split_strength = strength * (1.0 - pooled_m)
            fine_split_ok = fine[5] >= self.AD_SPLIT_MIN_RAW and fs + fq >= self.AD_SPLIT_MIN_MASS
            ps_given_stationary = (fs + split_strength * pooled_s) / (fs + fq + split_strength) if fine_split_ok else pooled_s
            source = "fine"
        return ((1.0 - pm) * ps_given_stationary, pm, (1.0 - pm) * (1.0 - ps_given_stationary)), source

    def _adaptive_distribution(self, r):
        cached = self.ad_predictions.get(r)
        if cached is not None:
            return tuple(cached['probabilities'])
        keys = self._ad_context(r, self.own, self.upg, self.pos, self.frz, self.ad_ready)
        st = self.streak[r]
        ps = 0.9 if st >= 2 else (0.7 if st == 1 else 0.4)
        distribution, source = self._ad_estimate(keys, ps) if keys else (None, "prior")
        if distribution is None:
            distribution = (ps, 0.5 * (1.0 - ps), 0.5 * (1.0 - ps))
        # A successful displacement is impossible when every adjacent cell is closed.
        if not any(not self.occ[q] for _, q in _NB[self.pos[r]]):
            s, _, q = distribution
            distribution = (s, 0.0, 1.0 - s) if source == "prior" else (s / (s + q), 0.0, q / (s + q))
        self.ad_diagnostics[source + '_predictions'] += 1
        self.ad_predictions[r] = dict(probabilities=list(distribution), source=source,
                                     context=keys, work_run=self.ad_work_run[r],
                                     work_known=self.ad_work_known[r])
        return distribution

    def _events(self, t, me, own, upg, pos, frz, pown, pupg, ppos, pfrz):
        moved = dict((s, pos[s] != ppos[s]) for s in _SEATS)
        contexts = dict((r, self._ad_context(r, pown, pupg, ppos, pfrz, self.ad_ready)) for r in _SEATS if r != me)
        masks = self._public_shield_masks(me, own, upg, pos, frz, pown, pupg, ppos, pfrz, moved)
        if not masks:
            self.ad_diagnostics['resyncs'] += 1
        for r in _SEATS:
            if r == me:
                continue
            labels = ({'M'} if moved[r] else set('Q' if mask & (1 << (r-1)) else 'S' for mask in masks)) if masks else set()
            label = next(iter(labels)) if len(labels) == 1 else None
            if pfrz[r]:
                self.ad_diagnostics['forced'] += 1
            elif contexts[r] is not None:
                if label is None:
                    self.ad_diagnostics['censored'] += 1
                    if labels == {'S', 'Q'}:
                        self._ad_record(contexts[r], 'A', t-1)
                else:
                    self._ad_record(contexts[r], label, t-1)
                    self.ad_diagnostics['identified'] += 1
            p = pos[r]
            fresh_freeze = frz[r] and not pfrz[r]
            if moved[r] or fresh_freeze or label == 'Q' or own[p] != pown[p] or upg[p] != pupg[p]:
                self.ad_work_run[r], self.ad_work_known[r] = 0, True
            elif pfrz[r]:
                pass
            elif own[p] in (0, r) or not upg[p] or self.home[p]:
                self.ad_work_run[r], self.ad_work_known[r] = 0, True
            elif label == 'S' and not frz[r]:
                self.ad_work_run[r] = min(2, self.ad_work_run[r] + 1)
                if self.ad_work_run[r] == 2:
                    self.ad_work_known[r] = True
            else:
                # This resets a certified-run lower bound, NOT actual hidden progress.
                self.ad_work_run[r], self.ad_work_known[r] = 0, False
        BlockerBot._events(self, t, me, own, upg, pos, frz, pown, pupg, ppos, pfrz)

    def _forecast(self):
        BlockerBot._forecast(self)
        self.ad_predictions = {}
        for r in self.riv:
            if self._ad_context(r, self.own, self.upg, self.pos, self.frz, self.ad_ready) is None:
                continue
            _, pm, _ = self._adaptive_distribution(r)
            if self.ad_predictions[r]["source"] == "prior":
                continue  # Preserve the established forecast exactly before learning.
            weights = self.stepp[r]
            total = sum(weights.values())
            if total > 0:
                self.stepp[r] = dict((q, weight * pm / total) for q, weight in weights.items())
            else:
                exits = [q for _, q in _NB[self.pos[r]] if not self.occ[q]]
                self.stepp[r] = dict((q, pm / len(exits)) for q in exits) if exits else {}

    def _public_shield_masks(self, me, own, upg, pos, frz,
                                 pown, pupg, ppos, pfrz, moved):
            # Enumerate public transition explanations, not hidden actions from a tape.
            # A stationary, unfrozen non-shielder is an effective STAY, including
            # blocked intended moves. Successful movers and shielders cannot be caught.
            ownbit = 1 << (me - 1)
            required = 0  # No private acceptance acknowledgement exists.
            forbidden = 0 if self.last == "SHIELD" else ownbit
            for s in _SEATS:
                if moved[s] or pfrz[s]:
                    forbidden |= 1 << (s - 1)
            valid = []
            for mask in range(16):
                if mask & forbidden or mask & required != required:
                    continue
                shielders = [s for s in _SEATS if mask & (1 << (s - 1))]
                caught = set()
                newly = set()
                for s in shielders:
                    got = [j for j in _SEATS if j != s and not pfrz[j]
                           and not moved[j] and not mask & (1 << (j - 1))
                           and pown[pos[j]] == s]
                    if got:
                        caught.update(got)
                        newly.update(got)
                    else:
                        newly.add(s)  # No eligible catch means own backfire.
                possible = True
                for s in _SEATS:
                    # Frozen bool history identifies which of two forced turns this is.
                    expected = (not self.pfrz.get(s, False)) if pfrz[s] else s in newly
                    if bool(frz[s]) != expected:
                        possible = False
                        break
                    q = pos[s]
                    work = not pfrz[s] and not moved[s] and s not in caught \
                           and not mask & (1 << (s - 1))
                    o = pown[q]
                    if own[q] != o:
                        if (not work or own[q] != s or o == s or self.home[q]
                                or o and mask & (1 << (o - 1)) or upg[q]):
                            possible = False
                            break
                    elif work and (o == 0 or (o != s and not self.home[q]
                                               and not pupg[q]
                                               and not mask & (1 << (o - 1)))):
                        # Neutral and unupgraded foreign cells fall in one work turn.
                        possible = False
                        break
                    if own[q] == o and upg[q] != pupg[q]:
                        if not (work and o == s and not pupg[q] and upg[q]):
                            possible = False
                            break
                if possible:
                    valid.append(mask)
            return valid

    def _defend(self, legal):
            if "SHIELD" not in legal:
                return False
            me, t = self.me, self.t
            rem = 81 - t
            lam = self.lam
            cands = []
            for r in self.riv:
                if self.frz[r]:
                    continue
                q = self.pos[r]
                if self.own[q] != me:
                    continue
                b = self.base[q]
                st = self.streak[r]
                a = self._alpha(r)
                if self.home[q]:
                    ps = 0.1 if st == 0 else 0.4
                    ben = 3.0 * lam * a
                elif not self.upg[q]:
                    ps = self._pstay(r)
                    if rem <= 3:
                        ben = b * rem + a * (8.0 * b + b * rem) + a * 3.0 * lam
                    else:
                        rr = rem - 3
                        ben = ((1.0 + a) * 3.0 * b + a * 3.0 * lam +
                               0.15 * (b * rr + a * (8.0 * b + b * rr)))
                else:
                    ps = self._adaptive_distribution(r)[0]
                    if st >= 2 or rem <= 3 - st:
                        ben = 2.0 * b * rem + a * (16.0 * b + b * rem) + a * 3.0 * lam
                    else:
                        ben = a * (st + 3.0) * lam * 0.5
                ben *= self._shield_weight(r) * self.SHW
                cands.append((ps, ben))
            if not cands:
                return False
            pn = 1.0
            gain = 0.0
            for ps, ben in cands:
                gain += ps * ben
                pn *= (1.0 - ps)
            left = 80 - t
            cost = lam * (1.0 + 0.5 * self.prog) + pn * lam * min(2, left)
            return gain > cost



class AdaptiveTransferBot(AdaptiveDefenseBot):
    """Marginal public cooldown SUPPORT for transferable learning only."""
    def __init__(self, seed=0):
        AdaptiveDefenseBot.__init__(self, seed)
        self.ad_cooldowns = dict((s, {0}) for s in _SEATS)
        self.ad_diagnostics['cooldown_resyncs'] = 0
        self.ad_diagnostics['unknown_readiness_skips'] = 0

    def _observe(self, view):
        AdaptiveDefenseBot._observe(self, view)
        # Own legal actions are an observation, not an acceptance acknowledgement.
        if not self.frz[self.me]:
            allowed = {0} if self.ad_ready else {1, 2, 3, 4}
            kept = self.ad_cooldowns[self.me] & allowed
            if not kept:
                self.ad_diagnostics['cooldown_resyncs'] += 1
                raise RuntimeError("Own public legality contradicts cooldown support")
            self.ad_cooldowns[self.me] = kept

    def _ad_defender_ready(self, owner, frz, own_ready):
        if frz[owner]:
            return False
        if owner == self.me:
            return bool(own_ready)
        support = self.ad_cooldowns[owner]
        if support == {0}:
            return True
        if 0 not in support:
            return False
        return None

    def _ad_context(self, r, own, upg, pos, frz, ready):
        p = pos[r]
        owner = own[p]
        if frz[r] or owner in (0, r) or not upg[p] or self.home[p]:
            return None
        defender_ready = self._ad_defender_ready(owner, frz, ready)
        if defender_ready is None:
            self.ad_diagnostics['unknown_readiness_skips'] += 1
            return None
        phase = self.ad_work_run[r] if self.ad_work_known[r] else "unknown"
        free = sum(not any(q == pos[s] for s in _SEATS) for _, q in _NB[p])
        opportunity = any(s != r and not frz[s] and own[pos[s]] == r for s in _SEATS)
        # Deliberately no owner identity: a rival's publicly comparable behavior
        # can transfer between defenders, while readiness remains conditioned.
        return (r, phase, defender_ready), (r, phase, defender_ready, min(2, free), opportunity)

    def _ad_mask_cooldowns(self, masks):
        old = self.ad_cooldowns
        valid = [mask for mask in masks if all(not mask & (1 << (s-1)) or 0 in old[s] for s in _SEATS)]
        if not valid:
            self.ad_diagnostics['cooldown_resyncs'] += 1
            raise RuntimeError("Public transition has no compatible cooldown support")
        # Product-marginal relaxation may retain impossible correlations, but it
        # cannot exclude a real state that was represented before this turn.
        following = dict((s, set()) for s in _SEATS)
        for mask in valid:
            for s in _SEATS:
                if mask & (1 << (s-1)):
                    following[s].add(4)
                else:
                    following[s].update(max(0, value-1) for value in old[s])
        return valid, following

    def _events(self, t, me, own, upg, pos, frz, pown, pupg, ppos, pfrz):
            moved = dict((s, pos[s] != ppos[s]) for s in _SEATS)
            contexts = dict((r, self._ad_context(r, pown, pupg, ppos, pfrz, self.ad_ready)) for r in _SEATS if r != me)
            masks = self._public_shield_masks(me, own, upg, pos, frz, pown, pupg, ppos, pfrz, moved)
            masks, next_cooldowns = self._ad_mask_cooldowns(masks)
            if not masks:
                self.ad_diagnostics['resyncs'] += 1
            for r in _SEATS:
                if r == me:
                    continue
                labels = ({'M'} if moved[r] else set('Q' if mask & (1 << (r-1)) else 'S' for mask in masks)) if masks else set()
                label = next(iter(labels)) if len(labels) == 1 else None
                if pfrz[r]:
                    self.ad_diagnostics['forced'] += 1
                elif contexts[r] is not None:
                    if label is None:
                        self.ad_diagnostics['censored'] += 1
                        if labels == {'S', 'Q'}:
                            self._ad_record(contexts[r], 'A', t-1)
                    else:
                        self._ad_record(contexts[r], label, t-1)
                        self.ad_diagnostics['identified'] += 1
                p = pos[r]
                fresh_freeze = frz[r] and not pfrz[r]
                if moved[r] or fresh_freeze or label == 'Q' or own[p] != pown[p] or upg[p] != pupg[p]:
                    self.ad_work_run[r], self.ad_work_known[r] = 0, True
                elif pfrz[r]:
                    pass
                elif own[p] in (0, r) or not upg[p] or self.home[p]:
                    self.ad_work_run[r], self.ad_work_known[r] = 0, True
                elif label == 'S' and not frz[r]:
                    self.ad_work_run[r] = min(2, self.ad_work_run[r] + 1)
                    if self.ad_work_run[r] == 2:
                        self.ad_work_known[r] = True
                else:
                    # This resets a certified-run lower bound, NOT actual hidden progress.
                    self.ad_work_run[r], self.ad_work_known[r] = 0, False
            BlockerBot._events(self, t, me, own, upg, pos, frz, pown, pupg, ppos, pfrz)
            self.ad_cooldowns = next_cooldowns
    



class AdaptiveTransferProgressBot(AdaptiveTransferBot):
    """Own work follows public effects, not guessed rival Shield attribution."""
    def _events(self, t, me, own, upg, pos, frz, pown, pupg, ppos, pfrz):
        old_progress = self.prog
        own_request = self.last
        AdaptiveTransferBot._events(self, t, me, own, upg, pos, frz, pown, pupg, ppos, pfrz)
        P = pos[me]
        if P != ppos[me] or (frz[me] and not pfrz[me]):
            self.prog = 0
        elif pfrz[me]:
            self.prog = old_progress
        elif own_request == "SHIELD":
            self.prog = 0
        elif pown[P] == me:
            if pupg[P]:
                self.prog = old_progress
            else:
                self.prog = 0 if upg[P] else old_progress + 1
        elif pown[P] == 0:
            self.prog = 0
        elif self.home[P]:
            self.prog = old_progress
        elif own[P] == me:
            # A visible completed capture proves the work counter reset.
            self.prog = 0
        else:
            # No displacement, prior freeze, own Shield or fresh freeze means
            # effective STAY worked. An actual landlord Shield would catch it;
            # a point-attributed rival cast cannot suppress this evidence.
            self.prog = old_progress + 1



class PublicSupportProjectionBot(AdaptiveTransferProgressBot):
    """Remove only publicly impossible effective-action outcomes."""
    def _adaptive_distribution(self, r):
        inherited = AdaptiveTransferProgressBot._adaptive_distribution(self, r)
        prediction = self.ad_predictions[r]
        original = tuple(prediction.get('pre_support_probabilities', inherited))
        frozen = bool(self.frz[r])
        can_move = not frozen and any(not self.occ[q] for _, q in _NB[self.pos[r]])
        can_shield = not frozen and 0 in self.ad_cooldowns[r]
        weights = (original[0], original[1] if can_move else 0.0,
                   original[2] if can_shield else 0.0)
        removed_mass = (not can_move and original[1] > 0.0) or (not can_shield and original[2] > 0.0)
        total = sum(weights)
        if not removed_mass and not frozen:
            projected = original  # Preserve exact bytes of unchanged probabilities.
        else:
            projected = tuple(value / total for value in weights) if total > 0.0 else (1.0, 0.0, 0.0)
        # Frozen S denotes forced stationary behavior, not a catchable intention.
        if frozen:
            projected = (1.0, 0.0, 0.0)
        prediction['pre_support_probabilities'] = list(original)
        prediction['probabilities'] = list(projected)
        prediction['support_projected'] = projected != original
        prediction['support_can_move'] = can_move
        prediction['support_can_shield'] = can_shield
        prediction['forced_frozen'] = frozen
        prediction['shield_catch_eligible'] = not frozen
        # Keep source='prior'/'coarse'/'fine' intact: projection is not learning.
        return projected

    def _forecast(self):
        AdaptiveTransferProgressBot._forecast(self)
        for r in self.riv:
            prediction = self.ad_predictions.get(r)
            if (prediction is None or prediction['source'] != 'prior'
                    or not prediction.get('support_projected')):
                continue
            # The parent already rescales learned contexts using our projected
            # distribution. Only mechanically projected cold priors need this.
            pm = prediction['probabilities'][1]
            weights = self.stepp[r]
            total = sum(weights.values())
            if total > 0.0:
                self.stepp[r] = dict((q, weight * pm / total) for q, weight in weights.items())
            else:
                exits = [q for _, q in _NB[self.pos[r]] if not self.occ[q]]
                self.stepp[r] = dict((q, pm / len(exits)) for q in exits) if exits else {}

# Standalone entry point: the unchanged research policy receives only its public view.
_CONSOLIDATED_PLAYERS = {}
def act(state):
    seat = state.bot_id
    player = _CONSOLIDATED_PLAYERS.get(seat)
    if player is None:
        player = PublicSupportProjectionBot(seed=seat * 7919)
        _CONSOLIDATED_PLAYERS[seat] = player
    return player.act(state)

# Experimental public-only, within-match offensive option; frozen402 is above.
import math


class OffensiveCloseBot(PublicSupportProjectionBot):
    """Compare a certified short Shield-spending option with ordinary finishing."""
    OC_DECAY = 0.97
    OC_PRIOR = (2.0, 2.0)
    OC_MIN_RAW = 2
    OC_MIN_MASS = 1.2
    OC_MIN_Q_LOWER = 0.55
    OC_MARGIN = 0.01
    OC_LOOKAHEAD = 16

    def __init__(self, seed=0):
        PublicSupportProjectionBot.__init__(self, seed)
        self.oc_hazards = {}
        self.oc_plan = None
        self.oc_last_labels = []
        self.oc_last_casts = dict((s, None) for s in _SEATS)
        self.oc_last_evaluation = None
        self.oc_diagnostics = {'start': 0, 'return': 0, 'capture': 0, 'abort': 0,
                               'phaseoverride': 0, 'censored': 0, 'labels': 0}
        self.oc_abort_reasons = {}

    def _oc_other_targets(self, defender, intruder, own, pos, frz):
        return any(s not in (defender, intruder) and not frz[s]
                   and own[pos[s]] == defender for s in _SEATS)

    def _oc_record(self, key, cast, turn):
        profile = self.oc_hazards.get(key)
        if profile is None:
            profile = dict(q=0.0, n=0.0, raw=0, last=turn)
        decay = self.OC_DECAY ** max(0, turn - profile['last'])
        profile = dict(q=profile['q'] * decay + float(cast),
                       n=profile['n'] * decay + 1.0,
                       raw=profile['raw'] + 1, last=turn)
        self.oc_hazards[key] = profile

    def _oc_hazard(self, defender, phase, other_targets, turn=None):
        turn = self.t if turn is None else turn
        key = (defender, phase, bool(other_targets))
        profile = self.oc_hazards.get(key)
        q, n, raw = 0.0, 0.0, 0
        if profile is not None:
            decay = self.OC_DECAY ** max(0, turn - profile['last'])
            q, n, raw = profile['q'] * decay, profile['n'] * decay, profile['raw']
        a, b = self.OC_PRIOR[0] + q, self.OC_PRIOR[1] + n - q
        mean = a / (a + b)
        sd = math.sqrt(a * b / ((a + b) ** 2 * (a + b + 1.0)))
        return dict(a=a, b=b, mean=mean, lower=max(0.0, mean - 0.5 * sd),
                    upper=min(1.0, mean + 0.5 * sd), mass=n, raw=raw,
                    eligible=raw >= self.OC_MIN_RAW and n >= self.OC_MIN_MASS,
                    other_targets=bool(other_targets))

    def _events(self, t, me, own, upg, pos, frz, pown, pupg, ppos, pfrz):
        # Everything here precedes the parent's public-state update. No actual
        # action acknowledgement, private cooldown or hidden work is available.
        moved = dict((s, pos[s] != ppos[s]) for s in _SEATS)
        masks = self._public_shield_masks(me, own, upg, pos, frz,
                                           pown, pupg, ppos, pfrz, moved)
        masks, _ = self._ad_mask_cooldowns(masks)
        self.oc_last_labels = []
        self.oc_last_casts = {}
        for d in _SEATS:
            labels = set(bool(mask & (1 << (d - 1))) for mask in masks)
            self.oc_last_casts[d] = next(iter(labels)) if len(labels) == 1 else None
        seen = set()
        for s in _SEATS:
            p = ppos[s]
            d = pown[p]
            if d in (0, s) or self.home[p] or not pupg[p] or pfrz[s]:
                continue
            if pfrz[d] or self.ad_cooldowns[d] != {0}:
                continue  # Readiness must be certain at the observed decision.
            phase = self.prog if s == me else self.ad_work_run[s]
            known = s == me or self.ad_work_known[s]
            if not known or phase not in (0, 1, 2):
                continue
            other = self._oc_other_targets(d, s, pown, ppos, pfrz)
            key = (d, phase, other)
            if key in seen:
                continue  # One defender/context/turn is one observation.
            seen.add(key)
            cast = self.oc_last_casts[d]
            if cast is None:
                self.oc_diagnostics['censored'] += 1
                continue
            self._oc_record(key, cast, t - 1)
            self.oc_last_labels.append(dict(defender=d, intruder=s, cell=p, phase=phase, cast=cast,
                                           prior_turn=t - 1, other_targets=other))
            self.oc_diagnostics['labels'] += 1
        PublicSupportProjectionBot._events(self, t, me, own, upg, pos, frz,
                                            pown, pupg, ppos, pfrz)

    def _oc_projected(self):
        remaining = 81 - self.t
        return dict((s, self.score[s] + remaining * self.income[s]) for s in _SEATS)

    def _oc_rank_value(self, own_delta=0.0, defender=None, defender_delta=0.0,
                       free_riders=None):
        projected = self._oc_projected()
        projected[self.me] += own_delta
        if defender is not None:
            projected[defender] += defender_delta
        for rival, gain in (free_riders or {}).items():
            projected[rival] += gain
        scale = max(20.0, 2.0 * (81 - self.t))
        total = 0.0
        for r in self.riv:
            x = max(-40.0, min(40.0, (projected[self.me] - projected[r]) / scale))
            total += 1.0 / (1.0 + math.exp(-x))
        return total

    def _oc_stakes(self, defender):
        projected = self._oc_projected()
        remaining = 81 - self.t
        close = abs(projected[self.me] - projected[defender]) <= max(60.0, 4.0 * remaining)
        miss_cost = 3.0 * max(1.0, self.lam)
        # Explicit downside guard against giving a currently lower rival a pass.
        safe_cushion = all(projected[self.me] - projected[r] > miss_cost + 20.0
                           for r in self.riv if projected[r] <= projected[self.me])
        return close and safe_cushion

    def _oc_late_hazard(self, defender):
        other = self._oc_other_targets(defender, self.me, self.own, self.pos, self.frz)
        return self._oc_hazard(defender, 2, other)

    def _oc_wins_all_tokens(self, rival, destination, turn):
        if self.own[destination] == self.me:
            return True
        if self.own[destination] == rival or not self.tok:
            return False
        return all((self.me - (((turn - 1 + k) % 4) + 1)) % 4
                   < (rival - (((turn - 1 + k) % 4) + 1)) % 4 for k in self.tok)

    def _oc_safe_step(self, destination, legal):
        if self.occ[destination]:
            return None
        action = next((a for a, q in _NB[self.pos[self.me]] if q == destination and a in legal), None)
        if action is None:
            return None
        for r in self.riv:
            if not self.frz[r] and _MD[self.pos[r]][destination] == 1:
                if not self._oc_wins_all_tokens(r, destination, self.t):
                    return None
        return action

    def _oc_return_safe_ahead(self, target, defender):
        # On the Q-spending branch the defender cannot move during the hop.
        # Other rivals get at most two moves before the immediate return.
        for r in self.riv:
            if self.frz[r]:
                steps = max(0, 2 - self._frz_left(r))
            else:
                steps = 1 if r == defender else 2
            if _MD[self.pos[r]][target] <= steps:
                if not self._oc_wins_all_tokens(r, target, self.t + 1):
                    return False
        return True

    def _oc_free_riders(self, defender, target):
        """Conservative public opening-risk proxy, never a future action tape."""
        projected = self._oc_projected()
        remaining = 81 - self.t
        result, details = {}, []
        for r in self.riv:
            if r == defender or projected[r] <= projected[self.me]:
                continue
            best_gain, best_cell, best_delay = 0.0, None, None
            for q in range(64):
                if (q == target or self.own[q] != defender or self.home[q]
                        or self.occ[q] not in (0, r)):
                    continue
                distance = _MD[self.pos[r]][q]
                if distance > 2:
                    continue
                service = 3 if self.upg[q] else 1
                # An already present rival may need to dodge and return; do not
                # invent its hidden partial work. Static distance is optimistic
                # for the rival, making this a hedge rather than a guarantee.
                if self.frz[r]:
                    delay = self._frz_left(r) + distance + service - 1
                else:
                    delay = (distance if distance else 2) + service - 1
                if delay > 4:
                    continue
                b = float(self.base[q])
                gain = (16.0 if self.upg[q] else 8.0) * b + b * (remaining - delay)
                if gain > best_gain:
                    best_gain, best_cell, best_delay = gain, q, delay
            if best_cell is not None:
                result[r] = best_gain
                details.append(dict(rival=r, cell=best_cell, completion_delay=best_delay,
                                    gain=best_gain))
        return result, details

    def _oc_evaluate(self, defender, target, hazard):
        remaining = 81 - self.t
        horizon = min(remaining, self.OC_LOOKAHEAD)
        base, lam = float(self.base[target]), max(1.0, self.lam)
        a, b = hazard['a'], hazard['b']
        free_riders, opening_details = self._oc_free_riders(defender, target)
        # Beta-geometric posterior predictive under a fixed unknown phase2 rate.
        # This is a model-based approximation, not an equilibrium or guarantee.
        mass, finish, k = 1.0, 0.0, 0
        while 5 * k < horizon:
            delay = 5 * k
            no_cast = b / (a + b + k)
            weight = mass * no_cast
            life = remaining - delay
            own = 16.0 * base + base * life - lam * (delay + 1)
            enemy = -2.0 * base * life
            finish += weight * self._oc_rank_value(own, defender, enemy,
                                                   free_riders if k else None)
            mass *= 1.0 - no_cast
            k += 1
        finish += mass * self._oc_rank_value(-lam * horizon, free_riders=free_riders)
        life = remaining - 4
        success_own = 16.0 * base + base * life - 5.0 * lam
        success_enemy = -2.0 * base * life
        # Another catch means the owner need not backfire. Even with no other
        # target, value no speculative freeze/income benefit for conservatism.
        q = hazard['mean']
        feint = (q * self._oc_rank_value(success_own, defender, success_enemy, free_riders)
                 + (1.0 - q) * self._oc_rank_value(-3.0 * lam))
        ordinary = self._oc_rank_value()
        return dict(finish=finish, feint=feint, ordinary=ordinary,
                    advantage_finish=feint - finish, advantage_ordinary=feint - ordinary,
                    q=q, q_lower=hazard['lower'], remaining=remaining,
                    assumed_success_capture_delay=4, success_own_delta=success_own,
                    success_defender_delta=success_enemy, miss_own_delta=-3.0 * lam,
                    free_rider_openings=opening_details,
                    model='finite_beta_geometric_plus_projected_pairwise_proxy')

    def _oc_cancel(self, reason, captured=False):
        if self.oc_plan is not None:
            self.oc_diagnostics['capture' if captured else 'abort'] += 1
            self.oc_abort_reasons[reason] = self.oc_abort_reasons.get(reason, 0) + 1
        self.oc_plan = None

    def _oc_start(self, legal):
        me, p = self.me, self.pos[self.me]
        defender = self.own[p]
        if (self.t > 76 or self.prog != 2 or self.frz[me] or defender in (0, me)
                or self.home[p] or not self.upg[p] or self.frz[defender]
                or self.ad_cooldowns[defender] != {0} or not self._oc_stakes(defender)):
            return None
        hazard = self._oc_late_hazard(defender)
        if not hazard['eligible'] or hazard['lower'] < self.OC_MIN_Q_LOWER:
            return None
        if not self._oc_return_safe_ahead(p, defender):
            return None
        options = []
        for action, q in _NB[p]:
            if self._oc_safe_step(q, legal) is None:
                continue
            # Own, neutral and enemy land are all allowed; no hidden same-owner
            # restriction inherited from _hop. Prefer harmless own developed land.
            preference = (self.own[q] == me, self.upg[q] and self.own[q] == me,
                          self.own[q] == 0, -q)
            options.append((preference, action, q))
        if not options:
            return None
        evaluation = self._oc_evaluate(defender, p, hazard)
        self.oc_last_evaluation = evaluation
        if (evaluation['advantage_finish'] <= self.OC_MARGIN
                or evaluation['advantage_ordinary'] <= self.OC_MARGIN):
            return None
        _, action, hop = max(options)
        self.oc_plan = dict(start=self.t, target=p, defender=defender, hop=hop,
                            stage='await_cast', expected_progress=0,
                            evaluation=dict(evaluation))
        self.oc_diagnostics['start'] += 1
        return action

    def _oc_continue(self, legal):
        plan = self.oc_plan
        if plan is None:
            return None
        p, d = plan['target'], plan['defender']
        if self.own[p] == self.me:
            self._oc_cancel('captured', captured=True)
            return None
        if self.frz[self.me] or self.own[p] != d or not self.upg[p] or self.home[p]:
            self._oc_cancel('board_changed_or_frozen')
            return None
        if plan['stage'] == 'await_cast':
            if self.t != plan['start'] + 1 or self.pos[self.me] != plan['hop']:
                self._oc_cancel('hop_failed_or_delayed')
                return None
            if self.oc_last_casts.get(d) is not True or self.ad_cooldowns[d] != {4}:
                self._oc_cancel('cast_withheld_or_ambiguous')
                return None
            action = self._oc_safe_step(p, legal)
            if action is None:
                self._oc_cancel('return_contested_or_blocked')
                return None
            plan['stage'] = 'work'
            self.target = p
            self.oc_diagnostics['return'] += 1
            return action
        if self.pos[self.me] != p or self.prog not in (0, 1, 2):
            self._oc_cancel('work_position_or_progress_changed')
            return None
        need = 3 - self.prog
        support = self.ad_cooldowns[d]
        if self.t > 80 or not support or min(support) < need:
            self._oc_cancel('capture_window_not_certified')
            return None
        self.target = p
        return 'STAY'

    def _work(self, job, legal):
        p = self.pos[self.me]
        d = self.own[p]
        if (self.oc_plan is None and d not in (0, self.me) and self.upg[p]
                and not self.home[p] and self.prog in (0, 1)
                and not self.frz[d] and self.ad_cooldowns[d] == {0}
                and self._oc_stakes(d)):
            other = self._oc_other_targets(d, self.me, self.own, self.pos, self.frz)
            early = self._oc_hazard(d, self.prog, other)
            late = self._oc_hazard(d, 2, other)
            if (early['eligible'] and late['eligible'] and early['upper'] <= 0.45
                    and late['lower'] >= self.OC_MIN_Q_LOWER
                    and late['lower'] - early['upper'] >= 0.10):
                self.oc_diagnostics['phaseoverride'] += 1
                return 'STAY'
        return PublicSupportProjectionBot._work(self, job, legal)

    def _decide(self, view):
        had_plan = self.oc_plan is not None
        ordinary = PublicSupportProjectionBot._decide(self, view)
        if ordinary == 'SHIELD':
            self._oc_cancel('own_defense_overrides')
            return ordinary
        if had_plan:
            action = self._oc_continue(view.legal_actions)
            return ordinary if action is None else action
        action = self._oc_start(view.legal_actions)
        return ordinary if action is None else action


_CONSOLIDATED_PLAYERS = {}
def act(state):
    seat = state.bot_id
    player = _CONSOLIDATED_PLAYERS.get(seat)
    if player is None:
        player = OffensiveCloseBot(seed=seat * 7919)
        _CONSOLIDATED_PLAYERS[seat] = player
    return player.act(state)

# New route-option hypothesis; every byte of the frozen8c8 parent precedes this.
class OffensiveRouteBot(OffensiveCloseBot):
    """Approach and work toward valuable raids before legacy job filtering."""
    def __init__(self, seed=0):
        OffensiveCloseBot.__init__(self, seed)
        self.or_counts = {}
        self.or_plan = None
        self.or_diagnostics = dict(approaches=0, approach_steps=0, work=0,
                                   cancellations=0, direct_captures=0,
                                   prior_guided_starts=0, own_evidence_guided_starts=0,
                                   weak_transfer_guided_starts=0)
        self.or_last_evaluation = None

    def _events(self, *args):
        OffensiveCloseBot._events(self, *args)
        for label in self.oc_last_labels:
            key = (label['defender'], label['intruder'], label['phase'], label['other_targets'])
            q, n = self.or_counts.get(key, (0.0, 0.0))
            self.or_counts[key] = (q + float(label['cast']), n + 1.0)

    def _oc_hazard(self, defender, phase, other_targets, turn=None):
        # Per-attacker direct evidence dominates; all transfers share at most
        # half a pseudo-observation. No clock decay within the80-turn match.
        q, n = self.or_counts.get((defender, self.me, phase, bool(other_targets)), (0.0, 0.0))
        prior = 0.75 if phase == 2 else 0.20
        a, b = 2.0 * prior, 2.0 * (1.0 - prior)
        tq, tn = 0.0, 0.0
        for (d, attacker, p, other), (cq, cn) in self.or_counts.items():
            if (p == phase and other == bool(other_targets)
                    and (d == defender or attacker == self.me)
                    and (d, attacker) != (defender, self.me)):
                tq, tn = tq + cq, tn + cn
        weak = 0.5 if tn else 0.0
        transfer_mean = (0.5 + tq) / (1.0 + tn)
        a += q + weak * transfer_mean
        b += n - q + weak * (1.0 - transfer_mean)
        mean = a / (a + b)
        sd = math.sqrt(a * b / ((a + b) ** 2 * (a + b + 1.0)))
        return dict(a=a, b=b, mean=mean, lower=max(0.0, mean - 0.5 * sd),
                    upper=min(1.0, mean + 0.5 * sd), mass=n, raw=int(n),
                    eligible=True, other_targets=bool(other_targets),
                    source='own_attacker' if n else 'declared_phase_prior',
                    weak_transfer_mass=weak, own_raw=int(n), own_mass=n,
                    prior_only=not n and not weak)

    def _oc_start(self, legal):
        old = self.oc_diagnostics['start']
        action = OffensiveCloseBot._oc_start(self, legal)
        if self.oc_diagnostics['start'] != old:
            hazard = self._oc_late_hazard(self.own[self.pos[self.me]])
            self.oc_last_evaluation['hazard'] = dict(hazard)
            self.oc_plan['evaluation'] = dict(self.oc_last_evaluation)
            kind = ('own_evidence_guided_starts' if hazard['own_raw'] else
                    'weak_transfer_guided_starts' if hazard['weak_transfer_mass'] else
                    'prior_guided_starts')
            self.or_diagnostics[kind] += 1
        return action

    def _oc_evaluate(self, defender, target, hazard):
        result = OffensiveCloseBot._oc_evaluate(self, defender, target, hazard)
        free = dict((z['rival'], z['gain']) for z in result['free_rider_openings'])
        conservative_q = hazard['lower']
        feint = (conservative_q * self._oc_rank_value(result['success_own_delta'], defender,
                                                     result['success_defender_delta'], free)
                 + (1.0 - conservative_q) * self._oc_rank_value(result['miss_own_delta']))
        result['uncertainty_penalty'] = result['feint'] - feint
        result['feint'] = feint
        result['advantage_finish'] = feint - result['finish']
        result['advantage_ordinary'] = feint - result['ordinary']
        result['decision_q'] = conservative_q
        return result

    def _or_paths(self):
        start = self.pos[self.me]
        queue, seen = [(start, 0, None)], {start}
        result = {start: (0, None)}
        for p, distance, first in queue:
            if distance >= 3:
                continue
            for action, q in _NB[p]:
                if q in seen or self.occ[q]:
                    continue
                seen.add(q)
                first_step = (action, q) if first is None else first
                result[q] = (distance + 1, first_step)
                queue.append((q, distance + 1, first_step))
        return result

    def _or_opening_risk(self, defender, target, lead):
        projected, remaining = self._oc_projected(), 81 - self.t
        gains = {}
        for r in self.riv:
            if r == defender or projected[r] <= projected[self.me]:
                continue
            best = 0.0
            for q in range(64):
                if (q == target or self.own[q] != defender or self.home[q]
                        or self.occ[q] not in (0, r)):
                    continue
                distance = _MD[self.pos[r]][q]
                frozen = self._frz_left(r) if self.frz[r] else 0
                service = 3 if self.upg[q] else 1
                delay = max(0, distance + frozen - lead) + service - 1
                if delay <= 4:
                    b = float(self.base[q])
                    best = max(best, (16.0 if self.upg[q] else 8.0) * b
                               + b * max(0, remaining - lead - delay))
            if best:
                gains[r] = best
        return gains

    def _or_value(self, target, distance):
        d, me = self.own[target], self.me
        remaining, lam = 81 - self.t, max(1.0, self.lam)
        progress = self.prog if target == self.pos[me] else 0
        need, b = 3 - progress, float(self.base[target])
        if need not in (1, 2, 3) or distance + need > remaining:
            return None
        support = self.ad_cooldowns[d]
        if not support:
            return None
        frozen = self._frz_left(d) if self.frz[d] else 0
        safe_until = max(min(support), frozen)
        finish_delay = distance + need - 1
        ordinary = self._oc_rank_value()
        own = 16.0 * b + b * (remaining - finish_delay) - lam * (distance + need)
        enemy = -2.0 * b * (remaining - finish_delay)
        direct = self._oc_rank_value(own, d, enemy)
        if safe_until >= distance + need:
            return dict(mode='safe_finish', value=direct, ordinary=ordinary,
                        distance=distance, target=target, early_survival=1.0)
        other = self._oc_other_targets(d, me, self.own, self.pos, self.frz)
        survival = 1.0
        for phase in range(progress, 2):
            when = distance + phase - progress
            if safe_until <= when:
                survival *= 1.0 - self._oc_hazard(d, phase, other)['upper']
        hazard = self._oc_hazard(d, 2, other)
        a, bb = hazard['a'], hazard['b']
        mass, finish, k = 1.0, 0.0, 0
        horizon = min(remaining, 16 + distance)
        opening = self._or_opening_risk(d, target, distance + max(0, 2 - progress))
        while finish_delay + 5 * k < horizon:
            delay = finish_delay + 5 * k
            success = bb / (a + bb + k)
            own = 16.0 * b + b * (remaining - delay) - lam * (delay + 1)
            enemy = -2.0 * b * (remaining - delay)
            finish += mass * success * self._oc_rank_value(own, d, enemy, opening if k else None)
            mass *= 1.0 - success
            k += 1
        finish += mass * self._oc_rank_value(-lam * horizon, free_riders=opening)
        early_fail = self._oc_rank_value(-lam * (distance + 5), free_riders=opening)
        finish = survival * finish + (1.0 - survival) * early_fail
        feint = -1.0
        delay = distance + 6 - progress
        # All possible cooldowns expire by the proposed phase2 opportunity,
        # conditional on no intervening cast; actual availability is rechecked.
        if delay < remaining and max(support) <= distance + 2 - progress:
            own = 16.0 * b + b * (remaining - delay) - lam * (delay + 1)
            enemy = -2.0 * b * (remaining - delay)
            q = hazard['lower']
            branch = (q * self._oc_rank_value(own, d, enemy, opening)
                      + (1.0 - q) * self._oc_rank_value(-lam * (distance + 3)))
            feint = survival * branch + (1.0 - survival) * early_fail
        mode = 'feint' if feint > finish else 'finish'
        return dict(mode=mode, value=max(feint, finish), ordinary=ordinary,
                    finish=finish, feint=feint, distance=distance, target=target,
                    early_survival=survival, hazard=hazard, free_riders=opening)

    def _or_candidate(self, target, paths):
        if target not in paths:
            return None
        d = self.own[target]
        if d in (0, self.me) or self.home[target] or not self.upg[target] or not self._oc_stakes(d):
            return None
        distance, first = paths[target]
        # A planned exit is only a feasibility screen; the real hop is checked
        # against actual future public occupancy/priority before any macro starts.
        if not any(not self.occ[q] or q == self.pos[self.me] for _, q in _NB[target]):
            return None
        if first is not None and self._oc_safe_step(first[1], self._or_legal) is None:
            return None
        result = self._or_value(target, distance)
        if result is None or result['value'] <= result['ordinary'] + self.OC_MARGIN:
            return None
        return result

    def _or_clear(self):
        if self.or_plan is not None:
            self.or_diagnostics['cancellations'] += 1
        self.or_plan = None

    def _decide(self, view):
        ordinary = OffensiveCloseBot._decide(self, view)
        if ordinary == 'SHIELD':
            self._or_clear()
            return ordinary
        if self.oc_plan is not None:
            self.or_plan = None
            return ordinary  # Only the existing exact physical macro counts.
        if len(view.legal_actions) == 1:
            self._or_clear()
            return ordinary
        self._or_legal = view.legal_actions
        paths = self._or_paths()
        if self.or_plan is not None and self.own[self.or_plan['target']] == self.me:
            self.or_diagnostics['direct_captures'] += 1
            self.or_plan = None
        chosen = None
        if self.or_plan is not None and self.t - self.or_plan['created'] <= 8:
            chosen = self._or_candidate(self.or_plan['target'], paths)
        if chosen is None:
            self._or_clear()
            candidates = [self._or_candidate(p, paths) for p in paths]
            candidates = [z for z in candidates if z is not None]
            if not candidates:
                return ordinary
            chosen = max(candidates, key=lambda z: (z['value'], -z['distance'], -z['target']))
            self.or_plan = dict(target=chosen['target'], defender=self.own[chosen['target']],
                                created=self.t)
            self.or_diagnostics['approaches'] += 1
        self.or_last_evaluation = chosen
        target = chosen['target']
        self.target = target
        if self.pos[self.me] != target:
            action, destination = paths[target][1]
            safe = self._oc_safe_step(destination, view.legal_actions)
            if safe is not None:
                self.or_diagnostics['approach_steps'] += 1
                return safe
            self._or_clear()
            return ordinary
        d = self.own[target]
        if chosen['mode'] == 'safe_finish':
            self.or_diagnostics['work'] += 1
            return 'STAY'
        if self.prog < 2:
            if (not self.frz[d] and 0 in self.ad_cooldowns[d]
                    and self._oc_hazard(d, self.prog, self._oc_other_targets(
                        d, self.me, self.own, self.pos, self.frz))['upper'] > 0.45):
                self._or_clear()
                return ordinary
            self.or_diagnostics['work'] += 1
            return 'STAY'
        if chosen['mode'] == 'feint':
            action = self._oc_start(view.legal_actions)
            if action is not None:
                self.or_plan = None
                return action
            self._or_clear()
            return ordinary
        self.or_diagnostics['work'] += 1
        return 'STAY'


_CONSOLIDATED_PLAYERS = {}
def act(state):
    seat = state.bot_id
    player = _CONSOLIDATED_PLAYERS.get(seat)
    if player is None:
        player = OffensiveRouteBot(seed=seat * 7919)
        _CONSOLIDATED_PLAYERS[seat] = player
    return player.act(state)
