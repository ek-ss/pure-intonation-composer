from __future__ import annotations

from fractions import Fraction
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.arrangement.profiles import HarmonyPerformanceStyle, SectionTemplate

RECOMMENDED_TAGS = {
    "stable",
    "tense",
    "open",
    "dense",
    "cadential",
    "suspended",
    "power",
    "color",
}


class ArrangeScaleInput(BaseModel):
    scale_id: str | None = Field(default=None, max_length=80)
    ratios: list[str] = Field(min_length=2, max_length=64)
    base_frequency: float = Field(default=220, ge=20, le=2000)


class BasicChordModel(BaseModel):
    id: str = Field(min_length=1, max_length=40, pattern=r"^[a-z0-9][a-z0-9_-]*$")
    name: str = Field(min_length=1, max_length=80)
    mode: Literal["absolute", "degree_template", "ratio_template"]
    tones: list[int | str] = Field(min_length=1, max_length=12)
    root_degree: int | None = Field(default=None, ge=0, le=63)
    allowed_root_degrees: list[int] | None = Field(default=None, min_length=1, max_length=64)
    tone_vectors: list[list[int]] | None = Field(default=None, max_length=12)
    tags: list[str] = Field(default_factory=list, max_length=12)

    @model_validator(mode="after")
    def tones_must_match_mode(self) -> BasicChordModel:
        if self.mode == "degree_template":
            if any(not isinstance(tone, int) for tone in self.tones):
                raise ValueError(
                    f"chord '{self.id}': degree_template tones must be integer "
                    "scale-degree offsets"
                )
        elif any(not isinstance(tone, str) for tone in self.tones):
            raise ValueError(
                f"chord '{self.id}': {self.mode} tones must be ratio strings like '5/4'"
            )
        if self.allowed_root_degrees is not None and any(
            degree < 0 for degree in self.allowed_root_degrees
        ):
            raise ValueError(f"chord '{self.id}': allowed_root_degrees must be non-negative")
        return self


class ArrangeClockInput(BaseModel):
    tempo_bpm: float | None = Field(default=None, ge=30, le=300)
    beats_per_bar: int | None = Field(default=None)
    subdivisions_per_beat: int = Field(default=4, ge=1, le=8)
    bars: int | None = Field(default=None, ge=1, le=128)

    @field_validator("beats_per_bar")
    @classmethod
    def meter_must_be_supported(cls, value: int | None) -> int | None:
        if value is not None and value not in {2, 3, 4, 6}:
            raise ValueError("beats_per_bar must be one of 2, 3, 4, 6")
        return value

    @field_validator("subdivisions_per_beat")
    @classmethod
    def subdivisions_must_fit_midi_clock(cls, value: int) -> int:
        if 480 % value:
            raise ValueError("subdivisions_per_beat must divide the 480-tick MIDI beat")
        return value


class ArrangementControlsInput(BaseModel):
    energy: float = Field(default=0.5, ge=0, le=1)
    density: float = Field(default=0.5, ge=0, le=1)
    syncopation: float = Field(default=0.5, ge=0, le=1)
    harmonic_complexity: float = Field(default=0.5, ge=0, le=1)
    repetition: float = Field(default=0.5, ge=0, le=1)
    root_variety: float = Field(default=0.0, ge=0, le=1)
    section_contrast: float = Field(default=0.5, ge=0, le=1)
    humanization: float = Field(default=0.0, ge=0, le=1)
    melody_enabled: bool = True
    drums_enabled: bool = True


class ArrangeFormInput(BaseModel):
    sections: list[SectionTemplate] = Field(min_length=1, max_length=32)


class ArrangeGenerateRequest(BaseModel):
    scale: ArrangeScaleInput
    chord_vocabulary: list[BasicChordModel] = Field(min_length=1, max_length=24)
    genre_profile: str | dict[str, Any]
    clock: ArrangeClockInput = ArrangeClockInput()
    form: ArrangeFormInput | None = None
    controls: ArrangementControlsInput = ArrangementControlsInput()
    harmony_performance: HarmonyPerformanceStyle | None = None
    seed: int = 0


Waveform = Literal["sine", "saw", "square", "triangle", "additive"]


class ArrangementProjectScale(BaseModel):
    base_frequency: float = Field(ge=20, le=2000)


class ArrangementProjectClock(BaseModel):
    tempo_bpm: float = Field(ge=30, le=300)
    beats_per_bar: Literal[2, 3, 4, 6]
    subdivisions_per_beat: int = Field(ge=1, le=8)
    bars: int = Field(ge=1, le=128)
    ticks_per_beat: int = Field(ge=24, le=960)
    total_ticks: int = Field(ge=1, le=737_280)

    @model_validator(mode="after")
    def timeline_must_be_consistent(self) -> ArrangementProjectClock:
        if self.ticks_per_beat % self.subdivisions_per_beat:
            raise ValueError("subdivisions_per_beat must divide ticks_per_beat")
        expected = self.bars * self.beats_per_bar * self.ticks_per_beat
        if self.total_ticks != expected:
            raise ValueError(
                f"total_ticks must equal bars * beats_per_bar * ticks_per_beat ({expected})"
            )
        return self


class ArrangementProjectTrack(BaseModel):
    id: str = Field(min_length=1, max_length=40, pattern=r"^[a-z0-9][a-z0-9_-]*$")
    role: Literal["drums", "bass", "harmony", "melody", "texture"]
    instrument: str = Field(min_length=1, max_length=80)
    waveform: Waveform


class ArrangementProjectSection(BaseModel):
    id: str = Field(min_length=1, max_length=40)
    role: str = Field(min_length=1, max_length=40)
    start_bar: int = Field(ge=0, le=127)
    bars: int = Field(ge=1, le=128)


class ArrangementProjectEvent(BaseModel):
    id: str = Field(min_length=1, max_length=40)
    track_id: str = Field(min_length=1, max_length=40)
    kind: Literal["note", "drum"]
    ratio: str | None = Field(default=None, max_length=80)
    drum_note: int | None = Field(default=None, ge=0, le=127)
    start_tick: int = Field(ge=0, le=737_279)
    duration_ticks: int = Field(ge=1, le=737_280)
    velocity: int = Field(ge=1, le=127)
    articulation: str = Field(min_length=1, max_length=24)
    chord_index: int = Field(ge=0, le=8191)
    section_id: str = Field(min_length=1, max_length=40)
    source_gesture_id: str | None = Field(default=None, max_length=60)
    gesture_component: Literal["block", "tone", "low", "chord"] | None = None
    phase_stream_id: Literal["a", "b"] | None = None
    source_slot_index: int | None = Field(default=None, ge=0, le=8191)
    source_chord_id: str | None = Field(default=None, max_length=80)
    visit_index: int | None = Field(default=None, ge=0, le=65_535)
    phase_iteration: int | None = Field(default=None, ge=0, le=65_535)

    @model_validator(mode="after")
    def pitch_must_match_event_kind(self) -> ArrangementProjectEvent:
        if self.kind == "note":
            if self.ratio is None or self.drum_note is not None:
                raise ValueError("note events require ratio and must not include drum_note")
            try:
                ratio = Fraction(self.ratio)
            except (ValueError, ZeroDivisionError) as error:
                raise ValueError("note event ratio must be a valid fraction") from error
            if ratio <= 0:
                raise ValueError("note event ratio must be positive")
        elif self.drum_note is None or self.ratio is not None:
            raise ValueError("drum events require drum_note and must not include ratio")
        return self


class ArrangementProjectMix(BaseModel):
    gain: float = Field(default=0.8, ge=0, le=2)
    pan: float = Field(default=0, ge=-1, le=1)


class ArrangementProjectRenderSettings(BaseModel):
    sample_rate: int = Field(default=22_050, ge=8_000, le=96_000)
    waveforms: dict[str, Waveform] = Field(default_factory=dict, max_length=8)


class ArrangementProjectGesture(BaseModel):
    id: str = Field(min_length=1, max_length=60)
    section_id: str = Field(min_length=1, max_length=40)
    chord_index: int = Field(ge=0, le=8191)
    mode: Literal["block", "arpeggio", "stride"]
    start_tick: int = Field(ge=0, le=737_279)
    duration_ticks: int = Field(ge=1, le=737_280)
    resolved_settings: dict[str, Any] = Field(default_factory=dict, max_length=16)


class ArrangementProjectMarker(BaseModel):
    tick: int = Field(ge=0, le=737_280)
    name: str = Field(min_length=1, max_length=120)


class ArrangementProjectInput(BaseModel):
    schema_version: Literal["1.0.0", "1.1.0"]
    source_scale: ArrangementProjectScale
    clock: ArrangementProjectClock
    tracks: list[ArrangementProjectTrack] = Field(min_length=1, max_length=8)
    form: list[ArrangementProjectSection] = Field(min_length=1, max_length=32)
    events: list[ArrangementProjectEvent] = Field(min_length=1, max_length=8192)
    harmony_gestures: list[ArrangementProjectGesture] = Field(
        default_factory=list, max_length=4096
    )
    markers: list[ArrangementProjectMarker] = Field(default_factory=list, max_length=128)
    mix: dict[str, ArrangementProjectMix] = Field(default_factory=dict, max_length=8)
    render_settings: ArrangementProjectRenderSettings = Field(
        default_factory=ArrangementProjectRenderSettings
    )

    @model_validator(mode="after")
    def references_and_timeline_must_be_valid(self) -> ArrangementProjectInput:
        track_ids = [track.id for track in self.tracks]
        if len(track_ids) != len(set(track_ids)):
            raise ValueError("arrangement track ids must be unique")
        section_ids = [section.id for section in self.form]
        if len(section_ids) != len(set(section_ids)):
            raise ValueError("arrangement section ids must be unique")

        cursor = 0
        for section in self.form:
            if section.start_bar != cursor:
                raise ValueError("arrangement sections must be contiguous from bar zero")
            cursor += section.bars
        if cursor != self.clock.bars:
            raise ValueError("arrangement sections must exactly fill the clock bars")

        known_tracks = set(track_ids)
        known_sections = set(section_ids)
        gesture_ids = {gesture.id for gesture in self.harmony_gestures}
        if len(gesture_ids) != len(self.harmony_gestures):
            raise ValueError("harmony gesture ids must be unique")
        for gesture in self.harmony_gestures:
            if gesture.section_id not in known_sections:
                raise ValueError(
                    f"harmony gesture references unknown section '{gesture.section_id}'"
                )
            if gesture.start_tick + gesture.duration_ticks > self.clock.total_ticks:
                raise ValueError(f"harmony gesture '{gesture.id}' extends beyond the clock")
        for event in self.events:
            if event.track_id not in known_tracks:
                raise ValueError(f"event references unknown track '{event.track_id}'")
            if event.section_id not in known_sections:
                raise ValueError(f"event references unknown section '{event.section_id}'")
            if event.start_tick + event.duration_ticks > self.clock.total_ticks:
                raise ValueError(f"event '{event.id}' extends beyond clock.total_ticks")
            if (
                event.source_gesture_id is not None
                and event.source_gesture_id not in gesture_ids
            ):
                raise ValueError(
                    f"event references unknown harmony gesture '{event.source_gesture_id}'"
                )
        if not set(self.mix).issubset(known_tracks):
            raise ValueError("mix references an unknown track")
        if not set(self.render_settings.waveforms).issubset(known_tracks):
            raise ValueError("render_settings.waveforms references an unknown track")
        return self


class ArrangeProjectRequest(BaseModel):
    """MIDI/render requests carry the canonical ArrangementProject JSON back."""

    arrangement: ArrangementProjectInput


class ArrangeMigrationRequest(BaseModel):
    """Migrate a canonical arrangement project without regenerating its events."""

    arrangement: dict[str, Any]
