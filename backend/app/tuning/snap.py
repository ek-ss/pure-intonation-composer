from __future__ import annotations

from fractions import Fraction
from math import gcd, log2

from app.tuning.ratios import reduce_to_octave


def _primes_up_to(limit: int) -> list[int]:
    sieve = [True] * (limit + 1)
    sieve[0] = sieve[1] = False
    for number in range(2, int(limit**0.5) + 1):
        if sieve[number]:
            sieve[number * number :: number] = [False] * len(sieve[number * number :: number])
    return [number for number in range(2, limit + 1) if sieve[number]]


def _smooth_numbers(limit: int, primes: list[int]) -> list[int]:
    numbers = {1}
    for prime in primes:
        for value in list(numbers):
            while value * prime <= limit:
                value *= prime
                numbers.add(value)
    return sorted(numbers)


def snap_ratio(ratio: Fraction, mode: str, value: int) -> Fraction:
    """Snap a ratio to the nearest EDO step or prime-limit rational.

    ``mode='edo'`` rounds the cents value to the nearest multiple of
    ``1200 / value``. ``mode='prime_limit'`` searches reduced ratios in the
    octave [1, 2) whose numerator and denominator are built only from primes
    up to ``value`` (and are at most 10_000) and returns the closest in cents.
    """
    if ratio <= 0:
        raise ValueError("ratio must be positive")
    if not isinstance(value, int) or value < 2:
        raise ValueError("value must be an integer >= 2")
    target_cents = 1200 * log2(float(ratio))
    if mode == "edo":
        step = 1200 / value
        snapped = round(target_cents / step) * step
        return Fraction(2 ** (snapped / 1200)).limit_denominator(1_000_000)
    if mode == "prime_limit":
        bound = min(value * 40, 10_000)
        numbers = _smooth_numbers(bound, _primes_up_to(value))
        target = 1200 * log2(float(reduce_to_octave(ratio)))
        best: Fraction | None = None
        best_distance = float("inf")
        for numerator in numbers:
            for denominator in numbers:
                if numerator < denominator or numerator >= 2 * denominator:
                    continue
                if gcd(numerator, denominator) != 1:
                    continue
                candidate = Fraction(numerator, denominator)
                distance = abs(1200 * log2(float(candidate)) - target)
                if distance < best_distance:
                    best = candidate
                    best_distance = distance
        if best is None:
            raise ValueError("no prime-limit candidate found")
        return best
    raise ValueError(f"unknown snap mode: {mode}")
