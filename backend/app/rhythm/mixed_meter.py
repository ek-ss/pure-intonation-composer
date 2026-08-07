from __future__ import annotations

from collections import defaultdict
from io import BytesIO
from math import exp, pi, sin
from random import Random
from struct import pack
from typing import Any, Literal
from wave import open as wave_open

from pydantic import BaseModel, Field, field_validator, model_validator


DrumRole = Literal["kick", "snare", "closed_hat", "open_hat", "percussion", "tom_fill", "crash"]


ROLE_NOTES: dict[DrumRole, int] = {
    "kick": 36,
    "snare": 38,
    "closed_hat": 42,
    "open_hat": 46,
    "percussion": 39,
    "tom_fill": 45,
    "crash": 49,
}


PATTERNS: dict[str, dict[str, Any]] = {
    "MM_3_5": {"name": "Short-Long", "meters": [3, 5], "groupings": [[3], [2, 3]], "tags": ["short", "resolution"]},
    "MM_5_3": {"name": "Long-Short", "meters": [5, 3], "groupings": [[3, 2], [3]], "tags": ["recovery"]},
    "MM_3535": {"name": "Alternating 16", "meters": [3, 5, 3, 5], "groupings": [[3], [2, 3], [3], [3, 2]], "tags": ["standard"]},
    "MM_3553": {"name": "Symmetric 16", "meters": [3, 5, 5, 3], "groupings": [[3], [2, 3], [3, 2], [3]], "tags": ["symmetric"]},
    "MM_3733": {"name": "Phase Walk 16", "meters": [3, 7, 3, 3], "groupings": [[3], [2, 2, 3], [3], [3]], "tags": ["phase-walk"]},
    "MM_745": {"name": "Held Offset 16", "meters": [7, 4, 5], "groupings": [[2, 2, 3], [2, 2], [3, 2]], "tags": ["held-offset"]},
    "MM_3575": {"name": "Prime Expansion 20", "meters": [3, 5, 7, 5], "groupings": [[3], [2, 3], [2, 2, 3], [3, 2]], "tags": ["prime", "expansion"]},
    "MM_3737": {"name": "Prime Phase Walk 20", "meters": [3, 7, 3, 7], "groupings": [[3], [2, 2, 3], [3], [3, 2, 2]], "tags": ["prime", "phase-walk"]},
    "MM_5775": {"name": "Symmetric 24", "meters": [5, 7, 7, 5], "groupings": [[2, 3], [2, 2, 3], [3, 2, 2], [3, 2]], "tags": ["long", "symmetric"]},
    "MM_4_4": {"name": "Stable 4/4", "meters": [4, 4, 4, 4], "groupings": [[2, 2]] * 4, "tags": ["stable"]},
}


DENSITY_PROFILES: dict[str, dict[str, tuple[float, float]]] = {
    "manual": {role: (0.45, 0.0) for role in ROLE_NOTES},
    "build_up": {
        "kick": (0.35, 0.15), "snare": (0.25, 0.20), "closed_hat": (0.50, 0.35),
        "open_hat": (0.05, 0.20), "percussion": (0.20, 0.45), "tom_fill": (0.0, 0.55), "crash": (0.02, 0.10),
    },
    "skeletal_tension": {
        "kick": (0.45, -0.10), "snare": (0.30, -0.05), "closed_hat": (0.65, -0.30),
        "open_hat": (0.10, -0.05), "percussion": (0.35, -0.25), "tom_fill": (0.0, 0.30), "crash": (0.02, 0.08),
    },
    "chorus_impact": {
        "kick": (0.30, 0.18), "snare": (0.24, 0.18), "closed_hat": (0.42, 0.38),
        "open_hat": (0.04, 0.24), "percussion": (0.14, 0.46), "tom_fill": (0.0, 0.62), "crash": (0.02, 0.12),
    },
}


class MixedMeterPattern(BaseModel):
    id: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=120)
    denominator: Literal[4, 8] = 4
    meters: list[int] = Field(min_length=1, max_length=16)
    groupings: list[list[int]] = Field(min_length=1, max_length=16)
    tags: list[str] = Field(default_factory=list, max_length=12)
    description: str | None = Field(default=None, max_length=500)

    @field_validator("meters")
    @classmethod
    def meters_are_supported(cls, values: list[int]) -> list[int]:
        if any(value < 2 or value > 13 for value in values):
            raise ValueError("meter lengths must be between 2 and 13")
        if sum(values) > 64:
            raise ValueError("mixed-meter cycle cannot exceed 64 beats")
        return values

    @model_validator(mode="after")
    def groupings_match(self) -> MixedMeterPattern:
        if len(self.meters) != len(self.groupings):
            raise ValueError("each meter requires one grouping")
        for meter, grouping in zip(self.meters, self.groupings, strict=True):
            if not grouping or any(value <= 0 for value in grouping) or sum(grouping) != meter:
                raise ValueError(f"grouping {grouping} does not sum to meter {meter}")
        return self


class MixedMeterValidateRequest(BaseModel):
    pattern: MixedMeterPattern
    allow_unaligned: bool = False


class DrumTrackConfig(BaseModel):
    id: str
    role: DrumRole
    midi_note: int = Field(ge=0, le=127)
    density_mode: Literal["manual", "section", "tension_linked", "hybrid"] = "hybrid"
    base_density: float = Field(default=0.45, ge=0, le=1)
    min_density: float = Field(default=0, ge=0, le=1)
    max_density: float = Field(default=1, ge=0, le=1)
    tension_response: float = Field(default=0, ge=-1, le=1)
    structural_clarity: float = Field(default=0.7, ge=0, le=1)
    syncopation: float = Field(default=0.2, ge=0, le=1)
    variation: float = Field(default=0.25, ge=0, le=1)
    velocity_range: tuple[int, int] = (58, 108)
    muted: bool = False
    solo: bool = False
    locked: bool = False

    @model_validator(mode="after")
    def ranges_are_ordered(self) -> DrumTrackConfig:
        if self.min_density > self.max_density:
            raise ValueError("minimum density cannot exceed maximum density")
        if self.velocity_range[0] < 1 or self.velocity_range[1] > 127 or self.velocity_range[0] > self.velocity_range[1]:
            raise ValueError("velocity range is invalid")
        return self


class RhythmFormSection(BaseModel):
    id: str
    role: Literal["stable", "tension", "pre_resolution", "resolved"]
    pattern_id: str | None = None
    inline_pattern: MixedMeterPattern | None = None
    repeats: int = Field(default=1, ge=1, le=16)
    tension_mode: Literal["manual", "auto", "blend"] = "blend"
    tension_curve: list[float] = Field(default_factory=list, max_length=32)
    density_profile_id: str | None = None

    @field_validator("tension_curve")
    @classmethod
    def tension_values_are_normalized(cls, values: list[float]) -> list[float]:
        if any(value < 0 or value > 1 for value in values):
            raise ValueError("tension values must be between zero and one")
        return values


class MixedMeterGenerateRequest(BaseModel):
    pattern_id: str = "MM_3575"
    custom_pattern: MixedMeterPattern | None = None
    form: Literal["direct_resolution", "two_stage_resolution", "custom"] = "two_stage_resolution"
    sections: list[RhythmFormSection] = Field(default_factory=list, max_length=16)
    tension_repeats: int = Field(default=2, ge=1, le=8)
    stable_repeats: int = Field(default=1, ge=1, le=8)
    resolved_repeats: int = Field(default=1, ge=1, le=8)
    density_profile: Literal["manual", "build_up", "skeletal_tension", "chorus_impact"] = "chorus_impact"
    tracks: list[DrumTrackConfig] = Field(default_factory=list, max_length=7)
    tempo_bpm: float = Field(default=120, ge=40, le=260)
    subdivision: Literal[1, 2, 4] = 2
    ppq: int = Field(default=480, ge=96, le=960)
    variation: float = Field(default=0.25, ge=0, le=1)
    syncopation: float = Field(default=0.2, ge=0, le=1)
    humanize: float = Field(default=0.1, ge=0, le=1)
    seed: int = 3575
    allow_unaligned: bool = False
    locked_events: list[dict[str, Any]] = Field(default_factory=list, max_length=2000)


class MixedMeterExportRequest(BaseModel):
    project: dict[str, Any]
    humanized_positions: bool = True


def _pattern_payload(pattern: MixedMeterPattern) -> dict[str, Any]:
    unit = 4 / pattern.denominator
    total = sum(pattern.meters) * unit
    phase: list[float] = [0]
    cursor = 0.0
    for meter in pattern.meters:
        cursor += meter * unit
        phase.append(round(cursor % 4, 4))
    return pattern.model_dump() | {
        "total_beats": total,
        "alignment_modulo": round(total % 4, 4),
        "phase_path": phase,
        "four_four_equivalent_bars": total / 4,
    }


def pattern_library() -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "patterns": [
            _pattern_payload(MixedMeterPattern(id=key, **value))
            for key, value in PATTERNS.items()
            if key != "MM_4_4"
        ],
        "density_profiles": DENSITY_PROFILES,
        "track_defaults": [item.model_dump() for item in _default_tracks("chorus_impact")],
    }


def validate_pattern(request: MixedMeterValidateRequest | dict[str, Any]) -> dict[str, Any]:
    if not isinstance(request, MixedMeterValidateRequest):
        request = MixedMeterValidateRequest.model_validate(request)
    payload = _pattern_payload(request.pattern)
    aligned = abs(float(payload["alignment_modulo"])) < 1e-6
    if not aligned and not request.allow_unaligned:
        raise ValueError("cycle total must align to the four-beat grid; enable Advanced unaligned mode to continue")
    return {"valid": True, "aligned": aligned, "pattern": payload, "warnings": [] if aligned else ["Cycle does not realign to the four-beat grid"]}


def _default_tracks(profile: str) -> list[DrumTrackConfig]:
    result = []
    for role, note in ROLE_NOTES.items():
        base, response = DENSITY_PROFILES[profile][role]
        result.append(DrumTrackConfig(id=f"track-{role}", role=role, midi_note=note, base_density=base, tension_response=response))
    return result


def _resolve_pattern(pattern_id: str | None, inline: MixedMeterPattern | None = None) -> MixedMeterPattern:
    if inline is not None:
        return inline
    value = PATTERNS.get(pattern_id or "")
    if value is None:
        raise ValueError(f"unknown mixed-meter pattern: {pattern_id}")
    return MixedMeterPattern(id=str(pattern_id), **value)


def _form_sections(request: MixedMeterGenerateRequest) -> list[RhythmFormSection]:
    if request.form == "custom":
        if not request.sections:
            raise ValueError("custom form requires sections")
        return request.sections
    sections = [RhythmFormSection(id="stable", role="stable", pattern_id="MM_4_4", repeats=request.stable_repeats, tension_curve=[0.15])]
    sections.append(RhythmFormSection(id="tension", role="tension", pattern_id=request.pattern_id, inline_pattern=request.custom_pattern, repeats=request.tension_repeats, tension_curve=[0.50, 0.85]))
    if request.form == "two_stage_resolution":
        sections.append(RhythmFormSection(id="pre-resolution", role="pre_resolution", pattern_id="MM_3_5", repeats=1, tension_curve=[0.55, 0.35]))
    sections.append(RhythmFormSection(id="resolved", role="resolved", pattern_id="MM_4_4", repeats=request.resolved_repeats, tension_curve=[0.15]))
    return sections


def _interpolate(values: list[float], position: float, fallback: float) -> float:
    if not values:
        return fallback
    if len(values) == 1:
        return values[0]
    scaled = max(0.0, min(1.0, position)) * (len(values) - 1)
    left = int(scaled)
    right = min(len(values) - 1, left + 1)
    blend = scaled - left
    return values[left] * (1 - blend) + values[right] * blend


def _automatic_tension(meter: int, phase: int, previous: int, progress: float) -> float:
    phase_displacement = min(phase, 4 - phase) / 2
    deviation = min(abs(meter - 4) / 4, 1)
    change = min(abs(meter - previous) / 4, 1)
    return max(0.0, min(1.0, 0.45 * phase_displacement + 0.30 * deviation + 0.15 * change + 0.10 * progress))


def generate(request: MixedMeterGenerateRequest | dict[str, Any]) -> dict[str, Any]:
    if not isinstance(request, MixedMeterGenerateRequest):
        request = MixedMeterGenerateRequest.model_validate(request)
    tracks = request.tracks or _default_tracks(request.density_profile)
    solo = {track.role for track in tracks if track.solo}
    sections = _form_sections(request)
    timeline_sections: list[dict[str, Any]] = []
    bars: list[dict[str, Any]] = []
    cursor = 0.0
    bar_index = 0
    for section_index, section in enumerate(sections):
        pattern = _resolve_pattern(section.pattern_id, section.inline_pattern)
        validation = validate_pattern({"pattern": pattern.model_dump(), "allow_unaligned": request.allow_unaligned})
        section_start = cursor
        section_bar_indices: list[int] = []
        for cycle in range(section.repeats):
            cycle_start = cursor
            previous = 4
            phase = 0
            unit = 4 / pattern.denominator
            total_pattern_bars = len(pattern.meters) * section.repeats
            for local_index, (meter, grouping) in enumerate(zip(pattern.meters, pattern.groupings, strict=True)):
                progress = (cycle * len(pattern.meters) + local_index) / max(1, total_pattern_bars - 1)
                phase = int(cursor) % 4
                automatic = _automatic_tension(meter, phase, previous, progress)
                manual = _interpolate(section.tension_curve, progress, 0.5)
                tension = automatic if section.tension_mode == "auto" else manual if section.tension_mode == "manual" else (automatic + manual) / 2
                group_boundaries = [cursor]
                group_cursor = cursor
                for group in grouping:
                    group_cursor += group * unit
                    group_boundaries.append(group_cursor)
                bars.append({
                    "index": bar_index, "section_id": section.id, "section_role": section.role,
                    "cycle_index": cycle, "meter": meter, "denominator": pattern.denominator,
                    "start_beat": cursor, "end_beat": cursor + meter * unit, "grouping": grouping,
                    "group_boundaries": group_boundaries, "phase": phase,
                    "phase_after": int(cursor + meter * unit) % 4, "tension": round(tension, 4),
                    "macro_start": local_index == 0, "cycle_start_beat": cycle_start,
                })
                section_bar_indices.append(bar_index)
                cursor += meter * unit
                bar_index += 1
                previous = meter
        timeline_sections.append({
            "id": section.id, "role": section.role, "start_beat": section_start,
            "end_beat": cursor, "repeats": section.repeats,
            "pattern": validation["pattern"], "bar_indices": section_bar_indices,
        })
    events: list[dict[str, Any]] = []
    density_report: list[dict[str, Any]] = []
    locked = list(request.locked_events)
    for track in tracks:
        if track.muted or (solo and track.role not in solo):
            continue
        for timeline_section in timeline_sections:
            section_bars = [bar for bar in bars if bar["section_id"] == timeline_section["id"]]
            candidates = _candidates(track, section_bars, request.subdivision, request.syncopation)
            mandatory = {candidate["position"] for candidate in candidates if candidate["mandatory"]}
            tension = sum(float(bar["tension"]) for bar in section_bars) / max(1, len(section_bars))
            density = _density(track, request.density_profile, str(timeline_section["role"]), tension)
            optional = [candidate for candidate in candidates if candidate["position"] not in mandatory]
            target = round(density * len(optional))
            random = Random(f"{request.seed}:{track.role}:{timeline_section['id']}")
            selected = set(mandatory)
            if target > 0:
                chosen = _weighted_sample(random, optional, min(target, len(optional)), track.variation * request.variation)
                selected.update(candidate["position"] for candidate in chosen)
            section_events = []
            for candidate in candidates:
                if candidate["position"] not in selected:
                    continue
                velocity = round(track.velocity_range[0] + candidate["weight"] * (track.velocity_range[1] - track.velocity_range[0]))
                offset = 0.0 if candidate["structural_role"] in {"macro", "bar"} else (random.random() * 2 - 1) * 12 * request.humanize
                event = {
                    "track_id": track.id, "role": track.role, "section_id": timeline_section["id"],
                    "cycle_index": candidate["cycle_index"], "bar_index": candidate["bar_index"],
                    "pulse_position": round(candidate["position"], 4),
                    "tick": round(candidate["position"] * request.ppq),
                    "duration_ticks": max(1, request.ppq // 8), "midi_note": track.midi_note,
                    "velocity": max(1, min(127, velocity)), "timing_offset_ms": round(offset, 3),
                    "structural_role": candidate["structural_role"], "locked": track.locked or candidate["mandatory"],
                }
                section_events.append(event)
            events.extend(section_events)
            density_report.append({"track_id": track.id, "role": track.role, "section_id": timeline_section["id"], "target_density": round(density, 4), "candidate_count": len(candidates), "mandatory_count": len(mandatory), "event_count": len(section_events), "actual_density": round(max(0, len(section_events) - len(mandatory)) / max(1, len(optional)), 4)})
    for event in locked:
        key = (event.get("track_id"), event.get("tick"))
        if not any((item["track_id"], item["tick"]) == key for item in events):
            events.append(event | {"locked": True})
    events.sort(key=lambda item: (int(item["tick"]), str(item["track_id"])))
    warnings = []
    if int(cursor) % 4:
        warnings.append("Form endpoint does not align to the four-beat grid")
    project = {
        "schema_version": "1.0", "feature": "mixed-meter-drums", "seed": request.seed,
        "settings": {"tempo_bpm": request.tempo_bpm, "subdivision": request.subdivision, "ppq": request.ppq, "variation": request.variation, "syncopation": request.syncopation, "humanize": request.humanize, "density_profile": request.density_profile},
        "patterns": {section["pattern"]["id"]: section["pattern"] for section in timeline_sections},
        "sections": timeline_sections, "bars": bars,
        "tracks": [track.model_dump() for track in tracks], "density": density_report,
        "events": events, "total_beats": cursor, "warnings": warnings,
    }
    project["compose_timeline"] = {"schema_version": "1.0", "clock": {"tempo_bpm": request.tempo_bpm, "ticks_per_beat": request.ppq, "total_ticks": round(cursor * request.ppq)}, "sections": timeline_sections, "bars": bars}
    return project


def _density(track: DrumTrackConfig, profile: str, section_role: str, tension: float) -> float:
    profile_base, profile_response = DENSITY_PROFILES[profile][track.role]
    base = track.base_density if track.density_mode in {"manual", "hybrid"} else profile_base
    response = track.tension_response if track.density_mode in {"tension_linked", "hybrid"} else profile_response
    if track.density_mode == "manual":
        response = 0
    offset = {"stable": -0.08, "tension": 0.0, "pre_resolution": -0.05 if track.role != "tom_fill" else 0.18, "resolved": 0.14 if track.role in {"kick", "snare", "closed_hat", "crash"} else -0.04}[section_role]
    return max(track.min_density, min(track.max_density, base + response * tension + offset))


def _candidates(track: DrumTrackConfig, bars: list[dict[str, Any]], subdivision: int, global_syncopation: float) -> list[dict[str, Any]]:
    result: dict[float, dict[str, Any]] = {}
    section_role = str(bars[0]["section_role"]) if bars else "stable"
    for bar_position, bar in enumerate(bars):
        start, end = float(bar["start_beat"]), float(bar["end_beat"])
        groups = {round(float(value), 6) for value in bar["group_boundaries"][:-1]}
        steps = round((end - start) * subdivision)
        for step in range(steps):
            position = round(start + step / subdivision, 6)
            on_beat = abs(position - round(position)) < 1e-6
            at_bar = position == start
            at_group = position in groups
            macro = bool(bar["macro_start"] and at_bar)
            offbeat = not on_beat
            structural = "macro" if macro else "bar" if at_bar else "group" if at_group else "beat" if on_beat else "offbeat"
            weight = 0.12
            mandatory = False
            if track.role == "kick":
                weight = 1.0 if macro else 0.82 if at_bar else 0.62 if at_group else 0.30 if offbeat else 0.42
                mandatory = macro or (at_bar and track.structural_clarity >= 0.9) or (at_group and track.structural_clarity >= 0.98)
            elif track.role == "snare":
                local = position - start
                backbeat = int(local) in {1, 3} and on_beat
                weight = 0.88 if backbeat else 0.68 if at_group and not at_bar else 0.46 if offbeat else 0.24
            elif track.role == "closed_hat":
                weight = 0.9 if at_bar else 0.72 if at_group else 0.58 if on_beat else 0.40
                mandatory = (at_bar and track.structural_clarity >= 0.95)
            elif track.role == "open_hat":
                weight = 0.84 if abs(position - (end - 0.5)) < 1e-6 else 0.46 if offbeat else 0.12
            elif track.role == "percussion":
                weight = 0.70 if offbeat else 0.46 if not at_bar else 0.10
            elif track.role == "tom_fill":
                final_bar = bar_position == len(bars) - 1
                weight = 0.92 if final_bar and position >= end - 2 else 0.05
                structural = "fill" if weight > 0.5 else structural
            else:
                weight = 1.0 if macro and section_role in {"stable", "resolved"} else 0.05
                mandatory = macro and (not result or section_role == "resolved")
            weight += (track.syncopation + global_syncopation) * 0.22 if offbeat else 0
            if weight >= 0.08 or mandatory:
                result[position] = {"position": position, "weight": min(1.0, weight), "mandatory": mandatory, "structural_role": structural, "bar_index": bar["index"], "cycle_index": bar["cycle_index"]}
    return list(result.values())


def _weighted_sample(random: Random, candidates: list[dict[str, Any]], count: int, variation: float) -> list[dict[str, Any]]:
    pool = list(candidates)
    result = []
    for _ in range(count):
        weights = [max(0.001, float(item["weight"]) * (1 - variation * 0.45) + random.random() * variation) for item in pool]
        target = random.random() * sum(weights)
        cursor = 0.0
        chosen = len(pool) - 1
        for index, weight in enumerate(weights):
            cursor += weight
            if cursor >= target:
                chosen = index
                break
        result.append(pool.pop(chosen))
    return result


def export_midi(request: MixedMeterExportRequest | dict[str, Any]) -> bytes:
    if not isinstance(request, MixedMeterExportRequest):
        request = MixedMeterExportRequest.model_validate(request)
    project = request.project
    ppq = int(project["settings"]["ppq"])
    tempo = float(project["settings"]["tempo_bpm"])
    conductor: list[tuple[int, int, bytes]] = [(0, 0, b"\xff\x51\x03" + round(60_000_000 / tempo).to_bytes(3, "big"))]
    for section in project["sections"]:
        conductor.append((round(float(section["start_beat"]) * ppq), 1, _meta_text(0x06, str(section["role"]))))
    for bar in project["bars"]:
        denominator_power = 2 if int(bar["denominator"]) == 4 else 3
        conductor.append((round(float(bar["start_beat"]) * ppq), 2, bytes((0xFF, 0x58, 0x04, int(bar["meter"]), denominator_power, 0x18, 0x08))))
    chunks = [_track_chunk(conductor)]
    by_role: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for event in project["events"]:
        by_role[str(event["role"])].append(event)
    for role, events in by_role.items():
        track_events: list[tuple[int, int, bytes]] = [(0, 0, _meta_text(0x03, role.replace("_", " ").title()))]
        for event in events:
            tick = int(event["tick"])
            if request.humanized_positions:
                tick += round(float(event.get("timing_offset_ms", 0)) / 1000 * tempo / 60 * ppq)
            tick = max(0, tick)
            note, velocity = int(event["midi_note"]), int(event["velocity"])
            track_events.extend([(tick, 2, bytes((0x99, note, velocity))), (tick + int(event["duration_ticks"]), 1, bytes((0x89, note, 0)))])
        chunks.append(_track_chunk(track_events))
    header = b"MThd\x00\x00\x00\x06\x00\x01" + len(chunks).to_bytes(2, "big") + ppq.to_bytes(2, "big")
    return header + b"".join(chunks)


def _meta_text(kind: int, value: str) -> bytes:
    data = value.encode("utf-8")[:120]
    return bytes((0xFF, kind)) + _vlq(len(data)) + data


def _track_chunk(events: list[tuple[int, int, bytes]]) -> bytes:
    events.sort(key=lambda item: (item[0], item[1]))
    data = bytearray()
    previous = 0
    for tick, _priority, payload in events:
        data.extend(_vlq(tick - previous))
        data.extend(payload)
        previous = tick
    data.extend(b"\x00\xff\x2f\x00")
    return b"MTrk" + len(data).to_bytes(4, "big") + bytes(data)


def _vlq(value: int) -> bytes:
    result = [value & 0x7F]
    while value > 0x7F:
        value >>= 7
        result.insert(0, (value & 0x7F) | 0x80)
    return bytes(result)


def render_wav(project: dict[str, Any], sample_rate: int = 22050) -> bytes:
    tempo = float(project["settings"]["tempo_bpm"])
    beat_seconds = 60 / tempo
    total = float(project["total_beats"]) * beat_seconds + 0.5
    samples = [0.0] * (round(total * sample_rate) + 1)
    for event in project["events"]:
        start = float(event["pulse_position"]) * beat_seconds + float(event.get("timing_offset_ms", 0)) / 1000
        duration = {"kick": 0.28, "snare": 0.16, "closed_hat": 0.07, "open_hat": 0.24, "percussion": 0.12, "tom_fill": 0.22, "crash": 0.42}[str(event["role"])]
        start_index = max(0, round(start * sample_rate))
        end_index = min(len(samples), start_index + round(duration * sample_rate))
        for index in range(start_index, end_index):
            elapsed = (index - start_index) / sample_rate
            samples[index] += _drum_sample(str(event["role"]), elapsed, duration, int(event["velocity"]))
    peak = max((abs(value) for value in samples), default=1)
    scale = min(1.0, 0.96 / peak)
    buffer = BytesIO()
    with wave_open(buffer, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(b"".join(pack("<h", round(max(-1, min(1, value * scale)) * 32767)) for value in samples))
    return buffer.getvalue()


def _drum_sample(role: str, elapsed: float, duration: float, velocity: int) -> float:
    envelope = exp(-elapsed / max(0.01, duration / 4)) * velocity / 127
    if role == "kick":
        return sin(2 * pi * (72 - 35 * elapsed / duration) * elapsed) * envelope * 0.55
    if role == "snare":
        return (sin(2 * pi * 181 * elapsed) + sin(2 * pi * 997 * elapsed) * 0.7) * envelope * 0.24
    if role in {"closed_hat", "open_hat", "crash"}:
        return sum(sin(2 * pi * frequency * elapsed) for frequency in (3100, 4210, 5870, 7430)) / 4 * envelope * 0.22
    frequency = 118 if role == "tom_fill" else 520
    return sin(2 * pi * frequency * elapsed) * envelope * 0.32
