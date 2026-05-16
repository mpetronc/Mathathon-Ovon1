import sys
from collections import deque
import random

# Game constants
WIDTH, HEIGHT = 31, 31

# -1 = empty, 0 = our cells, 1/2/3 = opponent cells
board = [[-1] * WIDTH for _ in range(HEIGHT)]

# Keep track of previous round coordinates to detect dead/frozen players
last_coords = None

def is_safe(x, y):
    """A cell is safe if it's within bounds and is either empty or claimed by US."""
    return 0 <= x < WIDTH and 0 <= y < HEIGHT and board[y][x] in (-1, 0)

def is_empty(x, y):
    """Check if a cell is completely unclaimed."""
    return 0 <= x < WIDTH and 0 <= y < HEIGHT and board[y][x] == -1

def evaluate_move(start_x, start_y, opp_heads):
    """
    Highly optimized BFS using a 2D boolean array.
    Returns a priority tuple prioritizing empty space, safety, and opponent avoidance.
    """
    if not is_safe(start_x, start_y):
        return (-1, float('-inf'), False, float('-inf'), -1)
    
    # 2D array is an order of magnitude faster than a Python set() for coordinate hashing
    visited = [[False] * WIDTH for _ in range(HEIGHT)]
    visited[start_y][start_x] = True
    
    queue = deque([(start_x, start_y, 1)])
    
    reachable_empty = 0
    reachable_safe = 1 # Counts our own cells to prevent dead-ending during infinite survival
    min_dist_to_empty = float('inf')
    
    if is_empty(start_x, start_y):
        reachable_empty += 1
        min_dist_to_empty = 1
        
    while queue:
        cx, cy, dist = queue.popleft()
        
        for dx, dy in [(0, -1), (0, 1), (-1, 0), (1, 0)]:
            nx, ny = cx + dx, cy + dy
            
            # Fast bounds and visited check
            if 0 <= nx < WIDTH and 0 <= ny < HEIGHT and not visited[ny][nx]:
                if board[ny][nx] in (-1, 0):  # If the cell is safe
                    visited[ny][nx] = True
                    queue.append((nx, ny, dist + 1))
                    reachable_safe += 1
                    
                    if board[ny][nx] == -1:  # If it is strictly empty
                        reachable_empty += 1
                        if min_dist_to_empty == float('inf'):
                            min_dist_to_empty = dist + 1
                            
    # Apply a penalty if this initial step risks a head-on collision with a living opponent
    threatened = 1 if (start_x, start_y) in opp_heads else 0
    
    # Tuple sorting hierarchy:
    # 1. Maximize empty space reachable
    # 2. Avoid moving directly next to an active opponent (-threatened)
    # 3. Prefer claiming a point NOW rather than later
    # 4. Shortest path to empty space
    # 5. Maximize safe space (Crucial fallback when reachable_empty is 0)
    return (reachable_empty, -threatened, is_empty(start_x, start_y), -min_dist_to_empty, reachable_safe)

# Main Game Loop
while True:
    try:
        line = input().strip()
        if not line:
            continue
            
        parts = line.split()
        if parts[0] == "IN":
            parts = parts[1:]
            
        coords = list(map(int, parts))
        
        opp_heads = set()
        
        # Parse the board
        for i in range(0, 8, 2):
            px, py = coords[i], coords[i+1]
            player_id = i // 2
            
            if 0 <= px < WIDTH and 0 <= py < HEIGHT:
                if player_id == 0:
                    # Always mark our own cells
                    board[py][px] = 0
                else:
                    # FIX: Never let a dead opponent's frozen body overwrite our safe trail
                    if board[py][px] != 0:
                        board[py][px] = player_id
                        
                    # FIX: Determine if opponent is alive to calculate collision threats
                    if last_coords is None or last_coords[i] != px or last_coords[i+1] != py:
                        for dx, dy in [(0, -1), (0, 1), (-1, 0), (1, 0)]:
                            opp_heads.add((px + dx, py + dy))
                            
        # Save state to track frozen players next round
        last_coords = coords[:]
        
        my_x, my_y = coords[0], coords[1]
        moves = {
            "u": (my_x, my_y - 1),
            "d": (my_x, my_y + 1),
            "l": (my_x - 1, my_y),
            "r": (my_x + 1, my_y)
        }
        
        valid_moves = []
        
        for move_name, (nx, ny) in moves.items():
            score_tuple = evaluate_move(nx, ny, opp_heads)
            # score_tuple[0] == -1 means instant death/wall
            if score_tuple[0] != -1: 
                valid_moves.append((score_tuple, move_name))
        
        if valid_moves:
            # Sort by our advanced priority tuple
            valid_moves.sort(key=lambda x: x[0], reverse=True)
            best_score = valid_moves[0][0]
            best_options = [m for score, m in valid_moves if score == best_score]
            best_move = random.choice(best_options)
        else:
            # Complete trap (Death inevitable)
            best_move = random.choice(["u", "d", "l", "r"])
            
        print(best_move)
        sys.stdout.flush()
        
    except EOFError:
        break
    except Exception as e:
        print(random.choice(["u", "d", "l", "r"]))
        sys.stdout.flush()