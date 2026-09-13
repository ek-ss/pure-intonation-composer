"""Independent fixture-only CalibrationDecision 1.1 draft authority builder.

This module computes the closed calibration chain but deliberately does not
write an authoritative fixture pack.  Supporting license, provenance, feature,
assignment, and exclusion artifacts must be materialized before promotion.
"""

from __future__ import annotations

import hashlib
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


def _opaque(label: str) -> str:
    return (
        "sha256:"
        + hashlib.sha256(b"cps-search-loop13-fixture-only/v1\0" + label.encode()).hexdigest()
    )


def _seal(value: dict[str, Any], member: str) -> dict[str, Any]:
    value[member] = artifact_hash(value, member)
    return value


def _fixture_set_hash(response_hash: str, cohort_hash: str, reference_hash: str) -> str:
    value = {
        "scope": "search_loop_13_fixture_only",
        "response_hash": response_hash,
        "cohort_hash": cohort_hash,
        "reference_hash": reference_hash,
    }
    return (
        "sha256:"
        + hashlib.sha256(b"cps-calibration-fixture-set/v1\0" + canonical_bytes(value)).hexdigest()
    )


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
    """Build the draft evidence chain; never use it as a production default."""
    participants = [_opaque(f"participant-{ordinal}") for ordinal in range(2)]
    participants.sort()
    cohort = _seal(
        {
            "schema": "cps.listener-cohort-manifest",
            "schema_version": "1.0.0",
            "cohort_id": "search_loop_13_fixture_only",
            "participant_hashes": participants,
            "recruitment_protocol_hash": _opaque("recruitment-protocol"),
            "eligibility_rule_hash": _opaque("eligibility-rule"),
            "exclusion_rule_hash": _opaque("exclusion-rule"),
            "consent_scope_hash": _opaque("consent-scope"),
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
            "extractor_build_hash": _opaque("extractor-build"),
            "input_audio_contract_hash": _opaque("audio-contract"),
            "model_config_hash": _opaque("model-config"),
            "model_weights_hash": _opaque("model-weights"),
            "runtime_hash": _opaque("extractor-runtime"),
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
    reference = _seal(
        {
            "schema": "cps.genre-reference-set-manifest",
            "schema_version": "1.0.0",
            "reference_set_id": "search_loop_13_fixture_only",
            "feature_extractor_manifest_hash": extractor["manifest_hash"],
            "license_policy_hash": _opaque("license-policy"),
            "license_policy_schema_hash": _opaque("license-policy-schema"),
            "source_provenance_schema_hash": _opaque("provenance-schema"),
            "members": [
                {
                    "reference_id": f"reference_{partition}",
                    "partition": partition,
                    "source_provenance_hash": _opaque(f"provenance-{partition}"),
                    "feature_record_hash": _opaque(f"feature-{partition}"),
                    "raw_audio_hash": None,
                }
                for partition in ("calibration", "validation", "holdout")
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
            "assignments_hash": _opaque("assignments"),
            "assignment_count": len(rows),
            "fixed_before_response_hash": _opaque("fixed-before-response"),
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
            "response_schema_hash": _opaque("calibration-response-schema"),
            "responses_hash": response["response_hash"],
            "exclusions_hash": _opaque("empty-exclusions"),
            "exclusion_rules_fixed_hash": _opaque("fixed-exclusion-rules"),
            "partition_membership_hash": _opaque("partition-membership"),
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
    fixture_set_hash = _fixture_set_hash(
        response["response_hash"], cohort["manifest_hash"], reference["manifest_hash"]
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
            "calibration_fixture_set_hash": fixture_set_hash,
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
        "calibration_decision": decision,
    }
