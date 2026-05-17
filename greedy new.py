import sys
import time
from collections import deque
from typing import List, Tuple, Optional

# ------------------------------------------------------------
# Snaky-Greed Bot
# Strategy:
# 1. Exact jump simulation.
# 2. Simultaneous collision handling.
# 3. Maximin + average enemy-response scoring.
# 4. Jump-Voronoi territory.
# 5. Mobility + survival-depth to avoid edge/corridor traps.
# 6. Score-aware death/trade evaluation.
# ------------------------------------------------------------

GRID_SIZE = 32
CELLS = GRID_SIZE * GRID_SIZE
TIME_LIMIT_SEC = 0.38  # keep safely under 500ms

MOVES = [
    ("u", 0, -1),
    ("d", 0, 1),
    ("l", -1, 0),
    ("r", 1, 0),
]

original_grid = [1] * CELLS
claimed_grid = bytearray(CELLS)


def idx_of(x: int, y: int) -> int:
    return y * GRID_SIZE + x


def inside(x: int, y: int) -> bool:
    return 0 <= x < GRID_SIZE and 0 <= y < GRID_SIZE


def get_jump_distance(x: int, y: int, dx: int, dy: int) -> int:
    """
    Jump distance is the value of the adjacent cell in that direction.
    If the adjacent cell is outside the board, the distance is 1.
    """
    nx, ny = x + dx, y + dy
    if not inside(nx, ny):
        return 1
    return original_grid[idx_of(nx, ny)]


def simulate_jump(
    x: int,
    y: int,
    dx: int,
    dy: int,
    state: bytearray,
) -> Optional[Tuple[int, int, List[int]]]:
    """
    Returns (final_x, final_y, path_indices) if the full jump is legal.
    Returns None if the jump hits a wall or an already claimed cell.
    """
    dist = get_jump_distance(x, y, dx, dy)
    path: List[int] = []
    cx, cy = x, y

    for _ in range(dist):
        cx += dx
        cy += dy

        if not inside(cx, cy):
            return None

        idx = idx_of(cx, cy)
        if state[idx]:
            return None

        path.append(idx)

    return cx, cy, path


def safe_prefix_len(x: int, y: int, dx: int, dy: int, state: bytearray) -> int:
    """
    If every full move is lethal, choose the move that scores the most
    safe partial steps before death.
    """
    dist = get_jump_distance(x, y, dx, dy)
    cx, cy = x, y
    count = 0

    for _ in range(dist):
        cx += dx
        cy += dy

        if not inside(cx, cy):
            break

        idx = idx_of(cx, cy)
        if state[idx]:
            break

        count += 1

    return count


def legal_count(x: int, y: int, state: bytearray) -> int:
    count = 0
    for _, dx, dy in MOVES:
        if simulate_jump(x, y, dx, dy, state):
            count += 1
    return count


def mark_path(state: bytearray, path: List[int]) -> None:
    for idx in path:
        state[idx] = 1


def fill_line_and_count(x1: int, y1: int, x2: int, y2: int) -> int:
    """
    Reconstructs a completed trail from observed positions.
    Counts movement steps, excluding the starting cell.
    """
    if not inside(x1, y1) or not inside(x2, y2):
        return 0

    if x1 == x2 and y1 == y2:
        claimed_grid[idx_of(x1, y1)] = 1
        return 0

    dx = 0 if x1 == x2 else (1 if x2 > x1 else -1)
    dy = 0 if y1 == y2 else (1 if y2 > y1 else -1)

    count = 0
    cx, cy = x1, y1
    claimed_grid[idx_of(cx, cy)] = 1

    if x1 == x2 or y1 == y2:
        while (cx, cy) != (x2, y2):
            cx += dx
            cy += dy

            if not inside(cx, cy):
                break

            claimed_grid[idx_of(cx, cy)] = 1
            count += 1
    else:
        # Should not happen in a valid game, but keep the bot safe.
        claimed_grid[idx_of(x2, y2)] = 1
        count = abs(x2 - x1) + abs(y2 - y1)

    return count


def resolve_simultaneous(my_path: List[int], en_path: List[int]) -> Tuple[bool, bool, List[int], List[int]]:
    """
    Resolves same-turn path conflicts step by step.

    Returns:
        my_alive, en_alive, my_claimed_prefix, en_claimed_prefix

    A player dies if they enter a cell already claimed earlier in this round.
    If both enter the same cell on the same step, both die.
    The death cell itself is not counted as newly claimed.
    """
    round_claimed = set()
    my_real: List[int] = []
    en_real: List[int] = []

    my_alive = True
    en_alive = True
    max_len = max(len(my_path), len(en_path))

    for i in range(max_len):
        my_cell = my_path[i] if my_alive and i < len(my_path) else None
        en_cell = en_path[i] if en_alive and i < len(en_path) else None

        my_dies = False
        en_dies = False

        if my_cell is not None and my_cell in round_claimed:
            my_dies = True

        if en_cell is not None and en_cell in round_claimed:
            en_dies = True

        if my_cell is not None and en_cell is not None and my_cell == en_cell:
            my_dies = True
            en_dies = True

        if my_cell is not None:
            if my_dies:
                my_alive = False
            else:
                my_real.append(my_cell)

        if en_cell is not None:
            if en_dies:
                en_alive = False
            else:
                en_real.append(en_cell)

        if my_cell is not None and not my_dies:
            round_claimed.add(my_cell)

        if en_cell is not None and not en_dies:
            round_claimed.add(en_cell)

    return my_alive, en_alive, my_real, en_real


def reachable_volume(x: int, y: int, state: bytearray, deadline: float) -> int:
    """
    Approximate amount of future score available to a lone surviving player
    using exact jump moves.
    """
    if time.monotonic() > deadline or not inside(x, y):
        return 0

    visited = bytearray(state)
    visited[idx_of(x, y)] = 1
    q = deque([(x, y)])
    total = 0

    while q:
        if time.monotonic() > deadline:
            break

        cx, cy = q.popleft()

        for _, dx, dy in MOVES:
            sim = simulate_jump(cx, cy, dx, dy, visited)

            if sim:
                nx, ny, path = sim
                mark_path(visited, path)
                total += len(path)
                q.append((nx, ny))

    return total


def calculate_jump_voronoi(
    my_x: int,
    my_y: int,
    en_x: int,
    en_y: int,
    state: bytearray,
    deadline: float,
) -> float:
    """
    Approximate jump-based territory difference:
        my reachable volume - enemy reachable volume
    """
    if time.monotonic() > deadline:
        return 0.0

    if not inside(my_x, my_y):
        return -10000.0

    if not inside(en_x, en_y):
        return 10000.0

    my_q = deque([(my_x, my_y)])
    en_q = deque([(en_x, en_y)])

    visited = bytearray(state)
    visited[idx_of(my_x, my_y)] = 1
    visited[idx_of(en_x, en_y)] = 1

    my_score = 0
    en_score = 0

    while my_q or en_q:
        if time.monotonic() > deadline:
            break

        for _ in range(len(my_q)):
            cx, cy = my_q.popleft()

            for _, dx, dy in MOVES:
                sim = simulate_jump(cx, cy, dx, dy, visited)

                if sim:
                    nx, ny, path = sim
                    mark_path(visited, path)
                    my_score += len(path)
                    my_q.append((nx, ny))

        for _ in range(len(en_q)):
            cx, cy = en_q.popleft()

            for _, dx, dy in MOVES:
                sim = simulate_jump(cx, cy, dx, dy, visited)

                if sim:
                    nx, ny, path = sim
                    mark_path(visited, path)
                    en_score += len(path)
                    en_q.append((nx, ny))

    if en_score == 0 and my_score > 0:
        return 10000.0 + my_score

    if my_score == 0 and en_score > 0:
        return -10000.0 - en_score

    return float(my_score - en_score)


def survival_depth(x: int, y: int, state: bytearray, depth: int, deadline: float) -> int:
    """
    Small DFS that answers:
    how many full moves can I still survive?

    This is the main anti-corridor / anti-edge-trap function.
    """
    if depth <= 0 or time.monotonic() > deadline:
        return 0

    best = 0

    for _, dx, dy in MOVES:
        sim = simulate_jump(x, y, dx, dy, state)

        if not sim:
            continue

        nx, ny, path = sim
        new_state = bytearray(state)
        mark_path(new_state, path)

        best = max(
            best,
            1 + survival_depth(nx, ny, new_state, depth - 1, deadline)
        )

    return best


def terminal_value_from_diff(diff: int) -> float:
    """
    Converts estimated final score difference into a large utility.
    Positive diff means we probably win; negative means we probably lose.
    """
    if diff > 0:
        return 1_000_000.0 + 150.0 * diff

    if diff < 0:
        return -1_000_000.0 + 150.0 * diff

    return -25_000.0  # avoid draws/trades unless no better option


def edge_penalty(x: int, y: int, mobility: int) -> float:
    """
    Being on an edge is acceptable only when we have exits.
    """
    margin = min(x, y, GRID_SIZE - 1 - x, GRID_SIZE - 1 - y)

    if mobility >= 3:
        return 0.0

    if margin == 0:
        return 250.0 * (3 - mobility)

    if margin == 1:
        return 100.0 * (3 - mobility)

    return 0.0


def evaluate_solo_move(
    move_tuple,
    my_score: int,
    en_score: int,
    deadline: float,
) -> float:
    """
    Used when the enemy is dead or has no complete legal move.
    """
    move_id, dx, dy, sim = move_tuple
    nx, ny, path = sim

    temp = bytearray(claimed_grid)
    mark_path(temp, path)

    mob = legal_count(nx, ny, temp)
    life = survival_depth(nx, ny, temp, depth=5, deadline=deadline)
    future = reachable_volume(nx, ny, temp, deadline)

    score_diff_now = (my_score + len(path)) - en_score

    score = (
        25.0 * len(path)
        + 3.0 * future
        + 900.0 * life
        + 80.0 * mob
        + 20.0 * score_diff_now
        - edge_penalty(nx, ny, mob)
    )

    if mob == 0:
        score -= 200_000.0
    elif mob == 1:
        score -= 25_000.0

    return score


def get_best_move(
    my_x: int,
    my_y: int,
    en_x: int,
    en_y: int,
    en_dead: bool,
    my_score: int,
    en_score: int,
) -> str:
    start_time = time.monotonic()
    deadline = start_time + TIME_LIMIT_SEC

    my_moves = []

    for move_id, dx, dy in MOVES:
        sim = simulate_jump(my_x, my_y, dx, dy, claimed_grid)

        if sim:
            my_moves.append((move_id, dx, dy, sim))

    # If no complete legal jump exists, take the longest safe prefix.
    if not my_moves:
        return max(
            MOVES,
            key=lambda m: safe_prefix_len(my_x, my_y, m[1], m[2], claimed_grid),
        )[0]

    # Fallback if time runs out.
    best_move = max(my_moves, key=lambda m: len(m[3][2]))[0]

    en_moves = []

    if not en_dead and inside(en_x, en_y):
        for move_id, dx, dy in MOVES:
            sim = simulate_jump(en_x, en_y, dx, dy, claimed_grid)

            if sim:
                en_moves.append((move_id, dx, dy, sim))

    # Enemy dead or doomed: maximize our future score, not just current jump length.
    if en_dead or not en_moves:
        best_score = -float("inf")

        for move in my_moves:
            if time.monotonic() > deadline:
                return best_move

            score = evaluate_solo_move(move, my_score, en_score, deadline)

            if score > best_score:
                best_score = score
                best_move = move[0]

        return best_move

    best_combined = -float("inf")

    for my_move in my_moves:
        if time.monotonic() > deadline:
            return best_move

        my_id, _, _, (my_nx, my_ny, my_path) = my_move
        response_scores: List[float] = []

        for en_move in en_moves:
            if time.monotonic() > deadline:
                return best_move

            en_id, _, _, (en_nx, en_ny, en_path) = en_move

            my_alive, en_alive, my_real_path, en_real_path = resolve_simultaneous(
                my_path,
                en_path,
            )

            temp = bytearray(claimed_grid)
            mark_path(temp, my_real_path)
            mark_path(temp, en_real_path)

            projected_my_score = my_score + len(my_real_path)
            projected_en_score = en_score + len(en_real_path)

            # Someone dies this turn. Estimate final score, not just survival.
            if not my_alive and not en_alive:
                final_diff = projected_my_score - projected_en_score
                score = terminal_value_from_diff(final_diff)

            elif not my_alive:
                enemy_future = reachable_volume(en_nx, en_ny, temp, deadline)
                final_diff = projected_my_score - (projected_en_score + enemy_future)
                score = terminal_value_from_diff(final_diff) - 30_000.0

            elif not en_alive:
                my_future = reachable_volume(my_nx, my_ny, temp, deadline)
                final_diff = (projected_my_score + my_future) - projected_en_score
                score = terminal_value_from_diff(final_diff) + 30_000.0

            else:
                vor = calculate_jump_voronoi(
                    my_nx,
                    my_ny,
                    en_nx,
                    en_ny,
                    temp,
                    deadline,
                )

                my_mob = legal_count(my_nx, my_ny, temp)
                en_mob = legal_count(en_nx, en_ny, temp)

                remaining = deadline - time.monotonic()
                depth = 5 if remaining > 0.12 else 4

                life = survival_depth(
                    my_nx,
                    my_ny,
                    temp,
                    depth=depth,
                    deadline=deadline,
                )

                score_diff_now = projected_my_score - projected_en_score
                path_diff = len(my_real_path) - len(en_real_path)

                score = (
                    1.0 * vor
                    + 55.0 * my_mob
                    - 75.0 * en_mob
                    + 900.0 * life
                    + 9.0 * path_diff
                    + 18.0 * score_diff_now
                    - edge_penalty(my_nx, my_ny, my_mob)
                )

                # Hard anti-dead-end rules.
                if my_mob == 0:
                    score -= 200_000.0
                elif my_mob == 1:
                    score -= 25_000.0

                if life == 0:
                    score -= 200_000.0
                elif life == 1:
                    score -= 80_000.0
                elif life == 2:
                    score -= 25_000.0
                elif life == 3:
                    score -= 7_000.0

                # Trapping the opponent is very valuable.
                if en_mob == 0:
                    score += 80_000.0
                elif en_mob == 1:
                    score += 12_000.0

            response_scores.append(score)

        if not response_scores:
            continue

        worst = min(response_scores)
        avg = sum(response_scores) / len(response_scores)

        # Mostly maximin, but not too paranoid.
        combined = 0.78 * worst + 0.22 * avg

        if combined > best_combined:
            best_combined = combined
            best_move = my_id

    return best_move


def read_nonempty_line() -> Optional[str]:
    while True:
        line = sys.stdin.readline()

        if line == "":
            return None

        line = line.strip()

        if line:
            return line


def read_initial_grid() -> bool:
    """
    Supports both:
    - 1024 space-separated digits
    - one continuous 1024-digit string
    """
    tokens: List[str] = []

    while len(tokens) < CELLS:
        line = read_nonempty_line()

        if line is None:
            return False

        parts = line.split()

        if len(parts) == 1 and len(parts[0]) >= CELLS and parts[0].isdigit():
            tokens.extend(list(parts[0][:CELLS]))
            break

        tokens.extend(parts)

    for i in range(CELLS):
        original_grid[i] = int(tokens[i])

    return True


def main() -> None:
    if not read_initial_grid():
        return

    my_pos: Optional[Tuple[int, int]] = None
    en_pos: Optional[Tuple[int, int]] = None
    en_dead = False

    # Starting cells count as claimed.
    my_score = 1
    en_score = 1

    while True:
        line = read_nonempty_line()

        if line is None:
            break

        vals = line.split()

        if len(vals) < 4:
            continue

        my_x, my_y, en_x, en_y = map(int, vals[:4])

        if my_pos is None:
            if inside(my_x, my_y):
                claimed_grid[idx_of(my_x, my_y)] = 1

            if inside(en_x, en_y):
                claimed_grid[idx_of(en_x, en_y)] = 1

        else:
            old_my_x, old_my_y = my_pos
            old_en_x, old_en_y = en_pos  # type: ignore[misc]

            my_score += fill_line_and_count(old_my_x, old_my_y, my_x, my_y)

            # If enemy position did not change, they are probably dead.
            if (en_x, en_y) == (old_en_x, old_en_y):
                en_dead = True

                if inside(en_x, en_y):
                    claimed_grid[idx_of(en_x, en_y)] = 1

            elif not en_dead:
                en_score += fill_line_and_count(old_en_x, old_en_y, en_x, en_y)

        my_pos = (my_x, my_y)
        en_pos = (en_x, en_y)

        move = get_best_move(
            my_x,
            my_y,
            en_x,
            en_y,
            en_dead,
            my_score,
            en_score,
        )

        print(move, flush=True)


if __name__ == "__main__":
    main()
