from __future__ import annotations

from fractions import Fraction


def parse_ratio(value: str) -> Fraction:
    numerator, denominator = value.split("/", maxsplit=1)
    ratio = Fraction(int(numerator), int(denominator))
    if ratio <= 0:
        raise ValueError("ratio must be positive")
    return ratio


def reduce_to_octave(ratio: Fraction) -> Fraction:
    """Move a positive ratio into the half-open interval [1, 2)."""
    while ratio >= 2:
        ratio /= 2
    while ratio < 1:
        ratio *= 2
    return ratio


def ratio_text(ratio: Fraction) -> str:
    return f"{ratio.numerator}/{ratio.denominator}"
