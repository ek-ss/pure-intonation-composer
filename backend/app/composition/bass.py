from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

from app.tuning.analysis import cents
from app.tuning.ratios import reduce_to_octave


@dataclass(frozen=True)
class BassLine:
    """A register-optimized bass note supporting each supplied chord."""

    notes: tuple[Fraction, ...]
    leap_cents: tuple[float, ...]
    strategies: tuple[str, ...]


def generate_bass(
    chords: list[list[Fraction]],
    strategy: str = "hybrid",
    max_leap_cents: float = 900,
    register_low_cents: float = -2400,
    register_high_cents: float = 0,
) -> BassLine:
    """Generate a compact bass line from rational chord roots and their mirrors."""
    if not chords or any(not chord for chord in chords):
        raise ValueError("at least one non-empty chord is required")
    if strategy not in {"mirror", "root", "fifth", "hybrid"}:
        raise ValueError("strategy must be mirror, root, fifth, or hybrid")
    if max_leap_cents <= 0 or register_low_cents >= register_high_cents:
        raise ValueError("bass register or max leap is invalid")

    notes: list[Fraction] = []
    leaps: list[float] = []
    strategies: list[str] = []
    for chord in chords:
        candidates = _bass_candidates(chord, strategy, register_low_cents, register_high_cents)
        if not candidates:
            raise ValueError("chord has no bass candidate in the requested register")
        if not notes:
            note, label = min(candidates, key=lambda item: cents(item[0]))
            notes.append(note)
            leaps.append(0.0)
            strategies.append(label)
            continue
        compatible = [
            (note, label, abs(cents(note / notes[-1])))
            for note, label in candidates
            if abs(cents(note / notes[-1])) <= max_leap_cents
        ]
        if not compatible:
            raise ValueError("no bass candidate satisfies max_leap_cents")
        note, label, leap = min(
            compatible,
            key=lambda item: (item[2], abs(cents(item[0]) - register_low_cents)),
        )
        notes.append(note)
        leaps.append(leap)
        strategies.append(label)
    return BassLine(tuple(notes), tuple(leaps), tuple(strategies))


def _bass_candidates(
    chord: list[Fraction], strategy: str, low: float, high: float
) -> list[tuple[Fraction, str]]:
    root = min(chord)
    mirrors = [reduce_to_octave(Fraction(1, 1) / ratio) for ratio in chord]
    source: list[tuple[Fraction, str]] = []
    if strategy in {"root", "hybrid"}:
        source.append((root, "root"))
    if strategy in {"mirror", "hybrid"}:
        source.extend((ratio, "mirror") for ratio in mirrors)
    if strategy in {"fifth", "hybrid"}:
        source.append((reduce_to_octave(root * Fraction(3, 2)), "fifth"))
    candidates = {
        (placement, label)
        for ratio, label in source
        for placement in _octave_placements(ratio, low, high)
    }
    return sorted(candidates, key=lambda item: (item[0], item[1]))


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
