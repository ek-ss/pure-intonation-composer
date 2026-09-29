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


def test_failing_seed_records_staged_failure_with_partial_artifacts() -> None:
    from tools.generate_piano_v3_cadence_trial import V3TrialFailure

    # Octave seed 0 has no progression path: the failure is staged at compile
    # and keeps every artifact produced before it (never a silent drop).
    with pytest.raises(V3TrialFailure) as excinfo:
        generate_one("2/1", 0, skip_wav=True)
    failure = excinfo.value
    assert failure.stage == "compile"
    assert failure.code == "PROGRESSION_NO_PATH"
    assert set(failure.artifacts) == {
        "composition_plan.json", "cadence_policy.json",
        "cadence_plan.json", "program.json",
    }


def test_successful_seed_report_carries_empty_mismatches() -> None:
    _, report = generate_one("3/1", 0, skip_wav=True)
    assert all(row["mismatches"] == [] for row in report["slot_bindings"])
    assert all(row["status"] == "matched" for row in report["slot_bindings"])
