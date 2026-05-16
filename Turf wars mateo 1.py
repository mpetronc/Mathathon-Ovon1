import sys
import random
from collections import deque

N = 31

DIRS = [
    ("u", (0, -1)),
    ("d", (0, 1)),
    ("l", (-1, 0)),
    ("r", (1, 0)),
]

claimed = set()
prev_positions = None
turn = 0
home_path = None
path_index = {}

def inside(x, y):
    return 0 <= x < N and 0 <= y < N

def neighbors(pos):
    x, y = pos
    for ch, (dx, dy) in DIRS:
        yield ch, (x + dx, y + dy)

def make_home_path(start):
    sx, sy = start

    # Template path for top-left 15x15 quadrant.
    # Other corners are reflections of this.
    path = []

    for yy in range(15):
        if yy % 2 == 0:
            xs = range(15)
        else:
            xs = range(14, -1, -1)

        for xx in xs:
            x = xx if sx == 0 else N - 1 - xx
            y = yy if sy == 0 else N - 1 - yy
            path.append((x, y))

    return path

def move_char(a, b):
    ax, ay = a
    bx, by = b
    if bx == ax and by == ay - 1:
        return "u"
    if bx == ax and by == ay + 1:
        return "d"
    if bx == ax - 1 and by == ay:
        return "l"
    if bx == ax + 1 and by == ay:
        return "r"
    return None

def flood_area(start, blocked):
    # Estimate how much unclaimed space is reachable after moving to start.
    q = deque([start])
    seen = {start}

    while q:
        p = q.popleft()
        for _, np in neighbors(p):
            if not inside(*np):
                continue
            if np in blocked:
                continue
            if np in seen:
                continue
            seen.add(np)
            q.append(np)

    return len(seen)

def onward_moves(pos, blocked):
    count = 0
    for _, np in neighbors(pos):
        if inside(*np) and np not in blocked:
            count += 1
    return count

def choose_move(positions):
    global home_path, path_index, turn

    me = positions[0]
    enemies = positions[1:]

    if home_path is None:
        home_path = make_home_path(me)
        path_index = {p: i for i, p in enumerate(home_path)}

    # Detect likely alive enemies.
    # Alive players must move every turn; repeated coordinates usually mean dead.
    alive_enemies = []
    if prev_positions is None:
        alive_enemies = enemies[:]
    else:
        for i, e in enumerate(enemies, start=1):
            if e != prev_positions[i]:
                alive_enemies.append(e)

    # Cells enemies could move into next turn.
    enemy_next = set()
    for e in alive_enemies:
        for _, np in neighbors(e):
            if inside(*np) and np not in claimed:
                enemy_next.add(np)

    legal = []
    for ch, np in neighbors(me):
        if inside(*np) and np not in claimed:
            legal.append((ch, np))

    if not legal:
        # Death is unavoidable, but still output something valid.
        return "u"

    safe_legal = [(ch, np) for ch, np in legal if np not in enemy_next]
    usable = safe_legal if safe_legal else legal

    # First follow the safe quadrant snake if possible.
    if me in path_index:
        idx = path_index[me]
        if idx + 1 < len(home_path):
            nxt = home_path[idx + 1]
            ch = move_char(me, nxt)
            if ch is not None:
                for legal_ch, legal_np in usable:
                    if legal_np == nxt:
                        return legal_ch

    # Fallback: choose move with best future space.
    scored = []

    for ch, np in usable:
        blocked = set(claimed)
        blocked.add(np)

        area = flood_area(np, blocked)
        onward = onward_moves(np, blocked)

        # Prefer the center slightly after the safe opening.
        cx, cy = 15, 15
        center_bonus = -abs(np[0] - cx) - abs(np[1] - cy)

        # Avoid stepping next to enemies unless necessary.
        enemy_dist = min(
            abs(np[0] - ex) + abs(np[1] - ey)
            for ex, ey in alive_enemies
        ) if alive_enemies else 99

        danger_penalty = 0
        if np in enemy_next:
            danger_penalty -= 10000

        dead_end_penalty = -5000 if onward == 0 else 0

        score = (
            area * 100
            + onward * 30
            + center_bonus * 2
            + min(enemy_dist, 6) * 5
            + danger_penalty
            + dead_end_penalty
            + random.random()
        )

        scored.append((score, ch, np))

    scored.sort(reverse=True)

    # Controlled randomness among almost-equally-good moves.
    best_score = scored[0][0]
    candidates = [(ch, np) for score, ch, np in scored if best_score - score <= 25]

    return random.choice(candidates)[0]

while True:
    line = sys.stdin.readline()
    if not line:
        break

    parts = line.strip().split()
    if len(parts) != 8:
        continue

    nums = list(map(int, parts))
    positions = [
        (nums[0], nums[1]),
        (nums[2], nums[3]),
        (nums[4], nums[5]),
        (nums[6], nums[7]),
    ]

    for p in positions:
        if inside(*p):
            claimed.add(p)

    move = choose_move(positions)

    print(move, flush=True)

    prev_positions = positions
    turn += 1
