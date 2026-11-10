"""In-process Zone Rush game runner used by every lab measurement.

Physics come from the repository's pinned referee (simulator/vendor_harness/referee.py),
so nothing here re-implements the rules. Each seat gets a fresh module namespace per
game, receives only the four documented public fields, and never sees another seat's
action before choosing its own.
"""
import os
import random
import sys
import time
import types

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "simulator", "vendor_harness"))
from referee import DEFAULT_RULES, Referee, mirror, random_map, example_map  # noqa: E402

LEGACY = os.path.join(ROOT, "lab", "legacy")
POOL = os.path.join(ROOT, "lab", "pool")


class Cell(object):
    __slots__ = ("occupant", "owner", "is_upgraded", "is_home", "is_frozen", "base_points")

    def __init__(self, occupant, owner, is_upgraded, is_home, is_frozen, base_points):
        self.occupant = occupant
        self.owner = owner
        self.is_upgraded = is_upgraded
        self.is_home = is_home
        self.is_frozen = is_frozen
        self.base_points = base_points


class Game(object):
    __slots__ = ("board", "bot_id", "is_priority_token", "legal_actions")

    def __init__(self, board, bot_id, is_priority_token, legal_actions):
        self.board = board
        self.bot_id = bot_id
        self.is_priority_token = is_priority_token
        self.legal_actions = legal_actions


_CODE = {}


def _code(path):
    code = _CODE.get(path)
    if code is None:
        with open(path, "rb") as handle:
            code = compile(handle.read(), path, "exec")
        _CODE[path] = code
    return code


_LEGACY_MODS = {}


def _legacy(seed):
    """Class-based opponents from the first project phase (zoo/holdout/aifield/probot)."""
    if not _LEGACY_MODS:
        sys.path.insert(0, LEGACY)
        import aifield
        import holdout
        import probot
        import zoo
        import json
        table = {}
        for cls in zoo.ZOO + holdout.HOLDOUT + aifield.AIFIELD:
            table[cls.name] = cls
        params = json.load(open(os.path.join(LEGACY, "pro_params_v1.json")))
        table["pro"] = probot.factory(None, "pro")
        table["pro_tuned"] = probot.factory(params, "pro_tuned")
        _LEGACY_MODS.update(table)
    return _LEGACY_MODS


def resolve(name):
    """Bot name -> source path, or ('legacy', name)."""
    if name.startswith("legacy:"):
        return ("legacy", name[7:])
    if os.path.isabs(name) and os.path.exists(name):
        return ("file", name)
    for folder in (POOL, os.path.join(ROOT, "lab", "ext"), os.path.join(ROOT, "lab", "stress"),
                   os.path.join(ROOT, "lab", "fresh"), os.path.join(ROOT, "lab", "cand"),
                   os.path.join(ROOT, "lab", "holdout")):
        path = os.path.join(folder, name + ".py")
        if os.path.exists(path):
            return ("file", path)
    path = os.path.join(ROOT, name)
    if os.path.exists(path):
        return ("file", path)
    raise KeyError("unknown bot %r" % name)


def make_actor(name, seed=0):
    kind, ref = resolve(name)
    if kind == "legacy":
        return _legacy(seed)[ref](seed)
    module = types.ModuleType("bot")
    module.__file__ = ref
    # Bots that seed their own RNG from the module-level `random` get a per-game stream.
    exec(_code(ref), module.__dict__)
    return module.act


def build_states(game):
    """Four independent Game objects for the current pre-turn board."""
    occ = {}
    for i, p in enumerate(game.pos):
        occ[p] = i + 1
    owner, upg, home, base, frozen = game.owner, game.upg, game.home, game.base, game.frozen
    out = []
    for seat in (1, 2, 3, 4):
        board = []
        for r in range(8):
            row = []
            for c in range(8):
                p = r * 8 + c
                o = occ.get(p, 0)
                row.append(Cell(o, owner[p], bool(upg[p]), bool(home[p]),
                                bool(o and frozen[o - 1] > 0), base[p]))
            board.append(row)
        out.append(Game(board, seat, game.token == seat, game.legal(seat - 1)))
    return out


def play(names, base, token=1, rules=None, seed=0, record=False, timing=False, max_turns=80):
    """Play one game. Returns dict(scores, pw, faults[, actions, ms])."""
    rnd_state = random.getstate()
    random.seed(seed * 7919 + 13)
    actors = [make_actor(n, seed * 4 + i) for i, n in enumerate(names)]
    game = Referee(base, rules=rules, start_token=token, max_turns=max_turns)
    faults = [0] * 4
    ms = [0.0] * 4
    worst = [0.0] * 4
    log = [] if record else None
    while not game.over():
        states = build_states(game)
        chosen = []
        for i in range(4):
            legal = states[i].legal_actions
            t0 = time.perf_counter() if timing else 0.0
            try:
                a = actors[i](states[i])
            except Exception:
                a = "STAY"
                faults[i] += 1
            if timing:
                dt = (time.perf_counter() - t0) * 1000.0
                ms[i] += dt
                if dt > worst[i] and game.turn > 1:
                    worst[i] = dt
            if a not in legal:
                a = "STAY"
                faults[i] += 1
            chosen.append(a)
        if record:
            snap = game.snapshot()
            log.append((snap, list(chosen), game.step(chosen)))
        else:
            game.step(chosen)
    random.setstate(rnd_state)
    s = game.score
    pw = [sum(1.0 if s[i] > s[j] else 0.5 if s[i] == s[j] else 0.0 for j in range(4) if j != i)
          for i in range(4)]
    out = {"scores": list(s), "pw": pw, "faults": faults}
    if timing:
        out["ms"] = [m / max_turns for m in ms]
        out["worst_ms"] = worst
    if record:
        out["log"] = log
        out["final"] = game.snapshot()
    return out


# ----------------------------------------------------------------------------- maps

def _quad_gradient(rnd, slope, noise):
    q = []
    for r in range(4):
        row = []
        for c in range(4):
            d = (3 - r) + (3 - c)
            v = 3.0 - d * slope + rnd.uniform(-noise, noise)
            row.append(max(1, min(3, int(round(v)))))
        q.append(row)
    return q


def make_map(family, seed):
    """Mirrored 8x8 maps, values 1..3. The organisers' real distribution is unknown,
    so measurements mix several families instead of trusting one."""
    rnd = random.Random("%s/%d" % (family, seed))
    if family == "example":
        return example_map()
    if family == "gradient":      # same generator the earlier project phases used
        return random_map(rnd.randrange(1 << 30))
    if family == "noisy":
        q = _quad_gradient(rnd, rnd.uniform(0.25, 0.6), rnd.uniform(0.8, 1.4))
        q[0][0] = min(q[0][0], 2)
        return mirror(q)
    if family == "uniform":
        q = [[rnd.choice((1, 2, 3)) for _ in range(4)] for _ in range(4)]
        return mirror(q)
    if family == "richhome":      # value falls toward the centre: the opposite of the example
        q = []
        for r in range(4):
            row = []
            for c in range(4):
                d = r + c
                v = 3.0 - d * rnd.uniform(0.3, 0.5) + rnd.uniform(-0.6, 0.6)
                row.append(max(1, min(3, int(round(v)))))
            q.append(row)
        return mirror(q)
    if family == "ring":          # a band of 3s away from both the corner and the centre
        q = []
        for r in range(4):
            row = []
            for c in range(4):
                d = abs((r + c) - 3)
                v = 3.0 - d * rnd.uniform(0.5, 0.9) + rnd.uniform(-0.5, 0.5)
                row.append(max(1, min(3, int(round(v)))))
            q.append(row)
        return mirror(q)
    # ---- families below were added for the final test and never used in development
    if family == "flat":          # every cell worth the same
        v = rnd.choice((1, 2, 3))
        return mirror([[v] * 4 for _ in range(4)])
    if family == "centre":        # only the middle of the board is rich
        q = [[(3 if r >= 2 and c >= 2 else rnd.choice((1, 1, 2))) for c in range(4)] for r in range(4)]
        return mirror(q)
    if family == "edges":         # the rim is rich, the interior poor
        q = [[(3 if r == 0 or c == 0 else rnd.choice((1, 1, 2))) for c in range(4)] for r in range(4)]
        return mirror(q)
    if family == "stripes":
        hi = rnd.randrange(2)
        q = [[(3 if r % 2 == hi else 1) for c in range(4)] for r in range(4)]
        return mirror(q)
    if family == "checker":
        hi = rnd.randrange(2)
        q = [[(3 if (r + c) % 2 == hi else 1) for c in range(4)] for r in range(4)]
        return mirror(q)
    if family == "sparse":        # poor land with a few jackpots
        q = [[1] * 4 for _ in range(4)]
        for _ in range(rnd.choice((2, 3))):
            q[rnd.randrange(4)][rnd.randrange(4)] = 3
        return mirror(q)
    if family == "rich":          # nearly everything is a 3
        q = [[3] * 4 for _ in range(4)]
        for _ in range(rnd.choice((2, 3, 4))):
            q[rnd.randrange(4)][rnd.randrange(4)] = rnd.choice((1, 2))
        return mirror(q)
    raise ValueError(family)


FAMILIES = ("example", "gradient", "gradient", "noisy", "uniform", "richhome", "ring")
NEW_FAMILIES = ("flat", "centre", "edges", "stripes", "checker", "sparse", "rich")
