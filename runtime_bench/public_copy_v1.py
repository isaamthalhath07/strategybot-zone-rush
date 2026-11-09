"""Version1 copy for the exact canonical reference-engine public View schema.

This is an experimental harness boundary, not an alternative bot input parser.
No private referee object or source counter is accepted. Every mutable public
container and Cell is separately allocated for every call.
"""
from tests import reference_engine as engine

VIEW_FIELDS = {'board', 'bot_id', 'is_priority_token', 'legal_actions'}
CELL_FIELDS = {'occupant', 'owner', 'is_upgraded', 'is_home', 'is_frozen', 'base_points'}
ACTIONS = frozenset(engine.ACTIONS)


def clone_public(view):
    if type(view) is not engine.View or set(view.__slots__) != VIEW_FIELDS:
        raise TypeError('Structural copy requires the exact canonical public View')
    if set(engine.Cell.__slots__) != CELL_FIELDS:
        raise TypeError('Canonical public Cell contract changed')
    if type(view.bot_id) is not int or not 1 <= view.bot_id <= 4 or type(view.is_priority_token) is not bool:
        raise ValueError('Invalid public identity/priority fields')
    if (type(view.legal_actions) is not list or not view.legal_actions
            or any(type(action) is not str or action not in ACTIONS for action in view.legal_actions)):
        raise ValueError('Invalid canonical legal-action list')
    board = view.board
    if type(board) is not list or len(board) != 8:
        raise ValueError('Canonical public board requires8 rows')
    rows, cell_ids, row_ids = [], set(), set()
    for row in board:
        if type(row) is not list or len(row) != 8 or id(row) in row_ids:
            raise ValueError('Canonical public board requires8 independent8-cell rows')
        row_ids.add(id(row))
        copied = []
        for cell in row:
            if type(cell) is not engine.Cell or id(cell) in cell_ids:
                raise TypeError('Canonical board requires64 independent public Cells')
            cell_ids.add(id(cell))
            occupant, owner, up, home, frozen, base = (cell.occupant, cell.owner, cell.is_upgraded,
                                                       cell.is_home, cell.is_frozen, cell.base_points)
            if (type(occupant) is not int or not 0 <= occupant <= 4
                    or type(owner) is not int or not 0 <= owner <= 4
                    or type(base) is not int or not 1 <= base <= 3
                    or type(up) is not bool or type(home) is not bool or type(frozen) is not bool):
                raise ValueError('Invalid canonical public Cell scalar fields')
            copied.append(engine.Cell(occupant, owner, up, home, frozen, base))
        rows.append(copied)
    return engine.View(rows, view.bot_id, view.is_priority_token, list(view.legal_actions))
