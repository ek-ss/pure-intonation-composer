"""Non-authoritative distance of emitted pitches from the 12-EDO grid."""

from __future__ import annotations

from collections import defaultdict
from decimal import Decimal, ROUND_HALF_EVEN, localcontext
from fractions import Fraction
from typing import Any, Mapping


def _gap_millicents(ratio: Fraction) -> int:
    with localcontext() as context:
        context.prec = 112
        cents = Decimal(1_200_000) * (
            Decimal(ratio.numerator).ln() - Decimal(ratio.denominator).ln()
        ) / Decimal(2).ln()
        remainder = cents % 100_000
        if remainder < 0:
            remainder += 100_000
        return int(min(remainder, 100_000 - remainder).to_integral_value(rounding=ROUND_HALF_EVEN))


def _rounded_ratio(numerator: int, denominator: int) -> int:
    return round(Fraction(numerator, denominator)) if denominator else 0


def lattice_pitch_diagnostic(project: Mapping[str, Any], *, threshold_millicents: int = 10_000) -> dict[str, Any]:
    """Measure 12-EDO distance in millicents, independent of lattice equave.

    Durations are summed per voice (not unioned); a chord contributes all its
    pitched voices. A note exactly on the 12-EDO grid has zero gap.
    """
    if not 0 <= threshold_millicents <= 50_000:
        raise ValueError("invalid lattice pitch threshold")
    count = exposed = duration = exposed_duration = gap_sum = max_gap = 0
    classes: set[Fraction] = set()
    exposed_classes: set[Fraction] = set()
    by_role: dict[str, dict[str, int]] = defaultdict(lambda: {
        "note_count": 0, "exposed_note_count": 0,
        "duration_ticks": 0, "exposed_duration_ticks": 0,
    })
    tracks = {track["id"]: track["role"] for track in project["tracks"]}
    for event in project["events"]:
        if event["kind"] != "note":
            continue
        ratio = Fraction(event["ratio"])
        if ratio <= 0 or event["duration_ticks"] <= 0:
            raise ValueError("invalid pitched note for lattice diagnostic")
        gap = _gap_millicents(ratio)
        pitch_class = ratio
        while pitch_class >= 2:
            pitch_class /= 2
        while pitch_class < 1:
            pitch_class *= 2
        ticks = event["duration_ticks"]
        role = by_role[tracks[event["track_id"]]]
        count += 1
        duration += ticks
        gap_sum += gap * ticks
        max_gap = max(max_gap, gap)
        classes.add(pitch_class)
        role["note_count"] += 1
        role["duration_ticks"] += ticks
        if gap >= threshold_millicents and gap > 0:
            exposed += 1
            exposed_duration += ticks
            exposed_classes.add(pitch_class)
            role["exposed_note_count"] += 1
            role["exposed_duration_ticks"] += ticks
    return {
        "schema": "cps.lattice-pitch-diagnostic", "schema_version": "1.0.0",
        "non_authoritative": True,
        "reference": "nearest-12-edo-absolute-frequency/v1",
        "threshold_millicents": threshold_millicents,
        "note_count": count, "exposed_note_count": exposed,
        "distinct_pitch_class_count": len(classes),
        "exposed_distinct_pitch_class_count": len(exposed_classes),
        "duration_ticks": duration, "exposed_duration_ticks": exposed_duration,
        "exposed_note_share_q": _rounded_ratio(10_000 * exposed, count),
        "exposed_duration_share_q": _rounded_ratio(10_000 * exposed_duration, duration),
        "duration_weighted_mean_gap_millicents": _rounded_ratio(gap_sum, duration),
        "maximum_gap_millicents": max_gap,
        "by_role": dict(sorted(by_role.items())),
    }
