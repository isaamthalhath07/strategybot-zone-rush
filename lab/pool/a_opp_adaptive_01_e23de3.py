"""Grudge keeper: farms in peace, counts every cell a rival takes from it, shields known offenders and raids the worst one back."""
from collections import deque

DIRS = (("NORTH", -1, 0), ("SOUTH", 1, 0), ("WEST", 0, -1), ("EAST", 0, 1))
_M = {}


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
            if not (0 <= n[0] < 8 and 0 <= n[1] < 8) or n in dist or n in blocked:
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
    owners, ups = [], []
    for r in range(8):
        for c in range(8):
            cell = g[r][c]
            owners.append(cell.owner)
            ups.append(bool(cell.is_upgraded))
            if cell.occupant == me:
                pos = (r, c)
            elif cell.occupant:
                blocked.add((r, c))
    if pos is None:
        return "STAY"

    mem = _M
    total = sum(1 for o in owners if o)
    if total < mem.get("total", 0):          # owned cells never shrink inside a game -> new game
        mem.clear()
    mem["total"] = total
    grudge = mem.setdefault("grudge", {})
    mem["cool"] = max(0, mem.get("cool", 0) - 1)

    prev_o, prev_u = mem.get("owners"), mem.get("ups")
    if prev_o:
        for i in range(64):
            was, now = prev_o[i], owners[i]
            if was == now:
                continue
            weight = 2 if prev_u[i] else 1
            if was == me and now not in (0, me):
                grudge[now] = grudge.get(now, 0) + weight          # they took our cell
            elif now == me and was not in (0, me):
                grudge[was] = max(0, grudge.get(was, 0) - weight)  # we took one back
    mem["owners"], mem["ups"] = owners, ups

    # shield when a known offender (or anyone, if the cell is upgraded) is parked on our land
    if mem["cool"] == 0 and "SHIELD" in legal:
        for r in range(8):
            for c in range(8):
                cell = g[r][c]
                if (cell.owner == me and not cell.is_home and cell.occupant not in (0, me)
                        and not cell.is_frozen
                        and (grudge.get(cell.occupant, 0) > 0 or cell.is_upgraded)):
                    mem["cool"] = 5
                    return "SHIELD"

    villain = max(grudge, key=grudge.get) if grudge else None
    if villain is not None and grudge[villain] <= 0:
        villain = None

    here = g[pos[0]][pos[1]]
    if villain is not None and here.owner == villain and not here.is_home:
        return "STAY"                       # finish the revenge take

    dist, first = _bfs(pos, blocked)

    if villain is not None:
        best = None
        for p, d in dist.items():
            cell = g[p[0]][p[1]]
            if d == 0 or cell.owner != villain or cell.is_home:
                continue
            stays = 3 if cell.is_upgraded else 1
            value = 8 * cell.base_points * (2 if cell.is_upgraded else 1)
            score = value / (d + stays)
            if best is None or score > best[0]:
                best = (score, p)
        if best is not None:
            move = first[best[1]]
            return move if move in legal else "STAY"

    # peace time: highest-value neutral cells, then upgrade
    neutral = [p for p in dist if p != pos and g[p[0]][p[1]].owner == 0]
    if here.owner == 0:
        return "STAY"
    if here.owner == me and not here.is_home and not here.is_upgraded:
        if here.base_points >= 2 or not neutral:
            return "STAY"
    if neutral:
        goal = max(neutral, key=lambda p: (g[p[0]][p[1]].base_points * 4 - dist[p], -p[0], -p[1]))
    else:
        cand = [p for p in dist
                if p != pos and g[p[0]][p[1]].owner == me
                and not g[p[0]][p[1]].is_home and not g[p[0]][p[1]].is_upgraded]
        if not cand:
            return "STAY"
        goal = min(cand, key=lambda p: (dist[p], p))
    move = first[goal]
    return move if move in legal else "STAY"
