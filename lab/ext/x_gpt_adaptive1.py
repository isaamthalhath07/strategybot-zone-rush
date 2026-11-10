"""Adaptive bot: remembers hostile raiders and prioritizes retaliation against the worst offender."""

from collections import deque

_raids = {1: 0, 2: 0, 3: 0, 4: 0}
_previous = None
_previous_positions = {}
_last_enemy = None


def act(state):
    global _raids, _previous, _previous_positions, _last_enemy

    raw = state.board
    board = [c for row in raw for c in row] if raw and isinstance(raw[0], (list, tuple)) else raw
    me = state.bot_id
    legal = state.legal_actions

    pos = next((i for i, c in enumerate(board) if c.occupant == me), None)

    if pos is None:
        return "STAY"

    if board[pos].is_frozen:
        return "STAY"

    # Track the locations of the opponents.
    enemy_positions = {
        c.occupant: i
        for i, c in enumerate(board)
        if c.occupant not in (0, me)
    }

    # Detect changes in our ownership map.
    if _previous is not None:
        for i, cell in enumerate(board):
            old_owner = _previous[i]

            if old_owner == me and cell.owner not in (0, me):
                attacker = cell.owner

                if attacker in _raids:
                    _raids[attacker] += 1

                    # Extra weight for expensive property.
                    if cell.base_points == 3:
                        _raids[attacker] += 1

    _previous = [c.owner for c in board]
    _previous_positions = enemy_positions.copy()

    # Determine our current nemesis.
    enemies = [p for p in range(1, 5) if p != me]
    nemesis = max(enemies, key=lambda p: _raids[p])

    if _raids[nemesis] == 0:
        nemesis = None

    if board[pos].owner != me and not board[pos].is_home and "STAY" in legal:  # FIX: arriving does not take a cell (rulebook: STAY on it); the target search below skips the cell it stands on, so it walked off every target
        return "STAY"

    def neighbors(p):
        r, c = divmod(p, 8)
        if r > 0: yield "NORTH", p - 8
        if c < 7: yield "EAST", p + 1
        if r < 7: yield "SOUTH", p + 8
        if c > 0: yield "WEST", p - 1

    # BFS to find reachable cells.
    distance = {pos: 0}
    first_action = {}
    queue = deque([pos])

    while queue:
        p = queue.popleft()

        for action, n in neighbors(p):
            if board[n].occupant != 0 or n in distance:
                continue

            distance[n] = distance[p] + 1
            first_action[n] = action if p == pos else first_action[p]
            queue.append(n)

    choices = []

    for p, d in distance.items():
        cell = board[p]

        if p == pos or cell.owner == me or cell.is_home:
            continue

        # Retaliation is deliberately biased toward the worst raider.
        score = cell.base_points * 2.0

        if cell.owner != 0:
            score += 5.0

        if nemesis is not None:
            if cell.owner == nemesis:
                score += 18.0 + _raids[nemesis] * 3.0
            else:
                score -= 3.0

        # A raid on a developed cell is less attractive because it takes longer.
        if cell.is_upgraded:
            score -= 4.0

        score /= (d + 1) ** 0.9

        choices.append((score, p))

    if choices:
        choices.sort(reverse=True)
        target = choices[0][1]
        move = first_action.get(target)

        if move in legal:
            return move

    # If we are already on valuable land, invest in it.
    here = board[pos]

    if here.owner == me and not here.is_upgraded:
        if here.base_points >= 2 and "STAY" in legal:
            return "STAY"

    # Fallback: expand into the most valuable adjacent property.
    local = []

    for action, n in neighbors(pos):
        if action not in legal or board[n].occupant:
            continue

        c = board[n]
        if c.owner == me or c.is_home:
            continue

        local.append((c.base_points, action))

    if local:
        return max(local)[1]

    return "STAY" if "STAY" in legal else legal[0]