#!/usr/bin/env python3
import os
import sys
import random
import heapq
import traceback
from typing import Dict, List, Tuple, Set, Optional, Callable, Any

# =============================================================================
# CONSTANTS & TYPES
# =============================================================================
N = 29
DIRS: Dict[str, Tuple[int, int]] = {
    "u": (0, -1),
    "d": (0, 1),
    "l": (-1, 0),
    "r": (1, 0),
    "s": (0, 0),
}
MOVE_ORDER = ["u", "d", "l", "r"]

Position = Tuple[int, int]
Player = Dict[str, Any]  # Keys: 'x', 'y', 'h', 'flag'

# =============================================================================
# GLOBAL STATE
# =============================================================================
board: str = "." * (N * N)
is_initialized: bool = False
home_top: bool = False
own_flag_initial: Position = (0, 0)
enemy_flag_initial: Position = (28, 28)
enemy_flag_pos: Position = (28, 28)

assigned_role: Optional[str] = None
prev_own: Optional[Player] = None
prev_mate: Optional[Player] = None


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================
def output(move: str) -> None:
    print(move if move in DIRS else "s", flush=True)

def parse_state(line: str) -> Tuple[Player, Player, List[Player]]:
    vals = list(map(int, line.split()))
    players = [
        {"x": vals[i], "y": vals[i + 1], "h": vals[i + 2], "flag": vals[i + 3] == 1}
        for i in range(0, 16, 4)
    ]
    return players[0], players[1], [players[2], players[3]]

def alive(p: Player) -> bool:
    return p["x"] >= 0 and p["y"] >= 0

def pos(p: Player) -> Position:
    return (p["x"], p["y"])

def in_bounds(x: int, y: int) -> bool:
    return 0 <= x < N and 0 <= y < N

def open_cell(p: Position) -> bool:
    x, y = p
    return in_bounds(x, y) and board[y * N + x] != "#"

def step_from(p: Position, move: str) -> Position:
    x, y = p
    dx, dy = DIRS[move]
    nx, ny = x + dx, y + dy
    return (nx, ny) if open_cell((nx, ny)) else p

def is_oasis(p: Position) -> bool:
    x, y = p
    return 12 <= x <= 16 and 12 <= y <= 16

def own_territory(p: Position) -> bool:
    if not open_cell(p) or is_oasis(p):
        return False
    return p[1] <= 13 if home_top else p[1] >= 15

def enemy_territory(p: Position) -> bool:
    if not open_cell(p) or is_oasis(p):
        return False
    return p[1] >= 15 if home_top else p[1] <= 13

def cheb(a: Position, b: Position) -> int:
    return max(abs(a[0] - b[0]), abs(a[1] - b[1]))

def manhattan(a: Position, b: Position) -> int:
    return abs(a[0] - b[0]) + abs(a[1] - b[1])

def get_cells_matching(pred: Callable[[Position], bool]) -> Set[Position]:
    return {(x, y) for y in range(N) for x in range(N) if open_cell((x, y)) and pred((x, y))}

# =============================================================================
# CORE ARCHITECTURE: WEIGHTED PATHFINDING (Dijkstra)
# =============================================================================
def path_move(start: Position, goals: Set[Position], enemies: List[Player], avoid_danger: bool) -> str:
    """
    Industry-standard Dijkstra implementation. 
    Never aborts early based on cost; guarantees shortest path finding even through heavy danger.
    """
    if start in goals:
        return "s"
    if not goals:
        return "s"

    # Danger mapping: O(E)
    danger_zones: Set[Position] = set()
    if avoid_danger:
        for e in enemies:
            if alive(e):
                ep = pos(e)
                for dy in range(-2, 3):
                    for dx in range(-2, 3):
                        dp = (ep[0] + dx, ep[1] + dy)
                        if enemy_territory(dp):
                            danger_zones.add(dp)

    pq: List[Tuple[int, Position, str]] = []
    seen: Dict[Position, int] = {start: 0}

    for move in MOVE_ORDER:
        nxt = step_from(start, move)
        if nxt == start:
            continue
        
        cost = 1000 if nxt in danger_zones else 1
        seen[nxt] = cost
        heapq.heappush(pq, (cost, nxt, move))

    best_move = "s"
    
    while pq:
        cost, cur, first_move = heapq.heappop(pq)

        if cur in goals:
            return first_move

        # No premature cost-break here. Let Dijkstra fully exhaust the 841-node graph.

        for move in MOVE_ORDER:
            nxt = step_from(cur, move)
            if nxt == cur:
                continue

            step_cost = 1000 if nxt in danger_zones else 1
            new_cost = cost + step_cost

            if nxt not in seen or new_cost < seen[nxt]:
                seen[nxt] = new_cost
                heapq.heappush(pq, (new_cost, nxt, first_move))

    return fallback_greedy_move(start, goals, danger_zones)

def fallback_greedy_move(start: Position, goals: Set[Position], danger_zones: Set[Position]) -> str:
    best_move, best_score = "s", -float('inf')
    
    for move in ["u", "d", "l", "r", "s"]:
        nxt = step_from(start, move)
        if move != "s" and nxt == start:
            continue

        dist = min((manhattan(nxt, g) for g in goals), default=0)
        score = -dist

        if nxt in danger_zones:
            score -= 1000
        if move == "s":
            score -= 0.1

        if score > best_score:
            best_score = score
            best_move = move

    return best_move

# =============================================================================
# STRATEGY LOGIC
# =============================================================================
def chase_invader_move(own: Player, enemies: List[Player]) -> Optional[str]:
    invaders = [e for e in enemies if alive(e) and own_territory(pos(e))]
    if not invaders:
        return None

    def priority(e: Player) -> Tuple[int, int, int]:
        flag_score = 0 if e["flag"] else 1
        escape_score = (13 - e["y"]) if home_top else (e["y"] - 15)
        return (flag_score, escape_score, manhattan(pos(own), pos(e)))

    target = min(invaders, key=priority)
    targets = {pos(target)}
    
    for move in (["d", "r", "l"] if home_top else ["u", "r", "l"]):
        p = step_from(pos(target), move)
        if open_cell(p):
            targets.add(p)

    return path_move(pos(own), targets, enemies, avoid_danger=False)

def defender_move(own: Player, mate: Player, enemies: List[Player]) -> str:
    p = pos(own)
    chase = chase_invader_move(own, enemies)
    if chase:
        return chase

    oasis_goals = get_cells_matching(is_oasis)
    if own["h"] < 75 and oasis_goals and not is_oasis(p):
        return path_move(p, oasis_goals, enemies, avoid_danger=False)

    fx, fy = own_flag_initial
    guard_cells = { (x, y) for y in range(max(0, fy-2), min(N, fy+3)) 
                           for x in range(max(0, fx-2), min(N, fx+3)) 
                           if open_cell((x, y)) and (x, y) != (fx, fy) }
                           
    return path_move(p, guard_cells, enemies, avoid_danger=False)

def attacker_move(own: Player, mate: Player, enemies: List[Player]) -> str:
    p = pos(own)
    
    if own["flag"]:
        home_goals = get_cells_matching(own_territory)
        return path_move(p, home_goals, enemies, avoid_danger=True)

    if mate["flag"] or any(alive(e) and e["flag"] and own_territory(pos(e)) for e in enemies):
        return defender_move(own, mate, enemies)

    if not is_oasis(p):
        should_go_oasis = own["h"] < 90 or (home_top and p[1] < 12) or (not home_top and p[1] > 16)
        if should_go_oasis:
            oasis_goals = get_cells_matching(is_oasis)
            if oasis_goals:
                return path_move(p, oasis_goals, enemies, avoid_danger=True)

    return path_move(p, {enemy_flag_pos}, enemies, avoid_danger=True)

def decide(own: Player, mate: Player, enemies: List[Player]) -> str:
    global is_initialized, home_top, own_flag_initial, enemy_flag_initial, enemy_flag_pos, assigned_role

    if not alive(own):
        return "s"

    # Strictly execute setup only once to guarantee orientation consistency.
    if not is_initialized:
        if own["y"] <= 14:
            home_top = True
            own_flag_initial = (0, 0)
            enemy_flag_initial = (28, 28)
            enemy_flag_pos = (28, 28)
        else:
            home_top = False
            own_flag_initial = (28, 28)
            enemy_flag_initial = (0, 0)
            enemy_flag_pos = (0, 0)
        is_initialized = True

    if not alive(mate):
        assigned_role = 'attacker'
    
    if assigned_role is None:
        if pos(own) == pos(mate):
            # Fallback random divergence for literal identical inputs
            valid_moves = [m for m in MOVE_ORDER if step_from(pos(own), m) != pos(own)]
            return random.choice(valid_moves) if valid_moves else "s"
        else:
            assigned_role = 'attacker' if pos(own) > pos(mate) else 'defender'

    if own["flag"]:
        return attacker_move(own, mate, enemies)
    if mate["flag"]:
        return defender_move(own, mate, enemies)
        
    return attacker_move(own, mate, enemies) if assigned_role == 'attacker' else defender_move(own, mate, enemies)


# =============================================================================
# MAIN LOOP
# =============================================================================
def main() -> None:
    global board, prev_own, prev_mate, enemy_flag_pos
    
    # Process-unique seeding guarantees different pathing choices during overlap
    random.seed(os.getpid())

    first = sys.stdin.readline()
    if not first:
        return
    first = first.rstrip("\n")

    if len(first) >= N * N and all(c in ".#" for c in first[:N * N]):
        board = first[:N * N]
        state_line = sys.stdin.readline()
    else:
        state_line = first

    while state_line:
        try:
            state_line = state_line.strip()
            if not state_line:
                output("s")
                state_line = sys.stdin.readline()
                continue

            own, mate, enemies = parse_state(state_line)
            
            if not own["flag"] and not mate["flag"]:
                for old_p in [prev_own, prev_mate]:
                    if old_p and old_p["flag"] and alive(old_p):
                        old_pos = pos(old_p)
                        caught = any(alive(e) and enemy_territory(old_pos) and cheb(old_pos, pos(e)) <= 1 for e in enemies)
                        enemy_flag_pos = enemy_flag_initial if caught else old_pos
            
            move = decide(own, mate, enemies)
            output(move)

            prev_own, prev_mate = own.copy(), mate.copy()

        except Exception:
            traceback.print_exc(file=sys.stderr)
            output("s")

        state_line = sys.stdin.readline()

if __name__ == "__main__":
    main()