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
    artifact_schemas = properties["candidate_artifact_schema_hashes"]
    assert artifact_schemas["additionalProperties"] is False
    assert artifact_schemas["required"] == [
        "sampler_request",
        "sampler_result",
        "production_request",
        "production_result",
        "program",
        "compile_report",
        "project",
        "evaluation_report",
        "fingerprint_record",
        "fingerprint_component",
        "near_duplicate_decision",
    ]
    assert "candidate_ledger_schema_hash" in properties["bindings"]["required"]


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
        "cps.gen0-cohort-gate-cas-index/v1",
    ):
        assert required in text


def test_fixture_suite_requires_all_normative_coverage_labels() -> None:
    schema = _schema("gen0_cohort_gate_fixture_suite_index.schema.json")
    coverage = schema["$defs"]["coverage"]["enum"]
    assert len(coverage) == 34
    assert schema["properties"]["coverage"]["minItems"] == 34
    assert schema["properties"]["coverage"]["maxItems"] == 34
    assert "boundary.mode.3500_pass" in coverage
    assert "failure.report_hash" in coverage
    assert coverage[-2:] == [
        "process.pythonhashseed_0_1_7_42",
        "parallel.workers_1_2_4_8",
    ]
    failure = schema["$defs"]["failure"]["allOf"][1]
    assert "input_report" in failure["required"]
    assert "cas_index" in schema["required"]
    assert "schema_registry" in schema["required"]
    assert "matrix_receipt" in schema["required"]
    registry = schema["properties"]["schema_registry"]
    assert registry["minItems"] == 1
    assert "identity_rules" in schema["$defs"]["schemaEntry"]["required"]


def test_cohort_cas_resolves_manifests_and_candidate_artifacts() -> None:
    schema = _schema("gen0_cohort_gate_cas_index.schema.json")
    kinds = schema["$defs"]["entry"]["properties"]["artifact_kind"]["enum"]
    for required in (
        "sampler_manifest",
        "evaluation_manifest",
        "descriptor_spec",
        "fingerprint_spec",
        "qd_manifest",
        "near_duplicate_calibration_decision",
        "sampler_request",
        "production_request",
        "fingerprint_component",
        "evaluation_report",
        "near_duplicate_decision",
    ):
        assert required in kinds


def test_cohort_matrix_receipt_binds_all_process_worker_coordinates() -> None:
    schema = _schema("gen0_cohort_gate_matrix_receipt.schema.json")
    coordinates = schema["properties"]["coordinates"]
    assert coordinates["minItems"] == coordinates["maxItems"] == 16
    assert schema["properties"]["all_equal"] == {"const": True}


def test_candidate_ledger_is_exactly_one_thousand_ordered_records() -> None:
    schema = _schema("gen0_cohort_candidate_ledger.schema.json")
    records = schema["properties"]["records"]
    assert records["minItems"] == records["maxItems"] == 1000
    assert records["items"] == {"$ref": "gen0_cohort_candidate_record.schema.json"}


def test_contract_closes_qd_axis_value_authority_chain() -> None:
    text = DOC.read_text(encoding="utf-8")
    assert "same `id` and\n`ordinal`" in text
    assert "authoritative axis value" in text
    assert "Descriptor axis order\ncomes only from DescriptorSpec" in text


def test_candidate_records_bind_requests_to_coordinates_and_results() -> None:
    schema = _schema("gen0_cohort_candidate_record.schema.json")
    required = schema["properties"]["artifact_hashes"]["required"]
    assert required[:4] == [
        "sampler_request",
        "sampler_result",
        "production_request",
        "production_result",
    ]
    text = DOC.read_text(encoding="utf-8")
    assert "sampler result's `request_hash`" in text
    assert "production result's\n`request_hash`" in text
    assert "`COHORT_COORDINATE_MISMATCH`" in text
    assert '"cps.structural-song-program/1.0"' in text
    assert "sampler result `structural_program_hash`" in text
    assert "CandidateRecord.artifact_hashes.program" in text
    assert "`COHORT_ARTIFACT_BINDING_MISMATCH`" in text


def test_contract_closes_all_candidate_stage_cross_links() -> None:
    text = DOC.read_text(encoding="utf-8")
    for required in (
        "CompileReport `source_program_hash`",
        "Project `source_program.hash`",
        "EvaluationReport `evaluation_manifest_hash`",
        "FingerprintRecord `fingerprint_spec_hash`",
        "NearDuplicateDecision `candidate_ordinal`",
        "same-ID fingerprint-component CAS payload",
        "`duplicate_classification`",
    ):
        assert required in text


def test_contract_maps_near_duplicate_universe_to_cohort_ordinals() -> None:
    text = DOC.read_text(encoding="utf-8")
    for required in (
        "canonical action order is exactly\nascending `candidate_ordinal`",
        "no external run/archive state participates",
        "program hashes sorted by raw 32-byte SHA-256 digest",
        "recomputes every component distance and weighted aggregate",
        "Exact program hash wins first",
        "distance equal to the threshold is `near_duplicate`",
        "`nearest` is null only for an empty comparison set",
    ):
        assert required in text


def test_contract_closes_terminal_stage_presence_and_code_matrix() -> None:
    text = DOC.read_text(encoding="utf-8")
    for stage in (
        "sampler",
        "production",
        "compiler",
        "evaluation",
        "fingerprint",
        "duplicate",
        "complete",
    ):
        assert f"| `{stage}` |" in text
    for required in (
        "sampler-result `error`",
        "production-result `error`",
        "CompileReport `error.code`",
        "EvaluationReport `failure_code`",
        "`FINGERPRINT_COMPUTATION_FAILED`",
        "`NEAR_DUPLICATE_DECISION_FAILED`",
        "complete row requires null",
    ):
        assert required in text
