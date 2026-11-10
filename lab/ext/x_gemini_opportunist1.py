"""Opportunist bot: tracks shield cooldowns and raids rival cells when landlords are vulnerable."""

_shield_cooldowns = {1: 0, 2: 0, 3: 0, 4: 0}
_turn = 0

def act(state):
    global _shield_cooldowns, _turn
    _turn += 1
    
    board = state.board
    if len(board) == 64 and not isinstance(board[0], list):
        grid = [board[i*8:(i+1)*8] for i in range(8)]
    else:
        grid = board
        
    bot_id = state.bot_id
    legal = state.legal_actions
    
    for b in _shield_cooldowns:
        if _shield_cooldowns[b] > 0:
            _shield_cooldowns[b] -= 1
            
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
    best_val = -999
    
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
            
            val = 0
            if owner == 0:
                val = 5 * base_pts
            elif owner != bot_id and not getattr(target, 'is_home', False):
                is_frozen = any(getattr(x, 'occupant', 0) == owner and getattr(x, 'is_frozen', False) for row in grid for x in row)  # FIX: is_frozen describes a cell's occupant, so read the landlord's own cell; the empty target cell was never frozen, so the raid-a-frozen-landlord branch could not fire
                if _shield_cooldowns.get(owner, 0) > 0 or is_frozen:
                    val = 25 * base_pts
                else:
                    val = 2 * base_pts
            else:
                val = base_pts
                
            if val > best_val:
                best_val = val
                best_action = action
                
    if best_action in legal:
        return best_action
    return 'STAY' if 'STAY' in legal else legal[0]