"""
Zone Rush -- exact rules engine, reimplemented from the official StrategyBot rulebook
(Sections 2.1-2.8) plus the starter-kit README at github.com/RedPokerJoker123/StrategyBot.

No reference engine ships with the starter kit, so several rule details are genuinely
ambiguous. Every one of them is a flag in RULES below so both readings can be tested.
"""
import random

N = 8
NC = 64
ACTIONS = ("NORTH", "EAST", "SOUTH", "WEST", "STAY", "SHIELD")
MOVES = {"NORTH": -N, "SOUTH": N, "WEST": -1, "EAST": 1}

# Corner for each seat (seats 1..4). The priority token rotates 1->2->3->4->1.
CORNERS = {1: 0, 2: N - 1, 3: NC - 1, 4: NC - N}

# --- ambiguous rules; defaults are the conservative reading -------------------
RULES = {
    # Does a frozen bot's forced STAY accrue take/upgrade progress?
    "frozen_stay_counts": False,
    # After a take/claim completes, does progress reset to 0?
    #   True  -> neutral cell costs 1 stay to claim + 3 more to upgrade (4 total)
    #   False -> progress carries over, so 3 stays total
    "claim_resets_progress": True,
    # Does a bot that chose SHIELD while standing on rival land escape the catch?
    "catch_requires_stay": True,
    # Does losing a contested-cell race count as a STAY for progress purposes?
    "lost_contest_is_stay": True,
    # Can a home cell be upgraded by its owner?
    "home_upgradable": True,
}


def make_map(seed=None, canonical=False):
    """8x8 point map, 4-fold mirrored, values 1..3, higher toward the middle."""
    if canonical or seed is None:
        q = [[1, 1, 1, 2], [1, 1, 2, 2], [1, 2, 2, 3], [2, 2, 3, 3]]
    else:
        rnd = random.Random(seed)
        slope = rnd.uniform(0.33, 0.58)
        noise = rnd.uniform(0.25, 0.75)
        q = []
        for r in range(4):
            row = []
            for c in range(4):
                d = (3 - r) + (3 - c)          # 0 nearest the centre, 6 at the home corner
                v = 3.0 - d * slope + rnd.uniform(-noise, noise)
                row.append(max(1, min(3, int(round(v)))))
            q.append(row)
        q[0][0] = min(q[0][0], 2)              # keep homes cheap-ish
    base = [0] * NC
    for r in range(4):
        for c in range(4):
            v = q[r][c]
            base[r * N + c] = v
            base[r * N + (N - 1 - c)] = v
            base[(N - 1 - r) * N + c] = v
            base[(N - 1 - r) * N + (N - 1 - c)] = v
    return base


class Cell(object):
    """Exactly the fields the starter kit documents -- nothing else is visible."""
    __slots__ = ("occupant", "owner", "is_upgraded", "is_home", "is_frozen", "base_points")

    def __init__(self, occupant, owner, is_upgraded, is_home, is_frozen, base_points):
        self.occupant = occupant
        self.owner = owner
        self.is_upgraded = is_upgraded
        self.is_home = is_home
        self.is_frozen = is_frozen
        self.base_points = base_points


class View(object):
    """The `state` object handed to act(). Mirrors the starter kit's class Game."""
    __slots__ = ("board", "bot_id", "is_priority_token", "legal_actions")

    def __init__(self, board, bot_id, is_priority_token, legal_actions):
        self.board = board
        self.bot_id = bot_id
        self.is_priority_token = is_priority_token
        self.legal_actions = legal_actions


class Game(object):
    __slots__ = ("base", "owner", "upg", "home", "pos", "frozen", "cd", "prog",
                 "score", "income", "turn", "token", "max_turns", "rules")

    def __init__(self, base=None, max_turns=80, rules=None, start_token=1):
        self.base = list(base if base is not None else make_map(canonical=True))
        self.owner = [0] * NC
        self.upg = [0] * NC
        self.home = [0] * NC
        self.pos = [0] * 4
        self.frozen = [0] * 4
        self.cd = [0] * 4
        self.prog = [0] * 4
        self.score = [0] * 4
        self.income = [0] * 4
        self.turn = 1
        self.max_turns = max_turns
        self.token = start_token
        self.rules = dict(RULES)
        if rules:
            self.rules.update(rules)
        for seat, cell in CORNERS.items():
            self.home[cell] = seat
            self.owner[cell] = seat
            self.pos[seat - 1] = cell
            self.income[seat - 1] = self.base[cell]

    # -- plumbing -------------------------------------------------------------
    def clone(self):
        g = Game.__new__(Game)
        g.base = self.base                      # immutable during a game
        g.owner = self.owner[:]
        g.upg = self.upg[:]
        g.home = self.home                      # immutable
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
            return ["STAY"]
        out = ["STAY"]
        r, c = divmod(self.pos[i], N)
        if r > 0:
            out.append("NORTH")
        if r < N - 1:
            out.append("SOUTH")
        if c > 0:
            out.append("WEST")
        if c < N - 1:
            out.append("EAST")
        if self.cd[i] == 0:
            out.append("SHIELD")
        return out

    def board_view(self):
        occ = [0] * NC
        frz = [False] * NC
        for i in range(4):
            occ[self.pos[i]] = i + 1
            if self.frozen[i] > 0:
                frz[self.pos[i]] = True
        bd = []
        for r in range(N):
            row = []
            for c in range(N):
                p = r * N + c
                row.append(Cell(occ[p], self.owner[p], bool(self.upg[p]),
                                bool(self.home[p]), frz[p], self.base[p]))
            bd.append(row)
        return bd

    def views(self):
        bd = self.board_view()
        return [View(bd, i + 1, self.token == i + 1, self.legal(i)) for i in range(4)]

    # -- the turn -------------------------------------------------------------
    def step(self, actions):
        """actions[i] is seat i+1's chosen action string. Resolves one full turn."""
        R = self.rules
        eff = [None] * 4

        # 0. forced STAY while frozen, and illegal-action normalisation
        for i in range(4):
            if self.frozen[i] > 0:
                eff[i] = "STAY"
                continue
            a = actions[i]
            if a == "SHIELD":
                eff[i] = "STAY" if self.cd[i] > 0 else "SHIELD"
            elif a in MOVES:
                r, c = divmod(self.pos[i], N)
                if ((a == "NORTH" and r == 0) or (a == "SOUTH" and r == N - 1) or
                        (a == "WEST" and c == 0) or (a == "EAST" and c == N - 1)):
                    eff[i] = "STAY"
                else:
                    eff[i] = a
            else:
                eff[i] = "STAY"

        # 1. moves and shields
        closed = set(self.pos)                 # occupied at the START of the turn
        intents = {}
        for i in range(4):
            if eff[i] in MOVES:
                t = self.pos[i] + MOVES[eff[i]]
                if t in closed:
                    eff[i] = "STAY"            # a blocked move counts as STAY
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
                    w, best = seats[0], 99
                    for s in seats:
                        rank = (s + 1 - self.token) % 4
                        if rank < best:
                            best, w = rank, s
                for s in seats:
                    if s != w:
                        eff[s] = "STAY" if R["lost_contest_is_stay"] else "BLOCKED"
            self.pos[w] = t
            self.prog[w] = 0                   # moving resets progress
        for i in range(4):
            if eff[i] == "SHIELD":
                self.prog[i] = 0               # a shield turn is not a stay

        # 2. takes, upgrades and freezes (shields resolve first)
        shielders = [i for i in range(4) if eff[i] == "SHIELD"]
        caught = [False] * 4
        newfrozen = [0] * 4
        for s in shielders:
            seat = s + 1
            got = []
            for j in range(4):
                if j == s or self.frozen[j] > 0:
                    continue
                if R["catch_requires_stay"] and eff[j] != "STAY":
                    continue
                if self.owner[self.pos[j]] == seat:
                    got.append(j)
            if got:
                for j in got:
                    caught[j] = True
                    newfrozen[j] = 2
                    self.prog[j] = 0
            else:
                newfrozen[s] = 2               # backfire
        shielded_seats = set(s + 1 for s in shielders)

        for i in range(4):
            if eff[i] != "STAY" or caught[i]:
                continue
            if self.frozen[i] > 0 and not R["frozen_stay_counts"]:
                continue
            p = self.pos[i]
            seat = i + 1
            o = self.owner[p]
            if o == seat:
                if self.upg[p]:
                    continue
                if self.home[p] == seat and not R["home_upgradable"]:
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
                    if R["claim_resets_progress"]:
                        self.prog[i] = 0
            else:
                if self.home[p] or o in shielded_seats:
                    continue                   # homes never fall; shielded cells hold
                needed = 3 if self.upg[p] else 1
                self.prog[i] += 1
                if self.prog[i] >= needed:
                    lvl = 2 if self.upg[p] else 1
                    self.score[i] += 8 * self.base[p] * lvl
                    self.income[o - 1] -= self.base[p] * lvl
                    self.owner[p] = seat
                    self.upg[p] = 0
                    self.income[i] += self.base[p]
                    if R["claim_resets_progress"]:
                        self.prog[i] = 0

        # 3. scoring
        for i in range(4):
            self.score[i] += self.income[i]

        # 4. bookkeeping, then the token passes
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
        for p in range(NC):
            if self.owner[p] == seat:
                n += 1
        return n

    def places(self, round_number=1, round1_ranks=None):
        """1-based mean place per seat under the selected competition round.

        Round 1 compares final scores only (rulebook 3.2): equal scores are
        draws regardless of cells. Round 2 first breaks score ties by cells
        (5.3). Pool games then share the remaining ties. For a Round 2
        semi-final or final, supply each seat's Round 1 rank, lower being
        better, to apply the last knockout tiebreak.
        """
        if round_number not in (1, 2):
            raise ValueError("round_number must be 1 or 2")
        if round1_ranks is not None:
            if round_number != 2 or len(round1_ranks) != 4:
                raise ValueError("round1_ranks requires Round 2 and four seat ranks")
        key = [(-self.score[i],) for i in range(4)]
        if round_number == 2:
            key = [key[i] + (-self.cells_owned(i),) for i in range(4)]
            if round1_ranks is not None:
                key = [key[i] + (round1_ranks[i],) for i in range(4)]
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


def play(bots, base=None, max_turns=80, rules=None, start_token=1):
    """bots[i] is a callable act(view) for seat i+1. Returns the finished Game."""
    g = Game(base=base, max_turns=max_turns, rules=rules, start_token=start_token)
    while not g.over():
        vs = g.views()
        acts = []
        for i in range(4):
            try:
                a = bots[i](vs[i])
            except Exception:
                a = "STAY"
            if a not in vs[i].legal_actions:
                a = "STAY"
            acts.append(a)
        g.step(acts)
    return g
