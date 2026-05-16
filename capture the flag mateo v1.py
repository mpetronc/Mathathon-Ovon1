#!/usr/bin/env python3
import sys
import os
import time
import json
import hashlib
from collections import deque

N = 29

DIRS = {
    "u": (0, -1),
    "d": (0, 1),
    "l": (-1, 0),
    "r": (1, 0),
    "s": (0, 0),
}

MOVE_ORDER = ["u", "d", "l", "r"]

board = None
home_top = None
own_flag_initial = None
enemy_flag_initial = None
enemy_flag_pos = None

assigned_attacker = None
prev_own = None
prev_mate = None


def output(move):
    if move not in DIRS:
        move = "s"
    print(move, flush=True)


def parse_state(line):
    vals = list(map(int, line.split()))
    players = []

    for i in range(0, 16, 4):
        players.append({
            "x": vals[i],
            "y": vals[i + 1],
            "h": vals[i + 2],
            "flag": vals[i + 3] == 1,
        })

    return players[0], players[1], [players[2], players[3]]


def alive(p):
    return p["x"] >= 0 and p["y"] >= 0


def pos(p):
    return (p["x"], p["y"])


def in_bounds(x, y):
    return 0 <= x < N and 0 <= y < N


def open_cell(x, y):
    return in_bounds(x, y) and board[y * N + x] != "#"


def step_from(p, move):
    x, y = p
    dx, dy = DIRS[move]
    nx, ny = x + dx, y + dy

    if open_cell(nx, ny):
        return (nx, ny)

    return (x, y)


def is_oasis(p):
    x, y = p
    return 12 <= x <= 16 and 12 <= y <= 16


def init_side(own):
    global home_top, own_flag_initial, enemy_flag_initial, enemy_flag_pos

    if home_top is not None:
        return

    home_top = own["y"] <= 14

    if home_top:
        own_flag_initial = (0, 0)
        enemy_flag_initial = (28, 28)
    else:
        own_flag_initial = (28, 28)
        enemy_flag_initial = (0, 0)

    enemy_flag_pos = enemy_flag_initial


def own_territory(p):
    x, y = p

    if not in_bounds(x, y) or is_oasis(p):
        return False

    return y <= 13 if home_top else y >= 15


def enemy_territory(p):
    x, y = p

    if not in_bounds(x, y) or is_oasis(p):
        return False

    return y >= 15 if home_top else y <= 13


def cheb(a, b):
    return max(abs(a[0] - b[0]), abs(a[1] - b[1]))


def manhattan(a, b):
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def all_open_cells(pred):
    cells = set()

    for y in range(N):
        for x in range(N):
            if open_cell(x, y) and pred((x, y)):
                cells.add((x, y))

    return cells


def dangerous_for_me(p, enemies):
    # You can only be caught while standing in enemy territory.
    # Distance 2 is treated as unsafe because everyone moves simultaneously.
    if not enemy_territory(p):
        return False

    for e in enemies:
        if alive(e) and cheb(p, pos(e)) <= 2:
            return True

    return False


def first_step_to(start, goals, avoid=None):
    if not goals:
        return None

    if start in goals:
        return "s"

    q = deque()
    seen = {start}

    for move in MOVE_ORDER:
        nxt = step_from(start, move)

        if nxt == start or nxt in seen:
            continue

        if avoid is not None and avoid(nxt):
            continue

        if nxt in goals:
            return move

        seen.add(nxt)
        q.append((nxt, move))

    while q:
        cur, first_move = q.popleft()

        for move in MOVE_ORDER:
            nxt = step_from(cur, move)

            if nxt == cur or nxt in seen:
                continue

            if avoid is not None and avoid(nxt):
                continue

            if nxt in goals:
                return first_move

            seen.add(nxt)
            q.append((nxt, first_move))

    return None


def greedy_move(start, goals, enemies, avoid_danger=True):
    best_move = "s"
    best_score = -10**18

    for move in ["u", "d", "l", "r", "s"]:
        nxt = step_from(start, move)

        if move != "s" and nxt == start:
            continue

        dist = min((manhattan(nxt, g) for g in goals), default=0)
        score = -dist

        if avoid_danger and dangerous_for_me(nxt, enemies):
            score -= 10000

        if move == "s":
            score -= 0.1

        if score > best_score:
            best_score = score
            best_move = move

    return best_move


def path_move(start, goals, enemies, avoid_danger=True):
    if avoid_danger:
        move = first_step_to(
            start,
            goals,
            avoid=lambda p: dangerous_for_me(p, enemies)
        )

        if move is not None:
            return move

        return greedy_move(start, goals, enemies, avoid_danger=True)

    move = first_step_to(start, goals)

    if move is not None:
        return move

    return greedy_move(start, goals, enemies, avoid_danger=False)


def adjacent_cells_around(p):
    x, y = p
    cells = set()

    for yy in range(y - 1, y + 2):
        for xx in range(x - 1, x + 2):
            if (xx, yy) != (x, y) and open_cell(xx, yy):
                cells.add((xx, yy))

    return cells


def guard_cells():
    fx, fy = own_flag_initial
    cells = adjacent_cells_around((fx, fy))

    # Backup ring in case direct guard squares are blocked.
    for y in range(max(0, fy - 2), min(N, fy + 3)):
        for x in range(max(0, fx - 2), min(N, fx + 3)):
            if open_cell(x, y) and (x, y) != (fx, fy):
                cells.add((x, y))

    return cells


def oasis_cells():
    return all_open_cells(is_oasis)


def home_cells():
    return all_open_cells(own_territory)


def pid_alive(pid):
    try:
        os.kill(pid, 0)
        return True
    except Exception:
        return False


def initial_side_key(first_state_line):
    try:
        vals = list(map(int, first_state_line.split()))
        own_y = vals[1]
        return "top" if own_y <= 14 else "bottom"
    except Exception:
        return "unknown"


def choose_role_with_shared_file(first_state_line):
    """
    Same code is run for both players.
    Each copy outputs one move.

    This file makes one copy attacker and the other defender.
    A normal static variable is usually not shared between the two processes.
    """
    try:
        uid = os.getuid() if hasattr(os, "getuid") else 0
        cwd_hash = hashlib.sha1(os.getcwd().encode()).hexdigest()[:10]
        board_hash = hashlib.sha1(board.encode()).hexdigest()[:16]
        side = initial_side_key(first_state_line)

        path = f"/tmp/mathathon_ctf_role_{uid}_{cwd_hash}_{board_hash}_{side}.json"

        my_pid = os.getpid()
        now = time.time()

        for _ in range(3):
            try:
                fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.write(
                    fd,
                    json.dumps({
                        "attacker_pid": my_pid,
                        "created": now,
                    }).encode()
                )
                os.close(fd)
                return True

            except FileExistsError:
                try:
                    with open(path, "r") as f:
                        data = json.load(f)

                    attacker_pid = int(data.get("attacker_pid", -1))
                    created = float(data.get("created", 0))

                    # Clear stale role files from old matches.
                    if now - created > 900 or not pid_alive(attacker_pid):
                        try:
                            os.remove(path)
                            continue
                        except Exception:
                            pass

                    return attacker_pid == my_pid

                except Exception:
                    break

    except Exception:
        pass

    # Fallback if /tmp file sharing is blocked.
    return os.getpid() % 2 == 0


def effective_attacker_role(own, mate):
    """
    Start with the assigned role.

    Once teammates separate, the one closer to the enemy flag becomes attacker.
    This keeps roles complementary even though both run identical code.
    """
    if not alive(mate):
        return assigned_attacker

    my_pos = pos(own)
    mate_pos = pos(mate)

    if my_pos == mate_pos:
        return assigned_attacker

    my_d = manhattan(my_pos, enemy_flag_initial)
    mate_d = manhattan(mate_pos, enemy_flag_initial)

    if my_d != mate_d:
        return my_d < mate_d

    # Symmetric tie-breaker: exactly one copy returns True.
    return my_pos > mate_pos


def update_enemy_flag_memory(own, mate, enemies):
    global enemy_flag_pos, prev_own, prev_mate

    if enemy_flag_pos is None:
        enemy_flag_pos = enemy_flag_initial

    if own["flag"] or mate["flag"]:
        return

    # If we had the enemy flag last turn and now nobody has it,
    # estimate whether it reset or dropped.
    for old in [prev_own, prev_mate]:
        if old is None:
            continue

        if old["flag"] and alive(old):
            old_pos = pos(old)
            caught = False

            for e in enemies:
                if alive(e) and enemy_territory(old_pos) and cheb(old_pos, pos(e)) <= 1:
                    caught = True

            enemy_flag_pos = enemy_flag_initial if caught else old_pos


def chase_invader_move(own, enemies):
    invaders = [
        e for e in enemies
        if alive(e) and own_territory(pos(e))
    ]

    if not invaders:
        return None

    def priority(e):
        flag_score = 0 if e["flag"] else 1

        # Lower escape_score means closer to escaping our territory.
        escape_score = (13 - e["y"]) if home_top else (e["y"] - 15)

        return (flag_score, escape_score, manhattan(pos(own), pos(e)))

    target = min(invaders, key=priority)

    likely_positions = {pos(target)}

    # Guess the enemy's escape direction.
    likely_moves = ["d", "r", "l", "s"] if home_top else ["u", "r", "l", "s"]

    for move in likely_moves:
        likely_positions.add(step_from(pos(target), move))

    targets = set()

    for q in likely_positions:
        targets |= adjacent_cells_around(q)

    if not targets:
        targets = {pos(target)}

    return path_move(pos(own), targets, enemies, avoid_danger=False)


def defender_move(own, mate, enemies, oasis_goals):
    p = pos(own)

    # First priority: kill invaders.
    chase = chase_invader_move(own, enemies)

    if chase is not None:
        return chase

    # Defending in own territory costs 2 hydration per turn.
    # Refill before dying.
    if own["h"] < 75 and oasis_goals and not is_oasis(p):
        return path_move(p, oasis_goals, enemies, avoid_danger=False)

    # Camp around our own flag.
    return path_move(p, guard_cells(), enemies, avoid_danger=False)


def attacker_move(own, mate, enemies, oasis_goals, home_goals):
    p = pos(own)

    # If carrying enemy flag, return to any home territory cell.
    if own["flag"]:
        return path_move(p, home_goals, enemies, avoid_danger=True)

    # If teammate has flag, protect our side.
    if mate["flag"]:
        return defender_move(own, mate, enemies, oasis_goals)

    # If enemy has our flag, help defend.
    if any(alive(e) and e["flag"] and own_territory(pos(e)) for e in enemies):
        return defender_move(own, mate, enemies, oasis_goals)

    # Route through oasis before entering enemy territory.
    should_go_oasis = False

    if not is_oasis(p):
        if own["h"] < 90:
            should_go_oasis = True

        if home_top and p[1] <= 16:
            should_go_oasis = True

        if (not home_top) and p[1] >= 12:
            should_go_oasis = True

    if should_go_oasis and oasis_goals:
        return path_move(p, oasis_goals, enemies, avoid_danger=True)

    target = enemy_flag_pos if enemy_flag_pos is not None else enemy_flag_initial

    return path_move(p, {target}, enemies, avoid_danger=True)


def decide(own, mate, enemies):
    if not alive(own):
        return "s"

    init_side(own)
    update_enemy_flag_memory(own, mate, enemies)

    oasis_goals = oasis_cells()
    home_goals = home_cells()

    # Emergency/dynamic rules override normal roles.
    if own["flag"]:
        return attacker_move(own, mate, enemies, oasis_goals, home_goals)

    if mate["flag"]:
        return defender_move(own, mate, enemies, oasis_goals)

    if any(alive(e) and e["flag"] and own_territory(pos(e)) for e in enemies):
        return defender_move(own, mate, enemies, oasis_goals)

    # Normal one-submission role split.
    if effective_attacker_role(own, mate):
        return attacker_move(own, mate, enemies, oasis_goals, home_goals)

    return defender_move(own, mate, enemies, oasis_goals)


def main():
    global board, assigned_attacker, prev_own, prev_mate

    first = sys.stdin.readline()

    if not first:
        return

    first = first.rstrip("\n")

    # Round 0 gives the board first.
    if len(first) >= N * N and all(c in ".#" for c in first[:N * N]):
        board = first[:N * N]
        state_line = sys.stdin.readline()
    else:
        # Local fallback only. The real judge should give the board first.
        board = "." * (N * N)
        state_line = first

    assigned_attacker = choose_role_with_shared_file(state_line)

    while state_line:
        try:
            state_line = state_line.strip()

            if not state_line:
                output("s")
                state_line = sys.stdin.readline()
                continue

            own, mate, enemies = parse_state(state_line)

            move = decide(own, mate, enemies)

            output(move)

            prev_own = own.copy()
            prev_mate = mate.copy()

        except Exception:
            # Never crash. Crashing means permanent disqualification.
            output("s")

        state_line = sys.stdin.readline()


if __name__ == "__main__":
    main()
