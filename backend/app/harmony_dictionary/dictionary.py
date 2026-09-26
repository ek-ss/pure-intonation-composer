"""Per-axis 1D chord dictionaries with bounded streaming.

Each dictionary is keyed by ``[equave, generator, voice count, version]``.
It does not enumerate all ``C(n, m)`` index tuples: max span, height from
root, interval diversity, and count caps are applied up front while
streaming candidates in deterministic order.  Different exact chords that
fall into the same 12-EDO approximation are kept as multiple variants under
one canonical pitch-class key, never collapsed.

The 12-EDO comparison uses root-relative *actual* interval widths: a tone at
1850 cents is not mechanically folded to -50 cents.  For the tritave equave
the circle is ~1901.955 cents and the interval vector uses that circle; for
the octave it is the usual 1200-cent / six-class vector.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_EVEN, localcontext
from fractions import Fraction
from itertools import combinations, permutations

from app.harmony_dictionary.authority import (
    DECIMAL_PRECISION,
    AuthorityError,
    AxisPoint,
    axis_index,
    loop_payload,
    reduce_on_equave,
)
from app.harmony_dictionary.templates import OTHER, TEMPLATES_VERSION, templates_for_voice_count
from app.tuning.ratios import ratio_text

DICT_VERSION = "1.0.0"

NOT_ENOUGH_AXIS_POINTS = "NOT_ENOUGH_AXIS_POINTS"
LOOP_NOT_FOUND_WITHIN_LIMIT = "LOOP_NOT_FOUND_WITHIN_LIMIT"


@dataclass(frozen=True)
class DictionaryPolicy:
    """Versioned resource bounds and gates for one axis dictionary.

    ``max_span_cents`` is 1300 (one octave plus a whole tone) so that
    lattice-native chords whose compact placement slightly exceeds an octave
    (e.g. the tritave 13-axis triad at 1273 cents) are admitted, while
    tritave-wide scatter is still rejected.
    """

    max_span_cents: float = 1300.0
    max_height_from_root: int = 32
    max_variants_per_key: int = 8
    max_entries: int = 512
    max_tuples_examined: int = 200_000
    template_match_tolerance_cents: float = 50.0
    pure_interval_tolerance_cents: float = 5.0

    def as_dict(self) -> dict[str, object]:
        return {
            "max_span_cents": self.max_span_cents,
            "max_height_from_root": self.max_height_from_root,
            "max_variants_per_key": self.max_variants_per_key,
            "max_entries": self.max_entries,
            "max_tuples_examined": self.max_tuples_examined,
            "template_match_tolerance_cents": self.template_match_tolerance_cents,
            "pure_interval_tolerance_cents": self.pure_interval_tolerance_cents,
        }


DEFAULT_POLICY = DictionaryPolicy()

# Versioned just-interval reference table (5-limit + 7-limit) for the "pure
# interval relation" diagnostic.  Intervals are compared root-relative on the
# equave circle, so the table covers [1, 3).
PURE_INTERVALS: tuple[tuple[str, Fraction], ...] = (
    ("1/1", Fraction(1)),
    ("16/15", Fraction(16, 15)),
    ("9/8", Fraction(9, 8)),
    ("10/9", Fraction(10, 9)),
    ("6/5", Fraction(6, 5)),
    ("5/4", Fraction(5, 4)),
    ("4/3", Fraction(4, 3)),
    ("45/32", Fraction(45, 32)),
    ("5/3", Fraction(5, 3)),
    ("3/2", Fraction(3, 2)),
    ("15/8", Fraction(15, 8)),
    ("8/5", Fraction(8, 5)),
    ("9/5", Fraction(9, 5)),
    ("16/9", Fraction(16, 9)),
    ("5/2", Fraction(5, 2)),
    ("9/4", Fraction(9, 4)),
    ("7/6", Fraction(7, 6)),
    ("8/7", Fraction(8, 7)),
    ("7/5", Fraction(7, 5)),
    ("9/7", Fraction(9, 7)),
    ("14/9", Fraction(14, 9)),
    ("7/4", Fraction(7, 4)),
    ("12/7", Fraction(12, 7)),
    ("7/3", Fraction(7, 3)),
)


def _cents_decimal(ratio: Fraction) -> Decimal:
    with localcontext() as context:
        context.prec = DECIMAL_PRECISION
        return (Decimal(ratio.numerator).ln() - Decimal(ratio.denominator).ln()) / Decimal(2).ln() * Decimal(1200)


# Precomputed once: the versioned just-interval table in cents.
_PURE_INTERVAL_CENTS: tuple[tuple[str, Decimal], ...] = tuple(
    (name, _cents_decimal(ratio)) for name, ratio in PURE_INTERVALS
)


def _semitone_cell(position_cents: float) -> int:
    """12-EDO semitone cell on the absolute semitone grid, mod 12."""
    value = Decimal(repr(position_cents)) / Decimal(100)
    return int(value.to_integral_value(rounding=ROUND_HALF_EVEN)) % 12


def _signed_12edo_error(position_cents: float) -> float:
    """Signed distance (cents) to the nearest 12-EDO semitone, no folding."""
    value = Decimal(repr(position_cents)) / Decimal(100)
    nearest = value.to_integral_value(rounding=ROUND_HALF_EVEN) * Decimal(100)
    return round(float(Decimal(repr(position_cents)) - nearest), 5)


def match_template(
    positions_cents: list[float],
    voice_count: int,
    *,
    tolerance_cents: float = 50.0,
) -> dict[str, object]:
    """Best 12-EDO template match for root-relative positions.

    Tries every template of the right size in every inversion (the template
    is re-rooted at each of its tones) and every tone permutation; minimizes
    max per-tone error first, then total absolute error, then name/inversion
    for determinism.  A template counts as a match only when every tone is
    within ``tolerance_cents`` of its assigned 12-EDO semitone (compared on
    the actual root-relative width, without folding ~1900 cents to 1200);
    otherwise the result is ``other`` (the best candidate is still reported).
    """
    if len(positions_cents) != voice_count:
        raise ValueError("positions and voice_count must agree")
    positions_dec = [Decimal(repr(position)) for position in positions_cents]
    best_key: tuple[float, float, str, int] | None = None
    best: dict[str, object] | None = None
    for name, shape in sorted(templates_for_voice_count(voice_count).items()):
        for inversion in range(voice_count):
            pivot = shape[inversion]
            rerooted = tuple(sorted((semitone - pivot) % 12 for semitone in shape))
            for perm in permutations(range(voice_count)):
                errors: list[float] = []
                matched_semitones: list[int] = []
                for index, position in enumerate(positions_cents):
                    base = Decimal(100) * rerooted[perm[index]]
                    lift = int(((positions_dec[index] - base) / Decimal(1200)).to_integral_value(rounding=ROUND_HALF_EVEN))
                    target = base + Decimal(1200) * lift
                    errors.append(abs(float(positions_dec[index] - target)))
                    matched_semitones.append(int(target / Decimal(100)))
                max_error = max(errors)
                key = (max_error, sum(errors), name, inversion)
                if best_key is None or key < best_key:
                    best_key = key
                    best = {
                        "name": name,
                        "inversion": inversion,
                        "matched_semitones": matched_semitones,
                        "max_error_cents": round(max_error, 5),
                        "total_error_cents": round(sum(errors), 5),
                    }
    assert best is not None and best_key is not None
    matched = best_key[0] <= tolerance_cents
    result = dict(best)
    result["matched"] = matched
    if not matched:
        result["name"] = OTHER
    return result


def _interval_vector(positions_cents: list[float], equave: Fraction) -> list[int]:
    """Interval vector on the equave circle (6 classes for 2/1, 10 for 3/1)."""
    equave_cents = Decimal(1200) * equave.numerator / equave.denominator
    class_count = 6 if equave == Fraction(2, 1) else 10
    positions_dec = [Decimal(repr(position)) for position in positions_cents]
    vector = [0] * class_count
    for i in range(len(positions_dec)):
        for j in range(i + 1, len(positions_dec)):
            difference = abs(positions_dec[i] - positions_dec[j])
            arc = min(difference, equave_cents - difference)
            index = int((arc / Decimal(100)).to_integral_value(rounding=ROUND_HALF_EVEN))
            index = max(1, min(class_count, index))
            vector[index - 1] += 1
    return vector


def _pure_interval_relation(
    first: Fraction, second: Fraction, equave: Fraction, tolerance_cents: float
) -> dict[str, object]:
    """Nearest versioned just interval for one exact root-relative pair."""
    interval, _ = reduce_on_equave(first / second, equave)
    cents = _cents_decimal(interval)
    best_name, best_distance = "1/1", Decimal("Infinity")
    for name, pure_cents in _PURE_INTERVAL_CENTS:
        distance = abs(cents - pure_cents)
        if distance < best_distance:
            best_name, best_distance = name, distance
    return {
        "ratio": ratio_text(interval),
        "cents": round(float(cents), 5),
        "nearest_pure": best_name,
        "distance_cents": round(float(best_distance), 5),
        "pure": bool(best_distance <= Decimal(tolerance_cents)),
    }


def _evaluate_combo(
    equave: Fraction,
    points: list[AxisPoint],
    combo: tuple[int, ...],
    policy: DictionaryPolicy,
) -> dict[str, object] | None:
    """Apply the versioned filters to one index tuple; return a variant or None."""
    voice_count = len(combo)
    positions = [points[index].reduced_cents for index in combo]

    root_position = min(positions)
    root_slot = positions.index(root_position)
    relative = [position - root_position for position in positions]

    if max(relative) > policy.max_span_cents:
        return None
    height = sum(abs(index - combo[root_slot]) for index in combo)
    if height > policy.max_height_from_root:
        return None
    cells = [_semitone_cell(position) for position in relative]
    if len(set(cells)) != voice_count:
        return None

    # Exact root-relative ratios with equave lifts into [1, E).  The variant
    # payload is ordered root-first so consumers can sound the chord directly.
    order = [root_slot, *[slot for slot in range(voice_count) if slot != root_slot]]
    root_ratio = points[combo[root_slot]].reduced_ratio
    ratios: list[Fraction] = []
    lifts: list[int] = []
    exact_cents: list[float] = []
    for slot in order:
        index = combo[slot]
        reduced = points[index].reduced_ratio
        lifted, exponent = reduce_on_equave(reduced / root_ratio, equave)
        ratios.append(lifted)
        lifts.append(exponent)
        exact_cents.append(round(float(_cents_decimal(lifted)), 5))

    signed_errors = [_signed_12edo_error(position) for position in exact_cents]
    cells = [_semitone_cell(position) for position in exact_cents]
    match = match_template(exact_cents, voice_count, tolerance_cents=policy.template_match_tolerance_cents)
    vector = _interval_vector(exact_cents, equave)

    relations: list[dict[str, object]] = []
    for i in range(voice_count):
        for j in range(i + 1, voice_count):
            relation = _pure_interval_relation(ratios[i], ratios[j], equave, policy.pure_interval_tolerance_cents)
            relations.append({"pair": [i, j], **relation})

    span = max(exact_cents)
    reason = (
        f"template={match['name']} inversion={match['inversion']} "
        f"max_err={match['max_error_cents']}c span={round(span, 1)}c height={height}"
    )
    return {
        "index_tuple": [combo[slot] for slot in order],
        "lifts": lifts,
        "ratios": [ratio_text(ratio) for ratio in ratios],
        "cents": exact_cents,
        "semitones": cells,
        "signed_errors_cents": signed_errors,
        "template": match["name"],
        "template_inversion": match["inversion"],
        "template_matched_semitones": match["matched_semitones"],
        "template_matched": match["matched"],
        "template_max_error_cents": match["max_error_cents"],
        "template_total_error_cents": match["total_error_cents"],
        "interval_vector": vector,
        "pure_intervals": relations,
        "span_cents": round(span, 5),
        "height_from_root": height,
        "adoption_reason": reason,
    }


def build_axis_dictionary(
    equave: Fraction,
    generator: int,
    voice_count: int,
    *,
    policy: DictionaryPolicy = DEFAULT_POLICY,
    limit: int = 256,
) -> dict[str, object]:
    """Build one sealed-ready axis dictionary by bounded streaming."""
    if voice_count not in (3, 4):
        raise ValueError(f"voice_count must be 3 or 4, got {voice_count}")
    failures: dict[str, int] = {NOT_ENOUGH_AXIS_POINTS: 0, LOOP_NOT_FOUND_WITHIN_LIMIT: 0}
    loop = None
    points: list[AxisPoint] = []
    try:
        loop, points = axis_index(equave, generator, limit=limit)
    except AuthorityError:
        failures[LOOP_NOT_FOUND_WITHIN_LIMIT] = 1
    if len(points) < voice_count:
        failures[NOT_ENOUGH_AXIS_POINTS] = 1

    buckets: dict[tuple[int, ...], list[dict[str, object]]] = {}
    total = 0
    examined = 0
    truncated = False
    if points:
        for combo in combinations(range(len(points)), voice_count):
            examined += 1
            if examined > policy.max_tuples_examined:
                truncated = True
                break
            if total >= policy.max_entries:
                break
            variant = _evaluate_combo(equave, points, combo, policy)
            if variant is None:
                continue
            key = tuple(sorted(variant["semitones"]))  # type: ignore[arg-type]
            bucket = buckets.setdefault(key, [])
            if len(bucket) < policy.max_variants_per_key:
                bucket.append(variant)
                total += 1

    entries = [
        {
            "key": ",".join(str(cell) for cell in key),
            "variants": bucket,
        }
        for key, bucket in sorted(buckets.items())
    ]
    return {
        "version": DICT_VERSION,
        "equave": ratio_text(equave),
        "generator": generator,
        "voice_count": voice_count,
        "templates_version": TEMPLATES_VERSION,
        "loop": loop_payload(loop) if loop is not None else None,
        "policy": policy.as_dict(),
        "entry_count": len(entries),
        "variant_count": total,
        "tuples_examined": examined,
        "truncated": truncated,
        "failures": failures,
        "entries": entries,
    }
