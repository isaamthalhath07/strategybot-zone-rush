"""Raider: expand early, attack unupgraded rival cells after turn 20, and shield invaded land."""

from collections import deque

_TURN = 0
_LAST_SHIELD = -100
_previous_position = None
_previous_owner = None
_previous_action = None
_stay_count = 0


def get(obj, name, default=None):
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def integer(obj, name, default=0):
    try:
        return int(get(obj, name, default))
    except (TypeError, ValueError):
        return default


def flag(obj, name):
    return bool(get(obj, name, False))


def board_of(state):
    raw = get(state, "board", [])
    if raw and isinstance(raw[0], (list, tuple)):
        raw = [cell for row in raw for cell in row]
    return list(raw)


def neighbors(i):
    r, c = divmod(i, 8)
    if r > 0:
        yield "NORTH", i - 8
    if c < 7:
        yield "EAST", i + 1
    if r < 7:
        yield "SOUTH", i + 8
    if c > 0:
        yield "WEST", i - 1


def find_routes(cells, start):
    distance = {start: 0}
    first_step = {start: None}
    queue = deque([start])

    while queue:
        here = queue.popleft()

        for move, nxt in neighbors(here):
            if nxt in distance:
                continue
            if integer(cells[nxt], "occupant") != 0:
                continue

            distance[nxt] = distance[here] + 1
            first_step[nxt] = (
                move if here == start else first_step[here]
            )
            queue.append(nxt)

    return distance, first_step


def finish(pos, owner, action, legal):
    global _previous_position, _previous_owner, _previous_action

    if action not in legal:
        action = "STAY" if "STAY" in legal else legal[0]

    _previous_position = pos
    _previous_owner = owner
    _previous_action = action
    return action


def act(state):
    global _TURN, _LAST_SHIELD, _stay_count

    turn = _TURN
    _TURN += 1

    cells = board_of(state)
    legal = list(get(state, "legal_actions", ["STAY"]))

    if len(cells) != 64:
        return "STAY" if "STAY" in legal else legal[0]
    if not legal:
        return "STAY"

    me = integer(state, "bot_id", 1)

    home = next(
        (i for i, cell in enumerate(cells)
         if flag(cell, "is_home") and integer(cell, "owner") == me),
        {1: 0, 2: 7, 3: 63, 4: 56}.get(me, 0)
    )

    pos = next(
        (i for i, cell in enumerate(cells)
         if integer(cell, "occupant") == me),
        home
    )

    current = cells[pos]
    owner = integer(current, "owner")
    frozen = flag(current, "is_frozen")

    if (
        _previous_position == pos
        and _previous_action == "STAY"
        and _previous_owner == owner
        and not frozen
    ):
        _stay_count += 1
    else:
        _stay_count = 0

    if frozen:
        return finish(pos, owner, "STAY", legal)

    # Shield when an unfrozen rival is occupying any of our territory.
    rival_on_my_land = any(
        integer(cell, "occupant") not in (0, me)
        and integer(cell, "owner") == me
        and not flag(cell, "is_frozen")
        for cell in cells
    )

    if (
        rival_on_my_land
        and "SHIELD" in legal
        and turn - _LAST_SHIELD >= 5
    ):
        action = finish(pos, owner, "SHIELD", legal)
        if action == "SHIELD":
            _LAST_SHIELD = turn
        return action

    # Finish taking the cell we are standing on.
    if owner != me:
        return finish(pos, owner, "STAY", legal)

    distance, first_step = find_routes(cells, pos)
    remaining = max(1, 80 - turn)

    # Before turn 20, focus on neutral expansion.
    # From turn 20 onward, prioritise rival cells that are still level 1.
    preferred_targets = []

    if turn >= 20:
        for index, dist in distance.items():
            cell = cells[index]
            cell_owner = integer(cell, "owner")

            if cell_owner in (0, me):
                continue
            if flag(cell, "is_home") or flag(cell, "is_upgraded"):
                continue

            value = max(1, integer(cell, "base_points", 1))
            raid_bonus = 8 * value
            gain = value * remaining + raid_bonus
            score = gain / (dist + 2.0)
            preferred_targets.append((score, -dist, index))

    if preferred_targets:
        _, _, target = max(preferred_targets)
    else:
        # Neutrals are the fallback target both early and late.
        neutral_targets = []

        for index, dist in distance.items():
            cell = cells[index]

            if integer(cell, "owner") != 0:
                continue
            if flag(cell, "is_home"):
                continue

            value = max(1, integer(cell, "base_points", 1))
            score = value * remaining / (dist + 2.0)
            neutral_targets.append((score, -dist, index))

        if neutral_targets:
            _, _, target = max(neutral_targets)
        else:
            return finish(pos, owner, "STAY", legal)

    if target == pos:
        action = "STAY"
    else:
        action = first_step[target] or "STAY"

    return finish(pos, owner, action, legal)