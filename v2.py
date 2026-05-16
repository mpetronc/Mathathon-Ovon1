import random



BOARD_SIZE = 31



# board[y][x] is -1 for empty, 0 for me, and 1..3 for opponents

board = [[-1 for x in range(BOARD_SIZE)] for y in range(BOARD_SIZE)]



MOVES = [

    ("u", 0, -1),

    ("d", 0, 1),

    ("l", -1, 0),

    ("r", 1, 0),

]





def is_inside(x, y):

    return 0 <= x < BOARD_SIZE and 0 <= y < BOARD_SIZE





while True:

    # Input: my_x my_y opponent1_x opponent1_y opponent2_x opponent2_y opponent3_x opponent3_y

    positions = [int(n) for n in input().split()]

    player_positions = [positions[i : i + 2] for i in range(0, 8, 2)]



    for player_id, (x, y) in enumerate(player_positions):

        if is_inside(x, y):

            board[y][x] = player_id



    my_x, my_y = player_positions[0]

    safe_moves = []

    for move, dx, dy in MOVES:

        next_x = my_x + dx

        next_y = my_y + dy

        if is_inside(next_x, next_y) and board[next_y][next_x] in (-1, 0):

            safe_moves.append(move)



    print(random.choice(safe_moves or [move for move, dx, dy in MOVES]))

