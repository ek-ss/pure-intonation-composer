"""Deterministic T/S/D minimal-music composition generator."""

from __future__ import annotations

from fractions import Fraction
from random import Random
from typing import Any, TypedDict

from app.rhythm.engine import euclidean_rhythm
from app.tuning.ratios import ratio_text


FUNCTION_TENSION = {"T": 0.18, "S": 0.46, "D": 0.78}
SECTION_ORDER = ("introduction", "accumulation", "development", "climax", "resolution", "coda")


class Tone(TypedDict):
    ratio: str
    role: str


class FunctionalChord(TypedDict):
    bar: int
    duration_bars: int
    section: str
    function: str
    id: str
    tones: list[Tone]


class VoiceSpec(TypedDict):
    id: str
    role: str
    cycle_length_steps: int
    phase_offset_steps: int


class BarAnalysis(TypedDict):
    bar: int
    section: str
    density: float
    tension: float
    phase_dispersion: float
    stability: float


def _section(position: float, climax_start: float, resolution_start: float) -> str:
    if position < 0.15:
        return "introduction"
    if position < 0.40:
        return "accumulation"
    if position < climax_start:
        return "development"
    if position < resolution_start:
        return "climax"
    if position < 0.92:
        return "resolution"
    return "coda"


def _function_for(section: str, previous: str, random: Random) -> str:
    weights = {
        "introduction": {"T": 0.88, "S": 0.09, "D": 0.03},
        "accumulation": {"T": 0.56, "S": 0.27, "D": 0.17},
        "development": {"T": 0.28, "S": 0.34, "D": 0.38},
        "climax": {"T": 0.16, "S": 0.24, "D": 0.60},
        "resolution": {"T": 0.72 if previous == "D" else 0.58, "S": 0.08, "D": 0.20},
        "coda": {"T": 0.97, "S": 0.02, "D": 0.01},
    }[section]
    choices, values = zip(*weights.items())
    return random.choices(choices, weights=values, k=1)[0]


def _chord(function: str, tuning: str) -> list[tuple[Fraction, str]]:
    if tuning == "12-tet":
        semitones = {"T": (0, 4, 7), "S": (5, 9, 12), "D": (7, 11, 14)}[function]
        roles = ("root", "third", "fifth")
        return [
            (Fraction(2 ** (semitone / 12)).limit_denominator(1_000_000), role)
            for semitone, role in zip(semitones, roles, strict=True)
        ]
    base = {
        "T": [(Fraction(1), "root"), (Fraction(5, 4), "third"), (Fraction(3, 2), "fifth")],
        "S": [(Fraction(4, 3), "root"), (Fraction(5, 3), "third"), (Fraction(2), "fifth")],
        "D": [(Fraction(3, 2), "root"), (Fraction(15, 8), "third"), (Fraction(9, 4), "fifth")],
    }[function]
    if tuning == "7-limit":
        colour = {"T": Fraction(7, 4), "S": Fraction(7, 3), "D": Fraction(7, 4)}[function]
        base.append((colour, "colour"))
    return base


def _imported_chords(config: dict[str, Any]) -> dict[str, list[tuple[Fraction, str]]]:
    imported: dict[str, list[tuple[Fraction, str]]] = {}
    for chord in config.get("prime_progression", []):
        if not isinstance(chord, dict) or not isinstance(chord.get("id"), str):
            continue
        tones: list[tuple[Fraction, str]] = []
        for tone in chord.get("tones", []):
            if not isinstance(tone, dict):
                continue
            representative = tone.get("representative", {})
            ratio = representative.get("normalized_ratio") if isinstance(representative, dict) else None
            if isinstance(ratio, str):
                try:
                    tones.append((Fraction(ratio), "prime_tone"))
                except (ValueError, ZeroDivisionError):
                    continue
        if len(tones) >= 2:
            imported[chord["id"]] = tones
    return imported


def _drum_events(bars: int, density: float, analysis: list[BarAnalysis]) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    definitions = (("kick", 36, 16, 3), ("snare", 38, 16, 2), ("hat", 42, 16, 7), ("perc", 39, 12, 3))
    events: list[dict[str, object]] = []
    layers: list[dict[str, object]] = []
    for name, note, steps, base_pulses in definitions:
        layers.append({"id": name, "note": note, "steps": steps})
        for bar in range(bars):
            form_density = analysis[bar]["density"]
            pulses = max(1, min(steps, round(base_pulses * (.35 + density) * (.55 + form_density))))
            phase = 0 if name == "kick" else (bar // 4 + note) % steps
            pattern = euclidean_rhythm(steps, pulses, phase)
            for step, active in enumerate(pattern):
                if active:
                    events.append({"layer": name, "note": note, "start_beat": bar * 4 + step / 4, "velocity": min(120, 58 + round(35 * density) + (16 if step % 4 == 0 else 0))})
    return layers, events


def _density(section: str, progress: float) -> float:
    start_end = {
        "introduction": (0.08, 0.20), "accumulation": (0.22, 0.42),
        "development": (0.42, 0.62), "climax": (0.70, 0.82),
        "resolution": (0.48, 0.20), "coda": (0.16, 0.06),
    }[section]
    return start_end[0] + (start_end[1] - start_end[0]) * progress


def _voice_time_delta(voice_index: int, bar: int, density: float, section: str) -> float:
    """Return a deterministic density-sensitive offset for one voice in one bar."""
    convergence = .34 if section in {"resolution", "coda"} else 1.0
    spread = (.018 + density * .085) * convergence
    direction = -1 if (voice_index + bar) % 2 else 1
    contour = ((bar * (voice_index + 2)) % 5 - 2) * density * .006
    return round(direction * spread * (1 + voice_index % 3 / 3) + contour, 5)


def generate_minimal_functional(config: dict[str, Any]) -> dict[str, object]:
    bars = int(config["duration_bars"])
    beats = int(config["beats_per_bar"])
    subdivisions = int(config["subdivisions_per_beat"])
    voices = int(config["voice_count"])
    seed = int(config["seed"])
    tempo = float(config["tempo_bpm"])
    tuning = str(config["tuning"])
    climax_start = float(config["climax_start"])
    resolution_start = float(config["resolution_start"])
    imported_chords = _imported_chords(config)
    assignments = {
        str(role): [str(item) for item in chord_ids] if isinstance(chord_ids, list) else [str(chord_ids)]
        for role, chord_ids in config.get("function_chord_ids", {}).items()
    }
    random = Random(seed)
    steps_per_bar = beats * subdivisions
    chord_bars = 2
    function_plan: list[FunctionalChord] = []
    prior = "T"
    for start_bar in range(0, bars, chord_bars):
        section = _section((start_bar / bars), climax_start, resolution_start)
        function = _function_for(section, prior, random)
        if section == "resolution" and start_bar >= int(resolution_start * bars):
            function = "T" if prior == "D" or random.random() < 0.65 else function
        if section == "coda":
            function = "T"
        assigned_ids = assignments.get(function, [])
        assigned_id = random.choice(assigned_ids) if assigned_ids else ""
        tones = imported_chords.get(assigned_id, _chord(function, tuning))
        function_plan.append({
            "bar": start_bar, "duration_bars": min(chord_bars, bars - start_bar), "section": section,
            "function": function, "id": assigned_id or f"{function}{start_bar // chord_bars}",
            "tones": [{"ratio": ratio_text(ratio), "role": role} for ratio, role in tones],
        })
        prior = function

    voice_specs: list[VoiceSpec] = []
    for index in range(voices):
        cycle = 8 + (index % 4) * 2
        role = ("bass", "root_pulse", "inner", "upper", "accent", "ornament", "colour", "drone")[index]
        voice_specs.append({"id": f"voice_{index + 1:02}", "role": role, "cycle_length_steps": cycle, "phase_offset_steps": (index * 2) % cycle})

    events: list[dict[str, object]] = []
    analysis: list[BarAnalysis] = []
    for bar in range(bars):
        position = bar / max(1, bars - 1)
        section = _section(position, climax_start, resolution_start)
        section_progress = (position * bars) % max(1, bars // 6) / max(1, bars // 6)
        density = _density(section, section_progress)
        chord_index = min(len(function_plan) - 1, bar // chord_bars)
        chord = function_plan[chord_index]
        tones = [(Fraction(item["ratio"]), str(item["role"])) for item in chord["tones"]]
        active_voices = max(1, round(voices * ({"introduction": .35, "accumulation": .60, "development": .82, "climax": 1, "resolution": .55, "coda": .25}[section])))
        hit_count = 0
        for voice_index, voice in enumerate(voice_specs[:active_voices]):
            cycle = int(voice["cycle_length_steps"])
            phase = 0 if section in {"resolution", "coda"} else int(voice["phase_offset_steps"])
            pulses = max(1, min(cycle, round(cycle * density * (1 + voice_index * .07))))
            pattern = euclidean_rhythm(cycle, pulses, phase)
            tone_index = min(len(tones) - 1, voice_index % len(tones))
            ratio, tone_role = tones[tone_index]
            if section == "coda" and voice_index > 0:
                continue
            octave = -1 if voice_index == 0 else min(2, voice_index // 2)
            sounding = ratio * (Fraction(2) ** octave)
            time_delta = _voice_time_delta(voice_index, bar, density, section)
            for step in range(steps_per_bar):
                if not pattern[(bar * steps_per_bar + step) % cycle]:
                    continue
                start = max(0, bar * beats + step / subdivisions + time_delta)
                gate = 0.55 if section in {"development", "climax"} else 0.8
                velocity = max(30, min(116, round(62 + density * 35 + (12 if step == 0 else 0) - voice_index * 2)))
                events.append({"start_beat": round(start, 5), "duration_beats": gate / subdivisions, "time_delta_beats": time_delta, "voice_id": voice["id"], "voice_role": voice["role"], "chord_id": chord["id"], "function": chord["function"], "ratio": ratio_text(sounding), "velocity": velocity, "accent": step == 0})
                hit_count += 1
        if section == "coda" and bar == bars - 1:
            events.append({"start_beat": bar * beats, "duration_beats": beats * 1.8, "voice_id": "drone", "voice_role": "drone", "chord_id": chord["id"], "function": "T", "ratio": "1/2", "velocity": 72, "accent": True})
        phase_dispersion = 0 if section in {"resolution", "coda"} else min(1, (active_voices - 1) / max(1, voices - 1) * .72)
        tension = min(1, FUNCTION_TENSION[str(chord["function"])] + density * .18 + phase_dispersion * .14)
        stability = max(0, min(1, (1 - tension) + (.35 if section == "coda" else 0)))
        analysis.append({"bar": bar + 1, "section": section, "density": round(hit_count / max(1, active_voices * steps_per_bar), 5), "tension": round(tension, 5), "phase_dispersion": round(phase_dispersion, 5), "stability": round(stability, 5)})
    drum_layers, drum_events = _drum_events(bars, float(config.get("drum_density", .55)), analysis) if config.get("include_drums", True) else ([], [])
    return {
        "metadata": {"title": "Minimal Functional Study", "tempo_bpm": tempo, "duration_bars": bars, "beats_per_bar": beats, "subdivisions_per_beat": subdivisions, "tuning": tuning, "seed": seed},
        "sections": [{"id": name, "start_bar": next((entry["bar"] + 1 for entry in analysis if entry["section"] == name), None)} for name in SECTION_ORDER],
        "chords": function_plan, "voices": voice_specs, "events": events, "analysis": analysis,
        "drum_layers": drum_layers, "drum_events": drum_events,
    }
