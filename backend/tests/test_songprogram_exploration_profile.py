from __future__ import annotations

import copy
import json
from pathlib import Path

from app.songprogram.exploration_profile import (
    apply_profile,
    apply_profile_with_arrangement,
    profile_hash,
    selected_layout,
    symbolic_coverage,
    validate_profile,
)


PROFILE_DIR = Path(__file__).resolve().parents[1] / "songprogram_conformance" / "profiles"


def _profile(name: str = "song_preview_exploration_v1.json") -> dict:
    return json.loads((PROFILE_DIR / name).read_text())


def test_checked_profiles_are_closed_and_self_hashed() -> None:
    for name in (
        "song_preview_exploration_v1.json",
        "full_song_exploration_v1.json",
        "song_preview_exploration_v2.json",
        "full_song_exploration_v2.json",
    ):
        profile = _profile(name)
        validate_profile(profile)
        assert profile_hash(profile) == profile["profile_hash"]


def test_profile_owns_schedule_and_bounds_the_final_repeat() -> None:
    profile = _profile()
    structural = {
        "clock": {"beats_per_bar": 4, "ticks_per_beat": 480},
        "form": [{"id": "sec_000", "bars": 4}],
        "materials": [
            {
                "id": "rhy_000",
                "kind": "rhythm_cell",
                "steps": [{"at_tick": 1200, "duration_ticks": 120}],
            },
            {
                "id": "mat_000",
                "kind": "direct_vector_cell",
                "rhythm_id": "rhy_000",
            },
        ],
        "realizations": [
            {
                "id": "rea_000",
                "section_id": "sec_000",
                "material_id": "mat_000",
                "role": "bass",
                "rhythm_transforms": [{"op": "rotate", "ticks": 1680}],
            }
        ],
    }
    lowered = apply_profile(structural, profile, 11)
    realization = lowered["realizations"][0]
    step = lowered["materials"][0]["steps"][0]
    assert realization["rhythm_transforms"] == []
    assert realization["repeat"] == 4
    final_onset = (
        realization["at_tick"]
        + (realization["repeat"] - 1) * realization["every_ticks"]
        + step["at_tick"]
    )
    assert final_onset + step["duration_ticks"] <= 4 * 4 * 480


def test_full_song_layout_is_deterministic_and_in_requested_range() -> None:
    profile = _profile("full_song_exploration_v1.json")
    first = [selected_layout(profile, seed) for seed in range(32)]
    second = [selected_layout(profile, seed) for seed in range(32)]
    assert first == second
    assert {row["section_count"] * row["bars_per_section"] for row in first} <= {
        28,
        32,
        40,
    }


def test_single_role_binding_specializes_shared_material_to_meet_role_floor() -> None:
    profile = _profile()
    structural = {
        "clock": {"beats_per_bar": 4, "ticks_per_beat": 480},
        "form": [{"id": "sec_000", "bars": 4}],
        "materials": [
            {
                "id": "rhy_000",
                "kind": "rhythm_cell",
                "steps": [{"at_tick": 0, "duration_ticks": 120}],
            },
            {
                "id": "mat_000",
                "kind": "direct_vector_cell",
                "rhythm_id": "rhy_000",
            },
            {
                "id": "rhy_001",
                "kind": "rhythm_cell",
                "steps": [{"at_tick": 0, "duration_ticks": 120}],
            },
            {
                "id": "mat_001",
                "kind": "harmony_intent_cell",
                "rhythm_id": "rhy_001",
            },
        ],
        "realizations": [
            {
                "id": "rea_b",
                "section_id": "sec_000",
                "material_id": "mat_000",
                "role": "bass",
                "rhythm_transforms": [],
            },
            {
                "id": "rea_t",
                "section_id": "sec_000",
                "material_id": "mat_000",
                "role": "texture",
                "rhythm_transforms": [],
            },
            {
                "id": "rea_h",
                "section_id": "sec_000",
                "material_id": "mat_001",
                "role": "harmony",
                "rhythm_transforms": [],
            },
        ],
    }
    lowered = apply_profile(structural, profile, 7)
    assert {row["role"] for row in lowered["realizations"]} == {
        "bass",
        "harmony",
        "texture",
    }
    owners: dict[str, set[str]] = {}
    for row in lowered["realizations"]:
        owners.setdefault(row["material_id"], set()).add(row["role"])
    assert all(len(roles) == 1 for roles in owners.values())


def test_symbolic_coverage_uses_section_relative_event_time() -> None:
    profile = _profile()
    project = {
        "clock": {"beats_per_bar": 4, "ticks_per_beat": 480},
        "form": [{"id": "sec_000", "role": "drop", "start_bar": 4, "bars": 4}],
        "tracks": [
            {"id": "trk_d", "role": "drums"},
            {"id": "trk_b", "role": "bass"},
            {"id": "trk_h", "role": "harmony"},
        ],
        "events": [
            {
                "section_id": "sec_000",
                "track_id": track,
                "start_tick": 4 * 1920,
                "duration_ticks": 4 * 1920,
            }
            for track in ("trk_d", "trk_b", "trk_h")
        ],
    }
    report = symbolic_coverage(project, profile)
    assert report["overall_coverage_basis_points"] == 10000
    assert report["maximum_empty_bar_run"] == 0
    assert report["sounding_role_count"] == 3
    assert report["status"] == "passed"


def test_v2_arrangement_is_deterministic_and_has_section_contrast() -> None:
    profile = _profile("song_preview_exploration_v2.json")
    structural = {
        "program_id": "sp_arrangement_test",
        "clock": {"beats_per_bar": 4, "ticks_per_beat": 480},
        "form": [
            {"id": "sec_000", "role": "intro", "bars": 4, "development_stage": "introduce"},
            {"id": "sec_001", "role": "drop", "bars": 4, "development_stage": "contrast"},
            {"id": "sec_002", "role": "outro", "bars": 4, "development_stage": "close"},
        ],
        "materials": [
            {
                "id": "rhy_000",
                "kind": "rhythm_cell",
                "steps": [{"at_tick": 0, "duration_ticks": 120}],
            },
            {"id": "mat_000", "kind": "direct_vector_cell", "rhythm_id": "rhy_000"},
            {
                "id": "rhy_001",
                "kind": "rhythm_cell",
                "steps": [{"at_tick": 0, "duration_ticks": 120}],
            },
            {"id": "mat_001", "kind": "harmony_intent_cell", "rhythm_id": "rhy_001"},
        ],
        "realizations": [
            {
                "id": "rea_b",
                "section_id": "sec_000",
                "material_id": "mat_000",
                "role": "bass",
                "rhythm_transforms": [],
                "velocity_scale_q": 10000,
            },
            {
                "id": "rea_t",
                "section_id": "sec_000",
                "material_id": "mat_000",
                "role": "texture",
                "rhythm_transforms": [],
                "velocity_scale_q": 10000,
            },
            {
                "id": "rea_h",
                "section_id": "sec_000",
                "material_id": "mat_001",
                "role": "harmony",
                "rhythm_transforms": [],
                "velocity_scale_q": 10000,
            },
        ],
    }
    first_program, first_plan = apply_profile_with_arrangement(structural, profile, 19)
    second_program, second_plan = apply_profile_with_arrangement(structural, profile, 19)
    assert (first_program, first_plan) == (second_program, second_plan)
    assert first_plan is not None
    assert first_plan["status"] == "passed"
    assert first_plan["sounding_role_count"] >= 3
    assert first_plan["distinct_role_mask_count"] >= 2
    plans = {item["section_role"]: item for item in first_plan["section_plans"]}
    assert len({role for item in first_plan["section_plans"] for role in item["active_roles"]}) >= 3
    assert len(plans["drop"]["active_roles"]) >= len(plans["intro"]["active_roles"])
    assert plans["drop"]["velocity_scale_q"] > plans["intro"]["velocity_scale_q"]
    realized_sections = {row["section_id"] for row in first_program["realizations"]}
    assert realized_sections == {"sec_000", "sec_001", "sec_002"}

    impossible = copy.deepcopy(profile)
    impossible["arrangement_policy"]["minimum_distinct_role_masks"] = 4
    impossible["profile_hash"] = profile_hash(impossible)
    _, rejected = apply_profile_with_arrangement(structural, impossible, 19)
    assert rejected is not None
    assert rejected["status"] == "rejected"
