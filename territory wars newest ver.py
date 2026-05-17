import sys
from collections import deque

W = H = 31
SIZE = W * H

EMPTY = -1
OWN = 0
ENEMY = 1

DIRS = (
    ("u", 0, -1),
    ("d", 0, 1),
    ("l", -1, 0),
    ("r", 1, 0),
)

DELTA = {
    "u": (0, -1),
    "d": (0, 1),
    "l": (-1, 0),
    "r": (1, 0),
}

OPPOSITE = {
    "u": "d",
    "d": "u",
    "l": "r",
    "r": "l",
}

board = [EMPTY] * SIZE
threat = [0] * SIZE
last_seen = [-999999] * SIZE

turn = 0
last_coords = None
last_move = None


def idx(x, y):
    return y * W + x


def inside(x, y):
    return 0 <= x < W and 0 <= y < H


def safe_on(b, x, y):
    return inside(x, y) and b[idx(x, y)] != ENEMY


def count_exits(b, x, y):
    c = 0

    for _, dx, dy in DIRS:
        nx = x + dx
        ny = y + dy

        if safe_on(b, nx, ny):
            c += 1

    return c


def empty_neighbors(b, x, y):
    c = 0

    for _, dx, dy in DIRS:
        nx = x + dx
        ny = y + dy

        if inside(nx, ny) and b[idx(nx, ny)] == EMPTY:
            c += 1

    return c


def line_empty_score(b, x, y, dx, dy):
    """
    Looks forward in the movement direction.
    Empty cells are good.
    Own cells are neutral.
    Enemy cells stop the line.
    """
    score = 0
    cx = x
    cy = y

    for step in range(1, 7):
        cx += dx
        cy += dy

        if not inside(cx, cy):
            break

        cell = b[idx(cx, cy)]

        if cell == ENEMY:
            break

        if cell == EMPTY:
            score += 7 - step

    return score


def flood_empty_area(b, sx, sy):
    """
    Standard flood-fill:
    count how many empty cells are reachable from this position,
    moving through empty or own cells but not enemy cells.
    """
    if not safe_on(b, sx, sy):
        return 0

    seen = bytearray(SIZE)
    q = deque()

    start = idx(sx, sy)
    seen[start] = 1
    q.append((sx, sy))

    area = 0

    while q:
        x, y = q.popleft()

        if b[idx(x, y)] == EMPTY:
            area += 1

        for _, dx, dy in DIRS:
            nx = x + dx
            ny = y + dy

            if not inside(nx, ny):
                continue

            ni = idx(nx, ny)

            if seen[ni]:
                continue

            if b[ni] == ENEMY:
                continue

            seen[ni] = 1
            q.append((nx, ny))

    return area


def score_move(my_x, my_y, move, dx, dy, threat_mark):
    nx = my_x + dx
    ny = my_y + dy

    if not safe_on(board, nx, ny):
        return -10**15

    ni = idx(nx, ny)
    cell = board[ni]

    # Simulate claiming the target cell.
    temp = board[:]
    temp[ni] = OWN

    area = flood_empty_area(temp, nx, ny)
    exits = count_exits(temp, nx, ny)
    frontier = empty_neighbors(temp, nx, ny)
    line = line_empty_score(temp, nx, ny, dx, dy)

    score = 0

    # Claiming new cells matters most.
    if cell == EMPTY:
        score += 10000
    else:
        # Own cells are safe repositioning, not horrible.
        score += 50

        age = turn - last_seen[ni]

        # Tiny anti-oscillation penalty only.
        if age < 3:
            score -= 400
        elif age < 8:
            score -= 120

    # Standard flood-fill space control.
    score += area * 70

    # Mobility matters.
    score += exits * 900

    if exits == 0:
        score -= 100000
    elif exits == 1:
        score -= 5000

    # Prefer borders of empty territory.
    score += frontier * 900
    score += line * 500

    # Enemy head threat.
    # Not too harsh, because sometimes contested empty cells are still worth it.
    if cell != OWN and threat[ni] == threat_mark:
        score -= 8000

    # Momentum: avoid jitter, but do not force it.
    if last_move is not None:
        if move == last_move:
            score += 600
        elif move == OPPOSITE[last_move]:
            score -= 900
        else:
            score += 100

    # Edges are not automatically bad in this game.
    edge = nx == 0 or nx == W - 1 or ny == 0 or ny == H - 1

    if edge:
        if exits >= 2:
            score += 120
        else:
            score -= 500

    # Deterministic tie-break.
    score += (nx * 17 + ny * 31 + turn * 7) % 13

    return score


def choose_move(my_x, my_y, threat_mark):
    best_move = None
    best_score = -10**15

    for move, dx, dy in DIRS:
        s = score_move(my_x, my_y, move, dx, dy, threat_mark)

        if s > best_score:
            best_score = s
            best_move = move

    if best_move is not None:
        return best_move

    # Fallback: any safe move.
    for move, dx, dy in DIRS:
        nx = my_x + dx
        ny = my_y + dy

        if safe_on(board, nx, ny):
            return move

    # Last resort: any in-board move.
    for move, dx, dy in DIRS:
        nx = my_x + dx
        ny = my_y + dy

        if inside(nx, ny):
            return move

    return "u"


for line in sys.stdin:
    parts = line.split()

    if not parts:
        continue

    vals = []

    for p in parts:
        try:
            vals.append(int(p))
        except ValueError:
            pass

    if len(vals) < 8:
        continue

    coords = vals[-8:]

    my_x = coords[0]
    my_y = coords[1]

    # Update board memory.
    for i in range(0, 8, 2):
        px = coords[i]
        py = coords[i + 1]
        pid = i // 2

        if not inside(px, py):
            continue

        pi = idx(px, py)

        if pid == 0:
            board[pi] = OWN
            last_seen[pi] = turn
        else:
            if board[pi] != OWN:
                board[pi] = ENEMY

    # Build enemy threat map.
    threat_mark = turn + 1

    for i in (2, 4, 6):
        ex = coords[i]
        ey = coords[i + 1]

        if not inside(ex, ey):
            continue

        alive = True

        if last_coords is not None:
            alive = coords[i] != last_coords[i] or coords[i + 1] != last_coords[i + 1]

        if not alive:
            continue

        for _, dx, dy in DIRS:
            tx = ex + dx
            ty = ey + dy

            if inside(tx, ty):
                threat[idx(tx, ty)] = threat_mark

    move = choose_move(my_x, my_y, threat_mark)

    sys.stdout.write(move + "\n")
    sys.stdout.flush()

    last_coords = coords[:]
    last_move = move
    turn += 1
