"""Buggy (slow): a decent nearest-neutral farmer that on roughly one turn in eight stalls for ~150 ms (legal, but close to the 200 ms limit)."""
import random
import time


def _grid(board):
    if len(board) == 64:
        return [board[i:i + 8] for i in range(0, 64, 8)]
    return board


def act(state):
    # "expensive evaluation" that is not actually needed
    if random.random() < 0.12:
        time.sleep(random.uniform(0.14, 0.16))

    me = state.bot_id
    legal = state.legal_actions
    grid = _grid(state.board)

    pos = None
    for r in range(8):
        for c in range(8):
            if grid[r][c].occupant == me:
                pos = (r, c)
    if pos is None:
        return "STAY"

    here = grid[pos[0]][pos[1]]
    if here.owner == 0:
        return "STAY"
    if here.owner == me and not here.is_home and not here.is_upgraded and here.base_points >= 2:
        return "STAY"

    best = None
    for r in range(8):
        for c in range(8):
            cell = grid[r][c]
            if cell.occupant:
                continue
            d = abs(r - pos[0]) + abs(c - pos[1])
            if cell.owner == 0:
                key = (d - cell.base_points, r, c)
            elif cell.owner == me and not cell.is_home and not cell.is_upgraded and cell.base_points >= 2:
                key = (d + 3 - cell.base_points, r, c)
            else:
                continue
            if best is None or key < best:
                best = key
    if best is None:
        return "STAY"

    _, tr, tc = best
    if tr != pos[0]:
        move, nr, nc = ("SOUTH", pos[0] + 1, pos[1]) if tr > pos[0] else ("NORTH", pos[0] - 1, pos[1])
        if move in legal and not grid[nr][nc].occupant:
            return move
    if tc != pos[1]:
        move, nr, nc = ("EAST", pos[0], pos[1] + 1) if tc > pos[1] else ("WEST", pos[0], pos[1] - 1)
        if move in legal and not grid[nr][nc].occupant:
            return move
    return "STAY"
