"""Centre rusher: aggressively claims the valuable three-point cells near the centre."""

from collections import deque

SIZE = 8

def act(state):
    raw = state.board
    board = [c for row in raw for c in row] if raw and isinstance(raw[0], (list, tuple)) else raw
    me = state.bot_id
    legal = state.legal_actions

    current = next((i for i, c in enumerate(board) if c.occupant == me), None)

    if current is None:
        return "STAY"

    if board[current].is_frozen:
        return "STAY"

    if board[current].owner != me and not board[current].is_home and "STAY" in legal:  # FIX: arriving does not take a cell (rulebook: STAY on it); the target search below skips the cell it stands on, so it walked off every target
        return "STAY"

    def adj(p):
        r, c = divmod(p, SIZE)
        if r: yield "NORTH", p - SIZE
        if c < 7: yield "EAST", p + 1
        if r < 7: yield "SOUTH", p + SIZE
        if c: yield "WEST", p - 1

    # Dijkstra-like search through empty cells.
    dist = {current: 0}
    first_step = {}
    queue = deque([current])

    while queue:
        p = queue.popleft()

        for action, n in adj(p):
            if board[n].occupant != 0:
                continue

            new_dist = dist[p] + 1
            if n not in dist or new_dist < dist[n]:
                dist[n] = new_dist
                first_step[n] = action if p == current else first_step[p]
                queue.append(n)

    candidates = []

    for p, d in dist.items():
        if p == current:
            continue

        cell = board[p]

        if cell.is_home or cell.owner == me:
            continue

        # Strong preference for the three-point centre.
        value = cell.base_points
        score = value * value * 3.0

        if value == 3:
            score += 30
        elif value == 2:
            score += 7

        if cell.owner:
            score += 4 if not cell.is_upgraded else 1

        # Capture distance matters, but valuable targets justify detours.
        score /= (d + 1.0) ** 0.85

        # Prefer cells closer to the exact centre.
        r, c = divmod(p, SIZE)
        centre_distance = abs(r - 3.5) + abs(c - 3.5)
        score += (7 - centre_distance) * 0.35

        candidates.append((score, p))

    if candidates:
        candidates.sort(reverse=True)
        target = candidates[0][1]
        direction = first_step.get(target)

        if direction in legal:
            return direction

    # Upgrade the best available current cell if expansion is unattractive.
    if board[current].owner == me and not board[current].is_upgraded:
        if board[current].base_points == 3 and "STAY" in legal:
            return "STAY"

    return "STAY" if "STAY" in legal else legal[0]