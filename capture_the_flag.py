import sys
import random
from collections import deque
from typing import List, Dict, Tuple, Set, Optional

# Constants
BOARD_SIZE = 29
MAX_HYDRATION = 140
MOVES = [
    ("u", 0, -1),
    ("d", 0, 1),
    ("l", -1, 0),
    ("r", 1, 0),
    ("s", 0, 0),
]

def get_territory(x: int, y: int) -> str:
    """
    Determines the territory type of a given cell.
    Oasis overrides standard territory boundaries.
    """
    if 12 <= x <= 16 and 12 <= y <= 16:
        return "neutral"
    if y <= 13:
        return "blue"
    if y >= 15:
        return "red"
    return "neutral"

def find_path(
    start_x: int,
    start_y: int,
    start_hyd: int,
    targets: Set[Tuple[int, int]],
    enemies: List[Dict[str, int]],
    obstacles: Set[Tuple[int, int]],
    our_team: str,
    enemy_team: str
) -> Tuple[Optional[str], float]:
    """
    Executes a hydration-aware layer-by-layer BFS to find the shortest
    safe path to any target cell within the target set.
    """
    if (start_x, start_y) in targets:
        return "s", 0.0

    # Queue stores: (x, y, current_hydration, path_taken)
    queue = deque([(start_x, start_y, start_hyd, [])])
    
    # Tracks the maximum hydration seen at a specific cell to optimize state space
    best_hyd: Dict[Tuple[int, int], int] = {(start_x, start_y): start_hyd}

    while queue:
        x, y, hyd, path = queue.popleft()

        if (x, y) in targets:
            return path[0] if path else "s", float(len(path))

        for move, dx, dy in MOVES:
            nx, ny = x + dx, y + dy

            # Out of bounds or structural obstacle
            if not (0 <= nx < BOARD_SIZE and 0 <= ny < BOARD_SIZE):
                continue
            if (nx, ny) in obstacles:
                continue

            # Combat Threat Mapping: Avoid enemy proximity death zones in enemy territory
            if get_territory(nx, ny) == enemy_team:
                unsafe = False
                for e in enemies:
                    if e["x"] != -1:  # Enemy is alive
                        if max(abs(nx - e["x"]), abs(ny - e["y"])) <= 1:
                            unsafe = True
                            break
                if unsafe:
                    continue

            # Hydration Cost Evaluation
            cost = 2 if get_territory(nx, ny) == our_team else 1
            nhyd = hyd - cost
            if nhyd <= 0:
                continue

            # Oasis Refill Mechanic
            if 12 <= nx <= 16 and 12 <= ny <= 16:
                nhyd = MAX_HYDRATION

            # State Pruning
            if nhyd > best_hyd.get((nx, ny), -1):
                best_hyd[(nx, ny)] = nhyd
                queue.append((nx, ny, nhyd, path + [move]))

    return None, float("inf")

def main():
    # Initial Setup Phase
    try:
        board_text = input().strip()
    except Exception:
        return

    obstacles: Set[Tuple[int, int]] = {
        (index % BOARD_SIZE, index // BOARD_SIZE)
        for index, cell in enumerate(board_text)
        if cell == "#"
    }

    # Global State Configuration determined dynamically on Round 0
    our_team = ""
    enemy_team = ""
    enemy_flag: Tuple[int, int] = (0, 0)
    home_territory_cells: Set[Tuple[int, int]] = set()
    oasis_cells: Set[Tuple[int, int]] = {
        (x, y) for x in range(12, 17) for y in range(12, 17)
    }

    # Precompute home territory layouts once configuration is locked
    initialized_config = False

    while True:
        try:
            line = input()
            if not line:
                break
            values = [int(n) for n in line.split()]
        except Exception:
            break

        players = [
            {
                "x": values[i],
                "y": values[i + 1],
                "hydration": values[i + 2],
                "has_flag": values[i + 3],
            }
            for i in range(0, 16, 4)
        ]

        me = players[0]
        teammate = players[1]
        enemies = [players[2], players[3]]

        # Dead players bypass calculation
        if me["x"] == -1 or me["y"] == -1:
            print("s", flush=True)
            continue

        # Dynamic Configuration Discovery
        if not initialized_config:
            if me["x"] == 0 and me["y"] == 0:
                our_team = "blue"
                enemy_team = "red"
                enemy_flag = (28, 28)
            else:
                our_team = "red"
                enemy_team = "blue"
                enemy_flag = (0, 0)

            for tx in range(BOARD_SIZE):
                for ty in range(BOARD_SIZE):
                    if get_territory(tx, ty) == our_team:
                        home_territory_cells.add((tx, ty))
            initialized_config = True

        # Symmetry Breaking Rule Engine
        if (me["x"], me["y"]) == (teammate["x"], teammate["y"]):
            # If stacked at spawn or elsewhere, use random exploration to split coordinates
            safe_moves = []
            for move, dx, dy in MOVES:
                nx, ny = me["x"] + dx, me["y"] + dy
                if 0 <= nx < BOARD_SIZE and 0 <= ny < BOARD_SIZE and (nx, ny) not in obstacles:
                    safe_moves.append(move)
            print(random.choice(safe_moves or ["s"]), flush=True)
            continue

        # Target Set Definition Based on Game State Context
        targets: Set[Tuple[int, int]] = set()

        if me["has_flag"] == 1:
            # Objective: Return the flag to home territory immediately
            targets = home_territory_cells
        elif any(e["has_flag"] == 1 for e in enemies):
            # Objective: Intercept the specific enemy carrier
            carrier = next(e for e in enemies if e["has_flag"] == 1)
            targets.add((carrier["x"], carrier["y"]))
            # Include adjacent tracking positions if carrier is outside their home base
            if get_territory(carrier["x"], carrier["y"]) != enemy_team:
                for _, dx, dy in MOVES:
                    nx, ny = carrier["x"] + dx, carrier["y"] + dy
                    if 0 <= nx < BOARD_SIZE and 0 <= ny < BOARD_SIZE:
                        targets.add((nx, ny))
        else:
            # Role Evaluation Strategy: Attacker vs Defender
            _, dist_me = find_path(me["x"], me["y"], me["hydration"], {enemy_flag}, enemies, obstacles, our_team, enemy_team)
            _, dist_team = find_path(teammate["x"], teammate["y"], teammate["hydration"], {enemy_flag}, enemies, obstacles, our_team, enemy_team)

            is_attacker = False
            if dist_me < dist_team:
                is_attacker = True
            elif dist_me == dist_team:
                # Deterministic Tie-Breaker
                if me["x"] != teammate["x"]:
                    is_attacker = me["x"] < teammate["x"]
                else:
                    is_attacker = me["y"] < teammate["y"]

            if is_attacker:
                targets.add(enemy_flag)
            else:
                # Defender Role: Neutralize threats invading home territory
                invaders = [e for e in enemies if e["x"] != -1 and get_territory(e["x"], e["y"]) == our_team]
                if invaders:
                    # Target the closest invader's structural proximity cell
                    for invader in invaders:
                        for _, dx, dy in MOVES:
                            nx, ny = invader["x"] + dx, invader["y"] + dy
                            if 0 <= nx < BOARD_SIZE and 0 <= ny < BOARD_SIZE:
                                targets.add((nx, ny))
                else:
                    # Default defensive position: Patrol near the Oasis gateway
                    targets.add(enemy_flag)

        # Route Calculation
        move, path_len = find_path(me["x"], me["y"], me["hydration"], targets, enemies, obstacles, our_team, enemy_team)

        # Hydration Mitigation Fallback
        if move is None:
            move, _ = find_path(me["x"], me["y"], me["hydration"], oasis_cells, enemies, obstacles, our_team, enemy_team)

        # Emergency Fail-safe Strategy
        if move is None:
            # If trapped or completely starved out, choose any viable move that doesn't trigger death
            for fallback_move, dx, dy in MOVES:
                nx, ny = me["x"] + dx, me["y"] + dy
                if 0 <= nx < BOARD_SIZE and 0 <= ny < BOARD_SIZE and (nx, ny) not in obstacles:
                    move = fallback_move
                    break
            else:
                move = "s"

        print(move, flush=True)

if __name__ == "__main__":
    main()