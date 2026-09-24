from __future__ import annotations

import copy
import json
from collections import Counter
from pathlib import Path

import pytest

from app.songprogram.composition_generation import generate_composition_plan
from app.songprogram.composition_lowering import (
    CompositionLoweringError,
    lower_composition_plan,
)
from app.songprogram.structural_sampler import execute_structural_sampler
from tools.run_fixture_generation_cohort import (
    DEFAULT_GENERATION_MANIFEST,
    _exploration_authorities,
)


BACKEND = Path(__file__).resolve().parents[1]
PROFILE = (
    BACKEND / "songprogram_conformance" / "profiles" / "composition_generation_v2.json"
)
REALIZATION_PROFILE = (
    BACKEND / "songprogram_conformance" / "profiles" / "composition_realization_v2_1.json"
)


def _inputs(seed: int = 0) -> tuple[dict, dict]:
    profile = json.loads(PROFILE.read_text(encoding="utf-8"))
    generation = json.loads(DEFAULT_GENERATION_MANIFEST.read_text(encoding="utf-8"))
    request, sampler, lowering = _exploration_authorities(seed, None, generation)
    sampled = execute_structural_sampler(request, sampler, lowering)
    assert sampled["result"]["status"] == "success"
    return sampled["structural_program"], generate_composition_plan(profile, seed)


def test_composition_lowering_is_deterministic_and_form_ordered() -> None:
    structural, plan = _inputs()
    first = lower_composition_plan(structural, plan)
    assert first == lower_composition_plan(structural, plan)
    assert [section["id"] for section in first["form"]] == [
        section["section_id"] for section in plan["sections"]
    ]
    assert [section["role"] for section in first["form"]] == [
        "intro", "verse", "build", "drop", "verse", "build", "final", "outro"
    ]
    assert structural["form"] != first["form"]


def test_composition_lowering_emits_core_roles_and_phrase_melody() -> None:
    structural, plan = _inputs()
    lowered = lower_composition_plan(structural, plan)
    materials = {material["id"]: material for material in lowered["materials"]}
    by_section: dict[str, Counter[str]] = {}
    for row in lowered["realizations"]:
        by_section.setdefault(row["section_id"], Counter())[row["role"]] += 1
    for section in lowered["form"]:
        assert {"drums", "bass", "harmony"} <= set(by_section[section["id"]])
        assert by_section[section["id"]]["harmony"] == 1
        assert by_section[section["id"]]["melody"] >= 1
    transformed_recall_sections = {
        row["section_id"]
        for row in lowered["realizations"]
        if row["material_id"] == "rhy_cmp_fill_shared" and row["rhythm_transforms"]
    }
    assert transformed_recall_sections == {
        section["section_id"]
        for section in plan["sections"]
        if section["function"] == "return"
    }
    melody = [row for row in lowered["realizations"] if row["role"] == "melody"]
    assert len(melody) == len(plan["motif_plan"]["occurrences"])
    for row in melody:
        material = materials[row["material_id"]]
        helper = materials[material["rhythm_id"]]
        assert material["kind"] == "melody_intent"
        assert len(material["points"]) == len(helper["steps"])
        assert all(
            step["at_tick"] + step["duration_ticks"] <= helper["length_ticks"]
            for step in helper["steps"]
        )
    members = {
        point["member"]
        for row in melody
        for point in materials[row["material_id"]]["points"]
    }
    assert members == {0, 1, 2}
    for section in plan["sections"]:
        rows = [
            row
            for row in lowered["realizations"]
            if row["section_id"] == section["section_id"]
        ]
        drum = next(
            row
            for row in rows
            if row["role"] == "drums" and row["repeat"] == section["bars"]
        )
        bass = next(row for row in rows if row["role"] == "bass")
        drum_steps = {
            step["at_tick"] for step in materials[drum["material_id"]]["steps"]
        }
        bass_material = materials[bass["material_id"]]
        bass_steps = {
            step["at_tick"]
            for step in materials[bass_material["rhythm_id"]]["steps"]
        }
        assert bass_steps <= drum_steps


def test_lowering_rejects_tampered_plan_before_mutation() -> None:
    structural, plan = _inputs()
    tampered = copy.deepcopy(plan)
    tampered["sections"][0]["bars"] = 5
    with pytest.raises(CompositionLoweringError, match="COMPOSITION_PLAN_INVALID"):
        lower_composition_plan(structural, tampered)


def test_realization_profile_activates_role_masks_and_density() -> None:
    structural, plan = _inputs()
    profile = json.loads(REALIZATION_PROFILE.read_text(encoding="utf-8"))
    lowered = lower_composition_plan(structural, plan, profile)
    assert lowered == lower_composition_plan(structural, plan, profile)
    materials = {material["id"]: material for material in lowered["materials"]}
    by_section: dict[str, list[dict]] = {}
    for row in lowered["realizations"]:
        by_section.setdefault(row["section_id"], []).append(row)
    role_masks = {section_id: {row["role"] for row in rows} for section_id, rows in by_section.items()}
    assert len(set(map(frozenset, role_masks.values()))) >= 2
    texture_rows = [
        row for rows in by_section.values() for row in rows if row["role"] == "texture"
    ]
    assert texture_rows
    assert all("mat_cmp_tex_" in row["material_id"] for row in texture_rows)
    assert any("noise_riser" in row["material_id"] for row in texture_rows)
    assert any("transition_tail" in row["material_id"] for row in texture_rows)
    for section in plan["sections"]:
        rows = by_section[section["section_id"]]
        expected_velocity = 8500 + round(section["energy_q"] * 1500 / 10000)
        assert all(row["velocity_scale_q"] == expected_velocity for row in rows)
        assert 8500 <= expected_velocity <= 10000
        for role in ("drums", "bass", "harmony"):
            ordinary = [
                row for row in rows
                if row["role"] == role and row["repeat"] == section["bars"]
            ]
            if not ordinary:
                continue
            material = materials[ordinary[0]["material_id"]]
            helper = materials[material["rhythm_id"]] if "rhythm_id" in material else material
            policy = profile["density_policy_by_role"][role]
            expected = policy["minimum_events_per_bar"] + round(
                section["density_q"]
                * (policy["maximum_events_per_bar"] - policy["minimum_events_per_bar"])
                / 10000
            )
            assert len(helper["steps"]) == expected
            expected_accent = 10000 if role == "harmony" else expected_velocity
            assert all(step["accent_q"] == expected_accent for step in helper["steps"])


def test_realized_harmony_uses_phrase_roots_and_bar_level_rhythms() -> None:
    structural, plan = _inputs()
    profile = json.loads(REALIZATION_PROFILE.read_text(encoding="utf-8"))
    lowered = lower_composition_plan(structural, plan, profile)
    materials = {row["id"]: row for row in lowered["materials"]}
    section_roots = []
    section_rhythms = []
    shifted = 0
    for section in plan["sections"]:
        rows = [row for row in lowered["realizations"]
                if row["role"] == "harmony" and row["section_id"] == section["section_id"]]
        assert len(rows) == section["bars"]
        assert [row["at_tick"] for row in rows] == [
            bar * structural["clock"]["beats_per_bar"] * structural["clock"]["ticks_per_beat"]
            for bar in range(section["bars"])
        ]
        roots = {tuple(materials[row["material_id"]]["root_anchors"][0]) for row in rows}
        section_roots.append(roots)
        section_rhythms.append({len(materials[materials[row["material_id"]]["rhythm_id"]]["steps"])
                                for row in rows})
        shifted += sum(bool(row["rhythm_transforms"]) for row in rows)
    assert any(len(roots) >= 3 for roots in section_roots)
    assert {1, 2} in section_rhythms
    assert {1} in section_rhythms
    assert shifted == 0  # active melody requires continuous chord coverage
    for section in plan["sections"]:
        rows = [row for row in lowered["realizations"]
                if row["role"] == "harmony" and row["section_id"] == section["section_id"]]
        for row in rows:
            rhythm = materials[materials[row["material_id"]]["rhythm_id"]]
            if len(rhythm["steps"]) == 2:
                assert all(step["duration_ticks"] == structural["clock"]["beats_per_bar"]
                           * structural["clock"]["ticks_per_beat"] // 2
                           for step in rhythm["steps"])


def test_plan_coordination_prior_changes_realized_onsets() -> None:
    structural, baseline = _inputs()
    variant_profile = json.loads((BACKEND / "songprogram_conformance/profiles/g1_experiments/rhythm_dialogue.json").read_text())
    alternative = generate_composition_plan(variant_profile, 0)
    realization = json.loads(REALIZATION_PROFILE.read_text())

    def onsets(plan: dict) -> list[tuple[str, tuple[int, ...]]]:
        lowered = lower_composition_plan(structural, plan, realization)
        materials = {row["id"]: row for row in lowered["materials"]}
        return [
            (row["role"], tuple(step["at_tick"] for step in materials[
                materials[row["material_id"]]["rhythm_id"]
            ]["steps"]))
            for row in lowered["realizations"]
            if row["role"] == "bass"
        ]

    assert onsets(baseline) != onsets(alternative)


def test_ambient_intro_keeps_offbeat_harmony_without_melody_conflict() -> None:
    structural, _ = _inputs(19)
    folder = BACKEND / "songprogram_conformance/profiles/g1_experiments"
    plan = generate_composition_plan(json.loads((folder / "section_variation.json").read_text()), 19)
    assert plan["sections"][0]["foreground_state"] == "absent"
    profile = json.loads((folder / "section_variation_roles.json").read_text())
    lowered = lower_composition_plan(structural, plan, profile)
    intro = plan["sections"][0]["section_id"]
    assert any(row["rhythm_transforms"] for row in lowered["realizations"]
               if row["role"] == "harmony" and row["section_id"] == intro)
    assert not any(row["role"] == "melody" and row["section_id"] == intro
                   for row in lowered["realizations"])


def test_flexible_section_roles_stay_within_material_budget() -> None:
    profile = json.loads((BACKEND / "songprogram_conformance/profiles/g1_experiments/role_flexible.json").read_text())
    for seed in (0, 7):
        structural, plan = _inputs(seed)
        lowered = lower_composition_plan(structural, plan, profile)
        assert len(lowered["materials"]) <= structural["limits"]["max_materials"]
        assert len(lowered["realizations"]) <= structural["limits"]["max_realizations"]
