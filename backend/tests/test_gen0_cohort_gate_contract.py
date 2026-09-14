from __future__ import annotations

import json
from pathlib import Path


BACKEND = Path(__file__).resolve().parents[1]
SCHEMAS = BACKEND / "songprogram_conformance" / "schemas"
DOC = BACKEND.parent / "docs" / "song_program_gen0_cohort_gate_contract.md"


def _schema(name: str) -> dict:
    return json.loads((SCHEMAS / name).read_text(encoding="utf-8"))


def test_manifest_freezes_first_cohort_coordinates_and_thresholds() -> None:
    schema = _schema("gen0_cohort_gate_manifest.schema.json")
    properties = schema["properties"]
    assert properties["cohort_size"] == {"const": 1000}
    assert properties["coordinate_rule"] == {
        "const": "candidate-ordinal-equals-cohort-index-0-through-999/v1"
    }
    thresholds = properties["thresholds_bp"]["properties"]
    assert {key: value["const"] for key, value in thresholds.items()} == {
        "compile_success_ge": 9500,
        "initial_viability_ge": 7000,
        "planner_viability_ge": 8000,
        "exact_duplicate_lt": 100,
        "near_duplicate_lt": 1000,
        "transformed_recall_ge": 8000,
        "mode_prevalence_le": 3500,
    }


def test_candidate_record_keeps_failures_in_the_fixed_ordinal_domain() -> None:
    schema = _schema("gen0_cohort_candidate_record.schema.json")
    assert schema["$defs"]["ordinal"] == {
        "type": "integer",
        "minimum": 0,
        "maximum": 999,
    }
    stages = schema["properties"]["terminal_stage"]["enum"]
    assert stages == [
        "sampler",
        "production",
        "compiler",
        "evaluation",
        "fingerprint",
        "duplicate",
        "complete",
    ]


def test_report_is_success_only_and_near_duplicate_gate_can_be_audit_only() -> None:
    schema = _schema("gen0_cohort_gate_report.schema.json")
    assert schema["properties"]["status"] == {"const": "success"}
    assert schema["properties"]["failure_code"] == {"type": "null"}
    assert schema["$defs"]["optionalGate"]["properties"]["status"]["enum"] == [
        "passed",
        "failed",
        "not_enforced",
    ]


def test_contract_closes_denominator_modes_and_failure_publication() -> None:
    text = DOC.read_text(encoding="utf-8")
    for required in (
        "denominator is always 1,000",
        "A sequence of length zero contributes the canonical sentinel `[]`",
        "at most once per candidate",
        "produces no\n`Gen0CohortGateReport`",
        "cannot promote any `pil.*` metric",
    ):
        assert required in text


def test_fixture_suite_requires_all_normative_coverage_labels() -> None:
    schema = _schema("gen0_cohort_gate_fixture_suite_index.schema.json")
    coverage = schema["$defs"]["coverage"]["enum"]
    assert len(coverage) == 35
    assert schema["properties"]["coverage"]["minItems"] == 35
    assert schema["properties"]["coverage"]["maxItems"] == 35
    assert "boundary.mode.3500_pass" in coverage
    assert "failure.report_hash" in coverage
    assert coverage[-2:] == [
        "process.pythonhashseed_0_1_7_42",
        "parallel.workers_1_2_4_8",
    ]
