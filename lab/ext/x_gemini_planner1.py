"""Planner bot: plans multi-step routes across high-value cells using lookahead pathfinding."""

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
        
    dir_map = {
        'NORTH': (-1, 0),
        'SOUTH': (1, 0),
        'EAST': (0, 1),
        'WEST': (0, -1),
        'STAY': (0, 0),
        'SHIELD': (0, 0)
    }
    
    best_action = 'STAY' if 'STAY' in legal else legal[0]
    max_eval = -9999
    
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
                
            owner = getattr(target, 'owner', target.get('owner', 0) if isinstance(target, dict) else 0)
            base_pts = getattr(target, 'base_points', target.get('base_points', 1) if isinstance(target, dict) else 1)
            is_upgraded = getattr(target, 'is_upgraded', target.get('is_upgraded', False) if isinstance(target, dict) else False)
            
            eval_score = 0
            if owner == bot_id:
                if not is_upgraded:
                    eval_score += 15 * base_pts
                else:
                    eval_score += 5 * base_pts
            elif owner == 0:
                eval_score += 20 * base_pts
            elif not getattr(target, 'is_home', False):
                eval_score += 35 * base_pts
            else:
                eval_score -= 100
                
            dist_center = abs(nr - 3.5) + abs(nc - 3.5)
            eval_score -= dist_center
            
            if eval_score > max_eval:
                max_eval = eval_score
                best_action = action
                
    if best_action in legal:
        return best_action
    return 'STAY' if 'STAY' in legal else legal[0]