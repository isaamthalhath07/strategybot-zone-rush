"""Adaptive bot: retaliates against whoever raids it most by targeting their cells."""

_grievances = {1: 0, 2: 0, 3: 0, 4: 0}
_prev_owners = {}

def act(state):
    global _grievances, _prev_owners
    
    board = state.board
    if len(board) == 64 and not isinstance(board[0], list):
        grid = [board[i*8:(i+1)*8] for i in range(8)]
    else:
        grid = board
        
    bot_id = state.bot_id
    legal = state.legal_actions
    
    for r in range(8):
        for c in range(8):
            cell = grid[r][c]
            owner = getattr(cell, 'owner', cell.get('owner', 0) if isinstance(cell, dict) else 0)
            cell_key = (r, c)
            prev_owner = _prev_owners.get(cell_key, bot_id)
            if prev_owner == bot_id and owner != bot_id and owner != 0:
                _grievances[owner] = _grievances.get(owner, 0) + 1
            _prev_owners[cell_key] = owner
            
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
        
    worst_rival = max([1, 2, 3, 4], key=lambda x: _grievances.get(x, 0) if x != bot_id else -1)
    
    dir_map = {
        'NORTH': (-1, 0),
        'SOUTH': (1, 0),
        'EAST': (0, 1),
        'WEST': (0, -1),
        'STAY': (0, 0),
        'SHIELD': (0, 0)
    }
    
    best_action = 'STAY' if 'STAY' in legal else legal[0]
    best_score = -999
    
    for action in legal:
        if action not in dir_map:
            continue
        dr, dc = dir_map[action]
        nr, nc = r + dr, c + dc
        if 0 <= nr < 8 and 0 <= nc < 8:
            target = grid[nr][nc]
            occ = getattr(target, 'occupant', target.get('occupant', 0) if isinstance(target, dict) else 0)
            if occ != 0:
                continue
            owner = getattr(target, 'owner', target.get('owner', 0) if isinstance(target, dict) else 0)
            base_pts = getattr(target, 'base_points', target.get('base_points', 1) if isinstance(target, dict) else 1)
            
            score = 0
            if owner == worst_rival and not getattr(target, 'is_home', False):
                score += 30 * base_pts
            elif owner == 0:
                score += 10 * base_pts
            elif owner != bot_id and not getattr(target, 'is_home', False):
                score += 15 * base_pts
            else:
                score += base_pts
                
            if score > best_score:
                best_score = score
                best_action = action
                
    if best_action in legal:
        return best_action
    return 'STAY' if 'STAY' in legal else legal[0]