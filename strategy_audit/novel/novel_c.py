"""Novel opponent bots, set C: three economic philosophies for Zone Rush.

nv_c_voronoi   -- territory by reachability: race distances decide what is "mine".
nv_c_bloomer   -- late bloomer: dense upgraded fortress near home, then mass raids.
nv_c_portfolio -- several heuristics, an in-game discounted-UCB bandit picks one.

All three share one observation core (pure standard library) that rebuilds from
the visible board everything the view hides: turn, token holder, every seat's
score and income, rival shield cool-downs (every shield leaves a visible freeze),
consecutive stays, own take/upgrade progress, raid and shield tendencies.
"""
import math
import random

_N = 8
_NC = 64
_MAXT = 80
_SEATS = (1, 2, 3, 4)


def _tables():
    nbr = []
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
        nbr.append(tuple(lst))
    man = []
    for a in range(_NC):
        ra, ca = divmod(a, _N)
        man.append(tuple(abs(ra - b // _N) + abs(ca - b % _N) for b in range(_NC)))
    return tuple(nbr), tuple(man)


_NBR, _MAN = _tables()
_CORNER = {1: 0, 2: _N - 1, 3: _NC - 1, 4: _NC - _N}
# measured in self-play: a level-1 cell d steps from a raider is lost at ~0.17*e^-d per turn
_EXPT = tuple(0.17 * math.exp(-d) for d in range(40))


class _Core(object):
    """Shared state reconstruction, chain planner, navigation and shield logic."""
    name = "nv_c_core"
    QC = 0.35          # chance a neutral cell is still free if a rival can reach it first
    SH_THR = 1.0       # shield when expected benefit > SH_THR * expected cost
    L1_BOOST = 0.0     # extra belief that a rival on my level-1 cell will stay
    DEPTH = 3
    WIDTHS = (6, 4, 3)
    POOL = 14
    HYST = 1.12
    HZ = 0.5           # scale of the raid-hazard model (0 = ignore raids on my land)
    HC = 0.7           # share of the hazard applied to future level-1 holdings
    BL = 0.4           # weight of the bonus a raider would collect from my cell
    fx = False         # does the current policy feint decisive raid stays?

    def __init__(self, seed=0):
        self.rng = random.Random(seed)
        self.t = 0
        self.me = 0
        self.base = None
        self.home = None
        self.rivals = ()
        self.homecell = dict(_CORNER)
        self.owner = [0] * _NC
        self.upg = [0] * _NC
        self.pos = [-1] * 5
        self.frz = [False] * 5
        self.frz_left = [0] * 5
        self.tok = set(_SEATS)
        self.last_shield = [-99] * 5
        self.stays = [0] * 5
        self.score = [0] * 5
        self.income = [0] * 5
        self.damage = 0.0
        self.raid_ev = [[0, 0] for _ in range(5)]
        self.sh_l1 = [[0, 0] for _ in range(5)]
        self.sh_up = [[0, 0] for _ in range(5)]
        self.pend_raid = [-1] * 5
        self.pend_sh = [0] * 5
        self.dec_ev = [[0, 0] for _ in range(5)]
        self.pend_dec = [-1] * 5
        self.sec_ev = [[0, 0] for _ in range(5)]
        self.pend_sec = [-1] * 5
        self.my_prog = 0
        self.last_act = "STAY"
        self.lost = {}
        self.prev_tgt = -1
        self.legal = ()
        self.occ = set()
        self.ar = [99] * _NC
        self.amin = [()] * _NC
        self.tw = [None] * 5
        self.hz = [0.0] * _NC

    # ------------------------------------------------------------------ API
    def __call__(self, view):
        try:
            a = self.act(view)
        except Exception:
            a = "STAY"
        return a if a in view.legal_actions else "STAY"

    def act(self, view):
        self.legal = view.legal_actions
        self._observe(view)
        if len(self.legal) == 1:
            a = self.legal[0]
        else:
            self._prep()
            a = self._decide()
        if a not in self.legal:
            a = "STAY"
        if a == "SHIELD":
            self.last_shield[self.me] = self.t
        self.last_act = a
        return a

    def _decide(self):
        act, rho, info = self._policy()
        if self._want_shield(rho, info, act):
            return "SHIELD"
        return act

    def _policy(self):
        raise NotImplementedError

    # ---------------------------------------------------------- observation
    def _observe(self, view):
        self.t += 1
        t = self.t
        owner = [0] * _NC
        upg = [0] * _NC
        pos = [-1] * 5
        frz = [False] * 5
        first = self.base is None
        if first:
            base = [1] * _NC
            home = [0] * _NC
        p = 0
        for row in view.board:
            for cell in row:
                o = cell.owner
                owner[p] = o
                if cell.is_upgraded:
                    upg[p] = 1
                oc = cell.occupant
                if oc:
                    pos[oc] = p
                    if cell.is_frozen:
                        frz[oc] = True
                if first:
                    base[p] = cell.base_points
                    if cell.is_home:
                        home[p] = o
                p += 1
        me = view.bot_id
        if first:
            self.me = me
            self.base = base
            self.home = home
            self.rivals = tuple(s for s in _SEATS if s != me)
            for q in range(_NC):
                if home[q]:
                    self.homecell[home[q]] = q
        for s in _SEATS:
            if pos[s] < 0:
                pos[s] = self.pos[s] if self.pos[s] >= 0 else self.homecell.get(s, _CORNER[s])
        # token holder: holder(u) = (T1 - 1 + u - 1) % 4 + 1
        k = (me - 1 - (t - 1)) % 4 + 1
        if view.is_priority_token:
            self.tok = set((k,))
        else:
            self.tok.discard(k)
            if not self.tok:
                self.tok = set(_SEATS)
                self.tok.discard(k)
        if not first:
            self._diff(owner, upg, pos, frz)
        else:
            inc = [0] * 5
            for q in range(_NC):
                if owner[q]:
                    inc[owner[q]] += self.base[q] * (2 if upg[q] else 1)
            self.income = inc
        self.owner = owner
        self.upg = upg
        self.pos = pos
        self.frz = frz
        # shield opportunities visible now (evaluated at the next observation)
        for y in self.rivals:
            self.pend_sh[y] = 0
            if frz[y] or not self._ready(y, t):
                continue
            kk = 0
            for x in _SEATS:
                if x == y or frz[x]:
                    continue
                q = pos[x]
                if owner[q] != y or self.home[q]:
                    continue
                if upg[q]:
                    if self.stays[x] >= 2:
                        kk = 2
                elif self.stays[x] == 0 and kk == 0:
                    kk = 1
            self.pend_sh[y] = kk

    def _diff(self, owner, upg, pos, frz):
        t = self.t
        me = self.me
        base = self.base
        po = self.owner
        pu = self.upg
        ppos = self.pos
        pfrz = self.frz
        inc = [0] * 5
        R = _MAXT + 1 - t
        for q in range(_NC):
            o = owner[q]
            if o:
                lv = 2 if upg[q] else 1
                inc[o] += base[q] * lv
                a = po[q]
                if a and a != o:
                    plv = 2 if pu[q] else 1
                    self.score[o] += 8 * base[q] * plv
                    if a == me:
                        self.lost[q] = t
                    elif o == me:
                        self.damage += base[q] * plv * max(0, R)
                        self.lost.pop(q, None)
        for s in _SEATS:
            self.score[s] += inc[s]
        self.income = inc
        # freezes -> shield events
        newf = [False] * 5
        for s in _SEATS:
            newf[s] = frz[s] and not pfrz[s]
        for s in _SEATS:
            if not newf[s]:
                continue
            q = pos[s]
            y = po[q]
            if s == me:
                if self.last_act != "SHIELD" and y and y != me:
                    self.last_shield[y] = t - 1
            elif y == me:
                if self.last_act != "SHIELD" or newf[me]:
                    self.last_shield[s] = t - 1
            elif y and y != s and not newf[y] and (self.last_shield[y] == t - 1 or
                                                   self._ready(y, t - 1)):
                self.last_shield[y] = t - 1
            else:
                self.last_shield[s] = t - 1
        for s in _SEATS:
            self.frz_left[s] = 2 if newf[s] else (1 if frz[s] else 0)
        # consecutive stays
        for s in _SEATS:
            if pos[s] == ppos[s]:
                if newf[s] or pfrz[s] or self.last_shield[s] == t - 1:
                    self.stays[s] = 0
                else:
                    self.stays[s] += 1
            else:
                self.stays[s] = 0
        # raid tendency: did a rival that stepped onto foreign level-1 land stay?
        for s in self.rivals:
            pr = self.pend_raid[s]
            if pr >= 0:
                ev = self.raid_ev[s]
                ev[1] += 1
                if pos[s] == pr:
                    ev[0] += 1
                self.pend_raid[s] = -1
            q = pos[s]
            if q != ppos[s] and not frz[s]:
                o = owner[q]
                if o and o != s and not self.home[q] and not upg[q]:
                    self.pend_raid[s] = q
        # decisive-stay tendency: on foreign upgraded land after two stays, did it stay?
        for s in self.rivals:
            for pend, evs in ((self.pend_dec, self.dec_ev), (self.pend_sec, self.sec_ev)):
                pr = pend[s]
                if pr >= 0:
                    ev = evs[s]
                    ev[1] += 1
                    if pos[s] == pr:
                        ev[0] += 1
                    pend[s] = -1
            q = pos[s]
            o = owner[q]
            if not frz[s] and upg[q] and o and o != s and not self.home[q]:
                if self.stays[s] >= 2:
                    self.pend_dec[s] = q
                elif self.stays[s] == 1:
                    self.pend_sec[s] = q
        # shield tendency at the decisive moments
        for y in self.rivals:
            kk = self.pend_sh[y]
            if kk:
                arr = self.sh_l1[y] if kk == 1 else self.sh_up[y]
                arr[1] += 1
                if self.last_shield[y] == t - 1:
                    arr[0] += 1
        # own progress
        mp = pos[me]
        if frz[me] or pfrz[me] or mp != ppos[me] or self.last_act == "SHIELD":
            self.my_prog = 0
        else:
            o = owner[mp]
            if o == me:
                if po[mp] != me or (upg[mp] and not pu[mp]) or upg[mp]:
                    self.my_prog = 0
                else:
                    self.my_prog += 1
            elif o != 0 and upg[mp] and not self.home[mp]:
                self.my_prog += 1
            else:
                self.my_prog = 0

    # ---------------------------------------------------------------- helpers
    def _ready(self, y, u):
        """Can seat y shield at turn u (inferred)?"""
        if self.frz[y] and u < self.t + self.frz_left[y]:
            return False
        return u >= self.last_shield[y] + 5

    def _rate_l1(self, y):
        a = self.sh_l1[y]
        return (a[0] + 1.0) / (a[1] + 2.5)

    def _rate_up(self, y):
        a = self.sh_up[y]
        return (a[0] + 1.5) / (a[1] + 2.5)

    def _raid_p(self, s):
        ev = self.raid_ev[s]
        return (ev[0] + 2.0) / (ev[1] + 3.0)

    def _w(self, s):
        """Weight of one point taken from rival s, relative to one point gained."""
        if self.score[s] >= self.score[self.me] - 40:
            return 0.45
        return 0.33

    def _prep(self):
        me = self.me
        ar = [99] * _NC
        amin = [()] * _NC
        for s in self.rivals:
            ps = self.pos[s]
            fl = self.frz_left[s]
            row = _MAN[ps]
            for q in range(_NC):
                d = row[q] + fl
                if d < ar[q]:
                    ar[q] = d
                    amin[q] = (s,)
                elif d == ar[q]:
                    amin[q] = amin[q] + (s,)
        self.ar = ar
        self.amin = amin
        tw = [None] * 5
        for s in self.rivals:
            row = []
            for m in range(4):
                ok = True
                for T1 in self.tok:
                    h = (T1 - 1 + m - 1) % 4 + 1
                    if (me - h) % 4 > (s - h) % 4:
                        ok = False
                        break
                row.append(ok)
            tw[s] = row
        self.tw = tw
        self.occ = set(self.pos[s] for s in self.rivals)
        # raid hazard of a level-1 cell (per turn), from rival bodies and land
        hz = [0.0] * _NC
        HZ = self.HZ
        if HZ > 0:
            owner = self.owner
            for s in self.rivals:
                rp = self._raid_p(s) / 0.67
                rp = HZ * (0.3 if rp < 0.3 else (1.5 if rp > 1.5 else rp))
                prow = _MAN[self.pos[s]]
                fl = self.frz_left[s]
                land = [q for q in range(_NC) if owner[q] == s]
                for q in range(_NC):
                    dt = 14
                    mq = _MAN[q]
                    for x in land:
                        if mq[x] < dt:
                            dt = mq[x]
                    hz[q] += rp * (_EXPT[prow[q] + fl] + 0.5 * _EXPT[dt + 1])
            for q in range(_NC):
                if self.home[q]:
                    hz[q] = 0.0        # homes can never be taken
        self.hz = hz

    def _expo(self):
        """Raid exposure of each cell: how close raid-prone rivals are."""
        ex = [0.0] * _NC
        for s in self.rivals:
            rp = self._raid_p(s)
            if self.frz[s]:
                rp *= 0.7
            row = _MAN[self.pos[s]]
            for q in range(_NC):
                ex[q] += rp / (1.0 + row[q])
        return ex

    def _adj_mine(self, q):
        me = self.me
        own = self.owner
        for _a, y in _NBR[q]:
            if own[y] == me:
                return True
        return False

    # ----------------------------------------------------------- the planner
    def _plan(self, Wc, Wu, Wr, Wx, depth=None, widths=None, pool_n=None):
        """Depth-limited chain search over targets; maximise gain per turn.

        Returns (action, rho, (target, kind)).  Kinds: 0 claim, 1 upgrade,
        2 raid level-1, 3 raid upgraded."""
        depth = depth or self.DEPTH
        widths = widths or self.WIDTHS
        pool_n = pool_n or self.POOL
        me = self.me
        t0 = self.t
        mp = self.pos[me]
        base = self.base
        owner = self.owner
        upg = self.upg
        home = self.home
        occ = self.occ
        ar = self.ar
        amin = self.amin
        tw = self.tw
        QC = self.QC
        prog = self.my_prog
        hz = self.hz
        fx = self.fx
        HC = self.HC
        BL = self.BL
        exp = math.exp
        cands = []
        for q in range(_NC):
            if q in occ:
                continue
            o = owner[q]
            b = base[q]
            if o == 0:
                w = Wc[q]
                if w > 0:
                    cands.append((q, 0, b, 1, w, 0.0, 0.0, 0, 1, hz[q]))
            elif o == me:
                if upg[q]:
                    continue
                w = Wu[q]
                if w > 0:
                    st = max(1, 3 - prog) if q == mp else 3
                    cands.append((q, 1, b, st, w, 0.0, 0.0, 0, 3, hz[q]))
            elif not home[q]:
                wy = self._w(o)
                if upg[q]:
                    w = Wx[q]
                    if w > 0:
                        st = max(1, 3 - prog) if q == mp else 3
                        cands.append((q, 3, b, st, w, 16.0 * b, 2.0 * wy * b, o, 3, hz[q]))
                else:
                    w = Wr[q]
                    if w > 0:
                        cands.append((q, 2, b, 1, w, 8.0 * b, wy * b, o, 1, hz[q]))
        if not cands:
            return self._idle(), 0.0, (mp, -1)
        ready = self._ready
        rl1 = {}
        rup = {}
        for s in self.rivals:
            rl1[s] = self._rate_l1(s)
            rup[s] = self._rate_up(s)

        def held(b, h, rem):
            """Expected income of a level-1 cell of base b under raid hazard h,
            minus the bonus a raider would collect from it."""
            x = h * rem
            if x < 1e-3:
                return b * rem
            e = 1.0 - exp(-x)
            return b * e / h - BL * 8.0 * b * e

        def ugain(b, h, rem):
            x = h * rem
            if x < 1e-3:
                return b * rem
            e = 1.0 - exp(-x)
            return b * rem + b * (rem - e / h) + BL * 8.0 * b * e

        def gain(c, arrive, st):
            q = c[0]
            kind = c[1]
            rem = _MAXT + 2 - (t0 + arrive + st)
            if rem <= 0:
                return 0.0, 0.0
            if kind == 0:
                P = 1.0
                if arrive > 0:
                    a = ar[q]
                    ai = int(arrive + 0.5)
                    if ai > a:
                        P = QC
                    elif ai == a:
                        m = (t0 + ai - 1) % 4
                        for s in amin[q]:
                            if not tw[s][m]:
                                P = QC
                                break
                return c[4] * P * held(c[2], c[9] * HC, rem), 0.0
            if kind == 1:
                return c[4] * ugain(c[2], c[9], rem), 0.0
            y = c[7]
            u = t0 + arrive
            if kind == 2:
                ps = rl1[y] if ready(y, u) else 0.0
                return (c[4] * (1.0 - 0.4 * ps) *
                        (c[5] + c[6] * rem + held(c[2], c[9] * HC, rem))), 3.0 * ps
            if ready(y, u + st - 1) or (st >= 2 and ready(y, u + st - 2)) or (st >= 3 and ready(y, u)):
                ps = rup[y]
            else:
                ps = 0.0
            if fx and ps > 0:
                # we feint the decisive stay: most shields backfire, costing a detour
                return (c[4] * (1.0 - 0.3 * ps) *
                        (c[5] + c[6] * (rem - 3 * ps) + held(c[2], c[9] * HC, rem - 3 * ps))), 3.0 * ps
            return (c[4] * (1.0 - ps) *
                    (c[5] + c[6] * rem + held(c[2], c[9] * HC, rem))), 3.0 * ps

        # pool by single-target ratio
        prev = self.prev_tgt
        scored = []
        for c in cands:
            d = _MAN[mp][c[0]]
            st = c[3]
            g, ex = gain(c, d, st)
            if g <= 0:
                continue
            if c[0] == prev:
                g *= self.HYST
            scored.append((g / (d + st + ex), c))
        if not scored:
            return self._idle(), 0.0, (mp, -1)
        scored.sort(key=lambda z: -z[0])
        pool = [z[1] for z in scored[:pool_n]]
        npool = len(pool)
        best = [-1.0, None]
        hyst = self.HYST

        def rec(cur, T, G, used, lvl, first, vq):
            opts = []
            for i in range(npool):
                if (used >> i) & 1:
                    continue
                c = pool[i]
                q = c[0]
                d = _MAN[cur][q]
                st = c[3] if (T == 0 and q == mp) else c[8]
                g, ex = gain(c, T + d, st)
                if g <= 0:
                    continue
                if lvl == 0 and q == prev:
                    g *= hyst
                dt = d + st + ex
                opts.append(((G + g) / (T + dt), i, g, dt, q, c[1]))
            if vq >= 0:
                w = Wu[vq]
                rem = _MAXT + 2 - (t0 + T + 3)
                if w > 0 and rem > 0:
                    g = w * ugain(base[vq], hz[vq], rem)
                    opts.append(((G + g) / (T + 3), -1, g, 3, vq, 1))
            if not opts:
                if T > 0 and first is not None and G / T > best[0]:
                    best[0] = G / T
                    best[1] = first
                return
            opts.sort(key=lambda z: -z[0])
            if lvl + 1 >= depth:
                o = opts[0]
                if o[0] > best[0]:
                    best[0] = o[0]
                    best[1] = first if first is not None else o
                return
            for o in opts[:widths[lvl]]:
                i = o[1]
                nused = used | (1 << i) if i >= 0 else used
                nvq = o[4] if o[5] in (0, 2, 3) else -1
                rec(o[4], T + o[3], G + o[2], nused, lvl + 1,
                    first if first is not None else o, nvq)

        rec(mp, 0, 0.0, 0, 0, None, -1)
        if best[1] is None:
            return self._idle(), 0.0, (mp, -1)
        tgt = best[1][4]
        kind = best[1][5]
        self.prev_tgt = tgt
        if tgt == mp:
            return "STAY", best[0], (tgt, kind)
        return self._step_to(tgt), best[0], (tgt, kind)

    def _feint(self, act, pmin):
        """About to make the decisive stay of a raid while the owner's shield is
        up and the owner is known to shield at such moments?  Step off instead
        (onto more of its land if possible): its shield then backfires, leaving
        it frozen and on cool-down while we raid.  Returns a move or None."""
        if act != "STAY":
            return None
        me = self.me
        mp = self.pos[me]
        y = self.owner[mp]
        if y == 0 or y == me or self.home[mp]:
            return None
        t = self.t
        if t >= _MAXT - 1 or not self._ready(y, t):
            return None
        if self.upg[mp]:
            if self.my_prog < 2:
                return None
            p = self._rate_up(y)
        else:
            p = self._rate_l1(y)
        if p < pmin:
            return None
        best = None
        for a, q in _NBR[mp]:
            if q in self.occ or a not in self.legal:
                continue
            o = self.owner[q]
            k = 0
            if o == y and not self.home[q]:
                k = 3 + self.base[q] * (2 if self.upg[q] else 1)
            elif o == 0:
                k = 1
            elif o == me:
                k = 2
            if best is None or k > best[0]:
                best = (k, a)
        return best[1] if best else None

    def _idle(self):
        """Nothing worth doing: stand still unless that is dangerous."""
        mp = self.pos[self.me]
        o = self.owner[mp]
        if o in (0, self.me):
            return "STAY"
        for a, y in _NBR[mp]:
            if y not in self.occ and self.owner[y] in (0, self.me):
                return a
        return "STAY"

    # ------------------------------------------------------------ navigation
    def _bfs_from(self, tgt):
        occ = self.occ
        dist = [99] * _NC
        dist[tgt] = 0
        dq = [tgt]
        i = 0
        while i < len(dq):
            x = dq[i]
            i += 1
            dx = dist[x] + 1
            for _a, y in _NBR[x]:
                if dist[y] == 99 and y not in occ:
                    dist[y] = dx
                    dq.append(y)
        return dist

    def _step_options(self, tgt):
        """Legal improving steps toward tgt: list of (key, action, cell)."""
        me = self.me
        cur = self.pos[me]
        dist = self._bfs_from(tgt)
        here = dist[cur] if dist[cur] < 99 else _MAN[cur][tgt]
        opts = []
        m = self.t % 4
        for a, y in _NBR[cur]:
            if y in self.occ or a not in self.legal:
                continue
            d = dist[y]
            if d >= 99:
                d = _MAN[y][tgt] + 3
            pen = 0
            for s in self.rivals:
                if self.frz[s]:
                    continue
                if _MAN[self.pos[s]][y] == 1:
                    if self.owner[y] == s or (self.owner[y] != me and not self.tw[s][m]):
                        pen += 1
            opts.append(((d, pen, -(self.base[y] if self.owner[y] == 0 else 0)), a, y))
        opts.sort()
        return opts, here

    def _step_to(self, tgt):
        opts, here = self._step_options(tgt)
        if not opts or opts[0][0][0] >= here:
            return "STAY"
        return opts[0][1]

    # --------------------------------------------------------------- shields
    def _want_shield(self, rho, info, act, thr=None, l1_boost=None):
        if "SHIELD" not in self.legal:
            return False
        me = self.me
        t = self.t
        R = _MAXT + 1 - t
        if R <= 0:
            return False
        if l1_boost is None:
            l1_boost = self.L1_BOOST
        threats = []
        extra = 0.0
        for s in self.rivals:
            if self.frz[s]:
                continue
            q = self.pos[s]
            if self.owner[q] != me:
                continue
            b = self.base[q]
            w = self._w(s)
            k = self.stays[s]
            if self.home[q]:
                if k >= 1:
                    threats.append((0.5, w * 2.0 * max(rho, 1.0)))
                continue
            if self.upg[q]:
                need = 3 - k
                if need > R:
                    continue
                ev = self.dec_ev[s]
                p = (ev[0] + 3.6) / (ev[1] + 4.0)
                if need == 2:
                    # against a rival that feints the decisive stay, strike one
                    # stay earlier, when it still has no reason to step off
                    e2 = self.sec_ev[s]
                    p2 = (e2[0] + 3.6) / (e2[1] + 4.0)
                    if p2 < p + 0.15:
                        continue
                    p = p2
                elif need > 2:
                    continue
                v = 0.85 * (16.0 * b * w + 2.0 * b * (1.0 + w) * R)
                # a raider that steps off at the decisive moment (a feint) makes
                # the shield backfire and then takes the cell during the cool-down
                extra += (1.0 - p) * 0.7 * v
                threats.append((p, v))
            else:
                p = self._raid_p(s)
                if k >= 1:
                    p = max(p, 0.8)
                p = min(0.96, p + l1_boost)
                full = 8.0 * b * w + b * (1.0 + w) * R
                if R <= 3:
                    v = full
                else:
                    v = 3.0 * b * (1.0 + w) + w * 3.0 * max(rho, 1.0) + 0.25 * full
                threats.append((p, v))
        if not threats:
            return False
        ben = 0.0
        pn = 1.0
        for p, v in threats:
            ben += p * v
            pn *= (1.0 - p)
        loss = 1.0
        if act == "STAY" and info[1] in (1, 3) and self.my_prog > 0:
            loss += self.my_prog
        cost = rho * loss + pn * rho * min(2, R - 1) + (extra if R > 3 else 0.0)
        if thr is None:
            thr = self.SH_THR
        return ben > thr * cost


# =============================================================================
class VoronoiBot(_Core):
    """Territory by reachability.  Each turn a multi-source race (arrival times,
    frozen turns, the token tie rule) gives the cells it reaches before every
    rival; it claims the most valuable first (thin-margin frontier before safe
    interior falls out of the timed chain search), refuses races it loses,
    annexes rival level-1 cells inside its region, upgrades cells of its own
    region, and breaks movement ties by the size of the resulting region."""
    name = "nv_c_voronoi"
    QC = 0.12
    WU = 1.5           # upgrade weight
    UI = 0.15          # penalty for upgrading cells a rival reaches before me
    WR = 1.0
    WX = 0.9

    def _policy(self):
        me = self.me
        mp = self.pos[me]
        ar = self.ar
        owner = self.owner
        upg = self.upg
        home = self.home
        row = _MAN[mp]
        Wc = [0.0] * _NC
        Wu = [0.0] * _NC
        Wr = [0.0] * _NC
        Wx = [0.0] * _NC
        WU = self.WU
        UI = self.UI
        for q in range(_NC):
            m = ar[q] - row[q]
            o = owner[q]
            if o == 0:
                Wc[q] = 1.0
                Wu[q] = WU
            elif o == me:
                if not upg[q]:
                    # cells a rival reaches before me are outside my region
                    Wu[q] = WU if m >= 0 else WU * (1.0 - UI)
            elif not home[q]:
                if upg[q]:
                    Wx[q] = self.WX if m > 0 else 0.5 * self.WX
                else:
                    Wr[q] = self.WR if m > 0 else 0.6 * self.WR
        act, rho, info = self._plan(Wc, Wu, Wr, Wx)
        if act in ("NORTH", "SOUTH", "EAST", "WEST"):
            act = self._region_step(info[0], act)
        return act, rho, info

    def _region_step(self, tgt, act):
        opts, here = self._step_options(tgt)
        if not opts:
            return act
        bestd = opts[0][0][0]
        if bestd >= here:
            return act
        tied = [o for o in opts if o[0][0] == bestd and o[0][1] == opts[0][0][1]]
        if len(tied) < 2:
            return act
        ar = self.ar
        base = self.base
        owner = self.owner
        me = self.me
        bestv = None
        besta = act
        for _k, a, y in tied:
            row = _MAN[y]
            v = 0
            for q in range(_NC):
                o = owner[q]
                if o == 0 or (o != me and not self.home[q] and not self.upg[q]):
                    if row[q] + 1 < ar[q]:
                        v += base[q]
            if bestv is None or v > bestv:
                bestv = v
                besta = a
        return besta


# =============================================================================
class BloomerBot(_Core):
    """Late bloomer.  Until 25 turns remain it builds a dense, upgrade-heavy
    fortress (compact claims, in-place upgrades, retaking intruded cells, no
    raids abroad) guarded by shields timed on a raider's decisive stay.  Then it
    turns mass raider: rival level-1 and upgraded cells (16 x base), favouring
    victims whose shield is on reconstructed cool-down, and feinting the
    decisive stay against owners known to shield it (their shield backfires)."""
    name = "nv_c_bloomer"
    LATE = 25          # turns left when the raiding phase starts
    ZONE = (1.0, 1.0, 1.0, 1.0, 0.95, 0.85, 0.7, 0.45, 0.3, 0.25, 0.2, 0.2, 0.2, 0.2, 0.2)
    ZK = 0.1           # strength of the near-home preference (0 = none)
    WU_A = 1.4         # fortress phase: upgrade weight
    DENSE = 1.05       # fortress phase: bonus for claims touching my land
    WR_A = 1.15        # fortress phase: retake / raid inside the fortress zone
    WR_B = 1.25        # bloom phase: raid level-1
    WX_B = 1.7         # bloom phase: raid upgraded
    COOL = 1.4         # bloom phase: bonus when the victim's shield is down
    WC_B = 0.75
    WU_B = 0.45
    ZQ = 1.0           # fortress phase: weight of cells outside my home quadrant
    FEINT_UP = 0.45    # bloom phase: feint when the owner shields a third stay this often
    FEINT_L1 = 0.55    # ... or a level-1 arrival this often
    feints = 0

    def _quadrant(self):
        zq = getattr(self, "_zq", None)
        if zq is None:
            me = self.me
            hs = self.homecell
            mine = hs.get(me, _CORNER[me])
            zq = []
            for q in range(_NC):
                dm = _MAN[mine][q]
                zq.append(all(dm < _MAN[hs.get(s, _CORNER[s])][q] for s in self.rivals))
            self._zq = zq
        return zq

    def _policy(self):
        me = self.me
        t = self.t
        R = _MAXT + 1 - t
        hc = self.homecell.get(me, _CORNER[me])
        hrow = _MAN[hc]
        owner = self.owner
        upg = self.upg
        home = self.home
        Wc = [0.0] * _NC
        Wu = [0.0] * _NC
        Wr = [0.0] * _NC
        Wx = [0.0] * _NC
        if R > self.LATE:
            self.fx = False
            ZK = self.ZK
            zq = self._quadrant()
            for q in range(_NC):
                o = owner[q]
                z = 1.0 - ZK * (1.0 - self.ZONE[hrow[q]])
                if not zq[q]:
                    z *= self.ZQ
                if o == 0:
                    Wc[q] = z * (self.DENSE if self._adj_mine(q) else 1.0)
                    Wu[q] = self.WU_A * z
                elif o == me:
                    if not upg[q]:
                        Wu[q] = self.WU_A
                elif not home[q]:
                    if not upg[q]:
                        Wr[q] = self.WR_A if (q in self.lost or hrow[q] <= 5) else 0.3
            return self._plan(Wc, Wu, Wr, Wx)
        # bloom: mass raiding
        mp = self.pos[me]
        self.fx = True
        for q in range(_NC):
            o = owner[q]
            if o == 0:
                Wc[q] = self.WC_B
                Wu[q] = self.WU_B
            elif o == me:
                if not upg[q]:
                    Wu[q] = self.WU_B
            elif not home[q]:
                cool = not self._ready(o, t + _MAN[mp][q])
                if upg[q]:
                    Wx[q] = self.WX_B * (self.COOL if cool else 1.0)
                else:
                    Wr[q] = self.WR_B * (self.COOL if cool else 1.0)
        act, rho, info = self._plan(Wc, Wu, Wr, Wx)
        mv = self._feint(act, self.FEINT_UP if self.upg[mp] else self.FEINT_L1)
        if mv is not None:
            self.feints += 1
            return mv, rho, (info[0], -1)
        return act, rho, info


# =============================================================================
class PortfolioBot(_Core):
    """Portfolio of five heuristics -- nearest-value claim, upgrade-in-place,
    opportunistic raid, frontier defence/recapture, centre-value rush -- and a
    discounted-UCB bandit that re-chooses one every few turns.  Its reward is
    the reconstructed projected-score delta of the window (score + income x
    turns left, plus a share of the damage dealt to rivals)."""
    name = "nv_c_portfolio"
    ARMS = ("grab", "build", "raid", "guard", "value")
    PRIOR = (0.75, 0.5, 0.6, 0.45, 0.7)
    WIN = 3
    GAMMA = 0.9
    UCB_C = 0.4
    HYST = 1.3         # keep the current target across arm switches

    def __init__(self, seed=0):
        _Core.__init__(self, seed)
        self.arm = -1
        self.arm_t = 0
        self.v0 = 0.0
        self.n = [1.0] * len(self.ARMS)
        self.s = list(self.PRIOR)
        self.hist = []

    def _value(self):
        me = self.me
        return self.score[me] + self.income[me] * (_MAXT + 1 - self.t) + self.damage / 3.0

    def _available(self, i):
        me = self.me
        own = self.owner
        if i in (0, 4):
            return any(o == 0 for o in own)
        if i == 1:
            return any(own[q] == me and not self.upg[q] for q in range(_NC))
        if i == 2:
            return any(own[q] not in (0, me) and not self.home[q] for q in range(_NC))
        if i == 3:
            return True
        return True

    def _choose(self):
        t = self.t
        if self.arm >= 0:
            L = t - self.arm_t
            v = self._value()
            Rm = _MAXT + 1 - (t + self.arm_t) / 2.0
            r = (v - self.v0) / (L * (Rm + 10.0))
            r = max(-1.0, min(2.0, r))
            for i in range(len(self.ARMS)):
                self.n[i] *= self.GAMMA
                self.s[i] *= self.GAMMA
            self.n[self.arm] += 1.0
            self.s[self.arm] += r
            self.hist.append((self.arm, round(r, 3)))
        tot = sum(self.n)
        best = -1
        bv = -1e9
        for i in range(len(self.ARMS)):
            if not self._available(i):
                continue
            idx = self.s[i] / self.n[i] + self.UCB_C * math.sqrt(math.log(tot + 1.0) / self.n[i])
            idx += 1e-6 * self.rng.random()
            if idx > bv:
                bv = idx
                best = i
        if best < 0:
            best = 0
        self.arm = best
        self.arm_t = t
        self.v0 = self._value()

    def _policy(self):
        t = self.t
        if self.arm < 0 or t - self.arm_t >= self.WIN:
            # do not abandon a half-finished upgrade or raid
            busy = (self.my_prog > 0 and self.arm >= 0 and t - self.arm_t < self.WIN + 3)
            if not busy:
                self._choose()
        a = self.arm
        me = self.me
        mp = self.pos[me]
        owner = self.owner
        upg = self.upg
        home = self.home
        Wc = [0.0] * _NC
        Wu = [0.0] * _NC
        Wr = [0.0] * _NC
        Wx = [0.0] * _NC
        depth = None
        thr = None
        boost = None
        self.fx = (a == 2)
        if a == 0:          # grab: nearest-value claiming, shallow look-ahead
            for q in range(_NC):
                o = owner[q]
                if o == 0:
                    Wc[q] = 1.0
                    Wu[q] = 1.15
                elif o == me:
                    Wu[q] = 1.15
                elif not home[q] and not upg[q]:
                    Wr[q] = 0.8
            depth = 2
        elif a == 1:        # build: upgrade in place, compact claims
            ex = self._expo()
            for q in range(_NC):
                o = owner[q]
                if o == 0:
                    Wc[q] = 0.85 if self._adj_mine(q) else 0.5
                    Wu[q] = 1.8
                elif o == me:
                    Wu[q] = 1.8 + 0.6 * ex[q]
                elif not home[q] and not upg[q]:
                    Wr[q] = 0.6
        elif a == 2:        # raid: bonus hunting, preferring rivals whose shield is down
            t = self.t
            for q in range(_NC):
                o = owner[q]
                if o == 0:
                    Wc[q] = 0.95
                    Wu[q] = 1.3
                elif o == me:
                    Wu[q] = 1.3
                elif not home[q]:
                    down = not self._ready(o, t + _MAN[mp][q])
                    if upg[q]:
                        Wx[q] = 1.6 if down else 1.35
                    else:
                        Wr[q] = 1.45 if down else 1.2
            depth = 2
        elif a == 3:        # guard: upgrade exposed frontier, recapture, shield eagerly
            ex = self._expo()
            for q in range(_NC):
                o = owner[q]
                if o == 0:
                    adj = self._adj_mine(q)
                    Wc[q] = 0.7 if adj else 0.4
                    Wu[q] = 1.2 + 1.5 * ex[q]
                elif o == me:
                    Wu[q] = 1.1 + 2.0 * ex[q]
                elif not home[q] and not upg[q]:
                    if q in self.lost:
                        Wr[q] = 1.9
                    elif self._adj_mine(q):
                        Wr[q] = 1.2
                    else:
                        Wr[q] = 0.4
            thr = 0.7
            boost = 0.1
        else:               # value: rush the high-value cells
            for q in range(_NC):
                o = owner[q]
                b = self.base[q]
                if o == 0:
                    Wc[q] = (b / 2.0) ** 1.5
                    Wu[q] = 1.2
                elif o == me:
                    Wu[q] = 1.2 * (b / 2.0)
                elif not home[q]:
                    if upg[q]:
                        Wx[q] = 0.4 * (b / 2.0)
                    else:
                        Wr[q] = 0.8 * (b / 2.0)
        act, rho, info = self._plan(Wc, Wu, Wr, Wx, depth=depth)
        if a == 2:
            mv = self._feint(act, 0.45 if self.upg[mp] else 0.55)
            if mv is not None:
                act, info = mv, (info[0], -1)
        self._thr = thr
        self._boost = boost
        return act, rho, info

    def _decide(self):
        self._thr = None
        self._boost = None
        act, rho, info = self._policy()
        if self._want_shield(rho, info, act, thr=self._thr, l1_boost=self._boost):
            return "SHIELD"
        return act


BOTS = [VoronoiBot, BloomerBot, PortfolioBot]
