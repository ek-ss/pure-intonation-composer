from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from .pil_external_authority_validator import (
    PILAuthorityError,
    artifact_hash,
    decision_hash,
    evidence_hash,
    validate_external_authority,
)

ROOT = Path(__file__).resolve().parent
SCHEMAS = ROOT / "schemas"
H = "sha256:" + "a" * 64


def _schema_validator(name: str, value: dict) -> bool:
    schema = json.loads((SCHEMAS / name).read_text(encoding="utf-8"))
    return (
        value.get("schema") == schema["properties"]["schema"]["const"]
        and value.get("schema_version") == schema["properties"]["schema_version"]["const"]
    )


def _genre_chain() -> tuple[dict, ...]:
    registry = json.loads(
        (ROOT / "fixtures" / "pil_calibration" / "genre_metric_registry.json").read_text()
    )
    listener = {
        "schema": "cps.listener-cohort-manifest",
        "schema_version": "1.0.0",
        "cohort_id": "external_2026",
        "participant_hashes": [H],
        "recruitment_protocol_hash": H,
        "eligibility_rule_hash": H,
        "exclusion_rule_hash": H,
        "consent_scope_hash": H,
        "minimum_completed_trials_per_listener": 1,
        "manifest_hash": "",
    }
    listener["manifest_hash"] = artifact_hash(listener, "manifest_hash")
    bindings = {
        "pil_manifest_hash": H,
        "oracle_suite_index_hash": H,
        "genre_intent_hash": H,
        "genre_model_hash": H,
        "genre_reference_set_manifest_hash": H,
    }
    rows = [
        {
            "metric_id": row["metric_id"],
            "aggregation": row["aggregation"],
            "direction": row["direction"],
            "missing_policy": "unavailable",
            "acceptance_threshold_q": 5000,
            "noninferiority_margin_q": 0,
            "improvement_margin_q": 1,
        }
        for row in registry["metrics"]
    ]
    policy = {
        "schema": "cps.pil-genre-calibration-acceptance-policy",
        "schema_version": "1.0.0",
        "scope": "genre_phase_5",
        **bindings,
        "phase5_build_id": "pil.phase5.1.0.0",
        "genre_metric_registry_hash": registry["registry_hash"],
        "minimum_listener_count": 1,
        "minimum_observation_count": 1,
        "metrics": rows,
        "policy_hash": "",
    }
    policy["policy_hash"] = artifact_hash(policy, "policy_hash")
    fixture = {
        "schema": "cps.pil-genre-calibration-fixture-set",
        "schema_version": "1.0.0",
        "scope": "genre_phase_5_external",
        **bindings,
        "phase5_build_id": "pil.phase5.1.0.0",
        "genre_metric_registry_hash": registry["registry_hash"],
        "listener_cohort_manifest_hash": listener["manifest_hash"],
        "genre_result_schema_hash": H,
        "genre_result_set_hash": H,
        "partition_membership_hash": H,
        "exclusion_rules_hash": H,
        "excluded_observation_hashes": [],
        "partition_leakage_count": 0,
        "acceptance_policy_hash": policy["policy_hash"],
        "fixture_set_hash": "",
    }
    fixture["fixture_set_hash"] = artifact_hash(fixture, "fixture_set_hash")
    evidence_rows = []
    for row in rows:
        observed = 4000 if row["direction"] == "minimize" else 6000
        evidence = {
            "metric_id": row["metric_id"],
            "aggregation": row["aggregation"],
            "direction": row["direction"],
            "missing_policy": "unavailable",
            "observed_q": observed,
            "acceptance_threshold_q": 5000,
            "passed": True,
            "source_observation_set_hash": H,
            "evidence_hash": "",
        }
        evidence["evidence_hash"] = evidence_hash(evidence)
        evidence_rows.append(evidence)
    summary = {
        "schema": "cps.pil-genre-calibration-metric-evidence-summary",
        "schema_version": "1.0.0",
        "scope": "genre_phase_5_external",
        "fixture_set_hash": fixture["fixture_set_hash"],
        "acceptance_policy_hash": policy["policy_hash"],
        "genre_metric_registry_hash": registry["registry_hash"],
        "listener_count": 1,
        "observation_count": 4,
        "metrics": evidence_rows,
        "all_required_metrics_passed": True,
        "summary_hash": "",
    }
    summary["summary_hash"] = artifact_hash(summary, "summary_hash")
    promotions = [
        {
            "metric_id": evidence["metric_id"],
            "aggregation": evidence["aggregation"],
            "direction": evidence["direction"],
            "acceptance_threshold_q": evidence["acceptance_threshold_q"],
            "missing_policy": "unavailable",
            "noninferiority_margin_q": 0,
            "improvement_margin_q": 1,
            "evidence_hash": evidence["evidence_hash"],
        }
        for evidence in evidence_rows
    ]
    decision = {
        "schema": "cps.pil-calibration-decision",
        "schema_version": "2.0.0",
        "scope": "genre_phase_5",
        "status": "promoted",
        **bindings,
        "phase5_build_id": "pil.phase5.1.0.0",
        "genre_metric_registry_hash": registry["registry_hash"],
        "calibration_fixture_set_hash": fixture["fixture_set_hash"],
        "acceptance_policy_hash": policy["policy_hash"],
        "evidence_summary_hash": summary["summary_hash"],
        "promoted_metrics": promotions,
        "metric_ids": [row["metric_id"] for row in promotions],
        "failure_code": None,
        "decision_hash": "",
    }
    decision["decision_hash"] = decision_hash(decision)
    return listener, registry, policy, fixture, summary, decision, bindings


def test_genre_external_authority_chain_is_accepted_read_only() -> None:
    listener, registry, policy, fixture, summary, decision, bindings = _genre_chain()
    before = copy.deepcopy((listener, registry, policy, fixture, summary, decision))
    assert (
        validate_external_authority(
            listener_cohort=listener,
            registry=registry,
            policy=policy,
            fixture_set=fixture,
            evidence_summary=summary,
            decision=decision,
            expected_bindings=bindings,
            schema_validator=_schema_validator,
        )
        == decision["decision_hash"]
    )
    assert (listener, registry, policy, fixture, summary, decision) == before


def test_genre_external_authority_rejects_hash_and_threshold_forgery() -> None:
    chain = list(_genre_chain())
    chain[4]["metrics"][0]["observed_q"] = 0
    with pytest.raises(PILAuthorityError) as caught:
        validate_external_authority(
            listener_cohort=chain[0],
            registry=chain[1],
            policy=chain[2],
            fixture_set=chain[3],
            evidence_summary=chain[4],
            decision=chain[5],
            expected_bindings=chain[6],
            schema_validator=_schema_validator,
        )
    assert caught.value.code == "PIL_GENRE_CALIBRATION_INPUT_INVALID"
