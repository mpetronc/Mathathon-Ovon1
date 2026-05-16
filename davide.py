import random

def get_best_move(values):
    # This perfectly mirrors your parsing template
    players = [
        {"position": values[i], "cumulative": values[i + 1]}
        for i in range(0, len(values), 2)
    ]

    my_position = players[0]['position']
    my_cumulative = players[0]['cumulative']
    leader_position = max(player['position'] for player in players)
    
    # --- YOUR STRATEGY LOGIC GOES HERE ---
    
    # 1. Endgame Snipe
    dist_to_win = 999 - my_position
    if dist_to_win <= 100:
        return max(1, dist_to_win)
    
    # 2. Check opponents' cumulatives to see if we have a "shield"
    max_opp_c = max(player['cumulative'] for player in players[1:])
    
    # 3. Decide output
    base_play = random.randint(82, 94)
    if my_cumulative > max_opp_c + 50:
        base_play = random.randint(90, 98) # Flex the shield
        
    return base_play