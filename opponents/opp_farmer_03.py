"""Centre-first farmer: claims the middle ring by ring, upgrading every 2+ point cell the moment it owns it."""
from collections import deque

STEPS = {"NORTH": (-1, 0), "SOUTH": (1, 0), "WEST": (0, -1), "EAST": (0, 1)}


def _cells(board):
    out = {}
    if len(board) == 64:
        for i, cell in enumerate(board):
            out[(i // 8, i % 8)] = cell
    else:
        for r, row in enumerate(board):
            for c, cell in enumerate(row):
                out[(r, c)] = cell
    return out


def _ring(p):
    # 1 for the four middle cells, 3, 5, 7 towards the border
    return max(abs(2 * p[0] - 7), abs(2 * p[1] - 7))


def _search(start, cells, blocked):
    dist = {start: 0}
    first = {}
    todo = deque([start])
    while todo:
        cur = todo.popleft()
        for name, (dr, dc) in STEPS.items():
            nxt = (cur[0] + dr, cur[1] + dc)
            if nxt not in cells or nxt in dist or nxt in blocked:
                continue
            dist[nxt] = dist[cur] + 1
            first[nxt] = first.get(cur, name)
            todo.append(nxt)
    return dist, first


def act(state):
    me = state.bot_id
    legal = state.legal_actions
    cells = _cells(state.board)

    pos = None
    blocked = set()
    for p, cell in cells.items():
        if cell.occupant == me:
            pos = p
        elif cell.occupant:
            blocked.add(p)
    if pos is None:
        return "STAY"
    here = cells[pos]
    if here.owner == 0:
        return "STAY"

    dist, first = _search(pos, cells, blocked)
    neutral = [p for p in dist if p != pos and cells[p].owner == 0]

    # upgrade-heavy: finish upgrading right where we stand (cheap cells only once nothing is left to claim)
    if here.owner == me and not here.is_home and not here.is_upgraded:
        if here.base_points >= 2 or not neutral:
            return "STAY"

    if neutral:
        goal = min(neutral, key=lambda p: (_ring(p), dist[p], p))
    else:
        ups = [p for p in dist
               if p != pos and cells[p].owner == me
               and not cells[p].is_home and not cells[p].is_upgraded]
        if not ups:
            return "STAY"
        goal = min(ups, key=lambda p: (-cells[p].base_points, dist[p], p))
    move = first[goal]
    return move if move in legal else "STAY"
