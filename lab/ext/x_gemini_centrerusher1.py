"""Centre rusher bot: prioritizes rushing to and capturing the center 3-point cells."""

def act(state):
    board = state.board
    if len(board) == 64 and not isinstance(board[0], list):
        grid = [board[i*8:(i+1)*8] for i in range(8)]
    else:
        grid = board
        
    bot_id = state.bot_id
    legal = state.legal_actions
    
    pos = None
    for r in range(8):
        for c in range(8):
            cell = grid[r][c]
            occ = getattr(cell, 'occupant', cell.get('occupant', 0) if isinstance(cell, dict) else 0)
            if occ == bot_id:
                pos = (r, c)
                break
        if pos:
            break
            
    if not pos:
        pos = (0, 0)
        
    r, c = pos
    current_cell = grid[r][c]
    cur_owner = getattr(current_cell, 'owner', current_cell.get('owner', 0) if isinstance(current_cell, dict) else 0)
    is_home = getattr(current_cell, 'is_home', current_cell.get('is_home', False) if isinstance(current_cell, dict) else False)
    
    if cur_owner != bot_id and not is_home and 'STAY' in legal:
        return 'STAY'
        
    centers = [(3,3), (3,4), (4,3), (4,4)]
    
    dir_map = {
        'NORTH': (-1, 0),
        'SOUTH': (1, 0),
        'EAST': (0, 1),
        'WEST': (0, -1),
        'STAY': (0, 0),
        'SHIELD': (0, 0)
    }
    
    best_action = 'STAY' if 'STAY' in legal else legal[0]
    min_dist = 999
    
    for action in legal:
        if action not in dir_map:
            continue
        dr, dc = dir_map[action]
        nr, nc = r + dr, c + dc
        if 0 <= nr < 8 and 0 <= nc < 8:
            target = grid[nr][nc]
            occ = getattr(target, 'occupant', target.get('occupant', 0) if isinstance(target, dict) else 0)
            if occ != 0 and (nr, nc) != (r, c):
                continue
            d = min(abs(nr - cr) + abs(nc - cc) for cr, cc in centers)
            if d < min_dist:
                min_dist = d
                best_action = action
                
    if best_action in legal:
        return best_action
    return 'STAY' if 'STAY' in legal else legal[0]