"""Turtle bot: stays near home and shields immediately when enemies approach."""

def act(state):
    board = state.board if not (len(state.board) == 8 and isinstance(state.board[0], list)) else [c for row in state.board for c in row]
    
    my_r, my_c = 0, 0
    for idx, cell in enumerate(board):
        occ = getattr(cell, 'occupant', 0) if not isinstance(cell, dict) else cell.get('occupant', 0)
        if occ == state.bot_id:
            my_r, my_c = idx // 8, idx % 8
            break
            
    corners = {1: (0, 0), 2: (0, 7), 3: (7, 7), 4: (7, 0)}
    hr, hc = corners.get(state.bot_id, (0, 0))
    
    legal = state.legal_actions
    if not legal:
        return "STAY"
        
    # Check if any rival is on our land
    invaded = False
    for cell in board:
        o = getattr(cell, 'owner', 0) if not isinstance(cell, dict) else cell.get('owner', 0)
        occ = getattr(cell, 'occupant', 0) if not isinstance(cell, dict) else cell.get('occupant', 0)
        if o == state.bot_id and occ != 0 and occ != state.bot_id:
            invaded = True
            break
            
    if invaded and "SHIELD" in legal:
        return "SHIELD"
        
    # Stay near home (Manhattan distance <= 2)
    best_action = legal[0]
    min_home_dist = 999.0
    for action in legal:
        if action == "SHIELD": continue
        nr, nc = my_r, my_c
        if action == "NORTH": nr -= 1
        elif action == "SOUTH": nr += 1
        elif action == "WEST": nc -= 1
        elif action == "EAST": nc += 1
        elif action == "STAY": pass
        
        hd = abs(nr - hr) + abs(nc - hc)
        if hd < min_home_dist:
            min_home_dist = hd
            best_action = action
            
    return best_action if best_action in legal else legal[0]