"""Greedy bot: targets high value-to-distance cells and never shields."""

def act(state):
    board = state.board if not (len(state.board) == 8 and isinstance(state.board[0], list)) else [c for row in state.board for c in row]
    
    my_r, my_c = 0, 0
    for idx, cell in enumerate(board):
        occ = getattr(cell, 'occupant', 0) if not isinstance(cell, dict) else cell.get('occupant', 0)
        if occ == state.bot_id:
            my_r, my_c = idx // 8, idx % 8
            break
            
    legal = [a for a in state.legal_actions if a != "SHIELD"]
    if not legal:
        legal = state.legal_actions
    if not legal:
        return "STAY"

    here = board[my_r * 8 + my_c]  # FIX: the cell it stands on, read by the next line
    if (here.get('owner', 0) if isinstance(here, dict) else here.owner) != state.bot_id and not (here.get('is_home', False) if isinstance(here, dict) else here.is_home) and "STAY" in legal:  # FIX: arriving does not take a cell (rulebook: STAY on it); the target search below skips its own cell (dist 0), so it walked off every target
        return "STAY"
        
    # Find best target cell across board based on value / distance
    best_target = None
    best_ratio = -999.0
    for idx, cell in enumerate(board):
        r, c = idx // 8, idx % 8
        owner = getattr(cell, 'owner', 0) if not isinstance(cell, dict) else cell.get('owner', 0)
        if owner == state.bot_id:
            continue
        base = getattr(cell, 'base_points', 1) if not isinstance(cell, dict) else cell.get('base_points', 1)
        dist = abs(r - my_r) + abs(c - my_c)
        if dist == 0:
            continue
        ratio = float(base * (3 if owner != 0 else 1)) / dist
        if ratio > best_ratio:
            best_ratio = ratio
            best_target = (r, c)
            
    if not best_target:
        return legal[0]
        
    tr, tc = best_target
    best_action = legal[0]
    min_dist = 999.0
    
    for action in legal:
        if action == "STAY":
            d = abs(tr - my_r) + abs(tc - my_c)
        else:
            nr, nc = my_r, my_c
            if action == "NORTH": nr -= 1
            elif action == "SOUTH": nr += 1
            elif action == "WEST": nc -= 1
            elif action == "EAST": nc += 1
            d = abs(tr - nr) + abs(tc - nc)
        if d < min_dist:
            min_dist = d
            best_action = action
            
    return best_action if best_action in legal else legal[0]