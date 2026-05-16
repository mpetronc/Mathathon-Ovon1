import sys
import time
import random
from collections import deque
from typing import List, Tuple, Optional

# --- Game Constants ---
GRID_SIZE = 32
TIME_LIMIT_SEC = 0.40  # 400ms cutoff ensures we never hit 500ms
MOVES = [
    ("u", 0, -1),
    ("d", 0, 1),
    ("l", -1, 0),
    ("r", 1, 0),
]

# --- Global State ---
original_grid = [1] * (GRID_SIZE * GRID_SIZE)
claimed_grid = bytearray(GRID_SIZE * GRID_SIZE)

def get_jump_distance(x: int, y: int, dx: int, dy: int) -> int:
    """Retrieves jump distance strictly adhering to game rules."""
    nx, ny = x + dx, y + dy
    if not (0 <= nx < GRID_SIZE and 0 <= ny < GRID_SIZE):
        return 1
    return original_grid[ny * GRID_SIZE + nx]

def simulate_jump(x: int, y: int, dx: int, dy: int, state: bytearray) -> Optional[Tuple[int, int, List[int]]]:
    """
    Simulates jump physics cleanly.
    Returns (final_x, final_y, list_of_claimed_1d_indices) or None if lethal.
    """
    dist = get_jump_distance(x, y, dx, dy)
    path = []
    cx, cy = x, y
    
    for _ in range(dist):
        cx += dx
        cy += dy
        
        if not (0 <= cx < GRID_SIZE and 0 <= cy < GRID_SIZE):
            return None  # Wall
            
        idx = cy * GRID_SIZE + cx
        if state[idx]:
            return None  # Claimed cell
            
        path.append(idx)
        
    return cx, cy, path

def calculate_jump_voronoi(my_x: int, my_y: int, en_x: int, en_y: int, current_state: bytearray) -> float:
    """
    Dual-BFS to calculate reachable territory using exact jump mechanics.
    Returns: (My Territory Volume) - (Enemy Territory Volume)
    """
    my_q = deque([(my_x, my_y)])
    en_q = deque([(en_x, en_y)])
    
    visited = bytearray(current_state)
    visited[my_y * GRID_SIZE + my_x] = 1
    visited[en_y * GRID_SIZE + en_x] = 1
    
    my_score = 0
    en_score = 0
    
    # Expand level by level to approximate fair simultaneous reach
    while my_q or en_q:
        # My Expansion
        for _ in range(len(my_q)):
            cx, cy = my_q.popleft()
            for _, dx, dy in MOVES:
                sim = simulate_jump(cx, cy, dx, dy, visited)
                if sim:
                    nx, ny, path = sim
                    for idx in path: visited[idx] = 1
                    my_score += len(path)
                    my_q.append((nx, ny))
                    
        # Enemy Expansion
        for _ in range(len(en_q)):
            cx, cy = en_q.popleft()
            for _, dx, dy in MOVES:
                sim = simulate_jump(cx, cy, dx, dy, visited)
                if sim:
                    nx, ny, path = sim
                    for idx in path: visited[idx] = 1
                    en_score += len(path)
                    en_q.append((nx, ny))

    # If the enemy has 0 reach but we have space, heavily reward this state
    if en_score == 0 and my_score > 0:
        return 10000.0 + my_score
        
    return float(my_score - en_score)

def get_best_move(my_x: int, my_y: int, en_x: int, en_y: int, en_dead: bool) -> str:
    """Uses a Maximin Matrix to handle simultaneous evaluation."""
    start_time = time.time()
    
    my_moves = []
    for move_id, dx, dy in MOVES:
        sim = simulate_jump(my_x, my_y, dx, dy, claimed_grid)
        if sim: my_moves.append((move_id, dx, dy, sim))
        
    en_moves = []
    if not en_dead:
        for move_id, dx, dy in MOVES:
            sim = simulate_jump(en_x, en_y, dx, dy, claimed_grid)
            if sim: en_moves.append((move_id, dx, dy, sim))

    if not my_moves: return "u"  # Inevitable death
    if len(my_moves) == 1 and en_dead: return my_moves[0][0]
    
    # If enemy is dead, maximize immediate safe volume 
    # (Voronoi vs nothing = maximize our score)
    if en_dead or not en_moves:
        my_moves.sort(key=lambda m: len(m[3][2]), reverse=True)
        return my_moves[0][0]

    best_move = my_moves[0][0]
    best_worst_case_score = -float('inf')

    # Construct Simultaneous Matrix
    random.shuffle(my_moves) # Prevent deterministic looping
    
    for my_id, _, _, (my_nx, my_ny, my_path) in my_moves:
        worst_case_response_score = float('inf')
        
        for en_id, _, _, (en_nx, en_ny, en_path) in en_moves:
            
            # 1. Check for Simultaneous Step Collision (Both die)
            step_collision = False
            min_steps = min(len(my_path), len(en_path))
            for i in range(min_steps):
                if my_path[i] == en_path[i]:
                    step_collision = True
                    break
                    
            # 2. Check for Cross-Path Collision
            # Did I land on a line they just drew, or vice versa?
            my_final_idx = my_ny * GRID_SIZE + my_nx
            en_final_idx = en_ny * GRID_SIZE + en_nx
            
            i_die = my_final_idx in en_path
            they_die = en_final_idx in my_path
            
            if step_collision:
                score = -50000.0  # Avoid mutual destruction unless losing
            elif i_die and they_die:
                score = -50000.0
            elif i_die:
                score = -100000.0
            elif they_die:
                score = 100000.0
            else:
                # Both survived this ply. Apply state and run Voronoi.
                temp_state = bytearray(claimed_grid)
                for idx in my_path: temp_state[idx] = 1
                for idx in en_path: temp_state[idx] = 1
                
                # Time safety check
                if time.time() - start_time > TIME_LIMIT_SEC:
                    break
                    
                score = calculate_jump_voronoi(my_nx, my_ny, en_nx, en_ny, temp_state)
                
            if score < worst_case_response_score:
                worst_case_response_score = score
                
        if worst_case_response_score > best_worst_case_score:
            best_worst_case_score = worst_case_response_score
            best_move = my_id

    return best_move

def fill_line(x1: int, y1: int, x2: int, y2: int) -> None:
    if x1 == x2:
        for y in range(min(y1, y2), max(y1, y2) + 1):
            claimed_grid[y * GRID_SIZE + x1] = 1
    elif y1 == y2:
        for x in range(min(x1, x2), max(x1, x2) + 1):
            claimed_grid[y1 * GRID_SIZE + x] = 1

def main():
    try:
        grid_digits = input().strip().replace(" ", "")
        for i in range(GRID_SIZE * GRID_SIZE):
            original_grid[i] = int(grid_digits[i])

        my_pos = None
        en_pos = None
        en_dead = False

        while True:
            line = input().strip()
            if not line: continue
            
            positions = [int(n) for n in line.split()]
            my_x, my_y = positions[0:2]
            en_x, en_y = positions[2:4]

            if my_pos is None:
                claimed_grid[my_y * GRID_SIZE + my_x] = 1
                claimed_grid[en_y * GRID_SIZE + en_x] = 1
            else:
                if en_pos == (en_x, en_y):
                    en_dead = True
                fill_line(my_pos[0], my_pos[1], my_x, my_y)
                fill_line(en_pos[0], en_pos[1], en_x, en_y)

            my_pos = (my_x, my_y)
            en_pos = (en_x, en_y)

            move = get_best_move(my_x, my_y, en_x, en_y, en_dead)
            
            print(move)
            sys.stdout.flush()
            
    except EOFError:
        pass

if __name__ == "__main__":
    main()