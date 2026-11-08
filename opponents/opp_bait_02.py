"""Twitchy squatter: hops between rival cells, sitting 1-2 turns on upgraded ones (none on level-1) and leaving before any take lands."""
import random
from collections import deque

DIRS = (("NORTH", -1, 0), ("SOUTH", 1, 0), ("WEST", 0, -1), ("EAST", 0, 1))
_M = {"dwell": 0, "lim": 0, "pos": None, "total": 0}


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
            if 0 <= n[0] < 8 and 0 <= n[1] < 8 and n not in dist and n not in blocked:
                dist[n] = dist[cur] + 1
                first[n] = first.get(cur, name)
                q.append(n)
    return dist, first


def act(state):
    me = state.bot_id
    legal = state.legal_actions
    g = _grid(state.board)

    pos = None
    blocked = set()
    total = 0
    for r in range(8):
        for c in range(8):
            cell = g[r][c]
            if cell.occupant == me:
                pos = (r, c)
            elif cell.occupant:
                blocked.add((r, c))
            if cell.owner:
                total += 1
    if pos is None:
        return "STAY"

    mem = _M
    if total < mem["total"]:
        mem.update(dwell=0, lim=0, pos=None)
    mem["total"] = total
    here = g[pos[0]][pos[1]]
    if mem["pos"] != pos:                    # just arrived: arrival is not a stay
        mem["dwell"] = 0
        mem["lim"] = random.choice((1, 2)) if here.is_upgraded else 0
    mem["pos"] = pos
    if here.is_frozen:
        mem["dwell"] = 0
        return "STAY"

    dist, first = _bfs(pos, blocked)
    victims = [p for p in dist
               if p != pos and g[p[0]][p[1]].owner not in (0, me) and not g[p[0]][p[1]].is_home]
    on_victim = here.owner not in (0, me) and not here.is_home

    if on_victim:
        if mem["dwell"] >= mem["lim"]:
            mem["dwell"] = 0
            if victims:                      # hop to the nearest other rival cell
                goal = min(victims, key=lambda p: (dist[p], p))
                move = first[goal]
                return move if move in legal else "STAY"
            for name, dr, dc in DIRS:        # nowhere to hop: just get off
                r, c = pos[0] + dr, pos[1] + dc
                if name in legal and 0 <= r < 8 and 0 <= c < 8 and not g[r][c].occupant:
                    return name
            return "STAY"
        mem["dwell"] += 1
        return "STAY"

    if victims:
        goal = min(victims, key=lambda p: (dist[p], p))
        move = first[goal]
        return move if move in legal else "STAY"

    # no rival land to harass: grab the nearest neutral cell
    if here.owner == 0:
        return "STAY"
    neutral = [p for p in dist if p != pos and g[p[0]][p[1]].owner == 0]
    if not neutral:
        return "STAY"
    goal = min(neutral, key=lambda p: (dist[p], p))
    move = first[goal]
    return move if move in legal else "STAY"
