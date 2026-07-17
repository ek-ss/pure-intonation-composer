from __future__ import annotations

from fractions import Fraction
from math import log2


def cents(ratio: Fraction) -> float:
    return 1200 * log2(float(ratio))


def _factor(value: int) -> dict[int, int]:
    factors: dict[int, int] = {}
    divisor = 2
    while divisor * divisor <= value:
        while value % divisor == 0:
            factors[divisor] = factors.get(divisor, 0) + 1
            value //= divisor
        divisor += 1 if divisor == 2 else 2
    if value > 1:
        factors[value] = factors.get(value, 0) + 1
    return factors


def monzo(ratio: Fraction) -> dict[str, int]:
    """Return a sparse prime-exponent vector for a rational interval."""
    result = _factor(ratio.numerator)
    for prime, exponent in _factor(ratio.denominator).items():
        result[prime] = result.get(prime, 0) - exponent
    return {str(prime): exponent for prime, exponent in sorted(result.items()) if exponent}
