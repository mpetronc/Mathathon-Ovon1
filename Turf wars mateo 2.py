import sys
import random
from collections import deque

BOARD_SIZE = 31
N = BOARD_SIZE
NN = N * N
EMPTY = -1
INF = 10**9

MOVES = [
    ("u", 0, -1),
    ("d", 0, 1),
    ("l", -1, 0),
    ("r", 1, 0),
]

# Flat board: board[y * 31 + x]
# -1 = empty, 0 = us, 1..3 = opponents
board = [EMPTY] * NN

# Claimed-cell counts, relative to our input ordering.
counts = [0, 0, 0, 0]

last_positions = None
turn = 0

# Precomputed neighbors for speed.
NEIGHBORS = [[] for _ in range(NN)]
for y in range(N):
    for x in range(N):
        i = y * N + x
        for move, dx, dy in MOVES:
            nx, ny = x + dx, y + dy
            if 0 <= nx < N and 0 <= ny < N:
                NEIGHBORS[i].append((move, ny * N + nx))


def idx(x, y):
    return y * N + x


def xy(i):
    return i % N, i // N


def inside(x, y):
    return 0 <= x < N and 0 <= y < N


def tournament_points_estimate():
    """
    Pessimistic ranking:
    points = number of opponents with fewer cells than us.

    Examples:
    - We are strictly first: 3 opponents below us -> 3 points
    - We are strictly second: 2 opponents below us -> 2 points
    - We are strictly third: 1 opponent below us -> 1 point
    - We are last or tied-last: 0 points
    """
    our_cells = counts[0]
    return sum(1 for c in counts[1:] if our_cells > c)


def get_active_enemies(current_positions):
    """
    Dead players stop moving, so if an enemy's position is unchanged,
    we treat them as dead and stop giving them Voronoi pressure.
    """
    global last_positions

    enemies = []

    if last_positions is None:
        for i in range(1, 4):
            x, y = current_positions[i]
            if inside(x, y):
                enemies.append((x, y))
        return enemies

    for i in range(1, 4):
        x, y = current_positions[i]
        old_x, old_y = last_positions[i]

        if not inside(x, y):
            continue

        if x == old_x and y == old_y:
            continue

        enemies.append((x, y))

    return enemies


def enemy_distance_map(active_enemies):
    """
    Multi-source BFS from all living enemies.
    dist[cell] = how quickly the closest enemy can reach that cell.
    """
    dist = [INF] * NN
    q = deque()

    for ex, ey in active_enemies:
        if inside(ex, ey):
            ei = idx(ex, ey)
            dist[ei] = 0
            q.append(ei)

    while q:
        cur = q.popleft()
        nd = dist[cur] + 1

        for _, ni in NEIGHBORS[cur]:
            if dist[ni] != INF:
                continue

            if board[ni] != EMPTY:
                continue

            dist[ni] = nd
            q.append(ni)

    return dist


def expected_cells_from(start_i, enemy_dist, risk_level):
    """
    Estimate expected cells if we move to start_i.

    Cells we reach before enemies are worth 1.
    Cells reached at the same time are contested:
      - if ahead, value them less
      - if behind/tied, value them more
    """
    q = deque([start_i])
    my_dist = {start_i: 0}

    guaranteed = 0
    contested = 0
    reachable = 0
    frontier = 0

    while q:
        cur = q.popleft()
        d_me = my_dist[cur]
        d_enemy = enemy_dist[cur]

        reachable += 1

        if d_me < d_enemy:
            guaranteed += 1
        elif d_me == d_enemy:
            contested += 1

        # Frontier cells matter against other expected-cell bots.
        if d_enemy <= d_me + 2:
            frontier += 1

        for _, ni in NEIGHBORS[cur]:
            if board[ni] != EMPTY:
                continue

            if ni in my_dist:
                continue

            my_dist[ni] = d_me + 1
            q.append(ni)

    if risk_level == 0:
        # Already top-2: prefer guaranteed cells, avoid uncertain frontier.
        return guaranteed * 100 + contested * 15 + reachable * 2 - frontier * 12

    if risk_level == 1:
        # Middle: balanced territory maximization.
        return guaranteed * 100 + contested * 35 + reachable * 3 + frontier * 5

    # Behind or tied: contested cells are valuable because we need to break rank.
    return guaranteed * 100 + contested * 65 + reachable * 3 + frontier * 14


def degree(cell):
    """
    Number of empty exits after moving to this cell.
    Used to avoid self-trapping.
    """
    c = 0
    for _, ni in NEIGHBORS[cell]:
        if board[ni] == EMPTY:
            c += 1
    return c


def second_degree(cell):
    """
    Small local lookahead.
    """
    total = 0
    for _, ni in NEIGHBORS[cell]:
        if board[ni] == EMPTY:
            total += degree(ni)
    return total


def enemy_next_cells(active_enemies):
    """
    Cells enemies could enter next turn.
    Moving into these risks simultaneous collision.
    """
    danger = set()

    for ex, ey in active_enemies:
        ei = idx(ex, ey)
        for _, ni in NEIGHBORS[ei]:
            if board[ni] == EMPTY:
                danger.add(ni)

    return danger


def choose_move(current_positions):
    my_x, my_y = current_positions[0]
    my_i = idx(my_x, my_y)

    active_enemies = get_active_enemies(current_positions)
    enemy_next = enemy_next_cells(active_enemies)
    enemy_dist = enemy_distance_map(active_enemies)

    legal_moves = []

    for move, ni in NEIGHBORS[my_i]:
        if board[ni] == EMPTY:
            legal_moves.append((move, ni))

    if not legal_moves:
        return "u"

    our_cells = counts[0]
    points_now = tournament_points_estimate()

    tied_with_someone = any(c == our_cells for c in counts[1:])

    if active_enemies:
        nearest_enemy = min(
            abs(my_x - ex) + abs(my_y - ey)
            for ex, ey in active_enemies
        )
    else:
        nearest_enemy = 99

    # Tournament risk level:
    # 0 = protect top-2
    # 1 = normal
    # 2 = behind/tied, push harder
    if points_now >= 2:
        risk_level = 0
    elif points_now == 1:
        risk_level = 1
    else:
        risk_level = 2

    # Pessimistic ties are bad, so break them.
    if tied_with_someone and turn > 30:
        risk_level = min(2, risk_level + 1)

    # If enemies are very close, reduce risk.
    if nearest_enemy <= 3:
        risk_level = max(0, risk_level - 1)

    best_score = -10**18
    best_moves = []

    for move, ni in legal_moves:
        nx, ny = xy(ni)

        score = 0

        # Main expected-cell calculation.
        score += expected_cells_from(ni, enemy_dist, risk_level)

        # Self-trap avoidance.
        d1 = degree(ni)
        d2 = second_degree(ni)

        score += d1 * 550
        score += d2 * 70

        if d1 == 0:
            # Early death is terrible in accumulated scoring.
            score -= 90000 if our_cells < 230 else 20000

        # Collision danger.
        if ni in enemy_next:
            if risk_level == 0:
                score -= 250000
            elif risk_level == 1:
                score -= 150000
            else:
                score -= 80000

        # Enemy distance shaping.
        if active_enemies:
            dist_to_enemy = min(
                abs(nx - ex) + abs(ny - ey)
                for ex, ey in active_enemies
            )

            if dist_to_enemy == 1:
                score -= 7000 if risk_level < 2 else 3000
            elif dist_to_enemy == 2:
                score -= 2500 if risk_level < 2 else 900
            else:
                score += min(dist_to_enemy, 7) * (45 if risk_level == 0 else 20)

        # Center / frontier pressure.
        center_dist = abs(nx - 15) + abs(ny - 15)

        if risk_level == 0:
            # Already getting good points: do not overgamble.
            score -= center_dist * 2
        elif risk_level == 1:
            # Normal expansion.
            score -= center_dist * 8
        else:
            # Behind/tied: claim differentiating center territory.
            score -= center_dist * 18

        # Extra tie-breaking pressure.
        if tied_with_someone and turn > 30:
            score -= center_dist * 8

        # Tiny randomness so we are not perfectly predictable.
        score += random.random()

        if score > best_score:
            best_score = score
            best_moves = [move]
        elif abs(score - best_score) < 10:
            best_moves.append(move)

    return random.choice(best_moves)


while True:
    line = sys.stdin.readline()

    if not line:
        break

    parts = line.split()

    if len(parts) != 8:
        continue

    nums = list(map(int, parts))

    current_positions = [
        (nums[0], nums[1]),
        (nums[2], nums[3]),
        (nums[4], nums[5]),
        (nums[6], nums[7]),
    ]

    # Update board and claimed counts.
    for player_id, (x, y) in enumerate(current_positions):
        if inside(x, y):
            cell = idx(x, y)

            if board[cell] == EMPTY:
                board[cell] = player_id
                counts[player_id] += 1

    move = choose_move(current_positions)

    print(move, flush=True)

    last_positions = current_positions
    turn += 1
