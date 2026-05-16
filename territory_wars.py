import sys
from collections import deque
from typing import List, Tuple

BOARD_SIZE = 31

# board[y][x] tracks permanent territory. -1 for empty, 0 for me, 1..3 for opponents.
board = [[-1 for _ in range(BOARD_SIZE)] for _ in range(BOARD_SIZE)]

MOVES = [
    ("u", 0, -1),
    ("d", 0, 1),
    ("l", -1, 0),
    ("r", 1, 0),
]


def is_inside(x: int, y: int) -> bool:
    """Validates if coordinates are strictly within the board boundaries."""
    return 0 <= x < BOARD_SIZE and 0 <= y < BOARD_SIZE


def get_manhattan_distance(x1: int, y1: int, x2: int, y2: int) -> int:
    """Standard L1 distance metric for grid geometry."""
    return abs(x1 - x2) + abs(y1 - y2)


def evaluate_candidate_move(candidate_x: int, candidate_y: int, active_opponents: List[Tuple[int, Tuple[int, int]]]) -> Tuple[int, int]:
    """
    Simulates a move using multi-source BFS to calculate Voronoi partitions.
    Returns: (my_guaranteed_territory_size, wall_adjacency_score)
    """
    visited = [[-1 for _ in range(BOARD_SIZE)] for _ in range(BOARD_SIZE)]
    queue = deque()
    
    # 1. Initialize BFS with our candidate future state
    visited[candidate_y][candidate_x] = 0
    queue.append((candidate_x, candidate_y, 0, 0))  # x, y, player_id, distance
    
    # 2. Initialize BFS with active opponent current states
    for opp_id, (ox, oy) in active_opponents:
        visited[oy][ox] = opp_id
        queue.append((ox, oy, opp_id, 0))
            
    my_territory = 0
    
    # 3. Flood the board to calculate nearest-neighbor ownership
    while queue:
        cx, cy, pid, dist = queue.popleft()
        
        if pid == 0:
            my_territory += 1
            
        for _, dx, dy in MOVES:
            nx, ny = cx + dx, cy + dy
            if is_inside(nx, ny) and board[ny][nx] == -1 and visited[ny][nx] == -1:
                visited[ny][nx] = pid
                queue.append((nx, ny, pid, dist + 1))
                
    # 4. Homogenization heuristic: Prefer paths that hug existing walls
    wall_touches = 0
    for dx, dy in [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]:
        nx, ny = candidate_x + dx, candidate_y + dy
        if not is_inside(nx, ny) or board[ny][nx] != -1:
            wall_touches += 1
            
    return my_territory, wall_touches


# --- Main Game Loop ---
def main():
    while True:
        try:
            line = input()
            if not line:
                break
        except EOFError:
            break
            
        positions = [int(n) for n in line.split()]
        player_positions = [positions[i : i + 2] for i in range(0, 8, 2)]

        active_opponents = []
        
        # Parse state: Update permanent trails and identify living enemies
        for player_id, (x, y) in enumerate(player_positions):
            if is_inside(x, y):
                board[y][x] = player_id
                if player_id != 0:
                    active_opponents.append((player_id, (x, y)))

        my_x, my_y = player_positions[0]
        
        # Death check: If engine sends invalid coordinates for us, output fallback and continue
        if not is_inside(my_x, my_y):
            print("u", flush=True)
            continue

        safe_moves = []
        risky_moves = []

        # Tier 1 Filtering: Categorize legal moves
        for move, dx, dy in MOVES:
            nx = my_x + dx
            ny = my_y + dy
            
            if is_inside(nx, ny) and board[ny][nx] == -1:
                is_risky = False
                # A move is risky if an active opponent can step into it this exact turn (mutual death)
                for _, (ox, oy) in active_opponents:
                    if get_manhattan_distance(nx, ny, ox, oy) <= 1:
                        is_risky = True
                        break
                
                if is_risky:
                    risky_moves.append((move, nx, ny))
                else:
                    safe_moves.append((move, nx, ny))

        # Tier 2 Selection: Evaluate the best move mathematically
        best_move = "u"
        best_score = (-1, -1) 
        
        # Evaluate 100% safe moves first
        moves_to_evaluate = safe_moves if safe_moves else risky_moves

        for move, nx, ny in moves_to_evaluate:
            score = evaluate_candidate_move(nx, ny, active_opponents)
            if score > best_score:
                best_score = score
                best_move = move

        # Execute
        if best_score[0] != -1:
            print(best_move, flush=True)
        else:
            # Complete entrapment: default to "u" to accept execution gracefully
            print("u", flush=True)

if __name__ == "__main__":
    main()