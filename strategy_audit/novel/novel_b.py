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
