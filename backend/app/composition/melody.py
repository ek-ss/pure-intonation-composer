from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from random import Random

from app.tuning.analysis import cents


@dataclass(frozen=True)
class Melody:
    """Independent rational-pitch voices constrained to a musical register."""

    voices: tuple[tuple[Fraction, ...], ...]


def generate_melody(
    chords: list[list[Fraction]],
    voice_count: int = 1,
    seed: int = 0,
    contour: str = "arch",
    max_leap_cents: float = 700,
    register_low_cents: float = 600,
    register_high_cents: float = 2400,
    phrase_memory: int = 3,
) -> Melody:
    """Generate repeatable melodic walks over chord tones for independent voices."""
    if not chords or any(not chord for chord in chords):
        raise ValueError("at least one non-empty chord is required")
    if not 1 <= voice_count <= 8:
        raise ValueError("voice_count must be between 1 and 8")
    if contour not in {"ascending", "descending", "arch", "free"}:
        raise ValueError("contour must be ascending, descending, arch, or free")
    if max_leap_cents <= 0 or register_low_cents >= register_high_cents or phrase_memory < 0:
        raise ValueError("melody constraints are invalid")

    return Melody(
        tuple(
            _generate_voice(
                chords,
                Random(seed + voice),
                contour,
                max_leap_cents,
                register_low_cents,
                register_high_cents,
                phrase_memory,
            )
            for voice in range(voice_count)
        )
    )


def _generate_voice(
    chords: list[list[Fraction]],
    random: Random,
    contour: str,
    max_leap: float,
    low: float,
    high: float,
    memory_length: int,
) -> tuple[Fraction, ...]:
    notes: list[Fraction] = []
    for position, chord in enumerate(chords):
        candidates = [
            placement for ratio in chord for placement in _octave_placements(ratio, low, high)
        ]
        candidates = sorted(set(candidates))
        if not candidates:
            raise ValueError("chord has no melody tone in the requested register")
        if not notes:
            note = candidates[random.randrange(len(candidates))]
        else:
            nearby = [
                candidate
                for candidate in candidates
                if abs(cents(candidate / notes[-1])) <= max_leap
            ]
            pool = nearby or candidates
            memory = set(notes[-memory_length:]) if memory_length else set()
            fresh = [candidate for candidate in pool if candidate not in memory]
            note = _choose_by_contour(fresh or pool, notes[-1], position, len(chords), contour, random)
        notes.append(note)
    return tuple(notes)


def _choose_by_contour(
    candidates: list[Fraction],
    previous: Fraction,
    position: int,
    total: int,
    contour: str,
    random: Random,
) -> Fraction:
    if contour == "free":
        return candidates[random.randrange(len(candidates))]
    rising = contour == "ascending" or (contour == "arch" and position < total / 2)
    directed = [candidate for candidate in candidates if (candidate >= previous) == rising]
    return random.choice(directed or candidates)


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
