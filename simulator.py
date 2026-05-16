import sys
import subprocess
import time

import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
import numpy as np

BOARD_SIZE = 31
MAX_ROUNDS = 512

MOVES = {
    "u": (0, -1),
    "d": (0, 1),
    "l": (-1, 0),
    "r": (1, 0)
}

class TerritoryWarsSimulator:
    def __init__(self, bot_commands):
        self.board = [[-1 for _ in range(BOARD_SIZE)] for _ in range(BOARD_SIZE)]
        self.positions = [(0, 0), (30, 0), (0, 30), (30, 30)]
        self.alive = [True] * 4
        self.scores = [1] * 4  # Start with 1 for the initial corner claim
        
        # Claim initial corners
        for i, (x, y) in enumerate(self.positions):
            self.board[y][x] = i

        # Start bot subprocesses
        self.bots = []
        for cmd in bot_commands:
            p = subprocess.Popen(
                [sys.executable, cmd],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                bufsize=1 # Line buffered
            )
            self.bots.append(p)

    def get_input_string_for_player(self, player_id):
        """Formats the input string exactly as the game server does."""
        order = [player_id] + [i for i in range(4) if i != player_id]
        coords = []
        for i in order:
            x, y = self.positions[i]
            coords.extend([str(x), str(y)])
        return " ".join(coords) + "\n"

    def calculate_ranking(self):
        """Calculates points based on pessimistic ranking."""
        sorted_players = sorted(enumerate(self.scores), key=lambda x: x[1], reverse=True)
        points = [0] * 4
        base_points = [3, 2, 1, 0]
        
        for i in range(4):
            # Find the worst rank that shares this score
            worst_rank = i
            for j in range(i, 4):
                if sorted_players[j][1] == sorted_players[i][1]:
                    worst_rank = j
            points[sorted_players[i][0]] = base_points[worst_rank]
            
        return points

    def play(self):
        print("Starting Territory Wars Simulation...")
        start_time = time.time()
        
        for round_num in range(MAX_ROUNDS):
            if not any(self.alive):
                break

            moves = [None] * 4
            
            # 1. Request moves from all alive players
            for i in range(4):
                if self.alive[i]:
                    try:
                        input_str = self.get_input_string_for_player(i)
                        self.bots[i].stdin.write(input_str)
                        self.bots[i].stdin.flush()
                        
                        move = self.bots[i].stdout.readline().strip()
                        if move in MOVES:
                            moves[i] = move
                        else:
                            self.alive[i] = False
                            print(f"Player {i} died (Invalid move: '{move}')")
                    except Exception:
                        self.alive[i] = False
                        print(f"Player {i} died (Crash or timeout)")

            # 2. Calculate intended next positions
            next_positions = [None] * 4
            for i in range(4):
                if self.alive[i] and moves[i]:
                    cx, cy = self.positions[i]
                    dx, dy = MOVES[moves[i]]
                    next_positions[i] = (cx + dx, cy + dy)

            # 3. Evaluate collisions
            for i in range(4):
                if not self.alive[i]:
                    continue
                    
                nx, ny = next_positions[i]
                
                # Check bounds
                if not (0 <= nx < BOARD_SIZE and 0 <= ny < BOARD_SIZE):
                    self.alive[i] = False
                    continue
                    
                # Check already claimed territory
                if self.board[ny][nx] != -1:
                    self.alive[i] = False
                    continue
                    
                # Check head-to-head collisions (two players moving to same cell this turn)
                head_to_head = False
                for j in range(4):
                    if i != j and self.alive[j] and next_positions[i] == next_positions[j]:
                        head_to_head = True
                        break
                if head_to_head:
                    self.alive[i] = False

            # 4. Finalize moves for players who survived this round
            for i in range(4):
                if self.alive[i]:
                    nx, ny = next_positions[i]
                    self.positions[i] = (nx, ny)
                    self.board[ny][nx] = i
                    self.scores[i] += 1

        # Clean up subprocesses
        for bot in self.bots:
            bot.terminate()

        # Output Results
        print("\n--- Game Over ---")
        print(f"Duration: {time.time() - start_time:.2f} seconds")
        print(f"Rounds played: {round_num}")
        
        points = self.calculate_ranking()
        for i in range(4):
            status = "Alive" if self.alive[i] else "Dead"
            print(f"Player {i} ({sys.argv[i+1]}): {self.scores[i]:>4} cells | {points[i]} pts | {status}")

def visualize_board(board, scores, bot_names):
    """
    Renders the final 31x31 game board using matplotlib.
    """
    # Convert the board to a numpy array for matplotlib
    grid = np.array(board)

    # Define our color map mapping:
    # -1: Empty (Light Gray)
    #  0: Bot 0 (Blue)
    #  1: Bot 1 (Red)
    #  2: Bot 2 (Green)
    #  3: Bot 3 (Orange)
    cmap = ListedColormap(['#E0E0E0', '#3498db', '#e74c3c', '#2ecc71', '#f39c12'])
    
    # We set vmin=-1 and vmax=3 so the values map correctly to the colors
    plt.figure(figsize=(10, 10))
    plt.imshow(grid, cmap=cmap, vmin=-1, vmax=3)

    # Add gridlines to make individual cells visible
    ax = plt.gca()
    ax.set_xticks(np.arange(-.5, 31, 1), minor=True)
    ax.set_yticks(np.arange(-.5, 31, 1), minor=True)
    ax.grid(which="minor", color="white", linestyle='-', linewidth=1)
    ax.tick_params(which="minor", size=0)
    
    # Hide major ticks
    ax.set_xticks([])
    ax.set_yticks([])

    # Create a dynamic title with the final scores
    title_text = "Territory Wars - Final State\n"
    colors = ['Blue', 'Red', 'Green', 'Orange']
    for i in range(4):
        title_text += f"P{i} ({bot_names[i]}) [{colors[i]}]: {scores[i]} cells\n"
        
    plt.title(title_text.strip(), loc='left', pad=10, fontsize=12)
    plt.tight_layout()
    plt.show()


if __name__ == "__main__":
    if len(sys.argv) != 5:
        print("Usage: python simulator.py <bot1.py> <bot2.py> <bot3.py> <bot4.py>")
        sys.exit(1)
        
    sim = TerritoryWarsSimulator(sys.argv[1:5])
    sim.play()