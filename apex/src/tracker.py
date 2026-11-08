"""Exact hidden-state reconstruction for Zone Rush (development module)."""

CORNER = (None, 0, 7, 63, 56)
NEIGHB = []
for _p in range(64):
    _r, _c = divmod(_p, 8)
    NEIGHB.append(tuple(q for q, ok in ((_p - 8, _r > 0), (_p + 1, _c < 7),
                                        (_p + 8, _r < 7), (_p - 1, _c > 0)) if ok))
DIR_OF = {}
for _p in range(64):
    _r, _c = divmod(_p, 8)
    for _nm, _q, _ok in (("NORTH", _p - 8, _r > 0), ("EAST", _p + 1, _c < 7),
                         ("SOUTH", _p + 8, _r < 7), ("WEST", _p - 1, _c > 0)):
        if _ok:
            DIR_OF[(_p, _q)] = _nm
TARGET = {}
for (_p, _q), _nm in DIR_OF.items():
    TARGET[(_p, _nm)] = _q


class Obs(object):
    """One normalised board."""
    __slots__ = ("owner", "up", "home", "base", "pos", "frz", "occ")

    def __init__(self, cells):
        self.owner = [c.owner for c in cells]
        self.up = [1 if c.is_upgraded else 0 for c in cells]
        self.home = [0] * 64
        self.base = [c.base_points for c in cells]
        self.pos = [-1] * 5
        self.frz = [False] * 5
        self.occ = [0] * 64
        for i, c in enumerate(cells):
            if c.is_home:
                h = c.owner or 0
                if not h and i in CORNER:
                    h = CORNER.index(i)
                self.home[i] = h
            o = c.occupant
            if o and 1 <= o <= 4:
                self.pos[o] = i
                self.frz[o] = bool(c.is_frozen)
                self.occ[i] = o

    def pristine(self):
        for s in (1, 2, 3, 4):
            if self.pos[s] != CORNER[s]:
                return False
        if any(self.up):
            return False
        n = 0
        for p in range(64):
            if self.owner[p]:
                n += 1
                if p not in CORNER:
                    return False
        return n == 4

    def owned_count(self):
        return sum(1 for o in self.owner if o)


class Tracker(object):
    """Turn, scores, progress, freezes, cooldowns, token, shields: from boards alone."""

    def __init__(self):
        self.me = None
        self.turn = 0
        self.seen = 0                # consecutive turns observed in this game
        self.prev = None
        self.reset_counts()

    def reset_counts(self):
        self.score = [0] * 5
        self.prog = [0] * 5          # consecutive productive stays on the current cell
        self.fl = [0] * 5            # frozen turns left at the start of this turn
        self.cd = [0] * 5            # best-estimate shield cooldown at the start of this turn
        self.cdmin = [0] * 5         # lowest cooldown consistent with every explanation
        self.holder_set = None       # possible token holders this turn
        self.shielded = set()        # seats that shielded in the last resolved turn
        self.amb = set()             # seats whose shield last turn is ambiguous
        self.caught = set()          # seats caught last turn
        self.events = []             # (kind, cell, seat, from_seat, was_up) last turn
        self.since = [0] * 5         # stays since the last completion on the same cell
        self.last_done = [None] * 5  # (kind, cell) of the last completion
        self.carry_ev = 0
        self.reset_ev = 0
        self.rogue = [0.0] * 5       # learned tendency to shield with nobody to catch
        self.known_start = False
        self.last_lost = []          # cells I lost last turn
        self.stats_turn0 = 0

    # ------------------------------------------------------------------
    def claim_resets(self):
        return self.reset_ev >= self.carry_ev

    def need(self, seat, cell, ob=None):
        """Stays needed in total for seat to finish its work on cell (0 = none)."""
        ob = ob or self.cur
        o = ob.owner[cell]
        if o == seat:
            if ob.up[cell]:
                return 0
            return 3
        if o == 0:
            return 1
        if ob.home[cell]:
            return 0
        return 3 if ob.up[cell] else 1

    def holder(self):
        if self.holder_set and len(self.holder_set) == 1:
            return next(iter(self.holder_set))
        return None

    def income_of(self, ob):
        inc = [0] * 5
        for p in range(64):
            o = ob.owner[p]
            if o:
                inc[o] += ob.base[p] * (2 if ob.up[p] else 1)
        return inc

    # ------------------------------------------------------------------
    def update(self, ob, me, token, my_legal, my_last, hint=None):
        """Advance to the new board. hint: optional callable(seat) -> P(shielded)."""
        new_game = False
        P = self.prev
        if P is None or me != self.me:
            new_game = True
        else:
            if ob.owned_count() < P.owned_count():
                new_game = True
            elif ob.pristine() and (self.turn >= 80 or any(P.up) or P.owned_count() > 4):
                new_game = True
            elif self.turn >= 80:
                new_game = True
            else:
                for s in (1, 2, 3, 4):
                    a, b = P.pos[s], ob.pos[s]
                    if a < 0 or b < 0 or (a != b and b not in NEIGHB[a]):
                        new_game = True
                        break
        if new_game:
            self.me = me
            self.seen = 1
            self.reset_counts()
            self.cur = ob
            self.known_start = ob.pristine()
            if self.known_start:
                self.turn = 1
            else:
                self.turn = self.estimate_turn(ob)
                inc = self.income_of(ob)
                for s in (1, 2, 3, 4):
                    self.score[s] = int(inc[s] * (self.turn - 1) * 0.55)
                    self.fl[s] = 1 if ob.frz[s] else 0
            self.holder_set = set([me]) if token else set(s for s in (1, 2, 3, 4) if s != me)
            self.prev = ob
            self.check_own(ob, me, my_legal)
            return True
        self.cur = ob
        self.turn += 1
        self.seen += 1
        self.resolve(P, ob, me, my_last, my_legal, hint)
        allowed = set([me]) if token else set(s for s in (1, 2, 3, 4) if s != me)
        shifted = set(s % 4 + 1 for s in (self.holder_set or (1, 2, 3, 4))) & allowed
        self.holder_set = shifted or allowed
        self.prev = ob
        self.check_own(ob, me, my_legal)
        return False

    def estimate_turn(self, ob):
        claimed = ob.owned_count() - 4
        ups = sum(ob.up)
        t = 2 + 0.75 * claimed + 1.4 * ups
        return int(max(2, min(70, round(t))))

    def check_own(self, ob, me, my_legal):
        """My own legal list pins my own cooldown and freeze exactly."""
        if my_legal is None:
            return
        frozen_now = ob.frz[me]
        if frozen_now and len(my_legal) == 1:
            if self.fl[me] == 0:
                self.fl[me] = 2
        elif not frozen_now:
            self.fl[me] = 0
        if not frozen_now:
            if "SHIELD" in my_legal:
                self.cd[me] = 0
                self.cdmin[me] = 0
            else:
                if self.cd[me] == 0:
                    self.cd[me] = 1
                self.cdmin[me] = max(self.cdmin[me], 1)

    # ------------------------------------------------------------------
    def resolve(self, P, B, me, my_last, my_legal_prev, hint):
        moved = [False] * 5
        for s in (1, 2, 3, 4):
            moved[s] = B.pos[s] != P.pos[s]
        nf = set(s for s in (1, 2, 3, 4) if B.frz[s] and self.fl[s] == 0)
        lost = [False] * 5
        bonus = [0] * 5
        events = []
        for p in range(64):
            a, b = P.owner[p], B.owner[p]
            if a != b:
                if a:
                    lost[a] = True
                    bonus[b] += 8 * P.base[p] * (2 if P.up[p] else 1)
                    events.append(("raid", p, b, a, P.up[p]))
                else:
                    events.append(("claim", p, b, 0, 0))
            elif B.up[p] and not P.up[p] and b:
                events.append(("upgrade", p, b, 0, 0))
        self.events = events
        # ---- who shielded? -------------------------------------------------
        my_shield = (my_last == "SHIELD" and self.fl[me] == 0 and self.cd[me] == 0)
        cand = [s for s in (1, 2, 3, 4) if s != me and not moved[s] and self.fl[s] == 0
                and not lost[s] and self.cdmin[s] == 0]
        sols = []
        for mask in range(1 << len(cand)):
            S = set(cand[k] for k in range(len(cand)) if mask >> k & 1)
            if my_shield:
                S.add(me)
            pred = set()
            catches = dict((s, False) for s in S)
            for j in (1, 2, 3, 4):
                if self.fl[j] > 0 or moved[j] or j in S:
                    continue
                o = P.owner[P.pos[j]]
                if o in S and o != j:
                    pred.add(j)
                    catches[o] = True
            for s in S:
                if not catches[s]:
                    pred.add(s)
            if pred == nf:
                sols.append(S)
        if not sols and my_shield:
            # perhaps my shield was turned into a STAY by the server
            my_shield = False
            for mask in range(1 << len(cand)):
                S = set(cand[k] for k in range(len(cand)) if mask >> k & 1)
                pred = set()
                catches = dict((s, False) for s in S)
                for j in (1, 2, 3, 4):
                    if self.fl[j] > 0 or moved[j] or j in S:
                        continue
                    o = P.owner[P.pos[j]]
                    if o in S and o != j:
                        pred.add(j)
                        catches[o] = True
                for s in S:
                    if not catches[s]:
                        pred.add(s)
                if pred == nf:
                    sols.append(S)
        if sols:
            def plaus(S):
                sc = 0.0
                for s in S:
                    hit = False
                    for j in (1, 2, 3, 4):
                        if j != s and j not in S and self.fl[j] == 0 and not moved[j] \
                                and P.owner[P.pos[j]] == s:
                            hit = True
                    sc -= 0.5 if hit else (2.0 - self.rogue[s])
                    o = P.owner[P.pos[s]]
                    if o not in (0, s):
                        sc -= 1.0          # shielding while standing on rival land
                if hint is not None:
                    for s in (1, 2, 3, 4):
                        if s == me:
                            continue
                        h = hint(s)
                        if h is None:
                            continue
                        if (s in S) == (h > 0.5):
                            sc += 6.0 * abs(h - 0.5) * 2
                        else:
                            sc -= 6.0 * abs(h - 0.5) * 2
                return sc
            best = max(sols, key=plaus)
            union = set().union(*sols)
            inter = set(sols[0]).intersection(*sols[1:]) if len(sols) > 1 else set(sols[0])
            amb = union - inter
        else:
            # inconsistent: fall back to the simplest reading
            best = set()
            for s in nf:
                o = P.owner[P.pos[s]] if not moved[s] else 0
                if o in (0, s):
                    best.add(s)
                elif o != me and not moved[o] and self.fl[o] == 0:
                    best.add(o)
            if my_shield:
                best.add(me)
            inter = set(best)
            amb = set()
        for s in inter:
            if s != me and s in nf:
                self.rogue[s] = min(1.4, self.rogue[s] + 0.35)
        self.shielded = best
        self.amb = amb
        self.caught = set(s for s in nf if s not in best)
        # ---- cooldowns, freezes ---------------------------------------------
        for s in (1, 2, 3, 4):
            if s in best:
                self.cd[s] = 4
            else:
                self.cd[s] = max(0, self.cd[s] - 1)
            if s in inter:
                self.cdmin[s] = 4
            else:
                self.cdmin[s] = max(0, self.cdmin[s] - 1)
            if s in nf:
                self.fl[s] = 2
            else:
                self.fl[s] = max(0, self.fl[s] - 1)
                if B.frz[s] and self.fl[s] == 0:
                    self.fl[s] = 1
                if not B.frz[s]:
                    self.fl[s] = 0
        # ---- progress ---------------------------------------------------------
        done = {}
        for kind, p, s, frm, wu in events:
            done[s] = (kind, p, frm, wu)
        resets = self.claim_resets()
        for s in (1, 2, 3, 4):
            if moved[s] or s in best or s in nf or P.frz[s]:
                self.prog[s] = 0
                self.since[s] = 0
                self.last_done[s] = None
                continue
            self.since[s] += 1
            p = B.pos[s]
            o = P.owner[p]
            if s in done and done[s][1] == p:
                kind, _p, frm, wu = done[s]
                if kind == "upgrade":
                    # evidence about the carry-over rule: stays since the claim
                    ld = self.last_done[s]
                    if ld is not None and ld[1] == p and ld[0] == "claim":
                        if self.since[s] == 2:
                            self.carry_ev += 1
                        elif self.since[s] == 3:
                            self.reset_ev += 1
                    self.prog[s] = 0
                else:
                    need = 3 if wu else 1
                    if resets:
                        self.prog[s] = 0
                    else:
                        self.prog[s] = min(2, need if kind == "raid" else 1)
                self.last_done[s] = (kind, p)
                self.since[s] = 0
                continue
            if o == s:
                if P.up[p]:
                    continue
                self.prog[s] = min(self.prog[s] + 1, 2)
            elif o == 0:
                self.prog[s] = 0       # a stay on neutral land always claims it
            else:
                if P.home[p]:
                    continue
                need = 3 if P.up[p] else 1
                self.prog[s] = min(self.prog[s] + 1, need - 1)
        # ---- scores ------------------------------------------------------------
        inc = self.income_of(B)
        for s in (1, 2, 3, 4):
            self.score[s] += inc[s] + bonus[s]
        self.last_lost = [p for kind, p, s, frm, wu in events if kind == "raid" and frm == me]
