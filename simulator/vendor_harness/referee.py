"""Zone Rush referee for the visual harness.

Implements Section 2 of the official rulebook and records what happened on every turn
(moves, blocks, contests, shields, freezes, claims, raids, upgrades, progress) so the
viewer can explain each step. The rulebook leaves a few details open; each one is a
flag in DEFAULT_RULES, and the defaults match engine.py on main.
"""
import random

N = 8
NC = N * N
MOVES = ("NORTH", "EAST", "SOUTH", "WEST")
ACTIONS = MOVES + ("STAY", "SHIELD")
DELTA = {"NORTH": (-1, 0), "EAST": (0, 1), "SOUTH": (1, 0), "WEST": (0, -1)}
HOMES = {1: 0, 2: N - 1, 3: NC - 1, 4: NC - N}
EXAMPLE_QUADRANT = ((1, 1, 1, 2), (1, 1, 2, 2), (1, 2, 2, 3), (2, 2, 3, 3))

DEFAULT_RULES = {
    "frozen_stay_counts": False,
    "claim_resets_progress": True,
    "catch_requires_stay": True,
    "lost_contest_is_stay": True,
    "home_upgradable": True,
    "legal_excludes_occupied": False,
}

RULE_HELP = {
    "frozen_stay_counts": "A frozen bot's forced STAY earns take/upgrade progress.",
    "claim_resets_progress": "Progress restarts after a take, so a neutral cell needs 1 stay to claim plus 3 more to upgrade.",
    "catch_requires_stay": "SHIELD only catches rivals that stayed this turn, not ones that just arrived or are shielding.",
    "lost_contest_is_stay": "Losing a contested move counts as a STAY, so it earns progress and can be caught.",
    "home_upgradable": "A bot can upgrade its own home cell.",
    "legal_excludes_occupied": "legal_actions leaves out moves into cells that are occupied at the start of the turn.",
}


def cell_name(p):
    return "(%d,%d)" % divmod(p, N)


def mirror(quadrant):
    base = [0] * NC
    for r in range(N):
        for c in range(N):
            base[r * N + c] = quadrant[min(r, N - 1 - r)][min(c, N - 1 - c)]
    return base


def example_map():
    return mirror(EXAMPLE_QUADRANT)


def random_map(seed):
    """Same generator as make_map() in engine.py on main, so seeds give the same maps."""
    rnd = random.Random(seed)
    slope = rnd.uniform(0.33, 0.58)
    noise = rnd.uniform(0.25, 0.75)
    q = []
    for r in range(4):
        row = []
        for c in range(4):
            d = (3 - r) + (3 - c)
            v = 3.0 - d * slope + rnd.uniform(-noise, noise)
            row.append(max(1, min(3, int(round(v)))))
        q.append(row)
    q[0][0] = min(q[0][0], 2)
    return mirror(q)


def parse_quadrant(text):
    """'1112/1122/1223/2233' -> top-left quadrant, mirrored to the full board."""
    rows = [r.strip() for r in str(text).replace(",", "/").replace(";", "/").split("/") if r.strip()]
    q = [[int(ch) for ch in r if not ch.isspace()] for r in rows]
    if len(q) != 4 or any(len(r) != 4 for r in q) or any(v not in (1, 2, 3) for r in q for v in r):
        raise ValueError("quadrant must be 4 rows of 4 values from 1 to 3, e.g. 1112/1122/1223/2233")
    return mirror(q)


def build_map(spec):
    kind = (spec or {}).get("kind", "example")
    if kind == "example":
        return example_map()
    if kind == "random":
        return random_map(int(spec.get("seed", 0)))
    if kind == "custom":
        return parse_quadrant(spec.get("quadrant", ""))
    raise ValueError("unknown map kind %r" % kind)


class Referee(object):
    def __init__(self, base, rules=None, start_token=1, max_turns=80):
        if len(base) != NC or any(v not in (1, 2, 3) for v in base):
            raise ValueError("the map needs 64 cell values from 1 to 3")
        if start_token not in (1, 2, 3, 4):
            raise ValueError("start_token must be a seat from 1 to 4")
        unknown = set(rules or {}) - set(DEFAULT_RULES)
        if unknown:
            raise ValueError("unknown rule flags: %s" % ", ".join(sorted(unknown)))
        self.base = list(base)
        self.rules = dict(DEFAULT_RULES, **(rules or {}))
        self.owner = [0] * NC
        self.upg = [False] * NC
        self.home = [0] * NC
        self.pos = [HOMES[s] for s in (1, 2, 3, 4)]
        self.frozen = [0] * 4
        self.cd = [0] * 4
        self.prog = [0] * 4
        self.score = [0] * 4
        self.turn = 1
        self.token = start_token
        self.max_turns = max_turns
        for seat, p in HOMES.items():
            self.owner[p] = seat
            self.home[p] = seat

    def over(self):
        return self.turn > self.max_turns

    def target(self, p, action):
        dr, dc = DELTA[action]
        r, c = divmod(p, N)
        r, c = r + dr, c + dc
        if 0 <= r < N and 0 <= c < N:
            return r * N + c
        return None

    def legal(self, i):
        if self.frozen[i] > 0:
            return ["STAY"]
        out = []
        for a in MOVES:
            t = self.target(self.pos[i], a)
            if t is None:
                continue
            if self.rules["legal_excludes_occupied"] and t in self.pos:
                continue
            out.append(a)
        out.append("STAY")
        if self.cd[i] == 0:
            out.append("SHIELD")
        return out

    def observation(self, seat):
        """The state handed to seat's act(), as plain data. Cells are
        [occupant, owner, is_upgraded, is_home, is_frozen, base_points]."""
        occ = {p: i + 1 for i, p in enumerate(self.pos)}
        board = []
        for r in range(N):
            row = []
            for c in range(N):
                p = r * N + c
                o = occ.get(p, 0)
                row.append([o, self.owner[p], self.upg[p], bool(self.home[p]),
                            bool(o and self.frozen[o - 1] > 0), self.base[p]])
            board.append(row)
        return {"board": board, "bot_id": seat, "is_priority_token": self.token == seat,
                "legal_actions": self.legal(seat - 1)}

    def need(self, i):
        """Stays the bot needs on its current cell to finish a take or upgrade (0 = nothing to gain)."""
        p = self.pos[i]
        o = self.owner[p]
        if o == i + 1:
            if self.upg[p] or (self.home[p] and not self.rules["home_upgradable"]):
                return 0
            return 3
        if o == 0:
            return 1
        if self.home[p]:
            return 0
        return 3 if self.upg[p] else 1

    def income(self):
        inc = [0] * 4
        for p in range(NC):
            if self.owner[p]:
                inc[self.owner[p] - 1] += self.base[p] * (2 if self.upg[p] else 1)
        return inc

    def snapshot(self):
        cells = [0] * 4
        upgraded = [0] * 4
        for p in range(NC):
            if self.owner[p]:
                cells[self.owner[p] - 1] += 1
                if self.upg[p]:
                    upgraded[self.owner[p] - 1] += 1
        return {
            "turn": self.turn, "token": self.token,
            "pos": list(self.pos), "owner": list(self.owner),
            "upg": [1 if u else 0 for u in self.upg],
            "frozen": list(self.frozen), "cd": list(self.cd),
            "prog": list(self.prog), "need": [self.need(i) for i in range(4)],
            "score": list(self.score), "income": self.income(),
            "cells": cells, "upgraded": upgraded,
        }

    def step(self, actions):
        """Resolve one turn. actions[i] is seat i+1's action (already checked for legality
        by the caller; anything unusable here is treated as STAY). Returns what happened."""
        R = self.rules
        start = list(self.pos)
        was_frozen = [f > 0 for f in self.frozen]
        before = list(self.score)
        eff = [None] * 4
        notes = [[] for _ in range(4)]
        events = []

        def reset(i, why):
            if self.prog[i]:
                events.append({"type": "reset", "seat": i + 1, "lost": self.prog[i], "why": why})
            self.prog[i] = 0

        # 0. frozen bots and unusable actions
        for i in range(4):
            a = actions[i]
            if was_frozen[i]:
                eff[i] = "STAY"
                notes[i].append("frozen (%d turn%s left): forced STAY" %
                                (self.frozen[i], "" if self.frozen[i] == 1 else "s"))
            elif a == "SHIELD":
                if self.cd[i] > 0:
                    eff[i] = "STAY"
                    notes[i].append("SHIELD on cooldown: treated as STAY")
                else:
                    eff[i] = "SHIELD"
            elif a in DELTA:
                if self.target(start[i], a) is None:
                    eff[i] = "STAY"
                    notes[i].append("%s leaves the board: treated as STAY" % a)
                else:
                    eff[i] = a
            else:
                eff[i] = "STAY"
                if a != "STAY":
                    notes[i].append("unusable action %r: treated as STAY" % (a,))

        # 1. moves and shields; cells occupied at the start of the turn are closed
        closed = set(start)
        intents = {}
        for i in range(4):
            if eff[i] in DELTA:
                t = self.target(start[i], eff[i])
                if t in closed:
                    by = start.index(t) + 1
                    events.append({"type": "blocked", "seat": i + 1, "from": start[i], "to": t, "by": by})
                    notes[i].append("%s blocked: %s was occupied by seat %d at the start of the turn"
                                    % (eff[i], cell_name(t), by))
                    eff[i] = "STAY"
                else:
                    intents.setdefault(t, []).append(i)
        for t, seats in intents.items():
            w = seats[0]
            if len(seats) > 1:
                owners = [s for s in seats if self.owner[t] == s + 1]
                if owners:
                    w, why = owners[0], "owner"
                else:
                    w, why = min(seats, key=lambda s: (s + 1 - self.token) % 4), "token"
                events.append({"type": "contest", "cell": t, "seats": [s + 1 for s in seats],
                               "winner": w + 1, "why": why, "token": self.token})
                for s in seats:
                    if s != w:
                        events.append({"type": "lost", "seat": s + 1, "from": start[s], "to": t, "winner": w + 1})
                        notes[s].append("lost the contest for %s to seat %d (%s)" %
                                        (cell_name(t), w + 1, "it owns the cell" if why == "owner"
                                         else "token order from seat %d" % self.token))
                        eff[s] = "STAY" if R["lost_contest_is_stay"] else "BLOCKED"
            self.pos[w] = t
            events.append({"type": "move", "seat": w + 1, "from": start[w], "to": t, "dir": eff[w]})
            reset(w, "moved")
        for i in range(4):
            if eff[i] == "SHIELD":
                reset(i, "shielded")

        # 2. takes, upgrades and freezes; shields resolve first
        shielders = [i for i in range(4) if eff[i] == "SHIELD"]
        caught = [False] * 4
        newfrozen = [0] * 4
        for s in shielders:
            got = []
            for j in range(4):
                if j == s or was_frozen[j]:
                    continue
                if R["catch_requires_stay"] and eff[j] != "STAY":
                    continue
                if self.owner[self.pos[j]] == s + 1:
                    got.append(j)
            events.append({"type": "shield", "seat": s + 1, "caught": [j + 1 for j in got], "backfire": not got})
            if got:
                for j in got:
                    caught[j] = True
                    newfrozen[j] = 2
                    reset(j, "caught by seat %d's shield" % (s + 1))
                    events.append({"type": "freeze", "seat": j + 1, "by": s + 1, "cell": self.pos[j], "why": "caught"})
                    notes[j].append("caught on %s by seat %d's SHIELD: frozen for 2 turns" %
                                    (cell_name(self.pos[j]), s + 1))
            else:
                newfrozen[s] = 2
                events.append({"type": "freeze", "seat": s + 1, "by": s + 1, "cell": self.pos[s], "why": "backfire"})
                notes[s].append("SHIELD caught nobody and backfired: frozen for 2 turns")
        shielded = set(s + 1 for s in shielders)

        bonus = [0] * 4
        for i in range(4):
            if eff[i] != "STAY" or caught[i]:
                continue
            if was_frozen[i] and not R["frozen_stay_counts"]:
                continue
            p = self.pos[i]
            seat = i + 1
            o = self.owner[p]
            if o == seat:
                if self.upg[p]:
                    continue
                if self.home[p] and not R["home_upgradable"]:
                    continue
                self.prog[i] += 1
                events.append({"type": "progress", "seat": seat, "cell": p, "value": self.prog[i],
                               "need": 3, "kind": "upgrade"})
                if self.prog[i] >= 3:
                    self.upg[p] = True
                    self.prog[i] = 0
                    events.append({"type": "upgrade", "seat": seat, "cell": p, "base": self.base[p]})
            elif o == 0:
                self.prog[i] += 1
                self.owner[p] = seat
                events.append({"type": "claim", "seat": seat, "cell": p, "base": self.base[p]})
                if R["claim_resets_progress"]:
                    self.prog[i] = 0
            else:
                if self.home[p]:
                    notes[i].append("%s is seat %d's home and can never be taken" % (cell_name(p), o))
                    continue
                if o in shielded:
                    notes[i].append("%s is protected by seat %d's SHIELD this turn" % (cell_name(p), o))
                    continue
                needed = 3 if self.upg[p] else 1
                self.prog[i] += 1
                if needed > 1:
                    events.append({"type": "progress", "seat": seat, "cell": p, "value": self.prog[i],
                                   "need": needed, "kind": "raid"})
                if self.prog[i] >= needed:
                    lvl = 2 if self.upg[p] else 1
                    gain = 8 * self.base[p] * lvl
                    self.score[i] += gain
                    bonus[i] += gain
                    self.owner[p] = seat
                    self.upg[p] = False
                    events.append({"type": "raid", "seat": seat, "cell": p, "from": o, "level": lvl,
                                   "base": self.base[p], "bonus": gain})
                    if R["claim_resets_progress"]:
                        self.prog[i] = 0

        # 3. scoring
        income = self.income()
        for i in range(4):
            self.score[i] += income[i]

        # 4. freezes and cooldowns tick, then the token passes
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
        return {"eff": eff, "notes": notes, "events": events, "income": income, "bonus": bonus,
                "gain": [self.score[i] - before[i] for i in range(4)]}


def places(scores):
    """Standard competition ranking: equal totals share a place (rulebook 2.7)."""
    return [1 + sum(1 for o in scores if o > s) for s in scores]


def pairwise(scores):
    """Fraction of rivals outscored, ties count half: what the Round 1 Elo rewards."""
    out = []
    for i, s in enumerate(scores):
        w = sum(1.0 if s > o else 0.5 if s == o else 0.0 for j, o in enumerate(scores) if j != i)
        out.append(w / 3.0)
    return out
