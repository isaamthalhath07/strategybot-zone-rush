"""Naive greedy: walks to the nearest cell it doesn't own and STAYs there until it flips; never shields or upgrades."""


def act(state):
    board = state.board
    cells = list(board) if len(board) == 64 else [c for row in board for c in row]
    me = state.bot_id
    legal = state.legal_actions

    pos = None
    for i in range(64):
        if cells[i].occupant == me:
            pos = i
            break
    if pos is None:
        return "STAY"
    r, c = divmod(pos, 8)

    # standing on something that isn't ours (and can be taken): just sit on it
    here = cells[pos]
    if here.owner != me and not here.is_home:
        return "STAY"

    best = None
    best_d = 1000
    for i in range(64):
        cell = cells[i]
        if cell.owner == me or cell.is_home or cell.occupant != 0:
            continue
        tr, tc = divmod(i, 8)
        d = abs(tr - r) + abs(tc - c)
        if d < best_d:
            best_d = d
            best = (tr, tc)
    if best is None:
        return "STAY"

    tr, tc = best
    if tr < r:
        move = "NORTH"
    elif tr > r:
        move = "SOUTH"
    elif tc < c:
        move = "WEST"
    else:
        move = "EAST"
    return move if move in legal else "STAY"
