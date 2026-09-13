"""Independent fixture-only CalibrationDecision 1.1 authority builder."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .canonical import canonical_bytes
from .search_loop13_extension_oracle import (
    calibrated_criterion,
    calibration_bootstrap_values,
    calibration_statistics,
    rank_interval,
    validate_response_rows,
)
from .search_loop13_fixture_oracle import artifact_hash


SCHEMAS = Path(__file__).with_name("schemas")
HASH_FIELDS = {
    "genre_license_policy": "policy_hash",
    "listener_cohort_manifest": "manifest_hash",
    "feature_extractor_manifest": "manifest_hash",
    "genre_reference_set_manifest": "manifest_hash",
    "calibration_statistic_operator": "operator_hash",
    "calibration_acceptance_policy": "policy_hash",
    "calibration_response_set": "response_hash",
    "blinded_assignment_manifest": "manifest_hash",
    "calibration_dataset_manifest": "manifest_hash",
    "calibration_bootstrap_trace": "trace_hash",
    "calibration_evidence_summary": "summary_hash",
    "calibration_fixture_set": "fixture_set_hash",
    "calibration_decision": "decision_hash",
}


def _raw_hash(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _seal(value: dict[str, Any], member: str) -> dict[str, Any]:
    value[member] = artifact_hash(value, member)
    return value


def _response_rows(participants: list[str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for category, judgment, auto_small in (
        ("high", "larger", False),
        ("low", "smaller", False),
        ("small", "similar", True),
    ):
        for presentation in (0, 1):
            item_id = f"{category}_{presentation}"
            for participant in participants:
                rows.append(
                    {
                        "participant_hash": participant,
                        "item_id": item_id,
                        "stratum": "fixture",
                        "presentation_ordinal": presentation,
                        "repeat_pair_id": f"{participant[-1]}_{category}",
                        "ordinal_judgment": judgment,
                        "broken": False,
                        "auto_small": auto_small,
                    }
                )
    return sorted(
        rows,
        key=lambda row: (
            row["stratum"].encode(),
            row["item_id"].encode(),
            row["participant_hash"].encode(),
            row["presentation_ordinal"],
        ),
    )


def build_calibration_authority(renderer_manifest_hash: str) -> dict[str, dict[str, Any]]:
    """Build the closed fixture evidence chain; never use it as a production default."""
    raw_authorities: dict[str, dict[str, Any]] = {}

    def raw(label: str, value: Any) -> str:
        payload = value if isinstance(value, bytes) else canonical_bytes(value)
        digest = _raw_hash(payload)
        raw_authorities[label] = {"hash": digest, "bytes_hex": payload.hex()}
        return digest

    participants = [
        raw(f"participant-{ordinal}", {"fixture_participant": ordinal}) for ordinal in range(2)
    ]
    participants.sort()
    cohort = _seal(
        {
            "schema": "cps.listener-cohort-manifest",
            "schema_version": "1.0.0",
            "cohort_id": "search_loop_13_fixture_only",
            "participant_hashes": participants,
            "recruitment_protocol_hash": raw("recruitment-protocol", {"fixture_only": True}),
            "eligibility_rule_hash": raw("eligibility-rule", {"fixture_only": True}),
            "exclusion_rule_hash": raw("exclusion-rule", {"excluded": []}),
            "consent_scope_hash": raw("consent-scope", {"scope": "conformance_fixture_only"}),
            "minimum_completed_trials_per_listener": 6,
            "manifest_hash": "",
        },
        "manifest_hash",
    )
    extractor = _seal(
        {
            "schema": "cps.feature-extractor-manifest",
            "schema_version": "1.0.0",
            "extractor_id": "search_loop_13_fixture_only",
            "extractor_version": "1",
            "extractor_build_hash": raw("extractor-build", b"search-loop-13-fixture-extractor-v1"),
            "input_audio_contract_hash": raw(
                "audio-contract", {"pcm": "q31", "sample_rate_hz": 48000}
            ),
            "model_config_hash": raw("model-config", {"embedding_dimension": 1}),
            "model_weights_hash": raw("model-weights", b"\x00\x00\x00\x00"),
            "runtime_hash": raw("extractor-runtime", {"integer_only": True}),
            "sample_rate_hz": 48_000,
            "channel_policy": "mono_downmix_rhe_q31/v1",
            "segment_policy": {
                "algorithm": "fixed-frame-window/v1",
                "start_frame": 0,
                "frame_count": 1,
            },
            "embedding_dimension": 1,
            "quantization": "signed_q31_rhe/v1",
            "manifest_hash": "",
        },
        "manifest_hash",
    )
    license_policy = _seal(
        {
            "schema": "cps.genre-license-policy",
            "schema_version": "1.0.0",
            "allowed_rights_bases": ["owned"],
            "require_storage_right": True,
            "require_feature_extraction_right": True,
            "require_evaluation_right": True,
            "expiry_policy": "reject_at_or_after_expiry/v1",
            "revocation_policy": "reject_revoked/v1",
            "raw_audio_null_policy": "eligible_only_with_feature_record_and_verified_nonretention_grant/v1",
            "policy_hash": "",
        },
        "policy_hash",
    )
    reference_partitions = ("calibration", "validation", "holdout")
    feature_records: dict[str, dict[str, Any]] = {}
    provenances: dict[str, dict[str, Any]] = {}
    for ordinal, partition in enumerate(reference_partitions):
        reference_id = f"reference_{partition}"
        retained_audio_identity = raw(
            f"nonretained-audio-identity-{partition}",
            {"reference_id": reference_id, "nonretained": True},
        )
        feature_records[partition] = _seal(
            {
                "schema": "cps.genre-feature-record",
                "schema_version": "1.0.0",
                "feature_extractor_manifest_hash": extractor["manifest_hash"],
                "source_audio_artifact_hash": retained_audio_identity,
                "segment_start_frame": 0,
                "segment_frame_count": 1,
                "embedding_q31": [ordinal],
                "record_hash": "",
            },
            "record_hash",
        )
        provenances[partition] = _seal(
            {
                "schema": "cps.reference-source-provenance",
                "schema_version": "1.0.0",
                "reference_id": reference_id,
                "source_class": "internal",
                "source_locator_hash": raw(
                    f"source-locator-{partition}", {"reference_id": reference_id}
                ),
                "rights_basis": "owned",
                "license_policy_hash": license_policy["policy_hash"],
                "storage_allowed": True,
                "feature_extraction_allowed": True,
                "evaluation_allowed": True,
                "expiry_epoch_day": None,
                "revoked": False,
                "raw_audio_hash": None,
                "raw_audio_null_reason": "verified_nonretention",
                "attribution_hash": None,
                "provenance_hash": "",
            },
            "provenance_hash",
        )
    reference = _seal(
        {
            "schema": "cps.genre-reference-set-manifest",
            "schema_version": "1.0.0",
            "reference_set_id": "search_loop_13_fixture_only",
            "feature_extractor_manifest_hash": extractor["manifest_hash"],
            "license_policy_hash": license_policy["policy_hash"],
            "license_policy_schema_hash": _raw_hash(
                (SCHEMAS / "genre_license_policy.schema.json").read_bytes()
            ),
            "source_provenance_schema_hash": _raw_hash(
                (SCHEMAS / "reference_source_provenance.schema.json").read_bytes()
            ),
            "members": [
                {
                    "reference_id": f"reference_{partition}",
                    "partition": partition,
                    "source_provenance_hash": provenances[partition]["provenance_hash"],
                    "feature_record_hash": feature_records[partition]["record_hash"],
                    "raw_audio_hash": None,
                }
                for partition in reference_partitions
            ],
            "manifest_hash": "",
        },
        "manifest_hash",
    )
    operator = _seal(
        {
            "schema": "cps.calibration-statistic-operator",
            "schema_version": "1.0.0",
            "algorithm": "ordinal-agreement-and-classification-q/v1",
            "quantum": 10_000,
            "ordinal_codes": ["smaller", "similar", "larger"],
            "ordinal_weight_matrix_q": [
                [10_000, 7_500, 0],
                [7_500, 10_000, 7_500],
                [0, 7_500, 10_000],
            ],
            "within_rater_algorithm": "weighted-kappa-paired-repeat/v1",
            "inter_rater_algorithm": "mean-pairwise-ordinal-weight/v1",
            "precision_algorithm": "auto-small-human-similar-and-not-broken/v1",
            "false_accept_algorithm": "auto-small-human-large-or-broken/v1",
            "integer_rounding": "nonnegative-rhe/v1",
            "zero_denominator_policy": "criterion-fails/v1",
            "operator_hash": "",
        },
        "operator_hash",
    )
    policy = _seal(
        {
            "schema": "cps.calibration-acceptance-policy",
            "schema_version": "1.0.0",
            "algorithm": "deterministic-stratified-bootstrap-q/v1",
            "root_seed": 7,
            "statistic_operator_hash": operator["operator_hash"],
            "evaluation_epoch_day": 0,
            "replicate_count": 8,
            "strata": ["fixture"],
            "lower_rank_numerator": 0,
            "lower_rank_denominator": 1,
            "upper_rank_numerator": 1,
            "upper_rank_denominator": 1,
            "minimum_listeners": 2,
            "minimum_judgments": 12,
            "minimum_within_rater_q": 0,
            "minimum_inter_rater_q": 0,
            "minimum_precision_lower_q": 0,
            "maximum_false_accept_upper_q": 10_000,
            "policy_hash": "",
        },
        "policy_hash",
    )
    rows = _response_rows(participants)
    validate_response_rows(rows, participants, policy["strata"])
    response = _seal(
        {
            "schema": "cps.calibration-response-set",
            "schema_version": "1.0.0",
            "dataset_id": "search_loop_13_fixture_only",
            "rows": rows,
            "response_hash": "",
        },
        "response_hash",
    )
    assignment = _seal(
        {
            "schema": "cps.blinded-assignment-manifest",
            "schema_version": "1.0.0",
            "cohort_manifest_hash": cohort["manifest_hash"],
            "root_seed": 7,
            "randomization_algorithm": "path-addressed-sha256-fisher-yates/v1",
            "assignments_hash": raw("assignments", rows),
            "assignment_count": len(rows),
            "fixed_before_response_hash": raw(
                "fixed-before-response", {"root_seed": 7, "assignment_count": len(rows)}
            ),
            "manifest_hash": "",
        },
        "manifest_hash",
    )
    dataset = _seal(
        {
            "schema": "cps.calibration-dataset-manifest",
            "schema_version": "1.0.0",
            "reference_set_manifest_hash": reference["manifest_hash"],
            "listener_cohort_manifest_hash": cohort["manifest_hash"],
            "blinded_assignment_manifest_hash": assignment["manifest_hash"],
            "response_schema_hash": _raw_hash(
                (SCHEMAS / "calibration_response_set.schema.json").read_bytes()
            ),
            "responses_hash": response["response_hash"],
            "exclusions_hash": raw("empty-exclusions", []),
            "exclusion_rules_fixed_hash": raw(
                "fixed-exclusion-rules", {"rules": [], "fixed_before_response": True}
            ),
            "partition_membership_hash": raw(
                "partition-membership",
                {
                    "calibration": ["reference_calibration"],
                    "validation": ["reference_validation"],
                    "holdout": ["reference_holdout"],
                },
            ),
            "partition_leakage_count": 0,
            "manifest_hash": "",
        },
        "manifest_hash",
    )
    bootstrap = calibration_bootstrap_values(
        rows,
        root_seed=policy["root_seed"],
        replicate_count=policy["replicate_count"],
        strata=policy["strata"],
    )
    trace = _seal(
        {
            "schema": "cps.calibration-bootstrap-trace",
            "schema_version": "1.0.0",
            "acceptance_policy_hash": policy["policy_hash"],
            "statistic_operator_hash": operator["operator_hash"],
            "within_rater_values_q": bootstrap["within_rater"],
            "inter_rater_values_q": bootstrap["inter_rater"],
            "precision_values_q": bootstrap["precision"],
            "false_accept_values_q": bootstrap["false_accept"],
            "trace_hash": "",
        },
        "trace_hash",
    )
    statistics = calibration_statistics(rows)
    precision_interval = rank_interval(
        bootstrap["precision"],
        policy["lower_rank_numerator"],
        policy["lower_rank_denominator"],
        policy["upper_rank_numerator"],
        policy["upper_rank_denominator"],
    )
    false_interval = rank_interval(
        bootstrap["false_accept"],
        policy["lower_rank_numerator"],
        policy["lower_rank_denominator"],
        policy["upper_rank_numerator"],
        policy["upper_rank_denominator"],
    )
    criteria = [
        {"id": "minimum_listeners", "passed": len(participants) >= policy["minimum_listeners"]},
        {"id": "minimum_judgments", "passed": len(rows) >= policy["minimum_judgments"]},
        {
            "id": "within_rater",
            "passed": calibrated_criterion(
                statistics["within_rater_q"], minimum=policy["minimum_within_rater_q"]
            ),
        },
        {
            "id": "inter_rater",
            "passed": calibrated_criterion(
                statistics["inter_rater_q"], minimum=policy["minimum_inter_rater_q"]
            ),
        },
        {
            "id": "precision_lower",
            "passed": precision_interval[0] >= policy["minimum_precision_lower_q"],
        },
        {
            "id": "false_accept_upper",
            "passed": false_interval[1] <= policy["maximum_false_accept_upper_q"],
        },
    ]
    summary = _seal(
        {
            "schema": "cps.calibration-evidence-summary",
            "schema_version": "1.0.0",
            "dataset_manifest_hash": dataset["manifest_hash"],
            "acceptance_policy_hash": policy["policy_hash"],
            "statistic_operator_hash": operator["operator_hash"],
            "listener_count": len(participants),
            "judgment_count": len(rows),
            **{
                key: statistics[key]
                for key in (
                    "repeat_pair_count",
                    "inter_rater_pair_count",
                    "auto_small_count",
                    "auto_small_true_positive_count",
                    "large_or_broken_count",
                    "large_or_broken_false_accept_count",
                    "within_rater_q",
                    "inter_rater_q",
                )
            },
            "precision_interval_q": {
                "lower_q": precision_interval[0],
                "upper_q": precision_interval[1],
            },
            "false_accept_interval_q": {"lower_q": false_interval[0], "upper_q": false_interval[1]},
            "bootstrap_trace_hash": trace["trace_hash"],
            "criteria": criteria,
            "summary_hash": "",
        },
        "summary_hash",
    )
    if not all(row["passed"] for row in criteria):
        raise AssertionError("fixture-only calibration did not satisfy its bound policy")
    fixture_set = _seal(
        {
            "schema": "cps.calibration-fixture-set",
            "schema_version": "1.0.0",
            "scope": "search_loop_13_fixture_only",
            "reference_set_manifest_hash": reference["manifest_hash"],
            "listener_cohort_manifest_hash": cohort["manifest_hash"],
            "blinded_assignment_manifest_hash": assignment["manifest_hash"],
            "response_set_hash": response["response_hash"],
            "dataset_manifest_hash": dataset["manifest_hash"],
            "statistic_operator_hash": operator["operator_hash"],
            "acceptance_policy_hash": policy["policy_hash"],
            "bootstrap_trace_hash": trace["trace_hash"],
            "evidence_summary_hash": summary["summary_hash"],
            "fixture_set_hash": "",
        },
        "fixture_set_hash",
    )
    promoted = [
        {
            "metric_id": metric_id,
            "noninferiority_margin_q": 0,
            "improvement_margin_q": 1,
            "evidence_hash": summary["summary_hash"],
        }
        for metric_id in ("genre_similarity", "native_ji_quality")
    ]
    decision = _seal(
        {
            "schema": "cps.calibration-decision",
            "schema_version": "1.1.0",
            "status": "promoted",
            "reference_set_manifest_hash": reference["manifest_hash"],
            "feature_extractor_manifest_hash": extractor["manifest_hash"],
            "renderer_manifest_hash": renderer_manifest_hash,
            "listener_cohort_manifest_hash": cohort["manifest_hash"],
            "calibration_fixture_set_hash": fixture_set["fixture_set_hash"],
            "acceptance_policy_hash": policy["policy_hash"],
            "evidence_summary_hash": summary["summary_hash"],
            "promoted_metrics": promoted,
            "metric_ids": [row["metric_id"] for row in promoted],
            "failure_code": None,
            "decision_hash": "",
        },
        "decision_hash",
    )
    return {
        "raw_authorities": raw_authorities,
        "genre_license_policy": license_policy,
        "reference_source_provenances": provenances,
        "genre_feature_records": feature_records,
        "listener_cohort_manifest": cohort,
        "feature_extractor_manifest": extractor,
        "genre_reference_set_manifest": reference,
        "calibration_statistic_operator": operator,
        "calibration_acceptance_policy": policy,
        "calibration_response_set": response,
        "blinded_assignment_manifest": assignment,
        "calibration_dataset_manifest": dataset,
        "calibration_bootstrap_trace": trace,
        "calibration_evidence_summary": summary,
        "calibration_fixture_set": fixture_set,
        "calibration_decision": decision,
    }


def write_calibration_authority(root: Path, renderer_manifest_hash: str) -> dict[str, Any]:
    """Materialize canonical CAS inputs and a self-hashed pack index."""
    authority = build_calibration_authority(renderer_manifest_hash)
    root.mkdir(parents=True, exist_ok=True)
    entries: list[dict[str, Any]] = []

    documents = {name: authority[name] for name in HASH_FIELDS}
    documents.update(
        {
            f"reference_source_provenance_{key}": value
            for key, value in authority["reference_source_provenances"].items()
        }
    )
    documents.update(
        {
            f"genre_feature_record_{key}": value
            for key, value in authority["genre_feature_records"].items()
        }
    )
    nested_fields = {
        **HASH_FIELDS,
        **{
            name: "provenance_hash"
            for name in documents
            if name.startswith("reference_source_provenance_")
        },
        **{name: "record_hash" for name in documents if name.startswith("genre_feature_record_")},
    }
    for name in sorted(documents):
        document = documents[name]
        payload = canonical_bytes(document)
        path = f"artifacts/{name}.json"
        target = root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)
        schema_name = document["schema"].removeprefix("cps.").replace("-", "_") + ".schema.json"
        if name == "calibration_decision":
            schema_name = "calibration_decision_1_1.schema.json"
        entries.append(
            {
                "name": name,
                "kind": "artifact",
                "path": path,
                "content_hash": document[nested_fields[name]],
                "canonical_bytes_sha256": _raw_hash(payload),
                "schema_raw_sha256": _raw_hash((SCHEMAS / schema_name).read_bytes()),
            }
        )
    for label, binding in sorted(authority["raw_authorities"].items()):
        payload = bytes.fromhex(binding["bytes_hex"])
        path = f"raw/{label}.bin"
        target = root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)
        entries.append(
            {
                "name": label,
                "kind": "raw",
                "path": path,
                "content_hash": binding["hash"],
                "canonical_bytes_sha256": binding["hash"],
                "schema_raw_sha256": None,
            }
        )
    index = {
        "schema": "cps.search-loop-13-calibration-authority-index",
        "schema_version": "1.0.0",
        "scope": "fixture_only_not_production_default",
        "renderer_manifest_hash": renderer_manifest_hash,
        "entries": sorted(entries, key=lambda row: row["name"].encode()),
        "index_hash": "",
    }
    index = _seal(index, "index_hash")
    (root / "index.json").write_text(
        json.dumps(index, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
        encoding="utf-8",
    )
    return index
