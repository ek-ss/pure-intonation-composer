"""Provider-neutral fresh-call boundary for blind synthetic PIL judgments."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping, Sequence
from typing import Any

from .pil_synthetic_authority_validator import artifact_hash

JudgeAdapter = Callable[[Mapping[str, Any], str, bytes], bytes]
SchemaValidator = Callable[[str, Mapping[str, Any]], bool]


class PILSyntheticJudgeError(ValueError):
    pass


def _canonical(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def _raw_hash(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def run_blind_judgments(
    *,
    protocol: Mapping[str, Any],
    agents: Sequence[Mapping[str, Any]],
    assignment_set: Mapping[str, Any],
    pcm_by_context_hash: Mapping[str, bytes],
    adapter: JudgeAdapter,
    schema_validator: SchemaValidator,
) -> list[dict[str, Any]]:
    """Call an injected audio judge once per assignment and seal parsed records."""

    if protocol.get("input_modality") != "audio_pcm" or protocol.get("audio_capable") is not True:
        raise PILSyntheticJudgeError("PIL_SYNTHETIC_PROTOCOL_INVALID")
    agent_by_hash = {agent["manifest_hash"]: agent for agent in agents}
    records: list[dict[str, Any]] = []
    for assignment in sorted(assignment_set["assignments"], key=lambda row: row["assignment_id"]):
        agent = agent_by_hash.get(assignment["agent_manifest_hash"])
        pcm = pcm_by_context_hash.get(assignment["sealed_context_hash"])
        if agent is None or pcm is None or _raw_hash(pcm) != assignment["sealed_context_hash"]:
            raise PILSyntheticJudgeError("PIL_SYNTHETIC_CONTEXT_MISMATCH")
        request = {
            "schema": "cps.pil-synthetic-judge-request",
            "schema_version": "1.0.0",
            "protocol_hash": protocol["protocol_hash"],
            "agent_manifest_hash": agent["manifest_hash"],
            "assignment_id": assignment["assignment_id"],
            "opaque_item_id": assignment["opaque_item_id"],
            "pcm_hash": assignment["sealed_context_hash"],
            "output_schema_hash": protocol["output_schema_hash"],
        }
        response_bytes = adapter(request, assignment["opaque_item_id"], pcm)
        try:
            response = json.loads(response_bytes)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise PILSyntheticJudgeError("PIL_SYNTHETIC_RESPONSE_INVALID") from error
        if (
            not isinstance(response, dict)
            or response_bytes != _canonical(response)
            or not schema_validator("pil_synthetic_judge_response.schema.json", response)
        ):
            raise PILSyntheticJudgeError("PIL_SYNTHETIC_RESPONSE_INVALID")
        judgments = response["judgments"]
        if not judgments:
            raise PILSyntheticJudgeError("PIL_SYNTHETIC_RESPONSE_INVALID")
        metric_ids = [row["metric_id"] for row in judgments]
        if metric_ids != sorted(metric_ids) or len(metric_ids) != len(set(metric_ids)):
            raise PILSyntheticJudgeError("PIL_SYNTHETIC_RESPONSE_INVALID")
        if any(row["available"] != (row["ordinal_label"] != "unavailable") for row in judgments):
            raise PILSyntheticJudgeError("PIL_SYNTHETIC_RESPONSE_INVALID")
        record = {
            "schema": "cps.pil-synthetic-raw-response-record",
            "schema_version": "1.0.0",
            "authority_kind": "synthetic_llm",
            "human_authority_compatible": False,
            "human_listener_response": False,
            "scope": protocol["scope"],
            "protocol_hash": protocol["protocol_hash"],
            "assignment_set_hash": assignment_set["assignment_set_hash"],
            "assignment_id": assignment["assignment_id"],
            "agent_manifest_hash": agent["manifest_hash"],
            "sealed_context_hash": assignment["sealed_context_hash"],
            "request_hash": _raw_hash(_canonical(request)),
            "provider_response_hash": _raw_hash(response_bytes),
            "judgments": judgments,
            "record_hash": "",
        }
        record["record_hash"] = artifact_hash(record, "record_hash")
        records.append(record)
    records.sort(key=lambda value: value["record_hash"])
    return records
