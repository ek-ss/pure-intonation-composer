"""Shared semantic descriptions for the Pure Intonation Vital presets."""

from __future__ import annotations

from typing import Any


def _profile(
    preset_id: str,
    name: str,
    roles: tuple[str, ...],
    midi_range: tuple[int, int],
    max_polyphony: int,
    articulation: str,
    spectral_band: str,
    section_affinity: tuple[str, ...],
    *,
    drum_note: int | None = None,
    preset_file: str | None = None,
) -> dict[str, Any]:
    return {
        "id": preset_id,
        "name": name,
        "roles": list(roles),
        "midi_range": list(midi_range),
        "max_polyphony": max_polyphony,
        "articulation": articulation,
        "spectral_band": spectral_band,
        "section_affinity": list(section_affinity),
        "tuning_policy": "fixed_trigger" if drum_note is not None else "per_note_exact",
        "drum_note": drum_note,
        "preset_file": preset_file,
    }


INSTRUMENT_PROFILES: dict[str, dict[str, Any]] = {
    "PI01": _profile(
        "PI01", "Clear Supersaw", ("harmony", "feature"), (48, 84), 5,
        "sustained", "wide", ("chorus", "drop", "final"),
    ),
    "PI02": _profile(
        "PI02", "Dream Chord", ("harmony", "pad"), (55, 91), 5,
        "sustained", "mid", ("verse", "bridge", "chorus"),
    ),
    "PI03": _profile(
        "PI03", "Air Pad", ("pad", "harmony"), (36, 84), 4,
        "slow", "wide", ("intro", "verse", "break", "outro"),
    ),
    "PI04": _profile(
        "PI04", "Gentle Pluck", ("arpeggio", "lead", "pulse"), (60, 96), 2,
        "short", "high_mid", ("verse", "pre", "a", "b"),
    ),
    "PI05": _profile(
        "PI05", "Warm Bass", ("bass",), (28, 52), 1,
        "sustained", "low", ("verse", "pre", "chorus", "drop", "final"),
    ),
    "PI06": _profile(
        "PI06", "Glass Bell", ("accent", "countermelody"), (72, 108), 2,
        "bell", "high", ("chorus", "drop", "final", "outro"),
    ),
    "PI07": _profile(
        "PI07", "Minimal Pulse", ("pulse", "rhythmic_harmony"), (48, 79), 4,
        "short", "mid", ("intro", "break", "minimal"),
    ),
    "PI08": _profile(
        "PI08", "Wide JI Pad", ("pad", "harmony", "feature"), (43, 84), 4,
        "sustained", "wide", ("intro", "bridge", "chorus", "final"),
    ),
    "PI09": _profile(
        "PI09", "Pop Kick", ("kick",), (36, 36), 1,
        "drum", "low", ("verse", "pre", "chorus", "drop", "final"), drum_note=36,
    ),
    "PI10": _profile(
        "PI10", "Pop Snare", ("snare",), (38, 38), 1,
        "drum", "mid", ("verse", "pre", "chorus", "drop", "final"), drum_note=38,
    ),
    "PI11": _profile(
        "PI11", "Pop Closed Hat", ("hat",), (42, 42), 1,
        "drum", "high", ("intro", "verse", "pre", "chorus", "drop", "final"), drum_note=42,
    ),
    "PI12": _profile(
        "PI12", "Pop Perc", ("perc", "accent"), (39, 39), 1,
        "drum", "high_mid", ("pre", "chorus", "drop", "bridge", "final"), drum_note=39,
    ),
    "PI13": _profile(
        "PI13", "Fifth Keys", ("harmony", "arpeggio"), (48, 84), 4,
        "keys", "mid", ("a", "verse", "intro"),
    ),
    "PI14": _profile(
        "PI14", "Minor Third Pluck", ("arpeggio", "harmony"), (55, 91), 3,
        "short", "high_mid", ("b", "pre", "bridge"),
    ),
    "PI15": _profile(
        "PI15", "13-Limit Chorus Lead", ("lead", "feature"), (60, 96), 3,
        "lead", "high_mid", ("chorus", "final"),
    ),
    "PI16": _profile(
        "PI16", "Vocal Guide", ("vocal", "lead"), (60, 96), 1,
        "monophonic", "high_mid", ("a", "b", "chorus", "final"),
    ),
    "PI17": _profile(
        "PI17", "Candy Pluck", ("arpeggio", "harmony", "pulse"), (55, 96), 4,
        "short", "high_mid", ("verse", "pre", "a", "b"),
    ),
    "PI18": _profile(
        "PI18", "Future Chord Stack", ("harmony", "feature"), (48, 96), 6,
        "sidechained", "wide", ("chorus", "drop", "final"),
    ),
    "PI19": _profile(
        "PI19", "Fractional Vocal Guide", ("vocal", "lead"), (60, 100), 1,
        "monophonic", "high_mid", ("verse", "pre", "chorus", "drop", "final"),
    ),
    "PI20": _profile(
        "PI20", "Minimal Pulse", ("pulse", "rhythmic_harmony"), (48, 96), 4,
        "short", "mid", ("intro", "minimal", "break"),
    ),
    "PI21": _profile(
        "PI21", "Sparkle Bell", ("accent", "countermelody"), (60, 108), 6,
        "bell", "high", ("chorus", "drop", "final"),
    ),
    "PI22": _profile(
        "PI22", "Fractional Piano", ("keys", "harmony", "arpeggio"), (48, 96), 8,
        "keys", "wide", ("intro", "verse", "a", "b", "chorus", "instrumental", "final"),
        preset_file="PI 22 Fractional Piano.vital",
    ),
}


STYLE_DEFAULT_PALETTES = {
    "fractional_pop": (
        "PI01", "PI04", "PI05", "PI06", "PI09", "PI10", "PI11", "PI12", "PI22",
    ),
    "fractional_jpop": (
        "PI05", "PI09", "PI10", "PI11", "PI12", "PI13", "PI14", "PI15", "PI16", "PI22",
    ),
    "kawaii_fractional_future_pop": (
        "PI05", "PI06", "PI09", "PI10", "PI11", "PI12", "PI17", "PI18", "PI19",
        "PI20", "PI21",
    ),
}


def public_instrument_profiles() -> list[dict[str, Any]]:
    """Return stable copies suitable for API clients."""
    return [dict(profile) for profile in INSTRUMENT_PROFILES.values()]
