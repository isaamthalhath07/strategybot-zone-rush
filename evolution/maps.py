"""Seeded, content-deduplicated legal maps, with explicit distribution labels."""
import hashlib
import math
import random


def mirrored(quadrant):
    return [quadrant[min(r, 7-r)*4 + min(c, 7-c)] for r in range(8) for c in range(8)]


def valid(base):
    return (len(base) == 64 and all(type(v) is int and 1 <= v <= 3 for v in base)
            and all(base[r*8+c] == base[r*8+7-c] == base[(7-r)*8+c] for r in range(8) for c in range(8)))


def generate(count, seed, excluded=()):
    rng, seen, output = random.Random(seed), {tuple(base) for base in excluded}, []
    families = ("centre-biased",) * 6 + ("noisy-centre",) * 2 + ("uniform-stress", "rich-home-stress")
    attempts = 0
    while len(output) < count:
        attempts += 1
        if attempts > max(10000, count*100):
            raise ValueError("Requested map diversity exhausted")
        family = rng.choice(families)
        q = []
        for r in range(4):
            for c in range(4):
                mean = 1.1 + 1.8*(r+c)/6
                if family == "uniform-stress":
                    weights = [1, 1, 1]
                else:
                    width = 0.65 if family == "centre-biased" else 1.05
                    weights = [math.exp(-((v-mean)/width)**2/2) for v in (1, 2, 3)]
                q.append(rng.choices((1, 2, 3), weights)[0])
        if family == "rich-home-stress":
            q[0] = 3
        base = mirrored(q)
        key = tuple(base)
        if key in seen:
            continue
        seen.add(key)
        assert valid(base)
        output.append(dict(id=hashlib.sha256(bytes(base)).hexdigest(), base=base,
                           family=family, generator_seed=seed, draw=attempts))
    return output


def seat_token(map_index, episode):
    """200/map: 50 games per seat/token, pair counts 12/13; globally balanced."""
    seat = episode % 4
    token = ((episode//4 + seat + map_index) % 4) + 1
    return seat, token
