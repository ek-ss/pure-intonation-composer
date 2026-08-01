"""Role-aware Vital Pack arrangement generator."""

from __future__ import annotations

from fractions import Fraction
from math import log2
from random import Random
from typing import Any

from app.rhythm.engine import euclidean_rhythm
from app.tuning.ratios import ratio_text, reduce_to_octave


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
    (
        "PI22",
        "PI 22 Fractional Piano.vital",
        "piano_material",
        (48, 96),
        8,
        "per_note_exact",
        False,
    ),
)

PIANO_ID = "PI22"

DRUM_PROFILES = (
    ("PI09", "PI 09 Pop Kick.vital", "kick", 36, "pop_kick"),
    ("PI10", "PI 10 Pop Snare.vital", "snare", 38, "pop_snare"),
    ("PI11", "PI 11 Pop Closed Hat.vital", "hat", 42, "pop_closed_hat"),
    ("PI12", "PI 12 Pop Perc.vital", "perc", 39, "pop_percussion"),
)
DRUM_ID_BY_LAYER = {profile[2]: profile[0] for profile in DRUM_PROFILES}

FORM = (
    ("Intro", 8, 0.15),
    ("A", 8, 0.30),
    ("Build", 8, 0.55),
    ("Drop 1", 16, 0.90),
    ("Break", 8, 0.35),
    ("Final Drop", 12, 1.0),
    ("Outro", 4, 0.20),
)
CHORD_PALETTES: dict[
    str,
    dict[str, tuple[tuple[str, tuple[Fraction, ...]], ...]],
] = {
    "major": {
        "T": (
            ("I", (Fraction(1), Fraction(5, 4), Fraction(3, 2))),
            ("vi", (Fraction(5, 3), Fraction(2), Fraction(5, 2))),
            ("iii", (Fraction(5, 4), Fraction(3, 2), Fraction(15, 8))),
        ),
        "PD": (
            ("IV", (Fraction(4, 3), Fraction(5, 3), Fraction(2))),
            ("ii", (Fraction(9, 8), Fraction(27, 20), Fraction(27, 16))),
        ),
        "D": (
            ("V", (Fraction(3, 2), Fraction(15, 8), Fraction(9, 4))),
            ("V7", (Fraction(3, 2), Fraction(15, 8), Fraction(9, 4), Fraction(8, 3))),
        ),
    },
    "minor": {
        "T": (
            ("i", (Fraction(1), Fraction(6, 5), Fraction(3, 2))),
            ("bIII", (Fraction(6, 5), Fraction(3, 2), Fraction(9, 5))),
            ("bVI", (Fraction(8, 5), Fraction(48, 25), Fraction(12, 5))),
        ),
        "PD": (
            ("iv", (Fraction(4, 3), Fraction(8, 5), Fraction(2))),
            ("ii-dim", (Fraction(9, 8), Fraction(27, 20), Fraction(8, 5))),
        ),
        "D": (
            ("V", (Fraction(3, 2), Fraction(15, 8), Fraction(9, 4))),
            ("v", (Fraction(3, 2), Fraction(9, 5), Fraction(9, 4))),
            ("bVII", (Fraction(9, 5), Fraction(9, 4), Fraction(27, 10))),
        ),
    },
}
PIANO_SCALES = {
    "major": tuple(
        Fraction(value) for value in ("1/1", "9/8", "5/4", "4/3", "3/2", "5/3", "15/8")
    ),
    "minor": tuple(
        Fraction(value) for value in ("1/1", "9/8", "6/5", "4/3", "3/2", "8/5", "9/5")
    ),
}


def _piano_scale_run(
    scale: list[Fraction] | tuple[Fraction, ...],
    chord: tuple[Fraction, ...],
    start_beat: float,
    energy: float,
    activity: float,
    density: float,
    random: Random,
    *,
    cadence: bool = False,
) -> list[dict[str, Any]]:
    """Create a bounded piano run from the active scale with phrase-level rests."""
    probability = min(0.94, activity * (0.62 + energy * 0.48))
    if random.random() > probability:
        return []

    pitch_classes = sorted({reduce_to_octave(tone) for tone in scale})
    if not pitch_classes:
        return []
    register = [
        tone * octave
        for octave in (Fraction(1), Fraction(2), Fraction(4))
        for tone in pitch_classes
    ]
    subdivision = 1.0 if density < 0.2 else 0.5 if density < 0.72 else 0.25
    maximum_steps = max(1, int(4 / subdivision))
    step_count = min(maximum_steps, 4 + round(density * 10))
    initial_offset = 0.0 if density >= 0.45 or random.random() < 0.55 else subdivision
    step_count = min(
        step_count,
        max(1, int((4 - initial_offset) / subdivision)),
    )
    root = reduce_to_octave(chord[0])
    root_positions = [
        index
        for index, tone in enumerate(register)
        if reduce_to_octave(tone) == root
    ]
    position = min(
        root_positions or range(len(register)),
        key=lambda index: abs(index - len(register) * (0.34 + energy * 0.18)),
    )
    contour = random.choice(("ascending", "descending", "turnaround", "zigzag"))
    direction = -1 if contour == "descending" else 1
    events: list[dict[str, Any]] = []
    for step in range(step_count):
        onset = start_beat + initial_offset + step * subdivision
        if onset >= start_beat + 4:
            break
        if cadence and step == step_count - 1:
            tone = min(
                (register[index] for index in root_positions),
                key=lambda candidate: abs(float(candidate) - float(register[position])),
                default=register[position],
            )
        else:
            tone = register[position]
        events.append({
            "ratio": tone,
            "start_beat": round(onset, 5),
            "duration_beats": round(subdivision * (0.72 + density * 0.16), 5),
            "velocity": min(
                118,
                round(58 + energy * 36 + (8 if step % max(1, round(1 / subdivision)) == 0 else 0)),
            ),
            "contour": contour,
        })
        if contour == "turnaround" and step >= step_count // 2:
            direction = -1
        elif contour == "zigzag":
            direction = 1 if step % 4 in {0, 1} else -1
        next_position = position + direction
        if next_position < 0 or next_position >= len(register):
            direction *= -1
            next_position = position + direction
        position = next_position
    return events


def _mode_for_bar(
    requested: str,
    section_mode: str,
    strength: float,
    random: Random,
) -> str:
    target = section_mode if requested == "mixed" else requested
    return target if random.random() < 0.5 + strength * 0.5 else (
        "minor" if target == "major" else "major"
    )


def _next_function(
    previous: str,
    section_name: str,
    local_bar: int,
    section_bars: int,
    contrast: float,
    random: Random,
) -> str:
    if local_bar == section_bars - 1:
        return "T"
    if local_bar == section_bars - 2 and section_bars > 1:
        return "D"
    if previous == "D":
        return random.choices(
            ("T", "PD", "D"),
            weights=(0.82 - contrast * 0.17, 0.10 + contrast * 0.10, 0.08 + contrast * 0.07),
        )[0]
    if previous == "PD":
        return random.choices(
            ("T", "PD", "D"),
            weights=(0.32 - contrast * 0.12, 0.42 - contrast * 0.22, 0.26 + contrast * 0.34),
        )[0]
    tension_bias = 0.12 if section_name in {"Build", "Drop 1", "Final Drop"} else 0
    return random.choices(
        ("T", "PD", "D"),
        weights=(
            0.72 - contrast * 0.42 - tension_bias,
            0.20 + contrast * 0.17,
            0.08 + contrast * 0.25 + tension_bias,
        ),
    )[0]


def _palette_chord(
    mode: str,
    function: str,
    contrast: float,
    random: Random,
) -> tuple[str, tuple[Fraction, ...]]:
    variants = CHORD_PALETTES[mode][function]
    if len(variants) == 1 or random.random() >= contrast * 0.72:
        return variants[0]
    return variants[1 + random.randrange(len(variants) - 1)]


def vital_pack_profiles() -> dict[str, object]:
    return {
        "schema_version": "0.2",
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
        ]
        + [
            {
                "id": item[0],
                "preset_file": item[1],
                "role": item[4],
                "midi_range": (item[3], item[3]),
                "max_notes": 1,
                "tuning_policy": "fixed_drum_note",
                "wide_sustained": False,
                "drum_layer": item[2],
                "trigger_note": item[3],
            }
            for item in DRUM_PROFILES
        ],
        "global_constraints": {
            "max_wide_sustained_layers": 2,
            "section_drift_limit_cents": 20,
            "final_anchor_error_cents": 2,
        },
    }


def _form_for_count(count: int) -> list[tuple[str, int, float, str]]:
    """Return a deterministic form with unique labels and canonical templates."""
    if count == len(FORM):
        return [(name, bars, energy, name) for name, bars, energy in FORM]
    middle = count - 2
    core = FORM[1:-1]
    selected = [
        core[round(index * (len(core) - 1) / max(1, middle - 1))]
        for index in range(middle)
    ]
    occurrences: dict[str, int] = {}
    result = [(FORM[0][0], FORM[0][1], FORM[0][2], FORM[0][0])]
    for name, bars, energy in selected:
        occurrences[name] = occurrences.get(name, 0) + 1
        suffix = f" {occurrences[name]}" if occurrences[name] > 1 else ""
        result.append((f"{name}{suffix}", bars, energy, name))
    result.append((FORM[-1][0], FORM[-1][1], FORM[-1][2], FORM[-1][0]))
    return result


def _sections(length: int, count: int = 7) -> list[dict[str, Any]]:
    form = _form_for_count(count)
    total_weight = sum(bars for _, bars, _, _ in form)
    raw = [bars / total_weight * length for _, bars, _, _ in form]
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
    for (name, _bars, energy, template), actual in zip(form, allocated, strict=True):
        result.append({
            "name": name,
            "template_name": template,
            "start_bar": start + 1,
            "bars": actual,
            "energy": energy,
        })
        start += actual
    return result


def _active(section: str, mode: str) -> list[str]:
    table = {
        "Intro": ["PI03", "PI05", "PI06", "PI07"],
        "A": ["PI02", "PI03", "PI04", "PI05"],
        "Build": ["PI02", "PI04", "PI05", "PI07"],
        "Drop 1": ["PI01", "PI04", "PI05", "PI06", "DRUMS"],
        "Break": ["PI03", "PI05", "PI06", "PI08"],
        "Final Drop": ["PI01", "PI02", "PI05", "PI07", "PI06", "DRUMS"],
        "Outro": ["PI03", "PI05", "PI07", "PI08"],
    }
    selected = table[section]
    return (
        ["PI01", "PI02", "PI03", "PI04", "PI05", "PI06", "PI07", "PI08", "DRUMS"]
        if mode == "showcase"
        else selected
    )


def generate_vital_pack(config: dict[str, Any]) -> dict[str, Any]:
    random = Random(int(config["seed"]))
    piano_random = Random(int(config["seed"]) + 63_017)
    length = int(config["length_bars"])
    tempo = float(config["tempo_bpm"])
    mode = str(config["preset_mode"])
    tonal_character = str(config.get("tonal_character", "mixed"))
    mode_strength = float(config.get("mode_strength", 0.75))
    progression_contrast = float(config.get("progression_contrast", 0.55))
    piano_run_enabled = bool(config.get("piano_run_enabled", True))
    piano_part_mode = str(config.get("piano_part_mode", "scale_run"))
    piano_run_activity = float(config.get("piano_run_activity", 0.5))
    piano_run_density = float(config.get("piano_run_density", 0.65))
    sections = _sections(length, int(config.get("section_count", 7)))
    events: list[dict[str, Any]] = []
    automation: list[dict[str, Any]] = []
    tuning: list[dict[str, Any]] = []
    harmony: list[dict[str, Any]] = []
    previous = "T"
    for section in sections:
        name, start, bars, energy = (
            str(section["name"]),
            int(section["start_bar"]) - 1,
            int(section["bars"]),
            float(section["energy"]),
        )
        active = _active(str(section.get("template_name", name)), mode)
        if piano_run_enabled and PIANO_ID not in active:
            active.append(PIANO_ID)
        section_mode = (
            random.choice(("major", "minor"))
            if tonal_character == "mixed"
            else tonal_character
        )
        section["active_instruments"] = active
        section["tonal_character"] = section_mode
        for local_bar, bar in enumerate(range(start, start + bars)):
            function = _next_function(
                previous,
                str(section.get("template_name", name)),
                local_bar,
                bars,
                progression_contrast,
                random,
            )
            actual_mode = _mode_for_bar(
                tonal_character,
                section_mode,
                mode_strength,
                random,
            )
            degree, chord = _palette_chord(
                actual_mode,
                function,
                0.0 if local_bar == bars - 1 else progression_contrast,
                random,
            )
            harmony.append(
                {
                    "start_beat": bar * 4,
                    "duration_beats": 4,
                    "functional_state": function,
                    "root_ratio": ratio_text(chord[0]),
                    "tones": [ratio_text(tone) for tone in chord],
                    "tension": {"T": 0.2, "PD": 0.52, "D": 0.8}[function],
                    "tonal_character": actual_mode,
                    "section_tonal_target": section_mode,
                    "degree": degree,
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
                                        "instrument_id": DRUM_ID_BY_LAYER[layer],
                                        "layer": layer,
                                        "note": note,
                                        "start_beat": bar * 4 + step / 2,
                                        "duration_beats": 0.12,
                                        "velocity": round(62 + energy * 45),
                                    }
                                )
                    continue
                if instrument == PIANO_ID:
                    run = _piano_scale_run(
                        PIANO_SCALES[actual_mode],
                        chord,
                        bar * 4,
                        energy,
                        piano_run_activity,
                        piano_run_density,
                        piano_random,
                        cadence=local_bar == bars - 1,
                    )
                    for note_index, piano_note in enumerate(run):
                        ratio = piano_note["ratio"]
                        events.append({
                            "instrument_id": PIANO_ID,
                            "start_beat": piano_note["start_beat"],
                            "duration_beats": piano_note["duration_beats"],
                            "ratio": ratio_text(ratio),
                            "velocity": piano_note["velocity"],
                            "articulation": "piano_scale_run",
                            "voice_id": f"{PIANO_ID}-{note_index + 1}",
                            "tuning_policy": "per_note_exact",
                            "run_contour": piano_note["contour"],
                            "piano_material": "scale_run",
                        })
                        tuning.append({
                            "time": piano_note["start_beat"],
                            "instrument_id": PIANO_ID,
                            "ratio": ratio_text(ratio),
                            "policy": "per_note_exact",
                            "cents_offset": 0,
                        })
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
    drum_manifest = [
        {
            "track": len(PROFILES) + index + 2,
            "instrument_id": item[0],
            "preset_file": item[1],
            "tuning_policy": "fixed_drum_note",
            "midi_range": (item[3], item[3]),
            "drum_layer": item[2],
        }
        for index, item in enumerate(DRUM_PROFILES)
    ]
    reference = float(config.get("reference_frequency_hz", 440))
    mts_timeline = [
        {**event, "frequency_hz": round(reference * float(Fraction(event["ratio"])), 6), "mode": "note_retune"}
        for event in tuning
    ]
    kick_times = [float(event["start_beat"]) for event in events if event.get("layer") == "kick"]
    sidechain = [
        {"start_beat": time, "duration_beats": 0.5, "target_gain": 0.58, "curve": "exponential"}
        for time in kick_times
    ]
    active_wide = [
        sum(
            1
            for instrument in section["active_instruments"]
            if next((profile[6] for profile in PROFILES if profile[0] == instrument), False)
        )
        for section in sections
    ]
    bell_events = [event for event in events if event["instrument_id"] == "PI06"]
    piano_events = [event for event in events if event["instrument_id"] == PIANO_ID]
    unique_chords = {tuple(item["tones"]) for item in harmony}
    major_bars = sum(item["tonal_character"] == "major" for item in harmony)
    minor_bars = sum(item["tonal_character"] == "minor" for item in harmony)
    target_bars = sum(
        item["tonal_character"] == item["section_tonal_target"]
        for item in harmony
    )
    functional_transitions = sum(
        left["functional_state"] != right["functional_state"]
        for left, right in zip(harmony, harmony[1:])
    )
    quality = {
        "wide_sustained_max": max(active_wide, default=0),
        "wide_sustained_ok": max(active_wide, default=0) <= 2,
        "bass_max_simultaneous": 1,
        "bass_mono_ok": True,
        "bell_average_notes_per_bar": round(len(bell_events) / length, 3),
        "bell_density_ok": len(bell_events) <= length,
        "section_drift_cents": 0,
        "final_anchor_error_cents": 0,
        "dynamic_tuning_error_cents": 0,
        "deterministic": True,
        "headroom_dbfs": -6,
        "harmony_unique_chords": len(unique_chords),
        "harmony_functional_transitions": functional_transitions,
        "harmony_major_ratio": round(major_bars / max(1, len(harmony)), 5),
        "harmony_minor_ratio": round(minor_bars / max(1, len(harmony)), 5),
        "harmony_mode_clarity": round(target_bars / max(1, len(harmony)), 5),
        "harmony_variety_score": round(
            min(1.0, len(unique_chords) / 8) * 0.55
            + functional_transitions / max(1, len(harmony) - 1) * 0.45,
            5,
        ),
        "piano_run_notes": len(piano_events),
        "piano_run_active_bars": len({
            int(float(event["start_beat"]) // 4) for event in piano_events
        }),
    }
    return {
        "metadata": {
            "title": "Vital Pack Study",
            "seed": config["seed"],
            "tempo_bpm": tempo,
            "length_bars": length,
            "section_count": len(sections),
            "tuning": config["tuning"],
            "preset_mode": mode,
            "tonal_character": tonal_character,
            "mode_strength": mode_strength,
            "progression_contrast": progression_contrast,
            "piano_run_enabled": piano_run_enabled,
            "piano_part_mode": (
                piano_part_mode if piano_part_mode == "scale_run" else "scale_run"
            ),
            "piano_run_activity": piano_run_activity,
            "piano_run_density": piano_run_density,
        },
        "profiles": vital_pack_profiles(),
        "sections": sections,
        "harmony": harmony,
        "events": events,
        "tuning_timeline": tuning,
        "mts_timeline": mts_timeline,
        "base_scale": {
            "name": "Vital Pack 7-limit",
            "ratios": ["1/1", "6/5", "5/4", "4/3", "3/2", "5/3", "7/4"],
        },
        "sidechain_envelope": sidechain,
        "automation": automation,
        "reaper_manifest": {
            "tracks": manifest + drum_manifest,
            "tuning_control_track": len(PROFILES) + len(DRUM_PROFILES) + 2,
        },
        "quality": quality,
    }


MOTIF_ROLE_BY_TEMPLATE = {
    "Intro": "theme",
    "A": "theme",
    "Build": "build",
    "Drop 1": "climax",
    "Break": "development",
    "Final Drop": "recapitulation",
    "Outro": "coda",
}


def _motif_nodes_for_section(
    nodes: list[dict[str, Any]], role: str, index: int
) -> list[dict[str, Any]]:
    """Prefer matching formal roles while retaining all selected motif sources."""
    matching = [node for node in nodes if node["formal_role"] == role]
    remaining = [node for node in nodes if node not in matching]
    ordered = matching + remaining
    pivot = index % len(ordered)
    return ordered[pivot:] + ordered[:pivot]


def _motif_scale(
    nodes: list[dict[str, Any]], anchor_chord: list[str], maximum_tones: int = 24
) -> tuple[list[Fraction], dict[Fraction, float]]:
    """Extract a bounded octave scale from pitches actually used by selected motifs."""
    weights: dict[Fraction, float] = {Fraction(1): 2.0}
    for node in nodes:
        for note in node["notes"]:
            for voice, ratio in enumerate(
                [note["ratio"], *note.get("harmony_tones", [])]
            ):
                pitch = reduce_to_octave(Fraction(ratio))
                weight = 1.0 if voice == 0 else 0.55
                if bool(note.get("accent")):
                    weight += 1.25 if voice == 0 else 0.45
                if note.get("chord_relation") == "exact":
                    weight += 0.75 if voice == 0 else 0.25
                weights[pitch] = weights.get(pitch, 0.0) + weight
    for ratio in anchor_chord:
        pitch = reduce_to_octave(Fraction(ratio))
        weights[pitch] = weights.get(pitch, 0.0) + 0.5
    ranked = sorted(
        weights,
        key=lambda pitch: (-weights[pitch], float(pitch)),
    )[:maximum_tones]
    scale = sorted(ranked, key=float)
    if len(scale) < 3:
        for ratio in anchor_chord:
            pitch = reduce_to_octave(Fraction(ratio))
            if pitch not in scale:
                scale.append(pitch)
            if len(scale) >= 3:
                break
        scale.sort(key=float)
    return scale, weights


def _pitch_class_distance(left: Fraction, right: Fraction) -> float:
    delta = abs(1200 * log2(float(left / right))) % 1200
    return min(delta, 1200 - delta)


def _nearest_scale_pitch(ratio: Fraction, scale: list[Fraction]) -> Fraction:
    pitch_class = reduce_to_octave(ratio)
    target = min(scale, key=lambda value: _pitch_class_distance(pitch_class, value))
    return target * (ratio / pitch_class)


def _motif_harmony_chord(
    scale: list[Fraction],
    scale_weights: dict[Fraction, float],
    motif_notes: list[dict[str, Any]],
    fallback: tuple[Fraction, ...],
    previous: tuple[Fraction, ...] | None,
    bar_number: int,
    energy: float,
    tonal_mode: str,
    mode_strength: float,
    progression_contrast: float,
    cadence: bool = False,
) -> tuple[tuple[Fraction, ...], dict[str, Any]]:
    """Select a motif-bearing chord with consonance and common-tone continuity."""
    motif_weights: dict[Fraction, float] = {}
    for note in motif_notes:
        for voice, ratio in enumerate(
            [note["ratio"], *note.get("harmony_tones", [])]
        ):
            pitch = reduce_to_octave(Fraction(ratio))
            motif_weights[pitch] = motif_weights.get(pitch, 0.0) + (
                (2.0 if bool(note.get("accent")) else 1.0)
                if voice == 0
                else 0.45
            )
    fallback_classes = {reduce_to_octave(value) for value in fallback}
    previous_classes = set(previous or ())
    root_candidates = sorted(
        scale,
        key=lambda pitch: (
            -(motif_weights.get(pitch, 0.0) * 2 + scale_weights.get(pitch, 0.0)),
            float(pitch),
        ),
    )
    root_pattern = (0, 1, 0, 2, 1, 3, 4, 2)
    root_span = min(
        len(root_candidates),
        max(1, 1 + round(progression_contrast * (len(root_candidates) - 1))),
    )
    root = (
        min(root_candidates, key=lambda pitch: _pitch_class_distance(pitch, Fraction(1)))
        if cadence
        else root_candidates[root_pattern[bar_number % len(root_pattern)] % root_span]
    )
    modal_third_target = 386.31371 if tonal_mode == "major" else 315.64129
    consonant_targets = (
        0.0,
        modal_third_target,
        498.04,
        701.96,
        884.36 if tonal_mode == "major" else 813.69,
        968.83,
    )

    def tone_score(tone: Fraction) -> float:
        interval = (1200 * log2(float(tone / root))) % 1200
        consonance = 1 - min(abs(interval - target) for target in consonant_targets) / 300
        modal_third = max(
            0.0,
            1 - abs(interval - modal_third_target) / 180,
        )
        return (
            motif_weights.get(tone, 0.0) * 2.4
            + scale_weights.get(tone, 0.0) * 0.18
            + (
                1.2 * (1 - progression_contrast * 0.72)
                if tone in previous_classes
                else 0.0
            )
            + (0.7 if tone in fallback_classes else 0.0)
            + max(0.0, consonance)
            + modal_third * mode_strength * 1.8
        )

    voice_count = min(len(scale), 4 if energy >= 0.7 else 3)
    candidates = sorted(
        (tone for tone in scale if tone != root),
        key=lambda tone: (-tone_score(tone), float(tone)),
    )
    chord = [root, *candidates[: max(0, voice_count - 1)]]
    if previous is not None and set(chord) == previous_classes and len(candidates) >= voice_count:
        chord[-1] = candidates[voice_count - 1]
    chord = list(dict.fromkeys(chord))
    motif_classes = set(motif_weights)
    common = previous_classes & set(chord)
    third_error = min(
        (
            abs((1200 * log2(float(tone / root))) % 1200 - modal_third_target)
            for tone in chord
            if tone != root
        ),
        default=1200.0,
    )
    return tuple(chord), {
        "motif_tones": [ratio_text(tone) for tone in chord if tone in motif_classes],
        "common_tones": [ratio_text(tone) for tone in sorted(common, key=float)],
        "motif_tone_coverage": round(
            len(set(chord) & motif_classes) / max(1, len(set(chord))), 5
        ),
        "tonal_character": tonal_mode,
        "modal_third_target_cents": round(modal_third_target, 5),
        "modal_third_error_cents": round(third_error, 5),
        "degree": "motif-I" if cadence else f"motif-{bar_number % root_span + 1}",
    }


def _developed_notes(
    notes: list[dict[str, Any]],
    chord: tuple[Fraction, ...],
    repetition: int,
    amount: float,
    seed: int,
    allowed_scale: list[Fraction] | None = None,
) -> tuple[list[dict[str, Any]], list[str]]:
    """Create deterministic repetition-level development without changing harmony."""
    developed = [dict(note) for note in notes]
    operations: list[str] = []

    def constrain_to_scale(note: dict[str, Any]) -> bool:
        if not allowed_scale:
            return False
        changed = False
        ratio = Fraction(note["ratio"])
        snapped = _nearest_scale_pitch(ratio, allowed_scale)
        changed = snapped != ratio
        note["ratio"] = ratio_text(snapped)
        harmony_tones = []
        seen = {note["ratio"]}
        for value in note.get("harmony_tones", []):
            ratio = Fraction(value)
            snapped = _nearest_scale_pitch(ratio, allowed_scale)
            changed = changed or snapped != ratio
            text = ratio_text(snapped)
            if text not in seen:
                harmony_tones.append(text)
                seen.add(text)
        note["harmony_tones"] = harmony_tones
        return changed

    if repetition == 0 or amount <= 0:
        if allowed_scale:
            constrained = any([constrain_to_scale(note) for note in developed])
            if constrained:
                operations.append("motif_scale_constraint")
        return developed, operations
    random = Random(seed + repetition * 7919)
    if amount >= 0.18 and len(developed) > 2:
        shift = 1 + random.randrange(max(1, len(developed) - 1))
        developed = developed[shift:] + developed[:shift]
        operations.append("cyclic_rotation")
    if amount >= 0.38:
        factor = chord[repetition % len(chord)] / chord[0]
        for note in developed:
            note["ratio"] = ratio_text(Fraction(note["ratio"]) * factor)
            note["harmony_tones"] = [
                ratio_text(Fraction(value) * factor)
                for value in note.get("harmony_tones", [])
            ]
        operations.append("chord_tone_transposition")
    if amount >= 0.62 and repetition % 3 == 2:
        stacks = [
            (note["ratio"], list(note.get("harmony_tones", [])))
            for note in reversed(developed)
        ]
        for note, (ratio, harmony_tones) in zip(developed, stacks, strict=True):
            note["ratio"] = ratio
            note["harmony_tones"] = harmony_tones
        operations.append("retrograde_pitch")
    if amount >= 0.78:
        for note_index in range(1, len(developed), 3):
            developed[note_index]["ratio"] = ratio_text(
                chord[(note_index + repetition) % len(chord)]
            )
            developed[note_index]["harmony_tones"] = [
                ratio_text(chord[(note_index + repetition + voice + 1) % len(chord)])
                for voice in range(
                    len(developed[note_index].get("harmony_tones", []))
                )
            ]
        operations.append("selective_chord_projection")
    if allowed_scale:
        constrained = any([constrain_to_scale(note) for note in developed])
        if constrained:
            operations.append("motif_scale_constraint")
    swing = round((random.random() - 0.5) * amount * 0.24, 5)
    if abs(swing) >= 0.01:
        for note_index, note in enumerate(developed):
            if note_index % 2:
                note["onset_beat"] = max(0, float(note["onset_beat"]) + swing)
        operations.append("rhythmic_displacement")
    return developed, operations


def _phase_offset(config: dict[str, Any], bar_index: int) -> float:
    mode = str(config.get("phase_shift_mode", "off"))
    initial = float(config.get("phase_shift_beats", 0.5))
    increment = float(config.get("phase_shift_increment", 0.125))
    cycle = int(config.get("phase_shift_cycle_bars", 4))
    if mode == "static":
        return initial
    if mode == "progressive":
        return initial + bar_index * increment
    if mode == "polymetric":
        return initial + (bar_index % cycle) * increment
    return 0.0


def _motif_activity_schedule(
    sections: list[dict[str, Any]],
    activity: float,
    style: str,
    seed: int,
    phase_enabled: bool,
) -> list[dict[str, Any]]:
    """Create deterministic motif play/rest phrases with mandatory breathing."""
    patterns = {
        "breathing": ((True, True, False, True), (False, True, True, False)),
        "sparse": ((True, False, False, True), (False, True, False, False)),
        "driving": ((True, True, True, False), (True, False, True, True)),
    }
    lead_pattern, pulse_pattern = patterns[style]
    random = Random(seed + 44_221)
    schedule: list[dict[str, Any]] = []
    lead_run = 0
    pulse_run = 0
    for section_index, section in enumerate(sections):
        energy = float(section["energy"])
        probability = min(1.0, max(0.15, activity + (energy - 0.5) * 0.22))
        for local_bar in range(int(section["bars"])):
            bar = int(section["start_bar"]) + local_bar
            pattern_index = (bar - 1 + section_index) % len(lead_pattern)
            full_breath = bar % 8 == 0
            lead_active = (
                not full_breath
                and lead_run < 3
                and lead_pattern[pattern_index]
                and random.random() <= probability
            )
            if bar == 1:
                lead_active = True
            pulse_probability = min(1.0, probability + (0.08 if phase_enabled else -0.12))
            pulse_active = (
                not full_breath
                and pulse_run < 3
                and pulse_pattern[pattern_index]
                and random.random() <= pulse_probability
            )
            if phase_enabled and not full_breath and not lead_active and pulse_run < 3:
                pulse_active = True
            reason = (
                "full_breath"
                if full_breath
                else "lead_breath"
                if not lead_active
                else "pulse_breath"
                if not pulse_active
                else "interlock"
            )
            schedule.append({
                "section_index": section_index,
                "section_name": section["name"],
                "bar": bar,
                "lane_a_active": lead_active,
                "lane_b_active": pulse_active,
                "reason": reason,
            })
            lead_run = lead_run + 1 if lead_active else 0
            pulse_run = pulse_run + 1 if pulse_active else 0
    return schedule


def _max_active_run(schedule: list[dict[str, Any]], key: str) -> int:
    longest = current = 0
    for item in schedule:
        current = current + 1 if item[key] else 0
        longest = max(longest, current)
    return longest


def _motif_event(
    instrument_id: str,
    ratio: Fraction,
    start: float,
    duration: float,
    velocity: int,
    node: dict[str, Any],
    note_index: int | None = None,
    articulation: str = "motif",
    *,
    development_operations: list[str] | None = None,
    phase_lane: str | None = None,
    repetition: int = 0,
) -> dict[str, Any]:
    return {
        "instrument_id": instrument_id,
        "start_beat": round(start, 5),
        "duration_beats": round(max(0.0625, duration), 5),
        "velocity": velocity,
        "ratio": ratio_text(ratio),
        "articulation": articulation,
        "motif_id": node["id"],
        "formal_role": node["formal_role"],
        "source_note_index": note_index,
        "transformation_chain": node.get("transformation_chain", []),
        "identity_retention": node.get("identity_retention"),
        "target_chord": node["target_chord"],
        "source_motif_id": node.get("source_motif_id") or node["id"],
        "development_operations": development_operations or [],
        "phase_lane": phase_lane,
        "repetition": repetition,
    }


def generate_motif_vital_pack(config: dict[str, Any]) -> dict[str, Any]:
    """Turn selected Development Tree nodes into a full Vital Pack song plan.

    The ordinary Vital Pack generator remains the owner of form, profile metadata,
    automation, and export contracts.  This adapter replaces its harmonic and
    note-event layer with Tree-derived material so every melodic, bass, pulse,
    and drum decision has a stable motif provenance.
    """
    base = generate_vital_pack(config)
    nodes = list(config["nodes"])
    reference = float(config.get("reference_frequency_hz", 440))
    mode = str(config["preset_mode"])
    harmony: list[dict[str, Any]] = []
    events: list[dict[str, Any]] = []
    assignments: list[dict[str, Any]] = []
    phase_schedule: list[dict[str, Any]] = []
    development_amount = float(config.get("development_amount", 0.55))
    motif_activity = float(config.get("motif_activity", 0.68))
    motif_rest_style = str(config.get("motif_rest_style", "breathing"))
    tonal_character = str(config.get("tonal_character", "mixed"))
    mode_strength = float(config.get("mode_strength", 0.75))
    progression_contrast = float(config.get("progression_contrast", 0.55))
    piano_run_enabled = bool(config.get("piano_run_enabled", True))
    piano_part_mode = str(config.get("piano_part_mode", "scale_run"))
    piano_run_activity = float(config.get("piano_run_activity", 0.5))
    piano_run_density = float(config.get("piano_run_density", 0.65))
    harmony_random = Random(int(config["seed"]) + 81_019)
    piano_random = Random(int(config["seed"]) + 63_017)
    phase_mode = str(config.get("phase_shift_mode", "off"))
    activity_schedule = _motif_activity_schedule(
        base["sections"],
        motif_activity,
        motif_rest_style,
        int(config["seed"]),
        phase_mode != "off",
    )
    activity_by_bar = {int(item["bar"]): item for item in activity_schedule}
    motif_scale, scale_weights = _motif_scale(
        nodes, list(config["anchor_chord"])
    )
    previous_chord: tuple[Fraction, ...] | None = None

    for section_index, section in enumerate(base["sections"]):
        template = str(section.get("template_name", section["name"]))
        desired_role = MOTIF_ROLE_BY_TEMPLATE[template]
        section_nodes = _motif_nodes_for_section(nodes, desired_role, section_index)
        primary = section_nodes[0]
        fallback_chord = tuple(Fraction(value) for value in primary["target_chord"])
        start = (int(section["start_bar"]) - 1) * 4
        end = start + int(section["bars"]) * 4
        energy = float(section["energy"])
        section_mode = str(section.get("tonal_character", "major"))
        active = _active(template, mode)
        if "PI04" not in active:
            active.append("PI04")
        if phase_mode != "off" and "PI07" not in active:
            active.append("PI07")
        if piano_run_enabled and PIANO_ID not in active:
            active.append(PIANO_ID)
        section["active_instruments"] = active
        section["motif_node_id"] = primary["id"]
        section["motif_formal_role"] = primary["formal_role"]
        assignment = {
            "section_index": section_index,
            "section_name": section["name"],
            "motif_id": primary["id"],
            "motif_ids": [node["id"] for node in section_nodes],
            "source_motif_ids": sorted({
                str(node.get("source_motif_id") or node["id"])
                for node in section_nodes
            }),
            "formal_role": primary["formal_role"],
            "initial_target_chord": primary["target_chord"],
            "generated_chords": [],
        }
        assignments.append(assignment)

        for bar_start in range(start, end, 4):
            bar_index = (bar_start - start) // 4
            bar_activity = activity_by_bar[bar_start // 4 + 1]
            actual_mode = _mode_for_bar(
                tonal_character,
                section_mode,
                mode_strength,
                harmony_random,
            )
            selection_index = int(bar_index * development_amount) % len(section_nodes)
            node = dict(section_nodes[selection_index])
            source_notes = list(node["notes"])
            provisional_notes, _provisional_operations = _developed_notes(
                source_notes,
                previous_chord or fallback_chord,
                bar_index,
                development_amount,
                int(config["seed"]) + section_index * 101,
                motif_scale,
            )
            chord, harmony_analysis = _motif_harmony_chord(
                motif_scale,
                scale_weights,
                provisional_notes,
                fallback_chord,
                previous_chord,
                bar_start // 4,
                energy,
                actual_mode,
                mode_strength,
                progression_contrast,
                cadence=bar_start + 4 >= int(base["metadata"]["length_bars"]) * 4,
            )
            node["target_chord"] = [ratio_text(tone) for tone in chord]
            developed_notes, operations = _developed_notes(
                source_notes,
                chord,
                bar_index,
                development_amount,
                int(config["seed"]) + section_index * 101,
                motif_scale,
            )
            phrase_beats = max(
                float(note["onset_beat"]) + float(note["duration_beats"])
                for note in developed_notes
            )
            harmony.append({
                "start_beat": bar_start,
                "duration_beats": 4,
                "functional_state": f"motif:{node['formal_role']}",
                "root_ratio": ratio_text(chord[0]),
                "tones": [ratio_text(tone) for tone in chord],
                "tension": round(min(1, 0.18 + energy * 0.72), 3),
                "motif_id": node["id"],
                "formal_role": node["formal_role"],
                "section_tonal_target": section_mode,
                **harmony_analysis,
            })
            assignment["generated_chords"].append([ratio_text(tone) for tone in chord])
            previous_chord = chord

            for instrument_id in active:
                if instrument_id in {"PI01", "PI02", "PI03", "PI08"}:
                    octave = Fraction(2) if instrument_id in {"PI01", "PI02"} else Fraction(1)
                    for voice, tone in enumerate(chord):
                        events.append(_motif_event(
                            instrument_id, tone * octave, bar_start, 3.72,
                            round(48 + energy * 48), node, voice, "sustain",
                            development_operations=operations,
                            repetition=bar_index,
                        ))
                elif instrument_id == "PI05":
                    events.append(_motif_event(
                        instrument_id, chord[0] / 2, bar_start, 3.55,
                        round(63 + energy * 36), node, 0, "bass_root",
                        development_operations=operations,
                        repetition=bar_index,
                    ))
                elif instrument_id == PIANO_ID:
                    full_breath = (
                        not bar_activity["lane_a_active"]
                        and not bar_activity["lane_b_active"]
                    )
                    if piano_part_mode == "motif":
                        probability = min(
                            0.94,
                            piano_run_activity * (0.62 + energy * 0.48),
                        )
                        piano_enters = (
                            not full_breath and piano_random.random() <= probability
                        )
                        phrase_start = float(bar_start)
                        phrase_index = 0
                        phrase_limit = 1 + round(piano_run_density * 2)
                        while (
                            piano_enters
                            and phrase_start < bar_start + 4
                            and phrase_index < phrase_limit
                        ):
                            piano_notes, piano_operations = _developed_notes(
                                developed_notes,
                                chord,
                                bar_index + phrase_index,
                                development_amount,
                                int(config["seed"]) + section_index * 419,
                                motif_scale,
                            )
                            combined_operations = list(
                                dict.fromkeys(operations + piano_operations)
                            )
                            for note_index, note in enumerate(piano_notes):
                                onset = phrase_start + float(note["onset_beat"])
                                if onset >= bar_start + 4:
                                    continue
                                duration = min(
                                    float(note["duration_beats"]),
                                    bar_start + 4 - onset,
                                )
                                for stack_voice, ratio in enumerate(
                                    [note["ratio"], *note.get("harmony_tones", [])]
                                ):
                                    event = _motif_event(
                                        PIANO_ID,
                                        Fraction(ratio),
                                        onset,
                                        duration,
                                        max(
                                            1,
                                            int(note["velocity"])
                                            + 4
                                            - stack_voice * 8,
                                        ),
                                        node,
                                        note_index,
                                        "piano_motif",
                                        development_operations=combined_operations,
                                        repetition=bar_index + phrase_index,
                                    )
                                    event["stack_voice"] = stack_voice
                                    event["piano_material"] = "motif"
                                    events.append(event)
                            phrase_start += phrase_beats
                            phrase_index += 1
                    else:
                        run = (
                            []
                            if full_breath
                            else _piano_scale_run(
                                motif_scale,
                                chord,
                                bar_start,
                                energy,
                                piano_run_activity,
                                piano_run_density,
                                piano_random,
                                cadence=bar_start + 4
                                >= int(base["metadata"]["length_bars"]) * 4,
                            )
                        )
                        for note_index, note in enumerate(run):
                            event = _motif_event(
                                PIANO_ID,
                                note["ratio"],
                                note["start_beat"],
                                note["duration_beats"],
                                note["velocity"],
                                node,
                                note_index,
                                "piano_scale_run",
                                development_operations=operations,
                                repetition=bar_index,
                            )
                            event["run_contour"] = note["contour"]
                            event["piano_material"] = "scale_run"
                            events.append(event)
                elif instrument_id == "PI04" and bar_activity["lane_a_active"]:
                    phrase_start = float(bar_start)
                    phrase_index = 0
                    phrase_limit = (
                        1
                        if motif_rest_style == "sparse"
                        else 3
                        if motif_rest_style == "driving" and energy >= 0.7
                        else 2
                    )
                    while phrase_start < bar_start + 4 and phrase_index < phrase_limit:
                        phrase_notes, phrase_operations = _developed_notes(
                            developed_notes,
                            chord,
                            bar_index + phrase_index,
                            development_amount,
                            int(config["seed"]) + section_index * 211,
                            motif_scale,
                        )
                        combined_operations = list(dict.fromkeys(operations + phrase_operations))
                        for note_index, note in enumerate(phrase_notes):
                            onset = phrase_start + float(note["onset_beat"])
                            if onset >= bar_start + 4:
                                continue
                            duration = min(float(note["duration_beats"]), bar_start + 4 - onset)
                            for stack_voice, ratio in enumerate(
                                [note["ratio"], *note.get("harmony_tones", [])]
                            ):
                                event = _motif_event(
                                    instrument_id,
                                    Fraction(ratio) * 2,
                                    onset,
                                    duration,
                                    min(
                                        127,
                                        int(note["velocity"]) + 8 - stack_voice * 9,
                                    ),
                                    node,
                                    note_index,
                                    (
                                        "lead_motif"
                                        if stack_voice == 0
                                        else "lead_motif_harmony"
                                    ),
                                    development_operations=combined_operations,
                                    phase_lane="a" if phase_mode != "off" else None,
                                    repetition=bar_index + phrase_index,
                                )
                                event["stack_voice"] = stack_voice
                                events.append(event)
                        phrase_start += phrase_beats
                        phrase_index += 1
                elif instrument_id == "PI06" and (bar_start - start) % 8 == 0:
                    terminal = developed_notes[-1]
                    events.append(_motif_event(
                        instrument_id, Fraction(terminal["ratio"]) * 4, bar_start + 3.5, 0.4,
                        round(65 + energy * 45), node, len(developed_notes) - 1, "terminal_accent",
                        development_operations=operations,
                        repetition=bar_index,
                    ))
                elif instrument_id == "PI07" and bar_activity["lane_b_active"]:
                    secondary = section_nodes[(selection_index + 1) % len(section_nodes)]
                    phase_node = {
                        **secondary,
                        "target_chord": [ratio_text(tone) for tone in chord],
                    }
                    phase_notes, phase_operations = _developed_notes(
                        list(secondary["notes"]),
                        chord,
                        bar_index + 1,
                        development_amount,
                        int(config["seed"]) + section_index * 307,
                        motif_scale,
                    )
                    offset = _phase_offset(config, bar_index)
                    time_scale = 15 / 16 if phase_mode == "polymetric" else 1.0
                    if phase_mode != "off":
                        phase_schedule.append({
                            "section_index": section_index,
                            "bar": bar_start // 4 + 1,
                            "mode": phase_mode,
                            "offset_beats": round(offset, 5),
                            "time_scale": time_scale,
                            "lane_a_motif_id": node["id"],
                            "lane_b_motif_id": phase_node["id"],
                        })
                    for note_index, note in enumerate(phase_notes):
                        local_onset = float(note["onset_beat"]) * time_scale
                        onset = bar_start + (
                            (local_onset + offset) % 4 if phase_mode != "off" else local_onset
                        )
                        if onset >= bar_start + 4:
                            continue
                        for stack_voice, ratio in enumerate(
                            [note["ratio"], *note.get("harmony_tones", [])]
                        ):
                            event = _motif_event(
                                instrument_id,
                                Fraction(ratio) * 2,
                                onset,
                                min(0.38, float(note["duration_beats"])),
                                max(1, round(52 + energy * 52) - stack_voice * 8),
                                phase_node,
                                note_index,
                                (
                                    "phase_motif"
                                    if phase_mode != "off"
                                    else "motif_pulse"
                                ),
                                development_operations=phase_operations,
                                phase_lane="b" if phase_mode != "off" else None,
                                repetition=bar_index,
                            )
                            event["stack_voice"] = stack_voice
                            events.append(event)
                elif instrument_id == "DRUMS":
                    hits: list[tuple[str, int, float, int]] = [
                        ("kick", 36, float(bar_start), round(70 + energy * 42)),
                        ("snare", 38, float(bar_start + 2), round(66 + energy * 45)),
                    ]
                    if bar_activity["lane_a_active"]:
                        for note_index, note in enumerate(developed_notes):
                            onset = bar_start + float(note["onset_beat"])
                            if onset >= bar_start + 4:
                                continue
                            hits.append(("hat", 42, onset, round(48 + energy * 48)))
                            if bool(note.get("accent")) and onset > bar_start + 0.25:
                                hits.append(("perc", 39, onset, round(54 + energy * 44)))
                    for layer, midi_note, onset, velocity in hits:
                        events.append({
                            "instrument_id": DRUM_ID_BY_LAYER[layer],
                            "layer": layer,
                            "note": midi_note,
                            "start_beat": round(onset, 5),
                            "duration_beats": 0.12,
                            "velocity": velocity,
                            "motif_id": node["id"],
                            "source_motif_id": node.get("source_motif_id") or node["id"],
                            "formal_role": node["formal_role"],
                            "target_chord": node["target_chord"],
                        })

    events.sort(key=lambda event: (float(event["start_beat"]), str(event["instrument_id"])))
    policy_by_instrument = {profile[0]: profile[5] for profile in PROFILES}
    tuning = [
        {
            "time": event["start_beat"],
            "instrument_id": event["instrument_id"],
            "ratio": event["ratio"],
            "policy": policy_by_instrument[event["instrument_id"]],
            "cents_offset": 0,
            "motif_id": event["motif_id"],
        }
        for event in events
        if event.get("ratio") and event["instrument_id"] in policy_by_instrument
    ]
    mts_timeline = [
        {**event, "frequency_hz": round(reference * float(Fraction(event["ratio"])), 6), "mode": "note_retune"}
        for event in tuning
    ]
    sidechain = [
        {"start_beat": event["start_beat"], "duration_beats": 0.5, "target_gain": 0.58, "curve": "exponential"}
        for event in events
        if event.get("layer") == "kick"
    ]
    active_wide = [
        sum(
            1
            for instrument in section["active_instruments"]
            if next((profile[6] for profile in PROFILES if profile[0] == instrument), False)
        )
        for section in base["sections"]
    ]
    retention = [float(node["identity_retention"]) for node in nodes if node.get("identity_retention") is not None]
    lane_a_onsets = {event["start_beat"] for event in events if event.get("phase_lane") == "a"}
    lane_b_onsets = {event["start_beat"] for event in events if event.get("phase_lane") == "b"}
    phase_union = lane_a_onsets | lane_b_onsets
    phase_overlap = len(lane_a_onsets & lane_b_onsets) / max(1, len(phase_union))
    development_operations = {
        operation
        for event in events
        for operation in event.get("development_operations", [])
    }
    source_motifs = {
        str(node.get("source_motif_id") or node["id"])
        for node in nodes
    }
    transferred_polyphony_max = max(
        (
            1 + len(note.get("harmony_tones", []))
            for node in nodes
            for note in node["notes"]
        ),
        default=1,
    )
    scale_set = set(motif_scale)
    harmony_tones = {
        reduce_to_octave(Fraction(tone))
        for chord_event in harmony
        for tone in chord_event["tones"]
    }
    event_tones = {
        reduce_to_octave(Fraction(event["ratio"]))
        for event in events
        if event.get("ratio")
    }
    piano_events = [
        event for event in events if event["instrument_id"] == PIANO_ID
    ]
    piano_motif_events = [
        event
        for event in piano_events
        if event["articulation"] == "piano_motif"
    ]
    piano_scale_run_events = [
        event
        for event in piano_events
        if event["articulation"] == "piano_scale_run"
    ]
    unique_chords = {
        tuple(chord_event["tones"])
        for chord_event in harmony
    }
    average_motif_chord_coverage = sum(
        float(chord_event["motif_tone_coverage"])
        for chord_event in harmony
    ) / max(1, len(harmony))
    motif_major_bars = sum(
        item["tonal_character"] == "major" for item in harmony
    )
    motif_minor_bars = sum(
        item["tonal_character"] == "minor" for item in harmony
    )
    motif_target_bars = sum(
        item["tonal_character"] == item["section_tonal_target"]
        for item in harmony
    )
    motif_root_changes = sum(
        left["root_ratio"] != right["root_ratio"]
        for left, right in zip(harmony, harmony[1:])
    )
    modal_third_error_mean = sum(
        float(item["modal_third_error_cents"]) for item in harmony
    ) / max(1, len(harmony))
    lead_active_bars = sum(bool(item["lane_a_active"]) for item in activity_schedule)
    pulse_active_bars = sum(bool(item["lane_b_active"]) for item in activity_schedule)
    full_rest_bars = sum(
        not item["lane_a_active"] and not item["lane_b_active"]
        for item in activity_schedule
    )
    lead_max_run = _max_active_run(activity_schedule, "lane_a_active")
    pulse_max_run = _max_active_run(activity_schedule, "lane_b_active")
    quality = dict(base["quality"])
    quality.update({
        "wide_sustained_max": max(active_wide, default=0),
        "wide_sustained_ok": max(active_wide, default=0) <= 2,
        "bass_mono_ok": True,
        "motif_section_coverage": len(assignments),
        "motif_identity_retention_mean": round(sum(retention) / len(retention), 5) if retention else 1.0,
        "motif_provenance_ok": all(event.get("motif_id") for event in events),
        "source_motif_count": len(source_motifs),
        "motif_polyphony_max": transferred_polyphony_max,
        "development_operation_count": len(development_operations),
        "phase_overlap_ratio": round(phase_overlap, 5),
        "phase_distinct_ok": phase_mode == "off" or phase_overlap < 0.75,
        "motif_scale_size": len(motif_scale),
        "motif_scale_harmony_coverage": round(
            len(harmony_tones & scale_set) / max(1, len(scale_set)), 5
        ),
        "motif_scale_event_conformance": round(
            len(event_tones & scale_set) / max(1, len(event_tones)), 5
        ),
        "motif_chord_tone_coverage_mean": round(
            average_motif_chord_coverage, 5
        ),
        "harmony_unique_chords": len(unique_chords),
        "harmony_variety_ok": len(unique_chords) >= min(3, len(harmony)),
        "harmony_root_changes": motif_root_changes,
        "harmony_major_ratio": round(
            motif_major_bars / max(1, len(harmony)), 5
        ),
        "harmony_minor_ratio": round(
            motif_minor_bars / max(1, len(harmony)), 5
        ),
        "harmony_mode_clarity": round(
            motif_target_bars / max(1, len(harmony)), 5
        ),
        "harmony_modal_third_error_mean_cents": round(
            modal_third_error_mean, 5
        ),
        "harmony_variety_score": round(
            min(1.0, len(unique_chords) / 8) * 0.55
            + motif_root_changes / max(1, len(harmony) - 1) * 0.45,
            5,
        ),
        "motif_lead_active_ratio": round(
            lead_active_bars / max(1, len(activity_schedule)), 5
        ),
        "motif_pulse_active_ratio": round(
            pulse_active_bars / max(1, len(activity_schedule)), 5
        ),
        "motif_full_rest_bars": full_rest_bars,
        "motif_lead_max_consecutive_bars": lead_max_run,
        "motif_pulse_max_consecutive_bars": pulse_max_run,
        "motif_breathing_ok": full_rest_bars > 0 and lead_max_run <= 3,
        "piano_run_notes": len(piano_events),
        "piano_motif_notes": len(piano_motif_events),
        "piano_scale_run_notes": len(piano_scale_run_events),
        "piano_run_active_bars": len({
            int(float(event["start_beat"]) // 4) for event in piano_events
        }),
        "piano_run_scale_conformance": round(
            sum(
                reduce_to_octave(Fraction(event["ratio"])) in scale_set
                for event in piano_events
            )
            / max(1, len(piano_events)),
            5,
        ),
    })
    base["metadata"] = {
        **base["metadata"],
        "title": "Motif Vital Pack Study",
        "composition_source": "motif-development-tree",
        "anchor_chord": list(config["anchor_chord"]),
        "prime_basis": list(config.get("prime_basis", [3, 5, 7])),
        "development_amount": development_amount,
        "motif_activity": motif_activity,
        "motif_rest_style": motif_rest_style,
        "phase_shift_mode": phase_mode,
        "tonal_character": tonal_character,
        "mode_strength": mode_strength,
        "progression_contrast": progression_contrast,
        "piano_run_enabled": piano_run_enabled,
        "piano_part_mode": piano_part_mode,
        "piano_run_activity": piano_run_activity,
        "piano_run_density": piano_run_density,
    }
    base["harmony"] = harmony
    base["events"] = events
    base["tuning_timeline"] = tuning
    base["mts_timeline"] = mts_timeline
    base["sidechain_envelope"] = sidechain
    base["quality"] = quality
    base["base_scale"] = {
        "name": "Motif-derived octave scale",
        "ratios": [ratio_text(tone) for tone in motif_scale],
        "source": "selected-motif-development-nodes",
    }
    base["motif_arrangement"] = {
        "section_assignments": assignments,
        "nodes": nodes,
        "development_amount": development_amount,
        "prime_basis": list(config.get("prime_basis", [3, 5, 7])),
        "development_operations": sorted(development_operations),
        "activity": {
            "target": motif_activity,
            "style": motif_rest_style,
            "lead_active_ratio": round(
                lead_active_bars / max(1, len(activity_schedule)), 5
            ),
            "pulse_active_ratio": round(
                pulse_active_bars / max(1, len(activity_schedule)), 5
            ),
            "full_rest_bars": full_rest_bars,
            "schedule": activity_schedule,
        },
        "motif_scale": {
            "ratios": [ratio_text(tone) for tone in motif_scale],
            "weights": {
                ratio_text(tone): round(scale_weights.get(tone, 0.0), 5)
                for tone in motif_scale
            },
        },
        "phase_shift": {
            "mode": phase_mode,
            "schedule": phase_schedule,
            "overlap_ratio": round(phase_overlap, 5),
        },
    }
    return base
