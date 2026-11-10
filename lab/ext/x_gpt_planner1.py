"""Planner: uses a bounded multi-step beam search to plan efficient routes across the board."""

import heapq

BOARD_SIZE = 8
SEARCH_DEPTH = 7
BEAM_WIDTH = 35

def act(state):
    raw = state.board
    board = [c for row in raw for c in row] if raw and isinstance(raw[0], (list, tuple)) else raw
    me = state.bot_id
    legal = state.legal_actions

    start = next((i for i, c in enumerate(board) if c.occupant == me), None)

    if start is None:
        return "STAY"

    if board[start].is_frozen:
        return "STAY"

    def adjacent(p):
        r, c = divmod(p, BOARD_SIZE)

        if r > 0:
            yield "NORTH", p - 8
        if c < 7:
            yield "EAST", p + 1
        if r < 7:
            yield "SOUTH", p + 8
        if c > 0:
            yield "WEST", p - 1

    def cell_reward(p):
        cell = board[p]

        if cell.is_home:
            return -1000

        if cell.owner == me:
            if not cell.is_upgraded:
                # Upgrading valuable cells has a good long-term return.
                return cell.base_points * 0.75
            return 0

        value = cell.base_points

        if cell.owner == 0:
            return value * 1.4 + 1

        # Raids offer a one-off bonus, but upgraded cells require
        # more commitment to capture.
        raid_bonus = 8 * value * (2 if cell.is_upgraded else 1)
        capture_cost = 3 if cell.is_upgraded else 1

        return value + raid_bonus / 8.0 - capture_cost * 0.5

    # Search states:
    # (estimated score, position, first action, visited mask, path score)
    beam = [(0.0, start, None, 1 << start, 0.0)]
    best_action = "STAY"
    best_value = -float("inf")

    # Staying on an enemy or neutral cell is a valid capture action.
    current_reward = cell_reward(start)

    if board[start].owner != me and not board[start].is_home:
        best_value = current_reward * 1.2

    for depth in range(1, SEARCH_DEPTH + 1):
        next_states = []

        for _, position, first_action, visited, accumulated in beam:

            for direction, nxt in adjacent(position):

                if direction not in legal and position == start:
                    continue

                # Occupied cells are closed for the whole turn.
                if board[nxt].occupant != 0:
                    continue

                bit = 1 << nxt
                if visited & bit:
                    continue

                reward = cell_reward(nxt)

                # Movement costs one turn. Staying to capture costs another.
                delay = depth + 1
                discounted = reward / (1.0 + depth * 0.48)

                # A route through valuable cells is better than repeatedly
                # chasing one distant target.
                route_bonus = max(0, reward) * 0.12

                new_score = accumulated + discounted + route_bonus

                chosen = direction if first_action is None else first_action

                # Evaluate capturing the current destination.
                capture_value = new_score - depth * 0.45

                if capture_value > best_value:
                    best_value = capture_value
                    best_action = chosen

                # Also consider longer routes beyond this cell.
                heuristic = new_score + (SEARCH_DEPTH - depth) * 0.12

                next_states.append((
                    heuristic,
                    nxt,
                    chosen,
                    visited | bit,
                    new_score
                ))

        if not next_states:
            break

        # Keep only the strongest diverse-looking paths.
        next_states.sort(reverse=True, key=lambda item: item[0])
        beam = next_states[:BEAM_WIDTH]

    # Upgrade a valuable cell when there is no clearly better route.
    here = board[start]

    if here.owner == me and not here.is_upgraded and here.base_points >= 2:
        upgrade_value = here.base_points * 1.5

        if upgrade_value > best_value and "STAY" in legal:
            return "STAY"

    # A bot already standing on enemy territory should continue taking it.
    if here.owner not in (0, me) and not here.is_home:
        if "STAY" in legal:
            return "STAY"

    if best_action in legal:
        return best_action

    return "STAY" if "STAY" in legal else legal[0]