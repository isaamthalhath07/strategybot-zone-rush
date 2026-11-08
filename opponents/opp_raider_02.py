"""Late raider: farms and upgrades while the board fills up, then switches to hunting the biggest rival upgraded cells."""
from collections import deque

DIRS = (("NORTH", -1, 0), ("SOUTH", 1, 0), ("WEST", 0, -1), ("EAST", 0, 1))


def _grid(board):
    if len(board) == 64:
        return [list(board[i:i + 8]) for i in range(0, 64, 8)]
    return [list(r) for r in board]


def _bfs(start, blocked):
    dist = {start: 0}
    first = {}
    q = deque([start])
    while q:
        cur = q.popleft()
        for name, dr, dc in DIRS:
            n = (cur[0] + dr, cur[1] + dc)
            if not (0 <= n[0] < 8 and 0 <= n[1] < 8):
                continue
            if n in dist or n in blocked:
                continue
            dist[n] = dist[cur] + 1
            first[n] = first[cur] if cur in first else name
            q.append(n)
    return dist, first


def act(state):
    me = state.bot_id
    legal = state.legal_actions
    g = _grid(state.board)

    pos = None
    blocked = set()
    neutral_count = 0
    rival_count = 0
    for r in range(8):
        for c in range(8):
            cell = g[r][c]
            if cell.occupant == me:
                pos = (r, c)
            elif cell.occupant:
                blocked.add((r, c))
            if cell.owner == 0:
                neutral_count += 1
            elif cell.owner != me and not cell.is_home:
                rival_count += 1
    if pos is None:
        return "STAY"
    here = g[pos[0]][pos[1]]

    # "late" is judged from the board, not a clock: most land is claimed and rivals have plenty to lose
    late = neutral_count <= 20 or rival_count >= 14

    dist, first = _bfs(pos, blocked)

    if late:
        if not here.is_home and here.owner not in (0, me):
            return "STAY"
        ups, l1s = [], []
        for p, d in dist.items():
            if d == 0:
                continue
            cell = g[p[0]][p[1]]
            if cell.owner in (0, me) or cell.is_home:
                continue
            value = 8 * cell.base_points * (2 if cell.is_upgraded else 1)
            (ups if cell.is_upgraded else l1s).append((value - 4 * d, p))
        pool = ups or l1s
        if pool:
            move = first[max(pool)[1]]
            return move if move in legal else "STAY"
        # nothing to raid: fall through to farming

    neutral = [p for p in dist if p != pos and g[p[0]][p[1]].owner == 0]
    if here.owner == 0:
        return "STAY"
    if here.owner == me and not here.is_home and not here.is_upgraded:
        if here.base_points >= 2 or not neutral:
            return "STAY"

    if neutral:
        goal = max(neutral, key=lambda p: (g[p[0]][p[1]].base_points * 3 - dist[p], -p[0], -p[1]))
    else:
        ups = [p for p in dist
               if p != pos and g[p[0]][p[1]].owner == me
               and not g[p[0]][p[1]].is_home and not g[p[0]][p[1]].is_upgraded]
        if not ups:
            return "STAY"
        goal = min(ups, key=lambda p: (dist[p], p))
    move = first[goal]
    return move if move in legal else "STAY"
