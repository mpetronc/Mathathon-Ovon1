import sys
import random

prev_p = None
prev_c = None

hist = {1: [], 2: [], 3: []}
blocked = {1: False, 2: False, 3: False}


def clamp(x, lo=1, hi=100):
    return max(lo, min(hi, int(round(x))))


def predict(i):
    h = hist[i]

    if not h:
        return 50  # after first round, if still no info, assume middle-ish play

    last = h[-1]

    # Repeating bot
    if len(h) >= 2 and h[-1] == h[-2]:
        return last

    # If they got blocked, expect them to lower slightly
    if blocked[i]:
        return clamp(last - 2)

    # Otherwise average recent moves
    recent = h[-3:]
    return clamp(sum(recent) / len(recent))


def get_rank(my_pos, all_positions):
    # rank 1 = best, rank 4 = worst
    better = sum(1 for x in all_positions if x > my_pos)
    return better + 1


def choose_move(p, c):
    my_pos = p[0]

    # FIRST ROUND: fixed opening move
    if prev_p is None:
        return 48

    preds = [predict(1), predict(2), predict(3)]
    danger = max(preds)

    rank = get_rank(my_pos, p)

    # Endgame: finish only if safe
    need = 999 - my_pos
    if 1 <= need <= 100 and need < danger:
        return need

    # If ahead, play safer. If behind, play more aggressive.
    if rank == 1:
        margin = 4
    elif rank == 2:
        margin = 3
    elif rank == 3:
        margin = 2
    else:
        margin = 1

    move = danger - margin

    # Usually don't play below 10
    if danger > 10:
        move = max(10, move)

    # Avoid 100
    move = min(99, move)

    # Small randomness after first round
    move += random.choice([-1, 0, 0, 0, 1])

    if danger > 10:
        move = max(10, move)

    return clamp(move, 1, 99)


for line in sys.stdin:
    try:
        vals = list(map(int, line.strip().split()))

        if len(vals) != 8:
            print(48 if prev_p is None else 50, flush=True)
            continue

        # Input format:
        # p0 c0 p1 c1 p2 c2 p3 c3
        p = [vals[0], vals[2], vals[4], vals[6]]
        c = [vals[1], vals[3], vals[5], vals[7]]

        # Learn from last round
        if prev_p is not None:
            for i in [1, 2, 3]:
                move = c[i] - prev_c[i]
                pos_change = p[i] - prev_p[i]

                if 1 <= move <= 100:
                    hist[i].append(move)

                    if len(hist[i]) > 5:
                        hist[i].pop(0)

                    blocked[i] = (pos_change == 0)

        move = choose_move(p, c)
        print(move, flush=True)

        prev_p = p
        prev_c = c

    except Exception:
        # Never crash
        print(48 if prev_p is None else 50, flush=True)
