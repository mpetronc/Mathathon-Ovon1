import sys
import random

TARGET = 999
HISTORY_WINDOW = 8

history = {1: [], 2: [], 3: []} 
last_cums = None

def calculate_variance(data):
    if len(data) < 2: return 0
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
        my_cum = players[0]['cumulative']
        my_cap = min(100, TARGET - my_pos)

        active_opponents = 0
        if last_cums is not None:
            for i in range(1, 4):
                bid = max(0, players[i]['cumulative'] - last_cums[i])
                is_alive = players[i]['position'] > 0 or players[i]['cumulative'] > 0 or bid > 0
                if is_alive:
                    active_opponents += 1
                    history[i].append(bid)
                    if len(history[i]) > HISTORY_WINDOW:
                        history[i].pop(0)

        last_cums = [p['cumulative'] for p in players]

        if active_opponents == 0 and not any(history.values()):
            active_opponents = 3

        active_variances = [calculate_variance(history[i]) for i in range(1, 4) if len(history[i]) > 3]
        is_chaotic_meta = active_variances and max(active_variances) > 300

        # ---------------------------------------------------------
        # Dynamic Bid Calculation
        # ---------------------------------------------------------
        if is_chaotic_meta or not active_variances:
            # DYNAMIC EV MAXIMIZATION (For Random Bots)
            if active_opponents >= 3: target_bid = 63
            elif active_opponents == 2: target_bid = 58
            else: target_bid = 50
            target_bid += random.randint(-1, 1)
            
        else:
            # ADVANCED STRUCTURED META (For Smart Bots)
            threats = []
            for i in range(1, 4):
                if history[i]:
                    typical = get_percentile(history[i], 0.75)
                    opp_cap = min(100, TARGET - players[i]['position'])
                    
                    # Endgame Projection: If they are within 100 points of winning, 
                    # they will abandon historical averages and push for the finish line.
                    if players[i]['position'] >= 899:
                         expected_bid = opp_cap
                    else:
                         expected_bid = typical
                         
                    threats.append({
                        'id': i,
                        'expected': expected_bid,
                        'cum': players[i]['cumulative']
                    })
            
            if threats:
                # Identify the apex predator in the lobby
                primary_threat = max(threats, key=lambda x: x['expected'])
                
                # THE SHIELD BASH (Offensive Tying)
                # Lowest cumulative gets blocked. If we have a strictly higher 
                # cumulative, we intentionally force a tie. They die, we move.
                if my_cum > primary_threat['cum']:
                    target_bid = primary_threat['expected']
                else:
                    target_bid = primary_threat['expected'] - 1
            else:
                target_bid = 63
                
            # NASH JITTER (Anti-Mirror Protocol)
            # Smart opponents are actively trying to undercut us. By introducing a 
            # 20% chance to drop 1-3 points, we break deterministic tracking loops
            # and become unexploitable to bots reading our history.
            if random.random() < 0.20:
                target_bid -= random.randint(1, 3)

        # Minimum threshold to avoid getting trapped in passive lobbies
        target_bid = max(40, target_bid)

        # Strict Endgame Clamping
        target_bid = min(target_bid, my_cap)
        target_bid = max(1, min(int(target_bid), 100))

        print(target_bid)
        sys.stdout.flush()

if __name__ == "__main__":
    main()