from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from .pil_synthetic_authority_validator import (
    PILSyntheticAuthorityError,
    artifact_hash,
    decision_hash,
    evidence_hash,
    validate_synthetic_provisional_authority,
)
from .pil_synthetic_blind_assignment import build_blind_assignment_set


ROOT = Path(__file__).resolve().parent
SCHEMAS = ROOT / "schemas"
H = "sha256:" + "a" * 64


def _schema_validator(name: str, value: dict) -> bool:
    schema = json.loads((SCHEMAS / name).read_text(encoding="utf-8"))
    return (
        value.get("schema") == schema["properties"]["schema"]["const"]
        and value.get("schema_version") == schema["properties"]["schema_version"]["const"]
    )


def _seal(value: dict, member: str) -> dict:
    value[member] = artifact_hash(value, member)
    return value


def _chain() -> dict:
    registry = json.loads(
        (ROOT / "fixtures" / "pil_calibration" / "genre_metric_registry.json").read_text()
    )
    protocol = _seal(
        {
            "schema": "cps.pil-synthetic-protocol-manifest",
            "schema_version": "1.0.0",
            "authority_kind": "synthetic_llm",
            "human_authority_compatible": False,
            "human_listener_evidence": False,
            "authority_effect": "audit_only",
            "scope": "genre_phase_5",
            "task": "sealed_pil_semantic_style_judgment",
            "input_modality": "audio_pcm",
            "audio_capable": True,
            "provider": "openai",
            "model": "gpt-test",
            "model_snapshot": "gpt-test-1",
            "generator_model_family_hash": "sha256:" + "b" * 64,
            "judge_model_family_hash": "sha256:" + "c" * 64,
            "reasoning_effort": "high",
            "prompt_asset_hash": H,
            "input_schema_hash": H,
            "output_schema_hash": H,
            "evaluation_policy_hash": H,
            "minimum_agent_count": 2,
            "protocol_hash": "",
        },
        "protocol_hash",
    )
    agents = []
    for ordinal in range(2):
        agents.append(
            _seal(
                {
                    "schema": "cps.pil-synthetic-agent-manifest",
                    "schema_version": "1.0.0",
                    "authority_kind": "synthetic_llm",
                    "human_authority_compatible": False,
                    "human_listener": False,
                    "agent_id": f"agent_{ordinal}",
                    "protocol_hash": protocol["protocol_hash"],
                    "independent_seed": ordinal,
                    "execution_environment_hash": H,
                    "manifest_hash": "",
                },
                "manifest_hash",
            )
        )
    agents.sort(key=lambda value: value["manifest_hash"])
    cohort = _seal(
        {
            "schema": "cps.pil-synthetic-cohort-manifest",
            "schema_version": "1.0.0",
            "authority_kind": "synthetic_llm",
            "human_authority_compatible": False,
            "human_listener_evidence": False,
            "authority_effect": "audit_only",
            "cohort_id": "synthetic_test",
            "protocol_hash": protocol["protocol_hash"],
            "agent_manifest_hashes": [agent["manifest_hash"] for agent in agents],
            "agent_count": len(agents),
            "manifest_hash": "",
        },
        "manifest_hash",
    )
    assignment_set = build_blind_assignment_set(
        scope="genre_phase_5",
        protocol_hash=protocol["protocol_hash"],
        cohort_manifest_hash=cohort["manifest_hash"],
        agent_manifest_hashes=[agent["manifest_hash"] for agent in agents],
        sealed_context_hashes=[H],
    )
    assignment_by_agent = {
        row["agent_manifest_hash"]: row for row in assignment_set["assignments"]
    }
    metric_id = registry["metrics"][0]["metric_id"]
    responses = []
    for ordinal, agent in enumerate(agents):
        responses.append(
            _seal(
                {
                    "schema": "cps.pil-synthetic-raw-response-record",
                    "schema_version": "1.0.0",
                    "authority_kind": "synthetic_llm",
                    "human_authority_compatible": False,
                    "human_listener_response": False,
                    "scope": "genre_phase_5",
                    "protocol_hash": protocol["protocol_hash"],
                    "assignment_set_hash": assignment_set["assignment_set_hash"],
                    "assignment_id": assignment_by_agent[agent["manifest_hash"]]["assignment_id"],
                    "agent_manifest_hash": agent["manifest_hash"],
                    "sealed_context_hash": H,
                    "request_hash": H,
                    "provider_response_hash": "sha256:" + str(ordinal + 1) * 64,
                    "judgments": [
                        {"metric_id": metric_id, "ordinal_label": "below", "available": True}
                    ],
                    "record_hash": "",
                },
                "record_hash",
            )
        )
    responses.sort(key=lambda value: value["record_hash"])
    judgment_set = _seal(
        {
            "schema": "cps.pil-synthetic-judgment-set",
            "schema_version": "1.0.0",
            "authority_kind": "synthetic_llm",
            "human_authority_compatible": False,
            "human_listener_evidence": False,
            "authority_effect": "audit_only",
            "scope": "genre_phase_5",
            "protocol_hash": protocol["protocol_hash"],
            "cohort_manifest_hash": cohort["manifest_hash"],
            "assignment_set_hash": assignment_set["assignment_set_hash"],
            "sealed_context_set_hash": H,
            "response_record_hashes": [response["record_hash"] for response in responses],
            "response_count": len(responses),
            "partition_membership_hash": H,
            "partition_leakage_count": 0,
            "judgment_set_hash": "",
        },
        "judgment_set_hash",
    )
    registered = registry["metrics"][0]
    row = {
        "metric_id": metric_id,
        "aggregation": registered["aggregation"],
        "direction": registered["direction"],
        "missing_policy": registered["missing_policy"],
        "observed_q": 2500,
        "acceptance_threshold_q": 5000,
        "passed": True,
        "source_judgment_hash": judgment_set["judgment_set_hash"],
        "evidence_hash": "",
    }
    row["evidence_hash"] = evidence_hash(row)
    summary = _seal(
        {
            "schema": "cps.pil-synthetic-evidence-summary",
            "schema_version": "1.0.0",
            "authority_kind": "synthetic_llm",
            "human_authority_compatible": False,
            "human_listener_evidence": False,
            "authority_effect": "audit_only",
            "scope": "genre_phase_5",
            "protocol_hash": protocol["protocol_hash"],
            "cohort_manifest_hash": cohort["manifest_hash"],
            "judgment_set_hash": judgment_set["judgment_set_hash"],
            "metric_registry_hash": registry["registry_hash"],
            "evaluation_policy_hash": H,
            "agent_count": len(agents),
            "observation_count": len(responses),
            "aggregation_algorithm": "ordinal-label-median-q/v1",
            "metrics": [row],
            "all_required_metrics_passed": True,
            "summary_hash": "",
        },
        "summary_hash",
    )
    provisional = {
        key: row[key]
        for key in (
            "metric_id", "direction", "observed_q", "acceptance_threshold_q", "passed",
            "evidence_hash",
        )
    }
    decision = {
        "schema": "cps.pil-synthetic-provisional-decision",
        "schema_version": "1.0.0",
        "authority_kind": "synthetic_llm",
        "human_authority_compatible": False,
        "human_listener_evidence": False,
        "authority_effect": "audit_only",
        "promotion_eligible": False,
        "status": "synthetic_provisional",
        "scope": "genre_phase_5",
        "pil_manifest_hash": H,
        "metric_registry_hash": registry["registry_hash"],
        "oracle_suite_index_hash": H,
        "protocol_hash": protocol["protocol_hash"],
        "cohort_manifest_hash": cohort["manifest_hash"],
        "judgment_set_hash": judgment_set["judgment_set_hash"],
        "evaluation_policy_hash": H,
        "evidence_summary_hash": summary["summary_hash"],
        "provisional_metrics": [provisional],
        "metric_ids": [metric_id],
        "failure_code": None,
        "decision_hash": "",
    }
    decision["decision_hash"] = decision_hash(decision)
    return {
        "protocol": protocol, "agents": agents, "cohort": cohort,
        "assignment_set": assignment_set, "responses": responses,
        "judgment_set": judgment_set, "registry": registry, "evidence_summary": summary,
        "decision": decision, "expected_bindings": {
            "pil_manifest_hash": H, "oracle_suite_index_hash": H,
        }, "schema_validator": _schema_validator,
    }


def _validate(chain: dict) -> str:
    return validate_synthetic_provisional_authority(**chain)


def _reseal_response_chain(chain: dict) -> None:
    chain["responses"].sort(key=lambda value: value["record_hash"])
    judgment_set = chain["judgment_set"]
    judgment_set["response_record_hashes"] = [
        response["record_hash"] for response in chain["responses"]
    ]
    judgment_set["judgment_set_hash"] = artifact_hash(judgment_set, "judgment_set_hash")
    summary = chain["evidence_summary"]
    summary["judgment_set_hash"] = judgment_set["judgment_set_hash"]
    summary["metrics"][0]["source_judgment_hash"] = judgment_set["judgment_set_hash"]
    summary["metrics"][0]["evidence_hash"] = evidence_hash(summary["metrics"][0])
    summary["summary_hash"] = artifact_hash(summary, "summary_hash")
    decision = chain["decision"]
    decision["judgment_set_hash"] = judgment_set["judgment_set_hash"]
    decision["evidence_summary_hash"] = summary["summary_hash"]
    decision["provisional_metrics"][0]["evidence_hash"] = summary["metrics"][0][
        "evidence_hash"
    ]
    decision["decision_hash"] = decision_hash(decision)


def test_complete_synthetic_chain_is_accepted_read_only() -> None:
    chain = _chain()
    before = copy.deepcopy(chain)
    assert _validate(chain) == chain["decision"]["decision_hash"]
    assert chain == before


@pytest.mark.parametrize(
    ("mutate", "code"),
    [
        (lambda c: c["cohort"].update(agent_count=3), "PIL_SYNTHETIC_INPUT_INVALID"),
        (lambda c: c["responses"][0]["judgments"][0].update(available=False), "PIL_SYNTHETIC_INPUT_INVALID"),
        (lambda c: c["evidence_summary"].update(observation_count=9), "PIL_SYNTHETIC_INPUT_INVALID"),
        (lambda c: c["decision"].update(pil_manifest_hash="sha256:" + "b" * 64), "PIL_SYNTHETIC_RESULT_INVALID"),
    ],
)
def test_tampering_is_rejected_before_links_are_trusted(mutate, code: str) -> None:
    chain = _chain()
    mutate(chain)
    with pytest.raises(PILSyntheticAuthorityError) as caught:
        _validate(chain)
    assert caught.value.code == code


def test_resealed_bad_count_and_available_semantics_are_rejected() -> None:
    chain = _chain()
    chain["cohort"]["agent_count"] = 3
    chain["cohort"]["manifest_hash"] = artifact_hash(chain["cohort"], "manifest_hash")
    with pytest.raises(PILSyntheticAuthorityError) as caught:
        _validate(chain)
    assert caught.value.code == "PIL_SYNTHETIC_RESULT_INVALID"

    chain = _chain()
    response = chain["responses"][0]
    response["judgments"][0]["available"] = False
    response["record_hash"] = artifact_hash(response, "record_hash")
    chain["responses"].sort(key=lambda value: value["record_hash"])
    with pytest.raises(PILSyntheticAuthorityError) as caught:
        _validate(chain)
    assert caught.value.code in {"PIL_SYNTHETIC_CONTEXT_MISMATCH", "PIL_SYNTHETIC_RESULT_INVALID"}


def test_human_external_artifact_is_never_accepted_in_synthetic_slot() -> None:
    chain = _chain()
    chain["cohort"] = {
        "schema": "cps.listener-cohort-manifest",
        "schema_version": "1.0.0",
    }
    with pytest.raises(PILSyntheticAuthorityError) as caught:
        _validate(chain)
    assert caught.value.code == "PIL_SYNTHETIC_INPUT_INVALID"


def test_duplicate_agent_votes_are_rejected_even_with_distinct_records() -> None:
    chain = _chain()
    duplicate = copy.deepcopy(chain["responses"][0])
    duplicate["provider_response_hash"] = "sha256:" + "f" * 64
    duplicate["record_hash"] = artifact_hash(duplicate, "record_hash")
    chain["responses"][1] = duplicate
    chain["responses"].sort(key=lambda value: value["record_hash"])
    with pytest.raises(PILSyntheticAuthorityError) as caught:
        _validate(chain)
    assert caught.value.code == "PIL_SYNTHETIC_INPUT_INVALID"


def test_quorum_is_enforced_per_metric_not_only_per_cohort() -> None:
    chain = _chain()
    response = chain["responses"][0]
    response["judgments"][0] = {
        "metric_id": response["judgments"][0]["metric_id"],
        "ordinal_label": "unavailable",
        "available": False,
    }
    response["record_hash"] = artifact_hash(response, "record_hash")
    _reseal_response_chain(chain)
    with pytest.raises(PILSyntheticAuthorityError) as caught:
        _validate(chain)
    assert caught.value.code == "PIL_SYNTHETIC_THRESHOLD_NOT_MET"


def test_same_generator_and_judge_family_is_rejected() -> None:
    chain = _chain()
    protocol = chain["protocol"]
    protocol["judge_model_family_hash"] = protocol["generator_model_family_hash"]
    protocol["protocol_hash"] = artifact_hash(protocol, "protocol_hash")
    with pytest.raises(PILSyntheticAuthorityError) as caught:
        _validate(chain)
    assert caught.value.code == "PIL_SYNTHETIC_CONTEXT_MISMATCH"


def test_summary_observation_is_recomputed_from_fixed_ordinal_mapping() -> None:
    chain = _chain()
    summary = chain["evidence_summary"]
    summary["metrics"][0]["observed_q"] = 2400
    summary["metrics"][0]["evidence_hash"] = evidence_hash(summary["metrics"][0])
    summary["summary_hash"] = artifact_hash(summary, "summary_hash")
    with pytest.raises(PILSyntheticAuthorityError) as caught:
        _validate(chain)
    assert caught.value.code == "PIL_SYNTHETIC_RESULT_INVALID"
