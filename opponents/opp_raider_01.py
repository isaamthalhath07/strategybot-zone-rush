"""Early raider: skips slow farming and rushes the nearest rival territory, hitting the best payoff-per-turn rival cell."""
from collections import deque

DIRS = (("NORTH", -1, 0), ("SOUTH", 1, 0), ("WEST", 0, -1), ("EAST", 0, 1))


def _grid(board):
    if len(board) == 64:
        return [board[i * 8:(i + 1) * 8] for i in range(8)]
    return board


def _bfs(start, blocked):
    dist = {start: 0}
    first = {}
    q = deque([start])
    while q:
        r, c = q.popleft()
        for name, dr, dc in DIRS:
            n = (r + dr, c + dc)
            if 0 <= n[0] < 8 and 0 <= n[1] < 8 and n not in dist and n not in blocked:
                dist[n] = dist[(r, c)] + 1
                first[n] = first.get((r, c), name)
                q.append(n)
    return dist, first


def act(state):
    me = state.bot_id
    legal = state.legal_actions
    g = _grid(state.board)

    pos = None
    blocked = set()
    rival_homes = []
    for r in range(8):
        for c in range(8):
            cell = g[r][c]
            if cell.occupant == me:
                pos = (r, c)
            elif cell.occupant:
                blocked.add((r, c))
            if cell.is_home and cell.owner != me:
                rival_homes.append((r, c))
    if pos is None:
        return "STAY"
    here = g[pos[0]][pos[1]]

    hub = None
    if rival_homes:
        hub = min(rival_homes, key=lambda p: abs(p[0] - pos[0]) + abs(p[1] - pos[1]))

    # sitting on a rival cell: finish the take.  On neutral ground: only if it's good or close to the enemy.
    if not here.is_home and here.owner != me:
        if here.owner != 0:
            return "STAY"
        near_enemy = hub is not None and abs(hub[0] - pos[0]) + abs(hub[1] - pos[1]) <= 3
        if here.base_points >= 2 or near_enemy:
            return "STAY"

    dist, first = _bfs(pos, blocked)

    best = None
    for p, d in dist.items():
        if d == 0:
            continue
        cell = g[p[0]][p[1]]
        if cell.owner in (0, me) or cell.is_home:
            continue
        stays = 3 if cell.is_upgraded else 1
        value = 8 * cell.base_points * (2 if cell.is_upgraded else 1)
        score = value / (d + stays)
        if best is None or score > best[0]:
            best = (score, p)
    if best is not None:
        move = first[best[1]]
        return move if move in legal else "STAY"

    # no rival land to hit yet: drift toward the closest rival corner, claiming neutral cells near it
    cands = [p for p in dist if p != pos and g[p[0]][p[1]].owner == 0]
    if not cands or hub is None:
        return "STAY"
    goal = min(cands, key=lambda p: (abs(p[0] - hub[0]) + abs(p[1] - hub[1]) + 0.5 * dist[p], p))
    move = first[goal]
    return move if move in legal else "STAY"
