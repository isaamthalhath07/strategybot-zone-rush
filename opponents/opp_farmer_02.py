"""Spine farmer: claims the two central columns first, then fans outwards; upgrades only prime spine cells until the board is full."""


def _grid(board):
    if len(board) == 64:
        return [board[i:i + 8] for i in range(0, 64, 8)]
    return board


def _pull(pos, goal, grid, legal):
    """One greedy step toward goal, longest axis first, never into a closed cell."""
    dr = goal[0] - pos[0]
    dc = goal[1] - pos[1]
    tries = []
    if dr:
        step = 1 if dr > 0 else -1
        tries.append(("SOUTH" if dr > 0 else "NORTH", abs(dr), (pos[0] + step, pos[1])))
    if dc:
        step = 1 if dc > 0 else -1
        tries.append(("EAST" if dc > 0 else "WEST", abs(dc), (pos[0], pos[1] + step)))
    tries.sort(key=lambda t: -t[1])
    for name, _, (r, c) in tries:
        if name in legal and not grid[r][c].occupant:
            return name
    return "STAY"


def act(state):
    me = state.bot_id
    legal = state.legal_actions
    grid = _grid(state.board)

    pos = None
    mine = 0
    for r in range(8):
        for c in range(8):
            if grid[r][c].occupant == me:
                pos = (r, c)
            if grid[r][c].owner == me:
                mine += 1
    if pos is None:
        return "STAY"
    here = grid[pos[0]][pos[1]]
    if here.owner == 0:
        return "STAY"

    neutral = []
    for r in range(8):
        for c in range(8):
            cell = grid[r][c]
            if cell.owner == 0 and not cell.occupant:
                group = 0 if c in (3, 4) else (1 if c in (2, 5) else 2)
                neutral.append((group, abs(r - pos[0]) + abs(c - pos[1]), r, c))

    if here.owner == me and not here.is_home and not here.is_upgraded:
        prime = pos[1] in (3, 4) and here.base_points >= 2
        if (prime and mine >= 6) or not neutral:
            return "STAY"

    if neutral:
        _, _, r, c = min(neutral)
        return _pull(pos, (r, c), grid, legal)

    # nothing left to claim: walk to the nearest of our own level-1 cells to upgrade it
    ups = []
    for r in range(8):
        for c in range(8):
            cell = grid[r][c]
            if cell.owner == me and not cell.is_home and not cell.is_upgraded and not cell.occupant:
                ups.append((abs(r - pos[0]) + abs(c - pos[1]), r, c))
    if not ups:
        return "STAY"
    _, r, c = min(ups)
    return _pull(pos, (r, c), grid, legal)
