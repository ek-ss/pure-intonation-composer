"""Build and validate the out-of-band SearchLoop13 synthetic audit binding."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .pil_synthetic_authority_validator import artifact_hash

PERMITTED_USES = [
    "human_review_selection",
    "planner_diagnostics",
    "shadow_archive",
    "soft_reranking",
]


class PILSyntheticAuditBindingError(ValueError):
    pass


def build_audit_binding(
    *,
    run_context_hash: str,
    sealed_context_hash: str,
    decision: Mapping[str, Any],
    assignment_set_hash: str,
) -> dict[str, Any]:
    if (
        decision.get("schema") != "cps.pil-synthetic-provisional-decision"
        or decision.get("authority_effect") != "audit_only"
        or decision.get("promotion_eligible") is not False
        or decision.get("human_authority_compatible") is not False
    ):
        raise PILSyntheticAuditBindingError("PIL_SYNTHETIC_AUTHORITY_KIND_MISMATCH")
    value = {
        "schema": "cps.pil-synthetic-audit-binding",
        "schema_version": "1.0.0",
        "authority_kind": "synthetic_llm",
        "human_authority_compatible": False,
        "authority_effect": "audit_only",
        "run_context_hash": run_context_hash,
        "sealed_context_hash": sealed_context_hash,
        "decision_hash": decision["decision_hash"],
        "assignment_set_hash": assignment_set_hash,
        "permitted_uses": PERMITTED_USES,
        "binding_hash": "",
    }
    value["binding_hash"] = artifact_hash(value, "binding_hash")
    return value


def validate_audit_binding(
    value: Mapping[str, Any], *, run_context_hash: str, decision: Mapping[str, Any]
) -> str:
    expected = build_audit_binding(
        run_context_hash=run_context_hash,
        sealed_context_hash=value.get("sealed_context_hash", ""),
        decision=decision,
        assignment_set_hash=value.get("assignment_set_hash", ""),
    )
    if dict(value) != expected:
        raise PILSyntheticAuditBindingError("PIL_SYNTHETIC_CONTEXT_MISMATCH")
    return expected["binding_hash"]


def require_permitted_use(binding: Mapping[str, Any], requested_use: str) -> None:
    if requested_use not in binding.get("permitted_uses", ()):
        raise PILSyntheticAuditBindingError("PIL_SYNTHETIC_USE_FORBIDDEN")
