import sys
import random
from collections import deque
from typing import List, Tuple, Set, Optional

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

# Pre-calculate territory map to replace function overhead
TERRITORY_MAP = [["neutral"] * BOARD_SIZE for _ in range(BOARD_SIZE)]
for x in range(BOARD_SIZE):
    for y in range(BOARD_SIZE):
        if 12 <= x <= 16 and 12 <= y <= 16:
            TERRITORY_MAP[x][y] = "neutral"
        elif y <= 13:
            TERRITORY_MAP[x][y] = "blue"
        elif y >= 15:
            TERRITORY_MAP[x][y] = "red"

OASIS_CELLS: Set[Tuple[int, int]] = {
    (x, y) for x in range(12, 17) for y in range(12, 17)
}

def find_path(
    start_x: int,
    start_y: int,
    start_hyd: int,
    targets: Set[Tuple[int, int]],
    danger_cells: Set[Tuple[int, int]],
    obstacle_map: List[List[bool]],
    cost_map: List[List[int]]
) -> Tuple[Optional[str], float]:
    
    # Failsafe for dead agents initiating paths
    if not (0 <= start_x < BOARD_SIZE and 0 <= start_y < BOARD_SIZE):
        return None, float("inf")
        
    if (start_x, start_y) in targets:
        return "s", 0.0

    queue = deque([(start_x, start_y, start_hyd, None, 0)])
    
    # SPEEDUP: 2D array replaces Dict. Removes Tuple hashing overhead.
    best_hyd = [[-1] * BOARD_SIZE for _ in range(BOARD_SIZE)]
    best_hyd[start_x][start_y] = start_hyd

    while queue:
        x, y, hyd, first_move, dist = queue.popleft()

        if (x, y) in targets:
            return first_move if first_move else "s", float(dist)

        for move, dx, dy in MOVES:
            nx, ny = x + dx, y + dy

            if not (0 <= nx < BOARD_SIZE and 0 <= ny < BOARD_SIZE):
                continue
            if obstacle_map[nx][ny]:
                continue
            if (nx, ny) in danger_cells:
                continue

            nhyd = hyd - cost_map[nx][ny]
            if nhyd <= 0:
                continue

            if 12 <= nx <= 16 and 12 <= ny <= 16:
                nhyd = MAX_HYDRATION

            # State Pruning via blazing-fast index lookup
            if nhyd > best_hyd[nx][ny]:
                best_hyd[nx][ny] = nhyd
                n_move = first_move if first_move else move
                queue.append((nx, ny, nhyd, n_move, dist + 1))

    return None, float("inf")

def main():
    try:
        board_text = input().strip()
    except Exception:
        return

    obstacle_map = [[False] * BOARD_SIZE for _ in range(BOARD_SIZE)]
    
    # FIX: Guarded creation prevents string-length/newline IndexErrors
    for index, cell in enumerate(board_text.replace('\n', '').replace('\r', '')):
        if cell == "#":
            x, y = index % BOARD_SIZE, index // BOARD_SIZE
            if x < BOARD_SIZE and y < BOARD_SIZE:
                obstacle_map[x][y] = True

    our_team = ""
    enemy_team = ""
    enemy_flag: Tuple[int, int] = (0, 0)
    home_territory_cells: Set[Tuple[int, int]] = set()
    cost_map = [[1] * BOARD_SIZE for _ in range(BOARD_SIZE)]
    initialized_config = False

    while True:
        try:
            line = input()
            if not line:
                break
            values = [int(n) for n in line.split()]
            
            players = [
                {
                    "x": values[i],
                    "y": values[i + 1],
                    "hydration": values[i + 2],
                    "has_flag": values[i + 3],
                }
                for i in range(0, 16, 4)
            ]
        except EOFError:
            break
        except Exception:
            # FATAL CRASH PREVENTION: If data is garbled, stay alive and print a safe move.
            print("s", flush=True)
            continue

        me = players[0]
        teammate = players[1]
        enemies = [players[2], players[3]]

        if me["x"] == -1 or me["y"] == -1:
            print("s", flush=True)
            continue

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
                    if TERRITORY_MAP[tx][ty] == our_team:
                        home_territory_cells.add((tx, ty))
                        cost_map[tx][ty] = 2 
            
            initialized_config = True

        danger_cells: Set[Tuple[int, int]] = set()
        for e in enemies:
            if e["x"] != -1:
                for dx in (-1, 0, 1):
                    for dy in (-1, 0, 1):
                        nx, ny = e["x"] + dx, e["y"] + dy
                        if 0 <= nx < BOARD_SIZE and 0 <= ny < BOARD_SIZE:
                            if TERRITORY_MAP[nx][ny] == enemy_team:
                                danger_cells.add((nx, ny))

        if (me["x"], me["y"]) == (teammate["x"], teammate["y"]):
            safe_moves = []
            for move, dx, dy in MOVES:
                nx, ny = me["x"] + dx, me["y"] + dy
                if 0 <= nx < BOARD_SIZE and 0 <= ny < BOARD_SIZE and not obstacle_map[nx][ny]:
                    safe_moves.append(move)
            print(random.choice(safe_moves or ["s"]), flush=True)
            continue

        targets: Set[Tuple[int, int]] = set()

        if me["has_flag"] == 1:
            targets = home_territory_cells
        else:
            # FIX: Safely retrieve carriers and guard bounds to prevent [-1][-1] map crashes
            carriers = [e for e in enemies if e["has_flag"] == 1]
            if carriers:
                carrier = carriers[0]
                cx, cy = carrier["x"], carrier["y"]
                
                if 0 <= cx < BOARD_SIZE and 0 <= cy < BOARD_SIZE:
                    targets.add((cx, cy))
                    if TERRITORY_MAP[cx][cy] != enemy_team:
                        for _, dx, dy in MOVES:
                            nx, ny = cx + dx, cy + dy
                            if 0 <= nx < BOARD_SIZE and 0 <= ny < BOARD_SIZE:
                                targets.add((nx, ny))
            else:
                _, dist_me = find_path(me["x"], me["y"], me["hydration"], {enemy_flag}, danger_cells, obstacle_map, cost_map)
                _, dist_team = find_path(teammate["x"], teammate["y"], teammate["hydration"], {enemy_flag}, danger_cells, obstacle_map, cost_map)

                is_attacker = False
                if dist_me < dist_team:
                    is_attacker = True
                elif dist_me == dist_team:
                    if me["x"] != teammate["x"]:
                        is_attacker = me["x"] < teammate["x"]
                    else:
                        is_attacker = me["y"] < teammate["y"]

                if is_attacker:
                    targets.add(enemy_flag)
                else:
                    invaders = [e for e in enemies if e["x"] != -1 and 0 <= e["x"] < BOARD_SIZE and 0 <= e["y"] < BOARD_SIZE and TERRITORY_MAP[e["x"]][e["y"]] == our_team]
                    if invaders:
                        for invader in invaders:
                            for _, dx, dy in MOVES:
                                nx, ny = invader["x"] + dx, invader["y"] + dy
                                if 0 <= nx < BOARD_SIZE and 0 <= ny < BOARD_SIZE:
                                    targets.add((nx, ny))
                    else:
                        targets.add(enemy_flag)

        # Execute searches
        move, _ = find_path(me["x"], me["y"], me["hydration"], targets, danger_cells, obstacle_map, cost_map)

        if move is None:
            move, _ = find_path(me["x"], me["y"], me["hydration"], OASIS_CELLS, danger_cells, obstacle_map, cost_map)

        if move is None:
            for fallback_move, dx, dy in MOVES:
                nx, ny = me["x"] + dx, me["y"] + dy
                if 0 <= nx < BOARD_SIZE and 0 <= ny < BOARD_SIZE and not obstacle_map[nx][ny]:
                    move = fallback_move
                    break
            else:
                move = "s"

        print(move, flush=True)

if __name__ == "__main__":
    main()