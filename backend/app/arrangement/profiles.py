from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

PROFILE_SCHEMA_VERSION = "1.0.0"

SECTION_ROLES = (
    "intro",
    "verse",
    "pre_chorus",
    "chorus",
    "bridge",
    "breakdown",
    "drop",
    "outro",
)

ROLE_ALIASES = {
    "opening": "intro",
    "field": "verse",
    "bloom": "chorus",
    "dissolve": "outro",
}


def canonical_role(role: str) -> str:
    """Map profile-specific section aliases onto the structural roles."""
    return ROLE_ALIASES.get(role, role)


class SectionTemplate(BaseModel):
    role: str
    bars: int = Field(ge=1, le=64)
    energy_start: float = Field(ge=0, le=1)
    energy_end: float = Field(ge=0, le=1)
    harmony_density: float = Field(default=0.5, ge=0.1, le=1)

    @field_validator("role")
    @classmethod
    def role_must_be_known(cls, value: str) -> str:
        if value not in SECTION_ROLES and value not in ROLE_ALIASES:
            raise ValueError(
                f"unknown section role '{value}'; expected one of "
                f"{', '.join(SECTION_ROLES)} or an alias {', '.join(ROLE_ALIASES)}"
            )
        return value


class HarmonyWeights(BaseModel):
    voice_leading: float = Field(default=1.0, ge=0, le=4)
    root_motion: float = Field(default=0.6, ge=0, le=4)
    complexity: float = Field(default=0.5, ge=0, le=4)
    repetition: float = Field(default=0.4, ge=0, le=4)
    section_energy: float = Field(default=0.8, ge=0, le=4)
    cadence: float = Field(default=0.7, ge=0, le=4)
    common_tone: float = Field(default=0.6, ge=0, le=4)
    motif: float = Field(default=0.5, ge=0, le=4)


class HarmonyStyle(BaseModel):
    weights: HarmonyWeights = HarmonyWeights()
    preferred_tags: list[str] = Field(default_factory=list, max_length=16)
    avoid_tags: list[str] = Field(default_factory=list, max_length=16)
    chord_size_preference: int = Field(default=3, ge=2, le=6)
    cadence_stability: float = Field(default=0.5, ge=0, le=1)
    max_root_motion_cents: float = Field(default=700, gt=0, le=1200)


class RhythmStyle(BaseModel):
    drums: bool = True
    half_time: bool = False
    fills: bool = True
    crash_on_section: bool = False
    density: float = Field(default=0.5, ge=0.05, le=0.95)
    syncopation: float = Field(default=0.3, ge=0, le=1)


class PartStyle(BaseModel):
    role: Literal["drums", "bass", "harmony", "melody", "texture"]
    instrument: str = Field(min_length=1, max_length=60)
    register_low: float = Field(gt=0, le=16)
    register_high: float = Field(gt=0, le=16)
    density: float = Field(default=0.5, ge=0.02, le=0.95)
    gate: float = Field(default=0.9, gt=0, le=4)
    waveform: str = Field(default="saw")
    enabled: bool = True

    @field_validator("waveform")
    @classmethod
    def waveform_must_be_known(cls, value: str) -> str:
        allowed = {"sine", "saw", "square", "triangle", "additive"}
        if value not in allowed:
            raise ValueError(f"unknown waveform '{value}'; expected one of {', '.join(sorted(allowed))}")
        return value


class GenreProfile(BaseModel):
    id: str = Field(min_length=1, max_length=40, pattern=r"^[a-z0-9][a-z0-9_-]*$")
    display_name: str = Field(min_length=1, max_length=80)
    schema_version: str = Field(default=PROFILE_SCHEMA_VERSION, max_length=20)
    tempo_range: tuple[float, float]
    allowed_meters: list[int] = Field(min_length=1, max_length=4)
    default_form: list[SectionTemplate] = Field(min_length=1, max_length=32)
    harmony: HarmonyStyle = HarmonyStyle()
    rhythm: RhythmStyle = RhythmStyle()
    parts: list[PartStyle] = Field(min_length=1, max_length=8)
    render: dict[str, Any] = Field(default_factory=dict)

    @field_validator("tempo_range")
    @classmethod
    def tempo_range_must_be_ordered(cls, value: tuple[float, float]) -> tuple[float, float]:
        low, high = value
        if not 30 <= low <= high <= 240:
            raise ValueError("tempo_range must satisfy 30 <= low <= high <= 240")
        return value

    @field_validator("allowed_meters")
    @classmethod
    def meters_must_be_valid(cls, value: list[int]) -> list[int]:
        if any(meter not in {2, 3, 4, 6} for meter in value):
            raise ValueError("allowed_meters entries must be one of 2, 3, 4, 6")
        return value

    @field_validator("parts")
    @classmethod
    def part_registers_must_be_ordered(cls, value: list[PartStyle]) -> list[PartStyle]:
        roles: set[str] = set()
        for part in value:
            if part.register_low >= part.register_high:
                raise ValueError(f"part '{part.role}' register_low must be below register_high")
            if part.role in roles:
                raise ValueError(f"duplicate part role '{part.role}'")
            roles.add(part.role)
        return value

    def part_for(self, role: str) -> PartStyle | None:
        return next((part for part in self.parts if part.role == role), None)


_POP = {
    "id": "pop",
    "display_name": "Pop",
    "tempo_range": (90.0, 130.0),
    "allowed_meters": [4],
    "default_form": [
        {"role": "intro", "bars": 2, "energy_start": 0.3, "energy_end": 0.4, "harmony_density": 0.5},
        {"role": "verse", "bars": 4, "energy_start": 0.45, "energy_end": 0.55, "harmony_density": 0.5},
        {"role": "chorus", "bars": 4, "energy_start": 0.75, "energy_end": 0.9, "harmony_density": 0.6},
        {"role": "verse", "bars": 4, "energy_start": 0.5, "energy_end": 0.6, "harmony_density": 0.5},
        {"role": "chorus", "bars": 4, "energy_start": 0.8, "energy_end": 0.95, "harmony_density": 0.6},
        {"role": "outro", "bars": 2, "energy_start": 0.5, "energy_end": 0.2, "harmony_density": 0.4},
    ],
    "harmony": {
        "preferred_tags": ["stable"],
        "chord_size_preference": 3,
        "cadence_stability": 0.7,
        "weights": {"motif": 0.9, "repetition": 0.2, "cadence": 0.9},
    },
    "rhythm": {"density": 0.55, "syncopation": 0.3},
    "parts": [
        {"role": "drums", "instrument": "drum kit", "register_low": 0.25, "register_high": 1.0,
         "density": 0.6, "waveform": "square"},
        {"role": "bass", "instrument": "electric bass", "register_low": 0.4, "register_high": 1.0,
         "density": 0.55, "waveform": "triangle"},
        {"role": "harmony", "instrument": "comping keys", "register_low": 1.0, "register_high": 3.0,
         "density": 0.45, "gate": 0.85, "waveform": "saw"},
        {"role": "melody", "instrument": "lead voice", "register_low": 1.5, "register_high": 4.0,
         "density": 0.5, "waveform": "additive"},
    ],
}

_AMBIENT = {
    "id": "ambient",
    "display_name": "Ambient",
    "tempo_range": (50.0, 90.0),
    "allowed_meters": [4, 3],
    "default_form": [
        {"role": "opening", "bars": 4, "energy_start": 0.15, "energy_end": 0.3, "harmony_density": 0.2},
        {"role": "field", "bars": 8, "energy_start": 0.3, "energy_end": 0.45, "harmony_density": 0.2},
        {"role": "bloom", "bars": 8, "energy_start": 0.45, "energy_end": 0.65, "harmony_density": 0.25},
        {"role": "dissolve", "bars": 4, "energy_start": 0.4, "energy_end": 0.1, "harmony_density": 0.15},
    ],
    "harmony": {
        "preferred_tags": ["stable", "open", "color"],
        "chord_size_preference": 3,
        "cadence_stability": 0.1,
        "max_root_motion_cents": 500,
        "weights": {"voice_leading": 1.4, "common_tone": 1.2, "cadence": 0.1, "motif": 0.3},
    },
    "rhythm": {"drums": False, "density": 0.2, "syncopation": 0.1, "fills": False},
    "parts": [
        {"role": "bass", "instrument": "low drone", "register_low": 0.25, "register_high": 0.75,
         "density": 0.15, "gate": 2.5, "waveform": "sine"},
        {"role": "harmony", "instrument": "pad", "register_low": 1.0, "register_high": 4.0,
         "density": 0.2, "gate": 2.2, "waveform": "additive"},
        {"role": "melody", "instrument": "slow lead", "register_low": 1.5, "register_high": 4.0,
         "density": 0.2, "gate": 1.6, "waveform": "sine"},
        {"role": "texture", "instrument": "texture layer", "register_low": 2.0, "register_high": 5.0,
         "density": 0.1, "gate": 2.8, "waveform": "triangle"},
    ],
}

_ALTERNATIVE_ROCK = {
    "id": "alternative_rock",
    "display_name": "Alternative Rock",
    "tempo_range": (80.0, 160.0),
    "allowed_meters": [4],
    "default_form": [
        {"role": "intro", "bars": 2, "energy_start": 0.5, "energy_end": 0.6, "harmony_density": 0.5},
        {"role": "verse", "bars": 4, "energy_start": 0.55, "energy_end": 0.65, "harmony_density": 0.5},
        {"role": "chorus", "bars": 4, "energy_start": 0.85, "energy_end": 0.95, "harmony_density": 0.5},
        {"role": "verse", "bars": 4, "energy_start": 0.55, "energy_end": 0.65, "harmony_density": 0.5},
        {"role": "chorus", "bars": 4, "energy_start": 0.85, "energy_end": 0.95, "harmony_density": 0.5},
        {"role": "bridge", "bars": 2, "energy_start": 0.5, "energy_end": 0.7, "harmony_density": 0.5},
        {"role": "chorus", "bars": 4, "energy_start": 0.9, "energy_end": 1.0, "harmony_density": 0.5},
        {"role": "outro", "bars": 2, "energy_start": 0.7, "energy_end": 0.3, "harmony_density": 0.5},
    ],
    "harmony": {
        "preferred_tags": ["power", "open", "stable"],
        "chord_size_preference": 2,
        "cadence_stability": 0.5,
        "weights": {"voice_leading": 0.5, "root_motion": 0.9, "complexity": 0.8, "motif": 0.8},
    },
    "rhythm": {"density": 0.7, "syncopation": 0.25, "crash_on_section": True},
    "parts": [
        {"role": "drums", "instrument": "drum kit", "register_low": 0.25, "register_high": 1.0,
         "density": 0.7, "waveform": "square"},
        {"role": "bass", "instrument": "electric bass", "register_low": 0.4, "register_high": 1.0,
         "density": 0.65, "waveform": "saw"},
        {"role": "harmony", "instrument": "rhythm guitar role", "register_low": 1.0,
         "register_high": 2.5, "density": 0.6, "gate": 0.6, "waveform": "saw"},
        {"role": "melody", "instrument": "lead role", "register_low": 1.5, "register_high": 4.0,
         "density": 0.45, "waveform": "square"},
    ],
}

_FUTURE_BASS = {
    "id": "future_bass",
    "display_name": "Future Bass",
    "tempo_range": (130.0, 160.0),
    "allowed_meters": [4],
    "default_form": [
        {"role": "intro", "bars": 4, "energy_start": 0.3, "energy_end": 0.45, "harmony_density": 0.5},
        {"role": "verse", "bars": 4, "energy_start": 0.5, "energy_end": 0.7, "harmony_density": 0.5},
        {"role": "drop", "bars": 4, "energy_start": 0.9, "energy_end": 1.0, "harmony_density": 0.75},
        {"role": "verse", "bars": 4, "energy_start": 0.5, "energy_end": 0.7, "harmony_density": 0.5},
        {"role": "drop", "bars": 4, "energy_start": 0.95, "energy_end": 1.0, "harmony_density": 0.75},
        {"role": "outro", "bars": 2, "energy_start": 0.5, "energy_end": 0.2, "harmony_density": 0.4},
    ],
    "harmony": {
        "preferred_tags": ["color", "dense", "suspended"],
        "chord_size_preference": 4,
        "cadence_stability": 0.4,
        "weights": {"complexity": 0.3, "section_energy": 1.2, "motif": 0.7},
    },
    "rhythm": {"density": 0.65, "syncopation": 0.6, "half_time": True, "crash_on_section": True},
    "parts": [
        {"role": "drums", "instrument": "trap-influenced drums", "register_low": 0.25,
         "register_high": 1.0, "density": 0.65, "waveform": "square"},
        {"role": "bass", "instrument": "sub bass", "register_low": 0.25, "register_high": 0.75,
         "density": 0.5, "gate": 1.2, "waveform": "sine"},
        {"role": "harmony", "instrument": "chord stack", "register_low": 1.5, "register_high": 4.0,
         "density": 0.55, "gate": 0.5, "waveform": "saw"},
        {"role": "melody", "instrument": "lead chop", "register_low": 2.0, "register_high": 5.0,
         "density": 0.4, "gate": 0.5, "waveform": "additive"},
    ],
    "render": {"sidechain_pump": {"amount": 0.6, "rate": "1/4", "target": "harmony"}},
}

_BUILTINS = (dict(_POP), dict(_AMBIENT), dict(_ALTERNATIVE_ROCK), dict(_FUTURE_BASS))


def builtin_profiles() -> list[GenreProfile]:
    return [GenreProfile.model_validate(payload) for payload in _BUILTINS]


def resolve_profile(profile: str | dict[str, Any]) -> GenreProfile:
    """Resolve a profile name or an inline profile object, with actionable errors."""
    if isinstance(profile, dict):
        try:
            return GenreProfile.model_validate(profile)
        except ValueError as error:
            raise ValueError(f"invalid inline genre profile: {error}") from error
    for candidate in builtin_profiles():
        if candidate.id == profile:
            return candidate
    available = ", ".join(candidate.id for candidate in builtin_profiles())
    raise ValueError(f"unknown genre profile '{profile}'; available profiles: {available}")


def profile_summaries() -> list[dict[str, Any]]:
    summaries = []
    for profile in builtin_profiles():
        summaries.append(
            {
                "id": profile.id,
                "display_name": profile.display_name,
                "schema_version": profile.schema_version,
                "tempo_range": list(profile.tempo_range),
                "allowed_meters": profile.allowed_meters,
                "form_roles": [section.role for section in profile.default_form],
                "drums": profile.rhythm.drums,
                "half_time": profile.rhythm.half_time,
                "preferred_tags": profile.harmony.preferred_tags,
                "parts": [part.role for part in profile.parts],
            }
        )
    return summaries
