"""Opportunist: attacks rival territory when its owner is frozen or on shield cooldown."""

# Persistent information between turns.
_previous_frozen = {}
_previous_owner = {}
_shield_cooldown = {}
_last_position = None
_last_turn = -1


def act(state):
    global _previous_frozen, _previous_owner
    global _shield_cooldown, _last_position, _last_turn

    raw = state.board
    board = [c for row in raw for c in row] if raw and isinstance(raw[0], (list, tuple)) else raw
    me = state.bot_id
    legal = state.legal_actions

    pos = next((i for i, c in enumerate(board) if c.occupant == me), None)

    if pos is None:
        return "STAY"

    # Advance our approximate internal clock.
    _last_turn += 1

    for player in range(1, 5):
        if player != me:
            _shield_cooldown[player] = max(
                0, _shield_cooldown.get(player, 0) - 1
            )

    # Detect a shield from a newly frozen bot standing on another
    # player's territory. That player must have activated the shield.
    for cell in board:
        if cell.occupant and cell.occupant != me:
            player = cell.occupant
            if cell.is_frozen and not _previous_frozen.get(player, False):
                if cell.owner != player:
                    _shield_cooldown[cell.owner] = 4
            _previous_frozen[player] = cell.is_frozen

    # Our own newly acquired frozen status can reveal the landlord's shield.
    if board[pos].is_frozen:
        owner = board[pos].owner
        if owner != 0 and owner != me:
            _shield_cooldown[owner] = 4
        return "STAY"

    # A cell that was previously owned by us and is now owned by someone
    # else indicates that an opponent successfully raided it.
    for i, cell in enumerate(board):
        old = _previous_owner.get(i, 0)
        if old == me and cell.owner not in (0, me):
            raider = cell.owner
            _shield_cooldown.setdefault(raider, 0)

    _previous_owner = {i: c.owner for i, c in enumerate(board)}

    if board[pos].owner != me and not board[pos].is_home and "STAY" in legal:  # FIX: arriving does not take a cell (rulebook: STAY on it); the target search below skips the cell it stands on, so it walked off every target
        return "STAY"

    def neighbors(p):
        r, c = divmod(p, 8)
        result = []
        if r > 0: result.append(("NORTH", p - 8))
        if c < 7: result.append(("EAST", p + 1))
        if r < 7: result.append(("SOUTH", p + 8))
        if c > 0: result.append(("WEST", p - 1))
        return result

    # Search for the nearest profitable vulnerable rival cell.
    from collections import deque

    dist = {pos: 0}
    first = {}
    q = deque([pos])

    while q:
        p = q.popleft()

        for action, n in neighbors(p):
            if board[n].occupant != 0 or n in dist:
                continue

            dist[n] = dist[p] + 1
            first[n] = action if p == pos else first[p]
            q.append(n)

    targets = []

    for p, d in dist.items():
        cell = board[p]

        if p == pos or cell.owner in (0, me) or cell.is_home:
            continue

        landlord = cell.owner

        frozen = _previous_frozen.get(landlord, False)
        cooling = _shield_cooldown.get(landlord, 0) > 0

        # Do not waste time attacking protected, upgraded territory.
        if not (frozen or cooling):
            continue

        if cell.is_upgraded:
            continue

        # Raid bonuses make three-point cells particularly valuable.
        reward = cell.base_points * 8 + cell.base_points
        score = reward / (d + 1)

        targets.append((score, p))

    if targets:
        targets.sort(reverse=True)
        direction = first.get(targets[0][1])

        if direction in legal:
            return direction

    # Ordinary expansion if no vulnerable rival property is available.
    alternatives = []

    for action, n in neighbors(pos):
        if action not in legal or board[n].occupant != 0:
            continue

        c = board[n]
        if c.owner == me or c.is_home:
            continue

        score = c.base_points
        if c.owner:
            score += 1

        alternatives.append((score, action))

    if alternatives:
        return max(alternatives)[1]

    return "STAY" if "STAY" in legal else legal[0]