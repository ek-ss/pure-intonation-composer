"""Role-aware Vital Pack arrangement generator."""

from __future__ import annotations

from fractions import Fraction
from random import Random
from typing import Any

from app.rhythm.engine import euclidean_rhythm
from app.tuning.ratios import ratio_text


PROFILES = (
    ("PI01", "PI 01 Clear Supersaw.vital", "main_harmony", (48, 84), 5, "chord_snapshot", True),
    ("PI02", "PI 02 Dream Chord.vital", "secondary_harmony", (55, 91), 5, "common_tone_lock", True),
    ("PI03", "PI 03 Air Pad.vital", "background_pad", (36, 84), 4, "sustained_note_lock", True),
    ("PI04", "PI 04 Gentle Pluck.vital", "arpeggio", (60, 96), 2, "per_note_exact", False),
    ("PI05", "PI 05 Warm Bass.vital", "bass", (28, 52), 1, "root_anchored", False),
    ("PI06", "PI 06 Glass Bell.vital", "high_accent", (72, 108), 2, "onset_locked", False),
    (
        "PI07",
        "PI 07 Minimal Pulse.vital",
        "rhythmic_harmony",
        (48, 79),
        4,
        "per_chord_retrigger",
        False,
    ),
    ("PI08", "PI 08 Wide JI Pad.vital", "feature_pad", (43, 84), 4, "common_tone_lock", True),
)

FORM = (
    ("Intro", 8, 0.15),
    ("A", 8, 0.30),
    ("Build", 8, 0.55),
    ("Drop 1", 16, 0.90),
    ("Break", 8, 0.35),
    ("Final Drop", 12, 1.0),
    ("Outro", 4, 0.20),
)
CHORDS = {
    "T": (Fraction(1), Fraction(5, 4), Fraction(3, 2)),
    "PD": (Fraction(4, 3), Fraction(5, 3), Fraction(2)),
    "D": (Fraction(3, 2), Fraction(15, 8), Fraction(9, 4)),
}


def vital_pack_profiles() -> dict[str, object]:
    return {
        "schema_version": "0.1",
        "pack": "Pure Intonation Vital Pack",
        "synth_version": "1.6.4",
        "instruments": [
            {
                "id": item[0],
                "preset_file": item[1],
                "role": item[2],
                "midi_range": item[3],
                "max_notes": item[4],
                "tuning_policy": item[5],
                "wide_sustained": item[6],
            }
            for item in PROFILES
        ],
        "global_constraints": {
            "max_wide_sustained_layers": 2,
            "section_drift_limit_cents": 20,
            "final_anchor_error_cents": 2,
        },
    }


def _sections(length: int) -> list[dict[str, Any]]:
    raw = [bars / 64 * length for _, bars, _ in FORM]
    allocated = [max(1, round(value)) for value in raw]
    while sum(allocated) > length:
        index = max(
            (index for index, value in enumerate(allocated) if value > 1),
            key=lambda index: allocated[index],
            default=-1,
        )
        if index < 0:
            break
        allocated[index] -= 1
    while sum(allocated) < length:
        index = max(range(len(allocated)), key=lambda item: raw[item] - allocated[item])
        allocated[index] += 1
    start = 0
    result: list[dict[str, Any]] = []
    for (name, _bars, energy), actual in zip(FORM, allocated, strict=True):
        result.append({"name": name, "start_bar": start + 1, "bars": actual, "energy": energy})
        start += actual
    return result


def _active(section: str, mode: str) -> list[str]:
    table = {
        "Intro": ["PI03", "PI07", "PI06"],
        "A": ["PI03", "PI04", "PI05"],
        "Build": ["PI02", "PI04", "PI05", "PI07"],
        "Drop 1": ["PI01", "PI04", "PI05", "PI06", "DRUMS"],
        "Break": ["PI08", "PI03", "PI06"],
        "Final Drop": ["PI01", "PI02", "PI05", "PI07", "PI06", "DRUMS"],
        "Outro": ["PI03", "PI05"],
    }
    selected = table[section]
    return (
        ["PI01", "PI02", "PI03", "PI04", "PI05", "PI06", "PI07", "PI08", "DRUMS"]
        if mode == "showcase"
        else selected
    )


def generate_vital_pack(config: dict[str, Any]) -> dict[str, object]:
    random = Random(int(config["seed"]))
    length = int(config["length_bars"])
    tempo = float(config["tempo_bpm"])
    mode = str(config["preset_mode"])
    sections = _sections(length)
    events: list[dict[str, object]] = []
    automation: list[dict[str, object]] = []
    tuning: list[dict[str, object]] = []
    harmony: list[dict[str, object]] = []
    previous = "T"
    for section in sections:
        name, start, bars, energy = (
            str(section["name"]),
            int(section["start_bar"]) - 1,
            int(section["bars"]),
            float(section["energy"]),
        )
        active = _active(name, mode)
        section["active_instruments"] = active
        for bar in range(start, start + bars):
            function = (
                "T"
                if name == "Outro"
                else random.choices(
                    ("T", "PD", "D"),
                    weights=(0.6, 0.25, 0.15)
                    if name in {"Intro", "A", "Break"}
                    else (0.25, 0.30, 0.45),
                )[0]
            )
            if previous == "D" and random.random() < 0.65:
                function = "T"
            chord = CHORDS[function]
            harmony.append(
                {
                    "start_beat": bar * 4,
                    "duration_beats": 4,
                    "functional_state": function,
                    "root_ratio": ratio_text(chord[0]),
                    "tones": [ratio_text(tone) for tone in chord],
                    "tension": {"T": 0.2, "PD": 0.52, "D": 0.8}[function],
                }
            )
            previous = function
            for instrument in active:
                if instrument == "DRUMS":
                    for layer, note, pulses in (
                        ("kick", 36, 3),
                        ("snare", 38, 2),
                        ("hat", 42, 5),
                        ("perc", 39, 2),
                    ):
                        for step, hit in enumerate(
                            euclidean_rhythm(8, max(1, round(pulses * energy)), (bar + note) % 8)
                        ):
                            if hit:
                                events.append(
                                    {
                                        "instrument_id": "DRUMS",
                                        "layer": layer,
                                        "note": note,
                                        "start_beat": bar * 4 + step / 2,
                                        "duration_beats": 0.12,
                                        "velocity": round(62 + energy * 45),
                                    }
                                )
                    continue
                profile = next(item for item in PROFILES if item[0] == instrument)
                policy = profile[5]
                tones = chord[: profile[4]]
                if instrument == "PI05":
                    tones = chord[:1]
                if instrument == "PI04":
                    tones = (chord[bar % len(chord)],)
                if instrument == "PI06":
                    tones = (chord[-1],) if bar % 2 == 0 else ()
                if instrument == "PI07":
                    tones = chord[: min(3, len(chord))]
                starts: list[float] = [float(bar * 4)]
                if instrument == "PI04":
                    starts = [
                        bar * 4 + step / 2
                        for step, hit in enumerate(
                            euclidean_rhythm(8, 3 if energy < 0.6 else 5, bar % 8)
                        )
                        if hit
                    ]
                if instrument == "PI07":
                    starts = [
                        bar * 4 + step / 2
                        for step, hit in enumerate(
                            euclidean_rhythm(8, 3 if energy < 0.6 else 5, (bar + 2) % 8)
                        )
                        if hit
                    ]
                for onset in starts:
                    for voice, ratio in enumerate(tones):
                        events.append(
                            {
                                "instrument_id": instrument,
                                "start_beat": onset + voice * (0.035 + energy * 0.025),
                                "duration_beats": 0.42 if instrument in {"PI04", "PI07"} else 3.7,
                                "ratio": ratio_text(
                                    ratio
                                    * (
                                        Fraction(2)
                                        ** (0 if instrument in {"PI03", "PI05", "PI08"} else 1)
                                    )
                                ),
                                "velocity": round(54 + energy * 55),
                                "articulation": "pulse" if instrument == "PI07" else "sustain",
                                "voice_id": f"{instrument}-{voice + 1}",
                                "tuning_policy": policy,
                            }
                        )
                        tuning.append(
                            {
                                "time": onset,
                                "instrument_id": instrument,
                                "ratio": ratio_text(ratio),
                                "policy": policy,
                                "cents_offset": 0,
                            }
                        )
        for instrument in active:
            if instrument == "DRUMS":
                continue
            automation.extend(
                {
                    "instrument_id": instrument,
                    "parameter": parameter,
                    "start_beat": start * 4,
                    "end_beat": (start + bars) * 4,
                    "start_value": round(max(0, energy - 0.18), 3),
                    "end_value": round(min(1, energy + 0.12), 3),
                    "curve": "linear",
                }
                for parameter in ("brightness", "motion", "space", "width")
            )
    manifest = [
        {
            "track": index + 2,
            "instrument_id": item[0],
            "preset_file": item[1],
            "tuning_policy": item[5],
            "midi_range": item[3],
        }
        for index, item in enumerate(PROFILES)
    ]
    return {
        "metadata": {
            "title": "Vital Pack Study",
            "seed": config["seed"],
            "tempo_bpm": tempo,
            "length_bars": length,
            "tuning": config["tuning"],
            "preset_mode": mode,
        },
        "profiles": vital_pack_profiles(),
        "sections": sections,
        "harmony": harmony,
        "events": events,
        "tuning_timeline": tuning,
        "automation": automation,
        "reaper_manifest": {
            "tracks": [{"track": 1, "instrument_id": "DRUMS", "preset_file": "External sampler"}]
            + manifest,
            "tuning_control_track": 11,
        },
        "quality": {"wide_sustained_max": 2, "final_anchor_error_cents": 0, "deterministic": True},
    }
