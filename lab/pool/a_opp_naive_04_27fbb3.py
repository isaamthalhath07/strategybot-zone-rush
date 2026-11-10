"""Naive sweeper: claims cells in plain reading order (row 0 left to right, then row 1, ...) and nothing else."""


def act(state):
    me = state.bot_id
    legal = state.legal_actions
    board = state.board
    if len(board) == 64:
        board = [board[i * 8:(i + 1) * 8] for i in range(8)]

    pr = pc = -1
    for r in range(8):
        for c in range(8):
            if board[r][c].occupant == me:
                pr, pc = r, c
    if pr < 0:
        return "STAY"

    here = board[pr][pc]
    if here.owner != me and not here.is_home:
        return "STAY"

    target = None
    for r in range(8):
        for c in range(8):
            cell = board[r][c]
            if cell.owner != me and not cell.is_home and cell.occupant == 0:
                target = (r, c)
                break
        if target:
            break
    if target is None:
        return "STAY"

    tr, tc = target
    if tc != pc:
        move = "EAST" if tc > pc else "WEST"
    else:
        move = "SOUTH" if tr > pr else "NORTH"
    return move if move in legal else "STAY"
