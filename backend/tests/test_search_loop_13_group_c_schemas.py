from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCHEMAS = ROOT / "songprogram_conformance" / "schemas"


def _load(name: str) -> dict:
    return json.loads((SCHEMAS / name).read_text(encoding="utf-8"))


def test_group_c_closed_schemas_are_bound_by_manifest_and_context() -> None:
    manifest = _load("search_run_manifest_1_3.schema.json")
    context = _load("search_loop_13_context.schema.json")
    expected = {
        "compile_only_request": "compile_only_request_schema_hash",
        "compile_only_result": "compile_only_result_schema_hash",
        "compile_only_cache_entry": "compile_only_cache_entry_schema_hash",
        "cancellation_inbox_record": "cancellation_inbox_record_schema_hash",
        "cancellation_decision": "cancellation_decision_schema_hash",
    }
    for context_name, manifest_name in expected.items():
        assert manifest_name in manifest["required"]
        assert manifest_name in manifest["properties"]
        assert context_name in context["properties"]["schema_hashes"]["required"]
        assert context_name in context["properties"]["schema_hashes"]["properties"]

    for name in (
        "compile_only_request.schema.json",
        "compile_only_result.schema.json",
        "compile_only_cache_entry.schema.json",
        "cancellation_inbox_record_1_1.schema.json",
        "cancellation_decision_1_1.schema.json",
    ):
        schema = _load(name)
        assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
        assert schema.get("additionalProperties") is False or "oneOf" in schema


def test_compile_only_is_receipt_bound_and_has_no_mutation_body() -> None:
    request = _load("compile_only_request.schema.json")
    required = set(request["required"])
    assert {
        "source_decision_hash", "mutation_result_event_payload_hash",
        "mutation_application_receipt_hash", "result_program", "result_program_hash",
        "compiler_manifest_hash", "context_hash",
    } <= required
    assert "mutation_request" not in request["properties"]
    assert "mutations" not in request["properties"]

    result = _load("compile_only_result.schema.json")["$defs"]["base"]
    assert result["properties"]["cache_outcome"]["enum"] == ["cold", "hit"]
    assert result["properties"]["error"]["enum"] == [
        None, "COMPILE_REQUEST_INVALID", "COMPILE_CONTEXT_MISMATCH",
        "COMPILE_MANIFEST_MISMATCH", "COMPILE_SOURCE_MISMATCH",
        "COMPILE_PROGRAM_MISMATCH", "COMPILE_BUDGET_EXHAUSTED",
        "COMPILE_FAILED", "COMPILE_RESULT_INVALID",
    ]

    entry = _load("compile_only_cache_entry.schema.json")
    assert set(entry["required"]) >= {
        "request_hash", "compile_result_hash", "mutation_application_receipt_hash",
        "result_program_hash", "project_hash", "compile_report_hash", "logical_charge",
    }
    # Result names its request hash as the key, while the later entry names the
    # result. Neither self-hash includes the other object's self-hash.
    assert "entry_hash" not in result["properties"]
    assert "cache_key" not in entry["properties"]


def test_cancellation_inbox_and_decision_are_new_1_1_payloads() -> None:
    inbox = _load("cancellation_inbox_record_1_1.schema.json")
    assert inbox["properties"]["schema_version"]["const"] == "1.1.0"
    assert set(inbox["required"]) >= {
        "raw_request_bytes_base64", "raw_request_digest", "request_hash",
        "acceptance_sequence", "inbox_hash",
    }

    decision = _load("cancellation_decision_1_1.schema.json")
    assert decision["properties"]["schema_version"]["const"] == "1.1.0"
    cutoff = decision["$defs"]["coordinate"]
    assert cutoff["required"] == ["round", "phase_ordinal", "candidate_ordinal", "event_ordinal"]
    assert cutoff["properties"]["event_ordinal"]["minimum"] == 2

    legacy = _load("cancellation_decision.schema.json")
    assert legacy["properties"]["schema_version"]["const"] == "1.0.0"
    assert "context_hash" not in legacy["properties"]


def test_event_payload_binds_action_coordinate_to_artifact() -> None:
    event = _load("search_loop_13_event_payload.schema.json")
    assert {"run_hash", "context_hash", "action_id", "coordinate", "artifact_hash"} <= set(event["required"])
    assert event["$defs"]["coordinate"]["required"] == [
        "round", "phase_ordinal", "candidate_ordinal", "event_ordinal"
    ]

    text = (ROOT.parent / "docs" / "song_program_search_loop_13_payload_contract.md").read_text(encoding="utf-8")
    for filename in (
        "compile_only_request.schema.json", "compile_only_result.schema.json",
        "compile_only_cache_entry.schema.json", "cancellation_inbox_record_1_1.schema.json",
        "cancellation_decision_1_1.schema.json",
    ):
        assert filename in text
    assert "exactly the sealed `CompileOnlyRequest.request_hash`" in text
    assert "lexicographically lowest raw" in text
