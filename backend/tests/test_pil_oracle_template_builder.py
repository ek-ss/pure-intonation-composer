from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

from app.songprogram.pil_fixture_suite import validate_pil_oracle_case_bindings
from app.songprogram.perceptual import run_perceptual_interpretation
from app.songprogram.validator import validate_project
from tools.build_pil_oracle_case_templates import build_cases


TEMPLATES = Path(__file__).resolve().parents[2] / "docs/pil_oracle_case_templates"


def test_generated_templates_are_standalone_and_match_checked_in_inputs() -> None:
    cases = build_cases()
    assert len(cases) == 13
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
