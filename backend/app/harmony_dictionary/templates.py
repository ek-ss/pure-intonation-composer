"""Versioned 12-EDO chord templates (root-relative semitone sets).

Template names are a *similarity diagnostic*, not an identity of the just
intonation chord: several different exact chords can fall into the same
template, and a lattice-native chord that matches no template within the
versioned tolerance is classified ``other``.
"""

from __future__ import annotations

TEMPLATES_VERSION = "1.0.0"

OTHER = "other"

# Root-relative semitone sets, sorted, root at 0.
TEMPLATES: dict[str, tuple[int, ...]] = {
    # Triads.
    "major_triad": (0, 4, 7),
    "minor_triad": (0, 3, 7),
    "diminished_triad": (0, 3, 6),
    "augmented_triad": (0, 4, 8),
    "sus2_triad": (0, 2, 7),
    "sus4_triad": (0, 5, 7),
    # Tetrads.
    "dominant_seventh": (0, 4, 7, 10),
    "major_seventh": (0, 4, 7, 11),
    "minor_seventh": (0, 3, 7, 10),
    "half_diminished_seventh": (0, 3, 6, 10),
    "diminished_seventh": (0, 3, 6, 9),
    "minor_major_seventh": (0, 3, 7, 11),
    "sus4_seventh": (0, 5, 7, 10),
}


def templates_for_voice_count(voice_count: int) -> dict[str, tuple[int, ...]]:
    if voice_count not in (3, 4):
        raise ValueError(f"voice_count must be 3 or 4, got {voice_count}")
    return {name: shape for name, shape in TEMPLATES.items() if len(shape) == voice_count}
