from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCHEMAS = ROOT / "songprogram_conformance" / "schemas"
DOCS = ROOT.parent / "docs"


def _load(name: str) -> dict:
    return json.loads((SCHEMAS / name).read_text(encoding="utf-8"))


MAPPING = {
    "candidate_source_decision": ("candidate_source_decision.schema.json", "candidate_source_decision_schema_hash", "candidate_source_decision"),
    "sampler_request": ("structural_sampler_request_1_1.schema.json", "sampler_request_schema_hash", "sampler_request"),
    "sampler_result": ("structural_sampler_result_1_1.schema.json", "sampler_result_schema_hash", "sampler_result"),
    "production_request": ("broad_prior_production_request_1_1.schema.json", "production_request_schema_hash", "production_request"),
    "production_result": ("broad_prior_production_result_1_1.schema.json", "production_result_schema_hash", "production_result"),
    "planner_request": ("planner_request.schema.json", "planner_request_schema_hash", "planner_request"),
    "planner_response": ("planner_response.schema.json", "planner_response_schema_hash", "planner_response"),
    "fallback_request": ("fallback_request_1_1.schema.json", "fallback_request_schema_hash", "fallback_request"),
    "mutation_request": ("mutation_application_request_1_2.schema.json", "mutation_request_schema_hash", "mutation_request"),
    "mutation_result": ("mutation_application_receipt.schema.json", "mutation_receipt_schema_hash", "mutation_receipt"),
    "fallback_result": ("fallback_result_1_1.schema.json", "fallback_result_schema_hash", "fallback_result"),
    "compile_request": ("compile_only_request.schema.json", "compile_only_request_schema_hash", "compile_only_request"),
    "compile_result": ("compile_only_result.schema.json", "compile_only_result_schema_hash", "compile_only_result"),
    "fingerprint_result": ("fingerprint_record.schema.json", "fingerprint_record_schema_hash", "fingerprint_record"),
    "near_duplicate_decision": ("near_duplicate_decision.schema.json", "near_duplicate_decision_schema_hash", "near_duplicate_decision"),
    "render_request": ("render_request.schema.json", "render_request_schema_hash", "render_request"),
    "render_reservation": ("render_charge.schema.json", "render_charge_schema_hash", "render_charge"),
    "render_dispatch": ("render_dispatch_authorization.schema.json", "render_dispatch_authorization_schema_hash", "render_dispatch_authorization"),
    "render_result": ("render_result.schema.json", "render_result_schema_hash", "render_result"),
    "evaluation_request": ("evaluation_request.schema.json", "evaluation_request_schema_hash", "evaluation_request"),
    "metric_report": ("evaluation_report_1_1.schema.json", "evaluation_report_schema_hash", "evaluation_report"),
    "challenger_acceptance_decision": ("challenger_acceptance_decision_1_1.schema.json", "challenger_acceptance_decision_schema_hash", "challenger_acceptance_decision"),
    "archive_admission_decision": ("archive_admission_decision.schema.json", "archive_admission_decision_schema_hash", "archive_admission_decision"),
    "archive_update": ("qd_archive_record.schema.json", "qd_archive_record_schema_hash", "qd_archive_record"),
    "round_decision": ("round_decision.schema.json", "round_decision_schema_hash", "round_decision"),
    "checkpoint": ("search_checkpoint_1_1.schema.json", "checkpoint_schema_hash", "checkpoint"),
    "cancellation_request": ("cancellation_inbox_record_1_1.schema.json", "cancellation_inbox_record_schema_hash", "cancellation_inbox_record"),
    "cancellation_decision": ("cancellation_decision_1_1.schema.json", "cancellation_decision_schema_hash", "cancellation_decision"),
}


def test_all_event_kinds_have_exact_schema_and_raw_byte_bindings() -> None:
    event = _load("search_loop_13_event_payload.schema.json")
    manifest = _load("search_run_manifest_1_3.schema.json")
    context = _load("search_loop_13_context.schema.json")["properties"]["schema_hashes"]
    assert set(event["properties"]["kind"]["enum"]) == set(MAPPING)
    for schema_name, manifest_field, context_field in MAPPING.values():
        assert (SCHEMAS / schema_name).is_file()
        assert manifest_field in manifest["required"]
        assert manifest_field in manifest["properties"]
        assert context_field in context["required"]
        assert context_field in context["properties"]


def test_event_payload_has_distinct_self_hash_contract() -> None:
    event = _load("search_loop_13_event_payload.schema.json")
    assert event["additionalProperties"] is False
    assert "payload_hash" in event["required"]
    assert "payload_hash" in event["properties"]
    text = (DOCS / "song_program_search_loop_13_payload_contract.md").read_text(encoding="utf-8")
    assert "with no trailing LF" in text
    assert "`RunRecord.payload_hash` MUST equal this value" in text
    assert "MUST NOT equal the inner `artifact_hash`" in text


def test_render_supporting_artifacts_are_closed_and_bound() -> None:
    manifest = _load("search_run_manifest_1_3.schema.json")
    context = _load("search_loop_13_context.schema.json")["properties"]["schema_hashes"]
    for base in ("render_cache_entry", "render_cache_corruption_receipt", "audio_artifact"):
        schema = _load(f"{base}.schema.json")
        assert schema["additionalProperties"] is False
        assert f"{base}_schema_hash" in manifest["required"]
        assert base in context["required"]
    authorization = _load("render_dispatch_authorization.schema.json")
    assert authorization["properties"]["authorization"]["const"] == "dispatch"
    failure = _load("render_failure.schema.json")
    assert failure["additionalProperties"] is False
    assert "render_failure_schema_hash" in manifest["required"]
    assert "render_failure" in context["required"]
    assert failure["properties"]["code"]["enum"][0] == "RENDER_REQUEST_INVALID"
    assert failure["properties"]["code"]["enum"][-1] == "RENDER_RESULT_INVALID"


def test_audio_and_corruption_render_contract_is_closed() -> None:
    audio = _load("audio_artifact.schema.json")
    assert audio["additionalProperties"] is False
    assert audio["properties"]["encoding"] == {"const": "pcm_s32"}
    assert audio["properties"]["sample_rate_hz"] == {"const": 48000}
    assert audio["properties"]["channels"] == {"const": 2}
    result = _load("render_result.schema.json")
    assert "corruption_receipt_hash" in result["required"]
    for index in (0, 1, 3):
        assert result["allOf"][index]["then"]["properties"]["corruption_receipt_hash"] == {"type": "null"}
    text = (DOCS / "song_program_search_loop_13_payload_contract.md").read_text(encoding="utf-8")
    assert "frame_count * 2 * 4" in text
    assert "RenderCacheEntry.request_hash` MUST both equal the sealed" in text
    assert "every exact\nraw byte returned by the cache read" in text
    assert "event-3 RenderResult MUST then commit" in text


def test_normative_table_contains_every_mapping_row() -> None:
    text = (DOCS / "song_program_search_loop_13_payload_contract.md").read_text(encoding="utf-8")
    for kind, (schema_name, manifest_field, context_field) in MAPPING.items():
        row = f"| `{kind}` | `{schema_name}` | `{manifest_field}` | `{context_field}` |"
        assert row in text
