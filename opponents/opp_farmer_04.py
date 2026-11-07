"""Efficiency farmer: scores every claim or upgrade as points-per-turn gained over turns spent and always takes the best ratio."""


def _grid(board):
    return [board[i:i + 8] for i in range(0, 64, 8)] if len(board) == 64 else board


def _pull(pos, goal, grid, legal):
    """Greedy step toward goal; tries the longer axis first and falls back to the other if closed."""
    pr, pc = pos
    gr, gc = goal
    options = []
    if gr != pr:
        options.append((abs(gr - pr), "SOUTH" if gr > pr else "NORTH", pr + (1 if gr > pr else -1), pc))
    if gc != pc:
        options.append((abs(gc - pc), "EAST" if gc > pc else "WEST", pr, pc + (1 if gc > pc else -1)))
    options.sort(key=lambda o: -o[0])
    for _, name, r, c in options:
        if name in legal and not grid[r][c].occupant:
            return name
    return "STAY"


def act(state):
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

    best = None
    for r in range(8):
        for c in range(8):
            cell = grid[r][c]
            d = abs(r - pos[0]) + abs(c - pos[1])
            if d and cell.occupant:
                continue
            if cell.owner == 0:
                gain, cost = cell.base_points, d + 1          # walk there, one STAY
            elif cell.owner == me and not cell.is_home and not cell.is_upgraded:
                gain, cost = cell.base_points, d + 3          # walk there, three STAYs
            else:
                continue
            key = (-gain / cost, d, r, c)
            if best is None or key < best:
                best = key
    if best is None:
        return "STAY"
    _, d, r, c = best
    if d == 0:
        return "STAY"
    return _pull(pos, (r, c), grid, legal)
