from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCHEMAS = ROOT / "songprogram_conformance" / "schemas"


def _load(name: str) -> dict:
    return json.loads((SCHEMAS / name).read_text(encoding="utf-8"))


def test_group_a_schema_bindings_are_present_in_run_and_context() -> None:
    manifest = _load("search_run_manifest_1_3.schema.json")
    context = _load("search_loop_13_context.schema.json")
    pairs = {
        "candidate_source_decision": "candidate_source_decision_schema_hash",
        "sampler_request": "sampler_request_schema_hash",
        "sampler_result": "sampler_result_schema_hash",
        "planner_request": "planner_request_schema_hash",
        "planner_response": "planner_response_schema_hash",
    }
    context_hashes = context["properties"]["schema_hashes"]
    for context_name, manifest_name in pairs.items():
        assert manifest_name in manifest["required"]
        assert manifest_name in manifest["properties"]
        assert context_name in context_hashes["required"]
        assert context_name in context_hashes["properties"]


def test_candidate_source_union_and_lock_shape_are_frozen() -> None:
    schema = _load("candidate_source_decision.schema.json")
    assert schema["properties"]["schema"]["const"] == "cps.candidate-source-decision"
    assert schema["properties"]["schema_version"]["const"] == "1.0.0"
    assert schema["required"][-1] == "decision_hash"
    branches = [schema["$defs"][name] for name in ("initial", "archive")]
    assert [branch["properties"]["kind"]["const"] for branch in branches] == [
        "initial_sampler",
        "archive_parent",
    ]
    assert branches[0]["required"] == ["kind", "root_seed", "cohort_index", "sampler_manifest_hash"]
    assert branches[1]["required"] == [
        "kind", "source_occurrence_ordinal", "round_start_archive_heads_hash",
        "selected_archive_update_record_hash", "archive_admission_decision_hash",
        "parent_program_hash", "parent_program",
    ]
    assert schema["$defs"]["root"]["required"] == ["kind", "id"]


def test_sampler_result_status_nullability_and_errors_are_frozen() -> None:
    schema = _load("structural_sampler_result.schema.json")
    base = schema["$defs"]["base"]
    assert base["properties"]["schema"]["const"] == "cps.structural-sampler-result"
    assert base["required"][-1] == "result_hash"
    assert base["properties"]["error"]["enum"] == [
        None, "SAMPLER_REQUEST_INVALID", "SAMPLER_CONTEXT_MISMATCH",
        "SAMPLER_MANIFEST_MISMATCH", "SAMPLER_SOURCE_MISMATCH",
        "SAMPLER_REJECTIONS_EXHAUSTED", "SAMPLER_RESULT_INVALID",
    ]
    assert schema["$defs"]["success"]["allOf"][1]["properties"]["error"] == {"type": "null"}
    assert schema["$defs"]["failure"]["allOf"][1]["properties"]["structural_program_hash"] == {"type": "null"}


def test_planner_payloads_freeze_missing_metrics_and_diagnostics() -> None:
    request = _load("planner_request.schema.json")
    response = _load("planner_response.schema.json")
    metric = request["$defs"]["metric"]
    assert metric["required"] == ["metric_id", "value", "delta", "missing_reason"]
    assert metric["properties"]["missing_reason"]["enum"] == [
        None, "not_evaluated", "not_applicable", "unavailable", "uncalibrated",
    ]
    diagnostics = response["$defs"]["base"]["properties"]["diagnostic"]["enum"]
    assert diagnostics == [
        None, "PLANNER_REQUEST_INVALID", "PLANNER_CONTEXT_MISMATCH", "PLANNER_MANIFEST_MISMATCH",
        "PLANNER_SOURCE_MISMATCH", "PLANNER_REQUEST_TOO_LARGE", "PLANNER_PROVIDER_UNAVAILABLE",
        "PLANNER_TIMEOUT", "PLANNER_RESPONSE_TOO_LARGE", "PLANNER_RESPONSE_SCHEMA_INVALID",
        "PLANNER_OPERATION_NOT_ALLOWED", "PLANNER_MUTATION_COUNT_INVALID", "PLANNER_RESULT_INVALID",
    ]
    assert response["$defs"]["success"]["allOf"][1]["properties"]["diagnostic"] == {"type": "null"}
    success = response["$defs"]["success"]["allOf"][1]["properties"]
    failure = response["$defs"]["failure"]["allOf"][1]["properties"]
    assert success["mutation_proposal"]["items"] == {"$ref": "mutation.schema.json"}
    assert failure["mutation_proposal"] == {"type": "null"}
    assert failure["proposal_hash"] == {"type": "null"}
    assert "mutation_request_hash" not in response["$defs"]["base"]["properties"]


def test_group_a_contract_names_every_machine_schema_and_self_hash() -> None:
    text = (ROOT.parent / "docs" / "song_program_search_loop_13_payload_contract.md").read_text(encoding="utf-8")
    for filename in (
        "candidate_source_decision.schema.json", "structural_sampler_request.schema.json",
        "structural_sampler_result.schema.json", "planner_request.schema.json",
        "planner_response.schema.json",
    ):
        assert filename in text
    assert "decision_hash" in text
    assert "response_hash" in text
