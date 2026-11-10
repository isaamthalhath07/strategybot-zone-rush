"""Turtle: secure a small area around home, improve it, and shield whenever rivals occupy its land."""

from collections import deque

_TURN = 0
_LAST_SHIELD = -100
_old_position = None
_old_owner = None
_old_action = None
_streak = 0


def read(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def as_int(obj, key, default=0):
    try:
        return int(read(obj, key, default))
    except (TypeError, ValueError):
        return default


def as_bool(obj, key):
    return bool(read(obj, key, False))


def get_board(state):
    board = read(state, "board", [])
    if board and isinstance(board[0], (list, tuple)):
        board = [cell for row in board for cell in row]
    return list(board)


def home_for(cells, player):
    for i, cell in enumerate(cells):
        if as_bool(cell, "is_home") and as_int(cell, "owner") == player:
            return i
    return {1: 0, 2: 7, 3: 63, 4: 56}.get(player, 0)


def neighbors(index):
    row, col = divmod(index, 8)
    if row > 0:
        yield "NORTH", index - 8
    if col < 7:
        yield "EAST", index + 1
    if row < 7:
        yield "SOUTH", index + 8
    if col > 0:
        yield "WEST", index - 1


def search_local(cells, start, is_local):
    distances = {start: 0}
    first_moves = {start: None}
    queue = deque([start])

    while queue:
        here = queue.popleft()

        for action, nxt in neighbors(here):
            if nxt in distances or not is_local(nxt):
                continue
            if as_int(cells[nxt], "occupant") != 0:
                continue

            distances[nxt] = distances[here] + 1
            first_moves[nxt] = (
                action if here == start else first_moves[here]
            )
            queue.append(nxt)

    return distances, first_moves


def complete_turn(pos, owner, chosen, legal):
    global _old_position, _old_owner, _old_action

    if chosen not in legal:
        chosen = "STAY" if "STAY" in legal else legal[0]

    _old_position = pos
    _old_owner = owner
    _old_action = chosen
    return chosen


def act(state):
    global _TURN, _LAST_SHIELD, _streak

    turn = _TURN
    _TURN += 1

    cells = get_board(state)
    legal = list(read(state, "legal_actions", ["STAY"]))

    if len(cells) != 64:
        return "STAY" if "STAY" in legal else legal[0]
    if not legal:
        return "STAY"

    player = as_int(state, "bot_id", 1)
    home = home_for(cells, player)

    position = next(
        (i for i, cell in enumerate(cells)
         if as_int(cell, "occupant") == player),
        home
    )

    current = cells[position]
    owner = as_int(current, "owner")
    frozen = as_bool(current, "is_frozen")

    if (
        _old_position == position
        and _old_action == "STAY"
        and _old_owner == owner
        and not frozen
    ):
        _streak += 1
    else:
        _streak = 0

    if frozen:
        return complete_turn(position, owner, "STAY", legal)

    # A rival on our land is the turtle's main reason to use a shield.
    enemy_on_our_land = any(
        as_int(cell, "occupant") not in (0, player)
        and as_int(cell, "owner") == player
        and not as_bool(cell, "is_frozen")
        for cell in cells
    )

    if (
        enemy_on_our_land
        and "SHIELD" in legal
        and turn - _LAST_SHIELD >= 5
    ):
        action = complete_turn(position, owner, "SHIELD", legal)
        if action == "SHIELD":
            _LAST_SHIELD = turn
        return action

    # Never abandon a cell before taking it.
    if owner != player:
        return complete_turn(position, owner, "STAY", legal)

    # Keep working on an upgrade once its progress has started.
    if not as_bool(current, "is_upgraded") and 0 < _streak < 3:
        return complete_turn(position, owner, "STAY", legal)

    home_row, home_col = divmod(home, 8)

    # The turtle only operates in the 3x3 region around its home corner.
    def nearby(index):
        row, col = divmod(index, 8)
        return max(abs(row - home_row), abs(col - home_col)) <= 2

    distance, first_move = search_local(cells, position, nearby)

    # Secure the local area before spending turns on upgrades.
    claims = []

    for index, dist in distance.items():
        cell = cells[index]

        if as_int(cell, "owner") == player:
            continue
        if as_bool(cell, "is_home"):
            continue

        value = max(1, as_int(cell, "base_points", 1))
        rival_land = 1 if as_int(cell, "owner") not in (0, player) else 0

        claims.append(((value, rival_land, -dist), index))

    if claims:
        _, target = max(claims, key=lambda item: item[0])

        if target == position:
            action = "STAY"
        else:
            action = first_move[target] or "STAY"

        return complete_turn(position, owner, action, legal)

    # Once the nearby region is secured, upgrade its best cells first.
    upgrades = []

    for index, dist in distance.items():
        cell = cells[index]

        if as_int(cell, "owner") != player:
            continue
        if as_bool(cell, "is_upgraded"):
            continue

        value = max(1, as_int(cell, "base_points", 1))
        upgrades.append(((value, -dist), index))

    if upgrades:
        _, target = max(upgrades, key=lambda item: item[0])

        if target == position:
            action = "STAY"
        else:
            action = first_move[target] or "STAY"

        return complete_turn(position, owner, action, legal)

    # The local territory is fully secured and upgraded.
    return complete_turn(position, owner, "STAY", legal)