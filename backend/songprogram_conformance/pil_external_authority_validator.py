"""Read-only semantic intake for externally issued PIL calibration authority."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping
from typing import Any

SchemaValidator = Callable[[str, Mapping[str, Any]], bool]


class PILAuthorityError(ValueError):
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
    prefix = b"cps-artifact-hash/v1\0cps.pil-calibration-metric-evidence\01.0.0\0"
    return _sha(prefix + _canonical(_without(value, "evidence_hash")))


def decision_hash(value: Mapping[str, Any]) -> str:
    version = value["schema_version"].split(".", 1)[0]
    return _sha(
        f"cps.pil-calibration-decision/v{version}\0".encode()
        + _canonical(_without(value, "decision_hash"))
    )


def _require_schema(
    validator: SchemaValidator, schema_name: str, value: Mapping[str, Any], code: str
) -> None:
    if not validator(schema_name, value):
        raise PILAuthorityError(code)


def _ordered(rows: list[Mapping[str, Any]]) -> bool:
    ids = [row["metric_id"] for row in rows]
    return ids == sorted(ids) and len(ids) == len(set(ids))


def validate_external_authority(
    *,
    listener_cohort: Mapping[str, Any],
    registry: Mapping[str, Any],
    policy: Mapping[str, Any],
    fixture_set: Mapping[str, Any],
    evidence_summary: Mapping[str, Any],
    decision: Mapping[str, Any],
    expected_bindings: Mapping[str, str],
    schema_validator: SchemaValidator,
) -> str:
    """Validate one Phase 1-4 or Phase 5 authority chain without repairing it."""

    genre = decision.get("schema_version") == "2.0.0"
    prefix = "PIL_GENRE_CALIBRATION" if genre else "PIL_CALIBRATION"
    invalid = f"{prefix}_INPUT_INVALID"
    mismatch = f"{prefix}_CONTEXT_MISMATCH"
    threshold = f"{prefix}_THRESHOLD_NOT_MET"
    result_invalid = f"{prefix}_RESULT_INVALID"
    names = (
        (
            "pil_genre_metric_registry.schema.json",
            "pil_genre_calibration_acceptance_policy.schema.json",
            "pil_genre_calibration_fixture_set.schema.json",
            "pil_genre_calibration_metric_evidence_summary.schema.json",
            "pil_genre_calibration_decision.schema.json",
            "genre_metric_registry_hash",
        )
        if genre
        else (
            "pil_metric_registry.schema.json",
            "pil_calibration_acceptance_policy.schema.json",
            "pil_calibration_fixture_set.schema.json",
            "pil_calibration_metric_evidence_summary.schema.json",
            "pil_calibration_decision.schema.json",
            "metric_registry_hash",
        )
    )
    (
        registry_schema,
        policy_schema,
        fixture_schema,
        summary_schema,
        decision_schema,
        registry_key,
    ) = names
    for schema_name, value in (
        ("listener_cohort_manifest.schema.json", listener_cohort),
        (registry_schema, registry),
        (policy_schema, policy),
        (fixture_schema, fixture_set),
        (summary_schema, evidence_summary),
        (decision_schema, decision),
    ):
        _require_schema(schema_validator, schema_name, value, invalid)

    identities = (
        (listener_cohort, "manifest_hash"),
        (registry, "registry_hash"),
        (policy, "policy_hash"),
        (fixture_set, "fixture_set_hash"),
        (evidence_summary, "summary_hash"),
    )
    if any(value[member] != artifact_hash(value, member) for value, member in identities):
        raise PILAuthorityError(invalid)
    if decision["decision_hash"] != decision_hash(decision):
        raise PILAuthorityError(result_invalid)

    registry_hash = registry["registry_hash"]
    common = {"pil_manifest_hash", "oracle_suite_index_hash"}
    if not genre:
        common.add("oracle_matrix_receipt_hash")
    else:
        common |= {
            "genre_intent_hash",
            "genre_model_hash",
            "genre_reference_set_manifest_hash",
        }
        if decision.get("phase5_build_id") != "pil.phase5.1.0.0":
            raise PILAuthorityError(mismatch)
    for key in common:
        expected = expected_bindings.get(key)
        if expected is None or decision.get(key) != expected:
            raise PILAuthorityError(mismatch)
        for value in (policy, fixture_set):
            if key in value and value[key] != expected:
                raise PILAuthorityError(mismatch)
    if any(
        value.get(registry_key) != registry_hash
        for value in (policy, fixture_set, evidence_summary, decision)
    ):
        raise PILAuthorityError(mismatch)
    if fixture_set["listener_cohort_manifest_hash"] != listener_cohort["manifest_hash"]:
        raise PILAuthorityError(mismatch)
    if fixture_set["acceptance_policy_hash"] != policy["policy_hash"]:
        raise PILAuthorityError(mismatch)
    if (
        evidence_summary["fixture_set_hash"] != fixture_set["fixture_set_hash"]
        or evidence_summary["acceptance_policy_hash"] != policy["policy_hash"]
    ):
        raise PILAuthorityError(mismatch)
    if (
        decision["calibration_fixture_set_hash"] != fixture_set["fixture_set_hash"]
        or decision["acceptance_policy_hash"] != policy["policy_hash"]
        or decision["evidence_summary_hash"] != evidence_summary["summary_hash"]
    ):
        raise PILAuthorityError(mismatch)

    registry_rows = {row["metric_id"]: row for row in registry["metrics"]}
    policy_rows = policy["metrics"]
    summary_rows = evidence_summary["metrics"]
    if not _ordered(policy_rows) or not _ordered(summary_rows):
        raise PILAuthorityError(invalid)
    if not set(row["metric_id"] for row in policy_rows) <= set(registry_rows):
        raise PILAuthorityError(mismatch)
    if [row["metric_id"] for row in policy_rows] != [row["metric_id"] for row in summary_rows]:
        raise PILAuthorityError(result_invalid)

    passed_rows: list[dict[str, Any]] = []
    for policy_row, observed in zip(policy_rows, summary_rows, strict=True):
        registered = registry_rows[policy_row["metric_id"]]
        for key in ("aggregation", "direction", "missing_policy"):
            if policy_row[key] != registered[key] or observed[key] != policy_row[key]:
                raise PILAuthorityError(mismatch)
        if observed["acceptance_threshold_q"] != policy_row["acceptance_threshold_q"]:
            raise PILAuthorityError(result_invalid)
        expected_pass = False
        if observed["observed_q"] is not None:
            expected_pass = (
                observed["observed_q"] >= observed["acceptance_threshold_q"]
                if observed["direction"] == "maximize"
                else observed["observed_q"] <= observed["acceptance_threshold_q"]
            )
        if observed["passed"] != expected_pass or observed["evidence_hash"] != evidence_hash(
            observed
        ):
            raise PILAuthorityError(result_invalid)
        if expected_pass:
            passed_rows.append(
                {
                    "metric_id": observed["metric_id"],
                    "aggregation": observed["aggregation"],
                    "direction": observed["direction"],
                    "acceptance_threshold_q": observed["acceptance_threshold_q"],
                    "missing_policy": observed["missing_policy"],
                    "noninferiority_margin_q": policy_row["noninferiority_margin_q"],
                    "improvement_margin_q": policy_row["improvement_margin_q"],
                    "evidence_hash": observed["evidence_hash"],
                }
            )

    counts_pass = (
        evidence_summary["listener_count"] >= policy["minimum_listener_count"]
        and evidence_summary["observation_count"] >= policy["minimum_observation_count"]
    )
    all_pass = counts_pass and len(passed_rows) == len(policy_rows)
    if evidence_summary["all_required_metrics_passed"] != all_pass:
        raise PILAuthorityError(result_invalid)
    if decision["status"] == "promoted":
        if not all_pass:
            raise PILAuthorityError(threshold)
        if decision["promoted_metrics"] != passed_rows or decision["metric_ids"] != [
            row["metric_id"] for row in passed_rows
        ]:
            raise PILAuthorityError(result_invalid)
    elif decision["promoted_metrics"] or decision["metric_ids"] or decision["failure_code"] is None:
        raise PILAuthorityError(result_invalid)
    return decision["decision_hash"]
