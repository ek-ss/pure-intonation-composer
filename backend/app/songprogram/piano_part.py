"""A separate, chord-aware piano voice for generated full songs."""

from __future__ import annotations

import copy
import hashlib
import math
from typing import Any

from .search import canonical_bytes

PIANO_STYLES = ("none", "ostinato", "obbligato", "mixed")
_PATTERNS = {
    "ostinato": ((0, 300, 0), (480, 300, 1), (960, 300, 2), (1440, 300, 1)),
    "obbligato": ((2160, 380, 2), (2880, 300, 1), (3360, 260, 0)),
}
_OBBLIGATO_FUNCTIONS = {"statement", "arrival", "return"}


def add_piano_part(program: dict[str, Any], plan: dict[str, Any], style: str) -> dict[str, Any]:
    """Add four shared materials and a section-specific piano realization.

    The renderer/Program protocol uses ``texture`` for this independent pitched
    track; its track ID and instrument distinguish the piano from other textures.
    """
    if style not in PIANO_STYLES:
        raise ValueError("PIANO_STYLE_INVALID")
    result = copy.deepcopy(program)
    if style == "none":
        return result
    if any(track["id"] == "trk_piano" for track in result["tracks"]):
        raise ValueError("PIANO_TRACK_ALREADY_EXISTS")
    if (len(result["tracks"]) + 1 > result["limits"]["max_tracks"]
            or len(result["materials"]) + 4 > result["limits"]["max_materials"]
            or len(result["realizations"]) + len(plan["sections"]) > result["limits"]["max_realizations"]):
        raise ValueError("PIANO_PROGRAM_LIMIT_EXCEEDED")
    bar_ticks = result["clock"]["beats_per_bar"] * result["clock"]["ticks_per_beat"]
    result["tracks"].append({
        "id": "trk_piano", "role": "texture", "instrument_id": "trial_piano",
        "register_millicents": [-1200000, 3600000], "maximum_polyphony": 4, "drum_map": None,
    })
    result["production"]["tracks"]["trk_piano"] = {"gain_q": 5200, "pan_q": 1200}
    for name, pattern in _PATTERNS.items():
        rhythm_id = f"rhy_piano_{name}"
        result["materials"].extend((
            {"id": rhythm_id, "kind": "rhythm_cell",
             "length_ticks": bar_ticks * (2 if name == "obbligato" else 1),
             "steps": [{"at_tick": onset * bar_ticks // 1920,
                        "duration_ticks": max(1, duration * bar_ticks // 1920),
                        "accent_q": 7500 if name == "ostinato" else 8500, "lane_id": None}
                       for onset, duration, _ in pattern]},
            {"id": f"mat_piano_{name}", "kind": "melody_intent", "rhythm_id": rhythm_id,
             "points": [{"relation": "chord_member", "member": member, "contour": "hold"}
                        for _, _, member in pattern], "mapping": "zip"},
        ))
    for ordinal, section in enumerate(plan["sections"]):
        section_style = ("obbligato" if section["function"] in _OBBLIGATO_FUNCTIONS
                         else "ostinato") if style == "mixed" else style
        if section_style == "obbligato" and section["bars"] % 2:
            raise ValueError("PIANO_OBBLIGATO_REQUIRES_EVEN_BARS")
        result["realizations"].append({
            "id": f"rea_piano_{ordinal:03d}", "section_id": section["section_id"],
            "track_id": "trk_piano", "material_id": f"mat_piano_{section_style}",
            "at_tick": 0, "repeat": (section["bars"] // 2 if section_style == "obbligato"
                                      else section["bars"]),
            "every_ticks": bar_ticks * (2 if section_style == "obbligato" else 1),
            "rhythm_transforms": [], "pitch_transforms": [],
            "velocity_scale_q": 6600 if section_style == "ostinato" else 7500,
            "gate_scale_q": 8500,
        })
    return result


def piano_catalog_entry(
    asset: dict[str, Any], maximum_polyphony: int, frequency_range: list[int]
) -> dict[str, Any]:
    return {
        "allowed_frequency_millihz": frequency_range, "asset": asset,
        "engine": "sample-linear-q31/v1", "gain_q14": 11000,
        "instrument_id": "trial_piano", "kind": "pitched",
        "loop": {"end_frame": 654, "mode": "forward", "start_frame": 436},
        "maximum_polyphony": maximum_polyphony, "release_frames": 320,
        "role": "texture", "root_frequency_millihz": 220000,
    }


def piano_samples() -> list[int]:
    """Two-cycle, bright-attack/soft-sustain reference piano-like timbre."""
    samples = []
    for frame in range(654):
        phase = 2 * math.pi * (frame % 218) / 218
        envelope = (0.85 - 0.35 * frame / 436) if frame < 436 else 0.5
        tone = (math.sin(phase) + 0.36 * math.sin(2 * phase)
                + 0.17 * math.sin(3 * phase) + 0.08 * math.sin(4 * phase))
        samples.append(round(2**30 * envelope * tone))
    return samples


def catalog_digest(catalog: dict[str, Any]) -> str:
    return "sha256:" + hashlib.sha256(
        b"cps.instrument-catalog/v1\0" + canonical_bytes(catalog)
    ).hexdigest()
