import sys
import os
import importlib.util
from collections import defaultdict

class IcarusEngine:
    def __init__(self, bots):
        self.bots = bots
        self.num_players = len(bots)
        
    def format_state_for_player(self, player_idx, positions, cumulatives):
        # Creates the flat 'values' array exactly as input().split() would
        state = [positions[player_idx], cumulatives[player_idx]]
        for i in range(self.num_players):
            if i != player_idx:
                state.extend([positions[i], cumulatives[i]])
        return state

    def calculate_pessimistic_scores(self, positions):
        ranked = sorted(enumerate(positions), key=lambda x: x[1], reverse=True)
        groups = defaultdict(list)
        for idx, pos in ranked:
            groups[pos].append(idx)
            
        scores = [0] * self.num_players
        available_points = [3, 2, 1, 0]
        current_rank_ptr = 0
        
        for pos in sorted(groups.keys(), reverse=True):
            tied_players = groups[pos]
            num_tied = len(tied_players)
            try:
                points_for_group = available_points[current_rank_ptr + num_tied - 1]
            except IndexError:
                points_for_group = 0
                
            for idx in tied_players:
                scores[idx] = points_for_group
            current_rank_ptr += num_tied
            
        return scores

    def play_game(self):
        positions = [0] * self.num_players
        cumulatives = [0] * self.num_players
        alive = [True] * self.num_players
        
        while max(positions) < 999 and any(alive):
            moves = [0] * self.num_players
            
            # 1. Get moves using the 'values' array
            for i in range(self.num_players):
                if alive[i]:
                    values_array = self.format_state_for_player(i, positions, cumulatives)
                    try:
                        move = self.bots[i](values_array)
                        if not isinstance(move, int) or move < 1 or move > 100:
                            raise ValueError("Invalid output")
                        moves[i] = move
                    except Exception as e:
                        alive[i] = False
                        positions[i] = 0
                        cumulatives[i] = 0
                        moves[i] = 0

            # 2. Update cumulatives
            for i in range(self.num_players):
                if alive[i] and moves[i] > 0:
                    cumulatives[i] += moves[i]

            # 3. Icarus mechanic (blocking the highest)
            active_moves = [moves[i] for i in range(self.num_players) if alive[i]]
            if not active_moves:
                break
                
            highest_move = max(active_moves)
            highest_players = [i for i in range(self.num_players) if alive[i] and moves[i] == highest_move]
            
            blocked_players = []
            if len(highest_players) == 1:
                blocked_players = highest_players
            elif len(highest_players) > 1:
                lowest_cum = min(cumulatives[i] for i in highest_players)
                blocked_players = [i for i in highest_players if cumulatives[i] == lowest_cum]

            # 4. Advance unblocked
            for i in range(self.num_players):
                if alive[i] and i not in blocked_players and moves[i] > 0:
                    positions[i] += moves[i]

        return self.calculate_pessimistic_scores(positions)

def run_simulation(bots, bot_names, num_games=1000):
    print(f"Running {num_games} games...")
    total_scores = [0] * len(bots)
    engine = IcarusEngine(bots)
    
    for _ in range(num_games):
        scores = engine.play_game()
        for i in range(len(bots)):
            total_scores[i] += scores[i]
            
    print("\n--- SIMULATION RESULTS ---")
    for i in range(len(bots)):
        avg_score = total_scores[i] / num_games
        print(f"Player {i} ({bot_names[i]:<15}) | Avg: {avg_score:.3f} | Total: {total_scores[i]}")

if __name__ == "__main__":
    if len(sys.argv) < 5:
        print("Usage: python simulator.py <bot1.py> <bot2.py> <bot3.py> <bot4.py> [num_games]")
        sys.exit(1)

    bot_files = sys.argv[1:5]
    num_games = int(sys.argv[5]) if len(sys.argv) >= 6 else 1000

    competing_bots, bot_names = [], []

    for filepath in bot_files:
        module_name = os.path.basename(filepath).replace('.py', '')
        spec = importlib.util.spec_from_file_location(module_name, filepath)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        
        competing_bots.append(module.get_best_move)
        bot_names.append(module_name)
            
    run_simulation(competing_bots, bot_names, num_games=num_games)