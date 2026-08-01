"""Kawaii future-bass, pop, minimalism, and exact-ratio composition."""

from __future__ import annotations

from fractions import Fraction
from random import Random
from typing import Any

from app.tuning.ratios import ratio_text, reduce_to_octave


KAWAII_PROFILES = (
    ("PI17", "PI 17 Candy Pluck.vital", "verse_candy_pluck", (55, 96), 4),
    ("PI18", "PI 18 Future Chord Stack.vital", "drop_chord_stack", (48, 96), 6),
    ("PI19", "PI 19 Fractional Vocal Guide.vital", "vocal_and_chop", (60, 100), 1),
    ("PI20", "PI 20 Minimal Pulse.vital", "phase_shift_pulse", (48, 96), 4),
    ("PI21", "PI 21 Sparkle Bell.vital", "kawaii_sparkle", (60, 108), 6),
)

DRUM_IDS = {"kick": "PI09", "snare": "PI10", "hat": "PI11", "perc": "PI12"}
DRUM_NOTES = {"kick": 36, "snare": 38, "hat": 42, "perc": 39}


def _scale(values: list[str]) -> tuple[Fraction, ...]:
    ratios = sorted({reduce_to_octave(Fraction(value)) for value in values})
    if Fraction(1) not in ratios:
        raise ValueError("scale must contain 1/1")
    return tuple(ratios)


def _form(cycles: int) -> list[dict[str, Any]]:
    templates: list[tuple[str, str, int, float]] = [
        ("Intro", "intro", 4, 0.28),
    ]
    for cycle in range(1, cycles + 1):
        templates.extend(
            (
                (f"Verse {cycle}", "verse", 8, 0.48 + cycle * 0.04),
                (f"Pre {cycle}", "pre", 4, 0.68 + cycle * 0.04),
                (f"Drop {cycle}", "drop", 8, 0.9 + cycle * 0.04),
            )
        )
    templates.extend(
        (
            ("Minimal Break", "minimal", 8, 0.42),
            ("Final Drop", "drop", 8, 1.0),
            ("Outro", "outro", 4, 0.24),
        )
    )
    result: list[dict[str, Any]] = []
    cursor = 0
    for index, (name, role, bars, energy) in enumerate(templates):
        result.append(
            {
                "id": f"section-{index + 1}",
                "name": name,
                "role": role,
                "start_bar": cursor,
                "bars": bars,
                "energy": min(1.0, round(energy, 3)),
            }
        )
        cursor += bars
    return result


def _degree(scale: tuple[Fraction, ...], index: int) -> Fraction:
    octave, degree = divmod(index, len(scale))
    return scale[degree] * Fraction(2**octave)


def _harmony(
    scale: tuple[Fraction, ...], role: str, local_bar: int, minimalism: float
) -> tuple[Fraction, tuple[Fraction, ...], str, int, str, float]:
    progressions = {
        "intro": (0, 3, 5, 4),
        "verse": (0, 4, 5, 3),
        "pre": (2, 3, 4, 4),
        "drop": (0, 5, 3, 4),
        "outro": (0, 3, 0, 0),
    }
    offsets: tuple[int, ...]
    if role == "minimal":
        hold = 4 if minimalism >= 0.66 else 2
        root_degree = (0, 5)[(local_bar // hold) % 2]
        offsets = (0, 2, 4)
        rule = "minimal-two-root-cell"
        voicing_stage = "minimal-triad"
        tension = 0.2
    elif role == "drop":
        root_degree = progressions[role][local_bar % 4]
        stage = min(3, (local_bar % 8) // 2)
        drop_voicings = (
            ((0, 2, 5), "triad-entry", 0.25),
            ((0, 3, 5), "triad-open", 0.32),
            ((0, 2, 5, 7), "four-voice-open", 0.46),
            ((0, 2, 4, 6), "four-voice-color", 0.68),
        )
        offsets, voicing_stage, tension = drop_voicings[stage]
        rule = "future-bass-gradual-color-stack"
    else:
        root_degree = progressions[role][local_bar % 4]
        offsets = (0, 2, 4)
        rule = {
            "intro": "pastel-pop-triad",
            "verse": "exact-ratio-pop",
            "pre": "rising-kawaii-color",
            "outro": "pastel-pop-triad",
        }[role]
        voicing_stage = "supporting-triad"
        tension = 0.3 if role == "pre" else 0.2
    root = reduce_to_octave(_degree(scale, root_degree))
    tones = tuple(reduce_to_octave(_degree(scale, root_degree + offset)) for offset in offsets)
    return root, tones, rule, root_degree, voicing_stage, tension


def _event(
    instrument_id: str,
    ratio: Fraction,
    start: float,
    duration: float,
    velocity: int,
    articulation: str,
    **extra: Any,
) -> dict[str, Any]:
    return {
        "instrument_id": instrument_id,
        "ratio": ratio_text(ratio),
        "start_beat": round(start, 5),
        "duration_beats": round(duration, 5),
        "velocity": max(1, min(127, velocity)),
        "articulation": articulation,
        **extra,
    }


def _drums(bar: int, role: str, energy: float) -> list[dict[str, Any]]:
    if role == "minimal":
        patterns = {"kick": (0.0,), "snare": (2.0,), "hat": (1.0, 3.0), "perc": ()}
    elif role == "drop":
        patterns = {
            "kick": (0.0, 1.5, 2.75),
            "snare": (2.0,),
            "hat": tuple(step / 2 for step in range(8)),
            "perc": (1.75, 3.5),
        }
    elif role in {"intro", "outro"}:
        patterns = {
            "kick": (0.0,) if bar % 2 == 0 else (),
            "snare": (),
            "hat": (1.0, 3.0),
            "perc": (),
        }
    else:
        patterns = {
            "kick": (0.0, 2.5),
            "snare": (1.0, 3.0),
            "hat": (0.0, 1.0, 2.0, 3.0),
            "perc": (3.5,) if role == "pre" else (),
        }
    events: list[dict[str, Any]] = []
    for layer, onsets in patterns.items():
        for onset in onsets:
            events.append(
                {
                    "instrument_id": DRUM_IDS[layer],
                    "layer": layer,
                    "note": DRUM_NOTES[layer],
                    "start_beat": bar * 4 + onset,
                    "duration_beats": 0.12,
                    "velocity": round(55 + energy * 55 + (7 if onset == 0 else 0)),
                }
            )
    return events


def _vocal(
    random: Random,
    scale: tuple[Fraction, ...],
    root_degree: int,
    section: dict[str, Any],
    bar: int,
    local_bar: int,
    activity: float,
    style: str,
) -> list[dict[str, Any]]:
    role = str(section["role"])
    if role in {"intro", "outro", "minimal"} or random.random() > activity:
        return []
    patterns = {
        "verse": (0.0, 1.0, 2.5),
        "pre": (0.0, 0.75, 1.5, 2.5, 3.25),
        "drop": (0.0, 0.5, 1.0, 2.0, 2.5, 3.0),
    }
    if style == "airy":
        patterns = {**patterns, "verse": (0.0, 1.5, 3.0), "drop": (0.0, 1.0, 2.0, 3.0)}
    elif style == "chopped":
        patterns = {**patterns, "drop": tuple(step / 2 for step in range(8))}
    onsets = patterns[role]
    hook = (0, 2, 4, 2, 5, 4, 2, 0)
    syllables = ("ki", "ra", "me", "ku", "yo", "ne", "a", "i")
    events: list[dict[str, Any]] = []
    phrase_id = f"{section['id']}-vocal-{local_bar + 1}"
    for index, onset in enumerate(onsets):
        degree = root_degree + hook[(index + (0 if role == "drop" else local_bar)) % len(hook)]
        tone = _degree(scale, degree) * (Fraction(4) if role == "drop" else Fraction(2))
        next_onset = onsets[index + 1] if index + 1 < len(onsets) else 4.0
        events.append(
            _event(
                "PI19",
                tone,
                bar * 4 + onset,
                max(0.16, (next_onset - onset) * (0.48 if style == "chopped" else 0.76)),
                round(70 + float(section["energy"]) * 35 + random.randrange(-4, 5)),
                "vocal_chop" if style == "chopped" and role == "drop" else "vocal_syllable",
                lyric=syllables[(bar + index) % len(syllables)],
                phrase_id=phrase_id,
                section_role=role,
            )
        )
    return events


def generate_kawaii_future_pop(config: dict[str, Any]) -> dict[str, Any]:
    random = Random(int(config["seed"]))
    scale = _scale(list(config["scale_ratios"]))
    minimalism = float(config["minimalism"])
    drop_intensity = float(config["drop_intensity"])
    phase_steps = int(config["phase_shift_steps"])
    sections = _form(int(config["cycles"]))
    harmony: list[dict[str, Any]] = []
    events: list[dict[str, Any]] = []
    sidechain: list[dict[str, Any]] = []
    minimal_cells: list[dict[str, Any]] = []

    for section in sections:
        role = str(section["role"])
        for local_bar in range(int(section["bars"])):
            bar = int(section["start_bar"]) + local_bar
            root, tones, rule, root_degree, voicing_stage, tension = _harmony(
                scale, role, local_bar, minimalism
            )
            harmony.append(
                {
                    "section_id": section["id"],
                    "section_name": section["name"],
                    "section_role": role,
                    "start_beat": bar * 4,
                    "duration_beats": 4,
                    "rule": rule,
                    "root_degree": root_degree,
                    "root_ratio": ratio_text(root),
                    "tones": [ratio_text(tone) for tone in tones],
                    "voice_count": len(tones),
                    "voicing_stage": voicing_stage,
                    "tension": tension,
                }
            )

            if role == "drop":
                chord_onsets = (0.0, 1.5, 2.75)
                for onset in chord_onsets:
                    for voice, tone in enumerate(tones):
                        events.append(
                            _event(
                                "PI18",
                                tone * Fraction(2),
                                bar * 4 + onset + voice * 0.018,
                                0.62,
                                round(66 + drop_intensity * 46 - voice * 3),
                                "sidechained_stack",
                                section_role=role,
                                voicing_stage=voicing_stage,
                                harmonic_tension=tension,
                            )
                        )
                    sidechain.append(
                        {
                            "start_beat": bar * 4 + onset,
                            "duration_beats": 0.5,
                            "amount": round(drop_intensity, 3),
                            "target": "PI18",
                        }
                    )
                for onset in (0.75, 2.25, 3.5):
                    events.append(
                        _event(
                            "PI21",
                            tones[(bar + int(onset * 2)) % len(tones)] * Fraction(4),
                            bar * 4 + onset,
                            0.3,
                            82,
                            "sparkle",
                            section_role=role,
                        )
                    )
            elif role == "minimal":
                density = max(1, round(4 - minimalism * 2))
                cell = tuple(_degree(scale, root_degree + step) for step in (0, 2, 4))
                phase = phase_steps * 0.25
                for lane, offset in (("A", 0.0), ("B", phase)):
                    for step in range(density):
                        onset = step * (4 / density) + offset
                        if onset < 4:
                            events.append(
                                _event(
                                    "PI20",
                                    cell[(step + (lane == "B")) % len(cell)] * Fraction(2),
                                    bar * 4 + onset,
                                    0.24,
                                    64 + (lane == "B") * 8,
                                    "minimal_pulse",
                                    section_role=role,
                                    phase_lane=lane,
                                )
                            )
                minimal_cells.append(
                    {
                        "bar": bar + 1,
                        "ratios": [ratio_text(tone) for tone in cell],
                        "phase_shift_beats": phase,
                        "pulses_per_bar": density,
                    }
                )
            else:
                instrument = "PI17"
                onsets = (0.5, 2.5) if role in {"verse", "pre"} else (0.0, 2.0)
                for onset in onsets:
                    for voice, tone in enumerate(tones):
                        events.append(
                            _event(
                                instrument,
                                tone * Fraction(2),
                                bar * 4 + onset + voice * 0.025,
                                0.42,
                                60 + round(float(section["energy"]) * 36) - voice * 3,
                                "candy_pluck",
                                section_role=role,
                            )
                        )

            events.append(
                _event(
                    "PI05",
                    root / 2,
                    bar * 4,
                    3.35 if role != "drop" else 1.25,
                    round(62 + float(section["energy"]) * 40),
                    "sub_root",
                    section_role=role,
                )
            )
            events.extend(
                _vocal(
                    random,
                    scale,
                    root_degree,
                    section,
                    bar,
                    local_bar,
                    float(config["vocal_activity"]),
                    str(config["vocal_style"]),
                )
            )
            events.extend(_drums(bar, role, float(section["energy"])))

    events.sort(key=lambda event: (float(event["start_beat"]), str(event["instrument_id"])))
    pitched = [event for event in events if "ratio" in event]
    vocal_events = [event for event in events if event["instrument_id"] == "PI19"]
    total_bars = sum(int(section["bars"]) for section in sections)
    scale_text = [ratio_text(value) for value in scale]
    return {
        "schema_version": "0.1",
        "metadata": {
            "title": "Kawaii Fractional Future Pop",
            "seed": int(config["seed"]),
            "tempo_bpm": float(config["tempo_bpm"]),
            "cycles": int(config["cycles"]),
            "length_bars": total_bars,
            "base_frequency": float(config["base_frequency"]),
            "minimalism": minimalism,
            "drop_intensity": drop_intensity,
            "phase_shift_steps": phase_steps,
            "vocal_style": str(config["vocal_style"]),
        },
        "scale": {
            "ratios": scale_text,
            "prime_limit": 13 if any(value.numerator % 13 == 0 for value in scale) else 7,
        },
        "sections": sections,
        "harmony": harmony,
        "events": events,
        "profiles": [
            {
                "id": item[0],
                "preset_file": item[1],
                "role": item[2],
                "midi_range": item[3],
                "max_notes": item[4],
                "tuning_policy": "per_note_exact",
            }
            for item in KAWAII_PROFILES
        ],
        "minimal_process": {
            "cells": minimal_cells,
            "phase_shift_beats": phase_steps * 0.25,
            "repetition": round(minimalism, 3),
        },
        "sidechain_envelope": sidechain,
        "vocal": {
            "instrument_id": "PI19",
            "event_count": len(vocal_events),
            "phrase_count": len({event["phrase_id"] for event in vocal_events}),
            "lyrics_mode": "guide_syllables",
            "style": str(config["vocal_style"]),
        },
        "quality": {
            "pitched_events": len(pitched),
            "minimal_bars": sum(
                section["bars"] for section in sections if section["role"] == "minimal"
            ),
            "drop_bars": sum(section["bars"] for section in sections if section["role"] == "drop"),
            "vocal_rest_bars": total_bars
            - len({int(event["start_beat"] // 4) for event in vocal_events}),
            "sidechain_triggers": len(sidechain),
            "drop_three_voice_bars": sum(
                item["section_role"] == "drop" and item["voice_count"] == 3 for item in harmony
            ),
            "maximum_drop_tension": max(
                float(item["tension"]) for item in harmony if item["section_role"] == "drop"
            ),
            "deterministic": True,
        },
    }
