"""Zone Rush opponent bots -- search-and-simulation family (novel_a).

Every bot carries its own exact forward model of the rules (``_step``), a
tracker that rebuilds the hidden state from the views (turn, priority token,
progress, freezes, shield cooldowns, exact scores) and learns two habits of
each rival (does it shield intruders? does it raid upgraded cells?), and a
fast greedy "rate" policy that models the rivals and continues its own plans.
Leaf value = score + income x turns left (level-1 cells at half value, work in
progress credited), relative to the mean of the three rivals.

  nv_a_mcts      UCT over its own next actions, stochastic rival rollouts.
  nv_a_paranoid  max-min-max against the nearest rival(s) when they contest,
                 exhaustive 2-3 move economic search otherwise.
  nv_a_rhea      rolling-horizon evolution of 8-move plans, shift-seeded.
"""
import random
import time
from math import log as _mlog

# ----------------------------------------------------------------- constants
_T = 80
_ACT = ("NORTH", "EAST", "SOUTH", "WEST", "STAY", "SHIELD")
_AIDX = dict((a, k) for k, a in enumerate(_ACT))
_STAY = 4
_SHIELD = 5

_DEST = []
for _p in range(64):
    _r, _c = divmod(_p, 8)
    _DEST.append((_p - 8 if _r > 0 else -1, _p + 1 if _c < 7 else -1,
                  _p + 8 if _r < 7 else -1, _p - 1 if _c > 0 else -1))
_NB = [tuple((a, _DEST[p][a]) for a in range(4) if _DEST[p][a] >= 0) for p in range(64)]
_DIST = [[abs(p // 8 - q // 8) + abs(p % 8 - q % 8) for q in range(64)] for p in range(64)]
_RINGS = [[tuple(q for q in range(64) if _DIST[p][q] == d) for d in range(15)] for p in range(64)]
_HOME = [0] * 64
for _s, _cell in ((1, 0), (2, 7), (3, 63), (4, 56)):
    _HOME[_cell] = _s
_L1CELLS = tuple(q for q in range(64) if not _HOME[q])
_PEND = 0.8    # credit for a claim/raid that the next stay would complete


# ------------------------------------------------------------- forward model
class _St(object):
    """Full game state. ow/up per cell; pos/fz/cd/pg/sc/inc per seat index."""
    __slots__ = ("ow", "up", "pos", "fz", "cd", "pg", "sc", "inc", "tok", "turn")

    def clone(self):
        s = _St.__new__(_St)
        s.ow = self.ow[:]
        s.up = self.up[:]
        s.pos = self.pos[:]
        s.fz = self.fz[:]
        s.cd = self.cd[:]
        s.pg = self.pg[:]
        s.sc = self.sc[:]
        s.inc = self.inc[:]
        s.tok = self.tok
        s.turn = self.turn
        return s


def _step(S, acts, base):
    """Resolve one full turn in place (mirrors the referee). acts are ints 0-5."""
    pos = S.pos
    fz = S.fz
    cd = S.cd
    pg = S.pg
    ow = S.ow
    p0, p1, p2, p3 = pos
    eff = [4, 4, 4, 4]
    tg = [-1, -1, -1, -1]
    nmove = 0
    nsh = 0
    for i in (0, 1, 2, 3):
        if fz[i]:
            continue
        a = acts[i]
        if a < 4:
            t = _DEST[pos[i]][a]
            if t >= 0 and t != p0 and t != p1 and t != p2 and t != p3:
                tg[i] = t
                eff[i] = a
                nmove += 1
        elif a == 5 and not cd[i]:
            eff[i] = 5
            nsh += 1
    if nmove:
        for i in (0, 1, 2, 3):
            t = tg[i]
            if t < 0:
                continue
            w = i
            if nmove > 1:
                grp = [j for j in (0, 1, 2, 3) if tg[j] == t]
                if len(grp) > 1:
                    o = ow[t]
                    if o and tg[o - 1] == t:
                        w = o - 1
                    else:
                        tok = S.tok
                        best = 9
                        for j in grp:
                            rk = (j + 1 - tok) % 4
                            if rk < best:
                                best = rk
                                w = j
                    for j in grp:
                        tg[j] = -1
                        if j != w:
                            eff[j] = 4
            tg[i] = -1
            pos[w] = t
            pg[w] = 0
    caught = 0
    frz = 0
    shm = 0
    if nsh:
        for s in (0, 1, 2, 3):
            if eff[s] != 5:
                continue
            pg[s] = 0
            seat = s + 1
            shm |= 1 << seat
            got = 0
            for j in (0, 1, 2, 3):
                if j != s and not fz[j] and eff[j] == 4 and ow[pos[j]] == seat:
                    got |= 1 << j
            if got:
                caught |= got
            else:
                frz |= 1 << s
        frz |= caught
    up = S.up
    sc = S.sc
    inc = S.inc
    for i in (0, 1, 2, 3):
        if eff[i] != 4 or fz[i] or (caught >> i) & 1:
            continue
        p = pos[i]
        seat = i + 1
        o = ow[p]
        if o == seat:
            if up[p]:
                continue
            g = pg[i] + 1
            if g >= 3:
                up[p] = 1
                pg[i] = 0
                inc[i] += base[p]
            else:
                pg[i] = g
        elif o == 0:
            ow[p] = seat
            inc[i] += base[p]
            pg[i] = 0
        else:
            if _HOME[p] or (shm >> o) & 1:
                continue
            b = base[p]
            if up[p]:
                g = pg[i] + 1
                if g < 3:
                    pg[i] = g
                    continue
                sc[i] += 16 * b
                inc[o - 1] -= 2 * b
                up[p] = 0
            else:
                sc[i] += 8 * b
                inc[o - 1] -= b
            ow[p] = seat
            inc[i] += b
            pg[i] = 0
    for i in (0, 1, 2, 3):
        sc[i] += inc[i]
        if fz[i]:
            fz[i] -= 1
        if (frz >> i) & 1:
            fz[i] = 2
            pg[i] = 0
        if eff[i] == 5:
            cd[i] = 4
        elif cd[i]:
            cd[i] -= 1
    S.tok = S.tok % 4 + 1
    S.turn += 1
    return eff


# ------------------------------------------------------- greedy rate policy
def _choose_target(S, i, base, nsm=0):
    """Best cell by (gain / turns needed); code = cell | 64 for an upgrade job.
    nsm: bit s set = owner seat s is believed not to shield (raid its upgrades)."""
    seat = i + 1
    ow = S.ow
    up = S.up
    pos = S.pos
    p = pos[i]
    a0, a1, a2, a3 = pos
    R = _T - S.turn + 1
    bv = 0.0
    best = -1
    if ow[p] == seat and not up[p] and R > 2:
        bv = base[p] * (R - 2) / 3.0
        best = p | 64
    rings = _RINGS[p]
    cd = S.cd
    fz = S.fz
    for d in range(1, 15):
        if R - d < 1 or 24.0 + 4.0 * (R - d) <= bv * (d + 1):
            break
        for q in rings[d]:
            if q == a0 or q == a1 or q == a2 or q == a3:
                continue
            o = ow[q]
            if o == 0:
                v = base[q] * (R - d) / (d + 1.0)
                if v > bv:
                    bv = v
                    best = q
            elif o == seat:
                if not up[q] and R - d > 2:
                    v = base[q] * (R - d - 2) / (d + 3.0)
                    if v > bv:
                        bv = v
                        best = q | 64
            elif not _HOME[q]:
                oi = o - 1
                e = cd[oi] if cd[oi] > fz[oi] else fz[oi]
                b = base[q]
                if up[q]:
                    if (e >= d + 3 or (nsm >> o) & 1) and R - d >= 3:
                        v = (16 * b + 1.67 * b * (R - d - 2)) / (d + 3.0)
                        if v > bv:
                            bv = v
                            best = q
                else:
                    w = d + 1 if e > d else d + 4
                    if w <= R:
                        v = (8 * b + 1.33 * b * (R - w + 1)) / w
                        if v > bv:
                            bv = v
                            best = q
    return best


def _tvalid(S, i, code):
    t = code & 63
    o = S.ow[t]
    seat = i + 1
    if code & 64:
        return o == seat and not S.up[t]
    if o == seat or (o and _HOME[t]):
        return False
    pos = S.pos
    if t != pos[i] and (t == pos[0] or t == pos[1] or t == pos[2] or t == pos[3]):
        return False
    return True


def _toward(S, i, p, t, base):
    pos = S.pos
    ow = S.ow
    dt = _DIST[t]
    cur = dt[p]
    seat = i + 1
    ba = 4
    bv = -1
    for a, q in _NB[p]:
        if dt[q] < cur and q != pos[0] and q != pos[1] and q != pos[2] and q != pos[3]:
            o = ow[q]
            if o == 0:
                v = base[q]
            elif o != seat and not S.up[q] and not _HOME[q]:
                v = 9 * base[q]
            else:
                v = 0
            if v > bv:
                bv = v
                ba = a
    return ba


def _policy(S, i, base, tg, ub=99, sh=True, nsm=0):
    """Cheap greedy model of a competent bot (used for rivals and for me).
    ub: a non-home cell of base >= ub that the bot stands on is upgraded.
    sh: whether the bot shields against an intruder about to take its cell.
    nsm: bit 0 = bold (keeps raiding an upgraded cell it stands on); bit s =
    owner seat s is believed not to shield."""
    fz = S.fz
    if fz[i]:
        return 4
    seat = i + 1
    ow = S.ow
    pos = S.pos
    p = pos[i]
    o = ow[p]
    if o == 0:
        return 4
    up = S.up
    R = _T - S.turn + 1
    if o != seat:
        if not _HOME[p]:
            if not up[p]:
                return 4
            need = 3 - S.pg[i]
            oi = o - 1
            e = S.cd[oi] if S.cd[oi] > fz[oi] else fz[oi]
            if R >= need and (e >= need or (nsm & 1) or (nsm >> o) & 1):
                return 4
    elif not up[p] and ((S.pg[i] and R + S.pg[i] >= 3) or
                        (R > 3 and base[p] >= ub and (not _HOME[p] or S.turn <= 3))):
        return 4
    if sh and not S.cd[i]:
        for j in (0, 1, 2, 3):
            if j != i and not fz[j]:
                q = pos[j]
                if ow[q] == seat and not _HOME[q] and (not up[q] or S.pg[j]):
                    return 5
    code = tg[i]
    if code < 0 or not _tvalid(S, i, code):
        code = _choose_target(S, i, base, nsm)
        tg[i] = code
        if code < 0:
            return 4
    t = code & 63
    if t == p:
        return 4
    return _toward(S, i, p, t, base)


def _cands(S, i):
    """Pruned legal actions: STAY, moves into free cells, SHIELD only if it can catch."""
    if S.fz[i]:
        return [4]
    pos = S.pos
    out = [4]
    for a, q in _NB[pos[i]]:
        if q != pos[0] and q != pos[1] and q != pos[2] and q != pos[3]:
            out.append(a)
    if not S.cd[i]:
        seat = i + 1
        ow = S.ow
        for j in (0, 1, 2, 3):
            if j != i and not S.fz[j] and ow[pos[j]] == seat:
                out.append(5)
                break
    return out


def _vals(S):
    R = _T - S.turn + 1
    if R < 0:
        R = 0
    sc = S.sc
    inc = S.inc
    return (sc[0] + inc[0] * R, sc[1] + inc[1] * R, sc[2] + inc[2] * R, sc[3] + inc[3] * R)


def _value(S, me, base=None, f=1.0):
    """Projected final score (score + income x turns left) relative to the mean
    of the three rivals; exposed level-1 cells count only a fraction f."""
    R = _T - S.turn + 1
    if R < 0:
        R = 0
    sc = S.sc
    inc = S.inc
    v = [sc[0] + inc[0] * R, sc[1] + inc[1] * R, sc[2] + inc[2] * R, sc[3] + inc[3] * R]
    if R:
        ow = S.ow
        up = S.up
        if f < 1.0:
            k = (1.0 - f) * R
            for q in _L1CELLS:
                o = ow[q]
                if o and not up[q]:
                    v[o - 1] -= k * base[q]
        # credit work in progress (removes the horizon saw-tooth): upgrades
        # under way, and a claim / raid that the next stay completes
        pg = S.pg
        pos = S.pos
        fz = S.fz
        for i in (0, 1, 2, 3):
            q = pos[i]
            o = ow[q]
            if o == i + 1:
                g = pg[i]
                if g and not up[q] and R > 3 - g:
                    v[i] += g * (2.0 - f) * base[q] * (R - 3 + g) / 3.0
            elif fz[i] or R < 2:
                continue
            elif o == 0:
                v[i] += _PEND * f * base[q] * (R - 1)
            elif not up[q] and not _HOME[q]:
                b = base[q]
                v[i] += _PEND * (8 * b + f * b * (R - 1))
                v[o - 1] -= _PEND * f * b * (R - 1)
    m = v[me]
    return m - (v[0] + v[1] + v[2] + v[3] - m) / 3.0


# ----------------------------------------------------------------- base bot
class _Base(object):
    name = "nv_a_base"
    BUDGET = 0.009
    UB_ME = 2      # upgrade cells of base >= 2 that I claim
    UB_RIV = 99    # rival model: pure claim/raid rate greedy
    F = 0.5        # value fraction of a level-1 cell at the horizon (raid risk)
    NOSH = 0.3     # rivals shielding less often than this are raided when upgraded
    BOLD = 2       # rival model keeps raiding an upgraded cell it stands on:
                   # 0 never, 1 always, 2 once it has been seen doing so

    def __init__(self, seed=0):
        self.rnd = random.Random(seed)
        self.base = None
        self.S = None
        self.turn = 0
        self.tokc = [1, 2, 3, 4]
        self.last = 4
        self.me = 0
        self.sh_opp = [0, 0, 0, 0]
        self.sh_yes = [0, 0, 0, 0]
        self.bold_yes = [0, 0, 0, 0]
        self.cur_shs = [True, True, True, True]
        self.cur_shp = [0.5, 0.5, 0.5, 0.5]
        self.cur_nsm = [1, 1, 1, 1]

    def __call__(self, view):
        try:
            a = self.act(view)
        except Exception:
            a = "STAY"
            self.last = 4
        if a in view.legal_actions:
            return a
        self.last = 4
        return "STAY"

    def act(self, view):
        S = self._observe(view)
        self.last = 4
        legal = view.legal_actions
        if len(legal) <= 1:
            return "STAY"
        a = self.decide(S, view)
        if a is None or a < 0 or a > 5 or _ACT[a] not in legal:
            a = 4
        self.last = a
        return _ACT[a]

    def decide(self, S, view):
        self._ubs()
        return _policy(S, self.me, self.base, [-1, -1, -1, -1], self.UB_ME, True,
                       self.cur_nsm[self.me])

    # ---- tracking the hidden state ---------------------------------------
    def _observe(self, view):
        self.turn += 1
        me = view.bot_id - 1
        self.me = me
        first = self.base is None
        if first:
            base = [1] * 64
        else:
            base = self.base
        ow = [0] * 64
        up = [0] * 64
        pos = [0, 0, 0, 0]
        frz = [0, 0, 0, 0]
        p = 0
        for row in view.board:
            for cell in row:
                if first:
                    base[p] = cell.base_points
                o = cell.owner
                if o:
                    ow[p] = o
                    if cell.is_upgraded:
                        up[p] = 1
                oc = cell.occupant
                if oc:
                    pos[oc - 1] = p
                    if cell.is_frozen:
                        frz[oc - 1] = 1
                p += 1
        if first:
            self.base = base
        t = self.turn
        tk = bool(view.is_priority_token)
        cand = [s for s in self.tokc if (((s - 1 + t - 1) % 4) == me) == tk]
        if not cand:
            cand = [((me - (t - 1)) % 4) + 1] if tk else [1, 2, 3, 4]
        self.tokc = cand
        tok = (cand[0] - 1 + t - 1) % 4 + 1
        legal = view.legal_actions
        P = self.S
        if P is None:
            Q = _St()
            Q.ow = ow
            Q.up = up
            Q.pos = pos
            Q.fz = [2 if f else 0 for f in frz]
            Q.cd = [0, 0, 0, 0]
            Q.pg = [0, 0, 0, 0]
            Q.sc = [0, 0, 0, 0]
            inc = [0, 0, 0, 0]
            for q in range(64):
                if ow[q]:
                    inc[ow[q] - 1] += base[q] * (1 + up[q])
            Q.inc = inc
        else:
            ppos = P.pos
            pow_ = P.ow
            acts = [4, 4, 4, 4]
            for j in (0, 1, 2, 3):
                if j == me:
                    acts[j] = self.last
                    continue
                d = pos[j] - ppos[j]
                if d == -8:
                    acts[j] = 0
                elif d == 1:
                    acts[j] = 1
                elif d == 8:
                    acts[j] = 2
                elif d == -1:
                    acts[j] = 3
            newly = [j for j in (0, 1, 2, 3) if frz[j] and not P.fz[j]]
            if newly:
                shooter = [False] * 4
                shooter[me] = self.last == 5
                for j in newly:
                    if pos[j] != ppos[j]:
                        continue
                    o = pow_[pos[j]]
                    if o and o != j + 1:
                        k = o - 1
                        # a shooter that froze itself caught nobody
                        if k != me and not P.fz[k] and not frz[k]:
                            shooter[k] = True
                for j in newly:
                    if j == me:
                        continue
                    o = pow_[pos[j]]
                    if not (o and o != j + 1 and shooter[o - 1]):
                        shooter[j] = True
                for k in (0, 1, 2, 3):
                    if k != me and shooter[k]:
                        acts[k] = 5
            # has each rival kept raiding an upgraded cell (a bold raider)?
            for k in (0, 1, 2, 3):
                q = ppos[k]
                o = pow_[q]
                if (k != me and o and o != k + 1 and P.up[q] and not _HOME[q]
                        and not P.fz[k] and pos[k] == q and acts[k] != 5):
                    self.bold_yes[k] += 1
            # shield propensity per raid episode: a shield is a "yes"; a cell
            # taken from a rival that could have shielded is a "no"
            for k in (0, 1, 2, 3):
                if k != me and acts[k] == 5:
                    self.sh_opp[k] += 1
                    self.sh_yes[k] += 1
            for q in range(64):
                o = pow_[q]
                if o and ow[q] != o:
                    k = o - 1
                    if k != me and not P.fz[k] and not P.cd[k] and acts[k] != 5:
                        self.sh_opp[k] += 1
            Q = P.clone()
            for k in (0, 1, 2, 3):
                if acts[k] == 5:
                    Q.cd[k] = 0
            _step(Q, acts, base)
            pup = P.up
            sc = P.sc[:]
            inc = [0, 0, 0, 0]
            for q in range(64):
                o = ow[q]
                if o:
                    po = pow_[q]
                    if po and po != o:
                        sc[o - 1] += 8 * base[q] * (2 if pup[q] else 1)
                    inc[o - 1] += base[q] * (1 + up[q])
            for j in (0, 1, 2, 3):
                sc[j] += inc[j]
            pg = Q.pg
            for j in (0, 1, 2, 3):
                q = pos[j]
                if frz[j] or pos[j] != ppos[j]:
                    pg[j] = 0
                elif ow[q] != pow_[q] or up[q] != pup[q]:
                    pg[j] = 0
                elif Q.ow[q] != ow[q] or Q.up[q] != up[q]:
                    pg[j] = 2 if (ow[q] == j + 1 or up[q]) else 0
            Q.ow = ow
            Q.up = up
            Q.pos = pos
            Q.sc = sc
            Q.inc = inc
            Q.fz = [(1 if P.fz[j] == 2 else 2) if frz[j] else 0 for j in (0, 1, 2, 3)]
        if not frz[me]:
            if "SHIELD" in legal:
                Q.cd[me] = 0
            elif Q.cd[me] == 0:
                Q.cd[me] = 1
        Q.tok = tok
        Q.turn = t
        self.S = Q
        return Q

    def _root_targets(self, S):
        base = self.base
        nsm = self.cur_nsm
        return [_choose_target(S, j, base, nsm[j]) for j in (0, 1, 2, 3)]

    def _ubs(self):
        """Per-seat model parameters for this decision (also sets cur_shs and
        cur_nsm): rivals claim/raid greedily, are bold raiders, and shield
        only if they have been seen to; I upgrade and raid non-shielders."""
        u = [self.UB_RIV] * 4
        u[self.me] = self.UB_ME
        shp = self._shp()
        self.cur_shp = shp
        sh = [p > 0.5 for p in shp]
        sh[self.me] = True
        self.cur_shs = sh
        m = 0
        for k in (0, 1, 2, 3):
            if k != self.me and shp[k] < self.NOSH:
                m |= 1 << (k + 1)
        b = self.BOLD
        nsm = [1 if (b == 1 or (b == 2 and self.bold_yes[k] >= 2)) else 0 for k in (0, 1, 2, 3)]
        nsm[self.me] = m
        self.cur_nsm = nsm
        return u

    def _shp(self):
        """Estimated probability that each rival shields an intruder."""
        return [(1.0 + self.sh_yes[k]) / (2.0 + self.sh_opp[k]) for k in (0, 1, 2, 3)]

    def _shs(self):
        s = [p > 0.5 for p in self._shp()]
        s[self.me] = True
        return s

    def _greedy_acts(self, S, tg, ubs):
        base = self.base
        shs = self.cur_shs
        nm = self.cur_nsm
        return [_policy(S, 0, base, tg, ubs[0], shs[0], nm[0]),
                _policy(S, 1, base, tg, ubs[1], shs[1], nm[1]),
                _policy(S, 2, base, tg, ubs[2], shs[2], nm[2]),
                _policy(S, 3, base, tg, ubs[3], shs[3], nm[3])]

    def _rollout(self, S, tg, ubs, n):
        """n greedy turns in place."""
        base = self.base
        s0, s1, s2, s3 = self.cur_shs
        u0, u1, u2, u3 = ubs
        n0, n1, n2, n3 = self.cur_nsm
        for _ in range(n):
            _step(S, [_policy(S, 0, base, tg, u0, s0, n0), _policy(S, 1, base, tg, u1, s1, n1),
                      _policy(S, 2, base, tg, u2, s2, n2), _policy(S, 3, base, tg, u3, s3, n3)],
                  base)


# --------------------------------------------------------------------- MCTS
class _Node(object):
    __slots__ = ("n", "w", "mx", "kids", "untried")

    def __init__(self):
        self.n = 0
        self.w = 0.0
        self.mx = -1e18
        self.kids = {}
        self.untried = None


class MctsBot(_Base):
    """UCT over my own next actions (open loop, 2 plies of tree, 7-turn sims).
    Children are expanded policy-move first, so each iteration tries one new
    deviation and then follows my greedy line; rivals are sampled from a noisy
    greedy model whose shield habits are drawn from the learned propensities.
    Backups blend the mean and the max; the best blended root action is played."""
    name = "nv_a_mcts"
    BUDGET = 0.0075
    MAXIT = 500
    H = 7
    EPS_RIV = 0.05
    CUCT = 0.25
    BETA = 0.6
    SAMPLE_SH = 1
    TREE_D = 2

    def decide(self, S0, view):
        me = self.me
        base = self.base
        rr = self.rnd.random
        deadline = time.perf_counter() + self.BUDGET
        H = min(self.H, _T - S0.turn + 1)
        cand0 = _cands(S0, me)
        if len(cand0) == 1:
            return cand0[0]
        ubs = self._ubs()
        ubm = ubs[me]
        F = self.F
        tg0 = self._root_targets(S0)
        root = _Node()
        lo = 1e18
        hi = -1e18
        eps = self.EPS_RIV
        beta = self.BETA
        cu = self.CUCT
        shp = self.cur_shp
        nsm = self.cur_nsm
        nsm_me = nsm[me]
        tree_d = self.TREE_D
        it = 0
        while it < self.MAXIT:
            it += 1
            if self.SAMPLE_SH:
                shs = [rr() < shp[0], rr() < shp[1], rr() < shp[2], rr() < shp[3]]
                shs[me] = True
            else:
                shs = self.cur_shs
            S = S0.clone()
            tg = tg0[:]
            node = root
            path = [root]
            depth = 0
            while depth < H:
                if node.untried is None:
                    a = _policy(S, me, base, tg, ubm, True, nsm_me)
                    if depth < tree_d:
                        cs = cand0 if depth == 0 else _cands(S, me)
                        if a not in cs:
                            a = 4
                        node.untried = [c for c in cs if c != a]
                    else:
                        node.untried = []
                    child = node.kids.get(a)
                    if child is None:
                        child = _Node()
                        node.kids[a] = child
                elif node.untried:
                    u = node.untried
                    a = u.pop(int(rr() * len(u)))
                    child = _Node()
                    node.kids[a] = child
                else:
                    lnN = _log(node.n)
                    cexp = cu * (hi - lo) + 1.0
                    bestu = -1e18
                    for c, k in node.kids.items():
                        q = beta * k.mx + (1.0 - beta) * k.w / k.n
                        x = q + cexp * (lnN / k.n) ** 0.5
                        if x > bestu:
                            bestu = x
                            a = c
                    child = node.kids[a]
                acts = [0, 0, 0, 0]
                for j in (0, 1, 2, 3):
                    if j == me:
                        acts[j] = a
                    elif eps and rr() < eps and not S.fz[j]:
                        cj = _cands(S, j)
                        acts[j] = cj[int(rr() * len(cj))]
                    else:
                        acts[j] = _policy(S, j, base, tg, ubs[j], shs[j], nsm[j])
                _step(S, acts, base)
                depth += 1
                path.append(child)
                node = child
            v = _value(S, me, base, F)
            if v < lo:
                lo = v
            if v > hi:
                hi = v
            for nd in path:
                nd.n += 1
                nd.w += v
                if v > nd.mx:
                    nd.mx = v
            if time.perf_counter() > deadline:
                break
        best = 4
        bk = None
        for a, k in root.kids.items():
            key = (beta * k.mx + (1.0 - beta) * k.w / k.n, k.n)
            if bk is None or key > bk:
                bk = key
                best = a
        return best


def _log(x):
    return _mlog(x) if x > 1 else 0.0


# ----------------------------------------------------------------- paranoid
class ParanoidBot(_Base):
    """Paranoid search.  When a rival can contest (within 2 steps, on my land, or
    I am on its land) each move of mine is scored against that rival's WORST
    plausible reply (a shield if it has shown it shields, a raid on my level-1
    cells, contesting my destination, or its greedy move), then my best reply,
    then greedy rollouts.  Otherwise: exhaustive 2-3 move economic search."""
    name = "nv_a_paranoid"
    BUDGET = 0.0085
    H = 8
    NEAR = 2
    MAXNEAR = 2
    SHP_MIN = 0.6  # a rival's shield is a threat only once it has shown it shields
    ECON_D = 2

    def _own_search(self, S, tg, ubs, depth, D, H, deadline):
        """max over my next D moves (rivals greedy), then greedy to horizon."""
        me = self.me
        base = self.base
        cs = _cands(S, me)
        best = -1e18
        for a in cs:
            S1 = S.clone()
            tg1 = tg[:]
            acts = self._greedy_acts(S1, tg1, ubs)
            acts[me] = a
            _step(S1, acts, base)
            if depth + 1 < D and depth + 1 < H:
                v = self._own_search(S1, tg1, ubs, depth + 1, D, H, deadline)
            else:
                self._rollout(S1, tg1, ubs, H - depth - 1)
                v = _value(S1, me, base, self.F)
            if v > best:
                best = v
            if time.perf_counter() > deadline:
                break
        return best

    def _threats(self, S, k, a, gk):
        """Plausible replies of rival k to my move a: its greedy move, a shield
        that can catch, raids onto my level-1 cells, contesting my target."""
        me = self.me
        pos = S.pos
        ow = S.ow
        up = S.up
        seat = me + 1
        mydest = _DEST[pos[me]][a] if a < 4 else -1
        out = [gk]
        for b in _cands(S, k):
            if b == gk:
                continue
            if b == 5:
                if self.cur_shp[k] > self.SHP_MIN:
                    out.append(b)
            elif b < 4:
                q = _DEST[pos[k]][b]
                if q == mydest or (ow[q] == seat and not up[q] and not _HOME[q]):
                    out.append(b)
        return out

    def decide(self, S0, view):
        me = self.me
        base = self.base
        deadline = time.perf_counter() + self.BUDGET
        H = min(self.H, _T - S0.turn + 1)
        cand0 = _cands(S0, me)
        if len(cand0) == 1:
            return cand0[0]
        ubs = self._ubs()
        F = self.F
        tg0 = self._root_targets(S0)
        gtg = tg0[:]
        g_acts = self._greedy_acts(S0, gtg, ubs)
        mine = g_acts[me]
        if mine in cand0:
            cand0.remove(mine)
            cand0.insert(0, mine)
        pos = S0.pos
        ow = S0.ow
        mp = pos[me]
        near = []
        for k in (0, 1, 2, 3):
            if k == me or S0.fz[k]:
                continue
            d = _DIST[mp][pos[k]]
            if d <= self.NEAR or ow[pos[k]] == me + 1 or ow[mp] == k + 1:
                near.append((d, k))
        near.sort()
        near = [k for _, k in near[:self.MAXNEAR]]
        best = cand0[0]
        bestv = -1e18
        if not near:
            D = 3 if len(cand0) <= 3 else self.ECON_D
            for a in cand0:
                S1 = S0.clone()
                tg1 = tg0[:]
                acts = self._greedy_acts(S1, tg1, ubs)
                acts[me] = a
                _step(S1, acts, base)
                if H > 1 and D > 1:
                    v = self._own_search(S1, tg1, ubs, 1, D, H, deadline)
                else:
                    self._rollout(S1, tg1, ubs, H - 1)
                    v = _value(S1, me, base, F)
                if v > bestv:
                    bestv = v
                    best = a
                if time.perf_counter() > deadline:
                    break
            return best
        self.cur_shp = self._shp()
        # paranoid: max over my move, min over each near rival's threats,
        # max over my follow-up, then greedy rollout
        for a in cand0:
            worst = 1e18
            for k in near:
                for b in self._threats(S0, k, a, g_acts[k]):
                    S1 = S0.clone()
                    tg1 = tg0[:]
                    acts = self._greedy_acts(S1, tg1, ubs)
                    acts[me] = a
                    acts[k] = b
                    _step(S1, acts, base)
                    if H > 1:
                        v = self._own_search(S1, tg1, ubs, 1, 2, H, deadline)
                    else:
                        v = _value(S1, me, base, F)
                    if v < worst:
                        worst = v
                    if v <= bestv or time.perf_counter() > deadline:
                        break       # alpha cut: a cannot beat the best so far
                if worst <= bestv or time.perf_counter() > deadline:
                    break
            if worst > bestv:
                bestv = worst
                best = a
            if time.perf_counter() > deadline:
                break
        return best


# --------------------------------------------------------------------- RHEA
class RheaBot(_Base):
    """Rolling-horizon evolution: an elite population of 8-move plans is evolved
    (point mutations with kept or greedy suffixes, stay insertion, deletion)
    against deterministic greedy rivals, re-using the parent's simulated prefix
    states.  The first move of the best plan is played and the plan, shifted by
    one, seeds the next turn's population along with greedy-completed seeds."""
    name = "nv_a_rhea"
    BUDGET = 0.0075
    L = 8
    MU = 4
    MAXEV = 300

    def __init__(self, seed=0):
        _Base.__init__(self, seed)
        self.plan = None

    def _run(self, genes, k, snaps, H, ubs):
        """Simulate plan genes from step k using parent snaps[k]; -1 = greedy.
        Returns (value, concrete genes, snaps)."""
        base = self.base
        me = self.me
        S, tg = snaps[k]
        S = S.clone()
        tg = tg[:]
        out_snaps = snaps[:k + 1]
        g = genes[:]
        u0, u1, u2, u3 = ubs
        s0, s1, s2, s3 = self.cur_shs
        n0, n1, n2, n3 = self.cur_nsm
        nme = self.cur_nsm[me]
        for d in range(k, H):
            acts = [_policy(S, 0, base, tg, u0, s0, n0) if me != 0 else 0,
                    _policy(S, 1, base, tg, u1, s1, n1) if me != 1 else 0,
                    _policy(S, 2, base, tg, u2, s2, n2) if me != 2 else 0,
                    _policy(S, 3, base, tg, u3, s3, n3) if me != 3 else 0]
            a = g[d]
            if a < 0:
                a = _policy(S, me, base, tg, ubs[me], True, nme)
                g[d] = a
            acts[me] = a
            _step(S, acts, base)
            if d + 1 < H:
                out_snaps.append((S.clone(), tg[:]))
        return _value(S, me, base, self.F), g, out_snaps

    def decide(self, S0, view):
        me = self.me
        rr = self.rnd.random
        deadline = time.perf_counter() + self.BUDGET
        H = min(self.L, _T - S0.turn + 1)
        cand0 = _cands(S0, me)
        if len(cand0) == 1:
            self.plan = None
            return cand0[0]
        ubs = self._ubs()
        tg0 = self._root_targets(S0)
        root_snaps = [(S0, tg0)]
        pop = []
        seen = set()
        v, g, sn = self._run([-1] * H, 0, root_snaps, H, ubs)
        seen.add(tuple(g))
        pop.append((v, g, sn))
        for a in cand0:
            if a != g[0]:
                v2, g2, sn2 = self._run([a] + [-1] * (H - 1), 0, root_snaps, H, ubs)
                if tuple(g2) not in seen:
                    seen.add(tuple(g2))
                    pop.append((v2, g2, sn2))
        if self.plan:
            sp = self.plan[1:H + 1]
            if sp and sp[0] in cand0:
                sp = sp + [-1] * (H - len(sp))
                v3, g3, sn3 = self._run(sp, 0, root_snaps, H, ubs)
                if tuple(g3) not in seen:
                    seen.add(tuple(g3))
                    pop.append((v3, g3, sn3))
        pop.sort(key=lambda x: -x[0])
        del pop[self.MU:]
        nev = len(seen)
        while nev < self.MAXEV and time.perf_counter() < deadline:
            nev += 1
            pv, pgn, psn = pop[int(rr() * rr() * len(pop))]
            r = rr()
            k = int(H * rr() * rr()) if H > 1 else 0
            if k >= H:
                k = H - 1
            g = pgn[:]
            if r < 0.7:
                ck = _cands(psn[k][0], me)
                if len(ck) > 1:
                    na = ck[int(rr() * len(ck))]
                    while na == g[k]:
                        na = ck[int(rr() * len(ck))]
                else:
                    na = ck[0]
                g[k] = na
                if rr() < 0.5:
                    for d in range(k + 1, H):
                        g[d] = -1
            elif r < 0.85:
                g = g[:k] + [4] + g[k:H - 1]
            else:
                g = g[:k] + g[k + 1:] + [-1]
            key = tuple(g)
            if key in seen:
                continue
            v, g2, sn = self._run(g, k, psn, H, ubs)
            seen.add(key)
            seen.add(tuple(g2))
            if len(pop) < self.MU or v > pop[-1][0]:
                pop.append((v, g2, sn))
                pop.sort(key=lambda x: -x[0])
                del pop[self.MU:]
        best = pop[0]
        self.plan = best[1]
        a = best[1][0]
        if a not in cand0:
            a = 4
        return a


BOTS = [MctsBot, ParanoidBot, RheaBot]

# Standalone entry point: the unchanged research policy receives only its public view.
_CONSOLIDATED_PLAYERS = {}
def act(state):
    seat = state.bot_id
    player = _CONSOLIDATED_PLAYERS.get(seat)
    if player is None:
        player = ParanoidBot(seed=seat * 7919)
        _CONSOLIDATED_PLAYERS[seat] = player
    return player.act(state)
