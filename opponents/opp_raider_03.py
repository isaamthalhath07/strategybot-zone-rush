"""Opportunistic raider: farms by default but pounces on a rival cell when the payoff per turn is high, especially if its owner is frozen."""


def _grid(board):
    if len(board) == 64:
        return [board[i:i + 8] for i in range(0, 64, 8)]
    return board


def _step(pos, goal, grid, legal):
    dr, dc = goal[0] - pos[0], goal[1] - pos[1]
    cands = []
    if dr:
        cands.append((abs(dr), "SOUTH" if dr > 0 else "NORTH", pos[0] + (1 if dr > 0 else -1), pos[1]))
    if dc:
        cands.append((abs(dc), "EAST" if dc > 0 else "WEST", pos[0], pos[1] + (1 if dc > 0 else -1)))
    for _, name, r, c in sorted(cands, reverse=True):
        if name in legal and not grid[r][c].occupant:
            return name
    return "STAY"


def act(state):
    me = state.bot_id
    legal = state.legal_actions
    grid = _grid(state.board)

    pos = None
    frozen = set()
    for r in range(8):
        for c in range(8):
            cell = grid[r][c]
            if cell.occupant == me:
                pos = (r, c)
            if cell.occupant and cell.is_frozen:
                frozen.add(cell.occupant)
    if pos is None:
        return "STAY"
    here = grid[pos[0]][pos[1]]

    # already on someone else's land: finish the take
    if here.owner == 0 or (here.owner != me and not here.is_home):
        return "STAY"

    neutral = []
    raids = []
    for r in range(8):
        for c in range(8):
            cell = grid[r][c]
            if cell.occupant:
                continue
            d = abs(r - pos[0]) + abs(c - pos[1])
            if cell.owner == 0:
                neutral.append((d - 2 * cell.base_points, r, c))
            elif cell.owner != me and not cell.is_home:
                stays = 3 if cell.is_upgraded else 1
                value = 8 * cell.base_points * (2 if cell.is_upgraded else 1)
                need = 2.5 if cell.owner in frozen else 4.0
                score = value / (d + stays)
                if score >= need:
                    raids.append((score, -d, r, c))

    if raids:
        _, _, r, c = max(raids)
        return _step(pos, (r, c), grid, legal)

    if here.owner == me and not here.is_home and not here.is_upgraded:
        if here.base_points >= 3 or not neutral:
            return "STAY"
    if neutral:
        _, r, c = min(neutral)
        return _step(pos, (r, c), grid, legal)

    # idle: walk to the nearest own level-1 cell to upgrade it
    ups = []
    for r in range(8):
        for c in range(8):
            cell = grid[r][c]
            if cell.owner == me and not cell.is_home and not cell.is_upgraded and not cell.occupant:
                ups.append((abs(r - pos[0]) + abs(c - pos[1]), r, c))
    if not ups:
        return "STAY"
    _, r, c = min(ups)
    return _step(pos, (r, c), grid, legal)
