from __future__ import annotations

from array import array
from collections.abc import Iterable
from dataclasses import dataclass
from fractions import Fraction
from io import BytesIO
from math import ceil
from sys import byteorder
from typing import Any
from wave import open as wave_open

from app.arrangement.chords import (
    BasicChordInput,
    build_transition_graph,
    materialize_chords,
)
from app.arrangement.form import ArrangementSection, build_form
from app.arrangement.models import ArrangeGenerateRequest, ArrangementProjectInput
from app.arrangement.parts import (
    ArrangementEvent,
    ArrangementTrack,
    build_tracks,
    finalize_events,
    generate_drum_events,
    generate_pitched_events,
    select_bass_notes,
    select_melody_notes,
)
from app.arrangement.profiles import GenreProfile, resolve_profile
from app.arrangement.progression import (
    generate_progression,
    plan_chord_slots,
    voice_progression,
)
from app.audio.render import Envelope, NoteEvent, render_wav
from app.composition.rhythm import CompositionClock
from app.exporters.midi import (
    MidiArrangementTrack,
    MidiDrumHit,
    MidiNote,
    arrangement_midi_bytes,
)
from app.tuning.ratios import parse_ratio, ratio_text

PROJECT_SCHEMA_VERSION = "1.0.0"
SAMPLE_RATE = 22_050
MAX_RENDER_SAMPLES = 4_000_000

_ENVELOPES = {
    "drums": Envelope(0.001, 0.06, 0.0, 0.05),
    "bass": Envelope(0.01, 0.1, 0.7, 0.12),
    "harmony": Envelope(0.05, 0.2, 0.6, 0.3),
    "melody": Envelope(0.02, 0.14, 0.65, 0.28),
    "texture": Envelope(0.3, 0.3, 0.7, 0.5),
}


@dataclass(frozen=True)
class ProjectView:
    """Parsed canonical project used by the MIDI and render exporters."""

    base_frequency: float
    tempo_bpm: float
    beats_per_bar: int
    ticks_per_beat: int
    total_ticks: int
    sample_rate: int
    tracks: list[dict[str, Any]]
    events: list[dict[str, Any]]
    markers: list[tuple[int, str]]


def generate_arrangement(request: ArrangeGenerateRequest) -> dict[str, Any]:
    """Compile scale + chord vocabulary + profile into one canonical timeline."""
    trace: list[dict[str, str]] = []

    def note(stage: str, message: str) -> None:
        trace.append({"stage": stage, "message": message})

    scale = [parse_ratio(ratio) for ratio in request.scale.ratios]
    profile = resolve_profile(request.genre_profile)
    controls = request.controls

    chords = [
        BasicChordInput(
            id=chord.id,
            name=chord.name,
            mode=chord.mode,
            tones=tuple(
                tone if isinstance(tone, int) else parse_ratio(tone) for tone in chord.tones
            ),
            root_degree=chord.root_degree,
            allowed_root_degrees=(
                tuple(chord.allowed_root_degrees)
                if chord.allowed_root_degrees is not None
                else None
            ),
            tone_vectors=(
                tuple(tuple(vector) for vector in chord.tone_vectors)
                if chord.tone_vectors is not None
                else None
            ),
            tags=tuple(tag.lower() for tag in chord.tags),
        )
        for chord in request.chord_vocabulary
    ]
    instances, materialization_notes = materialize_chords(chords, scale)
    for message in materialization_notes:
        note("chord-analysis", message)
    graph = build_transition_graph(instances)
    note("chord-analysis", f"materialized {len(instances)} chord instances")

    beats_per_bar = request.clock.beats_per_bar or profile.allowed_meters[0]
    if beats_per_bar not in profile.allowed_meters:
        raise ValueError(
            f"meter {beats_per_bar}/4 is not allowed by profile '{profile.id}' "
            f"(allowed: {profile.allowed_meters})"
        )
    low_tempo, high_tempo = profile.tempo_range
    tempo = request.clock.tempo_bpm or round((low_tempo + high_tempo) / 2, 2)
    if not low_tempo <= tempo <= high_tempo:
        clamped = min(max(tempo, low_tempo), high_tempo)
        note("form", f"tempo {tempo} is outside the profile range; clamped to {clamped}")
        tempo = clamped

    sections = build_form(
        profile,
        request.clock.bars,
        list(request.form.sections) if request.form else None,
        controls.energy,
        controls.section_contrast,
    )
    bars = sections[-1].end_bar
    clock = CompositionClock(
        beats_per_bar=beats_per_bar,
        subdivisions_per_beat=request.clock.subdivisions_per_beat,
        bars=bars,
        tempo_bpm=tempo,
    )
    note(
        "form",
        f"form: {len(sections)} sections, {bars} bars, "
        f"{beats_per_bar}/4 at {tempo} BPM",
    )

    slots = plan_chord_slots(sections, clock.subdivisions_per_bar)
    progression, progression_notes = generate_progression(
        profile,
        instances,
        graph,
        sections,
        slots,
        controls.harmonic_complexity,
        controls.repetition,
        request.seed,
    )
    for message in progression_notes:
        note("progression", message)

    harmony_part = profile.part_for("harmony")
    harmony_low = harmony_part.register_low if harmony_part else 1.0
    harmony_high = harmony_part.register_high if harmony_part else 3.0
    voiced = voice_progression(progression, instances, harmony_low, harmony_high)
    roots = [instances[slot.instance_index].root for slot in progression]

    tracks = build_tracks(profile, controls.drums_enabled, controls.melody_enabled)
    enabled_roles = {track.role for track in tracks}
    note("parts", f"tracks: {', '.join(track.id for track in tracks)}")

    pitched_parts = [
        part for part in profile.parts if part.enabled and part.role in enabled_roles
    ]
    bass_notes: list[Fraction] = []
    melody_notes: list[Fraction] = []
    for part in pitched_parts:
        if part.role == "bass":
            bass_notes = select_bass_notes(progression, roots, part)
        elif part.role == "melody":
            melody_notes = select_melody_notes(
                progression, voiced, sorted(set(_pitch_classes(scale))), part, request.seed
            )

    events: list[ArrangementEvent] = []
    if "drums" in enabled_roles:
        events.extend(
            generate_drum_events(
                clock,
                sections,
                profile,
                controls.density,
                controls.syncopation,
                controls.humanization,
                request.seed,
            )
        )
    pitched_event_parts = [part for part in pitched_parts if part.role != "drums"]
    if pitched_event_parts:
        events.extend(
            generate_pitched_events(
                clock,
                sections,
                profile,
                pitched_event_parts,
                progression,
                voiced,
                bass_notes,
                melody_notes,
                controls.density,
                controls.syncopation,
                controls.humanization,
                request.seed,
            )
        )
    final_events = finalize_events(events, clock.total_ticks)
    note("compile", f"compiled {len(final_events)} events on one canonical timeline")

    return {
        "schema_version": PROJECT_SCHEMA_VERSION,
        "metadata": {
            "generator": "pure-intonation-composer",
            "feature": "genre-arrangement",
            "profile_display_name": profile.display_name,
        },
        "source_scale": {
            "scale_id": request.scale.scale_id,
            "ratios": [ratio_text(ratio) for ratio in scale],
            "base_frequency": request.scale.base_frequency,
        },
        "chord_vocabulary": [_instance_payload(instance) for instance in instances],
        "requested_profile": (
            request.genre_profile
            if isinstance(request.genre_profile, str)
            else "inline"
        ),
        "resolved_profile": {
            "profile": profile.model_dump(),
            "resolved_controls": {
                "tempo_bpm": tempo,
                "beats_per_bar": beats_per_bar,
                "bars": bars,
                "subdivisions_per_beat": request.clock.subdivisions_per_beat,
                "energy": controls.energy,
                "density": controls.density,
                "syncopation": controls.syncopation,
                "harmonic_complexity": controls.harmonic_complexity,
                "repetition": controls.repetition,
                "section_contrast": controls.section_contrast,
                "humanization": controls.humanization,
                "melody_enabled": controls.melody_enabled,
                "drums_enabled": controls.drums_enabled,
            },
        },
        "seed": request.seed,
        "form": [section.payload() for section in sections],
        "harmony_progression": _progression_payload(progression, instances, clock),
        "clock": {
            "tempo_bpm": tempo,
            "beats_per_bar": beats_per_bar,
            "subdivisions_per_beat": request.clock.subdivisions_per_beat,
            "bars": bars,
            "ticks_per_beat": clock.ticks_per_beat,
            "total_ticks": clock.total_ticks,
        },
        "tracks": [_track_payload(track, final_events) for track in tracks],
        "events": [event.payload() for event in final_events],
        "automation": _automation(profile, sections, clock),
        "mix": {track.id: {"gain": track.gain, "pan": 0.0} for track in tracks},
        "render_settings": {
            "sample_rate": SAMPLE_RATE,
            "waveforms": {track.id: track.waveform for track in tracks},
            "fallbacks": [],
        },
        "decision_trace": trace,
    }


def project_midi_bytes(payload: ArrangementProjectInput | dict[str, Any]) -> bytes:
    """Export a previously generated ArrangementProject as SMF type 1."""
    view = _project_view(payload)
    tracks = []
    for track in view.tracks:
        notes = tuple(
            MidiNote(
                parse_ratio(event["ratio"]),
                event["start_tick"] / view.ticks_per_beat,
                event["duration_ticks"] / view.ticks_per_beat,
                event["velocity"],
            )
            for event in view.events
            if event["track_id"] == track["id"] and event["kind"] == "note"
        )
        drums = tuple(
            MidiDrumHit(
                event["drum_note"],
                event["start_tick"] / view.ticks_per_beat,
                event["velocity"],
            )
            for event in view.events
            if event["track_id"] == track["id"] and event["kind"] == "drum"
        )
        tracks.append(MidiArrangementTrack(track["name"], notes, drums))
    return arrangement_midi_bytes(
        tracks,
        view.tempo_bpm,
        view.beats_per_bar,
        view.ticks_per_beat,
        view.base_frequency,
        view.markers,
    )


def project_render_wav(payload: ArrangementProjectInput | dict[str, Any]) -> bytes:
    """Render a stereo-preview-style mono mixdown through instrument presets."""
    view = _project_view(payload)
    seconds_per_tick = 60 / view.tempo_bpm / view.ticks_per_beat
    render_seconds = (
        view.total_ticks * seconds_per_tick
        + max(envelope.release_seconds for envelope in _ENVELOPES.values())
    )
    render_samples = ceil(render_seconds * view.sample_rate)
    if render_samples > MAX_RENDER_SAMPLES:
        max_seconds = MAX_RENDER_SAMPLES / view.sample_rate
        raise ValueError(
            f"arrangement preview is {render_seconds:.1f} seconds; the "
            f"{view.sample_rate} Hz preview limit is {max_seconds:.1f} seconds "
            "(reduce bars or increase tempo)"
        )

    def render_stems() -> Iterable[tuple[bytes, float]]:
        for track in view.tracks:
            events = [
                event for event in view.events if event["track_id"] == track["id"]
            ]
            if not events:
                continue
            notes = []
            for event in events:
                if event["kind"] == "note":
                    ratio = parse_ratio(event["ratio"])
                else:
                    # Drum preview approximates the GM note pitch with a short blip.
                    frequency = 440 * 2 ** ((event["drum_note"] - 69) / 12)
                    ratio = Fraction(
                        frequency / view.base_frequency
                    ).limit_denominator(4096)
                notes.append(
                    NoteEvent(
                        ratio,
                        event["start_tick"] * seconds_per_tick,
                        max(0.03, event["duration_ticks"] * seconds_per_tick),
                        event["velocity"],
                    )
                )
            waveform = track.get("waveform", "saw")
            envelope = _ENVELOPES.get(track["role"], Envelope())
            yield (
                render_wav(
                    notes,
                    view.base_frequency,
                    waveform,
                    envelope,
                    view.sample_rate,
                ),
                float(track.get("gain", 0.8)),
            )
    return _mix_wavs(render_stems(), view.sample_rate)


def _mix_wavs(stems: Iterable[tuple[bytes, float]], sample_rate: int) -> bytes:
    mixed = array("f")
    stem_count = 0
    for data, gain in stems:
        with wave_open(BytesIO(data), "rb") as wav:
            if (
                wav.getnchannels() != 1
                or wav.getsampwidth() != 2
                or wav.getframerate() != sample_rate
            ):
                raise ValueError("rendered stem has incompatible WAV settings")
            frames = wav.readframes(wav.getnframes())
        samples = array("h")
        samples.frombytes(frames)
        if byteorder != "little":
            samples.byteswap()
        if len(mixed) < len(samples):
            mixed.extend(array("f", [0.0]) * (len(samples) - len(mixed)))
        for index, sample in enumerate(samples):
            mixed[index] += sample * gain
        stem_count += 1
    if not stem_count:
        raise ValueError("the arrangement contains no renderable events")
    peak = max((abs(sample) for sample in mixed), default=1)
    scale = min(1.0, 0.98 * 32767 / peak) if peak else 1.0
    output = array("h", (int(sample * scale) for sample in mixed))
    if byteorder != "little":
        output.byteswap()
    buffer = BytesIO()
    with wave_open(buffer, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(output.tobytes())
    return buffer.getvalue()


def _project_view(payload: ArrangementProjectInput | dict[str, Any]) -> ProjectView:
    try:
        project = (
            payload
            if isinstance(payload, ArrangementProjectInput)
            else ArrangementProjectInput.model_validate(payload)
        )
    except ValueError as error:
        raise ValueError(f"invalid arrangement project payload: {error}") from error

    tracks = []
    for track in project.tracks:
        mix = project.mix.get(track.id)
        tracks.append(
            {
                "id": track.id,
                "name": f"{track.role} ({track.instrument})",
                "role": track.role,
                "instrument": track.instrument,
                "waveform": project.render_settings.waveforms.get(
                    track.id, track.waveform
                ),
                "gain": mix.gain if mix is not None else 0.8,
            }
        )
    markers = [
        (
            section.start_bar
            * project.clock.beats_per_bar
            * project.clock.ticks_per_beat,
            section.role,
        )
        for section in project.form
    ]
    return ProjectView(
        base_frequency=project.source_scale.base_frequency,
        tempo_bpm=project.clock.tempo_bpm,
        beats_per_bar=project.clock.beats_per_bar,
        ticks_per_beat=project.clock.ticks_per_beat,
        total_ticks=project.clock.total_ticks,
        sample_rate=project.render_settings.sample_rate,
        tracks=tracks,
        events=[event.model_dump() for event in project.events],
        markers=markers,
    )


def _pitch_classes(scale: list[Fraction]) -> list[Fraction]:
    from app.tuning.ratios import reduce_to_octave

    return [reduce_to_octave(ratio) for ratio in scale]


def _instance_payload(instance: Any) -> dict[str, Any]:
    return {
        "id": instance.id,
        "template_id": instance.template_id,
        "name": instance.name,
        "mode": instance.mode,
        "root": ratio_text(instance.root),
        "tones": [ratio_text(tone) for tone in instance.tones],
        "tags": list(instance.tags),
        "root_degree": instance.root_degree,
        "tone_vectors": (
            [list(vector) for vector in instance.tone_vectors]
            if instance.tone_vectors is not None
            else None
        ),
        "cents_span": instance.cents_span,
        "complexity": instance.complexity,
        "tension": instance.tension,
    }


def _progression_payload(
    progression: list[Any], instances: list[Any], clock: CompositionClock
) -> list[dict[str, Any]]:
    slots = []
    for slot in progression:
        instance = instances[slot.instance_index]
        transition = slot.transition
        slots.append(
            {
                "index": slot.index,
                "section_id": slot.section_id,
                "instance_id": instance.id,
                "name": instance.name,
                "root": ratio_text(instance.root),
                "tones": [ratio_text(tone) for tone in instance.tones],
                "inversion": 0,
                "start_tick": slot.start_subdivision * clock.ticks_per_subdivision,
                "duration_ticks": slot.duration_subdivisions * clock.ticks_per_subdivision,
                "transition": (
                    {
                        "root_motion_cents": transition.root_motion_cents,
                        "common_tones": transition.common_tones,
                        "voice_leading_cents": transition.voice_leading_cents,
                        "tension_change": transition.tension_change,
                    }
                    if transition is not None
                    else None
                ),
            }
        )
    return slots


def _track_payload(
    track: ArrangementTrack, events: list[ArrangementEvent]
) -> dict[str, Any]:
    return {
        "id": track.id,
        "role": track.role,
        "instrument": track.instrument,
        "register": [track.register_low, track.register_high],
        "waveform": track.waveform,
        "gain": track.gain,
        "event_count": sum(1 for event in events if event.track_id == track.id),
    }


def _automation(
    profile: GenreProfile, sections: list[ArrangementSection], clock: CompositionClock
) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    pump = profile.render.get("sidechain_pump") if profile.render else None
    ticks_per_bar = clock.subdivisions_per_bar * clock.ticks_per_subdivision
    for section in sections:
        entries.append(
            {
                "type": "energy",
                "section_id": section.id,
                "start_tick": section.start_bar * ticks_per_bar,
                "duration_ticks": section.bars * ticks_per_bar,
                "value_start": section.energy_start,
                "value_end": section.energy_end,
            }
        )
        if pump and section.canonical_role in {"drop", "chorus"}:
            entries.append(
                {
                    "type": "sidechain_pump",
                    "section_id": section.id,
                    "target_track": pump.get("target", "harmony"),
                    "amount": pump.get("amount", 0.5),
                    "rate": pump.get("rate", "1/4"),
                    "start_tick": section.start_bar * ticks_per_bar,
                    "duration_ticks": section.bars * ticks_per_bar,
                    "note": "automation intent only; applied during rendering "
                    "once the effect-automation stage is available",
                }
            )
    return entries
