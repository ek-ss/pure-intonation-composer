from __future__ import annotations

from collections import defaultdict
from fractions import Fraction
from math import floor, log2
from statistics import fmean
from typing import Any


MIDI_SCALE_PRESETS: tuple[dict[str, Any], ...] = (
    {
        "id": "fractional-pop-bright",
        "name": "Bright 5-limit",
        "family": "Fractional Pop",
        "ratios": ["1/1", "9/8", "5/4", "4/3", "3/2", "5/3", "15/8"],
        "equave_ratio": "2/1",
    },
    {
        "id": "fractional-pop-minor",
        "name": "Minor 5-limit",
        "family": "Fractional Pop",
        "ratios": ["1/1", "9/8", "6/5", "4/3", "3/2", "8/5", "9/5"],
        "equave_ratio": "2/1",
    },
    {
        "id": "fractional-pop-color",
        "name": "7-limit color",
        "family": "Fractional Pop",
        "ratios": ["1/1", "8/7", "6/5", "5/4", "4/3", "3/2", "12/7", "7/4"],
        "equave_ratio": "2/1",
    },
    {
        "id": "kawaii-sparkle-13",
        "name": "13-limit sparkle",
        "family": "Kawaii Future Pop",
        "ratios": ["1/1", "9/8", "6/5", "5/4", "4/3", "3/2", "13/8", "5/3", "7/4"],
        "equave_ratio": "2/1",
    },
    {
        "id": "kawaii-prime-lattice",
        "name": "3 x 7 x 13 lattice",
        "family": "Kawaii Future Pop",
        "ratios": ["1/1", "9/8", "7/6", "39/32", "21/16", "3/2", "13/8", "7/4", "117/64"],
        "equave_ratio": "2/1",
    },
    {
        "id": "jpop-fifth-field",
        "name": "Pure-fifth field",
        "family": "Fractional J-Pop",
        "ratios": ["1/1", "9/8", "81/64", "4/3", "3/2", "27/16", "243/128"],
        "equave_ratio": "2/1",
    },
    {
        "id": "jpop-minor-third-field",
        "name": "Pure minor-third field",
        "family": "Fractional J-Pop",
        "ratios": ["1/1", "6/5", "36/25", "3/2", "8/5", "9/5"],
        "equave_ratio": "2/1",
    },
    {
        "id": "harmonic-series-16",
        "name": "Harmonics 8-15",
        "family": "Series",
        "ratios": ["1/1", "9/8", "5/4", "11/8", "3/2", "13/8", "7/4", "15/8"],
        "equave_ratio": "2/1",
    },
    {
        "id": "subharmonic-series-16",
        "name": "Subharmonics 8-16",
        "family": "Series",
        "ratios": ["1/1", "16/15", "8/7", "16/13", "4/3", "16/11", "8/5", "16/9"],
        "equave_ratio": "2/1",
    },
    {
        "id": "bohlen-pierce-pure",
        "name": "Pure 3:5:7 tritave",
        "family": "Bohlen-Pierce",
        "ratios": ["1/1", "9/7", "7/5", "5/3", "15/7", "7/3", "25/9"],
        "equave_ratio": "3/1",
    },
)


def midi_scale_catalog() -> dict[str, object]:
    """Return immutable built-in scales available to MIDI performance input."""
    return {
        "schema_version": "1.0",
        "presets": [{**preset, "ratios": list(preset["ratios"])} for preset in MIDI_SCALE_PRESETS],
        "generators": ["prime-limit-explorer"],
    }


def _ratio_text(value: Fraction) -> str:
    return f"{value.numerator}/{value.denominator}"


def _reduce(value: Fraction, equave: Fraction) -> Fraction:
    while value < 1:
        value *= equave
    while value >= equave:
        value /= equave
    return value


def _cents(value: Fraction) -> float:
    return 1200 * log2(float(value))


def _odd_primes(values: list[Fraction]) -> list[int]:
    result: set[int] = set()
    for value in values:
        for part in (value.numerator, value.denominator):
            remainder = part
            divisor = 2
            while divisor * divisor <= remainder:
                while remainder % divisor == 0:
                    if divisor != 2:
                        result.add(divisor)
                    remainder //= divisor
                divisor += 1
            if remainder > 1 and remainder != 2:
                result.add(remainder)
    return sorted(result)


def _monzo(value: Fraction, basis: list[int]) -> list[int]:
    result: list[int] = []
    numerator = value.numerator
    denominator = value.denominator
    for prime in basis:
        exponent = 0
        while numerator % prime == 0:
            numerator //= prime
            exponent += 1
        while denominator % prime == 0:
            denominator //= prime
            exponent -= 1
        result.append(exponent)
    return result


def _nearest_ratio(
    midi_note: int, root_midi: int, scale: list[Fraction], equave: Fraction
) -> Fraction:
    target_cents = (midi_note - root_midi) * 100
    approximate_equave = floor(target_cents / _cents(equave))
    candidates = [
        ratio * equave**period
        for period in range(approximate_equave - 2, approximate_equave + 3)
        for ratio in scale
    ]
    return min(candidates, key=lambda ratio: (abs(_cents(ratio) - target_cents), ratio))


_WHITE_KEY_OFFSETS = {0: 0, 2: 1, 4: 2, 5: 3, 7: 4, 9: 5, 11: 6}


def _white_key_index(midi_note: int) -> int:
    offset = _WHITE_KEY_OFFSETS.get(midi_note % 12)
    if offset is None:
        raise ValueError("white_keys_scale mapping accepts white MIDI keys only")
    return midi_note // 12 * 7 + offset


def _white_key_scale_ratio(
    midi_note: int, root_midi: int, scale: list[Fraction], equave: Fraction
) -> Fraction:
    degree = _white_key_index(midi_note) - _white_key_index(root_midi)
    period, scale_index = divmod(degree, len(scale))
    return scale[scale_index] * equave**period


def _mapped_ratio(
    midi_note: int, config: dict[str, Any], scale: list[Fraction], equave: Fraction
) -> Fraction:
    root_midi = int(config["root_midi"])
    if config.get("keyboard_mapping", "white_keys_scale") == "white_keys_scale":
        return _white_key_scale_ratio(midi_note, root_midi, scale, equave)
    return _nearest_ratio(midi_note, root_midi, scale, equave)


def _distance(left: Fraction, right: Fraction, equave: Fraction) -> float:
    period_cents = _cents(equave)
    difference = abs(
        (_cents(_reduce(left, equave)) - _cents(_reduce(right, equave))) % period_cents
    )
    return min(difference, period_cents - difference)


def _relation(value: Fraction, anchor: list[Fraction], equave: Fraction) -> str:
    distance = min(_distance(value, tone, equave) for tone in anchor)
    if distance < 25:
        return "exact"
    if distance < 80:
        return "near"
    if distance < 180:
        return "related"
    return "contrast"


def _quantize(config: dict[str, Any]) -> list[dict[str, Any]]:
    notes = [dict(note) for note in config["notes"]]
    offset = min(float(note["start_beats"]) for note in notes) if config["trim_start"] else 0
    step = 1 / int(config["quantize_division"])
    strength = float(config["quantize_strength"])
    minimum = float(config["minimum_duration_beats"])
    for note in notes:
        start = max(0.0, float(note["start_beats"]) - offset)
        target = round(start / step) * step
        start += (target - start) * strength
        grid_index = round(target / step)
        if grid_index % 2:
            start += step * float(config["swing"])
        duration = float(note["duration_beats"])
        duration_target = max(minimum, round(duration / step) * step)
        duration += (duration_target - duration) * strength
        note["start_beats"] = round(max(0, start), 6)
        note["duration_beats"] = round(max(minimum, duration), 6)
    return sorted(notes, key=lambda note: (note["start_beats"], note["midi_note"]))


def _anchor(
    notes: list[dict[str, Any]], config: dict[str, Any], scale: list[Fraction], size: int,
    equave: Fraction,
) -> list[Fraction]:
    weights: dict[Fraction, float] = defaultdict(float)
    for note in notes:
        value = _reduce(
            _mapped_ratio(int(note["midi_note"]), config, scale, equave), equave
        )
        weights[value] += float(note["duration_beats"]) * int(note["velocity"])
    ordered = sorted(weights, key=lambda value: (-weights[value], _cents(value)))
    result = [Fraction(1)]
    result.extend(value for value in ordered if value != 1)
    result.extend(value for value in scale if value not in result)
    return result[:size]


def _motif(
    notes: list[dict[str, Any]], config: dict[str, Any], scale: list[Fraction]
) -> tuple[dict[str, Any], list[dict[str, Any]], list[str]]:
    step = 1 / int(config["quantize_division"])
    grouped: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for note in notes:
        grouped[round(float(note["start_beats"]) / step)].append(note)
    maximum = int(config["maximum_polyphony"])
    equave = Fraction(config.get("equave_ratio", "2/1"))
    discarded = 0
    limited_groups: list[tuple[float, list[dict[str, Any]]]] = []
    for slot, group in sorted(grouped.items()):
        selected = sorted(group, key=lambda note: (-int(note["velocity"]), int(note["midi_note"])))[:maximum]
        discarded += max(0, len(group) - len(selected))
        onset = fmean(float(note["start_beats"]) for note in selected)
        limited_groups.append((onset, sorted(selected, key=lambda note: int(note["midi_note"]))))
    motif_groups = limited_groups[:32]
    truncated_steps = max(0, len(limited_groups) - len(motif_groups))
    flattened = [note for _, group in motif_groups for note in group]
    anchor = _anchor(
        flattened, config, scale, int(config["anchor_size"]), equave
    )
    basis = _odd_primes(scale)
    mean_velocity = fmean(int(note["velocity"]) for note in flattened)
    midi_notes: list[dict[str, Any]] = []
    for onset, group in limited_groups:
        ratios = [
            _mapped_ratio(int(note["midi_note"]), config, scale, equave)
            for note in group
        ]
        midi_notes.extend(
            {
                "ratio": _ratio_text(ratio),
                "start_beats": round(onset, 6),
                "duration_beats": round(float(note["duration_beats"]), 6),
                "velocity": int(note["velocity"]),
                "midi_note": int(note["midi_note"]),
            }
            for note, ratio in zip(group, ratios, strict=True)
        )
    motif_notes: list[dict[str, Any]] = []
    for onset, group in motif_groups:
        ratios = [
            _mapped_ratio(int(note["midi_note"]), config, scale, equave)
            for note in group
        ]
        primary = group[0]
        duration = max(float(note["duration_beats"]) for note in group)
        motif_notes.append(
            {
                "ratio": _ratio_text(ratios[0]),
                "onset_beat": round(onset, 6),
                "duration_beats": round(duration, 6),
                "velocity": max(int(note["velocity"]) for note in group),
                "accent": max(int(note["velocity"]) for note in group) >= mean_velocity + 8,
                "chord_relation": _relation(ratios[0], anchor, equave),
                "harmony_tones": [_ratio_text(value) for value in ratios[1:]],
                "midi_note": int(primary["midi_note"]),
                "monzo": _monzo(ratios[0], basis),
                "pitch_circle_cent": round(
                    _cents(_reduce(ratios[0], equave)) / _cents(equave) * 1200, 3
                ),
            }
        )
    end = max(note["onset_beat"] + note["duration_beats"] for note in motif_notes)
    gaps = [
        max(
            0,
            motif_notes[index + 1]["onset_beat"]
            - (note["onset_beat"] + note["duration_beats"]),
        )
        for index, note in enumerate(motif_notes[:-1])
    ]
    syncopated = sum(
        abs(note["onset_beat"] - round(note["onset_beat"])) > 0.04
        for note in motif_notes
    )
    affinity = fmean(
        max(
            0.0,
            1
            - min(_distance(Fraction(note["ratio"]), tone, equave) for tone in anchor)
            / (_cents(equave) / 2),
        )
        for note in motif_notes
    )
    contour = [
        int(motif_notes[index + 1]["midi_note"]) - int(note["midi_note"])
        for index, note in enumerate(motif_notes[:-1])
    ]
    polyphony = [1 + len(note["harmony_tones"]) for note in motif_notes]
    rests = [round(gap, 6) for gap in gaps if gap > 0.01]
    rhythmic_score = min(1.0, 0.35 + syncopated / max(1, len(motif_notes)) * 0.65)
    melody_score = min(1.0, 0.45 + len(set(contour)) / max(1, len(contour)) * 0.45)
    harmony_score = min(1.0, 0.35 + affinity * 0.65)
    total = fmean((rhythmic_score, melody_score, harmony_score))
    motif = {
        "id": "midi-performance-motif",
        "seed": 0,
        "prime_basis": basis,
        "anchor_chord": [_ratio_text(value) for value in anchor],
        "notes": motif_notes,
        "chord_affinity": round(affinity, 4),
        "anchor_membership": [note["chord_relation"] == "exact" for note in motif_notes],
        "contour_signature": contour,
        "rhythm_signature": {
            "rests": rests,
            "rest_ratio": round(sum(rests) / max(end, 0.001), 4),
            "syncopation": round(syncopated / len(motif_notes), 4),
        },
        "polyphony_signature": {
            "maximum": max(polyphony),
            "mean": round(fmean(polyphony), 3),
        },
        "identity_features": {
            "terminal_role": _relation(Fraction(motif_notes[-1]["ratio"]), anchor, equave)
        },
        "evaluation": {
            "rank": 1,
            "total": round(total, 4),
            "profile": "performed",
            "passed_filters": True,
            "components": {
                "harmony": round(harmony_score, 4),
                "melody": round(melody_score, 4),
                "rhythm": round(rhythmic_score, 4),
            },
            "diagnostics": {"source": "midi-toolkit", "discarded_voices": discarded},
            "rejected_reasons": [],
        },
    }
    warnings = []
    if discarded:
        warnings.append(f"Reduced {discarded} notes to the maximum polyphony")
    if truncated_steps:
        warnings.append(
            f"Motif uses the first 32 of {len(limited_groups)} performance steps"
        )
    return motif, midi_notes, warnings


def process_performance(config: dict[str, Any]) -> dict[str, Any]:
    """Quantize a keyboard performance and map it onto an exact-ratio scale."""
    equave = Fraction(config.get("equave_ratio", "2/1"))
    scale = sorted({_reduce(Fraction(value), equave) for value in config["scale_ratios"]})
    notes = _quantize(config)
    motif, midi_notes, warnings = _motif(notes, config, scale)
    duration = max(
        float(note["start_beats"]) + float(note["duration_beats"]) for note in notes
    )
    analysis = {
        "captured_notes": len(notes),
        "motif_steps": len(motif["notes"]),
        "duration_beats": round(duration, 4),
        "midi_range": [
            min(int(note["midi_note"]) for note in notes),
            max(int(note["midi_note"]) for note in notes),
        ],
        "average_velocity": round(fmean(int(note["velocity"]) for note in notes), 2),
        "maximum_polyphony": motif["polyphony_signature"]["maximum"],
        "note_density": round(len(notes) / max(duration, 0.001), 4),
        "syncopation": motif["rhythm_signature"]["syncopation"],
        "contour": motif["contour_signature"],
        "anchor_chord": motif["anchor_chord"],
        "prime_basis": motif["prime_basis"],
    }
    return {
        "schema_version": "1.0",
        "feature": "midi-creator-toolkit",
        "settings": {
            key: value for key, value in config.items() if key != "notes"
        },
        "captured_notes": notes,
        "midi_notes": midi_notes,
        "motif": motif,
        "analysis": analysis,
        "warnings": warnings,
    }
