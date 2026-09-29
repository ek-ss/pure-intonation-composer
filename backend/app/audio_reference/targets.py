"""Executable-target registry for reference-audio analysis.

A target names the generation pipeline an audio-derived profile patch will be
validated against.  Per spec section 1: the initial executable target is the
existing 3D full-song manifest; the 5D piano v3 targets are registered but not
executable until that work lands; the 2D piano v1 target is historical and
cannot be selected for new analysis.  Unknown manifest ids are rejected.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[2]
PROFILE_DIR = BACKEND / "songprogram_conformance" / "profiles"


class TargetError(ValueError):
    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(code if not detail else f"{code}: {detail}")
        self.code = code
        self.detail = detail


@dataclass(frozen=True)
class Target:
    manifest_id: str
    executable: bool
    dimensions: int
    composition_profile_path: Path | None
    generation_manifest_path: Path | None
    reason: str | None = None


TARGETS: dict[str, Target] = {
    "full-song-generation-v1": Target(
        manifest_id="full-song-generation-v1",
        executable=True,
        dimensions=3,
        composition_profile_path=PROFILE_DIR / "composition_generation_v2.json",
        generation_manifest_path=PROFILE_DIR / "full_song_generation_v1.json",
    ),
    "piano-solo-v3-octave": Target(
        manifest_id="piano-solo-v3-octave",
        executable=False,
        dimensions=5,
        composition_profile_path=None,
        generation_manifest_path=None,
        reason="piano v3 (5D cadence-driven) not yet implemented; registered for future use",
    ),
    "piano-solo-v3-tritave": Target(
        manifest_id="piano-solo-v3-tritave",
        executable=False,
        dimensions=5,
        composition_profile_path=None,
        generation_manifest_path=None,
        reason="piano v3 (5D cadence-driven) not yet implemented; registered for future use",
    ),
    "piano-solo-v1": Target(
        manifest_id="piano-solo-v1",
        executable=False,
        dimensions=2,
        composition_profile_path=None,
        generation_manifest_path=None,
        reason="historical 2D target; not selectable for new analysis",
    ),
}


def resolve_target(manifest_id: str) -> Target:
    if manifest_id not in TARGETS:
        known = ", ".join(sorted(TARGETS))
        raise TargetError("TARGET_UNKNOWN", f"{manifest_id} (known: {known})")
    return TARGETS[manifest_id]


def require_executable(target: Target) -> None:
    if not target.executable:
        raise TargetError("TARGET_NOT_EXECUTABLE", target.reason or target.manifest_id)
