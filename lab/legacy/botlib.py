"""Shared helpers for the opponent zoo (the submitted bot.py is self-contained)."""
from collections import deque

N = 8
NC = 64
MOVES = (("NORTH", -8), ("SOUTH", 8), ("WEST", -1), ("EAST", 1))
CORNERS = (0, 7, 63, 56)          # seat 1..4

NEIGH = []
for _p in range(NC):
    _r, _c = divmod(_p, N)
    _a = []
    if _r > 0:
        _a.append(_p - N)
    if _r < N - 1:
        _a.append(_p + N)
    if _c > 0:
        _a.append(_p - 1)
    if _c < N - 1:
        _a.append(_p + 1)
    NEIGH.append(tuple(_a))


def parse(view):
    """Flatten the Cell board into parallel arrays. Handles both documented layouts."""
    bd = view.board
    base = [0] * NC
    owner = [0] * NC
    upg = [0] * NC
    home = [0] * NC
    occ = [0] * NC
    frz = [0] * NC
    if bd and isinstance(bd[0], (list, tuple)):
        cells = [bd[r][c] for r in range(N) for c in range(N)]
    else:
        cells = list(bd)
    for p, cl in enumerate(cells):
        base[p] = cl.base_points
        owner[p] = cl.owner
        upg[p] = 1 if cl.is_upgraded else 0
        home[p] = 1 if cl.is_home else 0
        occ[p] = cl.occupant
        frz[p] = 1 if cl.is_frozen else 0
    return base, owner, upg, home, occ, frz


def bfs(start, blocked=()):
    """Step distances from start; blocked cells are impassable."""
    d = [99] * NC
    d[start] = 0
    q = deque([start])
    bl = set(blocked)
    while q:
        u = q.popleft()
        du = d[u] + 1
        for w in NEIGH[u]:
            if d[w] > du and w not in bl:
                d[w] = du
                q.append(w)
    return d


def first_step(start, target, blocked=()):
    """Action name for the first step of a shortest path, or None."""
    if start == target:
        return None
    d = bfs(target, blocked)
    best, bestd = None, d[start]
    if bestd >= 99:
        return None
    for name, delta in MOVES:
        w = start + delta
        if w in NEIGH[start] and d[w] == bestd - 1:
            return name
    return best


def man(a, b):
    ar, ac = divmod(a, N)
    br, bc = divmod(b, N)
    return abs(ar - br) + abs(ac - bc)


def zone_of(p):
    """Which seat's quadrant a cell belongs to (nearest home, ties by seat order)."""
    best, bestd = 1, 99
    for i, c in enumerate(CORNERS):
        d = man(p, c)
        if d < bestd:
            bestd, best = d, i + 1
    return best


def my_cells(owner, seat):
    return [p for p in range(NC) if owner[p] == seat]


def rivals_on_my_land(owner, occ, frz, seat):
    """Rival seats standing on a cell I own, excluding already-frozen ones."""
    out = []
    for p in range(NC):
        o = occ[p]
        if o and o != seat and owner[p] == seat and not frz[p]:
            out.append((p, o))
    return out
