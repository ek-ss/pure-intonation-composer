from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from math import log2
from random import Random

from app.rhythm.engine import euclidean_rhythm


@dataclass(frozen=True)
class CompositionClock:
    beats_per_bar: int = 4
    subdivisions_per_beat: int = 4
    bars: int = 8
    ticks_per_beat: int = 480
    tempo_bpm: float = 96

    @property
    def ticks_per_subdivision(self) -> int:
        return self.ticks_per_beat // self.subdivisions_per_beat

    @property
    def subdivisions_per_bar(self) -> int:
        return self.beats_per_bar * self.subdivisions_per_beat

    @property
    def total_subdivisions(self) -> int:
        return self.subdivisions_per_bar * self.bars

    @property
    def total_ticks(self) -> int:
        return self.total_subdivisions * self.ticks_per_subdivision


@dataclass(frozen=True)
class RhythmLayer:
    name: str
    pattern: tuple[int, ...]
    velocities: tuple[int, ...]
    phase_offsets: tuple[int, ...] = ()


@dataclass(frozen=True)
class RhythmMapping:
    source_layer: str
    target: str
    policy: str = "fixed-index"
    overflow: str = "drop"
    gate: float = 0.9
    register_octave: int = 0
    velocity_scale: float = 1.0
    collision: str = "merge"
    articulation: str = "gate"


@dataclass(frozen=True)
class RhythmGeneratorSettings:
    target: str
    strategy: str = "transition-aware"
    profile: str = "grounded"
    density: float = 0.35
    syncopation: float = 0.35


@dataclass(frozen=True)
class RhythmicNoteEvent:
    track_id: str
    chord_index: int
    ratio: Fraction
    start_tick: int
    duration_ticks: int
    velocity: int
    articulation: str
    source_layer: str | None

    def payload(self) -> dict[str, object]:
        return {
            "track_id": self.track_id,
            "chord_index": self.chord_index,
            "ratio": _ratio_text(self.ratio),
            "start_tick": self.start_tick,
            "duration_ticks": self.duration_ticks,
            "velocity": self.velocity,
            "articulation": self.articulation,
            "source_layer": self.source_layer,
        }


@dataclass(frozen=True)
class CompiledRhythm:
    clock: CompositionClock
    chord_spans: tuple[tuple[int, int], ...]
    events: tuple[RhythmicNoteEvent, ...]
    metrics: dict[str, object]

    def payload(self) -> dict[str, object]:
        return {
            "clock": {
                "beats_per_bar": self.clock.beats_per_bar,
                "subdivisions_per_beat": self.clock.subdivisions_per_beat,
                "bars": self.clock.bars,
                "ticks_per_beat": self.clock.ticks_per_beat,
                "tempo_bpm": self.clock.tempo_bpm,
                "total_ticks": self.clock.total_ticks,
            },
            "chord_spans": [
                {
                    "chord_index": index,
                    "start_tick": start,
                    "duration_ticks": end - start,
                }
                for index, (start, end) in enumerate(self.chord_spans)
            ],
            "events": [event.payload() for event in self.events],
            "metrics": self.metrics,
        }


def compile_rhythm(
    clock: CompositionClock,
    chords: list[list[Fraction]],
    bass: list[Fraction],
    melody: list[list[Fraction]],
    layers: list[RhythmLayer],
    mappings: list[RhythmMapping],
    chord_durations: list[int] | None = None,
) -> CompiledRhythm:
    """Map polymetric rhythm layers onto ordered composition pitches."""
    _validate_material(clock, chords, bass, melody, layers, mappings)
    spans = _chord_spans(clock, len(chords), chord_durations)
    layer_by_name = {layer.name: layer for layer in layers}
    prior_by_mapping: dict[int, Fraction] = {}
    events: list[tuple[RhythmicNoteEvent, str]] = []
    for subdivision in range(clock.total_subdivisions):
        tick = subdivision * clock.ticks_per_subdivision
        chord_index = _chord_at_tick(spans, tick)
        for mapping_index, mapping in enumerate(mappings):
            if mapping.target == "mute":
                continue
            layer = layer_by_name[mapping.source_layer]
            active, velocity = _layer_hit(layer, subdivision, clock)
            if not active:
                continue
            ratios = _target_ratios(
                mapping,
                chord_index,
                chords,
                bass,
                melody,
                prior_by_mapping.get(mapping_index),
            )
            if not ratios:
                continue
            chord_end = spans[chord_index][1]
            raw_duration = max(1, round(mapping.gate * clock.ticks_per_subdivision))
            duration = (
                raw_duration
                if mapping.articulation == "tie"
                else max(1, min(raw_duration, chord_end - tick))
            )
            scaled_velocity = max(1, min(127, round(velocity * mapping.velocity_scale)))
            for ratio in ratios:
                track_id = _track_id(mapping)
                events.append(
                    (
                        RhythmicNoteEvent(
                            track_id,
                            chord_index,
                            ratio,
                            tick,
                            duration,
                            scaled_velocity,
                            mapping.articulation,
                            mapping.source_layer,
                        ),
                        mapping.collision,
                    )
                )
                prior_by_mapping[mapping_index] = ratio
    resolved = _resolve_collisions(events)
    if len(resolved) > 4096:
        raise ValueError("compiled rhythm exceeds the 4096 event limit")
    return CompiledRhythm(clock, tuple(spans), tuple(resolved), _event_metrics(resolved, clock))


def generate_compose_rhythm(
    clock: CompositionClock,
    chords: list[list[Fraction]],
    bass: list[Fraction],
    melody: list[list[Fraction]],
    strategy: str,
    profile: str,
    density: float,
    syncopation: float,
    seed: int,
    targets: list[str],
    transition_scores: list[float | None] | None = None,
    target_settings: list[RhythmGeneratorSettings] | None = None,
) -> tuple[list[RhythmLayer], list[RhythmMapping], list[int], CompiledRhythm]:
    """Generate deterministic Compose-native patterns and compile their events."""
    settings = (
        target_settings
        if target_settings is not None
        else [
            RhythmGeneratorSettings(target, strategy, profile, density, syncopation)
            for target in targets
        ]
    )
    _validate_generator_settings(settings)
    if not settings:
        raise ValueError("at least one target is required")
    harmony_settings = next(
        (setting for setting in settings if setting.target == "harmony"),
        None,
    )
    use_transition_timing = (
        harmony_settings is not None and harmony_settings.strategy == "transition-aware"
        if target_settings is not None
        else strategy == "transition-aware"
    )
    chord_durations = (
        transition_aware_durations(clock, chords, transition_scores, seed)
        if use_transition_timing
        else _even_chord_durations(clock.total_subdivisions, len(chords))
    )
    layers = _native_layers(
        clock,
        chords,
        seed,
        settings,
        chord_durations,
    )
    mappings = [
        RhythmMapping(
            layer.name,
            setting.target,
            gate=_profile_gate(setting.profile, setting.target),
            velocity_scale=_role_velocity(setting.target),
            collision="retrigger" if setting.target == "harmony" else "merge",
            articulation="tie" if setting.profile == "flowing" else "gate",
        )
        for layer, setting in zip(layers, settings)
    ]
    compiled = compile_rhythm(
        clock,
        chords,
        bass,
        melody,
        layers,
        mappings,
        chord_durations,
    )
    return layers, mappings, chord_durations, compiled


def transition_aware_durations(
    clock: CompositionClock,
    chords: list[list[Fraction]],
    transition_scores: list[float | None] | None,
    seed: int,
) -> list[int]:
    """Fit transition-aware chord durations to the exact form length."""
    if not chords:
        raise ValueError("at least one chord is required")
    total = clock.total_subdivisions
    if total < len(chords):
        raise ValueError("the composition clock needs at least one subdivision per chord")
    candidates = sorted(
        {
            1,
            max(1, clock.subdivisions_per_beat // 2),
            clock.subdivisions_per_beat,
            clock.subdivisions_per_beat * 2,
            clock.subdivisions_per_beat * 4,
            clock.subdivisions_per_beat * 6,
            clock.subdivisions_per_beat * 8,
        }
    )
    motion = _transition_motion(chords, transition_scores)
    states: dict[int, tuple[float, list[int]]] = {0: (0.0, [])}
    random = Random(seed)
    jitter = {
        (index, duration): random.random() * 1e-6
        for index in range(len(chords))
        for duration in candidates
    }
    for index in range(len(chords)):
        remaining_chords = len(chords) - index - 1
        next_states: dict[int, tuple[float, list[int]]] = {}
        for used, (score, durations) in states.items():
            for duration in candidates:
                end = used + duration
                if end + remaining_chords > total or end > total:
                    continue
                metrical = _metrical_strength(used, clock)
                motion_weight = min(1.0, motion[index] / 1200)
                target = clock.subdivisions_per_beat * (6 - 4 * motion_weight)
                cost = (
                    score
                    + (1 - metrical) * (1 + motion[index] / 1200)
                    + abs(duration - target) / max(1, clock.subdivisions_per_beat)
                    + jitter[(index, duration)]
                )
                current = next_states.get(end)
                if current is None or cost < current[0]:
                    next_states[end] = (cost, [*durations, duration])
        states = next_states
    if total in states:
        return states[total][1]
    return _even_chord_durations(total, len(chords))


def _native_layers(
    clock: CompositionClock,
    chords: list[list[Fraction]],
    seed: int,
    settings: list[RhythmGeneratorSettings],
    chord_durations: list[int],
) -> list[RhythmLayer]:
    total = clock.total_subdivisions
    boundaries = set()
    cursor = 0
    for duration in chord_durations:
        boundaries.add(cursor)
        cursor += duration
    layers: list[RhythmLayer] = []
    placed: list[list[int]] = []
    for index, setting in enumerate(settings):
        target = setting.target
        role_density = _role_density(setting.profile, target, setting.density)
        if setting.strategy == "ratio-derived":
            pattern = _ratio_derived_pattern(total, chords, role_density, index)
        elif setting.strategy == "interlocking":
            pattern = _interlocking_pattern(
                total,
                role_density,
                setting.syncopation,
                seed + index,
                boundaries,
                placed,
                clock,
            )
        else:
            pattern = _semi_markov_pattern(
                total,
                role_density,
                setting.syncopation,
                seed + index,
                boundaries,
                target,
                setting.profile,
                clock,
            )
        if target in {"harmony", "bass"}:
            for boundary in boundaries:
                pattern[boundary] = 1
        velocities = tuple(
            _generated_velocity(step, active, target, clock) for step, active in enumerate(pattern)
        )
        layers.append(RhythmLayer(f"native-{index + 1}", tuple(pattern), velocities))
        placed.append(pattern)
    return layers


def _validate_generator_settings(settings: list[RhythmGeneratorSettings]) -> None:
    strategies = {"transition-aware", "semi-markov", "interlocking", "ratio-derived"}
    profiles = {"grounded", "interlocking", "sparse", "flowing"}
    if len({setting.target for setting in settings}) != len(settings):
        raise ValueError("Compose rhythm generator targets must be unique")
    for setting in settings:
        prefix, separator, index = setting.target.partition(":")
        if setting.target not in {"harmony", "bass"} and (
            prefix not in {"melody", "chord_tone"}
            or separator != ":"
            or not index.isdigit()
        ):
            raise ValueError(f"unknown Compose rhythm target: {setting.target}")
        if setting.strategy not in strategies:
            raise ValueError("unknown Compose rhythm strategy")
        if setting.profile not in profiles:
            raise ValueError("unknown Compose rhythm profile")
        if not 0.02 <= setting.density <= 0.95 or not 0 <= setting.syncopation <= 1:
            raise ValueError("density and syncopation are out of range")


def _semi_markov_pattern(
    total: int,
    density: float,
    syncopation: float,
    seed: int,
    boundaries: set[int],
    target: str,
    profile: str,
    clock: CompositionClock,
) -> list[int]:
    random = Random(seed)
    pattern = [0] * total
    step = 0
    state = "REST"
    while step < total:
        strength = _metrical_strength(step, clock)
        boundary = step in boundaries
        role_bias = 0.25 if target in {"harmony", "bass"} and boundary else 0
        weak_bias = syncopation * (1 - strength) * 0.35
        attack_probability = min(0.98, density + role_bias + weak_bias)
        attack = random.random() < attack_probability
        if attack and (state != "ATTACK" or profile == "flowing"):
            pattern[step] = 1
            state = "ATTACK"
            run = random.choice((1, 2, 2, 3)) if profile != "sparse" else random.choice((2, 3, 4))
        else:
            state = "REST"
            run = random.choice((1, 1, 2, 3))
        step += run
    return pattern


def _interlocking_pattern(
    total: int,
    density: float,
    syncopation: float,
    seed: int,
    boundaries: set[int],
    placed: list[list[int]],
    clock: CompositionClock,
) -> list[int]:
    pulses = max(1, min(total, round(total * density)))
    candidates: list[tuple[float, int]] = []
    random = Random(seed)
    for step in range(total):
        collision = sum(row[step] for row in placed)
        strength = _metrical_strength(step, clock)
        score = (
            collision * 2
            - (1 - collision) * 0.5
            - (syncopation * (1 - strength) + (1 - syncopation) * strength)
            - (0.5 if step in boundaries else 0)
            + random.random() * 1e-6
        )
        candidates.append((score, step))
    chosen = {step for _score, step in sorted(candidates)[:pulses]}
    return [1 if step in chosen else 0 for step in range(total)]


def _ratio_derived_pattern(
    total: int,
    chords: list[list[Fraction]],
    density: float,
    voice_index: int,
) -> list[int]:
    vocabulary = (5, 7, 8, 11, 13, 16)
    complexity = sum(_ratio_complexity(ratio) for chord in chords for ratio in chord)
    cardinality = round(sum(len(chord) for chord in chords) / len(chords))
    cycle = vocabulary[(complexity + cardinality + voice_index) % len(vocabulary)]
    pulses = max(1, min(cycle, round(cycle * density)))
    base = euclidean_rhythm(cycle, pulses, (complexity + voice_index) % cycle)
    return [base[step % cycle] for step in range(total)]


def _target_ratios(
    mapping: RhythmMapping,
    chord_index: int,
    chords: list[list[Fraction]],
    bass: list[Fraction],
    melody: list[list[Fraction]],
    prior: Fraction | None,
) -> list[Fraction]:
    register = Fraction(2) ** mapping.register_octave
    if mapping.target == "harmony":
        return [ratio * register for ratio in chords[chord_index]]
    if mapping.target == "bass":
        return [bass[chord_index] * register] if chord_index < len(bass) else []
    if mapping.target.startswith("melody:"):
        voice = _target_index(mapping.target)
        return (
            [melody[voice][chord_index] * register]
            if voice < len(melody) and chord_index < len(melody[voice])
            else []
        )
    if not mapping.target.startswith("chord_tone:"):
        raise ValueError(f"unknown mapping target: {mapping.target}")
    chord = chords[chord_index]
    index = _target_index(mapping.target)
    if mapping.policy == "rotate-per-chord":
        index += chord_index
    if index >= len(chord):
        if mapping.overflow == "drop":
            return []
        if mapping.overflow == "wrap":
            index %= len(chord)
        else:
            index = len(chord) - 1
    ratio = chord[index]
    if mapping.policy == "voice-led" and prior is not None:
        ratio = min(
            (
                tone * Fraction(2) ** octave
                for tone in chord
                for octave in range(mapping.register_octave - 4, mapping.register_octave + 5)
            ),
            key=lambda candidate: (
                abs(1200 * log2(float(candidate / prior))),
                candidate,
            ),
        )
        return [ratio]
    return [ratio * register]


def _resolve_collisions(
    events: list[tuple[RhythmicNoteEvent, str]],
) -> list[RhythmicNoteEvent]:
    resolved: list[RhythmicNoteEvent] = []
    merged: dict[tuple[str, int, Fraction], int] = {}
    for event, collision in events:
        key = (event.track_id, event.start_tick, event.ratio)
        if collision != "merge" or key not in merged:
            merged[key] = len(resolved)
            resolved.append(event)
            continue
        position = merged[key]
        previous = resolved[position]
        resolved[position] = RhythmicNoteEvent(
            previous.track_id,
            previous.chord_index,
            previous.ratio,
            previous.start_tick,
            max(previous.duration_ticks, event.duration_ticks),
            max(previous.velocity, event.velocity),
            previous.articulation,
            previous.source_layer,
        )
    return sorted(
        resolved,
        key=lambda event: (event.start_tick, event.track_id, event.ratio),
    )


def _event_metrics(
    events: list[RhythmicNoteEvent], clock: CompositionClock
) -> dict[str, object]:
    by_track: dict[str, int] = {}
    simultaneous: dict[int, int] = {}
    for event in events:
        by_track[event.track_id] = by_track.get(event.track_id, 0) + 1
        simultaneous[event.start_tick] = simultaneous.get(event.start_tick, 0) + 1
    active_subdivisions = {
        event.start_tick // clock.ticks_per_subdivision for event in events
    }
    return {
        "event_count": len(events),
        "events_by_track": by_track,
        "onset_density": len(active_subdivisions) / clock.total_subdivisions,
        "max_simultaneous_attacks": max(simultaneous.values(), default=0),
    }


def _validate_material(
    clock: CompositionClock,
    chords: list[list[Fraction]],
    bass: list[Fraction],
    melody: list[list[Fraction]],
    layers: list[RhythmLayer],
    mappings: list[RhythmMapping],
) -> None:
    if (
        clock.beats_per_bar < 1
        or clock.subdivisions_per_beat < 1
        or clock.bars < 1
        or clock.ticks_per_beat % clock.subdivisions_per_beat
        or clock.total_subdivisions > 4096
    ):
        raise ValueError("the composition clock is invalid")
    if not chords or any(not chord for chord in chords):
        raise ValueError("at least one non-empty chord is required")
    if bass and len(bass) != len(chords):
        raise ValueError("bass length must match the chord count")
    if any(len(voice) != len(chords) for voice in melody):
        raise ValueError("each melody voice must match the chord count")
    if not layers or len({layer.name for layer in layers}) != len(layers):
        raise ValueError("rhythm layer names must be unique")
    for layer in layers:
        if not layer.pattern or any(value not in {0, 1} for value in layer.pattern):
            raise ValueError("rhythm patterns must be non-empty and binary")
        if len(layer.velocities) != len(layer.pattern):
            raise ValueError("layer velocities must match the pattern length")
        if any(not 0 <= velocity <= 127 for velocity in layer.velocities):
            raise ValueError("layer velocities must be between 0 and 127")
    names = {layer.name for layer in layers}
    if not mappings or any(mapping.source_layer not in names for mapping in mappings):
        raise ValueError("every mapping must reference an existing rhythm layer")


def _chord_spans(
    clock: CompositionClock,
    chord_count: int,
    durations: list[int] | None,
) -> list[tuple[int, int]]:
    if durations is None:
        durations = _even_chord_durations(clock.total_subdivisions, chord_count)
    if len(durations) != chord_count or any(duration < 1 for duration in durations):
        raise ValueError("chord durations must contain one positive value per chord")
    if sum(durations) != clock.total_subdivisions:
        raise ValueError("chord durations must fill the complete composition clock")
    spans = []
    cursor = 0
    for duration in durations:
        start = cursor * clock.ticks_per_subdivision
        cursor += duration
        spans.append((start, cursor * clock.ticks_per_subdivision))
    return spans


def _even_chord_durations(total: int, count: int) -> list[int]:
    if count < 1 or total < count:
        raise ValueError("the clock needs at least one subdivision per chord")
    return [
        round((index + 1) * total / count) - round(index * total / count)
        for index in range(count)
    ]


def _chord_at_tick(spans: list[tuple[int, int]], tick: int) -> int:
    for index, (_start, end) in enumerate(spans):
        if tick < end:
            return index
    return len(spans) - 1


def _layer_hit(
    layer: RhythmLayer, subdivision: int, clock: CompositionClock
) -> tuple[bool, int]:
    bar = subdivision // clock.subdivisions_per_bar
    phase = layer.phase_offsets[bar % len(layer.phase_offsets)] if layer.phase_offsets else 0
    index = (subdivision - phase) % len(layer.pattern)
    return bool(layer.pattern[index]), layer.velocities[index] or 100


def _transition_motion(
    chords: list[list[Fraction]], scores: list[float | None] | None
) -> list[float]:
    motion = [0.0]
    for index in range(1, len(chords)):
        score = scores[index] if scores and index < len(scores) else None
        if score is not None:
            motion.append(abs(score))
        else:
            motion.append(abs(1200 * log2(float(chords[index][0] / chords[index - 1][0]))))
    return motion


def _metrical_strength(subdivision: int, clock: CompositionClock) -> float:
    within_bar = subdivision % clock.subdivisions_per_bar
    if within_bar == 0:
        return 1.0
    if within_bar % clock.subdivisions_per_beat == 0:
        return 0.7
    if within_bar % max(1, clock.subdivisions_per_beat // 2) == 0:
        return 0.4
    return 0.15


def _generated_velocity(
    step: int, active: int, target: str, clock: CompositionClock
) -> int:
    if not active:
        return 0
    base = 108 if target == "bass" else 96 if target == "harmony" else 88
    return min(127, base + round(18 * _metrical_strength(step, clock)))


def _role_density(profile: str, target: str, density: float) -> float:
    profile_scale = {
        "grounded": 0.85,
        "interlocking": 1.0,
        "sparse": 0.55,
        "flowing": 1.2,
    }[profile]
    role_scale = 0.55 if target == "harmony" else 0.75 if target == "bass" else 1.15
    return max(0.02, min(0.95, density * profile_scale * role_scale))


def _profile_gate(profile: str, target: str) -> float:
    if profile == "flowing":
        return 1.8
    if profile == "sparse":
        return 1.4
    return 0.85 if target == "harmony" else 0.7


def _role_velocity(target: str) -> float:
    return 1.1 if target == "bass" else 1.0 if target == "harmony" else 0.85


def _ratio_complexity(ratio: Fraction) -> int:
    numerator, denominator = ratio.numerator, ratio.denominator
    total = 0
    divisor = 2
    for value in (numerator, denominator):
        number = value
        while divisor * divisor <= number:
            while number % divisor == 0:
                total += 1
                number //= divisor
            divisor += 1
        if number > 1:
            total += 1
        divisor = 2
    return total


def _target_index(target: str) -> int:
    try:
        index = int(target.split(":", 1)[1])
    except (IndexError, ValueError) as error:
        raise ValueError(f"target needs a non-negative index: {target}") from error
    if index < 0:
        raise ValueError(f"target needs a non-negative index: {target}")
    return index


def _track_id(mapping: RhythmMapping) -> str:
    return f"{mapping.target}@{mapping.source_layer}"


def _ratio_text(ratio: Fraction) -> str:
    return f"{ratio.numerator}/{ratio.denominator}"
