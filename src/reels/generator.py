"""Seeded count-preserving construction; payout rules belong to game adapters."""
from collections import Counter
import random


def validate(strip, window_height, visible_limits):
    if not isinstance(window_height, int) or not 1 <= window_height <= len(strip):
        raise ValueError('Invalid window height')
    for symbol, limit in visible_limits.items():
        if not isinstance(limit, int) or not 0 <= limit <= window_height:
            raise ValueError('Invalid visible limit')
        for stop in range(len(strip)):
            if sum(strip[(stop + row) % len(strip)] == symbol for row in range(window_height)) > limit:
                raise ValueError('Visible limit violated, including wraparound')


def construct(counts, *, seed, window_height=3, visible_limits=None, attempts=10000):
    """Bounded rejection construction. Impossible or difficult inputs fail explicitly.

    Uniform stops on the resulting strip are assumed. This does not claim a
    uniform distribution over all possible legal strip arrangements.
    """
    limits = visible_limits or {}
    if not counts or any(not isinstance(n, int) or n <= 0 for n in counts.values()):
        raise ValueError('Counts must be positive integers')
    strip = [s for s, n in sorted(counts.items()) for _ in range(n)]
    if not isinstance(window_height, int) or not 1 <= window_height <= len(strip):
        raise ValueError('Invalid window height')
    for s, limit in limits.items():
        if not isinstance(limit, int) or not 0 <= limit <= window_height:
            raise ValueError('Invalid visible limit')
        if counts.get(s, 0) * window_height > limit * len(strip):
            raise ValueError('Impossible visible-symbol density')
    rng = random.Random(seed)
    for _ in range(attempts):
        rng.shuffle(strip)
        try:
            validate(strip, window_height, limits)
        except ValueError:
            continue
        return strip.copy()
    raise ValueError('Construction attempt budget exhausted; change constraints or seed')


def visible_count_probabilities(strip, symbol, window_height=3):
    hist = Counter(sum(strip[(stop+r) % len(strip)] == symbol for r in range(window_height))
                   for stop in range(len(strip)))
    return {k: n / len(strip) for k, n in sorted(hist.items())}


def trigger_probability(strips, symbol, minimum, window_height=3):
    """Exact enumeration of per-reel count distributions, independent uniform stops."""
    totals = {0: 1.0}
    for strip in strips:
        nxt = Counter()
        for a, p in totals.items():
            for b, q in visible_count_probabilities(strip, symbol, window_height).items():
                nxt[a+b] += p*q
        totals = nxt
    return sum(p for n, p in totals.items() if n >= minimum)
