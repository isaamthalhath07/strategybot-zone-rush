"""Buggy (oscillator): walks to two adjacent central cells and then shuttles between them forever, never staying long enough to claim anything."""

PAIRS = (((3, 3), (3, 4)), ((4, 3), (4, 4)))


def _flat(board):
    if len(board) == 64:
        return list(board)
    return [cell for row in board for cell in row]


def act(state):
    me = state.bot_id
    legal = state.legal_actions
    cells = _flat(state.board)

    pos = home = None
    for i, cell in enumerate(cells):
        if cell.occupant == me:
            pos = (i // 8, i % 8)
        if cell.is_home and cell.owner == me:
            home = (i // 8, i % 8)
    if pos is None:
        return "STAY"
    if home is None:
        home = pos

    a, b = PAIRS[0] if home[0] < 4 else PAIRS[1]
    if pos == a:
        target = b
    elif pos == b:
        target = a
    else:
        target = min((a, b), key=lambda p: abs(p[0] - pos[0]) + abs(p[1] - pos[1]))
        # BUG: arriving at the first cell of the pair counts as "done", so the shuttle starts at once

    if pos[0] != target[0]:
        move, nr, nc = ("SOUTH", pos[0] + 1, pos[1]) if target[0] > pos[0] else ("NORTH", pos[0] - 1, pos[1])
    else:
        move, nr, nc = ("EAST", pos[0], pos[1] + 1) if target[1] > pos[1] else ("WEST", pos[0], pos[1] - 1)
    if move in legal and not cells[nr * 8 + nc].occupant:
        return move
    return "STAY"
