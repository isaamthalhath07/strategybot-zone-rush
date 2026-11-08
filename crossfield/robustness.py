"""
Interface robustness matrix: what happens to a bot when the server's `state`
object is not exactly the one the starter kit documents.

The starter kit documents an 8x8 list of Cell objects with six int/bool fields,
an int bot_id, a bool token flag and a list of action strings. Nothing here has
been checked against the organisers' server, and a bot that misreads its input
does not crash visibly: the server scores the turn as STAY and the game goes on.
So each row below plays a full game with one perturbation applied to every
observation the bot receives, and reports the bot's score against its score on
the documented interface, plus how many turns raised or returned an unusable
action. A row is a failure when the score collapses, whatever the error count.

    python crossfield/robustness.py <bot.py> [<bot.py> ...]
"""
import collections
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
for _p in (ROOT, HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import engine  # noqa: E402
import xfield  # noqa: E402

NT = collections.namedtuple("Cell", "occupant owner is_upgraded is_home is_frozen base_points")


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


def _rows(v):
    return [[c for c in row] for row in v.board]


def _mk(board, bot_id, tok, legal):
    s = S()
    s.board, s.bot_id, s.is_priority_token, s.legal_actions = board, bot_id, tok, legal
    return s


def p_documented(v):
    return v, None


def p_flat_objects(v):
    return _mk([c for row in v.board for c in row], v.bot_id, v.is_priority_token,
               list(v.legal_actions)), None


def p_flat_namedtuple(v):
    return _mk([NT(c.occupant, c.owner, c.is_upgraded, c.is_home, c.is_frozen,
                   c.base_points) for row in v.board for c in row],
               v.bot_id, v.is_priority_token, list(v.legal_actions)), None


def p_namedtuple_rows(v):
    return _mk([[NT(c.occupant, c.owner, c.is_upgraded, c.is_home, c.is_frozen,
                    c.base_points) for c in row] for row in v.board],
               v.bot_id, v.is_priority_token, list(v.legal_actions)), None


def p_tuple_board(v):
    return _mk(tuple(tuple(r) for r in v.board), v.bot_id, v.is_priority_token,
               tuple(v.legal_actions)), None


def p_dict_cells(v):
    return _mk([[{"occupant": c.occupant, "owner": c.owner, "is_upgraded": c.is_upgraded,
                  "is_home": c.is_home, "is_frozen": c.is_frozen,
                  "base_points": c.base_points} for c in row] for row in v.board],
               v.bot_id, v.is_priority_token, list(v.legal_actions)), None


def p_int_flags(v):
    """bools delivered as 0/1 ints, as a JSON or C-backed server might."""
    return _mk([[NT(c.occupant, c.owner, int(c.is_upgraded), int(c.is_home),
                    int(c.is_frozen), c.base_points) for c in row] for row in v.board],
               v.bot_id, int(v.is_priority_token), list(v.legal_actions)), None


def p_str_bot_id(v):
    return _mk(v.board, str(v.bot_id), v.is_priority_token, list(v.legal_actions)), None


def p_lower_actions(v):
    low = [a.lower() for a in v.legal_actions]
    return _mk(v.board, v.bot_id, v.is_priority_token, low), (lambda a: a.upper()
                                                               if isinstance(a, str) else a)


def p_enum_actions(v):
    en = [Enumish(a) for a in v.legal_actions]
    return _mk(v.board, v.bot_id, v.is_priority_token, en), (lambda a: a.name
                                                             if isinstance(a, Enumish) else a)


def p_excl_occupied(v, g=None):
    return v, None                         # handled in play() with the real positions


def p_no_token_attr(v):
    s = S()
    s.board, s.bot_id, s.legal_actions = v.board, v.bot_id, list(v.legal_actions)
    return s, None


PERTURB = [
    ("documented 8x8 Cell objects", p_documented),
    ("flat 64-list of Cell objects", p_flat_objects),
    ("flat 64-list of namedtuples", p_flat_namedtuple),
    ("8x8 rows of namedtuples", p_namedtuple_rows),
    ("tuple-of-tuples board, tuple legal", p_tuple_board),
    ("cells are dicts", p_dict_cells),
    ("bools as 0/1 ints", p_int_flags),
    ("bot_id as a string", p_str_bot_id),
    ("lower-case action strings", p_lower_actions),
    ("Enum-like action objects", p_enum_actions),
    ("is_priority_token missing", p_no_token_attr),
]


def play(path, perturb, seed=5, amnesia=False, games=1):
    fac = xfield.file_bot(path)
    total = 0
    errors = 0
    worst = 0.0
    act = fac(0)
    for gi in range(games):
        g = engine.Game(base=engine.make_map(seed=seed + gi), start_token=1 + gi % 4)
        opp = [xfield.opponent("spine")(seed * 4 + i) for i in range(3)]
        while not g.over():
            vs = g.views()
            acts = []
            if amnesia:
                act = fac(0)
            v0, back = perturb(vs[0])
            t0 = time.perf_counter()
            try:
                a = act(v0)
            except Exception:
                a = None
                errors += 1
            worst = max(worst, (time.perf_counter() - t0) * 1000)
            # The answer must be a member of the list the bot was handed, in
            # that list's own type; only then is it translated for the engine.
            try:
                ok = a in list(v0.legal_actions)
            except Exception:
                ok = False
            if not ok:
                a = None
            elif back is not None:
                a = back(a)
            if a not in vs[0].legal_actions:
                errors += 1
                a = "STAY"
            acts.append(a)
            for i in range(3):
                b = opp[i](vs[i + 1])
                acts.append(b if b in vs[i + 1].legal_actions else "STAY")
            g.step(acts)
        total += g.score[0]
    return total / games, errors, worst


def main(paths):
    for path in paths:
        print("\n== %s" % path)
        ref, _, _ = play(path, p_documented)
        print("%-38s %7s %7s %9s" % ("perturbation", "score", "errors", "verdict"))
        for name, fn in PERTURB:
            sc, er, _ = play(path, fn)
            verdict = "ok" if sc >= 0.9 * ref and er == 0 else ("DEGRADED" if sc >= 0.5 * ref
                                                                else "BROKEN")
            print("%-38s %7.0f %7d %9s" % (name, sc, er, verdict))
        sc, er, _ = play(path, p_documented, amnesia=True)
        verdict = "ok" if sc >= 0.9 * ref and er == 0 else ("DEGRADED" if sc >= 0.5 * ref
                                                            else "BROKEN")
        print("%-38s %7.0f %7d %9s" % ("fresh module every turn", sc, er, verdict))


if __name__ == "__main__":
    main(sys.argv[1:] or [os.path.join(HERE, "bots", n) for n in sorted(os.listdir(
        os.path.join(HERE, "bots")))])
