"""Deterministically aggregate stored synthetic judgments into audit authority."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from .pil_synthetic_authority_validator import artifact_hash, decision_hash, evidence_hash

ORDINAL_Q = {
    "strongly_below": 0, "below": 2500, "borderline": 5000,
    "above": 7500, "strongly_above": 10000,
}


class PILSyntheticAggregationError(ValueError):
    pass


def build_evaluation_policy(
    *, scope: str, metric_registry_hash: str, minimum_agent_count: int,
    metrics: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    rows = sorted((dict(row) for row in metrics), key=lambda row: row["metric_id"])
    if not rows or len({row["metric_id"] for row in rows}) != len(rows):
        raise PILSyntheticAggregationError("PIL_SYNTHETIC_POLICY_INVALID")
    value = {
        "schema": "cps.pil-synthetic-evaluation-policy", "schema_version": "1.0.0",
        "authority_effect": "audit_only", "scope": scope,
        "metric_registry_hash": metric_registry_hash,
        "minimum_agent_count": minimum_agent_count,
        "ordinal_mapping": ORDINAL_Q, "even_median": "round_half_to_even",
        "metrics": rows, "policy_hash": "",
    }
    value["policy_hash"] = artifact_hash(value, "policy_hash")
    return value


def _median(values: list[int]) -> int | None:
    if not values:
        return None
    values.sort()
    middle = len(values) // 2
    if len(values) % 2:
        return values[middle]
    total = values[middle - 1] + values[middle]
    quotient, remainder = divmod(total, 2)
    return quotient + (1 if remainder and quotient % 2 else 0)


def aggregate(
    *, protocol: Mapping[str, Any], cohort: Mapping[str, Any],
    assignment_set: Mapping[str, Any], responses: Sequence[Mapping[str, Any]],
    registry: Mapping[str, Any], policy: Mapping[str, Any],
    expected_bindings: Mapping[str, str], sealed_context_set_hash: str,
    partition_membership_hash: str,
) -> dict[str, dict[str, Any]]:
    if (
        policy.get("policy_hash") != artifact_hash(policy, "policy_hash")
        or policy.get("policy_hash") != protocol.get("evaluation_policy_hash")
        or policy.get("metric_registry_hash") != registry.get("registry_hash")
        or policy.get("minimum_agent_count") != protocol.get("minimum_agent_count")
        or policy.get("scope") != protocol.get("scope")
    ):
        raise PILSyntheticAggregationError("PIL_SYNTHETIC_POLICY_INVALID")
    response_hashes = sorted(response["record_hash"] for response in responses)
    judgment_set = {
        "schema": "cps.pil-synthetic-judgment-set", "schema_version": "1.0.0",
        "authority_kind": "synthetic_llm", "human_authority_compatible": False,
        "human_listener_evidence": False, "authority_effect": "audit_only",
        "scope": protocol["scope"], "protocol_hash": protocol["protocol_hash"],
        "cohort_manifest_hash": cohort["manifest_hash"],
        "assignment_set_hash": assignment_set["assignment_set_hash"],
        "sealed_context_set_hash": sealed_context_set_hash,
        "response_record_hashes": response_hashes, "response_count": len(responses),
        "partition_membership_hash": partition_membership_hash,
        "partition_leakage_count": 0, "judgment_set_hash": "",
    }
    judgment_set["judgment_set_hash"] = artifact_hash(judgment_set, "judgment_set_hash")
    registry_rows = {row["metric_id"]: row for row in registry["metrics"]}
    summary_rows = []
    for policy_row in policy["metrics"]:
        metric_id = policy_row["metric_id"]
        registered = registry_rows.get(metric_id)
        if registered is None:
            raise PILSyntheticAggregationError("PIL_SYNTHETIC_POLICY_INVALID")
        values = [
            ORDINAL_Q[judgment["ordinal_label"]]
            for response in responses for judgment in response["judgments"]
            if judgment["metric_id"] == metric_id and judgment["available"]
        ]
        agent_count = len({
            response["agent_manifest_hash"] for response in responses
            if any(j["metric_id"] == metric_id and j["available"] for j in response["judgments"])
        })
        observed = _median(values) if agent_count >= policy["minimum_agent_count"] else None
        threshold = policy_row["acceptance_threshold_q"]
        passed = observed is not None and (
            observed >= threshold if registered["direction"] == "maximize" else observed <= threshold
        )
        row = {
            "metric_id": metric_id, "aggregation": registered["aggregation"],
            "direction": registered["direction"], "missing_policy": registered["missing_policy"],
            "observed_q": observed, "acceptance_threshold_q": threshold, "passed": passed,
            "source_judgment_hash": judgment_set["judgment_set_hash"], "evidence_hash": "",
        }
        row["evidence_hash"] = evidence_hash(row)
        summary_rows.append(row)
    all_pass = all(row["passed"] for row in summary_rows)
    summary = {
        "schema": "cps.pil-synthetic-evidence-summary", "schema_version": "1.0.0",
        "authority_kind": "synthetic_llm", "human_authority_compatible": False,
        "human_listener_evidence": False, "authority_effect": "audit_only",
        "scope": protocol["scope"], "protocol_hash": protocol["protocol_hash"],
        "cohort_manifest_hash": cohort["manifest_hash"],
        "judgment_set_hash": judgment_set["judgment_set_hash"],
        "metric_registry_hash": registry["registry_hash"],
        "evaluation_policy_hash": policy["policy_hash"], "agent_count": cohort["agent_count"],
        "observation_count": sum(len(r["judgments"]) for r in responses),
        "aggregation_algorithm": "ordinal-label-median-q/v1", "metrics": summary_rows,
        "all_required_metrics_passed": all_pass, "summary_hash": "",
    }
    summary["summary_hash"] = artifact_hash(summary, "summary_hash")
    provisional = [{key: row[key] for key in (
        "metric_id", "direction", "observed_q", "acceptance_threshold_q", "passed", "evidence_hash"
    )} for row in summary_rows]
    decision = {
        "schema": "cps.pil-synthetic-provisional-decision", "schema_version": "1.0.0",
        "authority_kind": "synthetic_llm", "human_authority_compatible": False,
        "human_listener_evidence": False, "authority_effect": "audit_only",
        "promotion_eligible": False, "status": "synthetic_provisional",
        "scope": protocol["scope"], "pil_manifest_hash": expected_bindings["pil_manifest_hash"],
        "metric_registry_hash": registry["registry_hash"],
        "oracle_suite_index_hash": expected_bindings["oracle_suite_index_hash"],
        "protocol_hash": protocol["protocol_hash"], "cohort_manifest_hash": cohort["manifest_hash"],
        "judgment_set_hash": judgment_set["judgment_set_hash"],
        "evaluation_policy_hash": policy["policy_hash"], "evidence_summary_hash": summary["summary_hash"],
        "provisional_metrics": provisional, "metric_ids": [r["metric_id"] for r in summary_rows],
        "failure_code": None if all_pass else "PIL_SYNTHETIC_THRESHOLD_NOT_MET", "decision_hash": "",
    }
    decision["decision_hash"] = decision_hash(decision)
    return {"judgment_set": judgment_set, "evidence_summary": summary, "decision": decision}
