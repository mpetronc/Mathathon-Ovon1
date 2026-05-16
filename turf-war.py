import sys
import random
from collections import deque
from typing import List, Tuple, Dict

BOARD_SIZE = 31

# Constants for clarity
EMPTY = -1
ME = 0

MOVES = [
    ("u", 0, -1),
    ("d", 0, 1),
    ("l", -1, 0),
    ("r", 1, 0),
]

def is_inside(x: int, y: int) -> bool:
    """Validates if coordinates are strictly within the board boundaries."""
    return 0 <= x < BOARD_SIZE and 0 <= y < BOARD_SIZE

def get_reachable_area(start_x: int, start_y: int, board: List[List[int]]) -> int:
    """Standard BFS to find total absolute contiguous empty space."""
    if not is_inside(start_x, start_y) or board[start_y][start_x] != EMPTY:
        return 0
        
    queue = deque([(start_x, start_y)])
    visited = {(start_x, start_y)}
    
    while queue:
        cx, cy = queue.popleft()
        for _, dx, dy in MOVES:
            nx, ny = cx + dx, cy + dy
            if is_inside(nx, ny) and board[ny][nx] == EMPTY and (nx, ny) not in visited:
                visited.add((nx, ny))
                queue.append((nx, ny))
                
    return len(visited)

def get_future_reachable_area(candidate_x: int, candidate_y: int, board: List[List[int]]) -> int:
    """
    stRWategy core mechanic: Simulates stepping onto the candidate cell.
    If this step splits our territory in half, this function will return a much 
    lower number, preventing us from locking ourselves out of our own space.
    """
    # Simulate moving here
    board[candidate_y][candidate_x] = ME
    
    max_reach = 0
    # Check what our best possible path is *after* this move
    for _, dx, dy in MOVES:
        nx, ny = candidate_x + dx, candidate_y + dy
        if is_inside(nx, ny) and board[ny][nx] == EMPTY:
            reach = get_reachable_area(nx, ny, board)
            if reach > max_reach:
                max_reach = reach
                
    # Backtrack simulation
    board[candidate_y][candidate_x] = EMPTY
    return max_reach

def get_voronoi_area(my_nx: int, my_ny: int, active_enemies: List[Tuple[int, int]], board: List[List[int]]) -> int:
    """Multi-source BFS to calculate strictly exclusive territory against active threats."""
    if not active_enemies:
        return 0 # If isolated/endgame, Voronoi doesn't matter.

    queue = deque()
    distances: Dict[Tuple[int, int], int] = {}
    owner: Dict[Tuple[int, int], int] = {}
    
    # 1. Seed our candidate future state
    queue.append(((my_nx, my_ny), ME, 0))
    distances[(my_nx, my_ny)] = 0
    owner[(my_nx, my_ny)] = ME
    
    # 2. Seed active enemy current states
    for idx, (ex, ey) in enumerate(active_enemies):
        pid = idx + 1
        queue.append(((ex, ey), pid, 0))
        distances[(ex, ey)] = 0
        owner[(ex, ey)] = pid

    # 3. Flood the board
    while queue:
        (cx, cy), pid, dist = queue.popleft()
        
        for _, dx, dy in MOVES:
            nx, ny = cx + dx, cy + dy
            if is_inside(nx, ny) and board[ny][nx] == EMPTY:
                state = (nx, ny)
                if state not in distances:
                    distances[state] = dist + 1
                    owner[state] = pid
                    queue.append((state, pid, dist + 1))
                elif distances[state] == dist + 1:
                    if owner[state] != pid:
                        owner[state] = -2  # Contested
                        
    return sum(1 for v in owner.values() if v == ME)

def count_wall_touches(x: int, y: int, board: List[List[int]]) -> int:
    """
    Homogenization heuristic: Hugs walls to force tight space packing.
    """
    touches = 0
    for dx in [-1, 0, 1]:
        for dy in [-1, 0, 1]:
            if dx == 0 and dy == 0:
                continue
            nx, ny = x + dx, y + dy
            if not is_inside(nx, ny) or board[ny][nx] != EMPTY:
                touches += 1
    return touches

def main():
    board = [[EMPTY for _ in range(BOARD_SIZE)] for _ in range(BOARD_SIZE)]
    last_positions = [None] * 4
    is_alive = [True] * 4

    while True:
        try:
            line = input()
        except EOFError:
            break
            
        if not line.strip():
            continue

        positions = [int(n) for n in line.split()]
        curr_positions = [positions[i : i + 2] for i in range(0, 8, 2)]

        # --- State Update & Ghost Tracking ---
        active_enemies = []
        for i, (x, y) in enumerate(curr_positions):
            if not is_inside(x, y):
                is_alive[i] = False
            elif last_positions[i] == (x, y):
                is_alive[i] = False
                
            if is_alive[i]:
                if board[y][x] == EMPTY:
                    board[y][x] = i
                elif board[y][x] != i:
                    is_alive[i] = False
                
                if is_alive[i] and i != ME:
                    active_enemies.append((x, y))
                    
            last_positions[i] = (x, y)

        my_x, my_y = curr_positions[0]
        
        if not is_alive[ME] or not is_inside(my_x, my_y):
            print("u", flush=True)
            continue

        # --- Threat Categorization ---
        safe_moves = []
        risky_moves = []

        for move, dx, dy in MOVES:
            nx, ny = my_x + dx, my_y + dy
            
            if is_inside(nx, ny) and board[ny][nx] == EMPTY:
                is_risky = any(abs(nx - ex) + abs(ny - ey) <= 1 for ex, ey in active_enemies)
                
                if is_risky:
                    risky_moves.append((move, nx, ny))
                else:
                    safe_moves.append((move, nx, ny))

        # --- Move Evaluation ---
        moves_to_evaluate = safe_moves if safe_moves else risky_moves
        
        best_moves = []
        best_score = None 

        for move, nx, ny in moves_to_evaluate:
            # stRWategy metric: How much space is left AFTER we step here?
            future_reach = get_future_reachable_area(nx, ny, board)
            voronoi = get_voronoi_area(nx, ny, active_enemies, board)
            touches = count_wall_touches(nx, ny, board)
            
            # The scoring hierarchy:
            # 1. future_reach: Strictly prevents cutting our own rooms in half.
            # 2. voronoi: Expands our territory aggressively against others.
            # 3. touches: Hugs edges for perfect endgame packing.
            score = (future_reach, voronoi, touches)
            
            if best_score is None or score > best_score:
                best_score = score
                best_moves = [move]
            elif score == best_score:
                best_moves.append(move)

        # --- Execution ---
        if best_moves:
            print(random.choice(best_moves), flush=True)
        else:
            print("u", flush=True)

if __name__ == "__main__":
    main()