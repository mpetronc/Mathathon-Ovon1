import sys
import time
import random
from collections import deque
from typing import List, Tuple, Optional, Dict

# Game Constants
GRID_SIZE = 32
TIME_LIMIT_SEC = 0.40  # 400ms to guarantee we avoid the 500ms execution timeout
MOVES = [
    ("u", 0, -1),
    ("d", 0, 1),
    ("l", -1, 0),
    ("r", 1, 0),
]

# 1D arrays for maximum cache locality and execution speed.
original_grid = [0] * (GRID_SIZE * GRID_SIZE)
claimed_grid = bytearray(GRID_SIZE * GRID_SIZE)

def get_jump_distance(x: int, y: int, dx: int, dy: int) -> int:
    """Calculates the jump distance based on the adjacent cell's value."""
    adj_x, adj_y = x + dx, y + dy
    if not (0 <= adj_x < GRID_SIZE and 0 <= adj_y < GRID_SIZE):
        return 1
    return original_grid[adj_y * GRID_SIZE + adj_x]

def simulate_move(x: int, y: int, dx: int, dy: int, current_claimed: bytearray) -> Optional[Tuple[int, int, List[int]]]:
    """
    Simulates a move without mutating global state.
    Returns (new_x, new_y, list_of_1d_indices_claimed) or None if lethal.
    """
    dist = get_jump_distance(x, y, dx, dy)
    
    indices = []
    curr_x, curr_y = x, y
    
    for _ in range(dist):
        curr_x += dx
        curr_y += dy
        
        # OOB Check
        if not (0 <= curr_x < GRID_SIZE and 0 <= curr_y < GRID_SIZE):
            return None
            
        idx = curr_y * GRID_SIZE + curr_x
        # Collision Check
        if current_claimed[idx]:
            return None
            
        indices.append(idx)
        
    return curr_x, curr_y, indices

def fast_bfs_territory(start_x: int, start_y: int, current_claimed: bytearray) -> int:
    """
    Calculates an approximation of reachable space (Voronoi region volume).
    Uses a standard BFS queue but simulates the line-drawing jump mechanics.
    """
    visited = bytearray(GRID_SIZE * GRID_SIZE)
    start_idx = start_y * GRID_SIZE + start_x
    visited[start_idx] = 1
    
    queue = deque([(start_x, start_y)])
    volume = 0
    
    while queue:
        cx, cy = queue.popleft()
        
        for _, dx, dy in MOVES:
            outcome = simulate_move(cx, cy, dx, dy, current_claimed)
            if outcome:
                nx, ny, path_indices = outcome
                n_idx = ny * GRID_SIZE + nx
                
                if not visited[n_idx]:
                    visited[n_idx] = 1
                    # Add the volume of the space we just jumped through
                    volume += len(path_indices)
                    queue.append((nx, ny))
                    
    return volume

def evaluate_state(my_x: int, my_y: int, enemy_x: int, enemy_y: int, current_claimed: bytearray) -> float:
    """
    Evaluates the board state. 
    Positive score = We control more territory.
    Negative score = Opponent controls more territory.
    """
    my_reach = fast_bfs_territory(my_x, my_y, current_claimed)
    enemy_reach = fast_bfs_territory(enemy_x, enemy_y, current_claimed)
    
    # If the enemy is completely trapped (0 reach), assign infinite score.
    if enemy_reach == 0 and my_reach > 0:
        return 1000000.0
    
    return float(my_reach - enemy_reach)

def get_best_move(my_x: int, my_y: int, enemy_x: int, enemy_y: int) -> str:
    """
    Uses Game Theory (Maximin) on a depth-1 simultaneous payoff matrix.
    """
    start_time = time.time()
    
    # Pre-calculate valid immediate moves to prune tree
    my_valid_moves = []
    for move_id, dx, dy in MOVES:
        out = simulate_move(my_x, my_y, dx, dy, claimed_grid)
        if out: my_valid_moves.append((move_id, dx, dy, out))
        
    enemy_valid_moves = []
    for move_id, dx, dy in MOVES:
        out = simulate_move(enemy_x, enemy_y, dx, dy, claimed_grid)
        if out: enemy_valid_moves.append((move_id, dx, dy, out))

    # Tactical failure handling
    if not my_valid_moves:
        return "u" # We are dead no matter what.

    if not enemy_valid_moves:
        # Enemy is dead, just pick our longest immediate jump to farm points safely.
        my_valid_moves.sort(key=lambda m: len(m[3][2]), reverse=True)
        return my_valid_moves[0][0]

    best_move = my_valid_moves[0][0]
    best_maximin_score = -float('inf')

    # Construct the Payoff Matrix
    for my_move_id, my_dx, my_dy, my_out in my_valid_moves:
        my_nx, my_ny, my_indices = my_out
        
        worst_case_response_score = float('inf')
        
        for e_move_id, e_dx, e_dy, e_out in enemy_valid_moves:
            e_nx, e_ny, e_indices = e_out
            
            # Rule: "If both players enter the same cell during the same movement step, both die"
            # We calculate step-by-step collision.
            step_collision = False
            min_steps = min(len(my_indices), len(e_indices))
            for i in range(min_steps):
                if my_indices[i] == e_indices[i]:
                    step_collision = True
                    break
            
            # Cross-path collision (one player crosses a line the other just drew)
            # Apply temporary state mutation
            temp_claimed = bytearray(claimed_grid)
            for idx in my_indices: temp_claimed[idx] = 1
            for idx in e_indices: temp_claimed[idx] = 1
            
            if step_collision:
                # Both die. We only want this if we are losing terribly, otherwise avoid.
                score = -500000.0
            else:
                # Check if we landed on a cell the enemy just claimed (or vice versa)
                if my_ny * GRID_SIZE + my_nx in e_indices:
                    score = -1000000.0 # We die
                elif e_ny * GRID_SIZE + e_nx in my_indices:
                    score = 1000000.0  # Enemy dies
                else:
                    # Both survived this turn, evaluate territory
                    # Time check to prevent timeouts mid-matrix
                    if time.time() - start_time > TIME_LIMIT_SEC:
                        break 
                    score = evaluate_state(my_nx, my_ny, e_nx, e_ny, temp_claimed)
            
            # The opponent wants to minimize our score.
            if score < worst_case_response_score:
                worst_case_response_score = score
                
        # We want to maximize our score in the worst-case scenario.
        if worst_case_response_score > best_maximin_score:
            best_maximin_score = worst_case_response_score
            best_move = my_move_id

    return best_move

def fill_line(x1: int, y1: int, x2: int, y2: int) -> None:
    """Updates the claimed_grid based on a player's movement line."""
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
        enemy_pos = None

        # Game Loop
        for round_i in range(999999):
            received_positions = [int(n) for n in input().strip().split()]
            my_x, my_y = received_positions[0:2]
            enemy_x, enemy_y = received_positions[2:4]

            if my_pos is None or enemy_pos is None:
                claimed_grid[my_y * GRID_SIZE + my_x] = 1
                claimed_grid[enemy_y * GRID_SIZE + enemy_x] = 1
            else:
                fill_line(my_pos[0], my_pos[1], my_x, my_y)
                fill_line(enemy_pos[0], enemy_pos[1], enemy_x, enemy_y)

            my_pos = (my_x, my_y)
            enemy_pos = (enemy_x, enemy_y)

            move = get_best_move(my_x, my_y, enemy_x, enemy_y)
            
            print(move)
            sys.stdout.flush() 
            
    except EOFError:
        # Graceful exit when the engine stops sending inputs (Game Over)
        pass

if __name__ == "__main__":
    main()