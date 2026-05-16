import sys
import random

prev_p = None
prev_c = None

hist = {1: [], 2: [], 3: []}
blocked = {1: False, 2: False, 3: False}

my_blocked = []
my_moves = []


def clamp(x, lo=1, hi=100):
    x = int(round(x))
    if x < lo:
        return lo
    if x > hi:
        return hi
    return x


def avg(xs):
    return sum(xs) / len(xs) if xs else 0


def rank_of_me(p):
    # Rank 1 = best. Ties count against us.
    better = sum(1 for x in p[1:] if x > p[0])
    tied = sum(1 for x in p[1:] if x == p[0])
    return better + tied + 1


def predict(i):
    h = hist[i]

    if not h:
        return 47

    last = h[-1]

    # Repeating bot.
    if len(h) >= 3 and h[-1] == h[-2] == h[-3]:
        return last

    # Linear trend.
    if len(h) >= 3:
        d1 = h[-1] - h[-2]
        d2 = h[-2] - h[-3]
        if d1 == d2 and -8 <= d1 <= 8:
            return clamp(last + d1)

    # If blocked, expect lowering.
    if blocked[i]:
        if last >= 75:
            return clamp(last - 3)
        return clamp(last - 2)

    recent = h[-5:]
    a = avg(recent)

    # Conservative band.
    if a <= 45:
        return clamp((2 * last + a) / 3)

    # High bots often drift down.
    if a >= 75:
        return clamp((2 * last + a) / 3 - 1)

    return clamp((2 * last + a) / 3)


def would_move(my_x, opps, c):
    moves = [my_x] + opps

    new_c = [
        c[0] + my_x,
        c[1] + opps[0],
        c[2] + opps[1],
        c[3] + opps[2],
    ]

    highest = max(moves)

    if my_x < highest:
        return True

    if moves.count(highest) == 1:
        return False

    tied = [i for i, x in enumerate(moves) if x == highest]
    lowest_c = min(new_c[i] for i in tied)

    return new_c[0] > lowest_c


def tie_risk_penalty(x, preds, c):
    penalty = 0

    for j, pred in enumerate(preds, start=1):
        if x == pred and c[0] + x <= c[j] + pred:
            penalty += 220

    return penalty


def make_scenarios(preds):
    scenarios = []

    # Main prediction.
    scenarios.append(preds[:])

    # Opponents slightly lower.
    scenarios.append([clamp(x - 2) for x in preds])

    # Opponents slightly higher.
    scenarios.append([clamp(x + 2) for x in preds])

    # Mixed uncertainty.
    scenarios.append([clamp(preds[0] - 1), preds[1], clamp(preds[2] + 1)])
    scenarios.append([clamp(preds[0] + 1), clamp(preds[1] - 1), preds[2]])

    # Last actual moves, if available.
    last_based = []
    for i in [1, 2, 3]:
        if hist[i]:
            last_based.append(hist[i][-1])
        else:
            last_based.append(preds[i - 1])
    scenarios.append(last_based)

    # Conservative-meta scenario.
    if max(preds) <= 50:
        scenarios.append([
            clamp(min(42, max(35, preds[0]))),
            clamp(min(42, max(35, preds[1]))),
            clamp(min(42, max(35, preds[2]))),
        ])

    return scenarios


def choose_candidates(preds, p):
    maxp = max(preds)
    minp = min(preds)
    second = sum(preds) - maxp - minp

    candidates = set()

    # High-anchor mode: use high bots as shields.
    if maxp >= 75:
        for d in range(3, 18):
            candidates.add(maxp - d)

        if second >= 65:
            for d in range(2, 8):
                candidates.add(second - d)

        for x in [65, 68, 70, 72, 75, 78, 80, 82, 85, 88]:
            candidates.add(x)

    # Medium lobby.
    elif maxp >= 50:
        for d in range(5, 18):
            candidates.add(maxp - d)

        for x in [37, 38, 39, 40, 42, 44, 46, 48, 50, 52, 54]:
            candidates.add(x)

    # Conservative leaderboard lobby.
    else:
        for d in range(1, 12):
            candidates.add(maxp - d)

        # Strong band from logs: 37-40.
        for x in [34, 35, 36, 37, 38, 39, 40, 41]:
            candidates.add(x)

    # Anti-block recovery.
    recent_blocks = sum(my_blocked[-5:])

    if my_blocked and my_blocked[-1]:
        for d in range(8, 20):
            candidates.add(maxp - d)

    if recent_blocks >= 2:
        for x in [28, 30, 32, 34, 36, 38]:
            candidates.add(x)

    # Endgame exact finish.
    need = 999 - p[0]
    if 1 <= need <= 100:
        candidates.add(need)

    cleaned = set()

    for x in candidates:
        x = clamp(x, 1, 99)

        if maxp > 20 and x < 10:
            x = 10

        cleaned.add(x)

    return cleaned


def score_candidate(x, preds, p, c):
    maxp = max(preds)
    minp = min(preds)
    rank = rank_of_me(p)
    recent_blocks = sum(my_blocked[-5:])

    scenarios = make_scenarios(preds)

    score = 0

    for opps in scenarios:
        if would_move(x, opps, c):
            score += x

            if p[0] + x >= 999:
                score += 5000
        else:
            penalty = 90 + x

            if rank <= 2:
                penalty += 45

            if recent_blocks:
                penalty += 35 * recent_blocks

            score -= penalty

    # Never like being predicted highest.
    if x >= maxp:
        score -= 240

    # Avoid bad cumulative tie.
    score -= tie_risk_penalty(x, preds, c)

    # Conservative-meta tuning.
    if maxp <= 50:
        if 37 <= x <= 40:
            score += 120
        elif x == 41:
            score += 20
        elif x >= 42:
            score -= 90
        elif x <= 33:
            score -= 40

    # High-anchor tuning.
    if maxp >= 80:
        if x < 65:
            score -= 200
        elif 68 <= x <= 88:
            score += 50

    # If one bot is very low and one is higher, do not chase the low bot.
    if maxp - minp >= 15 and x <= minp + 2:
        score -= 150

    # Rank-based tournament behavior.
    if rank == 1:
        score -= max(0, x - 42) * 2
    elif rank == 4:
        score += x * 0.5

    # Avoid repeating exact same move too much.
    if my_moves and x == my_moves[-1]:
        score -= 5

    if len(my_moves) >= 2 and x == my_moves[-1] == my_moves[-2]:
        score -= 15

    return score


def choose_move(p, c):
    if prev_p is None:
        return random.choice([45, 46, 47, 47])

    preds = [predict(1), predict(2), predict(3)]
    maxp = max(preds)

    candidates = choose_candidates(preds, p)

    best_x = 39
    best_score = -10**18

    for x in candidates:
        s = score_candidate(x, preds, p, c)

        if s > best_score:
            best_score = s
            best_x = x

    # Final safety: do not be predicted highest.
    if best_x >= maxp:
        best_x = maxp - 1

    if maxp > 20 and best_x < 10:
        best_x = 10

    return clamp(best_x, 1, 99)


for line in sys.stdin:
    try:
        vals = list(map(int, line.strip().split()))

        if len(vals) != 8:
            print(46 if prev_p is None else 39, flush=True)
            continue

        # Input:
        # p0 c0 p1 c1 p2 c2 p3 c3
        p = [vals[0], vals[2], vals[4], vals[6]]
        c = [vals[1], vals[3], vals[5], vals[7]]

        if prev_p is not None and prev_c is not None:
            own_move = c[0] - prev_c[0]
            own_pos_change = p[0] - prev_p[0]

            if 1 <= own_move <= 100:
                my_moves.append(own_move)
                my_blocked.append(own_pos_change == 0)

                if len(my_moves) > 8:
                    my_moves.pop(0)

                if len(my_blocked) > 8:
                    my_blocked.pop(0)

            for i in [1, 2, 3]:
                move = c[i] - prev_c[i]
                pos_change = p[i] - prev_p[i]

                if 1 <= move <= 100:
                    hist[i].append(move)
                    blocked[i] = (pos_change == 0)

                    if len(hist[i]) > 8:
                        hist[i].pop(0)

        move = choose_move(p, c)

        print(move, flush=True)

        prev_p = p
        prev_c = c

    except Exception:
        print(46 if prev_p is None else 39, flush=True)
