from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator


class CPSRequest(BaseModel):
    factors: list[int] = Field(min_length=1, max_length=16)
    choose: int = Field(ge=1, le=16)
    kind: Literal["harmonic", "subharmonic"] = "harmonic"
    octave_reduce: bool = True

    @field_validator("factors")
    @classmethod
    def factors_must_be_positive(cls, values: list[int]) -> list[int]:
        if any(value < 1 for value in values):
            raise ValueError("factors must contain positive integers")
        if len(set(values)) != len(values):
            raise ValueError("factors must be unique")
        return values


class EulerFokkerRequest(BaseModel):
    factors: list[int] = Field(min_length=1, max_length=12)
    octave_reduce: bool = True

    @field_validator("factors")
    @classmethod
    def factors_must_be_greater_than_one(cls, values: list[int]) -> list[int]:
        if any(value < 2 for value in values):
            raise ValueError("Euler–Fokker factors must be integers greater than one")
        return values


class SeriesRequest(BaseModel):
    count: int = Field(ge=1, le=128)
    octave_reduce: bool = True


class RatioRequest(BaseModel):
    ratio: str = Field(pattern=r"^\d+/\d+$")


class IntervalRequest(BaseModel):
    value: str = Field(min_length=1, max_length=200)


class SnapRequest(BaseModel):
    ratios: list[str] = Field(min_length=1, max_length=256)
    mode: Literal["edo", "prime_limit"]
    value: int = Field(ge=2, le=31)


class ScalaRequest(BaseModel):
    name: str = Field(default="Pure Intonation Scale", min_length=1, max_length=80)
    ratios: list[str] = Field(min_length=1, max_length=256)


class ScaleSaveRequest(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    ratios: list[str] = Field(min_length=1, max_length=256)


class ScalaImportRequest(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    content: str = Field(min_length=1)


class HarmonicGraphRequest(BaseModel):
    factors: list[int] = Field(min_length=2, max_length=16)
    choose: int = Field(ge=1, le=16)
    operation: Literal["graph", "shortest_path", "random_walk", "weighted_walk"] = "graph"
    start: int = Field(default=0, ge=0)
    end: int | None = Field(default=None, ge=0)
    steps: int = Field(default=8, ge=0, le=10_000)
    seed: int = 0
    metric: Literal["harmonic", "monzo", "cent"] = "harmonic"
    layout: Literal["reference_layered_grid"] | None = None
    reference: int | None = Field(default=None, ge=0)
    sort_mode: Literal["lexicographic", "product", "pitch"] = "lexicographic"

    @field_validator("factors")
    @classmethod
    def graph_factors_must_be_positive_and_unique(cls, values: list[int]) -> list[int]:
        if any(value < 1 for value in values):
            raise ValueError("factors must contain positive integers")
        if len(set(values)) != len(values):
            raise ValueError("factors must be unique")
        return values


class HarmonyRequest(BaseModel):
    factors: list[int] = Field(min_length=2, max_length=16)
    choose: int = Field(ge=1, le=16)
    length: int = Field(default=8, ge=1, le=10_000)
    start: int = Field(default=0, ge=0)
    seed: int = 0
    metric: Literal["harmonic", "monzo", "cent"] = "harmonic"

    @field_validator("factors")
    @classmethod
    def harmony_factors_must_be_positive_and_unique(cls, values: list[int]) -> list[int]:
        if any(value < 1 for value in values):
            raise ValueError("factors must contain positive integers")
        if len(set(values)) != len(values):
            raise ValueError("factors must be unique")
        return values


class VoiceLeadingRequest(BaseModel):
    chords: list[list[str]] = Field(min_length=1, max_length=128)
    max_leap_cents: float = Field(default=700, gt=0, le=2400)
    register_low_cents: float = Field(default=0, ge=-4800, le=9600)
    register_high_cents: float = Field(default=2400, ge=-4800, le=9600)

    @field_validator("chords")
    @classmethod
    def chords_must_have_a_bounded_voice_count(cls, values: list[list[str]]) -> list[list[str]]:
        if any(not 1 <= len(chord) <= 8 for chord in values):
            raise ValueError("each chord must contain between 1 and 8 voices")
        if len({len(chord) for chord in values}) != 1:
            raise ValueError("all chords must contain the same number of voices")
        return values


class BassRequest(BaseModel):
    chords: list[list[str]] = Field(min_length=1, max_length=128)
    strategy: Literal["mirror", "root", "fifth", "hybrid"] = "hybrid"
    max_leap_cents: float = Field(default=900, gt=0, le=2400)
    register_low_cents: float = Field(default=-2400, ge=-4800, le=9600)
    register_high_cents: float = Field(default=0, ge=-4800, le=9600)


class MelodyRequest(BaseModel):
    chords: list[list[str]] = Field(min_length=1, max_length=256)
    voice_count: int = Field(default=1, ge=1, le=8)
    seed: int = 0
    contour: Literal["ascending", "descending", "arch", "free"] = "arch"
    max_leap_cents: float = Field(default=700, gt=0, le=2400)
    register_low_cents: float = Field(default=600, ge=-4800, le=9600)
    register_high_cents: float = Field(default=2400, ge=-4800, le=9600)
    phrase_memory: int = Field(default=3, ge=0, le=64)


class EuclideanRhythmRequest(BaseModel):
    steps: int = Field(ge=1, le=256)
    pulses: int = Field(ge=0, le=256)
    rotation: int = 0


class RhythmStateGraphRequest(BaseModel):
    steps: int = Field(ge=1, le=12)


class PhaseShiftRequest(BaseModel):
    patterns: list[list[int]] = Field(min_length=1, max_length=16)
    length: int = Field(ge=1, le=4096)
    phases: list[int] | None = None


class HumanizeRequest(BaseModel):
    pattern: list[int] = Field(min_length=1, max_length=1024)
    seed: int = 0
    timing_amount_ms: float = Field(default=12, ge=0, le=100)
    velocity_amount: int = Field(default=10, ge=0, le=127)
    base_velocity: int = Field(default=100, ge=1, le=127)


class RenderEventRequest(BaseModel):
    ratio: str = Field(pattern=r"^\d+/\d+$")
    start_seconds: float = Field(ge=0, le=120)
    duration_seconds: float = Field(gt=0, le=120)
    velocity: int = Field(default=100, ge=1, le=127)


class RenderRequest(BaseModel):
    events: list[RenderEventRequest] = Field(max_length=256)
    base_frequency: float = Field(default=220, ge=20, le=2000)
    waveform: Literal["sine", "saw", "square", "triangle", "additive"] = "sine"
    attack_seconds: float = Field(default=0.02, gt=0, le=10)
    decay_seconds: float = Field(default=0.14, gt=0, le=10)
    sustain_level: float = Field(default=0.65, ge=0, le=1)
    release_seconds: float = Field(default=0.28, gt=0, le=10)
    sample_rate: int = Field(default=22_050, ge=8000, le=96_000)
    delay_seconds: float = Field(default=0, ge=0, le=5)
    reverb_amount: float = Field(default=0, ge=0, le=1)


class MidiNoteRequest(BaseModel):
    ratio: str = Field(pattern=r"^\d+/\d+$")
    start_beats: float = Field(ge=0, le=10_000)
    duration_beats: float = Field(gt=0, le=10_000)
    velocity: int = Field(default=100, ge=1, le=127)


class MidiRequest(BaseModel):
    notes: list[MidiNoteRequest] = Field(max_length=4096)
    base_frequency: float = Field(default=220, ge=20, le=2000)
    ticks_per_beat: int = Field(default=480, ge=24, le=960)
    pitch_bend: bool = False
    pitch_bend_range_semitones: int = Field(default=2, ge=1, le=48)


class RhythmMidiRequest(BaseModel):
    pattern: list[int] = Field(min_length=1, max_length=1024)
    note: int = Field(default=36, ge=0, le=127)
    velocity: int = Field(default=100, ge=1, le=127)
    velocities: list[int] | None = None
    steps_per_beat: int = Field(default=4, ge=1, le=16)
    ticks_per_beat: int = Field(default=480, ge=24, le=960)

    @field_validator("pattern")
    @classmethod
    def pattern_must_be_binary(cls, value: list[int]) -> list[int]:
        if any(step not in {0, 1} for step in value):
            raise ValueError("pattern must contain only zeros and ones")
        return value

    @field_validator("velocities")
    @classmethod
    def velocities_must_match_pattern(cls, values: list[int] | None) -> list[int] | None:
        if values is not None and any(not 0 <= velocity <= 127 for velocity in values):
            raise ValueError("velocities must be between 0 and 127")
        return values

    def velocities_for(self) -> list[int]:
        if self.velocities is None:
            return [self.velocity] * len(self.pattern)
        if len(self.velocities) != len(self.pattern):
            raise ValueError("velocities must match the pattern length")
        return [velocity or self.velocity for velocity in self.velocities]


class JsonExportRequest(BaseModel):
    name: str = Field(default="Pure Intonation Composition", min_length=1, max_length=80)
    composition: dict[str, object]
