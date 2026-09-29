from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.audio_reference.translation import (
    MAX_BARS,
    MAX_SECTIONS,
    MIN_BARS,
    MIN_TOTAL_BARS,
    MAX_TOTAL_BARS,
    TRANSITIONS,
    function_skeleton,
    map_sections_to_template,
    merge_profile_patch,
)

BACKEND = Path(__file__).resolve().parents[1]
PROFILE_PATH = BACKEND / "songprogram_conformance" / "profiles" / "composition_generation_v2.json"


def _profile() -> dict:
    return json.loads(PROFILE_PATH.read_text())


@pytest.mark.parametrize("count", [3, 4, 5, 6, 7, 8])
def test_function_skeleton_respects_the_transition_table(count: int) -> None:
    functions = function_skeleton(count)
    assert functions[0] == "opening"
    assert functions[-1] == "closure"
    for a, b in zip(functions, functions[1:]):
        assert b in TRANSITIONS[a], f"{a} -> {b} is not a legal transition"


def test_function_skeleton_rejects_out_of_range() -> None:
    with pytest.raises(ValueError):
        function_skeleton(2)
    with pytest.raises(ValueError):
        function_skeleton(9)


def test_map_sections_produces_a_valid_template() -> None:
    template = map_sections_to_template(
        section_beat_counts=[16, 24, 24, 16],
        beats_per_bar=4,
        energy_q14=[8000, 12000, 16384, 6000],
        density_q14=[4000, 8000, 12000, 3000],
    )
    assert template is not None
    assert len(template["sections"]) == 4
    total = sum(s["bars"] for s in template["sections"])
    assert MIN_TOTAL_BARS <= total <= MAX_TOTAL_BARS
    for section in template["sections"]:
        assert MIN_BARS <= section["bars"] <= MAX_BARS
        assert 0 <= section["energy_q"] <= 10_000
        assert 0 <= section["density_q"] <= 10_000
    # The loudest section (index 2) should map to the highest energy_q.
    energies = [s["energy_q"] for s in template["sections"]]
    assert energies.index(max(energies)) == 2


def test_map_sections_merges_when_over_the_section_bound() -> None:
    template = map_sections_to_template(
        section_beat_counts=[8] * 12,  # 12 sections > MAX_SECTIONS
        beats_per_bar=4,
        energy_q14=[8000] * 12,
        density_q14=[8000] * 12,
    )
    assert template is not None
    assert len(template["sections"]) <= MAX_SECTIONS


def test_map_sections_returns_none_when_irreconcilable() -> None:
    # A single tiny section cannot be split into the 3..8 bound.
    assert map_sections_to_template([2], 4, [8000], [8000]) is None


def test_merge_applies_settings_and_strips_hash() -> None:
    profile = _profile()
    patch = {
        "settings": [
            {
                "document": "composition_profile",
                "target_path": "/form_templates",
                "value": [
                    {
                        "template_id": "audio-derived",
                        "weight": 1,
                        "sections": [
                            {
                                "section_key": f"sec_{i:03d}",
                                "function": f,
                                "bars": b,
                                "energy_q": 5000,
                                "density_q": 5000,
                                "cadence_target": "continuation",
                                "foreground_state": "present",
                            }
                            for i, (f, b) in enumerate(
                                [("opening", 8), ("arrival", 8), ("closure", 8)]
                            )
                        ],
                    }
                ],
            }
        ]
    }
    merged, _manifest = merge_profile_patch(profile, None, patch)
    assert "profile_hash" not in merged
    assert merged["form_templates"][0]["template_id"] == "audio-derived"
    # The original profile object is not mutated.
    assert profile["form_templates"][0]["template_id"] != "audio-derived"
