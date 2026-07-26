from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from random import Random

from app.arrangement.form import ArrangementSection
from app.arrangement.parts import ArrangementEvent
from app.arrangement.profiles import HarmonyPerformanceStyle, PartStyle
from app.arrangement.progression import ProgressionSlot, _place_in_register
from app.composition.rhythm import CompositionClock
from app.rhythm.engine import euclidean_rhythm
from app.tuning.analysis import cents


@dataclass(frozen=True)
class HarmonyGesture:
    id: str
    section_id: str
    chord_index: int
    mode: str
    start_tick: int
    duration_ticks: int
    resolved_settings: dict[str, object]

    def payload(self) -> dict[str, object]:
        return {
            "id": self.id,
            "section_id": self.section_id,
            "chord_index": self.chord_index,
            "mode": self.mode,
            "start_tick": self.start_tick,
            "duration_ticks": self.duration_ticks,
            "resolved_settings": self.resolved_settings,
        }


def generate_harmony_gestures(
    clock: CompositionClock,
    sections: list[ArrangementSection],
    part: PartStyle,
    progression: list[ProgressionSlot],
    voiced_chords: list[tuple[Fraction, ...]],
    roots: list[Fraction],
    bass_notes: list[Fraction],
    bass_events: list[ArrangementEvent],
    style: HarmonyPerformanceStyle,
    density: float,
    syncopation: float,
    humanization: float,
    seed: int,
) -> tuple[list[ArrangementEvent], list[HarmonyGesture], list[str]]:
    """Expand voiced chord spans into block, arpeggio, or stride events."""
    random = Random(seed ^ 0x6A65)
    section_by_id = {section.id: section for section in sections}
    modes = _resolve_section_modes(style, sections, random)
    bass_by_tick = {
        event.start_tick: event
        for event in bass_events
        if event.track_id == "bass" and event.ratio is not None
    }
    events: list[ArrangementEvent] = []
    gestures: list[HarmonyGesture] = []
    mode_counts = {"block": 0, "arpeggio": 0, "stride": 0}
    for slot in progression:
        section = section_by_id[slot.section_id]
        mode = modes[slot.section_id]
        mode_counts[mode] += 1
        gesture_id = f"gesture-{slot.index + 1:04d}"
        start = slot.start_subdivision
        end = start + slot.duration_subdivisions
        settings = _resolved_settings(style, mode)
        gestures.append(
            HarmonyGesture(
                id=gesture_id,
                section_id=slot.section_id,
                chord_index=slot.index,
                mode=mode,
                start_tick=start * clock.ticks_per_subdivision,
                duration_ticks=slot.duration_subdivisions * clock.ticks_per_subdivision,
                resolved_settings=settings,
            )
        )
        if mode == "arpeggio":
            events.extend(
                _arpeggio_events(
                    clock,
                    part,
                    slot,
                    voiced_chords[slot.index],
                    gesture_id,
                    style,
                    humanization,
                    random,
                )
            )
        elif mode == "stride":
            events.extend(
                _stride_events(
                    clock,
                    part,
                    slot,
                    voiced_chords[slot.index],
                    roots[slot.index],
                    bass_notes[slot.index] if slot.index < len(bass_notes) else None,
                    bass_by_tick,
                    gesture_id,
                    style,
                    humanization,
                    random,
                )
            )
        else:
            events.extend(
                _block_events(
                    clock,
                    part,
                    section,
                    slot,
                    voiced_chords[slot.index],
                    gesture_id,
                    style,
                    density,
                    syncopation,
                    humanization,
                    random,
                )
            )
        if end > clock.total_subdivisions:
            raise ValueError("harmony gesture extends beyond the arrangement clock")
    summary = ", ".join(
        f"{mode}={count}" for mode, count in mode_counts.items() if count
    )
    return events, gestures, [f"harmony performance: {summary}"]


def _resolve_section_modes(
    style: HarmonyPerformanceStyle,
    sections: list[ArrangementSection],
    random: Random,
) -> dict[str, str]:
    if style.mode != "auto":
        return {section.id: style.mode for section in sections}
    result: dict[str, str] = {}
    for section in sections:
        weights = []
        for mode in style.allowed_modes:
            weight = style.mode_weights.get(mode, 1.0)
            if section.canonical_role in {"chorus", "drop"} and mode == "block":
                weight *= 1.8
            if section.canonical_role in {"intro", "verse"} and mode == "arpeggio":
                weight *= 1.4
            if section.canonical_role == "outro" and mode == "arpeggio":
                weight *= 1.25
            weights.append(weight)
        if not any(weights):
            weights = [1.0] * len(style.allowed_modes)
        result[section.id] = random.choices(style.allowed_modes, weights=weights, k=1)[0]
    return result


def _resolved_settings(
    style: HarmonyPerformanceStyle, mode: str
) -> dict[str, object]:
    settings: dict[str, object] = {
        "rate_subdivisions": style.rate_subdivisions,
        "gate": style.gate,
        "velocity_curve": style.velocity_curve,
    }
    if mode == "arpeggio":
        settings["order"] = style.arpeggio.order
        settings["octave_span"] = style.arpeggio.octave_span
        settings["rotate_per_chord"] = style.arpeggio.rotate_per_chord
    elif mode == "stride":
        settings["low_note_source"] = style.stride.low_note_source
        settings["chord_tones"] = style.stride.chord_tones
        settings["bass_conflict"] = style.stride.bass_conflict
    return settings


def _block_events(
    clock: CompositionClock,
    part: PartStyle,
    section: ArrangementSection,
    slot: ProgressionSlot,
    tones: tuple[Fraction, ...],
    gesture_id: str,
    style: HarmonyPerformanceStyle,
    density: float,
    syncopation: float,
    humanization: float,
    random: Random,
) -> list[ArrangementEvent]:
    steps = slot.duration_subdivisions
    energy = section.energy_at(section.start_bar + section.bars // 2)
    level = min(0.95, part.density * (0.35 + density) * (0.45 + energy))
    pulses = max(1, min(steps, round(steps * level * 0.25)))
    rotation = random.randrange(steps) if syncopation > 0.45 and steps > 1 else 0
    pattern = euclidean_rhythm(steps, pulses, rotation)
    pattern[0] = 1
    events = []
    for local_step, active in enumerate(pattern):
        if not active:
            continue
        subdivision = slot.start_subdivision + local_step
        duration = _duration_ticks(clock, style, slot, subdivision)
        velocity = _gesture_velocity(
            style, subdivision, clock, 90, humanization, random
        )
        for tone in tones:
            events.append(
                _harmony_event(
                    slot,
                    gesture_id,
                    "block",
                    tone,
                    subdivision * clock.ticks_per_subdivision,
                    duration,
                    velocity,
                    style,
                )
            )
    return events


def _arpeggio_events(
    clock: CompositionClock,
    part: PartStyle,
    slot: ProgressionSlot,
    tones: tuple[Fraction, ...],
    gesture_id: str,
    style: HarmonyPerformanceStyle,
    humanization: float,
    random: Random,
) -> list[ArrangementEvent]:
    ordered = _arpeggio_order(tones, part, slot.index, style, random)
    rate = style.rate_subdivisions
    events = []
    for event_index, subdivision in enumerate(
        range(
            slot.start_subdivision,
            slot.start_subdivision + slot.duration_subdivisions,
            rate,
        )
    ):
        tone = ordered[event_index % len(ordered)]
        events.append(
            _harmony_event(
                slot,
                gesture_id,
                "tone",
                tone,
                subdivision * clock.ticks_per_subdivision,
                _duration_ticks(clock, style, slot, subdivision),
                _gesture_velocity(
                    style, subdivision, clock, 88, humanization, random
                ),
                style,
            )
        )
    return events


def _arpeggio_order(
    tones: tuple[Fraction, ...],
    part: PartStyle,
    chord_index: int,
    style: HarmonyPerformanceStyle,
    random: Random,
) -> list[Fraction]:
    expanded = set(tones)
    for octave in range(1, style.arpeggio.octave_span):
        for tone in tones:
            candidate = tone * 2**octave
            if float(candidate) <= part.register_high:
                expanded.add(candidate)
    ordered = sorted(expanded)
    order = style.arpeggio.order
    if order == "down":
        ordered.reverse()
    elif order == "up_down" and len(ordered) > 2:
        ordered = [*ordered, *ordered[-2:0:-1]]
    elif order == "outside_in":
        outside = []
        while ordered:
            outside.append(ordered.pop(0))
            if ordered:
                outside.append(ordered.pop())
        ordered = outside
    elif order == "seeded":
        random.shuffle(ordered)
    if style.arpeggio.rotate_per_chord and ordered:
        amount = chord_index % len(ordered)
        ordered = [*ordered[amount:], *ordered[:amount]]
    return ordered


def _stride_events(
    clock: CompositionClock,
    part: PartStyle,
    slot: ProgressionSlot,
    tones: tuple[Fraction, ...],
    root: Fraction,
    bass_note: Fraction | None,
    bass_by_tick: dict[int, ArrangementEvent],
    gesture_id: str,
    style: HarmonyPerformanceStyle,
    humanization: float,
    random: Random,
) -> list[ArrangementEvent]:
    events = []
    beat = clock.subdivisions_per_beat
    start = slot.start_subdivision
    end = start + slot.duration_subdivisions
    for subdivision in range(start, end):
        if subdivision % beat:
            continue
        beat_index = (subdivision // beat) % clock.beats_per_bar
        component = _stride_component(clock.beats_per_bar, beat_index)
        if component is None:
            continue
        tick = subdivision * clock.ticks_per_subdivision
        if component == "low":
            pitch = _stride_low_pitch(part, tones, root, bass_note, style)
            if not _allow_stride_low(pitch, tick, bass_by_tick, style):
                continue
            event_tones = [pitch]
            base_velocity = 98
        else:
            event_tones = list(tones)
            if style.stride.chord_tones == "shell" and len(event_tones) > 2:
                event_tones = [event_tones[0], event_tones[-1]]
            base_velocity = 86
        duration = _duration_ticks(clock, style, slot, subdivision)
        velocity = _gesture_velocity(
            style, subdivision, clock, base_velocity, humanization, random
        )
        for tone in event_tones:
            events.append(
                _harmony_event(
                    slot,
                    gesture_id,
                    component,
                    tone,
                    tick,
                    duration,
                    velocity,
                    style,
                )
            )
    return events


def _stride_component(beats_per_bar: int, beat_index: int) -> str | None:
    if beats_per_bar == 3:
        return "low" if beat_index == 0 else "chord"
    if beats_per_bar == 6:
        if beat_index in {0, 3}:
            return "low"
        if beat_index in {1, 4}:
            return "chord"
        return None
    return "low" if beat_index % 2 == 0 else "chord"


def _stride_low_pitch(
    part: PartStyle,
    tones: tuple[Fraction, ...],
    root: Fraction,
    bass_note: Fraction | None,
    style: HarmonyPerformanceStyle,
) -> Fraction:
    if style.stride.low_note_source == "bass_note" and bass_note is not None:
        source = bass_note
    elif style.stride.low_note_source == "lowest_voiced":
        source = min(tones)
    else:
        source = root
    low = max(0.125, part.register_low / 2)
    return _place_in_register(source, low, part.register_low, None)


def _allow_stride_low(
    pitch: Fraction,
    tick: int,
    bass_by_tick: dict[int, ArrangementEvent],
    style: HarmonyPerformanceStyle,
) -> bool:
    bass_event = bass_by_tick.get(tick)
    if bass_event is None:
        return True
    if style.stride.bass_conflict == "yield":
        return False
    if style.stride.bass_conflict == "double":
        return True
    assert bass_event.ratio is not None
    return abs(cents(pitch / bass_event.ratio)) >= 700


def _duration_ticks(
    clock: CompositionClock,
    style: HarmonyPerformanceStyle,
    slot: ProgressionSlot,
    subdivision: int,
) -> int:
    raw = max(
        1,
        round(
            style.gate
            * style.rate_subdivisions
            * clock.ticks_per_subdivision
        ),
    )
    slot_end = (
        slot.start_subdivision + slot.duration_subdivisions
    ) * clock.ticks_per_subdivision
    return max(1, min(raw, slot_end - subdivision * clock.ticks_per_subdivision))


def _gesture_velocity(
    style: HarmonyPerformanceStyle,
    subdivision: int,
    clock: CompositionClock,
    base: int,
    humanization: float,
    random: Random,
) -> int:
    accent = 0
    if style.velocity_curve == "metrical":
        accent = 12 if subdivision % clock.subdivisions_per_bar == 0 else 6 if (
            subdivision % clock.subdivisions_per_beat == 0
        ) else 0
    elif style.velocity_curve == "phrase":
        accent = 10 if subdivision % clock.subdivisions_per_bar == 0 else 0
    jitter = round(random.uniform(-6, 6) * humanization)
    return max(1, min(127, base + accent + jitter))


def _harmony_event(
    slot: ProgressionSlot,
    gesture_id: str,
    component: str,
    tone: Fraction,
    start_tick: int,
    duration_ticks: int,
    velocity: int,
    style: HarmonyPerformanceStyle,
) -> ArrangementEvent:
    return ArrangementEvent(
        id="",
        track_id="harmony",
        kind="note",
        ratio=tone,
        drum_note=None,
        start_tick=start_tick,
        duration_ticks=duration_ticks,
        velocity=velocity,
        articulation="tie" if style.gate > 1.2 else "gate",
        chord_index=slot.index,
        section_id=slot.section_id,
        source_gesture_id=gesture_id,
        gesture_component=component,
    )
