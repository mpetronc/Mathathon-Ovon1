import sys
import time
import random
from typing import List, Tuple, Optional

# Constants mapped to game rules
GRID_SIZE = 32
TIME_LIMIT_SEC = 0.40  # 400ms cutoff ensures we never hit the 500ms timeout
MOVES = [
    ("u", 0, -1),
    ("d", 0, 1),
    ("l", -1, 0),
    ("r", 1, 0),
]

# 1D arrays for maximum memory locality and fast copy/undo operations
original_grid = [0] * (GRID_SIZE * GRID_SIZE)
claimed_grid = bytearray(GRID_SIZE * GRID_SIZE)

def get_move_outcome(x: int, y: int, dx: int, dy: int) -> Optional[Tuple[int, int, List[Tuple[int, int]]]]:
    """
    Simulates the full D-step trajectory of a given move.
    Returns the final coordinates and a list of cells traversed, or None if the move is lethal.
    """
    adj_x, adj_y = x + dx, y + dy
    
    # "If the adjacent cell is outside the grid, the movement distance is 1."
    if not (0 <= adj_x < GRID_SIZE and 0 <= adj_y < GRID_SIZE):
        dist = 1
    else:
        dist = original_grid[adj_y * GRID_SIZE + adj_x]

    cells = []
    curr_x, curr_y = x, y
    
    for _ in range(dist):
        curr_x += dx
        curr_y += dy
        
        # Out of bounds check
        if not (0 <= curr_x < GRID_SIZE and 0 <= curr_y < GRID_SIZE):
            return None
            
        # Collision with claimed cell check
        if claimed_grid[curr_y * GRID_SIZE + curr_x]:
            return None
            
        cells.append((curr_x, curr_y))
        
    return curr_x, curr_y, cells

def fill_line(x1: int, y1: int, x2: int, y2: int) -> None:
    """Updates the claimed_grid based on a player's movement line."""
    if x1 == x2:
        for y in range(min(y1, y2), max(y1, y2) + 1):
            claimed_grid[y * GRID_SIZE + x1] = 1
    elif y1 == y2:
        for x in range(min(x1, x2), max(x1, x2) + 1):
            claimed_grid[y1 * GRID_SIZE + x] = 1

def dfs(x: int, y: int, current_depth: int, max_depth: int, current_score: int, start_time: float) -> int:
    """
    Recursive depth-first search to evaluate path viability.
    Scoring hierarchy: Survival Depth > Score > Open Space
    """
    if time.time() - start_time > TIME_LIMIT_SEC:
        raise TimeoutError()

    if current_depth == max_depth:
        # Leaf node evaluation: Count immediate open paths to favor wide-open spaces over corridors
        valid_count = sum(1 for _, dx, dy in MOVES if get_move_outcome(x, y, dx, dy) is not None)
        return (current_depth * 1000000) + (current_score * 1000) + valid_count

    max_score = -float('inf')
    moved = False

    for _, dx, dy in MOVES:
        outcome = get_move_outcome(x, y, dx, dy)
        if outcome:
            nx, ny, cells = outcome
            moved = True
            
            # Apply state mutation
            for cx, cy in cells:
                claimed_grid[cy * GRID_SIZE + cx] = 1

            # Recurse deeper
            score = dfs(nx, ny, current_depth + 1, max_depth, current_score + len(cells), start_time)
            if score > max_score:
                max_score = score

            # Revert state mutation (Backtrack)
            for cx, cy in cells:
                claimed_grid[cy * GRID_SIZE + cx] = 0

    if not moved:
        # Path results in death at `current_depth`
        return (current_depth * 1000000) + (current_score * 1000)

    return int(max_score)

def get_best_move(my_x: int, my_y: int, enemy_x: int, enemy_y: int) -> str:
    start_time = time.time()
    
    valid_moves = []
    for move_id, dx, dy in MOVES:
        outcome = get_move_outcome(my_x, my_y, dx, dy)
        if outcome:
            valid_moves.append((move_id, dx, dy, outcome))

    if not valid_moves:
        return "u" # Inevitable death; send arbitrary valid format

    # If only one move prevents immediate death, take it without burning CPU time
    if len(valid_moves) == 1:
        return valid_moves[0][0]

    # Calculate opponent's immediate danger zones to avoid head-to-head collisions
    enemy_danger_zones = set()
    for _, dx, dy in MOVES:
        e_outcome = get_move_outcome(enemy_x, enemy_y, dx, dy)
        if e_outcome:
            _, _, e_cells = e_outcome
            for cx, cy in e_cells:
                enemy_danger_zones.add((cx, cy))

    best_overall_move = valid_moves[0][0]
    
    try:
        # Iterative Deepening: Search deeper until timeout
        for max_depth in range(1, 50): 
            best_depth_move = None
            best_depth_score = -float('inf')

            # Shuffle to prevent deterministic looping behavior in symmetrical maps
            random.shuffle(valid_moves)

            for move_id, dx, dy, outcome in valid_moves:
                nx, ny, cells = outcome

                # Check if this move intercepts a space the opponent can claim this turn
                is_dangerous = any((cx, cy) in enemy_danger_zones for cx, cy in cells)
                danger_penalty = 5000000 if is_dangerous else 0

                # Apply
                for cx, cy in cells:
                    claimed_grid[cy * GRID_SIZE + cx] = 1

                move_score = dfs(nx, ny, 1, max_depth, len(cells), start_time) - danger_penalty

                # Undo
                for cx, cy in cells:
                    claimed_grid[cy * GRID_SIZE + cx] = 0

                if move_score > best_depth_score:
                    best_depth_score = move_score
                    best_depth_move = move_id

            best_overall_move = best_depth_move

    except TimeoutError:
        # Time limit reached, fallback to the best move found in the fully completed previous depth layer
        pass

    return best_overall_move

def main():
    # Initialize Game State (Round 0)
    grid_digits = input().strip().replace(" ", "")
    for i in range(GRID_SIZE * GRID_SIZE):
        original_grid[i] = int(grid_digits[i])

    my_pos = None
    enemy_pos = None

    for round_i in range(999999):
        # Input: my_x my_y opponent_x opponent_y
        received_positions = [int(n) for n in input().strip().split()]
        my_x, my_y = received_positions[0:2]
        enemy_x, enemy_y = received_positions[2:4]

        # Register Starting Setup
        if my_pos is None or enemy_pos is None:
            claimed_grid[my_y * GRID_SIZE + my_x] = 1
            claimed_grid[enemy_y * GRID_SIZE + enemy_x] = 1
        else:
            # Update dynamic grid state with recent lines drawn by both players
            fill_line(my_pos[0], my_pos[1], my_x, my_y)
            fill_line(enemy_pos[0], enemy_pos[1], enemy_x, enemy_y)

        my_pos = (my_x, my_y)
        enemy_pos = (enemy_x, enemy_y)

        # Compute and dispatch optimal move
        move = get_best_move(my_x, my_y, enemy_x, enemy_y)
        
        print(move)
        sys.stdout.flush() 

if __name__ == "__main__":
    main()