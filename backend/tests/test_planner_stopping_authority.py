from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCHEMAS = ROOT / "songprogram_conformance" / "schemas"
def load(name: str) -> dict: return json.loads((SCHEMAS / name).read_text())

def test_planner_prompt_and_invocation_are_closed_and_bound() -> None:
    prompt = load("planner_prompt_asset.schema.json")
    invocation = load("planner_invocation_policy.schema.json")
    assert prompt["additionalProperties"] is False
    assert invocation["additionalProperties"] is False
    for key in ("maximum_input_bytes", "maximum_output_bytes", "maximum_input_tokens",
                "maximum_output_tokens", "temperature_q", "top_p_q", "seed", "tool_policy",
                "tokenizer_manifest_hash", "response_schema_hash", "tool_catalog_hash"):
        assert key in invocation["required"]
    request = load("planner_request.schema.json")
    assert {"prompt_asset_hash", "invocation_policy_hash", "invocation_request_hash"} <= set(request["required"])
    manifest = load("search_run_manifest_1_3.schema.json")
    assert {"planner_prompt_asset_hash", "planner_invocation_policy_hash",
            "planner_prompt_asset_schema_hash", "planner_invocation_policy_schema_hash"} <= set(manifest["required"])
    context = load("search_loop_13_context.schema.json")
    assert {"planner_prompt_asset", "planner_invocation_policy"} <= set(context["properties"]["schema_hashes"]["required"])
    assert {"planner_prompt_asset", "planner_invocation_policy"} <= set(context["$defs"]["artifacts"]["required"])

def test_round_improvement_is_closed_and_bound() -> None:
    evidence = load("round_improvement_evidence.schema.json")
    row = evidence["$defs"]["row"]
    assert evidence["additionalProperties"] is False and row["additionalProperties"] is False
    assert {"archive_admission_decision_hash", "first_differing_component_id",
            "direction_normalized_delta", "meets_threshold"} <= set(row["required"])
    assert "improvement_evidence_hash" in load("round_decision.schema.json")["required"]
    manifest = load("search_run_manifest_1_3.schema.json")
    assert "round_improvement_evidence_schema_hash" in manifest["required"]

def test_qd_runner_semantics_and_identity_split_are_normative() -> None:
    artifacts = (ROOT.parent / "docs" / "song_program_search_artifacts_contract.md").read_text()
    payload = (ROOT.parent / "docs" / "song_program_search_loop_13_payload_contract.md").read_text()
    stopping = (ROOT.parent / "docs" / "song_program_search_decision_contract.md").read_text()
    assert "runner sharing a\nlineage root" in artifacts
    assert "run hash identifies\nsealed inputs" in payload
    assert "transcript\nroot identifies the realized response" in payload
    assert "direction_normalized_delta = after-before" in stopping
    assert "Program-hash tie-breaks" in stopping
