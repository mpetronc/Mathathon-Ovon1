import random

def get_best_move(values):
    # You can still parse the data, even if the bot is simple
    players = [
        {"position": values[i], "cumulative": values[i + 1]}
        for i in range(0, len(values), 2)
    ]
    return random.randint(1, 100)