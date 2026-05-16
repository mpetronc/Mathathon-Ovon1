import sys
from collections import deque

BOARD_SIZE = 31

# board[y][x] is -1 for empty, 0 for me, and 1..3 for opponents
board = [[-1 for x in range(BOARD_SIZE)] for y in range(BOARD_SIZE)]

MOVES = [
    ("u", 0, -1),
    ("d", 0, 1),
    ("l", -1, 0),
    ("r", 1, 0),
]

def is_inside(x, y):
    return 0 <= x < BOARD_SIZE and 0 <= y < BOARD_SIZE

def get_open_neighbors(x, y, board_state):
    """Counts empty adjacent cells to enforce wall-hugging (Warnsdorff's rule)"""
    count = 0
    for _, dx, dy in MOVES:
        nx, ny = x + dx, y + dy
        if is_inside(nx, ny) and board_state[ny][nx] == -1:
            count += 1
    return count

def voronoi_area(my_nx, my_ny, active_enemies, board_state):
    """
    Multi-source BFS to calculate territory we are guaranteed to reach first.
    Enemies are given a slight algorithmic priority to simulate pessimistic (safe) ties.
    """
    queue = deque()
    visited = {}
    
    # Enqueue active enemies first
    for ex, ey in active_enemies:
        queue.append((ex, ey, 1, 0)) # (x, y, player_id, distance)
        visited[(ex, ey)] = (1, 0)
        
    # Enqueue our evaluated next position
    if (my_nx, my_ny) not in visited:
        queue.append((my_nx, my_ny, 0, 1))
        visited[(my_nx, my_ny)] = (0, 1)
    else:
        return 0 # Collides with an enemy head
        
    my_claimed_area = 0
    
    while queue:
        cx, cy, pid, dist = queue.popleft()
        
        if pid == 0:
            my_claimed_area += 1
            
        for _, dx, dy in MOVES:
            nnx, nny = cx + dx, cy + dy
            if is_inside(nnx, nny) and board_state[nny][nnx] == -1:
                # If unvisited, claim it for whoever reached it first
                if (nnx, nny) not in visited:
                    visited[(nnx, nny)] = (pid, dist + 1)
                    queue.append((nnx, nny, pid, dist + 1))
                    
    return my_claimed_area

# Game Loop
last_player_positions = []

while True:
    try:
        line = input()
    except EOFError:
        break
    if not line:
        continue
        
    positions = [int(n) for n in line.split()]
    if len(positions) != 8:
        continue
        
    player_positions = [positions[i : i + 2] for i in range(0, 8, 2)]

    # Update board with the current positions
    for player_id, (x, y) in enumerate(player_positions):
        if is_inside(x, y):
            board[y][x] = player_id

    my_x, my_y = player_positions[0]
    
    # Filter active enemies (Ignore dead enemies so they don't skew the Voronoi map)
    active_enemies = []
    for i in range(1, 4):
        ex, ey = player_positions[i]
        if is_inside(ex, ey):
            if last_player_positions:
                lex, ley = last_player_positions[i]
                if ex == lex and ey == ley:
                    continue # Enemy hasn't moved, they are dead
            active_enemies.append((ex, ey))
            
    last_player_positions = player_positions

    # Gather safe standard moves
    safe_moves = []
    for move, dx, dy in MOVES:
        next_x = my_x + dx
        next_y = my_y + dy
        if is_inside(next_x, next_y) and board[next_y][next_x] == -1:
            safe_moves.append((move, next_x, next_y))

    # Fallback to avoid crashes if completely trapped
    if not safe_moves:
        print(MOVES[0][0])
        sys.stdout.flush()
        continue

    best_move = None
    best_score = (-1, -10) 

    # Evaluate each safe move
    for move, nx, ny in safe_moves:
        area = voronoi_area(nx, ny, active_enemies, board)
        
        # Check for immediate head-to-head collision risk
        is_risky = False
        for ex, ey in active_enemies:
            if abs(ex - nx) + abs(ey - ny) == 1:
                is_risky = True
                break
                
        # If it's a 50/50 risk, halve the perceived area value
        expected_area = area if not is_risky else area // 2
        
        # Tie-breaker: prefer tighter spaces / hug walls
        open_n = get_open_neighbors(nx, ny, board)
        
        # Build hierarchy score
        score = (expected_area, -open_n)
        
        if best_move is None or score > best_score:
            best_score = score
            best_move = move

    # Fallback output
    if best_move is None:
        best_move = safe_moves[0][0]

    print(best_move)
    sys.stdout.flush()