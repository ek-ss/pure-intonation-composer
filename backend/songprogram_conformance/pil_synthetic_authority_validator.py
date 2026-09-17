"""Read-only validation for synthetic, audit-only PIL authority bundles."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from typing import Any, Callable

SchemaValidator = Callable[[str, Mapping[str, Any]], bool]


class PILSyntheticAuthorityError(ValueError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def _canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def _sha(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _without(value: Mapping[str, Any], member: str) -> dict[str, Any]:
    return {key: item for key, item in value.items() if key != member}


def artifact_hash(value: Mapping[str, Any], self_member: str) -> str:
    prefix = f"cps-artifact-hash/v1\0{value['schema']}\0{value['schema_version']}\0".encode()
    return _sha(prefix + _canonical(_without(value, self_member)))


def evidence_hash(value: Mapping[str, Any]) -> str:
    prefix = b"cps-artifact-hash/v1\0cps.pil-synthetic-metric-evidence\01.0.0\0"
    return _sha(prefix + _canonical(_without(value, "evidence_hash")))


def decision_hash(value: Mapping[str, Any]) -> str:
    return _sha(
        b"cps.pil-synthetic-provisional-decision/v1\0"
        + _canonical(_without(value, "decision_hash"))
    )


def _require_schema(
    validator: SchemaValidator, name: str, value: Mapping[str, Any]
) -> None:
    if not validator(name, value):
        raise PILSyntheticAuthorityError("PIL_SYNTHETIC_INPUT_INVALID")


def _sorted_unique(values: Sequence[str]) -> bool:
    return list(values) == sorted(values) and len(values) == len(set(values))


def validate_synthetic_provisional_authority(
    *,
    protocol: Mapping[str, Any],
    agents: Sequence[Mapping[str, Any]],
    cohort: Mapping[str, Any],
    responses: Sequence[Mapping[str, Any]],
    judgment_set: Mapping[str, Any],
    registry: Mapping[str, Any],
    evidence_summary: Mapping[str, Any],
    decision: Mapping[str, Any],
    expected_bindings: Mapping[str, str],
    schema_validator: SchemaValidator,
) -> str:
    """Validate a complete synthetic chain without repairing or promoting it."""

    invalid = "PIL_SYNTHETIC_INPUT_INVALID"
    mismatch = "PIL_SYNTHETIC_CONTEXT_MISMATCH"
    threshold = "PIL_SYNTHETIC_THRESHOLD_NOT_MET"
    result_invalid = "PIL_SYNTHETIC_RESULT_INVALID"
    genre = decision.get("scope") == "genre_phase_5"
    registry_schema = (
        "pil_genre_metric_registry.schema.json" if genre else "pil_metric_registry.schema.json"
    )
    for name, value in (
        ("pil_synthetic_protocol_manifest.schema.json", protocol),
        ("pil_synthetic_cohort_manifest.schema.json", cohort),
        ("pil_synthetic_judgment_set.schema.json", judgment_set),
        (registry_schema, registry),
        ("pil_synthetic_evidence_summary.schema.json", evidence_summary),
        ("pil_synthetic_provisional_decision.schema.json", decision),
    ):
        _require_schema(schema_validator, name, value)
    for value in agents:
        _require_schema(schema_validator, "pil_synthetic_agent_manifest.schema.json", value)
    for value in responses:
        _require_schema(schema_validator, "pil_synthetic_raw_response_record.schema.json", value)
    synthetic_values = (protocol, *agents, cohort, *responses, judgment_set, evidence_summary, decision)
    if any(value.get("human_authority_compatible") is not False for value in synthetic_values):
        raise PILSyntheticAuthorityError(invalid)
    if protocol["generator_model_family_hash"] == protocol["judge_model_family_hash"]:
        raise PILSyntheticAuthorityError(mismatch)

    identities = (
        (protocol, "protocol_hash"),
        *((value, "manifest_hash") for value in agents),
        (cohort, "manifest_hash"),
        *((value, "record_hash") for value in responses),
        (judgment_set, "judgment_set_hash"),
        (registry, "registry_hash"),
        (evidence_summary, "summary_hash"),
    )
    if any(value[member] != artifact_hash(value, member) for value, member in identities):
        raise PILSyntheticAuthorityError(invalid)
    if decision["decision_hash"] != decision_hash(decision):
        raise PILSyntheticAuthorityError(result_invalid)

    scope = decision["scope"]
    if any(value["scope"] != scope for value in (protocol, judgment_set, evidence_summary)):
        raise PILSyntheticAuthorityError(mismatch)
    for response in responses:
        if response["scope"] != scope:
            raise PILSyntheticAuthorityError(mismatch)
    if any(decision.get(key) != expected_bindings.get(key) for key in (
        "pil_manifest_hash", "oracle_suite_index_hash"
    )):
        raise PILSyntheticAuthorityError(mismatch)

    protocol_hash = protocol["protocol_hash"]
    if any(agent["protocol_hash"] != protocol_hash for agent in agents):
        raise PILSyntheticAuthorityError(mismatch)
    agent_hashes = [agent["manifest_hash"] for agent in agents]
    if not _sorted_unique(agent_hashes):
        raise PILSyntheticAuthorityError(invalid)
    if cohort["protocol_hash"] != protocol_hash or cohort["agent_manifest_hashes"] != agent_hashes:
        raise PILSyntheticAuthorityError(mismatch)
    if cohort["agent_count"] != len(agents):
        raise PILSyntheticAuthorityError(result_invalid)
    if len(agents) < protocol["minimum_agent_count"]:
        raise PILSyntheticAuthorityError(threshold)

    response_hashes = [response["record_hash"] for response in responses]
    if not _sorted_unique(response_hashes):
        raise PILSyntheticAuthorityError(invalid)
    known_agents = set(agent_hashes)
    for response in responses:
        if response["protocol_hash"] != protocol_hash or response["agent_manifest_hash"] not in known_agents:
            raise PILSyntheticAuthorityError(mismatch)
        metric_ids = [row["metric_id"] for row in response["judgments"]]
        if not _sorted_unique(metric_ids):
            raise PILSyntheticAuthorityError(invalid)
        for row in response["judgments"]:
            if row["available"] != (row["ordinal_label"] != "unavailable"):
                raise PILSyntheticAuthorityError(result_invalid)
    if (
        judgment_set["protocol_hash"] != protocol_hash
        or judgment_set["cohort_manifest_hash"] != cohort["manifest_hash"]
        or judgment_set["response_record_hashes"] != response_hashes
    ):
        raise PILSyntheticAuthorityError(mismatch)
    if judgment_set["response_count"] != len(responses):
        raise PILSyntheticAuthorityError(result_invalid)

    registry_rows = {row["metric_id"]: row for row in registry["metrics"]}
    if decision["metric_registry_hash"] != registry["registry_hash"]:
        raise PILSyntheticAuthorityError(mismatch)
    if (
        evidence_summary["protocol_hash"] != protocol_hash
        or evidence_summary["cohort_manifest_hash"] != cohort["manifest_hash"]
        or evidence_summary["judgment_set_hash"] != judgment_set["judgment_set_hash"]
        or evidence_summary["metric_registry_hash"] != registry["registry_hash"]
        or evidence_summary["evaluation_policy_hash"] != protocol["evaluation_policy_hash"]
    ):
        raise PILSyntheticAuthorityError(mismatch)
    if evidence_summary["agent_count"] != len(agents):
        raise PILSyntheticAuthorityError(result_invalid)
    observation_count = sum(len(response["judgments"]) for response in responses)
    if evidence_summary["observation_count"] != observation_count:
        raise PILSyntheticAuthorityError(result_invalid)

    summary_rows = evidence_summary["metrics"]
    summary_ids = [row["metric_id"] for row in summary_rows]
    if not _sorted_unique(summary_ids):
        raise PILSyntheticAuthorityError(invalid)
    if not set(summary_ids) <= set(registry_rows):
        raise PILSyntheticAuthorityError(mismatch)
    provisional_rows: list[dict[str, Any]] = []
    ordinal_q = {
        "strongly_below": 0, "below": 2500, "borderline": 5000,
        "above": 7500, "strongly_above": 10000,
    }
    for row in summary_rows:
        registered = registry_rows[row["metric_id"]]
        for key in ("aggregation", "direction", "missing_policy"):
            if row[key] != registered[key]:
                raise PILSyntheticAuthorityError(mismatch)
        observed_values = sorted(
            ordinal_q[judgment["ordinal_label"]]
            for response in responses
            for judgment in response["judgments"]
            if judgment["metric_id"] == row["metric_id"] and judgment["available"]
        )
        recomputed_q = None
        if observed_values:
            middle = len(observed_values) // 2
            if len(observed_values) % 2:
                recomputed_q = observed_values[middle]
            else:
                total = observed_values[middle - 1] + observed_values[middle]
                quotient, remainder = divmod(total, 2)
                recomputed_q = quotient + (1 if remainder and quotient % 2 else 0)
        if row["observed_q"] != recomputed_q:
            raise PILSyntheticAuthorityError(result_invalid)
        expected_pass = False
        if recomputed_q is not None:
            expected_pass = (
                recomputed_q >= row["acceptance_threshold_q"]
                if row["direction"] == "maximize"
                else recomputed_q <= row["acceptance_threshold_q"]
            )
        if row["passed"] != expected_pass or row["evidence_hash"] != evidence_hash(row):
            raise PILSyntheticAuthorityError(result_invalid)
        provisional_rows.append(
            {key: row[key] for key in (
                "metric_id", "direction", "observed_q", "acceptance_threshold_q", "passed",
                "evidence_hash",
            )}
        )
    all_pass = bool(summary_rows) and all(row["passed"] for row in summary_rows)
    if evidence_summary["all_required_metrics_passed"] != all_pass:
        raise PILSyntheticAuthorityError(result_invalid)

    if (
        decision["protocol_hash"] != protocol_hash
        or decision["cohort_manifest_hash"] != cohort["manifest_hash"]
        or decision["judgment_set_hash"] != judgment_set["judgment_set_hash"]
        or decision["evaluation_policy_hash"] != protocol["evaluation_policy_hash"]
        or decision["evidence_summary_hash"] != evidence_summary["summary_hash"]
    ):
        raise PILSyntheticAuthorityError(mismatch)
    if decision["provisional_metrics"] != provisional_rows or decision["metric_ids"] != summary_ids:
        raise PILSyntheticAuthorityError(result_invalid)
    expected_failure = None if all_pass else threshold
    if decision["failure_code"] != expected_failure:
        raise PILSyntheticAuthorityError(result_invalid)
    return decision["decision_hash"]
