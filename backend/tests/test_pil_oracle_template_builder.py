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
