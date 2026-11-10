"""
Zone Rush -- exact rules engine, reimplemented from the official StrategyBot rulebook
(Sections 2.1-2.8) plus the starter-kit README at github.com/RedPokerJoker123/StrategyBot.

No reference engine ships with the starter kit, so several rule details are genuinely
ambiguous. Every one of them is a flag in RULES below so both readings can be tested.
"""
import random as _outsim_random
_outsim_N = 8
_outsim_NC = 64
_outsim_ACTIONS = ('NORTH', 'EAST', 'SOUTH', 'WEST', 'STAY', 'SHIELD')
_outsim_MOVES = {'NORTH': -_outsim_N, 'SOUTH': _outsim_N, 'WEST': -1, 'EAST': 1}
_outsim_CORNERS = {1: 0, 2: _outsim_N - 1, 3: _outsim_NC - 1, 4: _outsim_NC - _outsim_N}
_outsim_RULES = {'frozen_stay_counts': False, 'claim_resets_progress': True, 'catch_requires_stay': True, 'lost_contest_is_stay': True, 'home_upgradable': True}

def _outsim_make_map(seed=None, canonical=False):
    """8x8 point map, 4-fold mirrored, values 1..3, higher toward the middle."""
    if canonical or seed is None:
        q = [[1, 1, 1, 2], [1, 1, 2, 2], [1, 2, 2, 3], [2, 2, 3, 3]]
    else:
        rnd = _outsim_random.Random(seed)
        slope = rnd.uniform(0.33, 0.58)
        noise = rnd.uniform(0.25, 0.75)
        q = []
        for r in range(4):
            row = []
            for c in range(4):
                d = 3 - r + (3 - c)
                v = 3.0 - d * slope + rnd.uniform(-noise, noise)
                row.append(max(1, min(3, int(round(v)))))
            q.append(row)
        q[0][0] = min(q[0][0], 2)
    base = [0] * _outsim_NC
    for r in range(4):
        for c in range(4):
            v = q[r][c]
            base[r * _outsim_N + c] = v
            base[r * _outsim_N + (_outsim_N - 1 - c)] = v
            base[(_outsim_N - 1 - r) * _outsim_N + c] = v
            base[(_outsim_N - 1 - r) * _outsim_N + (_outsim_N - 1 - c)] = v
    return base

class _outsim_Cell(object):
    """Exactly the fields the starter kit documents -- nothing else is visible."""
    __slots__ = ('occupant', 'owner', 'is_upgraded', 'is_home', 'is_frozen', 'base_points')

    def __init__(self, occupant, owner, is_upgraded, is_home, is_frozen, base_points):
        self.occupant = occupant
        self.owner = owner
        self.is_upgraded = is_upgraded
        self.is_home = is_home
        self.is_frozen = is_frozen
        self.base_points = base_points

class _outsim_View(object):
    """The `state` object handed to act(). Mirrors the starter kit's class Game."""
    __slots__ = ('board', 'bot_id', 'is_priority_token', 'legal_actions')

    def __init__(self, board, bot_id, is_priority_token, legal_actions):
        self.board = board
        self.bot_id = bot_id
        self.is_priority_token = is_priority_token
        self.legal_actions = legal_actions

class _outsim_Game(object):
    __slots__ = ('base', 'owner', 'upg', 'home', 'pos', 'frozen', 'cd', 'prog', 'score', 'income', 'turn', 'token', 'max_turns', 'rules')

    def __init__(self, base=None, max_turns=80, rules=None, start_token=1):
        self.base = list(base if base is not None else _outsim_make_map(canonical=True))
        self.owner = [0] * _outsim_NC
        self.upg = [0] * _outsim_NC
        self.home = [0] * _outsim_NC
        self.pos = [0] * 4
        self.frozen = [0] * 4
        self.cd = [0] * 4
        self.prog = [0] * 4
        self.score = [0] * 4
        self.income = [0] * 4
        self.turn = 1
        self.max_turns = max_turns
        self.token = start_token
        self.rules = dict(_outsim_RULES)
        if rules:
            self.rules.update(rules)
        for seat, cell in _outsim_CORNERS.items():
            self.home[cell] = seat
            self.owner[cell] = seat
            self.pos[seat - 1] = cell
            self.income[seat - 1] = self.base[cell]

    def clone(self):
        g = _outsim_Game.__new__(_outsim_Game)
        g.base = self.base
        g.owner = self.owner[:]
        g.upg = self.upg[:]
        g.home = self.home
        g.pos = self.pos[:]
        g.frozen = self.frozen[:]
        g.cd = self.cd[:]
        g.prog = self.prog[:]
        g.score = self.score[:]
        g.income = self.income[:]
        g.turn = self.turn
        g.token = self.token
        g.max_turns = self.max_turns
        g.rules = self.rules
        return g

    def legal(self, i):
        if self.frozen[i] > 0:
            return ['STAY']
        out = ['STAY']
        r, c = divmod(self.pos[i], _outsim_N)
        if r > 0:
            out.append('NORTH')
        if r < _outsim_N - 1:
            out.append('SOUTH')
        if c > 0:
            out.append('WEST')
        if c < _outsim_N - 1:
            out.append('EAST')
        if self.cd[i] == 0:
            out.append('SHIELD')
        return out

    def board_view(self):
        occ = [0] * _outsim_NC
        frz = [False] * _outsim_NC
        for i in range(4):
            occ[self.pos[i]] = i + 1
            if self.frozen[i] > 0:
                frz[self.pos[i]] = True
        bd = []
        for r in range(_outsim_N):
            row = []
            for c in range(_outsim_N):
                p = r * _outsim_N + c
                row.append(_outsim_Cell(occ[p], self.owner[p], bool(self.upg[p]), bool(self.home[p]), frz[p], self.base[p]))
            bd.append(row)
        return bd

    def views(self):
        bd = self.board_view()
        return [_outsim_View(bd, i + 1, self.token == i + 1, self.legal(i)) for i in range(4)]

    def step(self, actions):
        """actions[i] is seat i+1's chosen action string. Resolves one full turn."""
        R = self.rules
        eff = [None] * 4
        for i in range(4):
            if self.frozen[i] > 0:
                eff[i] = 'STAY'
                continue
            a = actions[i]
            if a == 'SHIELD':
                eff[i] = 'STAY' if self.cd[i] > 0 else 'SHIELD'
            elif a in _outsim_MOVES:
                r, c = divmod(self.pos[i], _outsim_N)
                if a == 'NORTH' and r == 0 or (a == 'SOUTH' and r == _outsim_N - 1) or (a == 'WEST' and c == 0) or (a == 'EAST' and c == _outsim_N - 1):
                    eff[i] = 'STAY'
                else:
                    eff[i] = a
            else:
                eff[i] = 'STAY'
        closed = set(self.pos)
        intents = {}
        for i in range(4):
            if eff[i] in _outsim_MOVES:
                t = self.pos[i] + _outsim_MOVES[eff[i]]
                if t in closed:
                    eff[i] = 'STAY'
                else:
                    intents.setdefault(t, []).append(i)
        for t, seats in intents.items():
            if len(seats) == 1:
                w = seats[0]
            else:
                own = [s for s in seats if self.owner[t] == s + 1]
                if own:
                    w = own[0]
                else:
                    w, best = (seats[0], 99)
                    for s in seats:
                        rank = (s + 1 - self.token) % 4
                        if rank < best:
                            best, w = (rank, s)
                for s in seats:
                    if s != w:
                        eff[s] = 'STAY' if R['lost_contest_is_stay'] else 'BLOCKED'
            self.pos[w] = t
            self.prog[w] = 0
        for i in range(4):
            if eff[i] == 'SHIELD':
                self.prog[i] = 0
        shielders = [i for i in range(4) if eff[i] == 'SHIELD']
        caught = [False] * 4
        newfrozen = [0] * 4
        for s in shielders:
            seat = s + 1
            got = []
            for j in range(4):
                if j == s or self.frozen[j] > 0:
                    continue
                if R['catch_requires_stay'] and eff[j] != 'STAY':
                    continue
                if self.owner[self.pos[j]] == seat:
                    got.append(j)
            if got:
                for j in got:
                    caught[j] = True
                    newfrozen[j] = 2
                    self.prog[j] = 0
            else:
                newfrozen[s] = 2
        shielded_seats = set((s + 1 for s in shielders))
        for i in range(4):
            if eff[i] != 'STAY' or caught[i]:
                continue
            if self.frozen[i] > 0 and (not R['frozen_stay_counts']):
                continue
            p = self.pos[i]
            seat = i + 1
            o = self.owner[p]
            if o == seat:
                if self.upg[p]:
                    continue
                if self.home[p] == seat and (not R['home_upgradable']):
                    continue
                self.prog[i] += 1
                if self.prog[i] >= 3:
                    self.upg[p] = 1
                    self.prog[i] = 0
                    self.income[i] += self.base[p]
            elif o == 0:
                self.prog[i] += 1
                if self.prog[i] >= 1:
                    self.owner[p] = seat
                    self.income[i] += self.base[p]
                    if R['claim_resets_progress']:
                        self.prog[i] = 0
            else:
                if self.home[p] or o in shielded_seats:
                    continue
                needed = 3 if self.upg[p] else 1
                self.prog[i] += 1
                if self.prog[i] >= needed:
                    lvl = 2 if self.upg[p] else 1
                    self.score[i] += 8 * self.base[p] * lvl
                    self.income[o - 1] -= self.base[p] * lvl
                    self.owner[p] = seat
                    self.upg[p] = 0
                    self.income[i] += self.base[p]
                    if R['claim_resets_progress']:
                        self.prog[i] = 0
        for i in range(4):
            self.score[i] += self.income[i]
        for i in range(4):
            if self.frozen[i] > 0:
                self.frozen[i] -= 1
            if newfrozen[i]:
                self.frozen[i] = newfrozen[i]
                self.prog[i] = 0
        for i in range(4):
            if i in shielders:
                self.cd[i] = 4
            elif self.cd[i] > 0:
                self.cd[i] -= 1
        self.token = self.token % 4 + 1
        self.turn += 1
        return eff

    def over(self):
        return self.turn > self.max_turns

    def cells_owned(self, i):
        seat = i + 1
        n = 0
        for p in range(_outsim_NC):
            if self.owner[p] == seat:
                n += 1
        return n

    def places(self):
        """1-based place per seat; equal (score, cells) share a place."""
        key = [(-self.score[i], -self.cells_owned(i)) for i in range(4)]
        order = sorted(range(4), key=lambda i: key[i])
        place = [0.0] * 4
        i = 0
        while i < 4:
            j = i
            while j + 1 < 4 and key[order[j + 1]] == key[order[i]]:
                j += 1
            shared = (i + 1 + j + 1) / 2.0
            for k in range(i, j + 1):
                place[order[k]] = shared
            i = j + 1
        return place

def _outsim_play(bots, base=None, max_turns=80, rules=None, start_token=1):
    """bots[i] is a callable act(view) for seat i+1. Returns the finished Game."""
    g = _outsim_Game(base=base, max_turns=max_turns, rules=rules, start_token=start_token)
    while not g.over():
        vs = g.views()
        acts = []
        for i in range(4):
            try:
                a = bots[i](vs[i])
            except Exception:
                a = 'STAY'
            if a not in vs[i].legal_actions:
                a = 'STAY'
            acts.append(a)
        g.step(acts)
    return g

"""
Outsiders: opponent designs that are NOT in this repository.

Every bot the shipped bot was tuned and measured against was written inside this
repository, by the same hand that wrote the bot. These eight were written for the
audit from the rulebook and the starter-kit README alone, share no code with
zoo.py / aifield.py / holdout.py / probot.py, and each one is built around an idea
the existing field does not contain:

  x_fort      Perfect-timing defender. Claims AND upgrades a compact cluster, and
              shields only at the one moment that matters: a rival's third stay on
              an UPGRADED cell. (2 frozen turns + 3 stays = 5 > 4-turn cooldown, so
              an upgraded cell can be held forever this way.) Never raids.
  x_leech     Patient level-1 raider. Takes rival level-1 cells (1 stay, 8 x v
              bonus) and never bails -- not even after being frozen, because the
              freeze (2) plus its single stay (1) is shorter than the cooldown (4).
  x_homebait  Home baiter. Farms, then steps onto a rival's HOME (which can never be
              taken) and straight off again to make the rival's shield backfire;
              raids that rival during the cooldown window. If baits stop working it
              raids directly.
  x_jackal    Trails the leader and steals its fresh level-1 claims, preferring
              owners that are on cooldown or frozen.
  x_vulture   Farms for 58 turns, then raids upgraded rival cells (16 x v bonus,
              which never decays) and shields for free on the last turn.
  x_flaky     A decent farmer that behaves like a real broken entry: 20% of turns
              lost to timeouts, occasional illegal strings, and a 30% chance of
              crashing for good partway through.
  x_literal   The single-prompt "first attempt": scores every target by points per
              turn of effort with the raid bonus included, raids eagerly, and
              shields on sight whenever a rival stands on a non-home cell it owns.
  x_sim       A different architecture: no hand-written plan at all. For each legal
              action it runs short random rollouts through a rules simulator and
              picks the action with the best simulated outcome.

All of them follow the starter-kit contract exactly: act on `view` (board,
bot_id, is_priority_token, legal_actions), return one string from legal_actions.
"""
import random as _out_random
_out_N = 8
_out_NC = 64
_out_NB = []
for _out__p in range(_out_NC):
    _out__r, _out__c = divmod(_out__p, _out_N)
    _out__o = []
    if _out__r > 0:
        _out__o.append(('NORTH', _out__p - _out_N))
    if _out__r < _out_N - 1:
        _out__o.append(('SOUTH', _out__p + _out_N))
    if _out__c > 0:
        _out__o.append(('WEST', _out__p - 1))
    if _out__c < _out_N - 1:
        _out__o.append(('EAST', _out__p + 1))
    _out_NB.append(tuple(_out__o))

def _out_manh(a, b):
    ar, ac = divmod(a, _out_N)
    br, bc = divmod(b, _out_N)
    return abs(ar - br) + abs(ac - bc)

class _out_Board(object):
    """The view, flattened. Reads only the six documented Cell attributes."""

    def __init__(self, view):
        bd = view.board
        if bd and isinstance(bd[0], (list, tuple)):
            cells = [bd[r][c] for r in range(_out_N) for c in range(_out_N)]
        else:
            cells = list(bd)
        self.base = [c.base_points for c in cells]
        self.owner = [c.owner for c in cells]
        self.upg = [bool(c.is_upgraded) for c in cells]
        self.home = [bool(c.is_home) for c in cells]
        self.occ = [c.occupant for c in cells]
        self.frz = [bool(c.is_frozen) for c in cells]
        self.seat = view.bot_id
        self.pos = [None] * 4
        for p in range(_out_NC):
            if self.occ[p]:
                self.pos[self.occ[p] - 1] = p
        self.me = self.pos[self.seat - 1]
        self.homes = [None] * 4
        for p in range(_out_NC):
            if self.home[p] and self.owner[p]:
                self.homes[self.owner[p] - 1] = p

    def blocked(self):
        return set((p for p in range(_out_NC) if self.occ[p] and p != self.me))

    def dist(self, src, avoid=None):
        avoid = self.blocked() if avoid is None else avoid
        d = [99] * _out_NC
        d[src] = 0
        q = [src]
        i = 0
        while i < len(q):
            u = q[i]
            i += 1
            for _nm, w in _out_NB[u]:
                if d[w] == 99 and w not in avoid:
                    d[w] = d[u] + 1
                    q.append(w)
        return d

    def step_to(self, target, rnd=None):
        if target is None or target == self.me:
            return 'STAY'
        blk = self.blocked()
        d = self.dist(target, blk - {target})
        opts = [(d[w], nm) for nm, w in _out_NB[self.me] if w not in blk and d[w] < 99]
        if not opts:
            opts = [(_out_manh(w, target), nm) for nm, w in _out_NB[self.me] if w not in blk]
        if not opts:
            return 'STAY'
        best = min((o[0] for o in opts))
        names = [nm for dd, nm in opts if dd == best]
        if rnd is not None and len(names) > 1:
            return rnd.choice(names)
        return names[0]

    def zone(self, p):
        """Seat (1-4) whose home is nearest to p."""
        best, bd = (0, 99)
        for s in range(4):
            h = self.homes[s]
            if h is None:
                continue
            dd = _out_manh(p, h)
            if dd < bd:
                bd, best = (dd, s + 1)
        return best

    def rivals_on_my_land(self):
        out = []
        for j in range(4):
            p = self.pos[j]
            if j == self.seat - 1 or p is None or self.frz[p]:
                continue
            if self.owner[p] == self.seat:
                out.append((j, p))
        return out

class _out_Watch(object):
    """Shield cooldowns and consecutive stays, rebuilt from board diffs."""

    def __init__(self):
        self.prev = None
        self.cd = [0] * 4
        self.stays = [0] * 4

    def update(self, b):
        if self.prev is not None:
            ppos, powner, pfrz = self.prev
            for i in range(4):
                if self.cd[i] > 0:
                    self.cd[i] -= 1
            for j in range(4):
                p, pp = (b.pos[j], ppos[j])
                if p is None or pp is None:
                    continue
                was = pfrz[j]
                now = b.frz[p]
                if now and (not was):
                    o = powner[pp]
                    if pp == p and o and (o != j + 1):
                        self.cd[o - 1] = 4
                    else:
                        self.cd[j] = 4
                if p == pp and (not was) and (not now):
                    self.stays[j] += 1
                else:
                    self.stays[j] = 0
        self.prev = (b.pos[:], b.owner[:], [b.frz[b.pos[j]] if b.pos[j] is not None else False for j in range(4)])

    def ready(self, b, j):
        """Can seat index j shield this turn?"""
        p = b.pos[j]
        return self.cd[j] == 0 and (not (p is not None and b.frz[p]))

class _out_Outsider(object):
    name = 'x_base'

    def __init__(self, seed=0):
        self.rnd = _out_random.Random(seed)
        self.t = 0
        self.watch = _out_Watch()

    def __call__(self, view):
        self.t += 1
        try:
            a = self.act(view)
        except Exception:
            a = 'STAY'
        return a if a in view.legal_actions else 'STAY'

    def R(self):
        return 81 - self.t

    def farm(self, b, upgrade_min=3):
        me, seat, R = (b.me, b.seat, self.R())
        o = b.owner[me]
        if o == 0 and (not b.home[me]):
            return 'STAY'
        if o == seat and (not b.upg[me]) and (b.base[me] >= upgrade_min) and (R > 3):
            return 'STAY'
        d = b.dist(me)
        best, bs = (None, 0.0)
        for p in range(_out_NC):
            if d[p] >= 99 or b.occ[p] or b.home[p] or (b.owner[p] != 0):
                continue
            s = b.base[p] * max(0, R - d[p] - 1) / float(d[p] + 1)
            if s > bs:
                bs, best = (s, p)
        if best is None:
            for p in range(_out_NC):
                if d[p] >= 99 or b.occ[p] or b.owner[p] != seat or b.upg[p]:
                    continue
                s = b.base[p] * max(0, R - d[p] - 3) / float(d[p] + 3)
                if s > bs:
                    bs, best = (s, p)
        return b.step_to(best, self.rnd)

    def timed_shield(self, b, legal, on_l1=False):
        """Shield only when it decides something: a third stay on an upgraded
        cell, (optionally) any stay on a level-1 cell, or anything on turn 80."""
        if 'SHIELD' not in legal:
            return False
        for j, p in b.rivals_on_my_land():
            if self.R() <= 1 and (not b.home[p]):
                return True
            if b.home[p]:
                continue
            if b.upg[p] and self.watch.stays[j] >= 2:
                return True
            if on_l1 and (not b.upg[p]):
                return True
        return False

class _out_Fort(_out_Outsider):
    name = 'x_fort'

    def act(self, view):
        b = _out_Board(view)
        self.watch.update(b)
        if self.timed_shield(b, view.legal_actions):
            return 'SHIELD'
        me, seat, R = (b.me, b.seat, self.R())
        o = b.owner[me]
        if o == 0 and (not b.home[me]) and (b.zone(me) == seat):
            return 'STAY'
        if o == seat and (not b.upg[me]) and (R > 3):
            return 'STAY'
        d = b.dist(me)
        best, bs = (None, 0.0)
        for p in range(_out_NC):
            if d[p] >= 99 or b.occ[p] or b.zone(p) != seat:
                continue
            if b.owner[p] == 0 and (not b.home[p]):
                need = 4
            elif b.owner[p] == seat and (not b.upg[p]):
                need = 3
            else:
                continue
            s = b.base[p] * max(0, R - d[p] - need) / float(d[p] + need)
            if s > bs:
                bs, best = (s, p)
        if best is None:
            best = max((p for p in range(_out_NC) if b.owner[p] == seat), key=lambda p: (b.base[p] * (2 if b.upg[p] else 1), -d[p]))
        return b.step_to(best, self.rnd)

class _out_Leech(_out_Outsider):
    name = 'x_leech'

    def act(self, view):
        b = _out_Board(view)
        self.watch.update(b)
        me, seat, R = (b.me, b.seat, self.R())
        o = b.owner[me]
        if o and o != seat and (not b.home[me]) and (not b.upg[me]):
            return 'STAY'
        if o == 0 and (not b.home[me]):
            return 'STAY'
        d = b.dist(me)
        best, bs = (None, 0.0)
        for p in range(_out_NC):
            if d[p] >= 99 or b.occ[p] or b.home[p]:
                continue
            op = b.owner[p]
            if op == seat or (op and b.upg[p]):
                continue
            rem = max(0, R - d[p] - 1)
            val = 8 * b.base[p] + b.base[p] * rem if op else 0.6 * b.base[p] * rem
            s = val / float(d[p] + 1)
            if s > bs:
                bs, best = (s, p)
        return b.step_to(best, self.rnd)

class _out_HomeBait(_out_Outsider):
    name = 'x_homebait'

    def __init__(self, seed=0):
        _out_Outsider.__init__(self, seed)
        self.victim = None
        self.fails = 0
        self.pending = False
        self.arrived = False
        self.last_pos = None

    def act(self, view):
        b = _out_Board(view)
        self.watch.update(b)
        me, seat, R = (b.me, b.seat, self.R())
        just_moved = self.last_pos is not None and me != self.last_pos
        self.last_pos = me
        if self.timed_shield(b, view.legal_actions):
            return 'SHIELD'
        if self.t <= 20 or R <= 2:
            return self.farm(b)
        if self.victim is None:
            rivals = [j for j in range(4) if j != seat - 1 and b.homes[j] is not None]
            self.victim = min(rivals, key=lambda j: _out_manh(me, b.homes[j]))
        v = self.victim
        if self.pending:
            self.pending = False
            if self.watch.ready(b, v):
                self.fails += 1
        open_window = not self.watch.ready(b, v)
        on_v = b.owner[me] == v + 1
        if open_window or self.fails >= 2:
            if on_v and (not b.home[me]):
                return 'STAY'
            d = b.dist(me)
            best, bs = (None, 0.0)
            for p in range(_out_NC):
                if d[p] >= 99 or b.occ[p] or b.home[p] or (b.owner[p] != v + 1):
                    continue
                need = 3 if b.upg[p] else 1
                if open_window and d[p] + need > self.watch.cd[v] + 1 and (self.fails < 2):
                    continue
                s = 8.0 * b.base[p] * (2 if b.upg[p] else 1) / (d[p] + need)
                if s > bs:
                    bs, best = (s, p)
            if best is not None and (open_window or d[best] <= 4):
                return b.step_to(best, self.rnd)
            return self.farm(b)
        if on_v and just_moved:
            for nm, w in _out_NB[me]:
                if not b.occ[w] and b.owner[w] != v + 1:
                    self.pending = True
                    return nm
            return 'STAY'
        vh = b.homes[v]
        spot = vh if vh is not None and _out_manh(me, vh) <= 3 and (not b.occ[vh]) else None
        if spot is None:
            d = b.dist(me)
            cands = [p for p in range(_out_NC) if b.owner[p] == v + 1 and (not b.occ[p]) and (d[p] <= 4)]
            if not cands:
                return self.farm(b)
            spot = min(cands, key=lambda p: d[p])
        return b.step_to(spot, self.rnd)

class _out_Jackal(_out_Outsider):
    name = 'x_jackal'

    def act(self, view):
        b = _out_Board(view)
        self.watch.update(b)
        legal = view.legal_actions
        if self.timed_shield(b, legal):
            return 'SHIELD'
        if 'SHIELD' in legal and b.rivals_on_my_land() and (self.rnd.random() < 0.3):
            return 'SHIELD'
        me, seat, R = (b.me, b.seat, self.R())
        inc = [0] * 4
        for p in range(_out_NC):
            if b.owner[p]:
                inc[b.owner[p] - 1] += b.base[p] * (2 if b.upg[p] else 1)
        leader = max((j for j in range(4) if j != seat - 1), key=lambda j: inc[j])
        o = b.owner[me]
        if o and o != seat and (not b.home[me]) and (not b.upg[me]):
            return 'STAY'
        d = b.dist(me)
        best, bs = (None, 0.0)
        for p in range(_out_NC):
            op = b.owner[p]
            if d[p] >= 99 or b.occ[p] or b.home[p] or (not op) or (op == seat) or b.upg[p]:
                continue
            s = (8.0 * b.base[p] + b.base[p] * max(0, R - d[p] - 1)) / (d[p] + 1)
            if op - 1 == leader:
                s *= 1.5
            if not self.watch.ready(b, op - 1):
                s *= 2.0
            lp = b.pos[op - 1]
            if lp is not None and _out_manh(lp, p) <= 1:
                s *= 0.5
            if s > bs:
                bs, best = (s, p)
        if o == 0 and (not b.home[me]):
            return 'STAY'
        claim = 0.0
        for p in range(_out_NC):
            if d[p] < 99 and (not b.occ[p]) and (not b.home[p]) and (b.owner[p] == 0):
                claim = max(claim, b.base[p] * max(0, R - d[p] - 1) / float(d[p] + 1))
        if best is not None and d[best] <= 6 and (bs >= claim):
            return b.step_to(best, self.rnd)
        if claim > 0.0:
            return self.farm(b)
        lp = b.pos[leader]
        if lp is not None and _out_manh(me, lp) > 2:
            return b.step_to(lp, self.rnd)
        return self.farm(b)

class _out_Vulture(_out_Outsider):
    name = 'x_vulture'

    def act(self, view):
        b = _out_Board(view)
        self.watch.update(b)
        if self.timed_shield(b, view.legal_actions):
            return 'SHIELD'
        if self.t <= 58:
            return self.farm(b)
        me, seat, R = (b.me, b.seat, self.R())
        o = b.owner[me]
        if o and o != seat and (not b.home[me]):
            return 'STAY'
        d = b.dist(me)
        best, bs = (None, 0.0)
        for p in range(_out_NC):
            op = b.owner[p]
            if d[p] >= 99 or b.occ[p] or b.home[p] or (not op) or (op == seat):
                continue
            lvl = 2 if b.upg[p] else 1
            need = 3 if b.upg[p] else 1
            if d[p] + need > R:
                continue
            s = (8.0 * b.base[p] * lvl + b.base[p] * (R - d[p] - need)) / (d[p] + need)
            if not self.watch.ready(b, op - 1):
                s *= 1.5
            if s > bs:
                bs, best = (s, p)
        if best is not None:
            return b.step_to(best, self.rnd)
        return self.farm(b)

class _out_Flaky(_out_Outsider):
    name = 'x_flaky'

    def __init__(self, seed=0):
        _out_Outsider.__init__(self, seed)
        self.dead_at = self.rnd.randint(20, 80) if self.rnd.random() < 0.3 else 999

    def act(self, view):
        if self.t >= self.dead_at:
            return 'STAY'
        x = self.rnd.random()
        if x < 0.2:
            return 'STAY'
        if x < 0.25:
            return 'north'
        b = _out_Board(view)
        if 'SHIELD' in view.legal_actions and b.rivals_on_my_land():
            return 'SHIELD'
        return self.farm(b, upgrade_min=2)

class _out_Literal(_out_Outsider):
    name = 'x_literal'

    def act(self, view):
        b = _out_Board(view)
        me, seat, R = (b.me, b.seat, self.R())
        if 'SHIELD' in view.legal_actions:
            for _j, p in b.rivals_on_my_land():
                if not b.home[p]:
                    return 'SHIELD'
        o = b.owner[me]
        if o != seat and (not b.home[me]):
            return 'STAY'
        if o == seat and (not b.upg[me]) and (b.base[me] == 3) and (R > 3):
            return 'STAY'
        d = b.dist(me)
        best, bs = (None, 0.0)
        for p in range(_out_NC):
            op = b.owner[p]
            if d[p] >= 99 or b.occ[p] or b.home[p] or (op == seat):
                continue
            need = 3 if op and b.upg[p] else 1
            rem = max(0, R - d[p] - need)
            val = b.base[p] * rem
            if op:
                val += 8 * b.base[p] * (2 if b.upg[p] else 1)
            s = val / float(d[p] + need)
            if s > bs:
                bs, best = (s, p)
        return b.step_to(best, self.rnd)

class _out_Sim(_out_Outsider):
    """Rollout planner on top of a rules simulator (engine.py stands in for the
    server). Hidden state it cannot see -- other bots' progress -- is set to 0."""
    name = 'x_sim'
    ROLLOUTS = 2
    DEPTH = 6

    def __init__(self, seed=0):
        _out_Outsider.__init__(self, seed)
        self.myprog = 0
        self.last_pos = None
        self.token = None

    @staticmethod
    def _policy(g, i, rnd):
        if g.frozen[i] > 0:
            return 'STAY'
        p = g.pos[i]
        seat = i + 1
        o = g.owner[p]
        if o != seat and (not g.home[p]) or (o == seat and (not g.upg[p]) and (g.base[p] >= 2)):
            return 'STAY'
        best, bs = (None, -1.0)
        pr, pc = divmod(p, _out_N)
        for q in range(_out_NC):
            if g.owner[q] == seat or g.home[q]:
                continue
            qr, qc = divmod(q, _out_N)
            dd = abs(pr - qr) + abs(pc - qc)
            s = g.base[q] / (dd + 1.0) + rnd.random() * 0.3
            if s > bs:
                bs, best = (s, q)
        if best is None:
            return 'STAY'
        br, bc = divmod(best, _out_N)
        opts = []
        if br < pr:
            opts.append('NORTH')
        if br > pr:
            opts.append('SOUTH')
        if bc < pc:
            opts.append('WEST')
        if bc > pc:
            opts.append('EAST')
        return rnd.choice(opts) if opts else 'STAY'

    def act(self, view):
        b = _out_Board(view)
        self.watch.update(b)
        me, seat = (b.me, b.seat)
        self.myprog = self.myprog + 1 if me == self.last_pos else 0
        self.last_pos = me
        if view.is_priority_token:
            self.token = seat
        elif self.token is not None:
            self.token = self.token % 4 + 1
        legal = list(view.legal_actions)
        if len(legal) == 1:
            return legal[0]
        g = _outsim_Game(base=b.base, start_token=self.token or 1)
        g.owner = b.owner[:]
        g.upg = [1 if u else 0 for u in b.upg]
        g.home = [b.owner[p] if b.home[p] else 0 for p in range(_out_NC)]
        g.pos = [b.pos[j] if b.pos[j] is not None else 0 for j in range(4)]
        g.frozen = [1 if b.pos[j] is not None and b.frz[b.pos[j]] else 0 for j in range(4)]
        g.cd = self.watch.cd[:]
        g.cd[seat - 1] = 0 if 'SHIELD' in legal else 1
        g.prog = [0] * 4
        o = b.owner[me]
        if o == seat and (not b.upg[me]):
            g.prog[seat - 1] = min(2, self.myprog)
        g.income = [0] * 4
        for p in range(_out_NC):
            if b.owner[p]:
                g.income[b.owner[p] - 1] += b.base[p] * (2 if b.upg[p] else 1)
        g.turn = self.t
        cands = [a for a in legal if a != 'SHIELD']
        if 'SHIELD' in legal and b.rivals_on_my_land():
            cands.append('SHIELD')
        rem_after = max(0, 80 - self.t - self.DEPTH)
        best, bv = ('STAY', -1e+18)
        for a in cands:
            tot = 0.0
            for _k in range(self.ROLLOUTS):
                gg = g.clone()
                for step in range(min(self.DEPTH, 81 - self.t)):
                    acts = [self._policy(gg, i, self.rnd) for i in range(4)]
                    if step == 0:
                        acts[seat - 1] = a
                    gg.step(acts)
                tot += gg.score[seat - 1] + gg.income[seat - 1] * rem_after
            v = tot / self.ROLLOUTS + self.rnd.random() * 1e-06
            if v > bv:
                bv, best = (v, a)
        return best
_out_ALL = (_out_Fort, _out_Leech, _out_HomeBait, _out_Jackal, _out_Vulture, _out_Flaky, _out_Literal, _out_Sim)
_out_REGISTRY = dict(((c.name, c) for c in _out_ALL))
_PLAYERS = {}
def act(state):
    s = state.bot_id
    if s not in _PLAYERS:
        _PLAYERS[s] = _out_Vulture(seed=s*7919)
    return _PLAYERS[s](state)
