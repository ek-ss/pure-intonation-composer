from __future__ import annotations

import json
from pathlib import Path

SCHEMAS = Path(__file__).resolve().parents[1] / "songprogram_conformance" / "schemas"
NAMES = (
    "pil_synthetic_protocol_manifest",
    "pil_synthetic_agent_manifest",
    "pil_synthetic_cohort_manifest",
    "pil_synthetic_blind_assignment_set",
    "pil_synthetic_raw_response_record",
    "pil_synthetic_judgment_set",
    "pil_synthetic_evidence_summary",
    "pil_synthetic_provisional_decision",
    "pil_synthetic_audit_binding",
)


def _load(name: str) -> dict:
    return json.loads((SCHEMAS / f"{name}.schema.json").read_text(encoding="utf-8"))


def test_synthetic_authority_family_is_closed_and_explicitly_nonhuman() -> None:
    for name in NAMES:
        schema = _load(name)
        assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
        assert schema["type"] == "object"
        assert schema["additionalProperties"] is False
        authority = schema["properties"]["authority_kind"]
        assert authority == {"const": "synthetic_llm"}
        assert schema["properties"]["human_authority_compatible"] == {"const": False}
        assert "human_authority_compatible" in schema["required"]

    for name in (
        "pil_synthetic_protocol_manifest",
        "pil_synthetic_cohort_manifest",
        "pil_synthetic_blind_assignment_set",
        "pil_synthetic_judgment_set",
        "pil_synthetic_evidence_summary",
        "pil_synthetic_provisional_decision",
    ):
        properties = _load(name)["properties"]
        assert properties["authority_effect"] == {"const": "audit_only"}


def test_synthetic_decision_cannot_claim_promotion_or_human_evidence() -> None:
    decision = _load("pil_synthetic_provisional_decision")
    properties = decision["properties"]
    assert properties["status"] == {"const": "synthetic_provisional"}
    assert properties["promotion_eligible"] == {"const": False}
    assert properties["human_listener_evidence"] == {"const": False}
    assert "promoted" not in json.dumps(decision, sort_keys=True)


def test_synthetic_raw_records_bind_model_execution_without_free_text_authority() -> None:
    record = _load("pil_synthetic_raw_response_record")
    required = set(record["required"])
    assert {
        "protocol_hash",
        "assignment_set_hash",
        "assignment_id",
        "agent_manifest_hash",
        "sealed_context_hash",
        "request_hash",
        "provider_response_hash",
        "judgments",
    } <= required
    assert "provider_response_text" not in record["properties"]
    assert "free_text" not in record["$defs"]["judgment"]["properties"]
    assert record["$defs"]["judgment"]["properties"]["ordinal_label"]["enum"][-1] == (
        "unavailable"
    )


def test_synthetic_cohort_is_not_a_listener_cohort() -> None:
    synthetic = _load("pil_synthetic_cohort_manifest")
    listener = _load("listener_cohort_manifest")
    assert synthetic["properties"]["schema"]["const"] == "cps.pil-synthetic-cohort-manifest"
    assert listener["properties"]["schema"]["const"] == "cps.listener-cohort-manifest"
    assert "participant_hashes" not in synthetic["properties"]
    assert "agent_manifest_hashes" not in listener["properties"]


def test_synthetic_protocol_requires_audio_independence_and_quorum() -> None:
    protocol = _load("pil_synthetic_protocol_manifest")
    assert protocol["properties"]["input_modality"] == {"const": "audio_pcm"}
    assert protocol["properties"]["audio_capable"] == {"const": True}
    assert {
        "generator_model_family_hash", "judge_model_family_hash", "minimum_agent_count"
    } <= set(protocol["required"])
