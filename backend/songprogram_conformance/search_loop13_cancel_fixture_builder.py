"""Independent builder for the reviewed phase-0 cancellation fixture.

This module intentionally imports only the independent oracle primitives.  It
is a golden-owner tool, not production runtime code.
"""

from __future__ import annotations

import base64
import hashlib
from pathlib import Path
from typing import Any

from .search_loop13_fixture_oracle import (
    action_id,
    artifact_hash,
    canonical_json,
    parity_group_hash,
    seal_event_payload,
    seal_record,
)

SCHEMAS = Path(__file__).parent / "schemas"
FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "search_loop_13"


def raw_hash(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _schema(name: str) -> tuple[bytes, str]:
    raw = (SCHEMAS / name).read_bytes()
    return raw, raw_hash(raw)


def _seal(value: dict[str, Any], field: str) -> dict[str, Any]:
    value[field] = artifact_hash(value, field)
    return value


def build() -> dict[str, bytes]:
    run_hash = raw_hash(b"cps.search-loop-13.cancel-phase0.run/v1")
    context_hash = raw_hash(b"cps.search-loop-13.cancel-phase0.context/v1")
    request = _seal(
        {
            "schema": "cps.cancellation-request",
            "schema_version": "1.0.0",
            "run_hash": run_hash,
            "request_id": "cancel_" + "a" * 26,
            "reason": "user",
            "request_hash": "",
        },
        "request_hash",
    )
    request_raw = canonical_json(request)
    _, request_schema_hash = _schema("cancellation_request.schema.json")
    inbox = _seal(
        {
            "schema": "cps.cancellation-inbox-record",
            "schema_version": "1.1.0",
            "run_hash": run_hash,
            "request_schema_hash": request_schema_hash,
            "raw_request_bytes_base64": base64.b64encode(request_raw).decode(),
            "raw_request_digest": raw_hash(request_raw),
            "request_hash": request["request_hash"],
            "acceptance_sequence": 0,
            "inbox_hash": "",
        },
        "inbox_hash",
    )
    snapshot = _seal(
        {
            "schema": "cps.archive-heads-snapshot",
            "schema_version": "1.0.0",
            "run_hash": run_hash,
            "context_hash": context_hash,
            "round": 0,
            "stage": "round_before",
            "entries": [],
            "snapshot_hash": "",
        },
        "snapshot_hash",
    )
    decision = _seal(
        {
            "schema": "cps.cancellation-decision",
            "schema_version": "1.1.0",
            "status": "accepted",
            "cancelled": True,
            "run_hash": run_hash,
            "context_hash": context_hash,
            "inbox_record_hash": inbox["inbox_hash"],
            "raw_request_digest": inbox["raw_request_digest"],
            "request_hash": request["request_hash"],
            "effective_cutoff_action_id": action_id(run_hash, 0, 0, 0, 2),
            "cutoff_coordinate": {
                "round": 0,
                "phase_ordinal": 0,
                "candidate_ordinal": 0,
                "event_ordinal": 2,
            },
            "last_committable_action_id": action_id(run_hash, 0, 0, 0, 1),
            "champion_at_cutoff": None,
            "archive_heads_hash": snapshot["snapshot_hash"],
            "decision_hash": "",
        },
        "decision_hash",
    )

    objects: list[tuple[str, dict[str, Any], str, str]] = [
        ("request", request, "request_hash", "cancellation_request.schema.json"),
        ("inbox", inbox, "inbox_hash", "cancellation_inbox_record_1_1.schema.json"),
        ("archive_before", snapshot, "snapshot_hash", "archive_heads_snapshot.schema.json"),
        ("decision", decision, "decision_hash", "cancellation_decision_1_1.schema.json"),
    ]
    event_specs = [
        (
            "cancellation_request",
            inbox["inbox_hash"],
            "cancellation_inbox_record_1_1.schema.json",
            (0, 0, 0, 0),
        ),
        (
            "cancellation_decision",
            decision["decision_hash"],
            "cancellation_decision_1_1.schema.json",
            (0, 0, 0, 1),
        ),
    ]
    records = []
    previous = None
    for seq, (kind, target, schema_name, coord) in enumerate(event_specs):
        payload = seal_event_payload(
            kind, run_hash, context_hash, coord, target, _schema(schema_name)[1]
        )
        record = seal_record(run_hash, seq, kind, coord, payload["payload_hash"], previous)
        objects.extend(
            [
                (
                    f"payload_{seq}",
                    payload,
                    "payload_hash",
                    "search_loop_13_event_payload.schema.json",
                ),
                (f"record_{seq}", record, "record_hash", "search_run_record_1_1.schema.json"),
            ]
        )
        records.append(record)
        previous = record["record_hash"]
    checkpoint = {
        "schema": "cps.search-checkpoint",
        "schema_version": "1.1.0",
        "run_hash": run_hash,
        "last_sequence": 1,
        "last_record_hash": records[-1]["record_hash"],
        "next_action_id": action_id(run_hash, 0, 13, 0, 3),
        "cursor": {"round": 0, "candidate_ordinal": 0, "phase_ordinal": 13, "event_ordinal": 3},
        "budget_usage": {"compile_logical_units": 0, "render_frames": 0, "planner_calls": 0},
        "planner_calls": 0,
        "patience_rounds": 0,
        "archive_heads": [],
        "champions": [],
        "accepted_champion": None,
        "termination": {
            "status": "terminated",
            "reason": "cancelled",
            "decision_hash": decision["decision_hash"],
        },
    }
    checkpoint_hash = artifact_hash(checkpoint, "unused")
    cp = seal_event_payload(
        "checkpoint",
        run_hash,
        context_hash,
        (0, 13, 0, 2),
        checkpoint_hash,
        _schema("search_checkpoint_1_1.schema.json")[1],
    )
    cr = seal_record(
        run_hash, 2, "checkpoint", (0, 13, 0, 2), cp["payload_hash"], records[-1]["record_hash"]
    )
    objects.extend(
        [
            ("checkpoint", checkpoint, "unused", "search_checkpoint_1_1.schema.json"),
            ("payload_2", cp, "payload_hash", "search_loop_13_event_payload.schema.json"),
            ("record_2", cr, "record_hash", "search_run_record_1_1.schema.json"),
        ]
    )
    publications = _seal(
        {
            "schema": "cps.cache-publication-index",
            "schema_version": "1.0.0",
            "run_hash": run_hash,
            "publications": [],
            "index_hash": "",
        },
        "index_hash",
    )
    objects.append(
        ("cache_publications", publications, "index_hash", "cache_publication_index.schema.json")
    )

    files: dict[str, bytes] = {}
    entries = []
    for role, value, field, schema_name in objects:
        raw = canonical_json(value)
        path = f"cas/{role}.json"
        files[path] = raw
        identity = checkpoint_hash if role == "checkpoint" else value[field]
        entries.append(
            {
                "locator": {"kind": "path", "path": path},
                "content_kind": "json_artifact",
                "artifact_hash": identity,
                "schema_hash": _schema(schema_name)[1],
                "byte_length": len(raw),
            }
        )
    entries.sort(
        key=lambda row: (
            row["locator"]["kind"].encode(),
            row["locator"]["path"].encode(),
            bytes.fromhex(row["artifact_hash"][7:]),
        )
    )
    cas_index = _seal(
        {
            "schema": "cps.search-loop-13-cas-index",
            "schema_version": "1.0.0",
            "run_hash": run_hash,
            "entries": entries,
            "index_hash": "",
        },
        "index_hash",
    )
    files["cas_index.json"] = canonical_json(cas_index)

    def edge(pointer, target, nullable=False, cardinality="one"):
        return {
            "json_pointer": pointer,
            "target_kind": target,
            "nullable": nullable,
            "cardinality": cardinality,
        }

    registry_entries = [
        {
            "schema_id": "cps.archive-heads-snapshot",
            "schema_version": "1.0.0",
            "canonical_root_role": None,
            "edges": [edge("/context_hash", "external"), edge("/run_hash", "external")],
        },
        {
            "schema_id": "cps.cache-publication-index",
            "schema_version": "1.0.0",
            "canonical_root_role": None,
            "edges": [edge("/run_hash", "external")],
        },
        {
            "schema_id": "cps.cancellation-decision",
            "schema_version": "1.1.0",
            "canonical_root_role": None,
            "edges": [
                edge("/archive_heads_hash", "cas_json"),
                edge("/context_hash", "external"),
                edge("/inbox_record_hash", "cas_json"),
                edge("/raw_request_digest", "comparator"),
                edge("/request_hash", "cas_json"),
                edge("/run_hash", "external"),
            ],
        },
        {
            "schema_id": "cps.cancellation-inbox-record",
            "schema_version": "1.1.0",
            "canonical_root_role": "cancellation_inbox",
            "edges": [
                edge("/raw_request_digest", "comparator"),
                edge("/request_hash", "cas_json"),
                edge("/request_schema_hash", "raw_schema"),
                edge("/run_hash", "external"),
            ],
        },
        {
            "schema_id": "cps.cancellation-request",
            "schema_version": "1.0.0",
            "canonical_root_role": "cancellation_request",
            "edges": [edge("/run_hash", "external")],
        },
        {
            "schema_id": "cps.search-checkpoint",
            "schema_version": "1.1.0",
            "canonical_root_role": None,
            "edges": [
                edge("/last_record_hash", "cas_json"),
                edge("/run_hash", "external"),
                edge("/termination/decision_hash", "cas_json", True, "zero_or_one"),
            ],
        },
        {
            "schema_id": "cps.search-loop-13-event-payload",
            "schema_version": "1.0.0",
            "canonical_root_role": None,
            "edges": [
                edge("/artifact_hash", "cas_json"),
                edge("/artifact_schema_hash", "raw_schema"),
                edge("/context_hash", "external"),
                edge("/run_hash", "external"),
                edge("/source_decision_hash", "cas_json", True, "zero_or_one"),
            ],
        },
        {
            "schema_id": "cps.search-run-record",
            "schema_version": "1.1.0",
            "canonical_root_role": None,
            "edges": [
                edge("/payload_hash", "cas_json"),
                edge("/previous_record_hash", "cas_json", True, "zero_or_one"),
                edge("/run_hash", "external"),
            ],
        },
    ]
    registry = _seal(
        {
            "schema": "cps.fixture-edge-registry",
            "schema_version": "1.0.0",
            "entries": registry_entries,
            "registry_hash": "",
        },
        "registry_hash",
    )
    registry_raw = canonical_json(registry)
    registry_schema_raw, registry_schema_hash = _schema("fixture_edge_registry.schema.json")
    files["edge_registry.json"] = registry_raw
    case_schema_raw, case_schema_hash = _schema("search_loop_13_fixture_case.schema.json")
    case = {
        "schema": "cps.search-loop-13-fixture-case",
        "schema_version": "1.0.0",
        "case_id": "cancel_phase0",
        "root_seed": 0,
        "edge_registry": {
            "path": "edge_registry.json",
            "registry_hash": registry["registry_hash"],
            "registry_schema_hash": registry_schema_hash,
            "registry_bytes_base64": base64.b64encode(registry_raw).decode(),
            "registry_schema_bytes_base64": base64.b64encode(registry_schema_raw).decode(),
        },
        "inputs": [
            {
                "role": "cancellation_inbox",
                "path": "cas/inbox.json",
                "raw_file_sha256": raw_hash(files["cas/inbox.json"]),
                "artifact_hash": inbox["inbox_hash"],
                "schema_hash": _schema("cancellation_inbox_record_1_1.schema.json")[1],
            },
            {
                "role": "cancellation_request",
                "path": "cas/request.json",
                "raw_file_sha256": raw_hash(files["cas/request.json"]),
                "artifact_hash": request["request_hash"],
                "schema_hash": request_schema_hash,
            },
        ],
        "policies": {
            "candidate_source_policy_hash": raw_hash(b"candidate-source"),
            "render_selection_policy_hash": raw_hash(b"render-selection"),
            "archive_admission_policy_hash": raw_hash(b"archive-admission"),
            "challenger_acceptance_policy_hash": raw_hash(b"challenger-acceptance"),
            "stopping_policy_hash": raw_hash(b"stopping"),
            "planner_branch": "planner_null",
        },
        "budgets": {
            "population_size": 1,
            "candidates_per_round": 1,
            "planner_call_budget": 0,
            "compile_logical_budget": 0,
            "render_frame_budget": 0,
            "operational_deadline_seconds": None,
        },
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
        "parallel_scenario": {
            "worker_count": 1,
            "scheduled_action_ids": [],
            "completion_permutation": [],
            "parity_group_hash": "",
        },
        "cancellation_scenario": {
            "arrivals": [
                {
                    "inbox_record_hash": inbox["inbox_hash"],
                    "arrival_barrier_coordinate": {
                        "round": 0,
                        "phase_ordinal": 0,
                        "candidate_ordinal": 0,
                        "event_ordinal": 0,
                    },
                }
            ]
        },
        "stop_branch": "cancelled",
        "expected": {
            "terminal_kind": "checkpoint",
            "transcript_root_hash": cr["record_hash"],
            "cas_index_hash": cas_index["index_hash"],
            "cas_index_schema_hash": _schema("search_loop_13_cas_index.schema.json")[1],
            "cache_publication_index_hash": publications["index_hash"],
            "final_checkpoint_hash": checkpoint_hash,
            "failure": None,
            "audio_pcm_assets": [],
        },
        "case_hash": "",
    }
    case["parallel_scenario"]["parity_group_hash"] = parity_group_hash(case)
    case = _seal(case, "case_hash")
    files["cancel_phase0.json"] = canonical_json(case)
    files["schemas/search_loop_13_fixture_case.schema.json"] = case_schema_raw
    return files


def write_fixture(root: Path = FIXTURE_ROOT) -> None:
    for relative, data in build().items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)


if __name__ == "__main__":
    write_fixture()
