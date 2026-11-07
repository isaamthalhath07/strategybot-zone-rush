"""Ledger enforcer: keeps a points ledger of what each rival has taken from it and answers with proportional raids, never shielding."""
from collections import deque

STEPS = (("NORTH", -1, 0), ("SOUTH", 1, 0), ("WEST", 0, -1), ("EAST", 0, 1))
_LEDGER = {}


def _cells(board):
    flat = list(board) if len(board) == 64 else [x for row in board for x in row]
    return {(i // 8, i % 8): cell for i, cell in enumerate(flat)}


def _paths(start, cells, blocked):
    dist = {start: 0}
    first = {}
    q = deque([start])
    while q:
        cur = q.popleft()
        for name, dr, dc in STEPS:
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
    for p, cell in cells.items():
        if cell.occupant == me:
            pos = p
        elif cell.occupant:
            blocked.add(p)
        if cell.is_home and cell.owner == me:
            home = p
    if pos is None:
        return "STAY"
    if home is None:
        home = pos

    snap = {p: (cell.owner, bool(cell.is_upgraded)) for p, cell in cells.items()}
    total = sum(1 for o, _ in snap.values() if o)
    if total < _LEDGER.get("total", 0):
        _LEDGER.clear()
    _LEDGER["total"] = total
    debt = _LEDGER.setdefault("debt", {})

    for s in list(debt):
        debt[s] *= 0.98                       # old grudges fade
    prev = _LEDGER.get("snap")
    if prev:
        for p, (was, was_up) in prev.items():
            now = snap[p][0]
            if was == now:
                continue
            worth = 8 * cells[p].base_points * (2 if was_up else 1)
            if was == me and now not in (0, me):
                debt[now] = debt.get(now, 0) + worth
            elif now == me and was not in (0, me):
                debt[was] = debt.get(was, 0) - worth
    _LEDGER["snap"] = snap

    villain = max(debt, key=debt.get) if debt else None
    if villain is not None and debt[villain] < 8:
        villain = None

    here = cells[pos]
    if villain is not None and here.owner == villain and not here.is_home:
        return "STAY"

    dist, first = _paths(pos, cells, blocked)

    if villain is not None:
        owed = debt[villain]
        best = None
        for p, d in dist.items():
            cell = cells[p]
            if d == 0 or cell.owner != villain or cell.is_home:
                continue
            stays = 3 if cell.is_upgraded else 1
            worth = 8 * cell.base_points * (2 if cell.is_upgraded else 1)
            score = min(worth, owed * 1.5) / (d + stays)      # proportional: don't chase far more than we're owed
            if best is None or score > best[0]:
                best = (score, p)
        if best is not None:
            move = first[best[1]]
            return move if move in legal else "STAY"

    # peace: expand outwards from home, upgrade the 2+ point cells when idle
    neutral = [p for p in dist if p != pos and cells[p].owner == 0]
    if here.owner == 0:
        return "STAY"
    if here.owner == me and not here.is_home and not here.is_upgraded:
        if here.base_points >= 2 or not neutral:
            return "STAY"
    if neutral:
        goal = min(neutral, key=lambda p: (abs(p[0] - home[0]) + abs(p[1] - home[1]) + 0.3 * dist[p], p))
    else:
        cand = [p for p in dist
                if p != pos and cells[p].owner == me and not cells[p].is_home and not cells[p].is_upgraded]
        if not cand:
            return "STAY"
        goal = min(cand, key=lambda p: (dist[p], p))
    move = first[goal]
    return move if move in legal else "STAY"
