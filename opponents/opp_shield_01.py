"""Shield spammer: raises SHIELD the instant it is allowed, whether or not anyone is on its land, and farms in between."""

_M = {"cool": 0, "total": 0}


def _grid(board):
    if len(board) == 64:
        return [board[i:i + 8] for i in range(0, 64, 8)]
    return board


def act(state):
    me = state.bot_id
    legal = state.legal_actions
    grid = _grid(state.board)

    pos = None
    total = 0
    for r in range(8):
        for c in range(8):
            if grid[r][c].occupant == me:
                pos = (r, c)
            if grid[r][c].owner:
                total += 1

    # owned-cell count never drops inside one game, so a drop means a fresh game
    if total < _M["total"]:
        _M["cool"] = 0
    _M["total"] = total

    if _M["cool"] > 0:
        _M["cool"] -= 1
    if _M["cool"] == 0 and "SHIELD" in legal:
        _M["cool"] = 5          # this turn + the 4 turn cooldown
        return "SHIELD"

    if pos is None:
        return "STAY"
    here = grid[pos[0]][pos[1]]
    if here.owner != me and not here.is_home:
        return "STAY"

    best = None
    for r in range(8):
        for c in range(8):
            cell = grid[r][c]
            if cell.owner == 0 and not cell.occupant:
                d = abs(r - pos[0]) + abs(c - pos[1])
                if best is None or d < best[0]:
                    best = (d, r, c)
    if best is None:
        return "STAY"
    _, r, c = best
    if r != pos[0]:
        move = "SOUTH" if r > pos[0] else "NORTH"
    else:
        move = "EAST" if c > pos[1] else "WEST"
    return move if move in legal else "STAY"
