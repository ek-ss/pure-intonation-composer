from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from itertools import product

from app.tuning.analysis import cents


@dataclass(frozen=True)
class VoicedProgression:
    """Chord voicings ordered from the lowest to the highest voice."""

    chords: tuple[tuple[Fraction, ...], ...]
    leap_cents: tuple[tuple[float, ...], ...]


def voice_lead(
    chords: list[list[Fraction]],
    max_leap_cents: float = 700,
    register_low_cents: float = 0,
    register_high_cents: float = 2400,
) -> VoicedProgression:
    """Find compact, non-crossing voicings for a sequence of equal-size chords."""
    _validate_input(chords, max_leap_cents, register_low_cents, register_high_cents)
    first_candidates = _candidate_voicings(
        chords[0], register_low_cents, register_high_cents
    )
    if not first_candidates:
        raise ValueError("first chord cannot fit inside the requested register")

    voiced_chords = [min(first_candidates, key=_voicing_height)]
    leaps = [tuple(0.0 for _ in voiced_chords[0])]
    for chord in chords[1:]:
        candidates = _candidate_voicings(chord, register_low_cents, register_high_cents)
        compatible = []
        for candidate in candidates:
            candidate_leaps = tuple(
                abs(cents(next_ratio / previous_ratio))
                for previous_ratio, next_ratio in zip(voiced_chords[-1], candidate)
            )
            if all(leap <= max_leap_cents for leap in candidate_leaps):
                compatible.append((candidate, candidate_leaps))
        if not compatible:
            raise ValueError("no non-crossing voicing satisfies max_leap_cents")
        voicing, chord_leaps = min(
            compatible,
            key=lambda item: (sum(item[1]), _voicing_height(item[0])),
        )
        voiced_chords.append(voicing)
        leaps.append(chord_leaps)
    return VoicedProgression(tuple(voiced_chords), tuple(leaps))


def _candidate_voicings(
    chord: list[Fraction], low: float, high: float
) -> list[tuple[Fraction, ...]]:
    placements = [_octave_placements(ratio, low, high) for ratio in chord]
    if any(not options for options in placements):
        return []
    return sorted({tuple(sorted(candidate)) for candidate in product(*placements)})


def _octave_placements(ratio: Fraction, low: float, high: float) -> list[Fraction]:
    candidate = ratio
    while cents(candidate) < low:
        candidate *= 2
    while cents(candidate / 2) >= low:
        candidate /= 2
    placements = []
    while cents(candidate) <= high:
        placements.append(candidate)
        candidate *= 2
    return placements


def _voicing_height(voicing: tuple[Fraction, ...]) -> float:
    return sum(cents(ratio) for ratio in voicing)


def _validate_input(
    chords: list[list[Fraction]], max_leap: float, low: float, high: float
) -> None:
    if len(chords) < 1:
        raise ValueError("at least one chord is required")
    voice_count = len(chords[0])
    if voice_count < 1 or any(len(chord) != voice_count for chord in chords):
        raise ValueError("all chords must contain the same positive number of voices")
    if any(ratio <= 0 for chord in chords for ratio in chord):
        raise ValueError("chord ratios must be positive")
    if max_leap <= 0:
        raise ValueError("max_leap_cents must be positive")
    if low >= high:
        raise ValueError("register_low_cents must be lower than register_high_cents")
