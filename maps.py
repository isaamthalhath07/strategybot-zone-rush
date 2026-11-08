"""
Map families that stay inside the rulebook but outside my own map generator.

The rulebook guarantees exactly two things about a map: every cell is worth 1, 2
or 3 points per turn, and the board is four-fold mirrored. It says values are
"generally more toward the middle" -- a tendency, not a rule -- and it says
nothing at all about homes being cheap.

engine.make_map nonetheless always builds an inward gradient and caps the home
corner at 2. That was my inference from the rulebook's example map, and every
training game, every tuning run and every measurement in this repo was played on
maps like that. So the tuned weights have never seen a valuable home, and a
weight like home_bonus (v7 discounts work on its own home by 19%) was learned on
a distribution where discounting the home was harmless because the home was
worth little. A map the organisers draw differently is exactly where that kind of
weight fails silently.

Each family below breaks one assumption and keeps the two real guarantees:

  standard    engine.make_map unchanged -- the control
  richhome    the standard generator, but the home corner is worth 3. One
              variable changed: is the bot's handling of its home miscalibrated?
  richcorner  the home and both of its neighbours are worth 3, so the most
              valuable land is the land nobody else can reach first
  inverted    the gradient reversed: richest at the corners, poorest in the
              middle. Breaks the centre-steal opening and every centre heuristic
  flat        every cell worth 2. No gradient at all, so nothing to read
  noise       every quadrant cell independently 1, 2 or 3. Structure-free
  edge        a rich outer ring with a poor interior and a cheap home, so the
              valuable land is far from everyone's home but not in the middle

    MAPS=richhome python measure.py 300 strangers v7=v7_params.json
    python maps.py              # print one example quadrant of every family
"""
import os
import random

import engine

N = engine.N
NC = engine.NC


def _mirror(q):
    """Reflect a 4x4 quadrant (q[0][0] is the home corner) into a full board,
    clamping to the rulebook's 1..3 so no family can stray outside it."""
    base = [0] * NC
    for r in range(4):
        for c in range(4):
            v = max(1, min(3, int(round(q[r][c]))))
            base[r * N + c] = v
            base[r * N + (N - 1 - c)] = v
            base[(N - 1 - r) * N + c] = v
            base[(N - 1 - r) * N + (N - 1 - c)] = v
    return base


def _quadrant_from(base):
    return [[base[r * N + c] for c in range(4)] for r in range(4)]


def _rnd(family, seed):
    # A string seed is hashed deterministically (sha512), unaffected by
    # PYTHONHASHSEED, so every worker process draws the same map for a task.
    return random.Random("%s:%d" % (family, seed))


def _standard(seed):
    return engine.make_map(seed=seed)


def _richhome(seed):
    q = _quadrant_from(engine.make_map(seed=seed))
    q[0][0] = 3
    return _mirror(q)


def _richcorner(seed):
    q = _quadrant_from(engine.make_map(seed=seed))
    q[0][0] = q[0][1] = q[1][0] = 3
    return _mirror(q)


def _inverted(seed):
    rnd = _rnd("inverted", seed)
    slope = rnd.uniform(0.33, 0.58)
    noise = rnd.uniform(0.25, 0.75)
    q = []
    for r in range(4):
        row = []
        for c in range(4):
            d = (3 - r) + (3 - c)            # 0 nearest the centre, 6 at home
            row.append(1.0 + d * slope + rnd.uniform(-noise, noise))
        q.append(row)
    return _mirror(q)


def _flat(seed):
    return _mirror([[2] * 4 for _ in range(4)])


def _noise(seed):
    rnd = _rnd("noise", seed)
    return _mirror([[rnd.randint(1, 3) for _ in range(4)] for _ in range(4)])


def _edge(seed):
    rnd = _rnd("edge", seed)
    q = []
    for r in range(4):
        row = []
        for c in range(4):
            ring = min(r, c)                 # 0 on the outer edge, 3 innermost
            row.append(3.0 - ring * 0.8 + rnd.uniform(-0.4, 0.4))
        q.append(row)
    q[0][0] = 1                              # the home stays cheap
    return _mirror(q)


FAMILIES = {
    "standard": _standard,
    "richhome": _richhome,
    "richcorner": _richcorner,
    "inverted": _inverted,
    "flat": _flat,
    "noise": _noise,
    "edge": _edge,
}


def make(seed, family=None):
    """The map for one task. With no family given, MAPS picks it, defaulting to
    the standard generator so every existing measurement is unchanged."""
    family = family or os.environ.get("MAPS", "standard")
    try:
        fn = FAMILIES[family]
    except KeyError:
        raise SystemExit("unknown map family %r (want one of: %s)"
                         % (family, ", ".join(sorted(FAMILIES))))
    return fn(seed)


if __name__ == "__main__":
    for name in FAMILIES:
        q = _quadrant_from(make(12345, name))
        print("%-11s home corner top-left" % name)
        for row in q:
            print("            " + " ".join(str(v) for v in row))
        print()
