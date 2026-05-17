import sys
import random

prev_p = None
prev_c = None

hist = {1: [], 2: [], 3: []}
blocked = {1: False, 2: False, 3: False}

my_blocked = []
my_moves = []

reset_phase = 0
reset_cooldown = 0


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
    better = sum(1 for x in p[1:] if x > p[0])
    tied = sum(1 for x in p[1:] if x == p[0])
    return better + tied + 1


def downward_count():
    count = 0
    for i in (1, 2, 3):
        h = hist[i]
        if len(h) >= 3 and h[-1] < h[-2] < h[-3]:
            count += 1
        elif len(h) >= 2 and h[-1] <= h[-2] - 3:
            count += 1
    return count


def low_stall_detected(preds):
    if len(my_moves) < 14:
        return False

    # We have also been crawling.
    if max(my_moves[-14:]) > 3:
        return False

    # Opponents are predicted tiny.
    if max(preds) > 3:
        return False

    # At least two opponents have actually been tiny recently.
    tiny_opps = 0
    for i in (1, 2, 3):
        h = hist[i]
        if len(h) >= 8 and max(h[-8:]) <= 3:
            tiny_opps += 1

    return tiny_opps >= 2


def predict(i):
    h = hist[i]

    if not h:
        return 48

    last = h[-1]

    # Repeating bots are common.
    if len(h) >= 2 and h[-1] == h[-2]:
        return last

    # Linear trend.
    if len(h) >= 3:
        d1 = h[-1] - h[-2]
        d2 = h[-2] - h[-3]
        if d1 == d2 and -10 <= d1 <= 10:
            return clamp(last + d1)

    # If blocked, expect lowering, unless stubborn/repeating.
    if blocked[i]:
        if len(h) >= 3 and max(h[-3:]) - min(h[-3:]) <= 2:
            return last
        if last >= 85:
            return clamp(last - 10)
        if last >= 70:
            return clamp(last - 5)
        if last >= 55:
            return clamp(last - 2)
        return clamp(last - 2)

    a = avg(h[-5:])
    pred = (2 * last + a) / 3

    if a >= 85:
        pred -= 4
    elif a >= 70:
        pred -= 1

    return clamp(pred)


def shield_is_stable(preds):
    maxp = max(preds)
    top_i = preds.index(maxp) + 1
    h = hist[top_i]

    if len(h) < 3:
        return False

    recent = h[-3:]

    # Medium shields can be useful even if blocked,
    # as long as they keep repeating around 55-70.
    return min(recent) >= 55 and max(recent) - min(recent) <= 6


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


def make_scenarios(preds):
    scenarios = [
        preds[:],
        [clamp(x - 2) for x in preds],
        [clamp(x + 2) for x in preds],
        [clamp(preds[0] - 1), preds[1], clamp(preds[2] + 1)],
        [clamp(preds[0] + 1), clamp(preds[1] - 1), preds[2]],
    ]

    last_based = []
    for i in (1, 2, 3):
        last_based.append(hist[i][-1] if hist[i] else preds[i - 1])
    scenarios.append(last_based)

    maxp = max(preds)
    top_i = preds.index(maxp)

    # Very high lobbies often collapse from 90/100 toward 60-75.
    if maxp >= 85:
        scenarios.append([
            clamp(x - 20) if x >= 85 else x
            for x in preds
        ])

        scenarios.append([
            clamp(min(x, 75)) if x >= 85 else x
            for x in preds
        ])

    elif shield_is_stable(preds):
        dropped = preds[:]
        dropped[top_i] = clamp(dropped[top_i] - 3)
        scenarios.append(dropped)

    else:
        dropped = preds[:]
        dropped[top_i] = clamp(dropped[top_i] - 7)
        scenarios.append(dropped)

        dropped_more = preds[:]
        dropped_more[top_i] = clamp(dropped_more[top_i] - 11)
        scenarios.append(dropped_more)

    if maxp < 50:
        scenarios.append([clamp(x - 4) for x in preds])

    if maxp < 45:
        scenarios.append([clamp(x - 6) for x in preds])

    return scenarios


def choose_candidates(preds, p):
    maxp = max(preds)
    minp = min(preds)
    second = sum(preds) - maxp - minp

    candidates = set()

    # Very high shield mode: 85+
    if maxp >= 85:
        for d in range(18, 31):
            candidates.add(maxp - d)

        if second >= 70:
            for d in range(10, 24):
                candidates.add(second - d)

        for x in [58, 60, 62, 64, 66, 68, 70, 72, 74, 76, 78, 80]:
            candidates.add(x)

    # Normal high shield mode: 70-84
    elif maxp >= 70:
        for d in range(8, 18):
            candidates.add(maxp - d)

        if second >= 55:
            for d in range(5, 12):
                candidates.add(second - d)

        for x in [50, 52, 55, 58, 60, 62, 64, 66, 68]:
            candidates.add(x)

    # Medium shield mode: 55-69
    elif maxp >= 55:
        for d in range(1, 11):
            candidates.add(maxp - d)

        if second >= 45:
            for d in range(2, 8):
                candidates.add(second - d)

        for x in [40, 42, 45, 48, 50, 52, 54, 55, 56, 57, 58, 59, 60]:
            candidates.add(x)

    # 50-54 transition
    elif maxp >= 50:
        for d in range(2, 14):
            candidates.add(maxp - d)

        for x in [35, 37, 38, 39, 40, 42, 44, 46, 48, 50]:
            candidates.add(x)

    # Under-50 mode
    else:
        for d in range(1, 14):
            candidates.add(maxp - d)

        for x in [
            1, 2, 3, 4, 5, 6, 8, 10, 12, 14, 16, 18,
            20, 22, 24, 26, 28, 30, 32, 34, 35, 36,
            37, 38, 39, 40, 41
        ]:
            candidates.add(x)

        if maxp - minp >= 6:
            for d in range(1, 7):
                candidates.add(maxp - d)

    recent_blocks = sum(my_blocked[-5:])

    if my_blocked and my_blocked[-1]:
        for d in range(5, 22):
            candidates.add(maxp - d)

    if recent_blocks >= 2:
        for x in [1, 2, 4, 6, 8, 10, 14, 18, 22, 26, 30, 34]:
            candidates.add(x)

    need = 999 - p[0]
    if 1 <= need <= 100:
        candidates.add(need)

    cleaned = set()

    for x in candidates:
        x = clamp(x, 1, 99)

        # Allow tiny moves when field has collapsed.
        if maxp > 25 and x < 10:
            x = 10

        cleaned.add(x)

    return cleaned


def tie_risk_penalty(x, preds, c):
    penalty = 0

    for j, pred in enumerate(preds, start=1):
        if x == pred and c[0] + x <= c[j] + pred:
            penalty += 240

    return penalty


def score_candidate(x, preds, p, c):
    maxp = max(preds)
    minp = min(preds)
    spread = maxp - minp
    rank = rank_of_me(p)
    recent_blocks = sum(my_blocked[-5:])
    down = downward_count()

    score = 0

    for opps in make_scenarios(preds):
        if would_move(x, opps, c):
            score += x

            if p[0] + x >= 999:
                score += 7000
        else:
            penalty = 100 + x

            if rank <= 2:
                penalty += 45

            if recent_blocks:
                penalty += 40 * recent_blocks

            score -= penalty

    # Do not be predicted highest.
    if x >= maxp:
        score -= 340

    score -= tie_risk_penalty(x, preds, c)

    # Under-50 mode: relative, not fixed 37-40.
    if maxp < 50:
        if maxp - 4 <= x <= maxp - 2:
            score += 170

        if spread >= 6:
            if maxp - 3 <= x <= maxp - 1:
                score += 85
            if x <= minp + 1:
                score -= 100
        else:
            if x >= maxp - 1:
                score -= 190

        if down >= 2 and maxp <= 45:
            if maxp - 5 <= x <= maxp - 2:
                score += 200
            if x >= 37:
                score -= 150
            if x > maxp - 1:
                score -= 230

        if 37 <= x <= 40 and x < maxp and maxp >= 40:
            score += 35

        if maxp <= 38:
            if maxp - 4 <= x <= maxp - 2:
                score += 130
            if x >= 37:
                score -= 180

        if x < maxp - 10:
            score -= 60

        if x >= 42 and spread < 6:
            score -= 150

    # 50-54 transition.
    if 50 <= maxp < 55:
        if maxp - 5 <= x <= maxp - 2:
            score += 120
        if x < 35:
            score -= 80

    # 55-69 medium shield mode.
    if 55 <= maxp < 70:
        stable = shield_is_stable(preds)

        if stable:
            if maxp - 2 <= x <= maxp - 1:
                score += 320
            elif x == maxp - 3:
                score += 220
            elif maxp - 6 <= x <= maxp - 4:
                score += 90
        else:
            if maxp - 5 <= x <= maxp - 3:
                score += 190
            if x >= maxp - 2:
                score -= 110

        if x < 42:
            score -= 90

        if x >= maxp:
            score -= 340

    # 70-84 normal high shield mode.
    if 70 <= maxp < 85:
        if maxp - 15 <= x <= maxp - 7:
            score += 150

        if 58 <= x <= 68:
            score += 80

        if x >= maxp - 4:
            score -= 180

        if x < 45:
            score -= 90

    # 85+ very high shield mode.
    if maxp >= 85:
        if maxp - 28 <= x <= maxp - 18:
            score += 240

        if 68 <= x <= 78:
            score += 120

        if x >= maxp - 10:
            score -= 260

        if x < 55:
            score -= 80

    # Endgame / falling-behind pressure.
    lead_gap = max(p[1:]) - p[0]
    finish_pressure = max(p) >= 900 or any(1 <= 999 - pi <= 100 for pi in p[1:])

    # IMPORTANT CHANGE:
    # Only become aggressive if there is a real shield.
    has_shield = maxp >= 55 or spread >= 8

    if finish_pressure:
        if rank >= 3 and has_shield:
            score += x * 0.80
        elif rank >= 3:
            score += x * 0.25

        if has_shield and x < maxp - 8:
            score -= 80

    if has_shield:
        if lead_gap > 180:
            score += x * 0.70
        elif lead_gap > 100:
            score += x * 0.35
    else:
        # In tight low clusters, do not chase recklessly.
        if lead_gap > 180 and x < maxp:
            score += x * 0.20

    # Tournament rank behavior.
    if rank == 1:
        score -= max(0, x - 55) * 1.5
    elif rank == 4:
        score += x * 0.55

    # Small repetition penalty.
    if my_moves and x == my_moves[-1]:
        score -= 4

    if len(my_moves) >= 2 and x == my_moves[-1] == my_moves[-2]:
        score -= 10

    return score


def choose_move(p, c):
    global reset_phase, reset_cooldown

    # Opening: balanced.
    if prev_p is None:
        return random.choice([47, 48, 48, 48, 50])

    preds = [predict(1), predict(2), predict(3)]
    maxp = max(preds)

    if reset_cooldown > 0:
        reset_cooldown -= 1

    # Continue reset sequence once started.
    if reset_phase > 0:
        seq = [100, 89, 78]
        move = seq[reset_phase]
        reset_phase += 1

        if reset_phase >= len(seq):
            reset_phase = 0
            reset_cooldown = 20

        return move

    # Low-stall escape: stricter now.
    if reset_cooldown == 0 and low_stall_detected(preds):
        rank = rank_of_me(p)
        lead_gap = max(p[1:]) - p[0]

        # Only reset if we are badly placed.
        if rank == 4 or lead_gap > 80:
            reset_phase = 1
            return 100

    candidates = choose_candidates(preds, p)

    best_x = 39
    best_score = -10**18

    for x in candidates:
        s = score_candidate(x, preds, p, c)

        if s > best_score:
            best_score = s
            best_x = x

    # Final safety.
    if best_x >= maxp:
        best_x = maxp - 1

    if maxp > 25 and best_x < 10:
        best_x = 10

    return clamp(best_x, 1, 99)


for line in sys.stdin:
    try:
        vals = list(map(int, line.strip().split()))

        if len(vals) != 8:
            print(48 if prev_p is None else 39, flush=True)
            continue

        # Input: p0 c0 p1 c1 p2 c2 p3 c3
        p = [vals[0], vals[2], vals[4], vals[6]]
        c = [vals[1], vals[3], vals[5], vals[7]]

        if prev_p is not None and prev_c is not None:
            own_move = c[0] - prev_c[0]
            own_pos_change = p[0] - prev_p[0]

            if 1 <= own_move <= 100:
                my_moves.append(own_move)
                my_blocked.append(own_pos_change == 0)

                if len(my_moves) > 12:
                    my_moves.pop(0)

                if len(my_blocked) > 12:
                    my_blocked.pop(0)

            for i in [1, 2, 3]:
                move = c[i] - prev_c[i]
                pos_change = p[i] - prev_p[i]

                if 1 <= move <= 100:
                    hist[i].append(move)
                    blocked[i] = (pos_change == 0)

                    if len(hist[i]) > 12:
                        hist[i].pop(0)

        move = choose_move(p, c)
        print(move, flush=True)

        prev_p = p
        prev_c = c

    except Exception:
        print(48 if prev_p is None else 39, flush=True)
