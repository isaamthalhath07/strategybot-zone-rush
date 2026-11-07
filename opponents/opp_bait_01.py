"""Patient squatter: parks on a rival's upgraded cell for two of the three stays a take needs, steps off, farms, repeats."""

DIRS = (("NORTH", -1, 0), ("SOUTH", 1, 0), ("WEST", 0, -1), ("EAST", 0, 1))
_M = {"dwell": 0, "pos": None, "away": 0, "total": 0}


def _grid(board):
    if len(board) == 64:
        return [board[i:i + 8] for i in range(0, 64, 8)]
    return board


def _toward(pos, goal, grid, legal):
    dr, dc = goal[0] - pos[0], goal[1] - pos[1]
    tries = []
    if dr:
        tries.append((abs(dr), "SOUTH" if dr > 0 else "NORTH", pos[0] + (1 if dr > 0 else -1), pos[1]))
    if dc:
        tries.append((abs(dc), "EAST" if dc > 0 else "WEST", pos[0], pos[1] + (1 if dc > 0 else -1)))
    tries.sort(key=lambda t: -t[0])
    for _, name, r, c in tries:
        if name in legal and not grid[r][c].occupant:
            return name
    return "STAY"


def _step_off(pos, grid, legal, me):
    """A free neighbouring cell to step onto; prefers land that is neutral or ours."""
    best = None
    for name, dr, dc in DIRS:
        r, c = pos[0] + dr, pos[1] + dc
        if not (0 <= r < 8 and 0 <= c < 8) or name not in legal:
            continue
        if grid[r][c].occupant:
            continue
        rank = 0 if grid[r][c].owner in (0, me) else 1
        if best is None or rank < best[0]:
            best = (rank, name)
    return best[1] if best else "STAY"


def _farm(pos, grid, legal, me):
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
                key = (d + 3 - cell.base_points, r, c)       # upgrade trip
            else:
                continue
            if best is None or key < best:
                best = key
    if best is None:
        return "STAY"
    return _toward(pos, (best[1], best[2]), grid, legal)


def act(state):
    me = state.bot_id
    legal = state.legal_actions
    grid = _grid(state.board)

    pos = None
    total = 0
    for r in range(8):
        for c in range(8):
            if grid[r][c].occupant == me:
                pos = (r, c)
            if grid[r][c].owner:
                total += 1
    if pos is None:
        return "STAY"

    mem = _M
    if total < mem["total"]:                 # owned cells never shrink within a game -> new game
        mem.update(dwell=0, pos=None, away=0)
    mem["total"] = total
    if mem["pos"] != pos:
        mem["dwell"] = 0
    mem["pos"] = pos
    if mem["away"] > 0:
        mem["away"] -= 1

    here = grid[pos[0]][pos[1]]
    if here.is_frozen:
        mem["dwell"] = 0
        return "STAY"

    if mem["away"] == 0:
        if here.owner not in (0, me) and not here.is_home and here.is_upgraded:
            if mem["dwell"] >= 2:            # progress is 2 of 3: leave before the take completes
                mem["dwell"] = 0
                mem["away"] = 4
                return _step_off(pos, grid, legal, me)
            mem["dwell"] += 1
            return "STAY"
        victims = []
        for r in range(8):
            for c in range(8):
                cell = grid[r][c]
                if cell.owner not in (0, me) and not cell.is_home and cell.is_upgraded and not cell.occupant:
                    victims.append((abs(r - pos[0]) + abs(c - pos[1]), r, c))
        if victims:
            _, r, c = min(victims)
            return _toward(pos, (r, c), grid, legal)

    return _farm(pos, grid, legal, me)
