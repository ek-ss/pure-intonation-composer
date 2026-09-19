from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from app.songprogram.exploration_profile import (
    apply_profile,
    apply_profile_with_arrangement,
    profile_hash,
    selected_layout,
    symbolic_coverage,
    validate_arrangement_plan,
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


def test_odd_section_normalizes_bed_period_without_tail_gap() -> None:
    profile = _profile("full_song_exploration_v1.json")
    structural = {
        "clock": {"beats_per_bar": 4, "ticks_per_beat": 480},
        "form": [{"id": "sec_000", "bars": 5}],
        "materials": [
            {
                "id": "rhy_000",
                "kind": "rhythm_cell",
                "steps": [{"at_tick": 0, "duration_ticks": 120}],
            },
            {
                "id": "mat_000",
                "kind": "harmony_intent_cell",
                "rhythm_id": "rhy_000",
            },
        ],
        "realizations": [
            {
                "id": "rea_000",
                "section_id": "sec_000",
                "material_id": "mat_000",
                "role": "harmony",
                "rhythm_transforms": [],
            }
        ],
    }
    lowered = apply_profile(structural, profile, 4)
    realization = lowered["realizations"][0]
    step = lowered["materials"][0]["steps"][0]
    assert realization["every_ticks"] == 1920
    assert realization["repeat"] == 5
    assert step["duration_ticks"] == 1920


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
    validate_arrangement_plan(first_plan, first_program, profile)

    tampered = copy.deepcopy(first_plan)
    tampered["section_plans"][0]["development_stage"] = "close"
    with pytest.raises(ValueError, match="ARRANGEMENT_PLAN_INVALID"):
        validate_arrangement_plan(tampered, first_program, profile)

    impossible = copy.deepcopy(profile)
    impossible["arrangement_policy"]["minimum_distinct_role_masks"] = 4
    impossible["profile_hash"] = profile_hash(impossible)
    _, rejected = apply_profile_with_arrangement(structural, impossible, 19)
    assert rejected is not None
    assert rejected["status"] == "rejected"


def _full_song_structural() -> dict:
    return {
        "program_id": "sp_recall_transform_test",
        "clock": {"beats_per_bar": 4, "ticks_per_beat": 480},
        "form": [
            {"id": "sec_000", "role": "intro", "bars": 4, "development_stage": "introduce"},
            {"id": "sec_001", "role": "verse", "bars": 4, "development_stage": "develop"},
            {"id": "sec_002", "role": "drop", "bars": 4, "development_stage": "contrast"},
        ],
        "materials": [
            {
                "id": "rhy_000",
                "kind": "rhythm_cell",
                "length_ticks": 1920,
                "steps": [
                    {"at_tick": 0, "duration_ticks": 120},
                    {"at_tick": 480, "duration_ticks": 120},
                ],
            },
            {"id": "mat_000", "kind": "direct_vector_cell", "rhythm_id": "rhy_000"},
            {
                "id": "rhy_001",
                "kind": "rhythm_cell",
                "length_ticks": 1920,
                "steps": [{"at_tick": 0, "duration_ticks": 120}],
            },
            {"id": "mat_001", "kind": "direct_vector_cell", "rhythm_id": "rhy_001"},
            {
                "id": "rhy_002",
                "kind": "rhythm_cell",
                "length_ticks": 1920,
                "steps": [{"at_tick": 0, "duration_ticks": 120}],
            },
            {"id": "mat_002", "kind": "harmony_intent_cell", "rhythm_id": "rhy_002"},
        ],
        "realizations": [
            {
                "id": f"rea_{role}",
                "section_id": "sec_000",
                "material_id": material,
                "role": role,
                "rhythm_transforms": [],
                "velocity_scale_q": 10000,
            }
            for role, material in (
                ("bass", "mat_000"),
                ("drums", "mat_001"),
                ("harmony", "mat_002"),
            )
        ],
    }


def _assert_recall_transforms_valid(program: dict, profile: dict) -> None:
    ticks_per_bar = program["clock"]["beats_per_bar"] * program["clock"]["ticks_per_beat"]
    sections = {section["id"]: section for section in program["form"]}
    materials = {material["id"]: material for material in program["materials"]}
    allowed_amounts = [
        1920 // denominator
        for denominator in profile["recall_transform_policy"]["rotation_denominator_choices"]
    ]
    rotated_by_material: dict[str, int] = {}
    for realization in program["realizations"]:
        transforms = realization["rhythm_transforms"]
        if not transforms:
            continue
        assert len(transforms) == 1
        entry = transforms[0]
        assert set(entry) == {"op", "ticks"} and entry["op"] == "rotate"
        assert entry["ticks"] in allowed_amounts
        material_id = realization["material_id"]
        assert material_id not in rotated_by_material
        rotated_by_material[material_id] = entry["ticks"]
    role_by_material = {
        realization["material_id"]: realization["role"]
        for realization in program["realizations"]
    }
    materials_in_two_sections = {
        material_id
        for material_id, rows in _realizations_by_material(program).items()
        if len({row["section_id"] for row in rows}) >= 2
    }
    expected_rotated = {
        material_id
        for material_id in materials_in_two_sections
        if role_by_material[material_id] not in {"harmony", "texture"}
    }
    assert set(rotated_by_material) == expected_rotated
    for realization in program["realizations"]:
        material = materials[realization["material_id"]]
        helper = (
            material
            if material["kind"] == "rhythm_cell"
            else materials[material["rhythm_id"]]
        )
        length_ticks = helper["length_ticks"]
        rotation = sum(
            entry["ticks"] for entry in realization["rhythm_transforms"]
        )
        section_bars = sections[realization["section_id"]]["bars"]
        for step in helper["steps"]:
            final_onset = (
                realization["at_tick"]
                + (realization["repeat"] - 1) * realization["every_ticks"]
                + (step["at_tick"] + rotation) % length_ticks
            )
            assert final_onset + step["duration_ticks"] <= section_bars * ticks_per_bar


def _realizations_by_material(program: dict) -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = {}
    for realization in program["realizations"]:
        grouped.setdefault(realization["material_id"], []).append(realization)
    return grouped


def test_full_song_recall_transform_is_nonidentity_and_section_bounded() -> None:
    profile = _profile("full_song_exploration_v2.json")
    structural = _full_song_structural()
    first_program, plan = apply_profile_with_arrangement(structural, profile, 23)
    second_program, _ = apply_profile_with_arrangement(structural, profile, 23)
    second_plan = apply_profile_with_arrangement(structural, profile, 23)[1]
    assert (first_program, plan) == (second_program, second_plan)
    _assert_recall_transforms_valid(first_program, profile)
    for seed in (0, 1, 2, 3):
        program, _ = apply_profile_with_arrangement(structural, profile, seed)
        _assert_recall_transforms_valid(program, profile)
    rotated = [
        realization["rhythm_transforms"]
        for realization in first_program["realizations"]
        if realization["rhythm_transforms"]
    ]
    assert rotated, "expected at least one non-identity transformed recall"


def test_recall_transform_policy_validation() -> None:
    profile = _profile("full_song_exploration_v2.json")
    for policy in (
        {"algorithm": "other/v1", "rotation_denominator_choices": [2, 3]},
        {"algorithm": "seeded-nonidentity-rotate-recall/v1", "rotation_denominator_choices": []},
        {"algorithm": "seeded-nonidentity-rotate-recall/v1", "rotation_denominator_choices": [1, 2]},
        {"algorithm": "seeded-nonidentity-rotate-recall/v1", "rotation_denominator_choices": [2, True]},
        {"algorithm": "seeded-nonidentity-rotate-recall/v1"},
    ):
        invalid = copy.deepcopy(profile)
        invalid["recall_transform_policy"] = policy
        invalid["profile_hash"] = profile_hash(invalid)
        with pytest.raises(ValueError, match="EXPLORATION_PROFILE_INVALID"):
            validate_profile(invalid)
