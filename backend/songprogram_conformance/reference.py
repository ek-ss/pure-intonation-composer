"""Independent SP0 NumericContract and exhaustive chord oracle.

This module must remain independent of production helpers.
"""

from __future__ import annotations

from decimal import Decimal, DivisionByZero, InvalidOperation, Overflow, ROUND_HALF_EVEN, localcontext
from fractions import Fraction
from itertools import combinations, permutations, product
from math import gcd
from typing import Any, Callable

PRECISIONS = (80, 112, 144, 176, 208, 240, 256)


def _rhe(value: Decimal) -> int:
    return int(value.to_integral_value(rounding=ROUND_HALF_EVEN))


def _stable_integer(compute: Callable[[], int]) -> int:
    previous: int | None = None
    for precision in PRECISIONS:
        with localcontext() as context:
            context.prec = precision
            context.rounding = ROUND_HALF_EVEN
            context.Emin, context.Emax = -999_999, 999_999
            context.traps[InvalidOperation] = True
            context.traps[DivisionByZero] = True
            context.traps[Overflow] = True
            current = compute()
        if current == previous:
            return current
        previous = current
    raise ArithmeticError("NUMERIC_INDETERMINATE")


def parse_ratio(text: str) -> Fraction:
    numerator_text, denominator_text = text.split("/", 1)
    numerator, denominator = int(numerator_text), int(denominator_text)
    if numerator <= 0 or denominator <= 0 or gcd(numerator, denominator) != 1:
        raise ValueError("ratio must be positive and reduced")
    return Fraction(numerator, denominator)


def ratio_text(value: Fraction) -> str:
    return f"{value.numerator}/{value.denominator}"


def ratio_mc(value: Fraction) -> int:
    if value <= 0:
        raise ValueError("ratio must be positive")

    def compute() -> int:
        numerator = Decimal(value.numerator)
        denominator = Decimal(value.denominator)
        return _rhe(Decimal(1_200_000) * (numerator.ln() - denominator.ln()) / Decimal(2).ln())

    return _stable_integer(compute)


def edo_phase_mc(equave: Fraction, divisions: int, step: int) -> int:
    if equave <= 1 or divisions < 1:
        raise ValueError("invalid EDO reference")
    canonical_step = step % divisions

    def compute() -> int:
        log2_equave = (
            Decimal(equave.numerator).ln() - Decimal(equave.denominator).ln()
        ) / Decimal(2).ln()
        return _rhe(Decimal(1_200_000) * log2_equave * canonical_step / divisions)

    return _stable_integer(compute)


def wrap_mc(value: int, period: int) -> int:
    if period <= 0:
        raise ValueError("period must be positive")
    return ((value + period // 2) % period) - period // 2


def pair_rms_mc(errors: tuple[int, ...]) -> int:
    if not errors:
        raise ValueError("RMS requires errors")

    def compute() -> int:
        mean_square = Decimal(sum(error * error for error in errors)) / len(errors)
        return _rhe(mean_square.sqrt())

    return _stable_integer(compute)


def _equave_reduce(value: Fraction, equave: Fraction) -> Fraction:
    if value <= 0 or equave <= 1:
        raise ValueError("invalid reduction")
    while value >= equave:
        value /= equave
    while value < 1:
        value *= equave
    return value


def odd_limit(value: Fraction, equave: Fraction) -> int:
    reduced = _equave_reduce(value, equave)

    def odd_part(component: int) -> int:
        while component % 2 == 0:
            component //= 2
        return component

    return max(odd_part(reduced.numerator), odd_part(reduced.denominator))


def chord_complexity(ratios: tuple[Fraction, ...], equave: Fraction) -> int:
    total = 0
    for left, right in combinations(ratios, 2):
        relation = _equave_reduce(max(left, right) / min(left, right), equave)
        total += relation.numerator.bit_length() + relation.denominator.bit_length() - 2
    return total


def _vector_ratio(generators: tuple[Fraction, ...], vector: tuple[int, ...], equave: Fraction, exponent: int) -> Fraction:
    value = Fraction(1)
    if len(generators) != len(vector):
        raise ValueError("dimension mismatch")
    for generator, power_value in zip(generators, vector):
        value *= generator**power_value
    return value * equave**exponent


def validate_query(query: dict[str, Any]) -> None:
    if query.get("schema") != "cps.sp0-oracle-query/v1":
        raise ValueError("invalid query schema")
    domain, intent, anchor = query["domain"], query["intent"], query["anchor"]
    generators = tuple(parse_ratio(value) for value in domain["generators"])
    bounds = tuple(tuple(value) for value in domain["coordinate_bounds"])
    vector = tuple(anchor["vector"])
    if len(generators) != len(bounds) or len(vector) != len(generators):
        raise ValueError("dimension mismatch")
    if any(low > high for low, high in bounds):
        raise ValueError("invalid coordinate bounds")
    if any(not low <= coordinate <= high for coordinate, (low, high) in zip(vector, bounds)):
        raise ValueError("anchor outside domain")
    canonical_steps = [step % intent["reference_divisions"] for step in intent["steps"]]
    phases = [edo_phase_mc(parse_ratio(intent["reference_equave"]), intent["reference_divisions"], step) for step in canonical_steps]
    if len(set(phases)) != len(phases):
        raise ValueError("duplicate target phase")
    if intent["bass_policy"] == "preserve_target" and intent["bass_target_ordinal"] != 0:
        raise ValueError("pack fixes anchor to canonical target ordinal zero")


def resolve_exact(query: dict[str, Any]) -> dict[str, Any]:
    validate_query(query)
    domain, intent, anchor = query["domain"], query["intent"], query["anchor"]
    equave = parse_ratio(domain["equave"])
    generators = tuple(parse_ratio(value) for value in domain["generators"])
    bounds = tuple(tuple(value) for value in domain["coordinate_bounds"])
    register_low, register_high = domain["register_bounds"]
    anchor_vector = tuple(anchor["vector"])
    anchor_exponent = anchor["equave_exponent"]
    anchor_ratio = _vector_ratio(generators, anchor_vector, equave, anchor_exponent)
    reference_equave = parse_ratio(intent["reference_equave"])
    period = ratio_mc(reference_equave)

    targets = sorted(
        ((edo_phase_mc(reference_equave, intent["reference_divisions"], step), step % intent["reference_divisions"]) for step in intent["steps"])
    )
    canonical_steps = [step for _, step in targets]
    target_phases = [phase for phase, _ in targets]
    voice_count = len(targets)

    placed_by_ratio: dict[Fraction, tuple[tuple[int, ...], int, Fraction]] = {}
    axes = [range(low, high + 1) for low, high in bounds]
    for vector_value in product(*axes):
        vector = tuple(vector_value)
        for exponent in range(register_low, register_high + 1):
            ratio = _vector_ratio(generators, vector, equave, exponent)
            reduced = _equave_reduce(ratio, equave)
            complexity_bits = reduced.numerator.bit_length() + reduced.denominator.bit_length()
            if odd_limit(ratio, equave) > domain["maximum_odd_limit"] or complexity_bits > domain["maximum_reduced_complexity_bits"]:
                continue
            placed_by_ratio.setdefault(ratio, (vector, exponent, ratio))
    placed = sorted(placed_by_ratio.values(), key=lambda item: (item[0], item[1]))
    anchor_pitch = (anchor_vector, anchor_exponent, anchor_ratio)
    non_anchor = [pitch for pitch in placed if pitch[2] != anchor_ratio]

    best: tuple[Any, dict[str, Any]] | None = None
    examined = 0
    for selected in combinations(non_anchor, voice_count - 1):
        for assigned_tail in permutations(selected):
            examined += 1
            voices = (anchor_pitch, *assigned_tail)
            ratios = tuple(voice[2] for voice in voices)
            absolute = [ratio_mc(value) for value in ratios]
            height_order = sorted(range(voice_count), key=lambda index: (absolute[index], ratios[index].numerator, ratios[index].denominator, voices[index][0], voices[index][1]))
            if len(set(ratios)) != voice_count:
                continue
            adjacent = [absolute[right] - absolute[left] for left, right in zip(height_order, height_order[1:])]
            if min(adjacent) < intent["minimum_spacing_millicents"]:
                continue
            if absolute[height_order[-1]] - absolute[height_order[0]] > intent["maximum_span_millicents"]:
                continue
            if intent["bass_policy"] == "preserve_target" and height_order[0] != intent["bass_target_ordinal"]:
                continue
            errors = []
            for left, right in combinations(range(voice_count), 2):
                target_interval = wrap_mc(target_phases[right] - target_phases[left], period)
                actual_interval = wrap_mc(ratio_mc(ratios[right] / ratios[left]), period)
                errors.append(wrap_mc(actual_interval - target_interval, period))
            error_tuple = tuple(errors)
            maximum = max(abs(value) for value in errors)
            rms = pair_rms_mc(error_tuple)
            complexity = chord_complexity(ratios, reference_equave)
            if maximum > intent["maximum_pair_error_millicents"] or rms > intent["maximum_pair_rms_millicents"] or complexity > intent["complexity_budget"]:
                continue
            assignment_key = tuple((absolute[index] % period, ratios[index].numerator, ratios[index].denominator, voices[index][0], voices[index][1]) for index in range(voice_count))
            canonical_shape_key = tuple((tuple(value - anchor_vector[axis] for axis, value in enumerate(voices[index][0])), voices[index][1] - anchor_exponent, ratios[index].numerator, ratios[index].denominator) for index in range(voice_count))
            score = (rms, maximum, complexity, assignment_key, canonical_shape_key)
            result = {
                "schema": "cps.sp0-oracle-result/v1",
                "search_completeness": "exact",
                "canonical_steps": canonical_steps,
                "vectors": [list(voice[0]) for voice in voices],
                "equave_exponents": [voice[1] for voice in voices],
                "exact_ratios": [ratio_text(value) for value in ratios],
                "pair_errors_millicents": list(error_tuple),
                "pair_max_millicents": maximum,
                "pair_rms_millicents": rms,
                "complexity_score": complexity,
                "score_prefix": [rms, maximum, complexity],
                "examined_assignments": 0,
            }
            if best is None or score < best[0]:
                best = (score, result)
    if best is None:
        raise ValueError("NO_JOINT_CHORD_SOLUTION")
    best[1]["examined_assignments"] = examined
    return best[1]
