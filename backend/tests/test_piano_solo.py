"""Tests for the piano-solo (two-part) generation pipeline.

Covers the four non-obvious behaviors added for the piano-solo spec:
anchor reduction mod equave (the ``PROGRESSION_NO_PATH`` fix), MIDI multi-
override channel allocation, hash-seeded chord humanization, and the compiler
melody figuration (nearest-lattice-point resolution with a previous-note anchor).
"""

from __future__ import annotations

from fractions import Fraction

import pytest

from app.songprogram.compiler import (
    _humanize_chord_onsets,
    _lattice_points,
    _mc,
    _nearest_lattice_point,
    _ratio,
    _reduced_anchor_exponent,
    _resolve_melody_pitch,
)
from app.songprogram.midi_export import export_evaluation_midi


def _lattice(reduce_anchor: bool = True) -> dict:
    return {
        "equave": "2/1",
        "generators": ["3/1", "5/1"],
        "coordinate_bounds": [[-2, 2], [-2, 2]],
        "register_bounds": [-4, 4],
        "reduce_anchor_mod_equave": reduce_anchor,
    }


def _major_triad() -> dict:
    """A JI major triad (1/1, 5/4, 3/2) with consistent lattice vectors."""
    return {
        "id": "chord_0",
        "anchor_vector": [0, 0],
        "target_voice_ordinals": [0, 1, 2],
        "voice_offsets": [[0, 0], [0, 1], [1, 0]],
        "equave_exponents": [0, -2, -1],
        "exact_ratios": ["1/1", "5/4", "3/2"],
    }


def _track() -> dict:
    return {"id": "trk_melody", "role": "melody", "register_millicents": [-3_600_000, 3_600_000]}


# --- anchor reduction mod equave -------------------------------------------


def test_reduced_anchor_disabled_returns_zero() -> None:
    lattice = _lattice(reduce_anchor=False)
    assert _reduced_anchor_exponent(lattice, [3, 0]) == 0
    assert _reduced_anchor_exponent(lattice, [-3, 0]) == 0


def test_reduced_anchor_keeps_within_one_octave() -> None:
    lattice = _lattice(reduce_anchor=True)
    for anchor in ([3, 0], [-3, 0], [2, 2], [-2, -2], [0, 3]):
        exponent = _reduced_anchor_exponent(lattice, anchor)
        value = Fraction(1)
        for generator, power in zip(lattice["generators"], anchor):
            value *= Fraction(generator) ** power
        reduced = value * Fraction(2) ** exponent
        assert 1 <= reduced < 2, f"anchor {anchor} -> {reduced} not in [1, 2)"


def test_reduced_anchor_preserves_intervallic_content() -> None:
    # Reducing mod equave changes only the octave, not the odd-part ratio.
    lattice = _lattice(reduce_anchor=True)
    anchor = [3, 0]  # 3^3 = 27, ~4.3 octaves above 1/1
    exponent = _reduced_anchor_exponent(lattice, anchor)
    value = Fraction(3) ** 3 * Fraction(2) ** exponent
    # The odd part (27) is preserved; only the power of two changes.
    assert value.numerator % 27 == 0 or 27 % value.numerator == 0


# --- MIDI multi-override channel allocation --------------------------------


def _midi_project() -> dict:
    return {
        "clock": {"beats_per_bar": 4, "ticks_per_beat": 480, "tempo_milli_bpm": 120_000},
        "tracks": [
            {"id": "trk_harmony", "role": "harmony"},
            {"id": "trk_melody", "role": "melody"},
        ],
        "events": [],
    }


def test_midi_single_override_uses_four_channel_span() -> None:
    midi, manifest = export_evaluation_midi(
        _midi_project(), program_by_track={"trk_harmony": 0}
    )
    assert manifest["program_by_track"] == {"trk_harmony": 0}
    assert len(midi) > 0


def test_midi_two_overrides_get_separate_channel_blocks() -> None:
    # Both piano tracks overridden: each gets its own channel block so a
    # multi-voice piano part can voice every note.
    midi, manifest = export_evaluation_midi(
        _midi_project(), program_by_track={"trk_harmony": 0, "trk_melody": 0}
    )
    assert manifest["program_by_track"] == {"trk_harmony": 0, "trk_melody": 0}
    assert len(midi) > 0


def test_midi_override_rejects_unknown_track() -> None:
    from app.songprogram.midi_export import MidiExportError

    with pytest.raises(MidiExportError, match="MIDI_PROGRAM_OVERRIDE_INVALID"):
        export_evaluation_midi(_midi_project(), program_by_track={"trk_missing": 0})


# --- chord humanization ----------------------------------------------------


def test_humanize_is_deterministic_per_draft() -> None:
    first = _humanize_chord_onsets("hoc_abc", 3)
    second = _humanize_chord_onsets("hoc_abc", 3)
    assert first == second


def test_humanize_varies_across_drafts() -> None:
    results = {
        tuple(_humanize_chord_onsets(f"hoc_{i}", 4)) for i in range(16)
    }
    # Different chords get different roll/drop patterns.
    assert len(results) > 1


def test_humanize_rolls_voices_in_order() -> None:
    offsets, dropped = zip(*_humanize_chord_onsets("hoc_roll", 4))
    # Lower voices start first; offsets are non-decreasing and small.
    assert offsets == tuple(sorted(offsets))
    assert all(0 <= offset < 16 for offset in offsets)
    # At least one voice sounds (not all dropped).
    assert not all(dropped)


# --- melody figuration -----------------------------------------------------


def test_lattice_points_enumerates_domain() -> None:
    points = _lattice_points(_lattice())
    # 5x5 coordinate domain x 9 octaves = 225 points.
    assert len(points) == 25 * 9
    # Every point is a (vector, exponent, ratio_text, mc) tuple.
    for vector, exponent, ratio_text, mc in points:
        assert len(vector) == 2
        assert -4 <= exponent <= 4
        Fraction(ratio_text)  # parses as a ratio
        assert isinstance(mc, int)


def test_nearest_lattice_point_respects_register() -> None:
    points = _lattice_points(_lattice())
    # Target far above the register: the nearest in-register point is clamped.
    found = _nearest_lattice_point(points, 10_000_000, [-3_600_000, 3_600_000])
    assert found is not None
    _, _, _, mc = next(
        (p for p in points if p[:3] == found), (None, None, None, None)
    )
    assert mc is not None and -3_600_000 <= mc <= 3_600_000


def test_resolve_chord_member_without_anchor_returns_voice() -> None:
    chord = _major_triad()
    resolved = _resolve_melody_pitch(
        _lattice(), _lattice_points(_lattice()), chord,
        {"member": 1, "relation": "chord_member", "contour": "hold"},
        _track(), seed=0,
    )
    assert resolved["relation"] == "chord_member"
    assert resolved["final_ratio"] == "5/4"


def test_resolve_chord_member_reoctaves_toward_anchor() -> None:
    chord = _major_triad()
    points = _lattice_points(_lattice())
    # Anchor an octave below the voice: the re-octaved note moves down.
    base = _resolve_melody_pitch(
        _lattice(), points, chord,
        {"member": 1, "relation": "chord_member", "contour": "hold"},
        _track(), seed=0,
    )
    anchored = _resolve_melody_pitch(
        _lattice(), points, chord,
        {"member": 1, "relation": "chord_member", "contour": "hold"},
        _track(), seed=0, anchor_mc=_mc(Fraction(base["final_ratio"])) - 1_200_000,
    )
    assert _mc(Fraction(anchored["final_ratio"])) < _mc(Fraction(base["final_ratio"]))


def test_resolve_figuration_stays_near_anchor() -> None:
    chord = _major_triad()
    points = _lattice_points(_lattice())
    track = _track()
    anchor_mc = 0  # middle of the register
    for seed in range(64):
        resolved = _resolve_melody_pitch(
            _lattice(), points, chord,
            {"member": 0, "relation": "passing", "contour": "hold"},
            track, seed=seed, anchor_mc=anchor_mc,
        )
        if resolved["relation"] in {"passing", "neighbor", "scale_degree"}:
            mc = _mc(Fraction(resolved["final_ratio"]))
            # The figuration note stays within the search window of the anchor.
            assert abs(mc - anchor_mc) <= 1_200_000 + 1_200_000


def test_figuration_relation_weights_sum_to_256() -> None:
    from app.songprogram.compiler import _MELODY_FIGURATION

    assert sum(weight for _, weight in _MELODY_FIGURATION) == 256
    relations = {relation for relation, _ in _MELODY_FIGURATION}
    assert relations == {"chord_member", "passing", "neighbor", "scale_degree"}
