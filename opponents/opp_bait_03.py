"""Leader squatter: picks the rival with the most land, sits two turns on its nearest upgraded cell, steps off, then goes home to farm."""
from collections import deque

DIRS = (("NORTH", -1, 0), ("SOUTH", 1, 0), ("WEST", 0, -1), ("EAST", 0, 1))
_M = {"dwell": 0, "pos": None, "rest": 0, "total": 0}


def _cells(board):
    flat = list(board) if len(board) == 64 else [x for row in board for x in row]
    return {(i // 8, i % 8): cell for i, cell in enumerate(flat)}


def _bfs(start, cells, blocked):
    dist = {start: 0}
    first = {}
    q = deque([start])
    while q:
        cur = q.popleft()
        for name, dr, dc in DIRS:
            n = (cur[0] + dr, cur[1] + dc)
            if n in cells and n not in dist and n not in blocked:
                dist[n] = dist[cur] + 1
                first[n] = first.get(cur, name)
                q.append(n)
    return dist, first


def act(state):
    me = state.bot_id
    legal = state.legal_actions
    cells = _cells(state.board)

    pos = home = None
    blocked = set()
    counts = {}
    total = 0
    for p, cell in cells.items():
        if cell.occupant == me:
            pos = p
        elif cell.occupant:
            blocked.add(p)
        if cell.is_home and cell.owner == me:
            home = p
        if cell.owner:
            total += 1
            if cell.owner != me:
                counts[cell.owner] = counts.get(cell.owner, 0) + 1
    if pos is None:
        return "STAY"
    if home is None:
        home = pos

    mem = _M
    if total < mem["total"]:
        mem.update(dwell=0, pos=None, rest=0)
    mem["total"] = total
    if mem["pos"] != pos:
        mem["dwell"] = 0
    mem["pos"] = pos
    if mem["rest"] > 0:
        mem["rest"] -= 1

    here = cells[pos]
    if here.is_frozen:
        mem["dwell"] = 0
        return "STAY"

    dist, first = _bfs(pos, cells, blocked)

    if mem["rest"] == 0:
        if here.owner not in (0, me) and not here.is_home and here.is_upgraded:
            if mem["dwell"] >= 2:
                mem["dwell"] = 0
                mem["rest"] = 6
                # step off onto a free neighbour, preferring the one nearest home
                exits = []
                for name, dr, dc in DIRS:
                    n = (pos[0] + dr, pos[1] + dc)
                    if name in legal and n in cells and not cells[n].occupant:
                        exits.append((abs(n[0] - home[0]) + abs(n[1] - home[1]), name))
                return min(exits)[1] if exits else "STAY"
            mem["dwell"] += 1
            return "STAY"

        leader = max(counts, key=lambda s: (counts[s], -s)) if counts else None
        prey = [p for p in dist
                if p != pos and cells[p].owner not in (0, me)
                and not cells[p].is_home and cells[p].is_upgraded]
        mine = [p for p in prey if cells[p].owner == leader]
        pool = mine or prey
        if pool:
            goal = min(pool, key=lambda p: (dist[p], p))
            move = first[goal]
            return move if move in legal else "STAY"

    # farming mode: neutral cells closest to home first, then upgrade our own level-1 cells
    neutral = [p for p in dist if p != pos and cells[p].owner == 0]
    if here.owner == 0:
        return "STAY"
    if here.owner == me and not here.is_home and not here.is_upgraded and not neutral:
        return "STAY"
    if neutral:
        goal = min(neutral, key=lambda p: (abs(p[0] - home[0]) + abs(p[1] - home[1]) + 0.5 * dist[p], p))
    else:
        ups = [p for p in dist
               if p != pos and cells[p].owner == me and not cells[p].is_home and not cells[p].is_upgraded]
        if not ups:
            return "STAY"
        goal = min(ups, key=lambda p: (dist[p], p))
    move = first[goal]
    return move if move in legal else "STAY"
