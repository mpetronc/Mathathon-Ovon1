import sys
import random

GRID_SIZE = 32
MAX_DEPTH = 5
FLOOD_FILL_LIMIT = 150

def debug_print(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)

# 1. Parse initial grid
grid_digits = input().strip().replace(" ", "")
grid = [
    [int(grid_digits[i * GRID_SIZE + j]) for j in range(GRID_SIZE)]
    for i in range(GRID_SIZE)
]

my_pos = None
enemy_pos = None
enemy_dead = False

possible_moves = [
    ("u", (0, -1)),
    ("d", (0, 1)),
    ("l", (-1, 0)),
    ("r", (1, 0)),
]

def fill_line(from_pos, to_pos, value):
    """Draws an orthogonal line between two points to claim cells."""
    (x1, y1), (x2, y2) = from_pos, to_pos
    assert x1 == x2 or y1 == y2
    if x1 == x2:
        for y in range(min(y1, y2), max(y1, y2) + 1):
            grid[y][x1] = value
    elif y1 == y2:
        for x in range(min(x1, x2), max(x1, x2) + 1):
            grid[y1][x] = value

def simulate_move(x, y, dx, dy):
    """Simulates a move and returns the destination, distance, and full path taken."""
    nx = x + dx
    ny = y + dy
    
    # If adjacent cell is outside grid, distance is 1 (immediate death by moving outside)
    if not (0 <= nx < GRID_SIZE and 0 <= ny < GRID_SIZE):
        return None
        
    dist = grid[ny][nx]
    if dist <= 0:
        return None

    path = []
    # Verify every step of the jump
    for step in range(1, dist + 1):
        cx = x + dx * step
        cy = y + dy * step
        
        # Check out of bounds
        if not (0 <= cx < GRID_SIZE and 0 <= cy < GRID_SIZE):
            return None
            
        # Check collision with claimed cells
        if grid[cy][cx] <= 0:
            return None
            
        path.append((cx, cy))
        
    return (cx, cy), dist, path

def flood_fill(x, y, max_count=FLOOD_FILL_LIMIT):
    """Evaluates how much 'open area' is accessible from a given cell."""
    visited = {(x, y)}
    queue = [(x, y)]
    count = 0
    
    while queue and count < max_count:
        cx, cy = queue.pop(0)
        count += 1
        for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
            nx, ny = cx + dx, cy + dy
            if 0 <= nx < GRID_SIZE and 0 <= ny < GRID_SIZE:
                if grid[ny][nx] > 0 and (nx, ny) not in visited:
                    visited.add((nx, ny))
                    queue.append((nx, ny))
    return count

def search(x, y, depth):
    """Recursive DFS to find the longest survival path."""
    if depth == 0:
        return flood_fill(x, y)

    best_score = 0
    for move_id, (dx, dy) in possible_moves:
        sim = simulate_move(x, y, dx, dy)
        if not sim:
            continue
            
        (nx, ny), dist, path = sim

        # Apply move locally
        modified = []
        for cx, cy in path:
            modified.append((cx, cy, grid[cy][cx]))
            grid[cy][cx] = 0

        score = dist + search(nx, ny, depth - 1)

        # Undo move to backtrack
        for cx, cy, old_val in modified:
            grid[cy][cx] = old_val

        if score > best_score:
            best_score = score

    return best_score

def get_enemy_threats():
    """Generates all cells the enemy could potentially claim on their next turn."""
    threats = set()
    if enemy_dead:
        return threats
        
    for move_id, (dx, dy) in possible_moves:
        sim = simulate_move(enemy_pos[0], enemy_pos[1], dx, dy)
        if sim:
            _, _, path = sim
            threats.update(path)
    return threats

# Game loop
for round_i in range(999999):
    try:
        line = input().strip()
        if not line:
            continue
        received_positions = [int(n) for n in line.split()]
    except EOFError:
        break

    new_my_pos = tuple(received_positions[0:2])
    new_enemy_pos = tuple(received_positions[2:4])

    # 2. Update state trackers
    if my_pos is None:
        my_pos = new_my_pos
        enemy_pos = new_enemy_pos
    else:
        # If the opponent's position hasn't changed, they died
        if enemy_pos == new_enemy_pos:
            enemy_dead = True

    # Claim cells
    fill_line(my_pos, new_my_pos, 0)
    fill_line(enemy_pos, new_enemy_pos, -1)

    my_pos = new_my_pos
    enemy_pos = new_enemy_pos

    # 3. Calculate Strategy
    threats = get_enemy_threats()
    random.shuffle(possible_moves) # Randomize to prevent directional bias

    best_move = None
    best_score = -1
    fallback_move = None
    fallback_score = -1

    for move_id, (dx, dy) in possible_moves:
        sim = simulate_move(my_pos[0], my_pos[1], dx, dy)
        if not sim:
            continue

        (nx, ny), dist, path = sim
        intersects_threat = any(cell in threats for cell in path)

        # Apply move temporarily to search forward
        modified = []
        for cx, cy in path:
            modified.append((cx, cy, grid[cy][cx]))
            grid[cy][cx] = 0

        score = dist + search(nx, ny, MAX_DEPTH - 1)

        # Backtrack
        for cx, cy, old_val in modified:
            grid[cy][cx] = old_val

        # Separate safe moves from potentially fatal collisions
        if intersects_threat:
            if score > fallback_score:
                fallback_score = score
                fallback_move = move_id
        else:
            if score > best_score:
                best_score = score
                best_move = move_id

    # Fallback to a risky move if no fully safe moves exist, else pick any valid move
    final_move = best_move if best_move is not None else fallback_move
    
    if final_move is None:
        final_move = "u"  # Doomed fallback, accept fate

    print(final_move, flush=True)