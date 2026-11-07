"""Level-1 raider: only ever raids rival level-1 cells (one STAY, hit and run), claims neutral land otherwise, never upgrades."""


def _flat(board):
    if len(board) == 64:
        return list(board)
    out = []
    for row in board:
        out.extend(row)
    return out


def _move(r, c, tr, tc, cells, legal):
    """Step toward (tr, tc): rows first, switch axis if the first step is closed."""
    order = []
    if tr != r:
        order.append(("SOUTH" if tr > r else "NORTH", r + (1 if tr > r else -1), c))
    if tc != c:
        order.append(("EAST" if tc > c else "WEST", r, c + (1 if tc > c else -1)))
    for name, nr, nc in order:
        if name in legal and not cells[nr * 8 + nc].occupant:
            return name
    return "STAY"


def act(state):
    me = state.bot_id
    legal = state.legal_actions
    cells = _flat(state.board)

    pos = -1
    for i, cell in enumerate(cells):
        if cell.occupant == me:
            pos = i
            break
    if pos < 0:
        return "STAY"
    r, c = divmod(pos, 8)
    here = cells[pos]

    if here.owner == 0:
        return "STAY"
    if here.owner != me and not here.is_home and not here.is_upgraded:
        return "STAY"          # rival level-1 cell: take it now

    prey = None
    land = None
    for i, cell in enumerate(cells):
        if cell.occupant:
            continue
        d = abs(i // 8 - r) + abs(i % 8 - c)
        if cell.owner not in (0, me) and not cell.is_home and not cell.is_upgraded:
            key = (d - cell.base_points, i)
            if prey is None or key < prey:
                prey = key
        elif cell.owner == 0:
            key = (d - cell.base_points, i)
            if land is None or key < land:
                land = key

    pick = prey if prey is not None else land
    if pick is None:
        return "STAY"
    tr, tc = divmod(pick[1], 8)
    return _move(r, c, tr, tc, cells, legal)
