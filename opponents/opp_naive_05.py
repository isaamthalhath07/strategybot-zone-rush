"""Naive centre camper: marches straight to the middle of the board, then just STAYs there for the rest of the game."""

CENTRE = ((3, 3), (3, 4), (4, 3), (4, 4))


def act(state):
    me = state.bot_id
    legal = state.legal_actions
    board = state.board
    if isinstance(board[0], (list, tuple)):
        flat = [cell for row in board for cell in row]
    else:
        flat = list(board)

    where = None
    for idx, cell in enumerate(flat):
        if cell.occupant == me:
            where = (idx // 8, idx % 8)
    if where is None or where in CENTRE:
        return "STAY"

    r, c = where
    tr, tc = min(CENTRE, key=lambda p: abs(p[0] - r) + abs(p[1] - c))
    if r != tr:
        move = "SOUTH" if tr > r else "NORTH"
    else:
        move = "EAST" if tc > c else "WEST"
    return move if move in legal else "STAY"
