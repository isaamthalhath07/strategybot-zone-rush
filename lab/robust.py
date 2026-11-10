"""Interface and deployment robustness: what happens when the server is not exactly the
one the starter kit documents, or runs the bot differently from our harness.

  python3 lab/robust.py cand1 [cand2 ...]

A bot that misreads its input does not crash visibly: the server scores the turn as STAY
and the game goes on. So every row plays full games with one perturbation applied to
every observation the bot receives and reports its mean score relative to the documented
interface, plus how many turns raised or returned something unusable.

The perturbations are the eleven from the project's earlier crossfield/robustness.py,
plus four server quirks and five deployment modes that file did not cover.
"""
import collections
import os
import sys
import types

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sim  # noqa: E402
from referee import Referee  # noqa: E402  (path set up by sim)

NT = collections.namedtuple("Cell", "occupant owner is_upgraded is_home is_frozen base_points")
FIELDS = ("occupant", "owner", "is_upgraded", "is_home", "is_frozen", "base_points")


class S(object):
    pass


class Enumish(object):
    """An action type that is not a str but names itself, like an Enum member."""

    def __init__(self, name):
        self.name = name

    def __eq__(self, other):
        return isinstance(other, Enumish) and other.name == self.name

    def __hash__(self):
        return hash(self.name)

    def __repr__(self):
        return "Action.%s" % self.name


def _mk(board, bot_id, tok, legal):
    s = S()
    s.board, s.bot_id, s.is_priority_token, s.legal_actions = board, bot_id, tok, legal
    return s


def _nt(c):
    return NT(c.occupant, c.owner, c.is_upgraded, c.is_home, c.is_frozen, c.base_points)


def p_documented(v):
    return v, None


def p_flat_objects(v):
    return _mk([c for row in v.board for c in row], v.bot_id, v.is_priority_token, list(v.legal_actions)), None


def p_flat_namedtuple(v):
    return _mk([_nt(c) for row in v.board for c in row], v.bot_id, v.is_priority_token, list(v.legal_actions)), None


def p_namedtuple_rows(v):
    return _mk([[_nt(c) for c in row] for row in v.board], v.bot_id, v.is_priority_token, list(v.legal_actions)), None


def p_tuple_board(v):
    return _mk(tuple(tuple(r) for r in v.board), v.bot_id, v.is_priority_token, tuple(v.legal_actions)), None


def p_dict_cells(v):
    return _mk([[dict((f, getattr(c, f)) for f in FIELDS) for c in row] for row in v.board],
               v.bot_id, v.is_priority_token, list(v.legal_actions)), None


def p_dict_state(v):
    return {"board": v.board, "bot_id": v.bot_id, "is_priority_token": v.is_priority_token,
            "legal_actions": list(v.legal_actions)}, None


def p_plain_tuples(v):
    return _mk([[tuple(getattr(c, f) for f in FIELDS) for c in row] for row in v.board],
               v.bot_id, v.is_priority_token, list(v.legal_actions)), None


def p_int_flags(v):
    return _mk([[NT(c.occupant, c.owner, int(c.is_upgraded), int(c.is_home), int(c.is_frozen), c.base_points)
                 for c in row] for row in v.board], v.bot_id, int(v.is_priority_token), list(v.legal_actions)), None


def p_str_bot_id(v):
    return _mk(v.board, str(v.bot_id), v.is_priority_token, list(v.legal_actions)), None


def p_lower_actions(v):
    return (_mk(v.board, v.bot_id, v.is_priority_token, [a.lower() for a in v.legal_actions]),
            lambda a: a.upper() if isinstance(a, str) else a)


def p_enum_actions(v):
    return (_mk(v.board, v.bot_id, v.is_priority_token, [Enumish(a) for a in v.legal_actions]),
            lambda a: a.name if isinstance(a, Enumish) else a)


def p_no_token_attr(v):
    s = S()
    s.board, s.bot_id, s.legal_actions = v.board, v.bot_id, list(v.legal_actions)
    return s, None


def p_homes_unowned(v):
    return _mk([[NT(c.occupant, 0 if c.is_home else c.owner, c.is_upgraded, c.is_home, c.is_frozen, c.base_points)
                 for c in row] for row in v.board], v.bot_id, v.is_priority_token, list(v.legal_actions)), None


def p_shield_always_listed(v):
    """A server that lists SHIELD even while it is on cooldown (it then resolves as STAY)."""
    legal = list(v.legal_actions)
    if "SHIELD" not in legal and len(legal) > 1:
        legal.append("SHIELD")
    return _mk(v.board, v.bot_id, v.is_priority_token, legal), None


def p_shuffled_legal(v):
    legal = list(v.legal_actions)
    legal.reverse()
    return _mk(v.board, v.bot_id, v.is_priority_token, legal), None


PERTURB = [
    ("documented 8x8 Cell objects", p_documented, None),
    ("flat 64-list of Cell objects", p_flat_objects, None),
    ("flat 64-list of namedtuples", p_flat_namedtuple, None),
    ("8x8 rows of namedtuples", p_namedtuple_rows, None),
    ("tuple-of-tuples board, tuple legal", p_tuple_board, None),
    ("cells are dicts", p_dict_cells, None),
    ("bools as 0/1 ints", p_int_flags, None),
    ("bot_id as a string", p_str_bot_id, None),
    ("lower-case action strings", p_lower_actions, None),
    ("Enum-like action objects", p_enum_actions, None),
    ("is_priority_token missing", p_no_token_attr, None),
    ("state is a dict", p_dict_state, None),
    ("cells are bare 6-tuples", p_plain_tuples, None),
    ("homes reported unowned", p_homes_unowned, None),
    ("SHIELD listed while on cooldown", p_shield_always_listed, None),
    ("legal_actions in reverse order", p_shuffled_legal, None),
    ("legal list omits occupied cells", p_documented, {"legal_excludes_occupied": True}),
    ("homes cannot be upgraded", p_documented, {"home_upgradable": False}),
    ("Shield catches by presence", p_documented, {"catch_requires_stay": False}),
    ("lost contest is not a STAY", p_documented, {"lost_contest_is_stay": False}),
    ("frozen STAY earns progress", p_documented, {"frozen_stay_counts": True}),
    ("claim keeps progress", p_documented, {"claim_resets_progress": False}),
]
OPP = ["a_novel_b_racer", "cur_e8", "a_opp_farmer_04_0db330"]
GAMES = [("gradient", 11, 0, 1), ("uniform", 12, 1, 3), ("noisy", 13, 2, 2), ("ring", 14, 3, 4)]


def play(focal, perturb, rules=None, mode="normal", games=GAMES):
    """Mean focal score and error count. mode: normal | amnesia | late | shared | second."""
    total, errors = 0, 0
    for family, mapseed, seat, token in games:
        base = sim.make_map(family, mapseed)
        names = list(OPP)
        names.insert(seat, focal)
        if mode == "shared":
            names = [focal] * 4
        actors = [sim.make_actor(n, 7 * i + mapseed) for i, n in enumerate(names)]
        if mode == "shared":
            actors = [actors[0]] * 4          # one module instance serves every seat
        rounds = 2 if mode == "second" else 1
        for rnd in range(rounds):
            game = Referee(base, rules=rules, start_token=token)
            while not game.over():
                states = sim.build_states(game)
                chosen = []
                for i in range(4):
                    legal = states[i].legal_actions
                    if i != seat and mode != "shared":
                        try:
                            a = actors[i](states[i])
                        except Exception:
                            a = "STAY"
                        chosen.append(a if a in legal else "STAY")
                        continue
                    if mode == "amnesia" or (mode == "late" and game.turn == 30):
                        actors[i] = sim.make_actor(focal, 99)
                    if mode == "late" and game.turn < 30:
                        # a stand-in plays the first 29 turns; the focal bot joins a running game
                        a = sim.make_actor("cur_e8", 5)(states[i]) if game.turn == 1 else actors_late[i](states[i])
                        chosen.append(a if a in legal else "STAY")
                        continue
                    v0, back = perturb(states[i])
                    try:
                        a = actors[i](v0)
                    except Exception:
                        a = None
                        errors += 1
                    try:
                        handed = v0["legal_actions"] if isinstance(v0, dict) else v0.legal_actions
                        ok = a is not None and a in list(handed)
                    except Exception:
                        ok = False
                    if not ok:
                        a = None
                    elif back is not None:
                        a = back(a)
                    if a not in legal:
                        if not (a == "SHIELD" and perturb is p_shield_always_listed):
                            errors += 1
                        a = "STAY"
                    chosen.append(a)
                game.step(chosen)
            score = game.score
        total += sum(score) / 4.0 if mode == "shared" else score[seat]
    return total / len(games), errors


actors_late = {}


def play_late(focal):
    """The focal bot is loaded at turn 30 of a game somebody else started."""
    total, errors = 0, 0
    for family, mapseed, seat, token in GAMES:
        base = sim.make_map(family, mapseed)
        names = list(OPP)
        names.insert(seat, "cur_e8")
        actors = [sim.make_actor(n, 7 * i + mapseed) for i, n in enumerate(names)]
        game = Referee(base, start_token=token)
        while not game.over():
            if game.turn == 30:
                actors[seat] = sim.make_actor(focal, 99)
            states = sim.build_states(game)
            chosen = []
            for i in range(4):
                legal = states[i].legal_actions
                try:
                    a = actors[i](states[i])
                except Exception:
                    a = "STAY"
                    errors += i == seat and game.turn >= 30
                if a not in legal:
                    errors += i == seat and game.turn >= 30
                    a = "STAY"
                chosen.append(a)
            game.step(chosen)
        total += game.score[seat]
    return total / len(GAMES), errors


def verdict(score, ref, errors, floor=0.9):
    if errors == 0 and score >= floor * ref:
        return "ok"
    return "DEGRADED" if score >= 0.5 * ref else "BROKEN"


def main(cands):
    out = {}
    for cand in cands:
        print("\n== %s" % cand)
        ref, _ = play(cand, p_documented)
        rows = []
        print("%-36s %7s %7s  %s" % ("condition", "score", "errors", "verdict"))
        for name, fn, rules in PERTURB:
            base_ref = ref
            if rules:                       # a different rule changes everyone's scores: judge on errors
                sc, er = play(cand, fn, rules)
                v = "ok" if er == 0 and sc >= 0.7 * ref else verdict(sc, ref, er, 0.7)
            else:
                sc, er = play(cand, fn)
                v = verdict(sc, base_ref, er)
            rows.append((name, sc, er, v))
            print("%-36s %7.0f %7d  %s" % (name, sc, er, v))
        sc, er = play(cand, p_documented, mode="amnesia")
        rows.append(("fresh module every turn", sc, er, verdict(sc, ref, er, 0.5)))
        sc, er = play(cand, p_documented, mode="second")
        rows.append(("second game in the same module", sc, er, verdict(sc, ref, er)))
        sc, er = play_late(cand)
        rows.append(("loaded at turn 30 of a running game", sc, er, "ok" if er == 0 else "BROKEN"))
        sep, _ = play(cand, p_documented, mode="shared_ref", games=GAMES) if False else (None, None)
        sc, er = play(cand, p_documented, mode="shared")
        # reference for the shared case: four separate module instances of the same bot
        tot = 0
        for family, mapseed, seat, token in GAMES:
            r = sim.play([cand] * 4, sim.make_map(family, mapseed), token=token, seed=mapseed)
            tot += sum(r["scores"]) / 4.0
        four = tot / len(GAMES)
        rows.append(("one module serving all four seats", sc, er, verdict(sc, four, er)))
        for name, sc, er, v in rows[len(PERTURB):]:
            print("%-36s %7.0f %7d  %s" % (name, sc, er, v))
        print("%-36s %7.0f          (four separate modules, for the row above)" % ("", four))
        out[cand] = rows
    bad = [(c, r[0], r[3]) for c, rows in out.items() for r in rows if r[3] != "ok"]
    print("\nnot ok:", bad if bad else "none")
    return out


if __name__ == "__main__":
    main(sys.argv[1:])
