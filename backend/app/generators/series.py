from __future__ import annotations

from fractions import Fraction

from app.tuning.ratios import reduce_to_octave


def harmonic_series(count: int, octave_reduce: bool) -> list[Fraction]:
    values = [Fraction(value, 1) for value in range(1, count + 1)]
    if octave_reduce:
        values = [reduce_to_octave(value) for value in values]
    return sorted(set(values))


def subharmonic_series(count: int, octave_reduce: bool) -> list[Fraction]:
    values = [Fraction(1, value) for value in range(1, count + 1)]
    if octave_reduce:
        values = [reduce_to_octave(value) for value in values]
    return sorted(set(values))
