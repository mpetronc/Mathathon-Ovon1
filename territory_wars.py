import sys
import random
from collections import deque
from typing import List, Tuple, Dict, Set

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
    """
    Standard BFS to find total absolute contiguous empty space available from a node.
    Critical for ensuring we do not walk into a completely sealed coffin, 
    even if Voronoi says we "own" it.
    """
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

def get_voronoi_area(my_nx: int, my_ny: int, active_enemies: List[Tuple[int, int]], board: List[List[int]]) -> int:
    """
    Multi-source BFS to calculate strictly exclusive territory.
    It identifies exactly how many cells we can reach before any active enemy can.
    """
    queue = deque()
    distances: Dict[Tuple[int, int], int] = {}
    owner: Dict[Tuple[int, int], int] = {}
    
    # 1. Seed our candidate future state
    queue.append(((my_nx, my_ny), ME, 0)) # (pos), player_id, distance
    distances[(my_nx, my_ny)] = 0
    owner[(my_nx, my_ny)] = ME
    
    # 2. Seed active enemy current states
    for idx, (ex, ey) in enumerate(active_enemies):
        pid = idx + 1 # Use 1, 2, 3 as generic enemy IDs for the BFS
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
                    # Cell reached simultaneously by multiple players. It is contested, not safe.
                    if owner[state] != pid:
                        owner[state] = -2 

    # Count cells strictly owned by us
    return sum(1 for v in owner.values() if v == ME)

def count_wall_touches(x: int, y: int, board: List[List[int]]) -> int:
    """
    Homogenization heuristic: Checks all 8 adjacent neighbors for walls/trails.
    Forces the bot to hug edges and pack tightly to prevent bisecting its own territory.
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
    # Persistent state tracking across rounds
    board = [[EMPTY for _ in range(BOARD_SIZE)] for _ in range(BOARD_SIZE)]
    last_positions = [None] * 4
    is_alive = [True] * 4

    while True:
        try:
            line = input()
        except EOFError:
            # Game engine closed the stream. Terminate cleanly.
            break
            
        if not line.strip():
            continue

        positions = [int(n) for n in line.split()]
        curr_positions = [positions[i : i + 2] for i in range(0, 8, 2)]

        # --- 1. State Update & Ghost Tracking ---
        active_enemies = []
        for i, (x, y) in enumerate(curr_positions):
            if not is_inside(x, y):
                is_alive[i] = False
            elif last_positions[i] == (x, y):
                # Ghost tracking: If coordinates didn't change, the player is dead.
                # We flag them dead so we stop generating Voronoi avoidance fields around them.
                is_alive[i] = False
                
            if is_alive[i]:
                # Mark the trail permanently
                if board[y][x] == EMPTY:
                    board[y][x] = i
                elif board[y][x] != i:
                    # An active player just crashed into a wall or tail. Mark them dead.
                    is_alive[i] = False
                
                # Only push living enemies to the active threat list
                if is_alive[i] and i != ME:
                    active_enemies.append((x, y))
                    
            last_positions[i] = (x, y)

        my_x, my_y = curr_positions[0]
        
        # If we are somehow dead but the engine still demands input
        if not is_alive[ME] or not is_inside(my_x, my_y):
            print("u", flush=True)
            continue

        # --- 2. Threat Categorization ---
        safe_moves = []
        risky_moves = []

        for move, dx, dy in MOVES:
            nx, ny = my_x + dx, my_y + dy
            
            if is_inside(nx, ny) and board[ny][nx] == EMPTY:
                # A move is risky if an enemy can step into it simultaneously (Manhattan distance <= 1)
                is_risky = any(abs(nx - ex) + abs(ny - ey) <= 1 for ex, ey in active_enemies)
                
                if is_risky:
                    risky_moves.append((move, nx, ny))
                else:
                    safe_moves.append((move, nx, ny))

        # --- 3. Mathematical Move Evaluation ---
        # Prioritize moves that cannot result in a head-on collision.
        moves_to_evaluate = safe_moves if safe_moves else risky_moves
        
        best_moves = []
        best_score = None # Tuple: (Reachable, Voronoi, Wall Touches)

        for move, nx, ny in moves_to_evaluate:
            reachable = get_reachable_area(nx, ny, board)
            voronoi = get_voronoi_area(nx, ny, active_enemies, board)
            touches = count_wall_touches(nx, ny, board)
            
            # The scoring hierarchy:
            # 1. Absolute survival space (prevents locking ourselves in a small box)
            # 2. Exclusive Voronoi territory (pushes the frontline aggressively)
            # 3. Wall touches (hugs the edges to pack space efficiently)
            score = (reachable, voronoi, touches)
            
            if best_score is None or score > best_score:
                best_score = score
                best_moves = [move]
            elif score == best_score:
                # Retain ties to break them randomly later (prevents predictable looping)
                best_moves.append(move)

        # --- 4. Execution ---
        if best_moves:
            print(random.choice(best_moves), flush=True)
        else:
            # Fatal state: Total entrapment. Accept death gracefully.
            print("u", flush=True)

if __name__ == "__main__":
    main()