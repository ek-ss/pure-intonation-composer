"""Equave/generator loop authority and 1D axis index.

For an equave ``E > 1`` and a generator ``g > 1``, the *approximate* loop is
the first ``n >= 1`` such that ``g**n`` comes within the versioned tolerance
of some power of ``E``:

    d_E(n, g) = min_{k in Z} |1200 * log2(g**n / E**k)|  cents

The loop is an approximation, not the identity ``g**n == E**k``.  The
boundary decision is made in integer *decicents* (1 dc = 0.1 cent; one
octave is 12,000 dc) under a fixed-precision Decimal context so that results
are reproducible across platforms and sealed by version.  ``n = 0`` is the
trivial solution and is excluded.

The two equaves ``2/1`` (octave; the same equivalence class as its inverse
``1/2``) and ``3/1`` (tritave; the same class as ``1/3``) are separate
authorities.  Pitch classes and dictionary entries of different equaves are
never merged implicitly.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_EVEN, localcontext
from fractions import Fraction

from app.tuning.ratios import ratio_text

# 1.1.0: the loop distance/tolerance fields are renamed *_mc -> *_dc.  The
# unit is a decicent (1 dc = 0.1 cent; 1 octave = 12,000 dc), not a
# millicent.  The numeric values are unchanged (100 dc = 10 cents), so the
# loop n/k decisions are identical; only the unit label and version change.
SCHEMA_VERSION = "1.1.0"

# Versioned loop policy.
LOOP_LIMIT = 256
LOOP_TOLERANCE_DC = Decimal("100")  # 10 cents, in decicents (1 dc = 0.1 cent)
DECIMAL_PRECISION = 60

OCTAVE = Fraction(2, 1)
TRITAVE = Fraction(3, 1)

# Initial five axes per equave.  The generator is never the equave itself, so
# no axis collapses to the trivial loop.
AXES_BY_EQUAVE: dict[str, tuple[int, ...]] = {
    "2/1": (3, 5, 7, 11, 13),
    "3/1": (2, 5, 7, 11, 13),
}

LOOP_NOT_FOUND_WITHIN_LIMIT = "LOOP_NOT_FOUND_WITHIN_LIMIT"


class AuthorityError(ValueError):
    """A versioned authority policy was violated."""


def equave_ratio(text: str) -> Fraction:
    """Parse an equave such as ``"2/1"`` or ``"3/1"`` into a reduced Fraction."""
    try:
        numerator, _, denominator = text.partition("/")
        ratio = Fraction(int(numerator), int(denominator))
    except (ValueError, ZeroDivisionError) as error:
        raise AuthorityError(f"invalid equave {text!r}: expected a positive reduced ratio") from error
    if ratio <= 1:
        raise AuthorityError(f"equave must be > 1, got {text!r}")
    return ratio


def axes_for_equave(equave: str) -> tuple[int, ...]:
    try:
        return AXES_BY_EQUAVE[equave]
    except KeyError as error:
        raise AuthorityError(f"unknown equave {equave!r}; supported: {sorted(AXES_BY_EQUAVE)}") from error


def reduce_on_equave(ratio: Fraction, equave: Fraction) -> tuple[Fraction, int]:
    """Return ``(reduced, k)`` with ``1 <= reduced < equave`` and ``ratio == reduced * equave**k``.

    Exact rational arithmetic; the loop terminates because ``ratio > 0``.
    """
    if ratio <= 0:
        raise AuthorityError("ratio must be positive")
    if equave <= 1:
        raise AuthorityError("equave must be > 1")
    reduced = ratio
    exponent = 0
    while reduced >= equave:
        reduced /= equave
        exponent += 1
    while reduced < 1:
        reduced *= equave
        exponent -= 1
    return reduced, exponent


@dataclass(frozen=True)
class LoopResult:
    """The first approximate equave loop for one (equave, generator) pair."""

    equave: Fraction
    generator: int
    found: bool
    n: int | None
    k: int | None
    distance_dc: int | None
    code: str

    def __post_init__(self) -> None:
        if self.found and (self.n is None or self.k is None or self.distance_dc is None):
            raise AuthorityError("a found loop must carry n, k, and distance_dc")
        if not self.found and (self.n is not None or self.k is not None or self.distance_dc is not None):
            raise AuthorityError("an unfound loop must carry no coordinates")


@dataclass(frozen=True)
class AxisPoint:
    """One 1D index point of a generator axis, equave-reduced.

    ``absolute_cents`` is the height of the *original* ratio ``g**n`` on the
    absolute frequency semitone grid; 12-EDO rounding is done there so that
    ``2/1`` and ``3/1`` are never confused.  ``reduced_cents`` is the equave
    phase (``[0, 1200)`` for the octave, ``[0, ~1901.955)`` for the tritave).
    """

    n: int
    original_ratio: Fraction
    reduced_ratio: Fraction
    equave_exponent: int
    absolute_cents: float
    nearest_12edo_semitone: int
    signed_12edo_error_cents: float
    reduced_cents: float


def _log2_decimal(numerator: int, denominator: int) -> Decimal:
    with localcontext() as context:
        context.prec = DECIMAL_PRECISION
        return (Decimal(numerator).ln() - Decimal(denominator).ln()) / Decimal(2).ln()


def loop_steps(
    equave: Fraction,
    generator: int,
    *,
    limit: int = LOOP_LIMIT,
    tolerance_dc: Decimal = LOOP_TOLERANCE_DC,
) -> LoopResult:
    """Find the first ``n >= 1`` with ``d_E(n, g) <= tolerance_dc/10`` cents.

    The search is bounded by ``limit`` (versioned policy).  When no ``n``
    within the limit satisfies the tolerance, the result carries
    ``LOOP_NOT_FOUND_WITHIN_LIMIT`` and the radius is *not* extended
    implicitly.
    """
    if not isinstance(generator, int) or generator < 2:
        raise AuthorityError(f"generator must be an integer >= 2, got {generator!r}")
    if equave <= 1:
        raise AuthorityError(f"equave must be > 1, got {ratio_text(equave)}")
    if not 1 <= limit:
        raise AuthorityError(f"limit must be >= 1, got {limit}")

    with localcontext() as context:
        context.prec = DECIMAL_PRECISION
        log_equave = (Decimal(equave.numerator).ln() - Decimal(equave.denominator).ln()) / Decimal(2).ln()
        log_generator = Decimal(generator).ln() / Decimal(2).ln()
        for n in range(1, limit + 1):
            quotient = log_generator * n / log_equave
            k = int(quotient.to_integral_value(rounding=ROUND_HALF_EVEN))
            best = min(abs(log_generator * n - Decimal(candidate) * log_equave) for candidate in (k - 1, k, k + 1))
            # ``best`` is in octaves; one octave is 1200 cents = 12,000 decicents.
            distance_dc = int((best * Decimal(12000)).to_integral_value(rounding=ROUND_HALF_EVEN))
            if distance_dc <= int(tolerance_dc):
                return LoopResult(equave, generator, True, n, k, distance_dc, "OK")
    return LoopResult(equave, generator, False, None, None, None, LOOP_NOT_FOUND_WITHIN_LIMIT)


def axis_index(
    equave: Fraction,
    generator: int,
    *,
    limit: int = LOOP_LIMIT,
) -> tuple[LoopResult, list[AxisPoint]]:
    """Build the 1D index ``n = 0 .. loop_steps[g] - 1`` for one axis.

    The negative direction is the same period with provenance: a request at
    ``n < 0`` resolves to ``n mod loop.n`` plus the loop approximation.
    """
    loop = loop_steps(equave, generator, limit=limit)
    if not loop.found:
        raise AuthorityError(f"{loop.code}: equave {ratio_text(equave)} generator {generator}")
    assert loop.n is not None
    points: list[AxisPoint] = []
    for n in range(loop.n):
        original = Fraction(generator) ** n
        reduced, exponent = reduce_on_equave(original, equave)
        absolute = _log2_decimal(original.numerator, original.denominator) * Decimal(1200)
        semitone = int((absolute / Decimal(100)).to_integral_value(rounding=ROUND_HALF_EVEN))
        reduced_cents = _log2_decimal(reduced.numerator, reduced.denominator) * Decimal(1200)
        points.append(
            AxisPoint(
                n=n,
                original_ratio=original,
                reduced_ratio=reduced,
                equave_exponent=exponent,
                absolute_cents=round(float(absolute), 5),
                nearest_12edo_semitone=int(semitone),
                signed_12edo_error_cents=round(float(absolute - Decimal(100) * semitone), 5),
                reduced_cents=round(float(reduced_cents), 5),
            )
        )
    return loop, points


def resolve_axis_point(
    equave: Fraction,
    generator: int,
    n: int,
    *,
    limit: int = LOOP_LIMIT,
) -> tuple[AxisPoint, dict[str, object]]:
    """Resolve any integer ``n`` (including negative) to an index point.

    The returned provenance records the requested ``n``, the equivalent
    non-negative index, and the loop approximation that relates them.
    """
    loop, points = axis_index(equave, generator, limit=limit)
    assert loop.n is not None and loop.distance_dc is not None
    index_n = n % loop.n
    provenance: dict[str, object] = {
        "requested_n": n,
        "index_n": index_n,
        "loop_period": loop.n,
        "loop_approximation_dc": loop.distance_dc * abs(n - index_n) // max(loop.n, 1),
    }
    return points[index_n], provenance


def loop_payload(result: LoopResult) -> dict[str, object]:
    return {
        "equave": ratio_text(result.equave),
        "generator": result.generator,
        "found": result.found,
        "n": result.n,
        "k": result.k,
        "distance_dc": result.distance_dc,
        "code": result.code,
    }


def axis_point_payload(point: AxisPoint) -> dict[str, object]:
    return {
        "n": point.n,
        "original_ratio": ratio_text(point.original_ratio),
        "reduced_ratio": ratio_text(point.reduced_ratio),
        "equave_exponent": point.equave_exponent,
        "absolute_cents": round(point.absolute_cents, 5),
        "nearest_12edo_semitone": point.nearest_12edo_semitone,
        "signed_12edo_error_cents": round(point.signed_12edo_error_cents, 5),
        "reduced_cents": round(point.reduced_cents, 5),
    }


def axis_payload(equave: Fraction, generator: int, *, limit: int = LOOP_LIMIT) -> dict[str, object]:
    """The sealed 1D axis: loop, points, and negative-direction provenance."""
    loop, points = axis_index(equave, generator, limit=limit)
    assert loop.n is not None and loop.distance_dc is not None
    return {
        "equave": ratio_text(equave),
        "generator": generator,
        "loop": loop_payload(loop),
        "negative_direction": {
            "offset": -loop.n,
            "approximation_dc": loop.distance_dc,
        },
        "points": [axis_point_payload(point) for point in points],
    }
