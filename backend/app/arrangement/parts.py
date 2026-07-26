from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from random import Random

from app.arrangement.form import ArrangementSection
from app.arrangement.profiles import GenreProfile, PartStyle
from app.arrangement.progression import ProgressionSlot, _place_in_register
from app.composition.rhythm import (
    CompositionClock,
    RhythmLayer,
    RhythmMapping,
    compile_rhythm,
)
from app.rhythm.engine import euclidean_rhythm
from app.tuning.analysis import cents

MAX_EVENTS = 8192

DRUM_NOTES = {"kick": 36, "snare": 38, "clap": 39, "closed_hat": 42, "open_hat": 46, "crash": 49}


@dataclass(frozen=True)
class ArrangementTrack:
    id: str
    role: str
    instrument: str
    register_low: float
    register_high: float
    waveform: str
    gain: float


@dataclass(frozen=True)
class ArrangementEvent:
    id: str
    track_id: str
    kind: str  # note | drum
    ratio: Fraction | None
    drum_note: int | None
    start_tick: int
    duration_ticks: int
    velocity: int
    articulation: str
    chord_index: int
    section_id: str
    source_gesture_id: str | None = None
    gesture_component: str | None = None
    phase_stream_id: str | None = None
    source_slot_index: int | None = None
    source_chord_id: str | None = None
    visit_index: int | None = None
    phase_iteration: int | None = None

    def payload(self) -> dict[str, object]:
        return {
            "id": self.id,
            "track_id": self.track_id,
            "kind": self.kind,
            "ratio": (
                f"{self.ratio.numerator}/{self.ratio.denominator}"
                if self.ratio is not None
                else None
            ),
            "drum_note": self.drum_note,
            "start_tick": self.start_tick,
            "duration_ticks": self.duration_ticks,
            "velocity": self.velocity,
            "articulation": self.articulation,
            "chord_index": self.chord_index,
            "section_id": self.section_id,
            "source_gesture_id": self.source_gesture_id,
            "gesture_component": self.gesture_component,
            "phase_stream_id": self.phase_stream_id,
            "source_slot_index": self.source_slot_index,
            "source_chord_id": self.source_chord_id,
            "visit_index": self.visit_index,
            "phase_iteration": self.phase_iteration,
        }


def build_tracks(
    profile: GenreProfile, drums_enabled: bool, melody_enabled: bool
) -> list[ArrangementTrack]:
    tracks: list[ArrangementTrack] = []
    for part in profile.parts:
        if not part.enabled:
            continue
        if part.role == "drums" and (not drums_enabled or not profile.rhythm.drums):
            continue
        if part.role == "melody" and not melody_enabled:
            continue
        tracks.append(
            ArrangementTrack(
                id=part.role,
                role=part.role,
                instrument=part.instrument,
                register_low=part.register_low,
                register_high=part.register_high,
                waveform=part.waveform,
                gain=_role_gain(part.role),
            )
        )
    if not tracks:
        raise ValueError("no parts remain enabled; check controls and profile part settings")
    return tracks


def generate_drum_events(
    clock: CompositionClock,
    sections: list[ArrangementSection],
    profile: GenreProfile,
    density: float,
    syncopation: float,
    humanization: float,
    seed: int,
) -> list[ArrangementEvent]:
    """Section-aware GM drum events with fills and shared accent landmarks."""
    random = Random(seed ^ 0xD00D)
    events: list[ArrangementEvent] = []
    beat = clock.subdivisions_per_beat
    spb = clock.subdivisions_per_bar
    duration = max(1, clock.ticks_per_subdivision // 2)
    for section in sections:
        for bar in range(section.start_bar, section.end_bar):
            energy = section.energy_at(bar)
            level = min(0.95, profile.rhythm.density * (0.35 + density) * (0.4 + 0.8 * energy))
            bar_start = bar * spb
            sync = min(1.0, (profile.rhythm.syncopation + syncopation) / 2)
            # Kick: strong beats plus seeded syncopated extras.
            kick_steps = {0, 2 * beat} if spb >= 4 * beat else {0}
            if profile.rhythm.half_time:
                kick_steps = {0}
                if random.random() < 0.4 + 0.4 * energy:
                    kick_steps.add(2 * beat + beat // 2)
            elif random.random() < sync:
                kick_steps.add(3 * beat + beat // 2 if spb >= 4 * beat else beat // 2)
            for step in sorted(kick_steps):
                if step < spb and random.random() < 0.5 + level:
                    events.append(
                        _drum(bar_start + step, DRUM_NOTES["kick"], 108, section.id, 0, clock, duration, random, humanization)
                    )
            # Snare: backbeat, or beat 3 under a half-time feel.
            snare_steps = {2 * beat} if profile.rhythm.half_time else {beat, 3 * beat}
            for step in sorted(snare_steps):
                if step < spb:
                    events.append(
                        _drum(bar_start + step, DRUM_NOTES["snare"], 100, section.id, 0, clock, duration, random, humanization)
                    )
            # Hats: euclidean density layer.
            pulses = max(1, round(spb * min(0.9, level * 1.3)))
            hat = euclidean_rhythm(spb, pulses, random.randrange(spb))
            for step, active in enumerate(hat):
                if active:
                    note = DRUM_NOTES["open_hat"] if step == spb - 1 and energy > 0.7 else DRUM_NOTES["closed_hat"]
                    events.append(
                        _drum(bar_start + step, note, 72, section.id, 0, clock, duration, random, humanization)
                    )
            # Fill on the final bar of a section (except the outro tail).
            if (
                profile.rhythm.fills
                and bar == section.end_bar - 1
                and section.canonical_role not in {"outro"}
                and section.end_bar < clock.bars
            ):
                for step in range(spb - beat, spb):
                    events.append(
                        _drum(bar_start + step, DRUM_NOTES["snare"], 96 + (step - (spb - beat)) * 4, section.id, 0, clock, duration, random, humanization)
                    )
            # Crash at section downbeats.
            if profile.rhythm.crash_on_section and bar == section.start_bar:
                events.append(
                    _drum(bar_start, DRUM_NOTES["crash"], 112, section.id, 0, clock, duration, random, humanization)
                )
    return events


def _drum(
    subdivision: int,
    note: int,
    velocity: int,
    section_id: str,
    chord_index: int,
    clock: CompositionClock,
    duration: int,
    random: Random,
    humanization: float,
) -> ArrangementEvent:
    jitter = round(random.uniform(-8, 8) * humanization)
    return ArrangementEvent(
        id="",
        track_id="drums",
        kind="drum",
        ratio=None,
        drum_note=note,
        start_tick=subdivision * clock.ticks_per_subdivision,
        duration_ticks=duration,
        velocity=max(1, min(127, velocity + jitter)),
        articulation="gate",
        chord_index=chord_index,
        section_id=section_id,
    )


def generate_pitched_events(
    clock: CompositionClock,
    sections: list[ArrangementSection],
    profile: GenreProfile,
    parts: list[PartStyle],
    progression: list[ProgressionSlot],
    voiced_chords: list[tuple[Fraction, ...]],
    bass_notes: list[Fraction],
    melody_notes: list[Fraction],
    density: float,
    syncopation: float,
    humanization: float,
    seed: int,
) -> list[ArrangementEvent]:
    """Compile pitched parts onto the shared clock through the G10 event compiler."""
    random = Random(seed ^ 0xBEEF)
    layers: list[RhythmLayer] = []
    mappings: list[RhythmMapping] = []
    landmarks = {slot.start_subdivision for slot in progression}
    roles = {part.role: part for part in parts}
    for part in parts:
        if part.role == "drums":
            continue
        pattern = _section_pattern(clock, sections, profile, part, density, syncopation, random)
        if part.role in {"harmony", "bass"}:
            for boundary in landmarks:
                if boundary < len(pattern):
                    pattern[boundary] = 1
        velocities = tuple(
            _velocity(active, step, part.role, landmarks, random, humanization)
            for step, active in enumerate(pattern)
        )
        layers.append(RhythmLayer(f"arr-{part.role}", tuple(pattern), velocities))
        mappings.append(_mapping_for(part))
    compiled = compile_rhythm(
        clock,
        [list(chord) for chord in voiced_chords],
        bass_notes,
        [melody_notes],
        layers,
        mappings,
        [slot.duration_subdivisions for slot in progression],
    )
    section_by_slot = {slot.index: slot.section_id for slot in progression}
    events = []
    for event in compiled.events:
        role = event.track_id.split("@", 1)[0]
        if role.startswith("chord_tone"):
            role = "texture"
        if role.startswith("melody"):
            role = "melody"
        if role not in roles:
            continue
        events.append(
            ArrangementEvent(
                id="",
                track_id=role,
                kind="note",
                ratio=event.ratio,
                drum_note=None,
                start_tick=event.start_tick,
                duration_ticks=event.duration_ticks,
                velocity=event.velocity,
                articulation=event.articulation,
                chord_index=event.chord_index,
                section_id=section_by_slot.get(event.chord_index, sections[0].id),
            )
        )
    return events


def _mapping_for(part: PartStyle) -> RhythmMapping:
    tie = part.gate > 1.2
    if part.role == "harmony":
        return RhythmMapping(
            f"arr-{part.role}", "harmony", gate=part.gate, collision="retrigger",
            articulation="tie" if tie else "gate",
        )
    if part.role == "bass":
        return RhythmMapping(
            f"arr-{part.role}", "bass", gate=part.gate, collision="merge",
            articulation="tie" if tie else "gate",
        )
    if part.role == "melody":
        return RhythmMapping(
            f"arr-{part.role}", "melody:0", gate=part.gate, collision="merge",
            articulation="tie" if tie else "gate",
        )
    # texture: sustained chord root one octave up
    return RhythmMapping(
        f"arr-{part.role}", "chord_tone:0", overflow="wrap", gate=part.gate,
        register_octave=1, collision="merge", articulation="tie",
    )


def _section_pattern(
    clock: CompositionClock,
    sections: list[ArrangementSection],
    profile: GenreProfile,
    part: PartStyle,
    density: float,
    syncopation: float,
    random: Random,
) -> list[int]:
    pattern: list[int] = []
    spb = clock.subdivisions_per_bar
    for section in sections:
        span = section.bars * spb
        energy = section.energy_at(section.start_bar + section.bars // 2)
        level = min(0.9, part.density * (0.3 + density) * (0.4 + 0.9 * energy))
        pulses = max(1, round(span * level * 0.5))
        rotation = random.randrange(span) if syncopation > 0.3 else 0
        pattern.extend(euclidean_rhythm(span, pulses, rotation))
    result = pattern[: clock.total_subdivisions]
    if len(result) < clock.total_subdivisions:
        result.extend([0] * (clock.total_subdivisions - len(result)))
    return result


def _velocity(
    active: int,
    step: int,
    role: str,
    landmarks: set[int],
    random: Random,
    humanization: float,
) -> int:
    if not active:
        return 0
    base = {"bass": 104, "harmony": 90, "melody": 96, "texture": 78}.get(role, 90)
    accent = 14 if step in landmarks else 0
    jitter = round(random.uniform(-6, 6) * humanization)
    return max(1, min(127, base + accent + jitter))


def finalize_events(
    events: list[ArrangementEvent], total_ticks: int | None = None
) -> list[ArrangementEvent]:
    """Bound events to the timeline, sort deterministically, and assign stable ids."""
    bounded: list[ArrangementEvent] = []
    for event in events:
        if total_ticks is not None:
            if not 0 <= event.start_tick < total_ticks:
                raise ValueError(
                    f"event on track '{event.track_id}' starts outside the arrangement clock"
                )
            duration_ticks = min(event.duration_ticks, total_ticks - event.start_tick)
        else:
            duration_ticks = event.duration_ticks
        if duration_ticks <= 0:
            raise ValueError(
                f"event on track '{event.track_id}' must have a positive duration"
            )
        bounded.append(
            ArrangementEvent(
                id=event.id,
                track_id=event.track_id,
                kind=event.kind,
                ratio=event.ratio,
                drum_note=event.drum_note,
                start_tick=event.start_tick,
                duration_ticks=duration_ticks,
                velocity=event.velocity,
                articulation=event.articulation,
                chord_index=event.chord_index,
                section_id=event.section_id,
                source_gesture_id=event.source_gesture_id,
                gesture_component=event.gesture_component,
                phase_stream_id=event.phase_stream_id,
                source_slot_index=event.source_slot_index,
                source_chord_id=event.source_chord_id,
                visit_index=event.visit_index,
                phase_iteration=event.phase_iteration,
            )
        )
    ordered = sorted(
        bounded,
        key=lambda event: (
            event.start_tick,
            event.track_id,
            event.drum_note if event.drum_note is not None else -1,
            float(event.ratio) if event.ratio is not None else 0.0,
        ),
    )
    if len(ordered) > MAX_EVENTS:
        raise ValueError(
            f"the arrangement compiles to {len(ordered)} events; the limit is "
            f"{MAX_EVENTS} (reduce bars, density, or part count)"
        )
    return [
        ArrangementEvent(
            id=f"ev-{index + 1:05d}",
            track_id=event.track_id,
            kind=event.kind,
            ratio=event.ratio,
            drum_note=event.drum_note,
            start_tick=event.start_tick,
            duration_ticks=event.duration_ticks,
            velocity=event.velocity,
            articulation=event.articulation,
            chord_index=event.chord_index,
            section_id=event.section_id,
            source_gesture_id=event.source_gesture_id,
            gesture_component=event.gesture_component,
            phase_stream_id=event.phase_stream_id,
            source_slot_index=event.source_slot_index,
            source_chord_id=event.source_chord_id,
            visit_index=event.visit_index,
            phase_iteration=event.phase_iteration,
        )
        for index, event in enumerate(ordered)
    ]


def select_bass_notes(
    progression: list[ProgressionSlot],
    roots: list[Fraction],
    part: PartStyle,
) -> list[Fraction]:
    """Chord root (or lowest chord tone) placed in the bass register."""
    notes = []
    previous: Fraction | None = None
    for slot in progression:
        placed = _place_in_register(roots[slot.index], part.register_low, part.register_high, previous)
        notes.append(placed)
        previous = placed
    return notes


def select_melody_notes(
    progression: list[ProgressionSlot],
    voiced_chords: list[tuple[Fraction, ...]],
    scale: list[Fraction],
    part: PartStyle,
    seed: int,
    max_leap_cents: float = 700,
) -> list[Fraction]:
    """Seeded melody: chord-tone-weighted scale selection with bounded leaps."""
    random = Random(seed ^ 0x3E10)
    notes: list[Fraction] = []
    previous: Fraction | None = None
    for slot in progression:
        chord_tones = set(voiced_chords[slot.index])
        candidates = []
        for pitch_class in scale:
            placed = _place_in_register(
                pitch_class, part.register_low, part.register_high, previous
            )
            weight = 0 if placed in chord_tones else 1
            leap = abs(cents(placed / previous)) if previous else 0.0
            candidates.append((weight, leap, random.random(), placed))
        bounded = [c for c in candidates if c[1] <= max_leap_cents] or candidates
        bounded.sort(key=lambda item: (item[0], item[1], item[2]))
        choice = bounded[min(random.randrange(min(2, len(bounded))), len(bounded) - 1)]
        notes.append(choice[3])
        previous = choice[3]
    return notes


def _role_gain(role: str) -> float:
    return {"drums": 0.9, "bass": 0.95, "harmony": 0.75, "melody": 0.85, "texture": 0.5}.get(
        role, 0.8
    )
