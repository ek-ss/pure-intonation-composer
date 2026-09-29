"""Bounded one-axis pitch search against an absolute 12-EDO reference window.

This is an index for selecting candidate pitches, not a SongProgram domain.
Only ``root + n * unit(axis)`` is examined; an equave lift changes register
without changing any of the other four coordinates.  In particular, no
five-axis Cartesian product is materialized or charged here.

The legacy 1D chord dictionary stops at the first approximate equave loop.
Coverage outside that loop is explicitly marked: a near-loop is not an exact
identity and cannot silently truncate a requested reference window.
"""

from __future__ import annotations

import math
from fractions import Fraction
from typing import Any, Sequence

from app.harmony_dictionary.authority import AXES_BY_EQUAVE, equave_ratio, loop_steps, reduce_on_equave
from app.songprogram.compiler import _mc
from app.tuning.ratios import ratio_text

AXIS_SEARCH_VERSION = "1.0.0"
MAX_RADIUS = 256
MAX_REFERENCE_NOTES = 24
REFERENCE_ERROR_MC = 50_000


class AxisSearchError(ValueError):
    """An axis-search request exceeds its versioned resource bounds."""


def _basis(equave_text: str) -> tuple[Fraction, tuple[int, ...]]:
    equave = equave_ratio(equave_text)
    if equave_text not in AXES_BY_EQUAVE:
        raise AxisSearchError("AXIS_EQUAVE_UNSUPPORTED")
    return equave, AXES_BY_EQUAVE[equave_text]


def reference_steps(equave_text: str) -> tuple[int, ...]:
    """12 octave semitones or 24 *absolute* semitones for a tritave.

    A 3/1 equave is about 19 semitones, not 12 or 24.  The 24-note window
    crosses the equave boundary; notes 19..23 retain their register/lift.
    """
    _basis(equave_text)
    return tuple(range(12 if equave_text == "2/1" else 24))


def _candidates_for_exponent(
    equave: Fraction, generator: int, n: int, last_target_mc: int, tolerance_mc: int
) -> list[dict[str, Any]]:
    # These floating bounds only choose a conservative range of lift integers.
    # Every actual boundary decision below uses exact rational -> integer cents.
    generator_mc = 1200 * math.log2(generator) * 1000
    equave_mc = 1200 * math.log2(float(equave)) * 1000
    low = math.ceil((n * generator_mc - last_target_mc - tolerance_mc) / equave_mc) - 1
    high = math.floor((n * generator_mc + tolerance_mc) / equave_mc) + 1
    result = []
    for k in range(low, high + 1):
        ratio = Fraction(generator) ** n / equave**k
        cents_mc = _mc(ratio)
        if -tolerance_mc <= cents_mc <= last_target_mc + tolerance_mc:
            result.append({
                "exponent": n,
                "equave_lift": -k,
                "ratio": ratio_text(ratio),
                "absolute_millicents": cents_mc,
            })
    return result


def axis_reference_coverage(
    equave_text: str,
    generator: int,
    *,
    radius_limit: int = MAX_RADIUS,
    tolerance_millicents: int = REFERENCE_ERROR_MC,
) -> dict[str, Any]:
    """Find the first symmetric axis radius that covers every reference note.

    Runtime is bounded by O(radius_limit * number_of_lifts * reference_notes),
    independently of the widths of all the other axes.  The returned points
    keep exact ratio, signed error, exponent and equave lift provenance.
    """
    equave, generators = _basis(equave_text)
    if type(generator) is not int or generator not in generators:
        raise AxisSearchError("AXIS_GENERATOR_UNSUPPORTED")
    if type(radius_limit) is not int or not 0 <= radius_limit <= MAX_RADIUS:
        raise AxisSearchError("AXIS_RADIUS_LIMIT_INVALID")
    if type(tolerance_millicents) is not int or not 0 <= tolerance_millicents <= REFERENCE_ERROR_MC:
        raise AxisSearchError("AXIS_TOLERANCE_INVALID")
    targets = reference_steps(equave_text)
    assert len(targets) <= MAX_REFERENCE_NOTES
    matches: dict[int, dict[str, Any]] = {}
    examined = 0
    first_radius = None
    last_target = targets[-1] * 100_000
    for radius in range(radius_limit + 1):
        for n in ((0,) if radius == 0 else (-radius, radius)):
            examined += 1
            for point in _candidates_for_exponent(equave, generator, n, last_target, tolerance_millicents):
                for step in targets:
                    error = point["absolute_millicents"] - step * 100_000
                    if abs(error) > tolerance_millicents:
                        continue
                    match = {**point, "signed_error_millicents": error}
                    previous = matches.get(step)
                    if previous is None or (
                        abs(error), abs(n), n, abs(point["equave_lift"]), point["equave_lift"]
                    ) < (
                        abs(previous["signed_error_millicents"]), abs(previous["exponent"]),
                        previous["exponent"], abs(previous["equave_lift"]), previous["equave_lift"]
                    ):
                        matches[step] = match
        if len(matches) == len(targets):
            first_radius = radius
            break
    loop = loop_steps(equave, generator)
    return {
        "version": AXIS_SEARCH_VERSION,
        "equave": equave_text,
        "generator": generator,
        "reference": "12-edo-absolute-12/v1" if equave_text == "2/1" else "12-edo-absolute-24/v1",
        "target_steps": list(targets),
        "tolerance_millicents": tolerance_millicents,
        "radius_limit": radius_limit,
        "first_coverage_radius": first_radius,
        "covered": first_radius is not None,
        "loop_steps": loop.n,
        "requires_beyond_first_loop": bool(first_radius is not None and loop.n is not None and first_radius >= loop.n),
        "examined_exponents": examined,
        "matches": {str(step): matches[step] for step in targets if step in matches},
        "missing_steps": [step for step in targets if step not in matches],
    }


def axis_pitch_at_root(
    equave_text: str, root_vector: Sequence[int], axis: int, exponent: int, equave_lift: int
) -> dict[str, Any]:
    """Place a selected 1D index point at an arbitrary five-coordinate root."""
    equave, generators = _basis(equave_text)
    if len(root_vector) != 5 or any(type(value) is not int for value in root_vector):
        raise AxisSearchError("AXIS_ROOT_VECTOR_INVALID")
    if type(axis) is not int or not 0 <= axis < 5:
        raise AxisSearchError("AXIS_INDEX_INVALID")
    if type(exponent) is not int or abs(exponent) > MAX_RADIUS:
        raise AxisSearchError("AXIS_EXPONENT_INVALID")
    if type(equave_lift) is not int or abs(equave_lift) > MAX_RADIUS * 5:
        raise AxisSearchError("AXIS_LIFT_INVALID")
    vector = list(root_vector)
    vector[axis] += exponent
    root_ratio = math.prod((Fraction(g) ** n for g, n in zip(generators, root_vector)), start=Fraction(1))
    ratio = root_ratio * Fraction(generators[axis]) ** exponent * equave**equave_lift
    return {
        "equave": equave_text,
        "axis": axis,
        "generator": generators[axis],
        "root_vector": list(root_vector),
        "vector": vector,
        "equave_lift": equave_lift,
        "root_ratio": ratio_text(root_ratio),
        "exact_ratio": ratio_text(ratio),
    }


def build_sparse_axis_chord(
    equave_text: str,
    root_vector: Sequence[int],
    generator: int,
    steps: Sequence[int],
    *,
    radius_limit: int = MAX_RADIUS,
    maximum_odd_limit: int = 4096,
    maximum_reduced_complexity_bits: int = 4096,
) -> dict[str, Any]:
    """Materialize only the selected 3/4 voices of one reference chord.

    This is an exact, single-axis *candidate*, not a GEN0-B compiled chord:
    the legacy resolver cannot accept its sparse placed-pitch list.  In
    particular we do not pretend that a rounded EDO step is the sounding pitch.
    """
    equave, generators = _basis(equave_text)
    if (
        type(maximum_odd_limit) is not int or not 1 <= maximum_odd_limit <= 65535
        or type(maximum_reduced_complexity_bits) is not int
        or not 2 <= maximum_reduced_complexity_bits <= 4096
    ):
        raise AxisSearchError("AXIS_RESOURCE_LIMIT_INVALID")
    if (
        len(steps) not in (3, 4)
        or any(type(step) is not int or step not in reference_steps(equave_text) for step in steps)
        or len(set(steps)) != len(steps)
        or 0 not in steps
    ):
        raise AxisSearchError("AXIS_CHORD_STEPS_INVALID")
    coverage = axis_reference_coverage(equave_text, generator, radius_limit=radius_limit)
    if not coverage["covered"]:
        raise AxisSearchError("AXIS_REFERENCE_COVERAGE_INSUFFICIENT")
    axis = generators.index(generator)
    voices = []
    for step in sorted(steps):
        point = coverage["matches"][str(step)]
        voice = axis_pitch_at_root(
            equave_text, root_vector, axis, point["exponent"], point["equave_lift"]
        )
        voice.update({"reference_step": step, "signed_error_millicents": point["signed_error_millicents"]})
        voices.append(voice)
    if len({voice["exact_ratio"] for voice in voices}) != len(voices):
        raise AxisSearchError("AXIS_CHORD_DUPLICATE_VOICE")
    resource_reasons: list[dict[str, Any]] = []
    for voice in voices:
        reduced, _ = reduce_on_equave(Fraction(voice["exact_ratio"]), equave)
        odd_numerator, odd_denominator = reduced.numerator, reduced.denominator
        while odd_numerator % 2 == 0:
            odd_numerator //= 2
        while odd_denominator % 2 == 0:
            odd_denominator //= 2
        if max(odd_numerator, odd_denominator) > maximum_odd_limit:
            resource_reasons.append({"step": voice["reference_step"], "reason": "ODD_LIMIT_EXCEEDED"})
        if reduced.numerator.bit_length() + reduced.denominator.bit_length() > maximum_reduced_complexity_bits:
            resource_reasons.append({"step": voice["reference_step"], "reason": "COMPLEXITY_BITS_EXCEEDED"})
    root = Fraction(voices[0]["exact_ratio"])
    return {
        "version": AXIS_SEARCH_VERSION,
        "status": "sparse_candidate_not_compiled",
        "equave": equave_text,
        "axis": axis,
        "generator": generator,
        "root_vector": list(root_vector),
        "coverage_radius": coverage["first_coverage_radius"],
        "requires_beyond_first_loop": coverage["requires_beyond_first_loop"],
        "reference_steps": sorted(steps),
        "voices": voices,
        "root_relative_ratios": [ratio_text(Fraction(voice["exact_ratio"]) / root) for voice in voices],
        "current_lattice_filter": {
            "maximum_odd_limit": maximum_odd_limit,
            "maximum_reduced_complexity_bits": maximum_reduced_complexity_bits,
            "reasons": resource_reasons,
            "passes": not resource_reasons,
        },
    }
