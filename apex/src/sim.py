"""Compact rules engine for in-bot rollouts (development module).

Same resolution order as the rulebook / engine.py with the confirmed rules:
frozen stays earn nothing, claims reset progress, lost contests and blocked
moves count as STAY, a shield is not a stay, homes are upgradable and never fall.
"""

_STEP = {"NORTH": -8, "SOUTH": 8, "WEST": -1, "EAST": 1}


class SimState(object):
    __slots__ = ("base", "home", "owner", "up", "pos", "fl", "cd", "prog", "score",
                 "turn", "token", "resets")

    def copy(self):
        s = SimState.__new__(SimState)
        s.base = self.base
        s.home = self.home
        s.owner = self.owner[:]
        s.up = self.up[:]
        s.pos = self.pos[:]
        s.fl = self.fl[:]
        s.cd = self.cd[:]
        s.prog = self.prog[:]
        s.score = self.score[:]
        s.turn = self.turn
        s.token = self.token
        s.resets = self.resets
        return s


def sim_legal(st, s):
    if st.fl[s] > 0:
        return ["STAY"]
    p = st.pos[s]
    r, c = divmod(p, 8)
    out = []
    if r > 0:
        out.append("NORTH")
    if c < 7:
        out.append("EAST")
    if r < 7:
        out.append("SOUTH")
    if c > 0:
        out.append("WEST")
    out.append("STAY")
    if st.cd[s] == 0:
        out.append("SHIELD")
    return out


def sim_step(st, acts):
    """acts[s] for s in 1..4 (index 0 unused). Mutates st."""
    eff = [None] * 5
    pos = st.pos
    for s in (1, 2, 3, 4):
        if st.fl[s] > 0:
            eff[s] = "STAY"
            continue
        a = acts[s]
        if a == "SHIELD":
            eff[s] = "STAY" if st.cd[s] > 0 else "SHIELD"
        elif a in _STEP:
            r, c = divmod(pos[s], 8)
            if (a == "NORTH" and r == 0) or (a == "SOUTH" and r == 7) or \
                    (a == "WEST" and c == 0) or (a == "EAST" and c == 7):
                eff[s] = "STAY"
            else:
                eff[s] = a
        else:
            eff[s] = "STAY"
    closed = (pos[1], pos[2], pos[3], pos[4])
    intents = {}
    for s in (1, 2, 3, 4):
        a = eff[s]
        if a in _STEP:
            t = pos[s] + _STEP[a]
            if t in closed:
                eff[s] = "STAY"
            else:
                intents.setdefault(t, []).append(s)
    for t, seats in intents.items():
        if len(seats) == 1:
            w = seats[0]
        else:
            w = None
            for s in seats:
                if st.owner[t] == s:
                    w = s
                    break
            if w is None:
                best = 99
                for s in seats:
                    rank = (s - st.token) % 4
                    if rank < best:
                        best, w = rank, s
            for s in seats:
                if s != w:
                    eff[s] = "STAY"
        pos[w] = t
        st.prog[w] = 0
    shielders = []
    for s in (1, 2, 3, 4):
        if eff[s] == "SHIELD":
            st.prog[s] = 0
            shielders.append(s)
    caught = [False] * 5
    newfrozen = [0] * 5
    owner = st.owner
    for s in shielders:
        got = False
        for j in (1, 2, 3, 4):
            if j == s or st.fl[j] > 0 or eff[j] != "STAY":
                continue
            if owner[pos[j]] == s:
                caught[j] = True
                newfrozen[j] = 2
                st.prog[j] = 0
                got = True
        if not got:
            newfrozen[s] = 2
    up = st.up
    base = st.base
    for s in (1, 2, 3, 4):
        if eff[s] != "STAY" or caught[s] or st.fl[s] > 0:
            continue
        p = pos[s]
        o = owner[p]
        if o == s:
            if up[p]:
                continue
            st.prog[s] += 1
            if st.prog[s] >= 3:
                up[p] = 1
                st.prog[s] = 0
        elif o == 0:
            owner[p] = s
            st.prog[s] = 0 if st.resets else 1
        else:
            if st.home[p] or o in shielders:
                continue
            need = 3 if up[p] else 1
            st.prog[s] += 1
            if st.prog[s] >= need:
                st.score[s] += 8 * base[p] * (2 if up[p] else 1)
                owner[p] = s
                up[p] = 0
                st.prog[s] = 0 if st.resets else need
    inc = [0] * 5
    for p in range(64):
        o = owner[p]
        if o:
            inc[o] += base[p] * (2 if up[p] else 1)
    for s in (1, 2, 3, 4):
        st.score[s] += inc[s]
        if st.fl[s] > 0:
            st.fl[s] -= 1
        if newfrozen[s]:
            st.fl[s] = newfrozen[s]
            st.prog[s] = 0
        if s in shielders:
            st.cd[s] = 4
        elif st.cd[s] > 0:
            st.cd[s] -= 1
    st.token = st.token % 4 + 1
    st.turn += 1
    return eff
