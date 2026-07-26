from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from hashlib import sha256
from json import dumps
from math import log2
from random import Random
from statistics import mean
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from app.arrangement.chords import ratio_complexity
from app.arrangement.models import ArrangementProjectInput
from app.rhythm.engine import euclidean_rhythm
from app.tuning.ratios import parse_ratio, ratio_text

MAX_PHASE_ATTEMPTS = 8


class PhaseRhythmSpec(BaseModel):
    source: Literal[
        "existing", "euclidean", "semi_markov", "interlocking", "manual"
    ] = "euclidean"
    cycle_steps: int = Field(default=16, ge=2, le=128)
    pulses: int | None = Field(default=None, ge=1, le=128)
    pattern: list[int] | None = Field(default=None, min_length=2, max_length=128)
    rotation: int = Field(default=0, ge=-127, le=127)
    density: float = Field(default=0.4, ge=0.02, le=0.98)
    syncopation: float = Field(default=0.4, ge=0, le=1)
    gate: float = Field(default=0.8, gt=0, le=4)

    @model_validator(mode="after")
    def rhythm_source_must_have_material(self) -> PhaseRhythmSpec:
        if self.source == "manual":
            if self.pattern is None:
                raise ValueError("manual phase rhythm requires pattern")
            if any(value not in {0, 1} for value in self.pattern):
                raise ValueError("manual phase rhythm pattern must contain only 0 and 1")
            self.cycle_steps = len(self.pattern)
        if self.pulses is not None and self.pulses > self.cycle_steps:
            raise ValueError("phase rhythm pulses cannot exceed cycle_steps")
        return self


PhaseRole = Literal["harmony", "bass", "melody", "texture"]


def _default_phase_roles() -> list[PhaseRole]:
    return ["harmony"]


class PhaseStreamSpec(BaseModel):
    id: Literal["a", "b"]
    track_ids: list[str] = Field(default_factory=list, max_length=8)
    generated_roles: list[PhaseRole] = Field(
        default_factory=_default_phase_roles, min_length=1, max_length=4
    )
    rhythm: PhaseRhythmSpec = Field(default_factory=PhaseRhythmSpec)
    chord_durations: list[int] | None = Field(
        default=None, min_length=1, max_length=128
    )
    register_low_cents: float = Field(default=0, ge=-3600, le=9600)
    register_high_cents: float = Field(default=2400, ge=-2400, le=12_000)
    gain: float = Field(default=0.7, ge=0, le=2)
    pan: float = Field(default=0, ge=-1, le=1)

    @model_validator(mode="after")
    def register_must_be_ordered(self) -> PhaseStreamSpec:
        if self.register_low_cents >= self.register_high_cents:
            raise ValueError("phase stream register_low_cents must be below register_high_cents")
        if "harmony" not in self.generated_roles:
            raise ValueError("the initial phase implementation requires generated harmony")
        return self


class PhaseAnchor(BaseModel):
    bar: int = Field(ge=0, le=128)
    rhythm_offset: int | None = Field(default=0, ge=-127, le=127)
    chord_offset: int = Field(default=0, ge=0, le=127)
    tolerance_ticks: int = Field(default=0, ge=0, le=960)
    protected: bool = True


class PhasePlan(BaseModel):
    process: Literal[
        "static", "discrete", "polymetric", "convergent", "fractional"
    ] = "static"
    initial_offset_steps: int = Field(default=1, ge=-127, le=127)
    increment_steps: int = Field(default=1, ge=-32, le=32)
    update_interval_bars: int = Field(default=1, ge=1, le=32)
    direction: Literal["forward", "backward", "alternate"] = "forward"
    convergence_points: list[PhaseAnchor] = Field(default_factory=list, max_length=64)
    maximum_supercycle_bars: int = Field(default=64, ge=1, le=128)


class SourceProgressionSpec(BaseModel):
    scope: Literal["whole_form", "section", "selected_slots"] = "whole_form"
    section_ids: list[str] = Field(default_factory=list, max_length=32)
    selected_slots: list[int] = Field(default_factory=list, max_length=4096)
    repeat: bool = True

    @model_validator(mode="after")
    def selection_must_be_present(self) -> SourceProgressionSpec:
        if self.scope == "section" and not self.section_ids:
            raise ValueError("section phase scope requires section_ids")
        if self.scope == "selected_slots" and not self.selected_slots:
            raise ValueError("selected_slots phase scope requires selected_slots")
        return self


class OverlapPolicy(BaseModel):
    resolution: Literal["strict_full_chord", "adaptive_voicing"] = (
        "strict_full_chord"
    )
    maximum_combined_density: float = Field(default=0.9, gt=0, le=1)
    maximum_active_tones: int = Field(default=12, ge=2, le=24)
    maximum_overlap_cost: float = Field(default=12, gt=0, le=100)
    minimum_hamming_distance: float = Field(default=0.15, ge=0, le=1)


class HarmonicPhaseShiftRequest(BaseModel):
    arrangement: dict[str, Any]
    source_progression: SourceProgressionSpec = Field(
        default_factory=SourceProgressionSpec
    )
    mode: Literal["shared_chord_clock", "independent_chord_clock"] = (
        "shared_chord_clock"
    )
    stream_a: PhaseStreamSpec = Field(
        default_factory=lambda: PhaseStreamSpec(
            id="a",
            rhythm=PhaseRhythmSpec(
                source="euclidean", cycle_steps=16, pulses=4, rotation=0
            ),
            register_low_cents=0,
            register_high_cents=2400,
            gain=0.72,
            pan=-0.25,
        )
    )
    stream_b: PhaseStreamSpec = Field(
        default_factory=lambda: PhaseStreamSpec(
            id="b",
            rhythm=PhaseRhythmSpec(
                source="euclidean", cycle_steps=15, pulses=5, rotation=2
            ),
            register_low_cents=1200,
            register_high_cents=3600,
            gain=0.66,
            pan=0.25,
        )
    )
    phase_plan: PhasePlan = Field(default_factory=PhasePlan)
    overlap_policy: OverlapPolicy = Field(default_factory=OverlapPolicy)
    seed: int = 0

    @model_validator(mode="after")
    def streams_must_be_distinct(self) -> HarmonicPhaseShiftRequest:
        if self.stream_a.id != "a" or self.stream_b.id != "b":
            raise ValueError("phase streams must use ids 'a' and 'b'")
        return self


@dataclass(frozen=True)
class SourceSlot:
    source_index: int
    section_id: str
    chord_id: str
    start_subdivision: int
    duration_subdivisions: int
    tones: tuple[Fraction, ...]

    @property
    def end_subdivision(self) -> int:
        return self.start_subdivision + self.duration_subdivisions


@dataclass(frozen=True)
class Visit:
    source_position: int
    source_slot: SourceSlot
    start_subdivision: int
    duration_subdivisions: int
    visit_index: int
    phase_iteration: int

    @property
    def end_subdivision(self) -> int:
        return self.start_subdivision + self.duration_subdivisions


def generate_phase_shift(request: HarmonicPhaseShiftRequest) -> dict[str, Any]:
    """Compile two distinct harmonic rhythms into one validated arrangement."""
    if request.phase_plan.process == "fractional":
        raise ValueError(
            "fractional phase drift is an HP5 experiment and is not available "
            "for integer-tick MIDI projects"
        )
    source = ArrangementProjectInput.model_validate(request.arrangement)
    ticks_per_subdivision = (
        source.clock.ticks_per_beat // source.clock.subdivisions_per_beat
    )
    slots = _source_slots(
        request.arrangement,
        request.source_progression,
        ticks_per_subdivision,
    )
    if not slots:
        raise ValueError("phase source progression selection is empty")
    if slots[-1].end_subdivision > (
        source.clock.total_ticks // ticks_per_subdivision
    ):
        raise ValueError("phase source progression extends beyond the project clock")

    random_a = Random(request.seed ^ 0xA11)
    random_b = Random(request.seed ^ 0xB22)
    cycle_a = _rhythm_cycle(
        request.stream_a.rhythm,
        request.arrangement,
        ticks_per_subdivision,
        random_a,
        None,
    )
    cycle_b = _rhythm_cycle(
        request.stream_b.rhythm,
        request.arrangement,
        ticks_per_subdivision,
        random_b,
        cycle_a,
    )
    total_subdivisions = source.clock.total_ticks // ticks_per_subdivision
    protected = _protected_subdivisions(request.phase_plan, source)
    hits_a = _phase_hits(
        cycle_a,
        request.stream_a.rhythm.rotation,
        request.phase_plan,
        "a",
        total_subdivisions,
        source.clock.beats_per_bar * source.clock.subdivisions_per_beat,
        protected,
    )
    hits_b, distinctness = _distinct_moving_hits(
        cycle_a,
        cycle_b,
        hits_a,
        request,
        total_subdivisions,
        source.clock.beats_per_bar * source.clock.subdivisions_per_beat,
        protected,
    )
    selected_ranges = [
        (slot.start_subdivision, slot.end_subdivision) for slot in slots
    ]
    hits_a = {hit for hit in hits_a if _inside_ranges(hit, selected_ranges)}
    hits_b = {hit for hit in hits_b if _inside_ranges(hit, selected_ranges)}

    if request.mode == "independent_chord_clock":
        visits_a = _independent_visits(
            slots,
            request.stream_a,
            request.phase_plan,
            source,
        )
        visits_b = _independent_visits(
            slots,
            request.stream_b,
            request.phase_plan,
            source,
        )
    else:
        visits_a = _shared_visits(slots)
        visits_b = visits_a

    selected_span = sum(end - start for start, end in selected_ranges)
    union_density = len(hits_a | hits_b) / max(1, selected_span)
    combined_density = (len(hits_a) + len(hits_b)) / max(1, selected_span * 2)
    if combined_density > request.overlap_policy.maximum_combined_density:
        raise ValueError(
            "combined phase-stream onset density exceeds the overlap policy; "
            "reduce pulses or density"
        )

    overlap_windows = _overlap_windows(
        visits_a, visits_b, request.overlap_policy
    )
    maximum_cost = max((window["cost"] for window in overlap_windows), default=0.0)
    if (
        request.overlap_policy.resolution == "strict_full_chord"
        and maximum_cost > request.overlap_policy.maximum_overlap_cost
    ):
        raise ValueError(
            f"phase overlap cost {maximum_cost:.3f} exceeds strict limit "
            f"{request.overlap_policy.maximum_overlap_cost:.3f}"
        )

    source_events = [
        dict(event)
        for event in request.arrangement["events"]
        if event.get("track_id") != "harmony"
    ]
    phase_events_a, omitted_a = _stream_events(
        "a",
        hits_a,
        visits_a,
        visits_b,
        request.stream_a,
        request.overlap_policy,
        source,
        request.arrangement["form"],
        ticks_per_subdivision,
    )
    phase_events_b, omitted_b = _stream_events(
        "b",
        hits_b,
        visits_b,
        visits_a,
        request.stream_b,
        request.overlap_policy,
        source,
        request.arrangement["form"],
        ticks_per_subdivision,
    )
    events = sorted(
        [*source_events, *phase_events_a, *phase_events_b],
        key=lambda event: (
            event["start_tick"],
            event["track_id"],
            event["id"],
        ),
    )
    if len(events) > 8192:
        raise ValueError(
            f"phase arrangement compiles to {len(events)} events; limit is 8192"
        )
    tracks = _phase_tracks(
        request.arrangement["tracks"],
        phase_events_a,
        phase_events_b,
    )
    mix = {
        track_id: value
        for track_id, value in request.arrangement.get("mix", {}).items()
        if track_id != "harmony"
    }
    mix["phase-a-harmony"] = {
        "gain": request.stream_a.gain,
        "pan": request.stream_a.pan,
    }
    mix["phase-b-harmony"] = {
        "gain": request.stream_b.gain,
        "pan": request.stream_b.pan,
    }
    waveforms = {
        track_id: value
        for track_id, value in request.arrangement.get("render_settings", {})
        .get("waveforms", {})
        .items()
        if track_id != "harmony"
    }
    waveforms.update(
        {"phase-a-harmony": "triangle", "phase-b-harmony": "saw"}
    )
    phase_schedule = _phase_schedule(
        source, request.phase_plan, visits_a, visits_b
    )
    convergence = _convergence_results(
        request.phase_plan,
        source,
        hits_a,
        hits_b,
        visits_a,
        visits_b,
    )
    source_digest = sha256(
        dumps(request.arrangement, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    markers = [
        {
            "tick": anchor["tick"],
            "name": f"phase-convergence-{index + 1}",
        }
        for index, anchor in enumerate(convergence)
        if anchor["protected"]
    ]
    result = {
        "schema_version": "1.1.0",
        "metadata": {
            "generator": "pure-intonation-composer",
            "feature": "harmonic-phase-shift",
        },
        "source_arrangement_digest": source_digest,
        "source_scale": request.arrangement["source_scale"],
        "chord_vocabulary": request.arrangement.get("chord_vocabulary", []),
        "requested_profile": request.arrangement.get("requested_profile", "phase"),
        "resolved_profile": request.arrangement.get("resolved_profile", {}),
        "seed": request.seed,
        "form": request.arrangement["form"],
        "harmony_progression": request.arrangement["harmony_progression"],
        "harmony_gestures": [],
        "clock": request.arrangement["clock"],
        "tracks": tracks,
        "events": events,
        "automation": request.arrangement.get("automation", []),
        "mix": mix,
        "render_settings": {
            **request.arrangement.get("render_settings", {}),
            "waveforms": waveforms,
        },
        "markers": markers,
        "phase_shift": {
            "mode": request.mode,
            "source_progression": request.source_progression.model_dump(),
            "resolved_phase_profile": request.phase_plan.model_dump(),
            "streams": [
                request.stream_a.model_dump(),
                request.stream_b.model_dump(),
            ],
            "phase_schedule": phase_schedule,
            "convergence_points": convergence,
            "overlap_windows": overlap_windows,
            "metrics": {
                "rhythm_distinctness": distinctness,
                "combined_density": round(combined_density, 6),
                "onset_union_density": round(union_density, 6),
                "maximum_overlap_cost": round(maximum_cost, 6),
                "mean_overlap_cost": round(
                    mean(
                        [float(window["cost"]) for window in overlap_windows]
                    )
                    if overlap_windows
                    else 0,
                    6,
                ),
                "optional_tone_omissions": omitted_a + omitted_b,
                "alignment_points": sum(
                    1 for anchor in convergence if anchor["met"]
                ),
            },
        },
        "decision_trace": [
            {
                "stage": "phase-rhythm",
                "message": (
                    f"A cycle {len(cycle_a)}/{sum(cycle_a)} pulses; "
                    f"B cycle {len(cycle_b)}/{sum(cycle_b)} pulses"
                ),
            },
            {
                "stage": "phase-overlap",
                "message": (
                    f"{len(overlap_windows)} overlap windows; "
                    f"maximum cost {maximum_cost:.3f}"
                ),
            },
        ],
    }
    ArrangementProjectInput.model_validate(result)
    return result


def _source_slots(
    arrangement: dict[str, Any],
    selection: SourceProgressionSpec,
    ticks_per_subdivision: int,
) -> list[SourceSlot]:
    raw_slots = arrangement.get("harmony_progression")
    if not isinstance(raw_slots, list) or not raw_slots:
        raise ValueError("arrangement has no harmony_progression")
    slots = []
    for raw in raw_slots:
        try:
            index = int(raw["index"])
            section_id = str(raw["section_id"])
            start_tick = int(raw["start_tick"])
            duration_tick = int(raw["duration_ticks"])
            tones = tuple(parse_ratio(value) for value in raw["tones"])
            chord_id = str(raw["instance_id"])
        except (KeyError, TypeError, ValueError, ZeroDivisionError) as error:
            raise ValueError(f"invalid source harmony slot: {error}") from error
        if start_tick % ticks_per_subdivision or duration_tick % ticks_per_subdivision:
            raise ValueError("phase source harmony must align to clock subdivisions")
        slots.append(
            SourceSlot(
                source_index=index,
                section_id=section_id,
                chord_id=chord_id,
                start_subdivision=start_tick // ticks_per_subdivision,
                duration_subdivisions=duration_tick // ticks_per_subdivision,
                tones=tones,
            )
        )
    if selection.scope == "section":
        wanted = set(selection.section_ids)
        slots = [slot for slot in slots if slot.section_id in wanted]
    elif selection.scope == "selected_slots":
        wanted_indices = set(selection.selected_slots)
        slots = [slot for slot in slots if slot.source_index in wanted_indices]
    return sorted(slots, key=lambda slot: slot.start_subdivision)


def _rhythm_cycle(
    spec: PhaseRhythmSpec,
    arrangement: dict[str, Any],
    ticks_per_subdivision: int,
    random: Random,
    anchor_cycle: list[int] | None,
) -> list[int]:
    if spec.source == "manual":
        assert spec.pattern is not None
        return list(spec.pattern)
    if spec.source == "existing":
        cycle = [0] * spec.cycle_steps
        for event in arrangement.get("events", []):
            if event.get("track_id") == "harmony":
                step = int(event["start_tick"]) // ticks_per_subdivision
                cycle[step % spec.cycle_steps] = 1
        if any(cycle):
            return cycle
    if spec.source == "interlocking" and anchor_cycle is not None:
        cycle = [
            0 if anchor_cycle[index % len(anchor_cycle)] else 1
            for index in range(spec.cycle_steps)
        ]
        target = spec.pulses or max(1, round(spec.cycle_steps * spec.density))
        active = [index for index, value in enumerate(cycle) if value]
        while len(active) > target:
            cycle[active.pop(random.randrange(len(active)))] = 0
        return cycle
    pulses = spec.pulses or max(1, round(spec.cycle_steps * spec.density))
    if spec.source == "semi_markov":
        cycle = [0] * spec.cycle_steps
        rest = 0
        for index in range(spec.cycle_steps):
            metrical = 0.25 if index % 4 == 0 else 0
            probability = min(0.95, spec.density + metrical + rest * 0.08)
            if random.random() < probability:
                cycle[index] = 1
                rest = 0
            else:
                rest += 1
        if not any(cycle):
            cycle[0] = 1
        return cycle
    return euclidean_rhythm(spec.cycle_steps, pulses, 0)


def _phase_hits(
    cycle: list[int],
    rotation: int,
    plan: PhasePlan,
    stream_id: str,
    total_subdivisions: int,
    subdivisions_per_bar: int,
    protected: set[int],
) -> set[int]:
    hits = set()
    for subdivision in range(total_subdivisions):
        offset = 0 if stream_id == "a" else _phase_offset(
            plan, subdivision, subdivisions_per_bar
        )
        index = (subdivision - rotation - offset) % len(cycle)
        if cycle[index]:
            hits.add(subdivision)
    hits.update(protected)
    return hits


def _phase_offset(
    plan: PhasePlan, subdivision: int, subdivisions_per_bar: int
) -> int:
    if plan.process in {"static", "polymetric"}:
        return plan.initial_offset_steps
    bar = subdivision // subdivisions_per_bar
    updates = bar // plan.update_interval_bars
    direction = -1 if plan.direction == "backward" else 1
    if plan.direction == "alternate" and updates % 2:
        direction = -1
    offset = plan.initial_offset_steps + direction * updates * plan.increment_steps
    if plan.process == "convergent":
        anchors = sorted(
            anchor.bar for anchor in plan.convergence_points if anchor.protected
        )
        if anchors:
            next_anchor = next((anchor for anchor in anchors if anchor >= bar), None)
            if next_anchor is not None:
                distance = next_anchor - bar
                if distance <= plan.update_interval_bars:
                    return round(offset * distance / plan.update_interval_bars)
    return offset


def _distinct_moving_hits(
    cycle_a: list[int],
    cycle_b: list[int],
    hits_a: set[int],
    request: HarmonicPhaseShiftRequest,
    total_subdivisions: int,
    subdivisions_per_bar: int,
    protected: set[int],
) -> tuple[set[int], dict[str, float]]:
    best_hits: set[int] = set()
    best_metrics: dict[str, float] = {}
    for attempt in range(MAX_PHASE_ATTEMPTS):
        rotation = request.stream_b.rhythm.rotation + attempt
        hits_b = _phase_hits(
            cycle_b,
            rotation,
            request.phase_plan,
            "b",
            total_subdivisions,
            subdivisions_per_bar,
            protected,
        )
        metrics = _rhythm_distinctness(hits_a, hits_b, total_subdivisions)
        best_hits, best_metrics = hits_b, metrics
        if metrics["onset_hamming_distance"] >= (
            request.overlap_policy.minimum_hamming_distance
        ):
            break
    else:
        raise ValueError(
            "phase rhythms are too similar after bounded regeneration; "
            "change cycle length, pulses, or rotation"
        )
    return best_hits, best_metrics


def _rhythm_distinctness(
    hits_a: set[int], hits_b: set[int], window: int
) -> dict[str, float]:
    intersection = len(hits_a & hits_b)
    union = len(hits_a | hits_b)
    xor = len(hits_a ^ hits_b)
    ioi_a = _mean_ioi(hits_a)
    ioi_b = _mean_ioi(hits_b)
    return {
        "onset_hamming_distance": round(xor / max(1, window), 6),
        "onset_overlap_ratio": round(intersection / max(1, union), 6),
        "complement_ratio": round(xor / max(1, union), 6),
        "density_difference": round(
            abs(len(hits_a) - len(hits_b)) / max(1, window), 6
        ),
        "inter_onset_interval_distance": round(abs(ioi_a - ioi_b), 6),
    }


def _mean_ioi(hits: set[int]) -> float:
    ordered = sorted(hits)
    if len(ordered) < 2:
        return 0.0
    return mean(
        ordered[index] - ordered[index - 1]
        for index in range(1, len(ordered))
    )


def _protected_subdivisions(
    plan: PhasePlan, source: ArrangementProjectInput
) -> set[int]:
    subdivisions_per_bar = (
        source.clock.beats_per_bar * source.clock.subdivisions_per_beat
    )
    protected = {0}
    for anchor in plan.convergence_points:
        if anchor.protected and anchor.bar <= source.clock.bars:
            protected.add(anchor.bar * subdivisions_per_bar)
    protected.discard(
        source.clock.bars * subdivisions_per_bar
    )
    return protected


def _shared_visits(slots: list[SourceSlot]) -> list[Visit]:
    return [
        Visit(
            source_position=position,
            source_slot=slot,
            start_subdivision=slot.start_subdivision,
            duration_subdivisions=slot.duration_subdivisions,
            visit_index=position,
            phase_iteration=0,
        )
        for position, slot in enumerate(slots)
    ]


def _independent_visits(
    slots: list[SourceSlot],
    stream: PhaseStreamSpec,
    plan: PhasePlan,
    source: ArrangementProjectInput,
) -> list[Visit]:
    subdivisions_per_bar = (
        source.clock.beats_per_bar * source.clock.subdivisions_per_beat
    )
    start = slots[0].start_subdivision
    end = slots[-1].end_subdivision
    anchors = {
        anchor.bar * subdivisions_per_bar
        for anchor in plan.convergence_points
        if anchor.protected and start < anchor.bar * subdivisions_per_bar < end
    }
    boundaries = [start, *sorted(anchors), end]
    base_weights = stream.chord_durations or [
        slot.duration_subdivisions for slot in slots
    ]
    weights = [
        max(1, base_weights[index % len(base_weights)])
        for index in range(len(slots))
    ]
    visits = []
    visit_index = 0
    for segment_start, segment_end in zip(boundaries, boundaries[1:]):
        span = segment_end - segment_start
        cycles = max(1, round(span / max(1, sum(weights))))
        while cycles * len(slots) > span and cycles > 1:
            cycles -= 1
        durations = _allocate_weighted(span, weights * cycles)
        cursor = segment_start
        for local_index, duration in enumerate(durations):
            position = local_index % len(slots)
            visits.append(
                Visit(
                    source_position=position,
                    source_slot=slots[position],
                    start_subdivision=cursor,
                    duration_subdivisions=duration,
                    visit_index=visit_index,
                    phase_iteration=local_index // len(slots),
                )
            )
            cursor += duration
            visit_index += 1
    return visits


def _allocate_weighted(total: int, weights: list[int]) -> list[int]:
    if total < len(weights):
        raise ValueError(
            "convergence segment is too short to preserve the source chord order"
        )
    remaining = total - len(weights)
    weight_sum = sum(weights)
    raw = [remaining * weight / weight_sum for weight in weights]
    result = [1 + int(value) for value in raw]
    remainder = total - sum(result)
    ranking = sorted(
        range(len(weights)),
        key=lambda index: (raw[index] - int(raw[index]), -index),
        reverse=True,
    )
    for index in ranking[:remainder]:
        result[index] += 1
    return result


def _stream_events(
    stream_id: str,
    hits: set[int],
    visits: list[Visit],
    other_visits: list[Visit],
    stream: PhaseStreamSpec,
    policy: OverlapPolicy,
    source: ArrangementProjectInput,
    form: list[dict[str, Any]],
    ticks_per_subdivision: int,
) -> tuple[list[dict[str, Any]], int]:
    events = []
    omissions = 0
    event_index = 0
    for subdivision in sorted(hits):
        visit = _visit_at(visits, subdivision)
        if visit is None:
            continue
        tones = list(visit.source_slot.tones)
        other = _visit_at(other_visits, subdivision)
        if (
            stream_id == "b"
            and other is not None
            and policy.resolution == "adaptive_voicing"
        ):
            allowed = max(1, policy.maximum_active_tones - len(other.source_slot.tones))
            if len(tones) > allowed:
                omissions += len(tones) - allowed
                tones = tones[:allowed]
        duration = max(
            1,
            min(
                round(stream.rhythm.gate * ticks_per_subdivision),
                (visit.end_subdivision - subdivision) * ticks_per_subdivision,
                source.clock.total_ticks - subdivision * ticks_per_subdivision,
            ),
        )
        section_id = _section_at_tick(
            form, subdivision * ticks_per_subdivision, source.clock
        )
        for tone in tones:
            event_index += 1
            placed = _place_in_cents_register(
                tone,
                stream.register_low_cents,
                stream.register_high_cents,
            )
            events.append(
                {
                    "id": f"phase-{stream_id}-{event_index:05d}",
                    "track_id": f"phase-{stream_id}-harmony",
                    "kind": "note",
                    "ratio": ratio_text(placed),
                    "drum_note": None,
                    "start_tick": subdivision * ticks_per_subdivision,
                    "duration_ticks": duration,
                    "velocity": 94 if stream_id == "a" else 84,
                    "articulation": "gate",
                    "chord_index": visit.source_slot.source_index,
                    "section_id": section_id,
                    "source_gesture_id": None,
                    "gesture_component": "tone",
                    "phase_stream_id": stream_id,
                    "source_slot_index": visit.source_slot.source_index,
                    "source_chord_id": visit.source_slot.chord_id,
                    "visit_index": visit.visit_index,
                    "phase_iteration": visit.phase_iteration,
                }
            )
    return events, omissions


def _place_in_cents_register(
    pitch_class: Fraction, low_cents: float, high_cents: float
) -> Fraction:
    candidates = [pitch_class * Fraction(2) ** octave for octave in range(-6, 9)]
    in_range = [
        candidate
        for candidate in candidates
        if low_cents <= 1200 * log2(float(candidate)) <= high_cents
    ]
    if not in_range:
        raise ValueError(
            f"phase pitch {ratio_text(pitch_class)} cannot fit stream register "
            f"{low_cents}..{high_cents} cents"
        )
    center = (low_cents + high_cents) / 2
    return min(
        in_range,
        key=lambda candidate: abs(1200 * log2(float(candidate)) - center),
    )


def _phase_tracks(
    source_tracks: list[dict[str, Any]],
    events_a: list[dict[str, Any]],
    events_b: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    tracks = [dict(track) for track in source_tracks if track.get("id") != "harmony"]
    tracks.extend(
        [
            {
                "id": "phase-a-harmony",
                "role": "harmony",
                "instrument": "phase anchor harmony",
                "register": [1.0, 4.0],
                "waveform": "triangle",
                "gain": 0.72,
                "event_count": len(events_a),
            },
            {
                "id": "phase-b-harmony",
                "role": "harmony",
                "instrument": "phase moving harmony",
                "register": [1.0, 8.0],
                "waveform": "saw",
                "gain": 0.66,
                "event_count": len(events_b),
            },
        ]
    )
    return tracks


def _overlap_windows(
    visits_a: list[Visit],
    visits_b: list[Visit],
    policy: OverlapPolicy,
) -> list[dict[str, Any]]:
    boundaries = sorted(
        {
            boundary
            for visit in [*visits_a, *visits_b]
            for boundary in (visit.start_subdivision, visit.end_subdivision)
        }
    )
    windows = []
    for start, end in zip(boundaries, boundaries[1:]):
        if end <= start:
            continue
        visit_a = _visit_at(visits_a, start)
        visit_b = _visit_at(visits_b, start)
        if visit_a is None or visit_b is None:
            continue
        tones_a = set(visit_a.source_slot.tones)
        tones_b = set(visit_b.source_slot.tones)
        common = len(tones_a & tones_b)
        combined = tones_a | tones_b
        pair_tension = mean(
            1
            - 1
            / (
                1
                + ratio_complexity(
                    _octave_reduce(tone_b / tone_a)
                )
            )
            for tone_a in tones_a
            for tone_b in tones_b
        )
        excess = max(0, len(combined) - policy.maximum_active_tones)
        cost = pair_tension + excess * 0.5 - common * 0.15
        windows.append(
            {
                "start_subdivision": start,
                "duration_subdivisions": end - start,
                "stream_a_slot": visit_a.source_slot.source_index,
                "stream_b_slot": visit_b.source_slot.source_index,
                "common_tones": common,
                "active_tones": len(combined),
                "cost": round(cost, 6),
            }
        )
    return windows


def _octave_reduce(ratio: Fraction) -> Fraction:
    while ratio < 1:
        ratio *= 2
    while ratio >= 2:
        ratio /= 2
    return ratio


def _phase_schedule(
    source: ArrangementProjectInput,
    plan: PhasePlan,
    visits_a: list[Visit],
    visits_b: list[Visit],
) -> list[dict[str, int]]:
    subdivisions_per_bar = (
        source.clock.beats_per_bar * source.clock.subdivisions_per_beat
    )
    schedule = []
    for bar in range(source.clock.bars):
        subdivision = bar * subdivisions_per_bar
        visit_a = _visit_at(visits_a, subdivision)
        visit_b = _visit_at(visits_b, subdivision)
        chord_offset = 0
        if visit_a is not None and visit_b is not None:
            chord_offset = (
                visit_b.source_position - visit_a.source_position
            ) % max(1, len({visit.source_position for visit in visits_a}))
        schedule.append(
            {
                "bar": bar,
                "rhythm_offset": _phase_offset(
                    plan, subdivision, subdivisions_per_bar
                ),
                "chord_offset": chord_offset,
            }
        )
    return schedule


def _convergence_results(
    plan: PhasePlan,
    source: ArrangementProjectInput,
    hits_a: set[int],
    hits_b: set[int],
    visits_a: list[Visit],
    visits_b: list[Visit],
) -> list[dict[str, Any]]:
    subdivisions_per_bar = (
        source.clock.beats_per_bar * source.clock.subdivisions_per_beat
    )
    anchors = list(plan.convergence_points)
    if not anchors:
        anchors = [
            PhaseAnchor(bar=0, protected=True),
            PhaseAnchor(bar=source.clock.bars, protected=True),
        ]
    results = []
    for anchor in anchors:
        subdivision = min(
            anchor.bar * subdivisions_per_bar,
            source.clock.total_ticks
            // (source.clock.ticks_per_beat // source.clock.subdivisions_per_beat),
        )
        visit_a = _visit_at(visits_a, max(0, subdivision - 1))
        visit_b = _visit_at(visits_b, max(0, subdivision - 1))
        chord_offset = 0
        if visit_a is not None and visit_b is not None:
            chord_offset = visit_b.source_position - visit_a.source_position
        rhythmic_met = (
            subdivision in hits_a and subdivision in hits_b
            if subdivision
            < source.clock.total_ticks
            // (source.clock.ticks_per_beat // source.clock.subdivisions_per_beat)
            else True
        )
        results.append(
            {
                "bar": anchor.bar,
                "tick": anchor.bar
                * source.clock.beats_per_bar
                * source.clock.ticks_per_beat,
                "requested_rhythm_offset": anchor.rhythm_offset,
                "requested_chord_offset": anchor.chord_offset,
                "actual_chord_offset": chord_offset,
                "protected": anchor.protected,
                "met": rhythmic_met and chord_offset == anchor.chord_offset,
            }
        )
    return results


def _visit_at(visits: list[Visit], subdivision: int) -> Visit | None:
    return next(
        (
            visit
            for visit in visits
            if visit.start_subdivision <= subdivision < visit.end_subdivision
        ),
        None,
    )


def _inside_ranges(value: int, ranges: list[tuple[int, int]]) -> bool:
    return any(start <= value < end for start, end in ranges)


def _section_at_tick(
    form: list[dict[str, Any]],
    tick: int,
    clock: Any,
) -> str:
    ticks_per_bar = clock.beats_per_bar * clock.ticks_per_beat
    bar = tick // ticks_per_bar
    for section in form:
        if section["start_bar"] <= bar < section["start_bar"] + section["bars"]:
            return str(section["id"])
    return str(form[-1]["id"])
