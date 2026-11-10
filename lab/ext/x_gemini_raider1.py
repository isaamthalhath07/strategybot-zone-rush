"""Raider bot: hunts rival level-1 cells after turn 20 and shields when invaded."""

_turn_count = 0

def act(state):
    global _turn_count
    _turn_count += 1
    
    board = state.board if not (len(state.board) == 8 and isinstance(state.board[0], list)) else [c for row in state.board for c in row]
    
    my_r, my_c = 0, 0
    for idx, cell in enumerate(board):
        occ = getattr(cell, 'occupant', 0) if not isinstance(cell, dict) else cell.get('occupant', 0)
        if occ == state.bot_id:
            my_r, my_c = idx // 8, idx % 8
            break
            
    legal = state.legal_actions
    if not legal:
        return "STAY"
        
    # Check if any rival is on our land (owner == bot_id and occupant != 0 and occupant != bot_id)
    invaded = False
    for cell in board:
        o = getattr(cell, 'owner', 0) if not isinstance(cell, dict) else cell.get('owner', 0)
        occ = getattr(cell, 'occupant', 0) if not isinstance(cell, dict) else cell.get('occupant', 0)
        if o == state.bot_id and occ != 0 and occ != state.bot_id:
            invaded = True
            break
            
    if invaded and "SHIELD" in legal:
        return "SHIELD"
        
    # After turn 20, hunt un-upgraded rival cells
    if _turn_count > 20:
        best_target = None
        min_dist = 999.0
        for idx, cell in enumerate(board):
            r, c = idx // 8, idx % 8
            o = getattr(cell, 'owner', 0) if not isinstance(cell, dict) else cell.get('owner', 0)
            upg = getattr(cell, 'is_upgraded', False) if not isinstance(cell, dict) else cell.get('is_upgraded', False)
            home = getattr(cell, 'is_home', False) if not isinstance(cell, dict) else cell.get('is_home', False)
            if o != 0 and o != state.bot_id and not upg and not home:
                d = abs(r - my_r) + abs(c - my_c)
                if d < min_dist:
                    min_dist = d
                    best_target = (r, c)
                    
        if best_target:
            tr, tc = best_target
            best_action = legal[0]
            d_best = 999.0
            for action in legal:
                if action == "SHIELD": continue
                nr, nc = my_r, my_c
                if action == "NORTH": nr -= 1
                elif action == "SOUTH": nr += 1
                elif action == "WEST": nc -= 1
                elif action == "EAST": nc += 1
                d = abs(tr - nr) + abs(tc - nc)
                if d < d_best:
                    d_best = d
                    best_action = action
            return best_action if best_action in legal else legal[0]
            
    return legal[0]