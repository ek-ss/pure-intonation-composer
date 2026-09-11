from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCHEMAS = ROOT / "songprogram_conformance" / "schemas"


def _load(name: str) -> dict:
    return json.loads((SCHEMAS / name).read_text(encoding="utf-8"))


def test_group_b_raw_schema_and_artifact_bindings_are_complete() -> None:
    run = _load("search_run_manifest_1_3.schema.json")
    context = _load("search_loop_13_context.schema.json")
    context_hashes = context["properties"]["schema_hashes"]
    for name in ("evaluation_manifest", "evaluation_request", "evaluation_report"):
        assert f"{name}_schema_hash" in run["required"]
        assert f"{name}_schema_hash" in run["properties"]
        assert name in context_hashes["required"]
        assert name in context_hashes["properties"]
    assert "evaluation_manifest_hash" in run["required"]
    assert "evaluation_manifest" in context["$defs"]["artifacts"]["required"]


def test_manifest_declarations_close_source_direction_and_render_requirement() -> None:
    manifest = _load("evaluation_manifest.schema.json")
    hard_check = manifest["$defs"]["hardCheck"]
    metric = manifest["$defs"]["metric"]
    assert hard_check["required"] == ["id", "sources", "operator", "required_render"]
    assert metric["required"] == ["id", "sources", "operator", "direction", "required_render"]
    assert metric["properties"]["direction"]["enum"] == ["maximize", "minimize"]
    assert metric["properties"]["required_render"] == {"type": "boolean"}
    assert manifest["required"][-1] == "manifest_hash"


def test_request_has_distinct_available_unselected_and_failed_render_states() -> None:
    request = _load("evaluation_request.schema.json")
    evidence = request["$defs"]["renderEvidence"]
    assert evidence["properties"]["status"]["enum"] == ["available", "not_selected", "failed"]
    assert evidence["properties"]["missing_reason"]["enum"] == [None, "not_selected", "render_failed"]
    rules = evidence["allOf"]
    assert [rule["if"]["properties"]["status"]["const"] for rule in rules] == ["available", "not_selected", "failed"]
    assert rules[1]["then"]["properties"]["render_result_hash"] == {"type": "null"}
    assert rules[2]["then"]["properties"]["render_result_hash"] == {"$ref": "#/$defs/sha"}


def test_report_failure_precedence_and_missing_metric_reasons_are_exact() -> None:
    report = _load("evaluation_report.schema.json")
    failure_codes = report["$defs"]["base"]["properties"]["failure_code"]["enum"]
    assert failure_codes == [
        None,
        "EVALUATION_REQUEST_INVALID",
        "EVALUATION_CONTEXT_MISMATCH",
        "EVALUATION_MANIFEST_MISMATCH",
        "EVALUATION_GENRE_INTENT_MISMATCH",
        "EVALUATION_SOURCE_MISMATCH",
        "EVALUATION_PROJECT_MISMATCH",
        "EVALUATION_FINGERPRINT_MISMATCH",
        "EVALUATION_RENDER_EVIDENCE_MISMATCH",
        "EVALUATION_SOURCE_TYPE_INVALID",
        "EVALUATION_OPERATOR_INVALID",
        "EVALUATION_OPERATOR_ARITY_INVALID",
        "EVALUATION_ACCUMULATOR_OVERFLOW",
        "EVALUATION_RESULT_OVERFLOW",
        "EVALUATION_RESULT_INVALID",
    ]
    assert report["$defs"]["missing"]["enum"] == [
        "source_unavailable", "render_not_selected", "render_failed", "not_applicable",
    ]
    failure = report["$defs"]["failure"]["allOf"][1]["properties"]
    assert failure["hard_checks"] == {"type": "array", "maxItems": 0}
    assert failure["metrics"] == {"type": "array", "maxItems": 0}


def test_report_evidence_and_metric_missing_union_are_closed() -> None:
    report = _load("evaluation_report.schema.json")
    evidence = report["$defs"]["evidence"]
    assert evidence["required"] == ["source_bindings", "operator", "inputs", "result", "evidence_hash"]
    assert report["$defs"]["hardCheck"]["properties"]["evidence"] == {"$ref": "#/$defs/evidence"}
    source = report["$defs"]["sourceBinding"]
    assert source["required"] == ["artifact_kind", "artifact_hash", "schema_hash", "json_pointer"]
    metric = report["$defs"]["metric"]
    assert "available_source_bindings" in metric["required"]
    present, missing = metric["allOf"]
    assert present["then"]["properties"]["missing_reason"] == {"type": "null"}
    assert present["then"]["properties"]["evidence"] == {"$ref": "#/$defs/evidence"}
    assert missing["then"]["properties"]["evidence"] == {"type": "null"}
    assert missing["then"]["properties"]["missing_reason"] == {"$ref": "#/$defs/missing"}


def test_metric_report_event_maps_to_the_single_evaluation_report_contract() -> None:
    event = _load("search_loop_13_event_payload.schema.json")
    kinds = event["properties"]["kind"]["enum"]
    assert "evaluation_request" in kinds
    assert "metric_report" in kinds
    contract = (ROOT.parent / "docs" / "song_program_search_loop_13_payload_contract.md").read_text(encoding="utf-8")
    assert "`metric_report` maps to EvaluationReport" in contract
    assert "/metrics/N/value" in contract
    assert "/hard_checks/N/passed" in contract
