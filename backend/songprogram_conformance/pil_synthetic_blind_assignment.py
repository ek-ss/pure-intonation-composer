"""Deterministic blind assignment and replay for synthetic PIL judges."""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from typing import Any

from .pil_synthetic_authority_validator import artifact_hash


class PILSyntheticAssignmentError(ValueError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def _sha(domain: bytes, *values: str) -> str:
    payload = domain + b"\0" + b"\0".join(value.encode("ascii") for value in values)
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def build_blind_assignment_set(
    *,
    scope: str,
    protocol_hash: str,
    cohort_manifest_hash: str,
    agent_manifest_hashes: Sequence[str],
    sealed_context_hashes: Sequence[str],
) -> dict[str, Any]:
    """Build a worker-order-independent full agent-by-context assignment."""

    agents = sorted(agent_manifest_hashes)
    contexts = sorted(sealed_context_hashes)
    if not agents or not contexts or len(agents) != len(set(agents)) or len(contexts) != len(
        set(contexts)
    ):
        raise PILSyntheticAssignmentError("PIL_SYNTHETIC_BLINDING_INVALID")
    assignments: list[dict[str, Any]] = []
    for agent_hash in agents:
        ordered = sorted(
            contexts,
            key=lambda context_hash: _sha(
                b"cps.pil-synthetic-order/v1", protocol_hash, agent_hash, context_hash
            ),
        )
        for ordinal, context_hash in enumerate(ordered):
            opaque_hash = _sha(
                b"cps.pil-synthetic-opaque-item/v1",
                protocol_hash,
                agent_hash,
                context_hash,
            )
            assignment_id = _sha(
                b"cps.pil-synthetic-assignment/v1",
                protocol_hash,
                cohort_manifest_hash,
                agent_hash,
                context_hash,
                str(ordinal),
            )
            assignments.append(
                {
                    "assignment_id": assignment_id,
                    "agent_manifest_hash": agent_hash,
                    "sealed_context_hash": context_hash,
                    "opaque_item_id": "item_" + opaque_hash[7:31],
                    "presentation_ordinal": ordinal,
                }
            )
    assignments.sort(key=lambda value: value["assignment_id"])
    result = {
        "schema": "cps.pil-synthetic-blind-assignment-set",
        "schema_version": "1.0.0",
        "authority_kind": "synthetic_llm",
        "human_authority_compatible": False,
        "authority_effect": "audit_only",
        "scope": scope,
        "protocol_hash": protocol_hash,
        "cohort_manifest_hash": cohort_manifest_hash,
        "sealed_context_hashes": contexts,
        "assignments": assignments,
        "assignment_count": len(assignments),
        "assignment_set_hash": "",
    }
    result["assignment_set_hash"] = artifact_hash(result, "assignment_set_hash")
    return result


def replay_blind_assignment_set(value: dict[str, Any]) -> str:
    """Recompute an assignment set and return its identity only on exact replay."""

    agents = sorted({row["agent_manifest_hash"] for row in value.get("assignments", [])})
    expected = build_blind_assignment_set(
        scope=value.get("scope", ""),
        protocol_hash=value.get("protocol_hash", ""),
        cohort_manifest_hash=value.get("cohort_manifest_hash", ""),
        agent_manifest_hashes=agents,
        sealed_context_hashes=value.get("sealed_context_hashes", []),
    )
    if value != expected:
        raise PILSyntheticAssignmentError("PIL_SYNTHETIC_BLINDING_INVALID")
    return expected["assignment_set_hash"]
