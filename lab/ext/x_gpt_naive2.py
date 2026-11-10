"""Naive bot: balances expansion, territory value, and simple tactical decisions."""

def act(state):
    board = state.board
    cells = [c for row in board for c in row] if board and isinstance(board[0], (list, tuple)) else board
    me = state.bot_id
    legal = state.legal_actions

    pos = next((i for i, c in enumerate(cells) if c.occupant == me), None)

    if pos is None:
        return "STAY" if "STAY" in legal else legal[0]

    if cells[pos].is_frozen:
        return "STAY"

    def neighbors(p):
        r, c = divmod(p, 8)
        result = []
        if r > 0: result.append(("NORTH", p - 8))
        if c < 7: result.append(("EAST", p + 1))
        if r < 7: result.append(("SOUTH", p + 8))
        if c > 0: result.append(("WEST", p - 1))
        return result

    # Stay when taking an attractive cell.
    current = cells[pos]
    if current.owner != me and not current.is_home:
        return "STAY"

    # Upgrade valuable territory when expansion is not attractive.
    if current.owner == me and not current.is_upgraded:
        if current.base_points >= 3:
            return "STAY"

    # Find nearby valuable cells using a simple BFS.
    distances = {pos: 0}
    queue = [pos]

    for p in queue:
        for _, nxt in neighbors(p):
            if nxt not in distances and cells[nxt].occupant == 0:
                distances[nxt] = distances[p] + 1
                queue.append(nxt)

    best_target = None
    best_score = -1

    for p, dist in distances.items():
        c = cells[p]

        if dist == 0 or c.is_home or c.owner == me:
            continue

        # Prefer neutral territory, but rival territory can be worthwhile.
        reward = c.base_points
        if c.owner != 0:
            reward += 2.5 if not c.is_upgraded else 1.5

        score = reward / (dist + 1.0)

        # Slight preference for moving toward the centre.
        r, col = divmod(p, 8)
        centrality = 7 - (abs(r - 3.5) + abs(col - 3.5))
        score += max(0, centrality) * 0.025

        if score > best_score:
            best_score = score
            best_target = p

    if best_target is not None:
        for action, nxt in neighbors(pos):
            if nxt in distances and nxt == best_target and action in legal:
                return action

        # Move toward the target along the shortest path.
        for action, nxt in neighbors(pos):
            if nxt not in distances:
                continue
            if distances[nxt] < distances[pos]:
                return action

        # Reconstruct the first step.
        for action, nxt in neighbors(pos):
            if cells[nxt].occupant != 0:
                continue
            if nxt == best_target:
                return action

        # BFS from the target to recover a first move.
        reverse = {best_target: 0}
        q = [best_target]
        for p in q:
            for _, n in neighbors(p):
                if n not in reverse and cells[n].occupant == 0:
                    reverse[n] = reverse[p] + 1
                    q.append(n)

        options = [
            (reverse.get(n, 999), action)
            for action, n in neighbors(pos)
            if n in reverse and action in legal
        ]

        if options:
            return min(options)[1]

    if "STAY" in legal:
        return "STAY"

    return legal[0]