from __future__ import annotations

import json
from pathlib import Path

from app.songprogram.pil_fixture_suite import validate_pil_oracle_case_bindings
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
