"""Quadrant farmer: fills its own 4x4 quadrant best-cells-first, upgrades it all, then spills into the rest of the board."""
from collections import deque

DIRS = (("NORTH", -1, 0), ("SOUTH", 1, 0), ("WEST", 0, -1), ("EAST", 0, 1))


def _grid(board):
    if len(board) == 64:
        return [list(board[i * 8:(i + 1) * 8]) for i in range(8)]
    return [list(row) for row in board]


def _bfs(start, blocked):
    """Shortest-path distance and first move to every reachable cell."""
    dist = {start: 0}
    first = {}
    queue = deque([start])
    while queue:
        cur = queue.popleft()
        for name, dr, dc in DIRS:
            nxt = (cur[0] + dr, cur[1] + dc)
            if not (0 <= nxt[0] < 8 and 0 <= nxt[1] < 8):
                continue
            if nxt in dist or nxt in blocked:
                continue
            dist[nxt] = dist[cur] + 1
            first[nxt] = first[cur] if cur in first else name
            queue.append(nxt)
    return dist, first


def act(state):
    me = state.bot_id
    legal = state.legal_actions
    g = _grid(state.board)

    pos = home = None
    blocked = set()
    for r in range(8):
        for c in range(8):
            cell = g[r][c]
            if cell.occupant == me:
                pos = (r, c)
            elif cell.occupant:
                blocked.add((r, c))
            if cell.is_home and cell.owner == me:
                home = (r, c)
    if pos is None:
        return "STAY"
    if home is None:
        home = pos
    qr, qc = home[0] // 4, home[1] // 4

    def in_quad(p):
        return p[0] // 4 == qr and p[1] // 4 == qc

    here = g[pos[0]][pos[1]]
    if here.owner == 0:
        return "STAY"

    dist, first = _bfs(pos, blocked)
    q_neutral, q_upgrade, far_neutral = [], [], []
    for p in dist:
        if p == pos:
            continue
        cell = g[p[0]][p[1]]
        if cell.owner == 0:
            (q_neutral if in_quad(p) else far_neutral).append(p)
        elif cell.owner == me and in_quad(p) and not cell.is_home and not cell.is_upgraded:
            q_upgrade.append(p)

    # quadrant fully claimed -> upgrade here if this is one of our level-1 cells
    if (not q_neutral and in_quad(pos) and here.owner == me
            and not here.is_home and not here.is_upgraded):
        return "STAY"

    if q_neutral:
        goal = max(q_neutral, key=lambda p: (g[p[0]][p[1]].base_points * 10 - dist[p], -p[0], -p[1]))
    elif q_upgrade:
        goal = max(q_upgrade, key=lambda p: (g[p[0]][p[1]].base_points * 10 - dist[p], -p[0], -p[1]))
    elif far_neutral:
        goal = min(far_neutral, key=lambda p: (dist[p], p))
    else:
        return "STAY"
    move = first[goal]
    return move if move in legal else "STAY"
