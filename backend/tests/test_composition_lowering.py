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
