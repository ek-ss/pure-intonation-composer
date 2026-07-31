from __future__ import annotations

from collections import Counter
from fractions import Fraction
from itertools import product

from app.tuning.ratios import reduce_to_octave


def generate_euler_fokker(factors: list[int], octave_reduce: bool) -> list[Fraction]:
    """Generate the genus: all divisors of the supplied factor product."""
    counts = Counter(factors)
    primes = sorted(counts)
    values: set[Fraction] = set()
    for exponents in product(*(range(counts[prime] + 1) for prime in primes)):
        ratio = Fraction(1)
        for prime, exponent in zip(primes, exponents):
            ratio *= prime**exponent
        values.add(reduce_to_octave(ratio) if octave_reduce else ratio)
    return sorted(values)
