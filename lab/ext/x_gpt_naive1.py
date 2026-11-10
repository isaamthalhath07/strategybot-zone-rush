"""Naive generalist: claim profitable nearby cells and upgrade valuable territory."""

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


def _read_board(state):
    raw = _get(state, "board", [])
    if raw and isinstance(raw[0], (list, tuple)):
        raw = [cell for row in raw for cell in row]
    return list(raw)


def _neighbors(index):
    row, col = divmod(index, 8)
    result = []
    if row > 0:
        result.append(("NORTH", index - 8))
    if col < 7:
        result.append(("EAST", index + 1))
    if row < 7:
        result.append(("SOUTH", index + 8))
    if col > 0:
        result.append(("WEST", index - 1))
    return result


def _routes(cells, start):
    distance = {start: 0}
    first_move = {start: None}
    queue = deque([start])

    while queue:
        current = queue.popleft()

        for action, nxt in _neighbors(current):
            if nxt in distance:
                continue
            if _num(cells[nxt], "occupant") != 0:
                continue

            distance[nxt] = distance[current] + 1
            first_move[nxt] = (
                action if current == start else first_move[current]
            )
            queue.append(nxt)

    return distance, first_move


def _save(pos, owner, action, legal):
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

    cells = _read_board(state)
    if len(cells) != 64:
        legal = list(_get(state, "legal_actions", ["STAY"]))
        return "STAY" if "STAY" in legal else legal[0]

    legal = list(_get(state, "legal_actions", ["STAY"]))
    if not legal:
        return "STAY"

    me = _num(state, "bot_id", 1)
    pos = next(
        (i for i, cell in enumerate(cells)
         if _num(cell, "occupant") == me),
        -1
    )

    home = next(
        (i for i, cell in enumerate(cells)
         if _flag(cell, "is_home") and _num(cell, "owner") == me),
        {1: 0, 2: 7, 3: 63, 4: 56}.get(me, 0)
    )

    if pos < 0:
        pos = home

    current = cells[pos]
    owner = _num(current, "owner")
    points = _num(current, "base_points", 1)
    upgraded = _flag(current, "is_upgraded")
    frozen = _flag(current, "is_frozen")

    if (
        _prev_pos == pos
        and _prev_action == "STAY"
        and _prev_owner == owner
        and not frozen
    ):
        _streak += 1
    else:
        _streak = 0

    if frozen:
        return _save(pos, owner, "STAY", legal)

    # Finish taking any cell we are currently standing on.
    if owner != me:
        return _save(pos, owner, "STAY", legal)

    # A high-value cell is worth upgrading before moving on.
    if not upgraded and points >= 3 and _streak < 3:
        return _save(pos, owner, "STAY", legal)

    # Do not abandon an upgrade that is already underway.
    if not upgraded and points >= 2 and 0 < _streak < 3:
        return _save(pos, owner, "STAY", legal)

    distance, first_move = _routes(cells, pos)
    remaining = max(1, 80 - turn)

    best_score = float("-inf")
    best_target = None

    for index, dist in distance.items():
        cell = cells[index]
        cell_owner = _num(cell, "owner")
        value = max(1, _num(cell, "base_points", 1))
        is_home = _flag(cell, "is_home")
        is_upgraded = _flag(cell, "is_upgraded")

        if cell_owner != me:
            if is_home:
                continue

            stays = 3 if cell_owner != 0 and is_upgraded else 1
            raid = (
                8 * value * (2 if is_upgraded else 1)
                if cell_owner not in (0, me)
                else 0
            )
            gain = value * remaining + raid
            score = gain / (dist + stays + 1.0)

        elif not is_upgraded and value >= 2:
            gain = value * remaining * 0.70
            score = gain / (dist + 4.0)

        else:
            continue

        if score > best_score:
            best_score = score
            best_target = index

    if best_target is None or best_target == pos:
        action = "STAY"
    else:
        action = first_move[best_target] or "STAY"

    return _save(pos, owner, action, legal)