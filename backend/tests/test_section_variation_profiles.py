from __future__ import annotations

import json

from jsonschema import Draft202012Validator

from app.songprogram.composition_generation import generate_composition_plan
from app.songprogram.composition_lowering import lower_composition_plan
from app.songprogram.composition_realization import choose_role_mask, choose_texture_mode
from app.songprogram.structural_sampler import execute_structural_sampler
from tools.build_section_variation_profiles import (
    PROFILES, build_composition_profile, build_realization_profile,
)
from tools.run_fixture_generation_cohort import DEFAULT_GENERATION_MANIFEST, _exploration_authorities


def _profiles() -> tuple[dict, dict]:
    folder = PROFILES / "g1_experiments"
    composition = json.loads((folder / "section_variation.json").read_text())
    realization = json.loads((folder / "section_variation_roles.json").read_text())
    assert composition == build_composition_profile(json.loads(
        (PROFILES / "composition_generation_v2.json").read_text()))
    assert realization == build_realization_profile(json.loads(
        (PROFILES / "composition_realization_v2_1.json").read_text()))
    return composition, realization


def test_section_choices_keep_cadences_and_expand_all_functions() -> None:
    composition, realization = _profiles()
    Draft202012Validator(json.loads((PROFILES.parent / "schemas" /
        "composition_generation_profile_2_0.schema.json").read_text())).validate(composition)
    Draft202012Validator(json.loads((PROFILES.parent / "schemas" /
        "composition_realization_profile_2_1.schema.json").read_text())).validate(realization)
    plans = [generate_composition_plan(composition, seed) for seed in range(256)]
    assert len(composition["form_templates"]) == 32
    assert len({plan["form_template_id"] for plan in plans}) >= 28
    for position in (0, -1):
        signatures = {(plan["sections"][position]["bars"],
                       plan["sections"][position]["density_q"],
                       plan["sections"][position]["foreground_state"])
                      for plan in plans}
        assert len(signatures) == 4
    for function in ("opening", "closure"):
        assert len({choose_role_mask(realization, seed, f"sec-{seed}", function)
                    for seed in range(128)}) >= 3
    for function in ("statement", "preparation", "arrival", "contrast", "return"):
        signatures = {(section["bars"], section["energy_q"], section["density_q"])
                      for plan in plans for section in plan["sections"]
                      if section["function"] == function}
        assert len(signatures) >= 3
        assert len({choose_role_mask(realization, seed, f"sec-{seed}", function)
                    for seed in range(128)}) >= 2
    for plan in plans:
        assert plan["sections"][-1]["cadence_target"] == "home"
        assert plan["harmonic_trajectory"][-1]["harmonic_function"] in {
            "home", "return", "arrival",
        }
    assert len({choose_texture_mode(realization, seed, "sec_000", "opening")
                for seed in range(128)}) >= 4
    assert len({choose_texture_mode(realization, seed, "sec_007", "closure")
                for seed in range(128)}) >= 4


def test_section_variants_lower_within_structural_budgets() -> None:
    composition, realization = _profiles()
    generation = json.loads(DEFAULT_GENERATION_MANIFEST.read_text())
    for seed in range(12):
        request, sampler, lowering = _exploration_authorities(seed, None, generation)
        sampled = execute_structural_sampler(request, sampler, lowering)
        assert sampled["result"]["status"] == "success"
        structural = sampled["structural_program"]
        program = lower_composition_plan(structural, generate_composition_plan(composition, seed), realization)
        assert len(program["materials"]) <= structural["limits"]["max_materials"]
        assert len(program["realizations"]) <= structural["limits"]["max_realizations"]
