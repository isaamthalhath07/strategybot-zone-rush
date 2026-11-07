"""Buggy (illegal action): a greedy neutral-grabber whose step helper sometimes tries a diagonal move, which is not a real action."""
import random


def act(state):
    board = state.board
    cells = list(board) if len(board) == 64 else [c for row in board for c in row]
    me = state.bot_id
    legal = state.legal_actions

    pos = None
    for i, cell in enumerate(cells):
        if cell.occupant == me:
            pos = i
            break
    if pos is None:
        return "STAY"
    r, c = divmod(pos, 8)

    here = cells[pos]
    if not here.is_home and here.owner != me:
        return "STAY"
    if not here.is_home and not here.is_upgraded and here.base_points >= 3:
        return "STAY"

    best = None
    for i, cell in enumerate(cells):
        if cell.owner != 0 or cell.occupant:
            continue
        d = abs(i // 8 - r) + abs(i % 8 - c)
        if best is None or d < best[0]:
            best = (d, i // 8, i % 8)
    if best is None:
        return "STAY"

    _, tr, tc = best
    vert = ("SOUTH" if tr > r else "NORTH") if tr != r else ""
    horiz = ("EAST" if tc > c else "WEST") if tc != c else ""
    if vert and horiz and random.random() < 0.12:
        # BUG: "optimised" the path by moving diagonally -> e.g. "SOUTHEAST", which is not in legal_actions
        return vert + horiz
    move = vert or horiz
    return move if move in legal else "STAY"
