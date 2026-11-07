"""Naive random walker: STAYs on any non-home cell it doesn't own yet, otherwise wanders randomly; never shields."""
import random


def act(state):
    board = state.board
    if len(board) == 64:
        cells = list(board)
    else:
        cells = [cell for row in board for cell in row]
    me = state.bot_id
    legal = list(state.legal_actions)

    here = None
    for cell in cells:
        if cell.occupant == me:
            here = cell
            break

    if here is not None and not here.is_home:
        if here.owner != me:
            return "STAY"
        # on our own level-1 cell: sometimes hang around (accidentally upgrades)
        if not here.is_upgraded and random.random() < 0.3:
            return "STAY"

    moves = [a for a in legal if a in ("NORTH", "SOUTH", "EAST", "WEST")]
    if not moves:
        return "STAY"
    return random.choice(moves)
