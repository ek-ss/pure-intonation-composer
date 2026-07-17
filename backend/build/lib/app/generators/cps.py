from __future__ import annotations

from fractions import Fraction
from itertools import combinations

from app.tuning.ratios import reduce_to_octave


def generate_cps(factors: list[int], choose: int, kind: str, octave_reduce: bool) -> list[Fraction]:
    if choose > len(factors):
        raise ValueError("choose cannot be greater than the number of factors")
    ratios: set[Fraction] = set()
    for subset in combinations(factors, choose):
        product = Fraction(1)
        for factor in subset:
            product *= factor
        ratio = product if kind == "harmonic" else Fraction(1, 1) / product
        ratios.add(reduce_to_octave(ratio) if octave_reduce else ratio)
    return sorted(ratios)
