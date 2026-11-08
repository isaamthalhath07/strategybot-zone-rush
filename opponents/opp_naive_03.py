"""Naive value-chaser: always heads for the highest-point cell it doesn't own (ties: nearest), column first."""


def act(state):
    me = state.bot_id
    legal = state.legal_actions
    grid = state.board
    if len(grid) == 64:
        grid = [grid[i:i + 8] for i in range(0, 64, 8)]

    pr = pc = None
    for r in range(8):
        for c in range(8):
            if grid[r][c].occupant == me:
                pr, pc = r, c
    if pr is None:
        return "STAY"

    cur = grid[pr][pc]
    if cur.owner != me and not cur.is_home:
        return "STAY"

    best = None
    for r in range(8):
        for c in range(8):
            cell = grid[r][c]
            if cell.owner == me or cell.is_home or cell.occupant:
                continue
            key = (-cell.base_points, abs(r - pr) + abs(c - pc))
            if best is None or key < best[0]:
                best = (key, r, c)
    if best is None:
        return "STAY"

    _, tr, tc = best
    if tc < pc:
        move = "WEST"
    elif tc > pc:
        move = "EAST"
    elif tr < pr:
        move = "NORTH"
    else:
        move = "SOUTH"
    return move if move in legal else "STAY"
