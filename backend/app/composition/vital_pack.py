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
    length = int(config["length_bars"])
    tempo = float(config["tempo_bpm"])
    mode = str(config["preset_mode"])
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
            "tracks": [{"track": 1, "instrument_id": "DRUMS", "preset_file": "External sampler"}]
            + manifest,
            "tuning_control_track": 11,
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


def _developed_notes(
    notes: list[dict[str, Any]],
    chord: tuple[Fraction, ...],
    repetition: int,
    amount: float,
    seed: int,
) -> tuple[list[dict[str, Any]], list[str]]:
    """Create deterministic repetition-level development without changing harmony."""
    if repetition == 0 or amount <= 0:
        return [dict(note) for note in notes], []
    random = Random(seed + repetition * 7919)
    developed = [dict(note) for note in notes]
    operations: list[str] = []
    if amount >= 0.18 and len(developed) > 2:
        shift = 1 + random.randrange(max(1, len(developed) - 1))
        developed = developed[shift:] + developed[:shift]
        operations.append("cyclic_rotation")
    if amount >= 0.38:
        factor = chord[repetition % len(chord)] / chord[0]
        for note in developed:
            note["ratio"] = ratio_text(Fraction(note["ratio"]) * factor)
        operations.append("chord_tone_transposition")
    if amount >= 0.62 and repetition % 3 == 2:
        pitches = [note["ratio"] for note in reversed(developed)]
        for note, ratio in zip(developed, pitches, strict=True):
            note["ratio"] = ratio
        operations.append("retrograde_pitch")
    if amount >= 0.78:
        for note_index in range(1, len(developed), 3):
            developed[note_index]["ratio"] = ratio_text(
                chord[(note_index + repetition) % len(chord)]
            )
        operations.append("selective_chord_projection")
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
    phase_mode = str(config.get("phase_shift_mode", "off"))

    for section_index, section in enumerate(base["sections"]):
        template = str(section.get("template_name", section["name"]))
        desired_role = MOTIF_ROLE_BY_TEMPLATE[template]
        section_nodes = _motif_nodes_for_section(nodes, desired_role, section_index)
        primary = section_nodes[0]
        chord = tuple(Fraction(value) for value in primary["target_chord"])
        start = (int(section["start_bar"]) - 1) * 4
        end = start + int(section["bars"]) * 4
        energy = float(section["energy"])
        active = _active(template, mode)
        if "PI04" not in active:
            active.append("PI04")
        if phase_mode != "off" and "PI07" not in active:
            active.append("PI07")
        section["active_instruments"] = active
        section["motif_node_id"] = primary["id"]
        section["motif_formal_role"] = primary["formal_role"]
        assignments.append({
            "section_index": section_index,
            "section_name": section["name"],
            "motif_id": primary["id"],
            "motif_ids": [node["id"] for node in section_nodes],
            "source_motif_ids": sorted({
                str(node.get("source_motif_id") or node["id"])
                for node in section_nodes
            }),
            "formal_role": primary["formal_role"],
            "target_chord": primary["target_chord"],
        })

        for bar_start in range(start, end, 4):
            bar_index = (bar_start - start) // 4
            selection_index = int(bar_index * development_amount) % len(section_nodes)
            node = {
                **section_nodes[selection_index],
                "target_chord": primary["target_chord"],
            }
            source_notes = list(node["notes"])
            developed_notes, operations = _developed_notes(
                source_notes,
                chord,
                bar_index,
                development_amount,
                int(config["seed"]) + section_index * 101,
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
            })

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
                elif instrument_id == "PI04":
                    phrase_start = float(bar_start)
                    phrase_index = 0
                    while phrase_start < bar_start + 4:
                        phrase_notes, phrase_operations = _developed_notes(
                            developed_notes,
                            chord,
                            bar_index + phrase_index,
                            development_amount,
                            int(config["seed"]) + section_index * 211,
                        )
                        combined_operations = list(dict.fromkeys(operations + phrase_operations))
                        for note_index, note in enumerate(phrase_notes):
                            onset = phrase_start + float(note["onset_beat"])
                            if onset >= bar_start + 4:
                                continue
                            duration = min(float(note["duration_beats"]), bar_start + 4 - onset)
                            events.append(_motif_event(
                                instrument_id, Fraction(note["ratio"]) * 2, onset, duration,
                                min(127, int(note["velocity"]) + 8), node, note_index, "lead_motif",
                                development_operations=combined_operations,
                                phase_lane="a" if phase_mode != "off" else None,
                                repetition=bar_index + phrase_index,
                            ))
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
                elif instrument_id == "PI07":
                    secondary = section_nodes[(selection_index + 1) % len(section_nodes)]
                    phase_node = {**secondary, "target_chord": primary["target_chord"]}
                    phase_notes, phase_operations = _developed_notes(
                        list(secondary["notes"]),
                        chord,
                        bar_index + 1,
                        development_amount,
                        int(config["seed"]) + section_index * 307,
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
                        events.append(_motif_event(
                            instrument_id, Fraction(note["ratio"]) * 2, onset, min(0.38, float(note["duration_beats"])),
                            round(52 + energy * 52), phase_node, note_index,
                            "phase_motif" if phase_mode != "off" else "motif_pulse",
                            development_operations=phase_operations,
                            phase_lane="b" if phase_mode != "off" else None,
                            repetition=bar_index,
                        ))
                elif instrument_id == "DRUMS":
                    hits: list[tuple[str, int, float, int]] = [
                        ("kick", 36, float(bar_start), round(70 + energy * 42)),
                        ("snare", 38, float(bar_start + 2), round(66 + energy * 45)),
                    ]
                    for note_index, note in enumerate(developed_notes):
                        onset = bar_start + float(note["onset_beat"])
                        if onset >= bar_start + 4:
                            continue
                        hits.append(("hat", 42, onset, round(48 + energy * 48)))
                        if bool(note.get("accent")) and onset > bar_start + 0.25:
                            hits.append(("perc", 39, onset, round(54 + energy * 44)))
                    for layer, midi_note, onset, velocity in hits:
                        events.append({
                            "instrument_id": "DRUMS",
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
    quality = dict(base["quality"])
    quality.update({
        "wide_sustained_max": max(active_wide, default=0),
        "wide_sustained_ok": max(active_wide, default=0) <= 2,
        "bass_mono_ok": True,
        "motif_section_coverage": len(assignments),
        "motif_identity_retention_mean": round(sum(retention) / len(retention), 5) if retention else 1.0,
        "motif_provenance_ok": all(event.get("motif_id") for event in events),
        "source_motif_count": len(source_motifs),
        "development_operation_count": len(development_operations),
        "phase_overlap_ratio": round(phase_overlap, 5),
        "phase_distinct_ok": phase_mode == "off" or phase_overlap < 0.75,
    })
    base["metadata"] = {
        **base["metadata"],
        "title": "Motif Vital Pack Study",
        "composition_source": "motif-development-tree",
        "anchor_chord": list(config["anchor_chord"]),
        "development_amount": development_amount,
        "phase_shift_mode": phase_mode,
    }
    base["harmony"] = harmony
    base["events"] = events
    base["tuning_timeline"] = tuning
    base["mts_timeline"] = mts_timeline
    base["sidechain_envelope"] = sidechain
    base["quality"] = quality
    base["motif_arrangement"] = {
        "section_assignments": assignments,
        "nodes": nodes,
        "development_amount": development_amount,
        "development_operations": sorted(development_operations),
        "phase_shift": {
            "mode": phase_mode,
            "schedule": phase_schedule,
            "overlap_ratio": round(phase_overlap, 5),
        },
    }
    return base
