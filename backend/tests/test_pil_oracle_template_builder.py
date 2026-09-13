from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

from app.songprogram.pil_fixture_suite import (
    PIL_REQUIRED_COVERAGE,
    validate_pil_oracle_case_bindings,
)
from app.songprogram.perceptual import run_perceptual_interpretation
from app.songprogram.validator import validate_project
from tools.build_pil_oracle_case_templates import build_cases


TEMPLATES = Path(__file__).resolve().parents[2] / "docs/pil_oracle_case_templates"


def test_generated_templates_are_standalone_and_match_checked_in_inputs() -> None:
    cases = build_cases()
    assert len(cases) == 18
    assert {label for case in cases for label in case["coverage"]} == set(PIL_REQUIRED_COVERAGE)
    for case in cases:
        checked_in = json.loads((TEMPLATES / f"{case['case_id']}.json").read_text(encoding="utf-8"))
        assert checked_in == case
        validate_project(case["project"])
        validate_pil_oracle_case_bindings(case)
        assert case["expected"] == {
            "status": None,
            "error": None,
            "report_hash": None,
            "canonical_report_sha256": None,
        }
        assert case["case_hash"] is None


def test_template_inputs_execute_without_mutation_or_hidden_assets() -> None:
    for case in build_cases():
        original_project = deepcopy(case["project"])
        keyword_assets = {
            key: case[key]
            for key in (
                "segmentation_policy",
                "feature_spec",
                "voice_matching_policy",
                "trajectory_template_set",
            )
            if case[key] is not None
        }
        if case["vocabulary"] is not None:
            keyword_assets["chord_vocabulary"] = case["vocabulary"]
        report = run_perceptual_interpretation(
            case["project"],
            case["manifest"],
            expected_project_hash=case["project_hash"],
            native_ji_report_hash=case["native_ji_report_hash"],
            **keyword_assets,
        )
        expected_status = "failure" if "kernel_empty_support" in case["coverage"] else "success"
        assert report["status"] == expected_status
        assert case["project"] == original_project
        coverage = set(case["coverage"])
        if "ambiguous_winner" in coverage:
            assert report["segment_interpretations"][0]["best_label"] is None
        if "missing_bass" in coverage:
            assert report["segments"][0]["bass_event_id"] is None
        if "unequal_voice_count" in coverage:
            matching = report["voice_matching_records"][0]
            assert matching["unmatched_from_event_ids"]
            assert not matching["unmatched_to_event_ids"]
        if "identity_constraint" in coverage:
            pairs = report["voice_matching_records"][0]["pairs"]
            assert any(pair["from_event_id"] == pair["to_event_id"] for pair in pairs)
        if "trajectory_missing_bass" in coverage:
            scores = report["trajectory_interpretations"][0]["component_scores_q"]
            assert scores["bass"] is None


def test_owner_review_semantic_contrasts_are_present_before_promotion() -> None:
    cases = {case["case_id"]: case for case in build_cases()}

    tet = _run_template(cases["pil_12et_ii_v_i"])
    ji = _run_template(cases["pil_exact_ratio_ii_v_i"])
    assert (
        cases["pil_12et_ii_v_i"]["project_hash"] != cases["pil_exact_ratio_ii_v_i"]["project_hash"]
    )
    assert tet["report_hash"] != ji["report_hash"]
    assert tet["trajectory_interpretations"][0]["template_id"] == "ii_v_i"
    assert ji["trajectory_interpretations"][0]["template_id"] == "ii_v_i"

    seven_limit = _run_template(cases["pil_seven_limit_multi_candidate"])
    assert all(len(record["mapping_q31"]) >= 2 for record in seven_limit["pitch_records"])

    kernel = _run_template(cases["pil_kernel_boundaries"])
    rows = {record["source_ratio"]: record for record in kernel["pitch_records"]}
    tie = rows["2158603/2097152"]
    assert tie["interpretation_phase_millicents"] == 50_000
    assert [item["weight_q31"] for item in tie["mapping_q31"]] == [
        1_073_741_824,
        1_073_741_823,
    ]
    edge = rows["8887423/8388608"]
    assert edge["interpretation_phase_millicents"] == 100_000
    assert edge["mapping_q31"] == [{"pitch_class_ordinal": 1, "weight_q31": 2_147_483_647}]

    passing = _run_template(cases["pil_passing_tone_delta"])["segment_interpretations"]
    passing_similarity = passing[0]["candidates"][0]
    baseline_similarity = passing[1]["candidates"][0]
    assert passing_similarity["id"] == baseline_similarity["id"] == "major"
    assert baseline_similarity["similarity_q"] - passing_similarity["similarity_q"] >= 700


def _run_template(case: dict) -> dict:
    assets = {
        key: case[key]
        for key in (
            "segmentation_policy",
            "feature_spec",
            "voice_matching_policy",
            "trajectory_template_set",
        )
        if case[key] is not None
    }
    if case["vocabulary"] is not None:
        assets["chord_vocabulary"] = case["vocabulary"]
    return run_perceptual_interpretation(
        case["project"],
        case["manifest"],
        expected_project_hash=case["project_hash"],
        native_ji_report_hash=case["native_ji_report_hash"],
        **assets,
    )
