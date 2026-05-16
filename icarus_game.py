import sys
import random

TARGET = 999
HISTORY_WINDOW = 8

# Global state
history = {1: [] , 2: [], 3: []} 
last_cums = None

def calculate_variance(data):
    """Calculates the variance of a list of numbers to detect random/chaotic bots."""
    if len(data) < 2:
        return 0
    mean = sum(data) / len(data)
    return sum((x - mean) ** 2 for x in data) / len(data)

def get_percentile(data, percentile):
    if not data: return 0
    sorted_data = sorted(data)
    index = (len(sorted_data) - 1) * percentile
    return sorted_data[int(index)]

def main():
    global last_cums, history
    
    while True:
        try:
            raw_input = input()
            if not raw_input: break
        except EOFError: break

        values = [int(n) for n in raw_input.split()]
        if len(values) != 8:
            print(1)
            sys.stdout.flush()
            continue

        players = [{"position": values[i], "cumulative": values[i + 1]} for i in range(0, 8, 2)]

        my_pos = players[0]['position']
        my_cap = min(100, TARGET - my_pos)

        # ---------------------------------------------------------
        # State Update & Exact Bid Tracking
        # ---------------------------------------------------------
        active_opponents = 0
        
        if last_cums is not None:
            for i in range(1, 4):
                bid = max(0, players[i]['cumulative'] - last_cums[i])
                
                # Identify if opponent is alive. If they have a position > 0 or a cumulative > 0
                # they are in the game. Dead bots reset to 0/0.
                is_alive = players[i]['position'] > 0 or players[i]['cumulative'] > 0 or bid > 0
                
                if is_alive:
                    active_opponents += 1
                    history[i].append(bid)
                    if len(history[i]) > HISTORY_WINDOW:
                        history[i].pop(0)

        last_cums = [p['cumulative'] for p in players]

        # In round 0, we assume all 3 opponents are alive and chaotic.
        if active_opponents == 0 and not any(history.values()):
            active_opponents = 3

        # ---------------------------------------------------------
        # Meta Analysis (Chaotic vs Structured)
        # ---------------------------------------------------------
        active_variances = [calculate_variance(history[i]) for i in range(1, 4) if len(history[i]) > 3]
        
        # A uniform distribution U(1,100) has a theoretical variance of ~833.
        # Variance > 300 strongly indicates irrational/random behavior.
        is_chaotic_meta = active_variances and max(active_variances) > 300

        # ---------------------------------------------------------
        # Dynamic Bid Calculation
        # ---------------------------------------------------------
        if is_chaotic_meta or not active_variances:
            # DYNAMIC EV MAXIMIZATION
            # Optimal calculus derivations based on number of active chaotic threats
            if active_opponents >= 3:
                target_bid = 63
            elif active_opponents == 2:
                target_bid = 58
            else:
                target_bid = 50
                
            # +/- 1 jitter to prevent exact tracking by mirror bots
            target_bid += random.randint(-1, 1)
            
        else:
            # STRUCTURED UNDERCUTTING
            # If opponents are deterministic, we undercut their aggressive baseline
            active_profiles = [get_percentile(history[i], 0.75) for i in range(1, 4) if history[i]]
            most_aggressive = max(active_profiles) if active_profiles else 63
            target_bid = int(most_aggressive) - 1

        # Minimum threshold to avoid getting trapped in "Turtle" lobbies
        target_bid = max(40, target_bid)

        # ---------------------------------------------------------
        # Strict Endgame Clamping
        # ---------------------------------------------------------
        # Never, under any circumstances, bid more than the exact distance needed to win.
        target_bid = min(target_bid, my_cap)
        target_bid = max(1, min(target_bid, 100))

        print(int(target_bid))
        sys.stdout.flush()

if __name__ == "__main__":
    main()