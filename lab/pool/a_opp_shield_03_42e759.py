"""Shield-on-sight: farms the whole board, but raises SHIELD the moment any unfrozen rival is standing on one of its cells."""

_STATE = {"cooldown": 0, "seen": 0}


def _grid(board):
    if len(board) == 64:
        return [board[i * 8:(i + 1) * 8] for i in range(8)]
    return board


def act(state):
    me = state.bot_id
    legal = state.legal_actions
    grid = _grid(state.board)

    pos = None
    owned_total = 0
    on_sight = False
    for r in range(8):
        for c in range(8):
            cell = grid[r][c]
            if cell.occupant == me:
                pos = (r, c)
            if cell.owner:
                owned_total += 1
            if cell.owner == me and cell.occupant not in (0, me) and not cell.is_frozen:
                on_sight = True
    if pos is None:
        return "STAY"

    if owned_total < _STATE["seen"]:
        _STATE["cooldown"] = 0
    _STATE["seen"] = owned_total
    _STATE["cooldown"] = max(0, _STATE["cooldown"] - 1)

    if on_sight and _STATE["cooldown"] == 0 and "SHIELD" in legal:
        _STATE["cooldown"] = 5
        return "SHIELD"

    here = grid[pos[0]][pos[1]]
    if here.owner == 0:
        return "STAY"
    if here.owner == me and not here.is_home and not here.is_upgraded and here.base_points >= 2:
        return "STAY"

    best = None
    for r in range(8):
        for c in range(8):
            cell = grid[r][c]
            if cell.occupant or cell.owner not in (0, me) or cell.is_home:
                continue
            if cell.owner == me and (cell.is_upgraded or cell.base_points < 2):
                continue
            d = abs(r - pos[0]) + abs(c - pos[1])
            # neutral cells before upgrade trips, close before far
            key = (cell.owner != 0, d, r, c)
            if best is None or key < best:
                best = key
    if best is None:
        return "STAY"
    _, _, r, c = best
    if c != pos[1]:
        move, nr, nc = ("EAST", pos[0], pos[1] + 1) if c > pos[1] else ("WEST", pos[0], pos[1] - 1)
    else:
        move, nr, nc = ("SOUTH", pos[0] + 1, pos[1]) if r > pos[0] else ("NORTH", pos[0] - 1, pos[1])
    if move in legal and not grid[nr][nc].occupant:
        return move
    return "STAY"
