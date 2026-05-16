import sys

N = 31
NN = N * N
EMPTY = -1
ME = 0

MOVES = [
    ("u", 0, -1),
    ("d", 0, 1),
    ("l", -1, 0),
    ("r", 1, 0),
]

board = [EMPTY] * NN
counts = [0, 0, 0, 0]

last_positions = None
turn = 0

NEI = [[] for _ in range(NN)]
NEI8 = [[] for _ in range(NN)]

for y in range(N):
    for x in range(N):
        i = y * N + x

        for m, dx, dy in MOVES:
            nx, ny = x + dx, y + dy
            if 0 <= nx < N and 0 <= ny < N:
                NEI[i].append((m, ny * N + nx))

        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                if dx == 0 and dy == 0:
                    continue
                nx, ny = x + dx, y + dy
                if 0 <= nx < N and 0 <= ny < N:
                    NEI8[i].append(ny * N + nx)
                else:
                    NEI8[i].append(-1)


def idx(x, y):
    return y * N + x


def xy(i):
    return i % N, i // N


def inside(x, y):
    return 0 <= x < N and 0 <= y < N


def passable_for_us(cell):
    return board[cell] == EMPTY or board[cell] == ME


def passable_for_player(cell, pid):
    return board[cell] == EMPTY or board[cell] == pid


def active_enemies(positions):
    if last_positions is None:
        enemies = []
        for pid in range(1, 4):
            x, y = positions[pid]
            if inside(x, y):
                enemies.append((pid, x, y))
        return enemies

    enemies = []

    for pid in range(1, 4):
        x, y = positions[pid]
        ox, oy = last_positions[pid]

        if not inside(x, y):
            continue

        # If position did not change, assume dead.
        if x == ox and y == oy:
            continue

        enemies.append((pid, x, y))

    return enemies


def enemy_next_cells(enemies):
    danger = set()

    for pid, x, y in enemies:
        cur = idx(x, y)

        for _, ni in NEI[cur]:
            if passable_for_player(ni, pid):
                danger.add(ni)

    return danger


def estimated_points():
    our = counts[ME]
    return sum(1 for c in counts[1:] if our > c)


def mobility(cell):
    c = 0

    for _, ni in NEI[cell]:
        if passable_for_us(ni):
            c += 1

    return c


def local_empty_count(cell):
    c = 0

    for _, ni in NEI[cell]:
        if board[ni] == EMPTY:
            c += 1

    return c


def local_own_count(cell):
    c = 0

    for _, ni in NEI[cell]:
        if board[ni] == ME:
            c += 1

    return c


def wall_touches(cell):
    c = 0

    for ni in NEI8[cell]:
        if ni == -1 or board[ni] != EMPTY:
            c += 1

    return c


def route_to_nearest_empty(me, danger):
    """
    Rare fallback:
    if all adjacent moves are own paint, use our territory as roads
    and move toward the nearest empty cell.

    This is the only BFS, and it is not used every turn.
    """
    seen = [False] * NN
    q = []
    head = 0

    seen[me] = True

    for move, ni in NEI[me]:
        if not passable_for_us(ni):
            continue
        if ni in danger:
            continue

        if board[ni] == EMPTY:
            return move

        seen[ni] = True
        q.append((ni, move))

    while head < len(q):
        cur, first_move = q[head]
        head += 1

        for _, ni in NEI[cur]:
            if seen[ni]:
                continue
            if not passable_for_us(ni):
                continue

            if board[ni] == EMPTY and ni not in danger:
                return first_move

            seen[ni] = True
            q.append((ni, first_move))

    return None


def choose_move(positions):
    mx, my = positions[0]
    me = idx(mx, my)

    enemies = active_enemies(positions)
    danger = enemy_next_cells(enemies)

    legal = []
    safe = []
    safe_empty_exists = False

    for move, ni in NEI[me]:
        if passable_for_us(ni):
            legal.append((move, ni))

            if ni not in danger:
                safe.append((move, ni))
                if board[ni] == EMPTY:
                    safe_empty_exists = True

    if not legal:
        return "u"

    candidates = safe if safe else legal

    # If we have no safe adjacent empty cell, use our own paint as a road.
    if not safe_empty_exists:
        routed = route_to_nearest_empty(me, danger)
        if routed is not None:
            return routed

    points = estimated_points()
    our_cells = counts[ME]
    tied = any(c == our_cells for c in counts[1:])

    if points >= 2:
        risk = 0
    elif points == 1:
        risk = 1
    else:
        risk = 2

    if tied and turn > 70:
        risk = min(2, risk + 1)

    best_score = -10**9
    best_move = candidates[0][0]

    for move, ni in candidates:
        nx, ny = xy(ni)

        is_new = board[ni] == EMPTY

        score = 0

        # New territory is valuable, but own-paint movement is allowed.
        if is_new:
            score += 5000
        else:
            score -= 1200

        # Prefer positions that open more future empty cells.
        empty_adj = local_empty_count(ni)
        own_adj = local_own_count(ni)
        mob = mobility(ni)
        touches = wall_touches(ni)

        score += empty_adj * 900
        score += mob * 500
        score += own_adj * 120
        score += touches * 15

        # Avoid simultaneous collision cells.
        if ni in danger:
            if risk == 0:
                score -= 200000
            elif risk == 1:
                score -= 130000
            else:
                score -= 80000

        # Enemy distance shaping.
        if enemies:
            nearest = 99
            for _, ex, ey in enemies:
                d = abs(nx - ex) + abs(ny - ey)
                if d < nearest:
                    nearest = d

            if nearest == 1:
                score -= 10000
            elif nearest == 2:
                score -= 3000
            else:
                score += min(nearest, 7) * 25

        # Early: do not sprint center.
        center_dist = abs(nx - 15) + abs(ny - 15)

        if turn < 70:
            score += center_dist * 2
        elif turn < 180:
            if risk == 2:
                score -= center_dist * 2
        else:
            if risk == 0:
                score -= center_dist
            elif risk == 1:
                score -= center_dist * 3
            else:
                score -= center_dist * 6

        # Deterministic tiny tie-breaker.
        score += (turn % 5)

        if score > best_score:
            best_score = score
            best_move = move

    return best_move


while True:
    line = sys.stdin.readline()

    if not line:
        break

    parts = line.split()
    if len(parts) != 8:
        continue

    nums = list(map(int, parts))

    positions = [
        (nums[0], nums[1]),
        (nums[2], nums[3]),
        (nums[4], nums[5]),
        (nums[6], nums[7]),
    ]

    # Update board and counts.
    for pid, (x, y) in enumerate(positions):
        if inside(x, y):
            cell = idx(x, y)

            if board[cell] == EMPTY:
                board[cell] = pid
                counts[pid] += 1

    move = choose_move(positions)

    sys.stdout.write(move + "\n")
    sys.stdout.flush()

    last_positions = positions
    turn += 1
