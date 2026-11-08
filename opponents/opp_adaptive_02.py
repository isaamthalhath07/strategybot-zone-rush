"""Threat tracker: times how long each rival lingers on its land, shields just before a take lands, and raids the worst offender."""

_M = {}


def _grid(board):
    if len(board) == 64:
        return [board[i:i + 8] for i in range(0, 64, 8)]
    return board


def _step(pos, goal, grid, legal):
    dr, dc = goal[0] - pos[0], goal[1] - pos[1]
    moves = []
    if dr:
        moves.append((abs(dr), "SOUTH" if dr > 0 else "NORTH", pos[0] + (1 if dr > 0 else -1), pos[1]))
    if dc:
        moves.append((abs(dc), "EAST" if dc > 0 else "WEST", pos[0], pos[1] + (1 if dc > 0 else -1)))
    moves.sort(key=lambda m: -m[0])
    for _, name, r, c in moves:
        if name in legal and not grid[r][c].occupant:
            return name
    return "STAY"


def act(state):
    me = state.bot_id
    legal = state.legal_actions
    grid = _grid(state.board)

    pos = None
    seats = {}
    owners = {}
    total = 0
    for r in range(8):
        for c in range(8):
            cell = grid[r][c]
            owners[(r, c)] = cell.owner
            if cell.owner:
                total += 1
            if cell.occupant == me:
                pos = (r, c)
            elif cell.occupant:
                seats[cell.occupant] = (r, c)
    if pos is None:
        return "STAY"

    mem = _M
    if total < mem.get("total", 0):
        mem.clear()
    mem["total"] = total
    streak = mem.setdefault("streak", {})
    last = mem.setdefault("last", {})
    aggro = mem.setdefault("aggro", {})
    mem["cool"] = max(0, mem.get("cool", 0) - 1)

    for s in list(aggro):
        aggro[s] *= 0.97
    prev = mem.get("owners")
    if prev:
        for p, was in prev.items():
            now = owners[p]
            if was == me and now not in (0, me):
                aggro[now] = aggro.get(now, 0) + 4        # they took a cell
            elif now == me and was not in (0, me):
                aggro[was] = max(0.0, aggro.get(was, 0) - 3)   # we took one back
    mem["owners"] = owners

    threats = []
    for s, p in seats.items():
        cell = grid[p[0]][p[1]]
        if cell.owner == me and not cell.is_home:
            streak[s] = streak.get(s, 0) + 1 if last.get(s) == p else 1
            aggro[s] = aggro.get(s, 0) + 1
            if not cell.is_frozen:
                threats.append((s, cell, streak[s]))
        else:
            streak[s] = 0
        last[s] = p

    # shield on the last turn that still stops the take: 1st sighting for level 1, 3rd for level 2
    if mem["cool"] == 0 and "SHIELD" in legal:
        for s, cell, n in threats:
            if n >= (3 if cell.is_upgraded else 1):
                mem["cool"] = 5
                return "SHIELD"

    villain = max(aggro, key=aggro.get) if aggro else None
    if villain is not None and aggro[villain] < 3:
        villain = None

    here = grid[pos[0]][pos[1]]
    if villain is not None:
        if here.owner == villain and not here.is_home:
            return "STAY"
        best = None
        for r in range(8):
            for c in range(8):
                cell = grid[r][c]
                if cell.owner != villain or cell.is_home or cell.occupant:
                    continue
                d = abs(r - pos[0]) + abs(c - pos[1])
                stays = 3 if cell.is_upgraded else 1
                score = 8 * cell.base_points * (2 if cell.is_upgraded else 1) / (d + stays)
                if best is None or score > best[0]:
                    best = (score, r, c)
        if best is not None:
            return _step(pos, (best[1], best[2]), grid, legal)

    # peace: nearest neutral cell first, then upgrade
    neutral = []
    for r in range(8):
        for c in range(8):
            cell = grid[r][c]
            if cell.owner == 0 and not cell.occupant:
                neutral.append((abs(r - pos[0]) + abs(c - pos[1]), r, c))
    if here.owner == 0:
        return "STAY"
    if here.owner == me and not here.is_home and not here.is_upgraded and not neutral:
        return "STAY"
    if neutral:
        _, r, c = min(neutral)
        return _step(pos, (r, c), grid, legal)
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
