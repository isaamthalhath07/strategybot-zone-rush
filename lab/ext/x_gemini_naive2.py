"""Naive bot: picks simple moves toward neutral or valuable cells."""

def act(state):
    # Parse board and find own position
    board = state.board if not (len(state.board) == 8 and isinstance(state.board[0], list)) else [c for row in state.board for c in row]
    
    # Find current bot position (where occupant == bot_id)
    my_r, my_c = 0, 0
    for idx, cell in enumerate(board):
        occupant = getattr(cell, 'occupant', 0) if not isinstance(cell, dict) else cell.get('occupant', 0)
        if occupant == state.bot_id:
            my_r, my_c = idx // 8, idx % 8
            break
            
    legal = state.legal_actions
    if not legal:
        return "STAY"
        
    # Evaluate actions based on target cell value / ownership
    best_action = legal[0]
    best_score = -999.0
    
    for action in legal:
        if action == "SHIELD":
            score = 1.0
        elif action == "STAY":
            idx = my_r * 8 + my_c
            cell = board[idx]
            owner = getattr(cell, 'owner', 0) if not isinstance(cell, dict) else cell.get('owner', 0)
            base = getattr(cell, 'base_points', 1) if not isinstance(cell, dict) else cell.get('base_points', 1)
            score = base if owner == state.bot_id else 2.0
        else:
            r, c = my_r, my_c
            if action == "NORTH": r -= 1
            elif action == "SOUTH": r += 1
            elif action == "WEST": c -= 1
            elif action == "EAST": c += 1
            
            if 0 <= r < 8 and 0 <= c < 8:
                idx = r * 8 + c
                cell = board[idx]
                owner = getattr(cell, 'owner', 0) if not isinstance(cell, dict) else cell.get('owner', 0)
                base = getattr(cell, 'base_points', 1) if not isinstance(cell, dict) else cell.get('base_points', 1)
                occupant = getattr(cell, 'occupant', 0) if not isinstance(cell, dict) else cell.get('occupant', 0)
                
                if occupant != 0:
                    score = -10.0 # closed / occupied
                elif owner == 0:
                    score = 5.0 + base # neutral
                elif owner == state.bot_id:
                    score = float(base) # own
                else:
                    score = 8.0 * base # rival
            else:
                score = -100.0
                
        if score > best_score:
            best_score = score
            best_action = action
            
    return best_action if best_action in legal else legal[0]