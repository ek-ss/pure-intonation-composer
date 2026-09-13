"""Independent phase-0 schedule-failure fixture builder.

The shared RunManifest/RunContext authority is injected by its golden owner.
This module never fabricates a manifest, context, policy, budget, or binding.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from .search_loop13_cancel_fixture_builder import SCHEMAS, raw_hash
from .search_loop13_fixture_oracle import artifact_hash, canonical_json, parity_group_hash


@dataclass(frozen=True)
class SharedContextAuthority:
    run_hash: str
    context_hash: str
    context_input: Mapping[str, Any]
    policies: Mapping[str, Any]
    budgets: Mapping[str, Any]
    cas_objects: Sequence[tuple[str, bytes, str, str]]
    edge_registry_entries: Sequence[Mapping[str, Any]]


def _schema_hash(name: str) -> str:
    return raw_hash((SCHEMAS / name).read_bytes())


def build(authority: SharedContextAuthority) -> dict[str, bytes]:
    """Build bytes for an absent phase-0/event-2 subject failure case."""
    if authority.context_input.get("artifact_hash") != authority.context_hash:
        raise ValueError("context input does not bind injected context_hash")
    if authority.context_input.get("role") != "run_context":
        raise ValueError("shared authority canonical root role must be run_context")
    if not authority.cas_objects or not authority.edge_registry_entries:
        raise ValueError("shared authority closure must not be empty")

    coordinate = {"round": 0, "phase_ordinal": 0, "candidate_ordinal": 0, "event_ordinal": 2}
    evidence = {
        "schema": "cps.conformance-violation-evidence",
        "schema_version": "1.0.0",
        "run_hash": authority.run_hash,
        "context_hash": authority.context_hash,
        "coordinate": coordinate,
        "stage": "schedule",
        "subject_schema_hash": _schema_hash("candidate_source_decision.schema.json"),
        "subject_hash": None,
        "failure_code": "CONFORMANCE_VIOLATION",
        "evidence_hash": "",
    }
    evidence["evidence_hash"] = artifact_hash(evidence, "evidence_hash")
    publications = {
        "schema": "cps.cache-publication-index",
        "schema_version": "1.0.0",
        "run_hash": authority.run_hash,
        "publications": [],
        "index_hash": "",
    }
    publications["index_hash"] = artifact_hash(publications, "index_hash")

    files: dict[str, bytes] = {}
    rows = []
    for path, raw, identity, schema_hash in authority.cas_objects:
        if raw_hash(raw) == "sha256:" + "0" * 64:
            raise ValueError("dummy shared authority object is forbidden")
        files[path] = raw
        rows.append({"locator": {"kind": "path", "path": path}, "content_kind": "json_artifact", "artifact_hash": identity, "schema_hash": schema_hash, "byte_length": len(raw)})
    for path, value, identity, schema_name in (
        ("failure_phase0/cas/evidence.json", evidence, evidence["evidence_hash"], "conformance_violation_evidence.schema.json"),
        ("failure_phase0/cas/cache_publications.json", publications, publications["index_hash"], "cache_publication_index.schema.json"),
    ):
        raw = canonical_json(value)
        files[path] = raw
        rows.append({"locator": {"kind": "path", "path": path}, "content_kind": "json_artifact", "artifact_hash": identity, "schema_hash": _schema_hash(schema_name), "byte_length": len(raw)})
    rows.sort(key=lambda row: (row["locator"]["kind"].encode(), row["locator"]["path"].encode(), bytes.fromhex(row["artifact_hash"][7:])))
    cas_index = {"schema": "cps.search-loop-13-cas-index", "schema_version": "1.0.0", "run_hash": authority.run_hash, "entries": rows, "index_hash": ""}
    cas_index["index_hash"] = artifact_hash(cas_index, "index_hash")
    files["failure_phase0/cas_index.json"] = canonical_json(cas_index)

    def edge(pointer: str, target: str, nullable: bool = False, cardinality: str = "one") -> dict[str, Any]:
        return {"json_pointer": pointer, "target_kind": target, "nullable": nullable, "cardinality": cardinality}

    registry_entries = [dict(row) for row in authority.edge_registry_entries]
    registry_entries.extend((
        {"schema_id": "cps.cache-publication-index", "schema_version": "1.0.0", "canonical_root_role": None, "edges": [edge("/run_hash", "external")]},
        {"schema_id": "cps.conformance-violation-evidence", "schema_version": "1.0.0", "canonical_root_role": None, "edges": [edge("/context_hash", "cas_json"), edge("/run_hash", "external"), edge("/subject_hash", "cas_json", True, "zero_or_one"), edge("/subject_schema_hash", "raw_schema")]},
    ))
    registry_entries.sort(key=lambda row: (row["schema_id"].encode(), tuple(map(int, row["schema_version"].split(".")))))
    registry = {"schema": "cps.fixture-edge-registry", "schema_version": "1.0.0", "entries": registry_entries, "registry_hash": ""}
    registry["registry_hash"] = artifact_hash(registry, "registry_hash")
    registry_raw = canonical_json(registry)
    files["failure_phase0/edge_registry.json"] = registry_raw
    registry_schema = (SCHEMAS / "fixture_edge_registry.schema.json").read_bytes()

    case = {
        "schema": "cps.search-loop-13-fixture-case", "schema_version": "1.0.0", "case_id": "failure_missing_candidate_source", "root_seed": authority.budgets.get("root_seed", 0),
        "edge_registry": {"path": "failure_phase0/edge_registry.json", "registry_hash": registry["registry_hash"], "registry_schema_hash": raw_hash(registry_schema), "registry_bytes_base64": base64.b64encode(registry_raw).decode(), "registry_schema_bytes_base64": base64.b64encode(registry_schema).decode()},
        "inputs": [dict(authority.context_input)], "policies": dict(authority.policies),
        "budgets": {key: value for key, value in authority.budgets.items() if key != "root_seed"},
        "cache_scenario": {
            kind: {
                "mode": "not_reached",
                "initial_entries": [],
                "expected_lookup": "not_performed",
                "expected_corruption_receipt_hash": None,
                "expected_publication_entry_hash": None,
            }
            for kind in ("compile", "render")
        },
        "parallel_scenario": {"worker_count": 1, "scheduled_action_ids": [], "completion_permutation": [], "parity_group_hash": ""},
        "cancellation_scenario": {"arrivals": []}, "stop_branch": "conformance_violation",
        "expected": {"terminal_kind": "conformance_violation", "transcript_root_hash": None, "cas_index_hash": cas_index["index_hash"], "cas_index_schema_hash": _schema_hash("search_loop_13_cas_index.schema.json"), "cache_publication_index_hash": publications["index_hash"], "final_checkpoint_hash": None, "failure": {"coordinate": coordinate, "code": "CONFORMANCE_VIOLATION", "evidence_hash": evidence["evidence_hash"]}, "audio_pcm_assets": []}, "case_hash": "",
    }
    case["parallel_scenario"]["parity_group_hash"] = parity_group_hash(case)
    case["case_hash"] = artifact_hash(case, "case_hash")
    files["failure_phase0.json"] = canonical_json(case)
    return files
