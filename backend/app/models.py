from __future__ import annotations

from typing import Literal

from pydantic import AliasChoices, BaseModel, Field, field_validator, model_validator

from app.rhythm.drums import LayerSpec


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


class CompositionClockRequest(BaseModel):
    beats_per_bar: int = Field(default=4, ge=1, le=16)
    subdivisions_per_beat: int = Field(default=4, ge=1, le=16)
    bars: int = Field(default=8, ge=1, le=128)
    ticks_per_beat: int = Field(default=480, ge=24, le=960)
    tempo_bpm: float = Field(default=96, ge=20, le=400)

    @model_validator(mode="after")
    def ticks_must_fit_subdivisions(self) -> CompositionClockRequest:
        if self.ticks_per_beat % self.subdivisions_per_beat:
            raise ValueError("ticks_per_beat must be divisible by subdivisions_per_beat")
        if self.beats_per_bar * self.subdivisions_per_beat * self.bars > 4096:
            raise ValueError("composition clock must not exceed 4096 subdivisions")
        return self


class CompositionPitchesRequest(BaseModel):
    chords: list[list[str]] = Field(min_length=1, max_length=256)
    bass: list[str] = Field(default_factory=list, max_length=256)
    melody: list[list[str]] = Field(default_factory=list, max_length=8)
    transition_scores: list[float | None] = Field(default_factory=list, max_length=256)


class ComposeRhythmLayerRequest(BaseModel):
    name: str = Field(min_length=1, max_length=32)
    pattern: list[int] = Field(min_length=1, max_length=4096)
    velocities: list[int] | None = None
    phase_offsets: list[int] = Field(default_factory=list, max_length=128)

    @field_validator("pattern")
    @classmethod
    def compose_pattern_must_be_binary(cls, values: list[int]) -> list[int]:
        if any(value not in {0, 1} for value in values):
            raise ValueError("pattern must contain only zeros and ones")
        return values

    @field_validator("velocities")
    @classmethod
    def compose_velocities_must_be_valid(
        cls, values: list[int] | None
    ) -> list[int] | None:
        if values is not None and any(not 0 <= value <= 127 for value in values):
            raise ValueError("velocities must be between 0 and 127")
        return values

    def velocities_for(self) -> list[int]:
        if self.velocities is None:
            return [100 if active else 0 for active in self.pattern]
        if len(self.velocities) != len(self.pattern):
            raise ValueError("velocities must match the pattern length")
        return self.velocities


class ComposeRhythmMappingRequest(BaseModel):
    source_layer: str = Field(min_length=1, max_length=32)
    target: str = Field(min_length=1, max_length=40)
    policy: Literal[
        "fixed-index", "voice-led", "rotate-per-chord", "register-spread"
    ] = "fixed-index"
    overflow: Literal["drop", "wrap", "clamp"] = "drop"
    gate: float = Field(default=0.9, gt=0, le=16)
    register_octave: int = Field(default=0, ge=-4, le=4)
    velocity_scale: float = Field(default=1, gt=0, le=2)
    collision: Literal["merge", "retrigger", "stack"] = "merge"
    articulation: Literal["gate", "legato", "tie", "accent"] = "gate"

    @field_validator("target")
    @classmethod
    def target_must_be_supported(cls, value: str) -> str:
        if value in {"harmony", "bass", "mute"}:
            return value
        prefix, separator, index = value.partition(":")
        if (
            prefix not in {"melody", "chord_tone"}
            or separator != ":"
            or not index.isdigit()
        ):
            raise ValueError("target must be harmony, bass, mute, melody:i, or chord_tone:i")
        return value


class ComposeRhythmApplyRequest(BaseModel):
    clock: CompositionClockRequest = Field(default_factory=CompositionClockRequest)
    composition: CompositionPitchesRequest
    layers: list[ComposeRhythmLayerRequest] = Field(min_length=1, max_length=16)
    mappings: list[ComposeRhythmMappingRequest] = Field(min_length=1, max_length=64)
    chord_durations: list[int] | None = Field(default=None, max_length=256)


class ComposeRhythmGeneratorRequest(BaseModel):
    target: str = Field(min_length=1, max_length=40)
    strategy: Literal[
        "transition-aware", "semi-markov", "interlocking", "ratio-derived"
    ] = "transition-aware"
    profile: Literal["grounded", "interlocking", "sparse", "flowing"] = "grounded"
    density: float = Field(default=0.35, ge=0.02, le=0.95)
    syncopation: float = Field(default=0.35, ge=0, le=1)

    @field_validator("target")
    @classmethod
    def target_must_be_supported(cls, value: str) -> str:
        if value in {"harmony", "bass"}:
            return value
        prefix, separator, index = value.partition(":")
        if (
            prefix not in {"melody", "chord_tone"}
            or separator != ":"
            or not index.isdigit()
        ):
            raise ValueError(
                "target must be harmony, bass, melody:i, or chord_tone:i"
            )
        return value


class ComposeRhythmGenerateRequest(BaseModel):
    clock: CompositionClockRequest = Field(default_factory=CompositionClockRequest)
    composition: CompositionPitchesRequest
    strategy: Literal[
        "transition-aware", "semi-markov", "interlocking", "ratio-derived"
    ] = "transition-aware"
    profile: Literal["grounded", "interlocking", "sparse", "flowing"] = "grounded"
    density: float = Field(default=0.35, ge=0.02, le=0.95)
    syncopation: float = Field(default=0.35, ge=0, le=1)
    seed: int = 0
    generators: list[ComposeRhythmGeneratorRequest] | None = Field(
        default=None,
        min_length=1,
        max_length=16,
    )
    targets: list[str] = Field(
        default_factory=lambda: ["harmony", "bass", "melody:0"],
        min_length=1,
        max_length=16,
    )

    @field_validator("targets")
    @classmethod
    def targets_must_be_supported(cls, values: list[str]) -> list[str]:
        for value in values:
            if value in {"harmony", "bass"}:
                continue
            prefix, separator, index = value.partition(":")
            if (
                prefix not in {"melody", "chord_tone"}
                or separator != ":"
                or not index.isdigit()
            ):
                raise ValueError(
                    "targets must contain harmony, bass, melody:i, or chord_tone:i"
                )
        return values

    @field_validator("generators")
    @classmethod
    def generator_targets_must_be_unique(
        cls,
        values: list[ComposeRhythmGeneratorRequest] | None,
    ) -> list[ComposeRhythmGeneratorRequest] | None:
        if values is not None and len({value.target for value in values}) != len(values):
            raise ValueError("generator targets must be unique")
        return values


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
    events: list[RenderEventRequest] = Field(max_length=4096)
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


class DrumLayerRequest(BaseModel):
    name: str = Field(min_length=1, max_length=32)
    steps: int = Field(ge=1, le=64)
    pulses: int = Field(ge=0, le=64)
    rotation: int | None = None
    phase_increment: int = 0
    phase_update_bars: int = Field(default=4, ge=1, le=1024)
    base_velocity: int = Field(default=100, ge=1, le=127)

    @model_validator(mode="after")
    def pulses_must_not_exceed_steps(self) -> DrumLayerRequest:
        if self.pulses > self.steps:
            raise ValueError("pulses must not exceed steps")
        return self

    def to_spec(self) -> LayerSpec:
        return LayerSpec(
            name=self.name,
            steps=self.steps,
            pulses=self.pulses,
            rotation=self.rotation,
            phase_increment=self.phase_increment,
            phase_update_bars=self.phase_update_bars,
            base_velocity=self.base_velocity,
        )


class OptimizeRotationsRequest(BaseModel):
    layers: list[DrumLayerRequest] = Field(min_length=1, max_length=16)
    max_analysis_steps: int = Field(default=512, ge=1, le=4096)


class RhythmAnalyzeLayerRequest(BaseModel):
    name: str = Field(min_length=1, max_length=32)
    pattern: list[int] = Field(min_length=1, max_length=1024)

    @field_validator("pattern")
    @classmethod
    def pattern_must_be_binary(cls, value: list[int]) -> list[int]:
        if any(step not in {0, 1} for step in value):
            raise ValueError("pattern must contain only zeros and ones")
        return value


class RhythmAnalyzeRequest(BaseModel):
    layers: list[RhythmAnalyzeLayerRequest] = Field(min_length=1, max_length=16)
    max_analysis_steps: int = Field(default=512, ge=1, le=4096)


class DrumGenerateRequest(BaseModel):
    layers: list[DrumLayerRequest] = Field(min_length=1, max_length=16)
    bars: int = Field(default=8, ge=1, le=128)
    seed: int = 0
    optimize: bool = True
    max_analysis_steps: int = Field(default=512, ge=1, le=4096)


def _resolve_velocities(pattern: list[int], velocity: int, velocities: list[int] | None) -> list[int]:
    if velocities is None:
        return [velocity] * len(pattern)
    if len(velocities) != len(pattern):
        raise ValueError("velocities must match the pattern length")
    return [value or velocity for value in velocities]


class RhythmMidiLayerRequest(BaseModel):
    pattern: list[int] = Field(min_length=1, max_length=1024)
    note: int = Field(default=36, ge=0, le=127)
    velocity: int = Field(default=100, ge=1, le=127)
    velocities: list[int] | None = None

    @field_validator("pattern")
    @classmethod
    def pattern_must_be_binary(cls, value: list[int]) -> list[int]:
        if any(step not in {0, 1} for step in value):
            raise ValueError("pattern must contain only zeros and ones")
        return value

    @field_validator("velocities")
    @classmethod
    def velocities_must_be_valid(cls, values: list[int] | None) -> list[int] | None:
        if values is not None and any(not 0 <= velocity <= 127 for velocity in values):
            raise ValueError("velocities must be between 0 and 127")
        return values

    def velocities_for(self) -> list[int]:
        return _resolve_velocities(self.pattern, self.velocity, self.velocities)


class RhythmMidiRequest(BaseModel):
    pattern: list[int] | None = Field(default=None, min_length=1, max_length=1024)
    note: int = Field(default=36, ge=0, le=127)
    velocity: int = Field(default=100, ge=1, le=127)
    velocities: list[int] | None = None
    steps_per_beat: int = Field(default=4, ge=1, le=16)
    ticks_per_beat: int = Field(default=480, ge=24, le=960)
    cycles: int = Field(default=1, ge=1, le=128)
    layers: list[RhythmMidiLayerRequest] | None = Field(default=None, min_length=1, max_length=16)

    @field_validator("pattern")
    @classmethod
    def pattern_must_be_binary(cls, value: list[int] | None) -> list[int] | None:
        if value is not None and any(step not in {0, 1} for step in value):
            raise ValueError("pattern must contain only zeros and ones")
        return value

    @field_validator("velocities")
    @classmethod
    def velocities_must_match_pattern(cls, values: list[int] | None) -> list[int] | None:
        if values is not None and any(not 0 <= velocity <= 127 for velocity in values):
            raise ValueError("velocities must be between 0 and 127")
        return values

    def velocities_for(self) -> list[int]:
        if self.pattern is None:
            raise ValueError("pattern is required when layers are not provided")
        return _resolve_velocities(self.pattern, self.velocity, self.velocities)


class LatticeScaleRequest(BaseModel):
    generators: list[int] = Field(min_length=1, max_length=8)
    minimum: list[int]
    maximum: list[int]
    collision_policy: Literal["keep", "merge"] = "keep"


class LatticeHarmonyRequest(BaseModel):
    root: str = Field(pattern=r"^\d+/\d+$")
    generators: list[int] = Field(min_length=1, max_length=8)
    chord_vectors: list[list[int]] = Field(
        max_length=512,
        validation_alias=AliasChoices("chord_vectors", "differences"),
    )
    root_vector: list[int] | None = None


class LatticeChordRequest(BaseModel):
    root: str = Field(default="1/1", pattern=r"^\d+/\d+$")
    generators: list[int] = Field(min_length=1, max_length=8)
    allowed_differences: list[list[int]] = Field(min_length=1, max_length=64)
    tone_count: int = Field(default=3, ge=1, le=16)
    seed: int = 0
    minimum: list[int]
    maximum: list[int]


class LatticeWalkRequest(BaseModel):
    generators: list[int] = Field(min_length=1, max_length=8)
    start_vector: list[int]
    allowed_differences: list[list[int]] = Field(min_length=1, max_length=64)
    root: str = Field(default="1/1", pattern=r"^\d+/\d+$")
    chord_vectors: list[list[int]] = Field(
        default_factory=list,
        max_length=512,
        validation_alias=AliasChoices("chord_vectors", "harmony_differences"),
    )
    length: int = Field(default=16, ge=1, le=512)
    seed: int = 0
    minimum: list[int]
    maximum: list[int]
    boundary: Literal["stop", "reflect", "wrap", "resample"] = "reflect"


class LatticeProgressionRequest(BaseModel):
    generators: list[int] = Field(min_length=1, max_length=8)
    root: str = Field(default="1/1", pattern=r"^\d+/\d+$")
    start_vector: list[int]
    chord_vectors: list[list[int]] = Field(default_factory=list, max_length=512)
    progression_differences: list[list[int]] = Field(max_length=512)


class LatticeAnalyzeRequest(BaseModel):
    generators: list[int] = Field(min_length=1, max_length=8)
    vectors: list[list[int]] = Field(min_length=1, max_length=64)


class PrimeExplorerRequest(BaseModel):
    primes: list[int] = Field(default_factory=lambda: [3, 5, 7], min_length=1, max_length=5)
    exponent_limit: int = Field(default=2, ge=0, le=8)
    height_limit: int = Field(default=4, ge=0, le=32)
    tolerance_cents: float = Field(default=8, gt=0, le=100)
    target_count: int = Field(default=12, ge=1, le=64)


class PrimeChordRequest(PrimeExplorerRequest):
    tone_count: int = Field(default=3, ge=2, le=6)
    candidate_limit: int = Field(default=24, ge=1, le=128)


class PrimeProgressionRequest(BaseModel):
    chords: list[list[float]] = Field(min_length=2, max_length=64)

    @field_validator("chords")
    @classmethod
    def chord_voice_counts_must_match(cls, value: list[list[float]]) -> list[list[float]]:
        if not value[0] or len(value[0]) > 6 or any(len(chord) != len(value[0]) for chord in value):
            raise ValueError("chords must contain matching voice counts between 1 and 6")
        return value


class JsonExportRequest(BaseModel):
    name: str = Field(default="Pure Intonation Composition", min_length=1, max_length=80)
    composition: dict[str, object]
