"""Canonical bundle construction and read-only replay for synthetic PIL authority."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from .pil_synthetic_authority_validator import (
    SchemaValidator,
    artifact_hash,
    validate_synthetic_provisional_authority,
)


class PILSyntheticBundleError(ValueError):
    pass


def build_bundle_index(
    *,
    protocol: Mapping[str, Any],
    agents: Sequence[Mapping[str, Any]],
    cohort: Mapping[str, Any],
    assignment_set: Mapping[str, Any],
    responses: Sequence[Mapping[str, Any]],
    judgment_set: Mapping[str, Any],
    registry: Mapping[str, Any],
    evidence_summary: Mapping[str, Any],
    decision: Mapping[str, Any],
) -> dict[str, Any]:
    value = {
        "schema": "cps.pil-synthetic-bundle-index",
        "schema_version": "1.0.0",
        "authority_kind": "synthetic_llm",
        "human_authority_compatible": False,
        "protocol_hash": protocol["protocol_hash"],
        "agent_manifest_hashes": sorted(agent["manifest_hash"] for agent in agents),
        "cohort_manifest_hash": cohort["manifest_hash"],
        "assignment_set_hash": assignment_set["assignment_set_hash"],
        "response_record_hashes": sorted(response["record_hash"] for response in responses),
        "judgment_set_hash": judgment_set["judgment_set_hash"],
        "registry_hash": registry["registry_hash"],
        "evidence_summary_hash": evidence_summary["summary_hash"],
        "decision_hash": decision["decision_hash"],
        "bundle_hash": "",
    }
    value["bundle_hash"] = artifact_hash(value, "bundle_hash")
    return value


def replay_bundle(
    *,
    index: Mapping[str, Any],
    protocol: Mapping[str, Any],
    agents: Sequence[Mapping[str, Any]],
    cohort: Mapping[str, Any],
    assignment_set: Mapping[str, Any],
    responses: Sequence[Mapping[str, Any]],
    judgment_set: Mapping[str, Any],
    registry: Mapping[str, Any],
    evidence_summary: Mapping[str, Any],
    decision: Mapping[str, Any],
    expected_bindings: Mapping[str, str],
    schema_validator: SchemaValidator,
) -> str:
    if not schema_validator("pil_synthetic_bundle_index.schema.json", index):
        raise PILSyntheticBundleError("PIL_SYNTHETIC_BUNDLE_INPUT_INVALID")
    expected = build_bundle_index(
        protocol=protocol,
        agents=agents,
        cohort=cohort,
        assignment_set=assignment_set,
        responses=responses,
        judgment_set=judgment_set,
        registry=registry,
        evidence_summary=evidence_summary,
        decision=decision,
    )
    if dict(index) != expected:
        raise PILSyntheticBundleError("PIL_SYNTHETIC_BUNDLE_INDEX_MISMATCH")
    validate_synthetic_provisional_authority(
        protocol=protocol,
        agents=agents,
        cohort=cohort,
        assignment_set=assignment_set,
        responses=responses,
        judgment_set=judgment_set,
        registry=registry,
        evidence_summary=evidence_summary,
        decision=decision,
        expected_bindings=expected_bindings,
        schema_validator=schema_validator,
    )
    return expected["bundle_hash"]
