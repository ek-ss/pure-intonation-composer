"""Deterministic audit-only reranking for validated synthetic PIL decisions."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from .pil_synthetic_audit_binding import require_permitted_use, validate_audit_binding
from .pil_synthetic_authority_validator import artifact_hash, decision_hash


class PILSyntheticRerankingError(ValueError):
    pass


def build_policy(metric_priorities: Sequence[Mapping[str, str]]) -> dict[str, Any]:
    rows = [dict(row) for row in metric_priorities]
    ids = [row.get("metric_id") for row in rows]
    if (
        not rows
        or len(ids) != len(set(ids))
        or any(row.get("direction") not in {"maximize", "minimize"} for row in rows)
    ):
        raise PILSyntheticRerankingError("PIL_SYNTHETIC_RERANK_POLICY_INVALID")
    value = {
        "schema": "cps.pil-synthetic-soft-reranking-policy",
        "schema_version": "1.0.0",
        "authority_effect": "audit_only",
        "comparison": "lexicographic_metric_priority_then_context_hash",
        "unavailable_policy": "after_available",
        "metric_priorities": rows,
        "policy_hash": "",
    }
    value["policy_hash"] = artifact_hash(value, "policy_hash")
    return value


def rerank(
    *,
    run_context_hash: str,
    policy: Mapping[str, Any],
    candidates: Sequence[tuple[Mapping[str, Any], Mapping[str, Any]]],
) -> dict[str, Any]:
    if policy.get("policy_hash") != artifact_hash(policy, "policy_hash"):
        raise PILSyntheticRerankingError("PIL_SYNTHETIC_RERANK_POLICY_INVALID")
    priorities = policy.get("metric_priorities", [])
    context_hashes: list[str] = []
    keyed: list[tuple[tuple[Any, ...], str]] = []
    for binding, decision in candidates:
        require_permitted_use(binding, "soft_reranking")
        if (
            binding.get("run_context_hash") != run_context_hash
            or binding.get("decision_hash") != decision.get("decision_hash")
            or decision.get("authority_effect") != "audit_only"
            or decision.get("decision_hash") != decision_hash(decision)
        ):
            raise PILSyntheticRerankingError("PIL_SYNTHETIC_CONTEXT_MISMATCH")
        validate_audit_binding(binding, run_context_hash=run_context_hash, decision=decision)
        context_hash = binding["sealed_context_hash"]
        if context_hash in context_hashes:
            raise PILSyntheticRerankingError("PIL_SYNTHETIC_RERANK_INPUT_INVALID")
        context_hashes.append(context_hash)
        metrics = {row["metric_id"]: row for row in decision.get("provisional_metrics", [])}
        key: list[Any] = []
        for priority in priorities:
            row = metrics.get(priority["metric_id"])
            observed = None if row is None else row.get("observed_q")
            key.extend((observed is None, 0 if observed is None else (
                -observed if priority["direction"] == "maximize" else observed
            )))
        key.append(context_hash)
        keyed.append((tuple(key), context_hash))
    if not keyed:
        raise PILSyntheticRerankingError("PIL_SYNTHETIC_RERANK_INPUT_INVALID")
    result = {
        "schema": "cps.pil-synthetic-soft-reranking-result",
        "schema_version": "1.0.0",
        "authority_effect": "audit_only",
        "run_context_hash": run_context_hash,
        "policy_hash": policy["policy_hash"],
        "input_context_hashes": sorted(context_hashes),
        "shadow_order": [context_hash for _, context_hash in sorted(keyed)],
        "result_hash": "",
    }
    result["result_hash"] = artifact_hash(result, "result_hash")
    return result
