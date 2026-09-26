"""Context-dependent stability scoring and T/D/S classification.

``stability_q`` is a one-dimensional value in ``[0, 10000]``: higher means
more stable *relative to the specified tonic*.  The same chord gets a
different value when the tonic changes.

The versioned scoring table outputs four components, each in ``[0, 1]``:

- ``R``: proximity of the chord's bass/root to the tonic,
- ``C``: consonance/roughness proxy of the chord's exact intervals,
- ``V``: minimum voice movement to the versioned tonic chord,
- ``F``: similarity to the 12-EDO reference.

The initial calibration aggregate is
``stability_q = round(10000 * (0.30 R + 0.30 C + 0.25 V + 0.15 F))``.
The roughness interval table, the evaluated tonic chord, the distance-to-
0..1 mappings, rounding, and all weights are fixed in the versioned profile.

Tendency tones, actual resolution to a next chord, and beat position are
recorded separately as ``contextual_arrival_q``; they are not mixed into the
standalone chord score.  Perfect consonance is *not* assumed to always be
tonic.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_EVEN
from fractions import Fraction

from app.harmony_dictionary.authority import reduce_on_equave
from app.harmony_dictionary.dictionary import _PURE_INTERVAL_CENTS, _cents_decimal, match_template

STABILITY_VERSION = "1.0.0"


@dataclass(frozen=True)
class StabilityProfile:
    """Versioned stability scoring table."""

    version: str = STABILITY_VERSION
    # Aggregate weights for (R, C, V, F).
    weights: tuple[float, float, float, float] = (0.30, 0.30, 0.25, 0.15)
    # R: linear falloff of root proximity to zero at this distance (cents).
    root_proximity_half_width_cents: float = 300.0
    # V: linear falloff of voice movement to zero at this total distance.
    voice_movement_half_width_cents: float = 400.0
    # F: 12-EDO similarity falls to zero at this max per-tone error.
    template_similarity_full_error_cents: float = 100.0
    # The evaluated tonic chord (root-relative ratios), versioned.
    tonic_chord: tuple[str, ...] = ("1/1", "5/4", "3/2")

    def as_dict(self) -> dict[str, object]:
        return {
            "version": self.version,
            "weights": list(self.weights),
            "root_proximity_half_width_cents": self.root_proximity_half_width_cents,
            "voice_movement_half_width_cents": self.voice_movement_half_width_cents,
            "template_similarity_full_error_cents": self.template_similarity_full_error_cents,
            "tonic_chord": list(self.tonic_chord),
        }


DEFAULT_PROFILE = StabilityProfile()

# Versioned roughness proxy: consonance of a just interval, 1.0 (most
# consonant) to 0.0 (most rough), keyed by the nearest versioned just ratio.
ROUGHNESS_TABLE: dict[str, float] = {
    "1/1": 1.0,
    "8/5": 0.95,
    "5/4": 0.9,
    "3/2": 0.9,
    "4/3": 0.85,
    "6/5": 0.8,
    "5/3": 0.75,
    "9/8": 0.6,
    "10/9": 0.55,
    "7/6": 0.5,
    "8/7": 0.45,
    "7/5": 0.4,
    "9/7": 0.35,
    "16/15": 0.3,
    "7/4": 0.25,
    "15/8": 0.2,
    "9/5": 0.15,
    "16/9": 0.1,
    "45/32": 0.05,
    "14/9": 0.05,
    "12/7": 0.05,
    "9/4": 0.0,
    "5/2": 0.0,
    "7/3": 0.0,
}

# Fallback when the nearest just ratio is not in the table.
ROUGHNESS_DEFAULT = 0.25


def _equave_cents(equave: Fraction) -> Decimal:
    return Decimal(1200) * equave.numerator / equave.denominator


def _circular_distance_cents(first: Fraction, second: Fraction, equave: Fraction) -> Decimal:
    """Distance on the equave circle between two ratios, in ``[0, E_cents/2]``."""
    interval, _ = reduce_on_equave(first / second, equave)
    cents = _cents_decimal(interval)
    return min(cents, _equave_cents(equave) - cents)


def root_proximity(root_ratio: Fraction, tonic_ratio: Fraction, equave: Fraction, profile: StabilityProfile) -> float:
    """R: linear falloff of the root's distance to the tonic, in ``[0, 1]``."""
    distance = _circular_distance_cents(root_ratio, tonic_ratio, equave)
    width = Decimal(str(profile.root_proximity_half_width_cents))
    value = Decimal(1) - distance / width
    return float(max(Decimal(0), min(Decimal(1), value)))


def consonance(root_relative_ratios: list[Fraction], equave: Fraction, profile: StabilityProfile) -> float:
    """C: mean roughness proxy over all tone pairs, in ``[0, 1]``."""
    if len(root_relative_ratios) < 2:
        return 1.0
    values: list[float] = []
    for i in range(len(root_relative_ratios)):
        for j in range(i + 1, len(root_relative_ratios)):
            interval, _ = reduce_on_equave(root_relative_ratios[i] / root_relative_ratios[j], equave)
            cents = _cents_decimal(interval)
            best_name, best_distance = "1/1", Decimal("Infinity")
            for name, pure_cents in _PURE_INTERVAL_CENTS:
                distance = abs(cents - pure_cents)
                if distance < best_distance:
                    best_name, best_distance = name, distance
            values.append(ROUGHNESS_TABLE.get(best_name, ROUGHNESS_DEFAULT))
    return sum(values) / len(values)


def voice_movement(
    chord_ratios: list[Fraction], tonic_chord_ratios: list[Fraction], equave: Fraction, profile: StabilityProfile
) -> float:
    """V: ``1 - min total voice movement / half_width``, in ``[0, 1]``.

    Each chord voice moves independently to its nearest copy (with equave
    lifts) of any tonic-chord voice; doublings are allowed.  This keeps the
    metric defined for mixed 3/4-voice chords.
    """
    if not chord_ratios or not tonic_chord_ratios:
        return 0.0
    equave_cents = _equave_cents(equave)
    chord_dec = [Decimal(repr(float(_cents_decimal(ratio)))) for ratio in chord_ratios]
    target_dec = [Decimal(repr(float(_cents_decimal(ratio)))) for ratio in tonic_chord_ratios]

    def nearest_distance(source: Decimal) -> Decimal:
        best = Decimal("Infinity")
        for target in target_dec:
            difference = source - target
            steps = int((difference / equave_cents).to_integral_value(rounding=ROUND_HALF_EVEN))
            distance = abs(difference - equave_cents * steps)
            if distance < best:
                best = distance
        return best

    total = sum(nearest_distance(source) for source in chord_dec)
    width = Decimal(str(profile.voice_movement_half_width_cents))
    value = Decimal(1) - total / width
    return float(max(Decimal(0), min(Decimal(1), value)))


def template_similarity(root_relative_cents: list[float], voice_count: int, profile: StabilityProfile) -> float:
    """F: 12-EDO similarity from the template match, in ``[0, 1]``."""
    match = match_template(root_relative_cents, voice_count)
    full_error = Decimal(str(profile.template_similarity_full_error_cents))
    max_error = Decimal(repr(match["max_error_cents"]))
    value = Decimal(1) - max_error / full_error
    return float(max(Decimal(0), min(Decimal(1), value)))


def stability_components(
    root_ratio: Fraction,
    root_relative_ratios: list[Fraction],
    tonic_ratio: Fraction,
    *,
    equave: Fraction,
    profile: StabilityProfile = DEFAULT_PROFILE,
) -> dict[str, float]:
    """The four versioned components, each in ``[0, 1]``.

    ``root_relative_ratios`` are the chord's exact root-relative ratios;
    they are reduced to one equave here.
    """
    reduced = [reduce_on_equave(ratio, equave)[0] for ratio in root_relative_ratios]
    tonic_chord = [Fraction(text) for text in profile.tonic_chord]
    return {
        "R": root_proximity(root_ratio, tonic_ratio, equave, profile),
        "C": consonance(reduced, equave, profile),
        "V": voice_movement(reduced, tonic_chord, equave, profile),
        "F": template_similarity(
            [round(float(_cents_decimal(ratio)), 5) for ratio in reduced],
            len(reduced),
            profile,
        ),
    }


def stability_q(
    root_ratio: Fraction,
    root_relative_ratios: list[Fraction],
    tonic_ratio: Fraction,
    *,
    equave: Fraction,
    profile: StabilityProfile = DEFAULT_PROFILE,
) -> int:
    """The versioned aggregate in ``[0, 10000]`` (higher = more stable)."""
    components = stability_components(root_ratio, root_relative_ratios, tonic_ratio, equave=equave, profile=profile)
    weights = [Decimal(str(weight)) for weight in profile.weights]
    total = sum(weight * Decimal(repr(value)) for weight, value in zip(weights, components.values()))
    quantized = int((total * Decimal(10000)).to_integral_value(rounding=ROUND_HALF_EVEN))
    return max(0, min(10000, quantized))


@dataclass(frozen=True)
class ClassificationThresholds:
    """Versioned T/D/S thresholds, calibrated on held-out seeds.

    ``stability_q >= T_high`` -> tonic candidate;
    ``stability_q <= D_low`` -> dominant candidate;
    in between -> subdominant candidate.  ``D_low < T_high`` is required.
    """

    version: str = "1.0.0"
    T_high: int = 7000
    D_low: int = 3000
    # A candidate within this margin of its threshold is ambiguous.
    margin: int = 500

    def __post_init__(self) -> None:
        if not self.D_low < self.T_high:
            raise ValueError("thresholds require D_low < T_high")

    def as_dict(self) -> dict[str, object]:
        return {"version": self.version, "T_high": self.T_high, "D_low": self.D_low, "margin": self.margin}


DEFAULT_THRESHOLDS = ClassificationThresholds()


def classify_threshold(stability_value: int, thresholds: ClassificationThresholds) -> str:
    """The threshold-only three-way classification."""
    if stability_value >= thresholds.T_high:
        return "tonic"
    if stability_value <= thresholds.D_low:
        return "dominant"
    return "subdominant"


def _function_root(tonic_ratio: Fraction, function: str, equave: Fraction) -> Fraction:
    if function == "tonic":
        factor = Fraction(1)
    elif function == "dominant":
        factor = Fraction(3, 2)
    elif function == "subdominant":
        factor = Fraction(4, 3)
    else:
        raise ValueError(f"unknown function {function!r}")
    reduced, _ = reduce_on_equave(tonic_ratio * factor, equave)
    return reduced


def classify_with_context(
    root_ratio: Fraction,
    root_relative_ratios: list[Fraction],
    tonic_ratio: Fraction,
    *,
    equave: Fraction,
    profile: StabilityProfile = DEFAULT_PROFILE,
    thresholds: ClassificationThresholds = DEFAULT_THRESHOLDS,
    following_root: Fraction | None = None,
) -> dict[str, object]:
    """Threshold classification conditioned on root position and resolution.

    Mismatches and low margins yield ``ambiguous`` (explained, not rejected).
    The result carries both the threshold-only candidate and the contextual
    final label.
    """
    value = stability_q(root_ratio, root_relative_ratios, tonic_ratio, equave=equave, profile=profile)
    candidate = classify_threshold(value, thresholds)
    reasons: list[str] = []
    final = candidate

    expected_root = _function_root(tonic_ratio, candidate, equave)
    root_distance = float(_circular_distance_cents(root_ratio, expected_root, equave))
    position_tolerance = profile.root_proximity_half_width_cents if candidate == "tonic" else 100.0
    if root_distance > position_tolerance:
        final = "ambiguous"
        reasons.append(f"root {round(root_distance, 1)}c from the expected {candidate} position")

    if candidate == "tonic" and value < thresholds.T_high + thresholds.margin:
        final = "ambiguous"
        reasons.append(f"stability {value} is within the margin of T_high")
    if candidate == "dominant" and value > thresholds.D_low - thresholds.margin:
        final = "ambiguous"
        reasons.append(f"stability {value} is within the margin of D_low")

    if following_root is not None:
        motion = float(_circular_distance_cents(root_ratio, following_root, equave))
        resolution = {
            "tonic": 0.0,
            "dominant": float(_circular_distance_cents(Fraction(3, 2), Fraction(1), equave)),
            "subdominant": float(_circular_distance_cents(Fraction(4, 3), Fraction(1), equave)),
        }[candidate]
        if abs(motion - resolution) > 100.0:
            reasons.append(f"root motion {round(motion, 1)}c does not resolve as {candidate} (expected {round(resolution, 1)}c)")

    return {
        "stability_q": value,
        "candidate": candidate,
        "final": final,
        "root_distance_cents": round(root_distance, 5),
        "reasons": reasons,
    }

