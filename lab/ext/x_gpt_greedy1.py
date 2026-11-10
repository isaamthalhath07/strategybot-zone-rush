"""Greedy value-per-distance claimer: maximise territory value gained per turn spent."""

from collections import deque

_TURN = 0
_prev_pos = None
_prev_owner = None
_prev_action = None
_streak = 0


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _num(cell, key, default=0):
    try:
        return int(_get(cell, key, default))
    except (TypeError, ValueError):
        return default


def _flag(cell, key):
    return bool(_get(cell, key, False))


def _board(state):
    raw = _get(state, "board", [])
    if raw and isinstance(raw[0], (list, tuple)):
        raw = [item for row in raw for item in row]
    return list(raw)


def _adjacent(i):
    r, c = divmod(i, 8)
    if r:
        yield "NORTH", i - 8
    if c < 7:
        yield "EAST", i + 1
    if r < 7:
        yield "SOUTH", i + 8
    if c:
        yield "WEST", i - 1


def _bfs(cells, start):
    dist = {start: 0}
    opening = {start: None}
    todo = deque([start])

    while todo:
        here = todo.popleft()
        for move, nxt in _adjacent(here):
            if nxt in dist or _num(cells[nxt], "occupant") != 0:
                continue
            dist[nxt] = dist[here] + 1
            opening[nxt] = move if here == start else opening[here]
            todo.append(nxt)

    return dist, opening


def _finish(pos, owner, action, legal):
    global _prev_pos, _prev_owner, _prev_action

    if action not in legal:
        action = "STAY" if "STAY" in legal else legal[0]

    _prev_pos = pos
    _prev_owner = owner
    _prev_action = action
    return action


def act(state):
    global _TURN, _streak

    turn = _TURN
    _TURN += 1

    cells = _board(state)
    legal = list(_get(state, "legal_actions", ["STAY"]))

    if len(cells) != 64:
        return "STAY" if "STAY" in legal else legal[0]
    if not legal:
        return "STAY"

    me = _num(state, "bot_id", 1)
    pos = next(
        (i for i, x in enumerate(cells) if _num(x, "occupant") == me),
        -1
    )

    if pos < 0:
        pos = next(
            (i for i, x in enumerate(cells)
             if _flag(x, "is_home") and _num(x, "owner") == me),
            {1: 0, 2: 7, 3: 63, 4: 56}.get(me, 0)
        )

    here = cells[pos]
    owner = _num(here, "owner")
    frozen = _flag(here, "is_frozen")

    if (
        _prev_pos == pos
        and _prev_action == "STAY"
        and _prev_owner == owner
        and not frozen
    ):
        _streak += 1
    else:
        _streak = 0

    if frozen or owner != me:
        return _finish(pos, owner, "STAY", legal)

    # Once an upgrade has begun, finish it rather than wasting progress.
    if (
        not _flag(here, "is_upgraded")
        and _streak > 0
        and _streak < 3
    ):
        return _finish(pos, owner, "STAY", legal)

    distances, openings = _bfs(cells, pos)
    remaining = max(1, 80 - turn)

    best_value = float("-inf")
    best_cell = None

    for index, dist in distances.items():
        cell = cells[index]
        cell_owner = _num(cell, "owner")
        value = max(1, _num(cell, "base_points", 1))
        upgraded = _flag(cell, "is_upgraded")

        if cell_owner != me:
            if _flag(cell, "is_home"):
                continue

            capture_turns = 3 if cell_owner != 0 and upgraded else 1
            raid = 0
            if cell_owner not in (0, me):
                raid = 8 * value * (2 if upgraded else 1)

            # Future income plus the one-off raid reward.
            gain = value * remaining + raid
            ratio = gain / (dist + capture_turns + 1.0)

        elif not upgraded:
            # Upgrading adds one extra point per turn for this cell.
            gain = value * remaining
            ratio = 0.90 * gain / (dist + 4.0)

        else:
            continue

        if ratio > best_value:
            best_value = ratio
            best_cell = index

    if best_cell is None or best_cell == pos:
        action = "STAY"
    else:
        action = openings[best_cell] or "STAY"

    # This bot deliberately never selects SHIELD.
    if action == "SHIELD":
        action = "STAY"

    return _finish(pos, owner, action, legal)