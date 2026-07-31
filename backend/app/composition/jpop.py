"""Section-aware exact-ratio J-pop composition."""

from __future__ import annotations

from fractions import Fraction
from random import Random
from typing import Any

from app.tuning.ratios import ratio_text, reduce_to_octave


JPOP_PROFILES = (
    ("PI13", "PI 13 Fifth Keys.vital", "a_melody_fifth_keys", (48, 84), 4),
    ("PI14", "PI 14 Minor Third Pluck.vital", "b_melody_minor_pluck", (55, 91), 3),
    ("PI15", "PI 15 13-Limit Chorus Lead.vital", "chorus_lattice_lead", (60, 96), 3),
    ("PI16", "PI 16 Vocal Guide.vital", "vocal_guide", (60, 96), 1),
)

DRUM_IDS = {"kick": "PI09", "snare": "PI10", "hat": "PI11", "perc": "PI12"}
DRUM_NOTES = {"kick": 36, "snare": 38, "hat": 42, "perc": 39}


def _section_form(cycles: int) -> list[dict[str, Any]]:
    templates: list[tuple[str, str, int, float]] = [("Intro", "intro", 4, 0.32)]
    for cycle in range(1, cycles + 1):
        templates.extend(
            (
                (f"A-melody {cycle}", "a_melody", 8, 0.5 + cycle * 0.04),
                (f"B-melody {cycle}", "b_melody", 4, 0.64 + cycle * 0.04),
                (f"Chorus {cycle}", "chorus", 8, 0.8 + cycle * 0.04),
            )
        )
    templates.extend(
        (
            ("Bridge", "b_melody", 4, 0.62),
            ("Final Chorus", "chorus", 8, 1.0),
            ("Outro", "outro", 4, 0.3),
        )
    )
    cursor = 0
    result: list[dict[str, Any]] = []
    for index, (name, role, bars, energy) in enumerate(templates):
        result.append(
            {
                "id": f"section-{index + 1}",
                "name": name,
                "role": role,
                "start_bar": cursor,
                "bars": bars,
                "energy": round(min(1.0, energy), 3),
            }
        )
        cursor += bars
    return result


def _ratio_power(base: int, exponent: int) -> Fraction:
    return Fraction(base**exponent) if exponent >= 0 else Fraction(1, base**-exponent)


def _harmony_for_bar(role: str, local_bar: int, shift_depth: int) -> dict[str, Any]:
    if role in {"intro", "a_melody", "outro"}:
        exponent = (0, 1, 2, 3)[local_bar % 4]
        root = reduce_to_octave(_ratio_power(3, exponent))
        tones = tuple(reduce_to_octave(root * _ratio_power(3, step)) for step in range(3))
        return {
            "rule": "pure-fifth-stack",
            "root": root,
            "tones": tones,
            "lattice_vector": {"3": exponent, "5": 0, "13": 0},
        }
    if role == "b_melody":
        roots = (Fraction(1), Fraction(4, 3), Fraction(3, 2), Fraction(9, 8))
        root = roots[local_bar % len(roots)]
        tones = (
            reduce_to_octave(root),
            reduce_to_octave(root * Fraction(6, 5)),
            reduce_to_octave(root * Fraction(3, 2)),
        )
        return {
            "rule": "pure-minor-third",
            "root": root,
            "tones": tones,
            "lattice_vector": {"3": 0, "5": -1, "13": 0},
        }
    vectors = ((0, 0), (1, 0), (0, 1), (1, 1))
    exponent_3, exponent_13 = vectors[local_bar % len(vectors)]
    exponent_13 *= shift_depth
    root = reduce_to_octave(_ratio_power(3, exponent_3) * _ratio_power(13, exponent_13))
    tones = (
        root,
        reduce_to_octave(root * Fraction(3, 2)),
        reduce_to_octave(root * Fraction(13, 8)),
    )
    return {
        "rule": "13-limit-fifth-shift",
        "root": root,
        "tones": tones,
        "lattice_vector": {"3": exponent_3, "5": 0, "13": exponent_13},
    }


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
        "velocity": velocity,
        "articulation": articulation,
        **extra,
    }


def _drums(bar: int, role: str, energy: float) -> list[dict[str, Any]]:
    if role in {"intro", "outro"} and bar % 2:
        return []
    patterns: dict[str, tuple[float, ...]] = {
        "kick": (0.0, 2.5) if role == "chorus" else (0.0, 2.0),
        "snare": (1.0, 3.0),
        "hat": tuple(step / 2 for step in range(8)) if role == "chorus" else (0.0, 1.0, 2.0, 3.0),
        "perc": (1.5, 3.5) if role in {"b_melody", "chorus"} else (),
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
                    "velocity": round(58 + energy * 48 + (6 if onset == 0 else 0)),
                }
            )
    return events


def _vocal_phrase(
    random: Random,
    chord: tuple[Fraction, ...],
    section: dict[str, Any],
    bar: int,
    local_bar: int,
    activity: float,
) -> list[dict[str, Any]]:
    if random.random() > activity or section["role"] in {"intro", "outro"}:
        return []
    role = str(section["role"])
    patterns = {
        "a_melody": (0.0, 1.0, 2.5),
        "b_melody": (0.0, 0.75, 1.5, 2.5, 3.25),
        "chorus": (0.0, 0.5, 1.0, 2.0, 2.5, 3.0),
    }
    onsets = patterns[role]
    syllables = ("la", "na", "a", "i", "yo", "ne")
    register = Fraction(4) if role == "chorus" else Fraction(2)
    events: list[dict[str, Any]] = []
    phrase_id = f"{section['id']}-vocal-{local_bar + 1}"
    for index, onset in enumerate(onsets):
        tone = chord[(index + local_bar) % len(chord)] * register
        if index == len(onsets) - 1 and local_bar == int(section["bars"]) - 1:
            tone = chord[0] * register
        next_onset = onsets[index + 1] if index + 1 < len(onsets) else 4.0
        events.append(
            _event(
                "PI16",
                tone,
                bar * 4 + onset,
                max(0.22, (next_onset - onset) * 0.78),
                round(72 + float(section["energy"]) * 34 + random.randrange(-4, 5)),
                "vocal_syllable",
                lyric=syllables[(bar + index) % len(syllables)],
                phrase_id=phrase_id,
                section_role=role,
            )
        )
    return events


def generate_jpop(config: dict[str, Any]) -> dict[str, Any]:
    seed = int(config["seed"])
    random = Random(seed)
    tempo = float(config["tempo_bpm"])
    cycles = int(config["cycles"])
    vocal_activity = float(config["vocal_activity"])
    shift_depth = int(config["chorus_shift_depth"])
    base_frequency = float(config.get("base_frequency", 220))
    sections = _section_form(cycles)
    harmony: list[dict[str, Any]] = []
    events: list[dict[str, Any]] = []
    for section in sections:
        role = str(section["role"])
        for local_bar in range(int(section["bars"])):
            bar = int(section["start_bar"]) + local_bar
            material = _harmony_for_bar(role, local_bar, shift_depth)
            root = material["root"]
            tones = material["tones"]
            harmony.append(
                {
                    "section_id": section["id"],
                    "section_name": section["name"],
                    "section_role": role,
                    "start_beat": bar * 4,
                    "duration_beats": 4,
                    "rule": material["rule"],
                    "root_ratio": ratio_text(root),
                    "tones": [ratio_text(tone) for tone in tones],
                    "lattice_vector": material["lattice_vector"],
                }
            )
            harmony_instrument = {
                "a_melody": "PI13",
                "intro": "PI13",
                "outro": "PI13",
                "b_melody": "PI14",
                "chorus": "PI15",
            }[role]
            for voice, tone in enumerate(tones):
                events.append(
                    _event(
                        harmony_instrument,
                        tone * (Fraction(2) if role != "chorus" else Fraction(4)),
                        bar * 4 + voice * 0.035,
                        3.72,
                        round(58 + float(section["energy"]) * 44 - voice * 4),
                        "block" if role != "b_melody" else "minor_third_pulse",
                        section_role=role,
                    )
                )
            events.append(
                _event(
                    "PI05",
                    root / 2,
                    bar * 4,
                    3.4,
                    round(66 + float(section["energy"]) * 38),
                    "bass_root",
                    section_role=role,
                )
            )
            hook_onsets = (0.5, 1.5, 3.0) if role == "chorus" else (0.5, 2.5)
            for index, onset in enumerate(hook_onsets):
                events.append(
                    _event(
                        "PI04",
                        tones[(index + bar) % len(tones)] * Fraction(4),
                        bar * 4 + onset,
                        0.38,
                        round(60 + float(section["energy"]) * 38),
                        "instrumental_hook",
                        section_role=role,
                    )
                )
            events.extend(
                _vocal_phrase(
                    random,
                    tones,
                    section,
                    bar,
                    local_bar,
                    vocal_activity,
                )
            )
            events.extend(_drums(bar, role, float(section["energy"])))
    events.sort(key=lambda event: (float(event["start_beat"]), str(event["instrument_id"])))
    vocal_events = [event for event in events if event["instrument_id"] == "PI16"]
    chorus_harmony = [item for item in harmony if item["section_role"] == "chorus"]
    total_bars = sum(int(section["bars"]) for section in sections)
    profiles = [
        {
            "id": item[0],
            "preset_file": item[1],
            "role": item[2],
            "midi_range": item[3],
            "max_notes": item[4],
            "tuning_policy": "per_note_exact",
        }
        for item in JPOP_PROFILES
    ]
    return {
        "schema_version": "0.1",
        "metadata": {
            "title": "Fractional Ratio J-Pop",
            "seed": seed,
            "tempo_bpm": tempo,
            "cycles": cycles,
            "length_bars": total_bars,
            "base_frequency": base_frequency,
            "chorus_shift_depth": shift_depth,
            "vocal_activity": vocal_activity,
        },
        "sections": sections,
        "harmony": harmony,
        "events": events,
        "profiles": profiles,
        "vocal": {
            "instrument_id": "PI16",
            "event_count": len(vocal_events),
            "phrase_count": len({event["phrase_id"] for event in vocal_events}),
            "lyrics_mode": "guide_syllables",
        },
        "quality": {
            "a_melody_pure_fifth_bars": sum(item["section_role"] == "a_melody" for item in harmony),
            "b_melody_minor_third_bars": sum(
                item["rule"] == "pure-minor-third" for item in harmony
            ),
            "chorus_13_limit_bars": len(chorus_harmony),
            "chorus_shifted_roots": len({item["root_ratio"] for item in chorus_harmony}),
            "vocal_events": len(vocal_events),
            "vocal_rest_bars": total_bars
            - len({int(event["start_beat"] // 4) for event in vocal_events}),
            "deterministic": True,
        },
        "reaper_manifest": {
            "tracks": [
                {
                    "track": index + 1,
                    "instrument_id": item[0],
                    "preset_file": item[1],
                }
                for index, item in enumerate(JPOP_PROFILES)
            ]
        },
    }
