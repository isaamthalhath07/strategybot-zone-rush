"""Turtle: digs in within two steps of its home, upgrades everything there, shields at the first rival on its land, otherwise sits."""

RADIUS = 2
_M = {"cool": 0, "total": 0}


def _flat(board):
    if len(board) == 64:
        return list(board)
    return [cell for row in board for cell in row]


def act(state):
    me = state.bot_id
    legal = state.legal_actions
    cells = _flat(state.board)

    pos = home = None
    total = 0
    intruder = False
    for i, cell in enumerate(cells):
        if cell.occupant == me:
            pos = (i // 8, i % 8)
        if cell.is_home and cell.owner == me:
            home = (i // 8, i % 8)
        if cell.owner:
            total += 1
        if (cell.owner == me and cell.occupant and cell.occupant != me
                and not cell.is_frozen):
            intruder = True
    if pos is None:
        return "STAY"
    if home is None:
        home = pos

    if total < _M["total"]:
        _M["cool"] = 0
    _M["total"] = total
    if _M["cool"] > 0:
        _M["cool"] -= 1

    if intruder and _M["cool"] == 0 and "SHIELD" in legal:
        _M["cool"] = 5
        return "SHIELD"

    def near_home(p):
        return abs(p[0] - home[0]) + abs(p[1] - home[1]) <= RADIUS

    here = cells[pos[0] * 8 + pos[1]]
    if near_home(pos) and not here.is_home:
        if here.owner == 0:
            return "STAY"
        if here.owner == me and not here.is_upgraded:
            return "STAY"

    # nearest unclaimed or un-upgraded cell inside the safe zone, else go back to the home cell
    goal = None
    for i, cell in enumerate(cells):
        p = (i // 8, i % 8)
        if p == pos or not near_home(p) or cell.occupant or cell.is_home:
            continue
        if cell.owner == 0 or (cell.owner == me and not cell.is_upgraded):
            key = (abs(p[0] - pos[0]) + abs(p[1] - pos[1]), cell.owner != 0, p)
            if goal is None or key < goal:
                goal = key
    if goal is None:
        target = home
    else:
        target = goal[2]
    if target == pos:
        return "STAY"

    # one step, columns first; if that cell is closed (someone standing there) try the other axis
    steps = []
    if target[1] != pos[1]:
        steps.append(("EAST", pos[0], pos[1] + 1) if target[1] > pos[1] else ("WEST", pos[0], pos[1] - 1))
    if target[0] != pos[0]:
        steps.append(("SOUTH", pos[0] + 1, pos[1]) if target[0] > pos[0] else ("NORTH", pos[0] - 1, pos[1]))
    for move, r, c in steps:
        if move in legal and not cells[r * 8 + c].occupant:
            return move
    return "STAY"
