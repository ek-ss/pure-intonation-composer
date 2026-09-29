"""Real CompositionPlan-to-Project v3 generation on both equaves."""

from __future__ import annotations

import pytest

from tools.generate_piano_v3_cadence_trial import generate_one


@pytest.mark.parametrize(("equave", "seed"), [("2/1", 4), ("3/1", 0)])
def test_composition_cadence_program_project_reconciliation(equave: str, seed: int) -> None:
    artifacts, report = generate_one(equave, seed, skip_wav=True)
    assert report["status"] == "success"
    assert report["candidate_slots"] == report["matched_slots"]
    assert report["section_bars"]
    assert all(row["status"] == "matched" for row in report["slot_bindings"])
    assert all(row["source_dictionary_hash"] == report["dictionary_hash"]
               for row in report["slot_bindings"])
    assert all(row["program_variant_hashes"] for row in report["slot_bindings"])
    assert artifacts["composition_plan.json"]
    assert artifacts["cadence_plan.json"]
    assert artifacts["program.json"]
    assert artifacts["project.json"]
    assert report["pcm"] == {"status": "not_evaluated"}


def test_cadence_trial_repeats_identical_plan_program_and_project_hashes() -> None:
    first_artifacts, first = generate_one("3/1", 0, skip_wav=True)
    second_artifacts, second = generate_one("3/1", 0, skip_wav=True)
    for field in (
        "composition_plan_hash", "cadence_plan_hash", "program_hash", "project_hash"
    ):
        assert first[field] == second[field]
    assert first_artifacts == second_artifacts
