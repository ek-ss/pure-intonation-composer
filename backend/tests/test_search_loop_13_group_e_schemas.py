from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCHEMAS = ROOT / "songprogram_conformance" / "schemas"
def load(name: str) -> dict: return json.loads((SCHEMAS / name).read_text(encoding="utf-8"))

PLANNER_ERRORS = ["PLANNER_REQUEST_INVALID","PLANNER_CONTEXT_MISMATCH","PLANNER_MANIFEST_MISMATCH","PLANNER_SOURCE_MISMATCH","PLANNER_REQUEST_TOO_LARGE","PLANNER_PROVIDER_UNAVAILABLE","PLANNER_TIMEOUT","PLANNER_RESPONSE_TOO_LARGE","PLANNER_RESPONSE_SCHEMA_INVALID","PLANNER_OPERATION_NOT_ALLOWED","PLANNER_MUTATION_COUNT_INVALID","PLANNER_RESULT_INVALID"]

def test_planner_diagnostic_order_is_exact_and_shared_by_fallback() -> None:
    assert load("planner_response.schema.json")["$defs"]["base"]["properties"]["diagnostic"]["enum"] == [None, *PLANNER_ERRORS]
    assert load("fallback_request_1_1.schema.json")["$defs"]["plannerFailure"]["properties"]["diagnostic"]["enum"] == PLANNER_ERRORS

def test_fallback_source_union_and_v2_coordinate() -> None:
    schema = load("fallback_request_1_1.schema.json")
    assert schema["$defs"]["plannerNull"]["required"] == ["kind"]
    assert schema["$defs"]["plannerFailure"]["required"] == ["kind","planner_response_hash","diagnostic"]
    assert schema["$defs"]["coordinate"]["properties"]["phase_ordinal"] == {"const":1}
    assert schema["$defs"]["coordinate"]["properties"]["event_ordinal"] == {"const":4}

def test_mutation_request_12_origin_union() -> None:
    schema = load("mutation_application_request_1_2.schema.json")
    assert schema["$defs"]["planner"]["required"] == ["kind","response_hash","proposal_hash"]
    assert schema["$defs"]["fallback"]["required"] == ["kind","fallback_request_hash","proposal_hash"]
    assert {"context_hash","source_decision_hash","origin"} <= set(schema["required"])

def test_fallback_result_single_receipt_or_failure() -> None:
    schema = load("fallback_result_1_1.schema.json")
    success = schema["$defs"]["success"]["allOf"][1]["properties"]
    pre = schema["$defs"]["preApplicationFailure"]["allOf"][1]["properties"]
    failed = schema["$defs"]["applicationFailure"]["allOf"][1]["properties"]
    assert success["application_receipt_hash"] == {"$ref":"#/$defs/sha"}
    for name in ("mutation_application_request_hash","application_receipt_hash","mutations","proposal_hash","final_program_hash"):
        assert pre[name] == {"type":"null"}
    assert failed["mutation_application_request_hash"] == {"$ref":"#/$defs/sha"}
    assert failed["application_receipt_hash"] == {"$ref":"#/$defs/sha"}
    assert failed["final_program_hash"] == {"type":"null"}
    assert failed["error"] == {"const":"FALLBACK_MUTATION_APPLICATION_FAILED"}

def test_raw_bindings_and_cancellation_constants() -> None:
    run = load("search_run_manifest_1_3.schema.json")
    context = load("search_loop_13_context.schema.json")["properties"]["schema_hashes"]
    for raw,key in (("fallback_request_schema_hash","fallback_request"),("fallback_result_schema_hash","fallback_result"),("mutation_request_schema_hash","mutation_request")):
        assert raw in run["required"] and key in context["required"]
    cancellation = load("cancellation_decision_1_1.schema.json")
    assert cancellation["properties"]["status"] == {"const":"accepted"}
    assert cancellation["properties"]["cancelled"] == {"const":True}

def test_context_has_no_dangling_mutation_result_schema_binding() -> None:
    hashes = load("search_loop_13_context.schema.json")["properties"]["schema_hashes"]
    assert "mutation_result" not in hashes["required"]
    assert "mutation_result" not in hashes["properties"]
    assert "mutation_receipt" in hashes["required"]
