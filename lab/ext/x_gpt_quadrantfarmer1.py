"""Quadrant farmer: fill the home quadrant, then upgrade its highest-value cells first."""

from collections import deque

_TURN = 0
_previous_position = None
_previous_owner = None
_previous_action = None
_stays_here = 0


def field(obj, name, default=None):
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def number(obj, name, default=0):
    try:
        return int(field(obj, name, default))
    except (TypeError, ValueError):
        return default


def yes(obj, name):
    return bool(field(obj, name, False))


def read_cells(state):
    board = field(state, "board", [])
    if board and isinstance(board[0], (list, tuple)):
        board = [cell for row in board for cell in row]
    return list(board)


def home_index(cells, player):
    for i, cell in enumerate(cells):
        if yes(cell, "is_home") and number(cell, "owner") == player:
            return i
    return {1: 0, 2: 7, 3: 63, 4: 56}.get(player, 0)


def adjacent(index):
    row, col = divmod(index, 8)
    moves = []
    if row > 0:
        moves.append(("NORTH", index - 8))
    if col < 7:
        moves.append(("EAST", index + 1))
    if row < 7:
        moves.append(("SOUTH", index + 8))
    if col > 0:
        moves.append(("WEST", index - 1))
    return moves


def reachable_cells(cells, start, inside_quadrant):
    distance = {start: 0}
    first = {start: None}
    queue = deque([start])

    while queue:
        current = queue.popleft()

        for direction, nxt in adjacent(current):
            if nxt in distance:
                continue
            if not inside_quadrant(nxt):
                continue
            if number(cells[nxt], "occupant") != 0:
                continue

            distance[nxt] = distance[current] + 1
            first[nxt] = direction if current == start else first[current]
            queue.append(nxt)

    return distance, first


def respond(pos, owner, desired, legal):
    global _previous_position, _previous_owner, _previous_action

    if desired not in legal:
        desired = "STAY" if "STAY" in legal else legal[0]

    _previous_position = pos
    _previous_owner = owner
    _previous_action = desired
    return desired


def act(state):
    global _TURN, _stays_here

    turn = _TURN
    _TURN += 1

    cells = read_cells(state)
    legal = list(field(state, "legal_actions", ["STAY"]))

    if len(cells) != 64:
        return "STAY" if "STAY" in legal else legal[0]
    if not legal:
        return "STAY"

    player = number(state, "bot_id", 1)
    home = home_index(cells, player)

    pos = next(
        (i for i, cell in enumerate(cells)
         if number(cell, "occupant") == player),
        home
    )

    current = cells[pos]
    owner = number(current, "owner")
    frozen = yes(current, "is_frozen")

    if (
        _previous_position == pos
        and _previous_action == "STAY"
        and _previous_owner == owner
        and not frozen
    ):
        _stays_here += 1
    else:
        _stays_here = 0

    if frozen or owner != player:
        return respond(pos, owner, "STAY", legal)

    # Complete an upgrade already in progress.
    if not yes(current, "is_upgraded") and 0 < _stays_here < 3:
        return respond(pos, owner, "STAY", legal)

    home_row, home_col = divmod(home, 8)

    row_min = 0 if home_row < 4 else 4
    row_max = 4 if home_row < 4 else 8
    col_min = 0 if home_col < 4 else 4
    col_max = 4 if home_col < 4 else 8

    def in_my_quadrant(index):
        row, col = divmod(index, 8)
        return (
            row_min <= row < row_max
            and col_min <= col < col_max
        )

    distance, first_move = reachable_cells(cells, pos, in_my_quadrant)

    # Phase one: claim every reachable cell in the home quadrant.
    unclaimed = []

    for index, dist in distance.items():
        cell = cells[index]
        cell_owner = number(cell, "owner")

        if cell_owner == player or yes(cell, "is_home"):
            continue

        value = max(1, number(cell, "base_points", 1))
        rival_bonus = 1 if cell_owner not in (0, player) else 0

        # Point value comes first; distance breaks ties.
        unclaimed.append(((value, rival_bonus, -dist), index))

    if unclaimed:
        _, target = max(unclaimed, key=lambda item: item[0])

        if target == pos:
            action = "STAY"
        else:
            action = first_move[target] or "STAY"

        return respond(pos, owner, action, legal)

    # Phase two: all local territory is ours. Upgrade the most valuable
    # cells first, using distance only to break equal-value ties.
    upgrades = []

    for index, dist in distance.items():
        cell = cells[index]

        if number(cell, "owner") != player:
            continue
        if yes(cell, "is_upgraded"):
            continue

        value = max(1, number(cell, "base_points", 1))
        upgrades.append(((value, -dist), index))

    if upgrades:
        _, target = max(upgrades, key=lambda item: item[0])

        if target == pos:
            action = "STAY"
        else:
            action = first_move[target] or "STAY"

        return respond(pos, owner, action, legal)

    # Nothing useful remains inside the quadrant.
    return respond(pos, owner, "STAY", legal)