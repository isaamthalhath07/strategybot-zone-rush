"""Quadrant farmer bot: focuses on local cells and upgrades high-value ones."""

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
    
    current_cell = board[my_r * 8 + my_c]
    owner = getattr(current_cell, 'owner', 0) if not isinstance(current_cell, dict) else current_cell.get('owner', 0)
    is_upgraded = getattr(current_cell, 'is_upgraded', False) if not isinstance(current_cell, dict) else current_cell.get('is_upgraded', False)
    base = getattr(current_cell, 'base_points', 1) if not isinstance(current_cell, dict) else current_cell.get('base_points', 1)
    
    legal = state.legal_actions
    if not legal:
        return "STAY"
        
    # If on own cell with high base points and not upgraded, stay to upgrade
    if owner == state.bot_id and not is_upgraded and base >= 2 and "STAY" in legal:
        return "STAY"
    if owner != state.bot_id and "STAY" in legal:  # FIX: arriving does not take a cell (rulebook: STAY on it); STAY scored the same as moving to an equal cell and lost the tie, so it shuttled and never claimed
        return "STAY"
        
    # Otherwise expand within quadrant (manhattan distance from home <= 4)
    best_action = legal[0]
    best_score = -999.0
    for action in legal:
        if action == "SHIELD":
            continue
        nr, nc = my_r, my_c
        if action == "NORTH": nr -= 1
        elif action == "SOUTH": nr += 1
        elif action == "WEST": nc -= 1
        elif action == "EAST": nc += 1
        elif action == "STAY": pass
        
        dist_home = abs(nr - hr) + abs(nc - hc)
        if dist_home > 4:
            score = -50.0
        else:
            idx = nr * 8 + nc
            cell = board[idx]
            o = getattr(cell, 'owner', 0) if not isinstance(cell, dict) else cell.get('owner', 0)
            bp = getattr(cell, 'base_points', 1) if not isinstance(cell, dict) else cell.get('base_points', 1)
            score = bp if o == 0 else (10.0 if o != state.bot_id else 0.0)
            
        if score > best_score:
            best_score = score
            best_action = action
            
    return best_action if best_action in legal else legal[0]