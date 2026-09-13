"""Independent primitives for SearchLoop13 authoritative fixture creation.

This module deliberately has no dependency on ``app.songprogram``.  Oracle
owners use it to calculate the parallel semantic identity before fixture bytes
are admitted to the read-only conformance pack.
"""

from __future__ import annotations

import copy
import base64
import hashlib
import json
from collections.abc import Mapping, Sequence
from typing import Any


PARITY_DOMAIN = b"cps-search-loop-13-parity-group/v1\0"
WORKER_MATRIX = (1, 2, 4, 8)


def canonical_json(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def artifact_hash(value: Mapping[str, Any], self_field: str) -> str:
    """Compute the Search Decision Contract artifact identity independently."""
    body = dict(value)
    body.pop(self_field, None)
    preimage = (
        b"cps-artifact-hash/v1\0"
        + str(value["schema"]).encode()
        + b"\0"
        + str(value["schema_version"]).encode()
        + b"\0"
        + canonical_json(body)
    )
    return "sha256:" + hashlib.sha256(preimage).hexdigest()


def manifest_hash(domain: str, value: Mapping[str, Any]) -> str:
    return (
        "sha256:"
        + hashlib.sha256(domain.encode() + b"\0" + canonical_json(value) + b"\n").hexdigest()
    )


def seal_event_payload(kind, run_hash, context_hash, coordinate, artifact_hash_, schema_hash):
    payload = {
        "schema": "cps.search-loop-13-event-payload",
        "schema_version": "1.0.0",
        "kind": kind,
        "run_hash": run_hash,
        "context_hash": context_hash,
        "action_id": action_id(
            run_hash, coordinate[0], coordinate[1], coordinate[2], coordinate[3]
        ),
        "coordinate": {
            "round": coordinate[0],
            "phase_ordinal": coordinate[1],
            "candidate_ordinal": coordinate[2],
            "event_ordinal": coordinate[3],
        },
        "source_decision_hash": None,
        "artifact_hash": artifact_hash_,
        "artifact_schema_hash": schema_hash,
        "payload_hash": "",
    }
    payload["payload_hash"] = artifact_hash(payload, "payload_hash")
    return payload


def seal_record(run_hash, sequence, kind, coordinate, payload_hash, previous):
    record = {
        "schema": "cps.search-run-record",
        "schema_version": "1.1.0",
        "run_hash": run_hash,
        "sequence": sequence,
        "action_id": action_id(run_hash, *coordinate),
        "round": coordinate[0],
        "phase_ordinal": coordinate[1],
        "candidate_ordinal": coordinate[2],
        "event_ordinal": coordinate[3],
        "kind": kind,
        "payload_hash": payload_hash,
        "previous_record_hash": previous,
    }
    record["record_hash"] = manifest_hash("cps.search-run-record/v1", record)
    return record


def action_id(run_hash: str, round_: int, phase: int, candidate: int, event: int) -> str:
    """Compute the normative v2 coordinate ID without production imports."""
    preimage = (
        b"cps-action-id/v2\0"
        + run_hash.encode()
        + round_.to_bytes(8, "big")
        + phase.to_bytes(1, "big")
        + candidate.to_bytes(8, "big")
        + event.to_bytes(2, "big")
    )
    # First 130 bits are the first 17 bytes with the low six bits cleared.
    digest = bytearray(hashlib.sha256(preimage).digest()[:17])
    digest[-1] &= 0xC0
    encoded = base64.b32encode(bytes(digest)).decode("ascii").lower().rstrip("=")
    return "act_" + encoded[:26]


def semantic_parity_projection(case: Mapping[str, Any]) -> dict[str, Any]:
    """Return the exact projection defined by the payload contract."""
    projected = copy.deepcopy(dict(case))
    del projected["case_id"]
    del projected["case_hash"]
    parallel = projected["parallel_scenario"]
    del parallel["worker_count"]
    del parallel["completion_permutation"]
    del parallel["parity_group_hash"]
    return projected


def parity_group_hash(case: Mapping[str, Any]) -> str:
    preimage = PARITY_DOMAIN + canonical_json(semantic_parity_projection(case)) + b"\n"
    return "sha256:" + hashlib.sha256(preimage).hexdigest()


def validate_parallel_matrix(cases: Sequence[Mapping[str, Any]]) -> None:
    """Reject a matrix that does not represent exactly the 1/2/4/8 projection."""
    if len(cases) != 4:
        raise ValueError("parallel matrix must contain exactly four cases")
    workers = tuple(sorted(case["parallel_scenario"]["worker_count"] for case in cases))
    if workers != WORKER_MATRIX:
        raise ValueError("parallel matrix worker counts must be exactly 1,2,4,8")
    expected_projection = canonical_json(semantic_parity_projection(cases[0]))
    expected_hash = parity_group_hash(cases[0])
    for case in cases:
        scenario = case["parallel_scenario"]
        scheduled = scenario["scheduled_action_ids"]
        completion = scenario["completion_permutation"]
        if len(completion) != len(set(completion)) or set(completion) != set(scheduled):
            raise ValueError("completion_permutation is not an exact action permutation")
        if canonical_json(semantic_parity_projection(case)) != expected_projection:
            raise ValueError("parallel semantic projections differ")
        if scenario["parity_group_hash"] != expected_hash:
            raise ValueError("parallel parity_group_hash mismatch")
