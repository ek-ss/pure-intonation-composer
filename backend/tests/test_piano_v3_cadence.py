"""Contract tests for the isolated cadence-driven piano v3 planner."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.songprogram.piano_v3 import (
    PIANO_V3_DOMAINS,
    PianoV3Error,
    build_cadence_policy,
    cadence_impact_report,
    compare_navigation_coverage,
    generate_cadence_plan,
    measure_navigation_coverage,
    validate_cadence_plan,
    v3_domain_cardinalities,
)


BACKEND = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("equave,filename", [("2/1", "2-1"), ("3/1", "3-1")])
def test_v3_domain_is_five_dimensional_and_budgeted(equave: str, filename: str) -> None:
    domain = PIANO_V3_DOMAINS[equave]
    assert len(domain["generators"]) == len(domain["coordinate_bounds"]) == 5
    assert v3_domain_cardinalities(domain) == (1024, 4096)


@pytest.mark.parametrize("equave,filename", [("2/1", "2-1"), ("3/1", "3-1")])
def test_cadence_plan_is_separate_deterministic_and_auditable(
    equave: str, filename: str
) -> None:
    dictionary = json.loads(
        (BACKEND / "harmony_dictionary_data" / f"harmony_dictionary_{filename}.json")
        .read_text(encoding="utf-8")
    )
    policy = build_cadence_policy(
        equave, dictionary["hash"], dictionary["stability_profile_hash"],
        dictionary["thresholds"]["version"],
    )
    plan = {
        "seed": 19,
        "plan_hash": "sha256:" + "0" * 64,
        "sections": [{"section_id": "sec_000", "phrases": [{
            "section_id": "sec_000", "phrase_id": "phr_000", "start_bar": 0,
            "length_bars": 4, "cadence_target": "home",
        }]}],
    }
    first = generate_cadence_plan(plan, dictionary, policy)
    second = generate_cadence_plan(plan, dictionary, policy)
    assert first == second
    assert len(first["slots"]) == 4
    assert first["slots"][-1]["expectation"] == "arrive"
    assert first["slots"][-1]["function"] == "T"
    assert first["slots"][0]["source_chord_key"]
    validate_cadence_plan(first)
    report = cadence_impact_report(first)
    assert report["project_checked"] is False
    assert report["slots"][-1]["status"] == "planned"

    tampered = json.loads(json.dumps(first))
    tampered["slots"][0]["root_ratio"] = "2/1"
    with pytest.raises(PianoV3Error, match="CADENCE_PLAN_INVALID"):
        validate_cadence_plan(tampered)


@pytest.mark.parametrize("equave,covered", [("2/1", True), ("3/1", False)])
def test_coverage_measurement_uses_navigation_gate_before_ranking(equave: str, covered: bool) -> None:
    measurement = measure_navigation_coverage(PIANO_V3_DOMAINS[equave])
    assert measurement["covered"] is covered
    assert all(step["covered"] == (step["vector"] is not None) for step in measurement["steps"].values())
    if covered:
        assert measurement["maximum_error_millicents_measured"] <= 50_000
    else:
        assert any(not step["covered"] for step in measurement["steps"].values())


def test_navigation_measurement_matches_actual_generation_gate() -> None:
    from app.songprogram.exploration_generation import (
        ExplorationGenerationManifestError,
        derive_lattice_navigation,
    )

    policy = {
        "algorithm": "nearest-12tet-vector/v1",
        "required_prime_factors": [2, 3, 5, 7, 11, 13],
        "maximum_navigation_points": 32,
        "maximum_error_millicents": 50_000,
        "tonal_center_steps": list(range(12)),
        "harmony_root_steps": [0],
        "walk_step_patterns": [[0]],
    }
    octave = derive_lattice_navigation(PIANO_V3_DOMAINS["2/1"], policy)
    measured = measure_navigation_coverage(PIANO_V3_DOMAINS["2/1"])
    assert octave["tonal_centers"][:12] == [measured["steps"][i]["vector"] for i in range(12)]
    with pytest.raises(ExplorationGenerationManifestError, match="GENERATION_12TET_COVERAGE_INSUFFICIENT"):
        derive_lattice_navigation(PIANO_V3_DOMAINS["3/1"], policy)


@pytest.mark.parametrize(("equave", "actual_status", "expected_uncovered"), [
    ("2/1", "covered", set()),
    ("3/1", "GENERATION_12TET_COVERAGE_INSUFFICIENT", {1, 5, 11}),
])
def test_navigation_comparison_records_actual_gate_and_uncovered_steps(
    equave: str, actual_status: str, expected_uncovered: set[int]
) -> None:
    comparison = compare_navigation_coverage(PIANO_V3_DOMAINS[equave])
    assert comparison["actual_status"] == actual_status
    uncovered = {
        step for step, result in comparison["measurement"]["steps"].items()
        if not result["covered"]
    }
    assert uncovered == expected_uncovered
    assert comparison["seal_eligible"] is (equave == "2/1")
