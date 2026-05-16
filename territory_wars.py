import random
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
    return abs(x1 - x2) + abs(y1 - y2)


def evaluate_candidate_move(candidate_x: int, candidate_y: int, active_opponents: List[Tuple[int, Tuple[int, int]]]) -> Tuple[int, int]:
    """
    Simulates a move using multi-source Asymmetrical BFS to calculate Voronoi partitions.
    Returns: (my_guaranteed_territory_size, wall_adjacency_score)
    """
    visited = [[None for _ in range(BOARD_SIZE)] for _ in range(BOARD_SIZE)]
    queue = deque()
    
    # 1. Initialize BFS
    visited[candidate_y][candidate_x] = (0, 0)
    queue.append((candidate_x, candidate_y, 0, 0))
    
    for opp_id, (ox, oy) in active_opponents:
        visited[oy][ox] = (opp_id, 0)
        queue.append((ox, oy, opp_id, 0))
        
    my_territory = 0
    
    while queue:
        cx, cy, pid, dist = queue.popleft()
        
        # We only score points for claiming -1 cells
        if pid == 0 and board[cy][cx] == -1:
            my_territory += 1
            
        for _, dx, dy in MOVES:
            nx, ny = cx + dx, cy + dy
            if is_inside(nx, ny):
                # Asymmetrical traversal: players can walk on empty AND their OWN trail.
                if pid == 0 and board[ny][nx] not in (-1, 0): continue
                if pid != 0 and board[ny][nx] not in (-1, pid): continue
                
                if visited[ny][nx] is None:
                    visited[ny][nx] = (pid, dist + 1)
                    queue.append((nx, ny, pid, dist + 1))
                    
    # 2. Homogenization heuristic: Prefer paths that pack tightly
    wall_touches = 0
    for dx, dy in [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]:
        nx, ny = candidate_x + dx, candidate_y + dy
        # Our own trail counts as a wall for packing purposes to keep territory uniform
        if not is_inside(nx, ny) or board[ny][nx] != -1:
            wall_touches += 1
            
    return my_territory, wall_touches


def get_best_transit_move(my_x: int, my_y: int) -> str:
    """
    BFS to find the shortest path through our own trail (0) to the nearest empty cell (-1).
    Prevents the bot from getting trapped inside its own closed pockets.
    """
    queue = deque()
    visited = set([(my_x, my_y)])
    
    # Start BFS in all valid transit directions
    for move, dx, dy in MOVES:
        nx, ny = my_x + dx, my_y + dy
        if is_inside(nx, ny) and board[ny][nx] == 0:
            queue.append((nx, ny, move))
            visited.add((nx, ny))
            
    while queue:
        cx, cy, first_move = queue.popleft()
        
        for _, dx, dy in MOVES:
            nx, ny = cx + dx, cy + dy
            if is_inside(nx, ny):
                if board[ny][nx] == -1:
                    return first_move  # Found the exit, return the move that gets us there
                if board[ny][nx] == 0 and (nx, ny) not in visited:
                    visited.add((nx, ny))
                    queue.append((nx, ny, first_move))
    return None


def main():
    while True:
        try:
            line = input()
            if not line: break
        except EOFError: break
            
        positions = [int(n) for n in line.split()]
        player_positions = [positions[i : i + 2] for i in range(0, 8, 2)]

        active_opponents = []
        
        for player_id, (x, y) in enumerate(player_positions):
            if is_inside(x, y):
                board[y][x] = player_id
                if player_id != 0:
                    active_opponents.append((player_id, (x, y)))

        my_x, my_y = player_positions[0]
        
        if not is_inside(my_x, my_y):
            print("u", flush=True)
            continue

        safe_expansions = []
        risky_expansions = []
        survival_moves = []

        for move, dx, dy in MOVES:
            nx = my_x + dx
            ny = my_y + dy
            
            if is_inside(nx, ny):
                cell_state = board[ny][nx]
                
                if cell_state == -1:
                    # A move is risky if an active opponent can step into it this exact turn
                    is_risky = any(get_manhattan_distance(nx, ny, ox, oy) <= 1 for _, (ox, oy) in active_opponents)
                    if is_risky:
                        risky_expansions.append((move, nx, ny))
                    else:
                        safe_expansions.append((move, nx, ny))
                elif cell_state == 0:
                    survival_moves.append(move)

        # Decision Engine
        if safe_expansions or risky_expansions:
            # We are bordering unclaimed territory. Evaluate to find optimal Voronoi + Homogenization cut.
            moves_to_evaluate = safe_expansions if safe_expansions else risky_expansions
            best_move = moves_to_evaluate[0][0]
            best_score = (-1, -1) 
            
            for move, nx, ny in moves_to_evaluate:
                score = evaluate_candidate_move(nx, ny, active_opponents)
                if score > best_score:
                    best_score = score
                    best_move = move
            print(best_move, flush=True)
            
        elif survival_moves:
            # We are inside our own territory. Navigate out to the nearest free point.
            transit_move = get_best_transit_move(my_x, my_y)
            if transit_move:
                print(transit_move, flush=True)
            else:
                # 100% of the board is claimed. Pace to stay alive until R512.
                print(random.choice(survival_moves), flush=True)
                
        else:
            # Complete entrapment by enemies
            print("u", flush=True)

if __name__ == "__main__":
    main()