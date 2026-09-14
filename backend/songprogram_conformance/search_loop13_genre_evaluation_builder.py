"""Build the non-cyclic SearchLoop13 genre/evaluation/policy authority chain."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .canonical import canonical_bytes
from .search_loop13_fixture_oracle import artifact_hash


ROOT = Path(__file__).resolve().parents[1]
SCHEMAS = ROOT / "songprogram_conformance" / "schemas"
CALIBRATION = (
    ROOT / "songprogram_conformance" / "fixtures" / "search_loop_13" / "calibration_authority"
)


def _load(name: str) -> dict[str, Any]:
    return json.loads((CALIBRATION / "artifacts" / f"{name}.json").read_bytes())


def _raw_schema_hash(name: str) -> str:
    import hashlib

    return "sha256:" + hashlib.sha256((SCHEMAS / name).read_bytes()).hexdigest()


def _raw_file_hash(path: Path) -> str:
    import hashlib

    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _seal(value: dict[str, Any], member: str) -> dict[str, Any]:
    value[member] = artifact_hash(value, member)
    return value


def build_genre_evaluation_authority() -> dict[str, dict[str, Any]]:
    decision = _load("calibration_decision")
    reference = _load("genre_reference_set_manifest")
    extractor = _load("feature_extractor_manifest")
    similarity = _seal(
        {
            "schema": "cps.genre-similarity-spec",
            "schema_version": "1.0.0",
            "algorithm": "normalized-l1-q31/v1",
            "reference_partition": "calibration",
            "aggregation": "lower-median-reference-score/v1",
            "output_min": 0,
            "output_max": 10_000,
            "feature_record_schema_hash": _raw_schema_hash("genre_feature_record.schema.json"),
            "spec_hash": "",
        },
        "spec_hash",
    )
    intent = _seal(
        {
            "schema": "cps.genre-intent",
            "schema_version": "1.0.0",
            "intent_id": "search_loop_13_fixture_only",
            "display_label": "SearchLoop13 fixture-only Native JI plus perceptual genre",
            "requested_tags": ["fixture_only", "native_ji_parallel", "perceptual_genre"],
            "metrics": [
                {
                    "id": "genre_similarity",
                    "evaluation_metric_id": "genre_similarity",
                    "kind": "genre_similarity_q",
                    "usage": "acceptance",
                    "missing_policy": "ineligible",
                },
                {
                    "id": "native_ji_quality",
                    "evaluation_metric_id": "native_ji_quality",
                    "kind": "symbolic_integer",
                    "usage": "acceptance",
                    "missing_policy": "ineligible",
                },
            ],
            "reference_set_manifest_hash": reference["manifest_hash"],
            "feature_extractor_manifest_hash": extractor["manifest_hash"],
            "genre_similarity_spec_hash": similarity["spec_hash"],
            "calibration_decision_hash": decision["decision_hash"],
            "intent_hash": "",
        },
        "intent_hash",
    )
    compile_schema_hash = _raw_schema_hash("compile_report_1_1.schema.json")
    feature_schema_hash = _raw_schema_hash("genre_feature_record.schema.json")
    evaluation = _seal(
        {
            "schema": "cps.evaluation-manifest",
            "schema_version": "1.1.0",
            "evaluator_id": "search_loop_13_fixture_evaluator",
            "evaluator_version": "1",
            "evaluator_build_hash": _raw_file_hash(
                ROOT / "songprogram_conformance" / "evaluation_operator_oracle.py"
            ),
            "genre_intent_hash": intent["intent_hash"],
            "hard_checks": [
                {
                    "id": "compile_activity_valid",
                    "ordinal": 0,
                    "sources": [
                        {
                            "artifact_kind": "compile_report",
                            "schema_hash": compile_schema_hash,
                            "json_pointer": "/search_statistics/chord_query_count",
                        }
                    ],
                    "operator": {"kind": "integer_compare", "comparator": "ge", "threshold": 0},
                    "required_render": False,
                }
            ],
            "metrics": [
                {
                    "id": metric_id,
                    "ordinal": ordinal,
                    "sources": [
                        {
                            "artifact_kind": artifact_kind,
                            "schema_hash": source_schema_hash,
                            "json_pointer": pointer,
                        }
                    ],
                    "operator": operator,
                    "direction": direction,
                    "required_render": required_render,
                }
                for ordinal, (
                    metric_id,
                    artifact_kind,
                    source_schema_hash,
                    pointer,
                    operator,
                    direction,
                    required_render,
                ) in enumerate(
                    [
                        (
                            "distinct_sounding_material_lineage_count",
                            "compile_report",
                            compile_schema_hash,
                            "/search_statistics/chord_eligible_candidates",
                            {"kind": "integer_identity"},
                            "maximize",
                            False,
                        ),
                        (
                            "genre_similarity",
                            "genre_feature_record",
                            feature_schema_hash,
                            "/embedding_q31",
                            {
                                "kind": "genre_similarity_q",
                                "genre_similarity_spec_hash": similarity["spec_hash"],
                            },
                            "maximize",
                            True,
                        ),
                        (
                            "material_recurrence_distance_q",
                            "compile_report",
                            compile_schema_hash,
                            "/search_statistics/progression_states",
                            {"kind": "integer_identity"},
                            "maximize",
                            False,
                        ),
                        (
                            "native_ji_quality",
                            "compile_report",
                            compile_schema_hash,
                            "/search_statistics/chord_eligible_candidates",
                            {"kind": "integer_identity"},
                            "maximize",
                            False,
                        ),
                        (
                            "negative_program_structural_item_count",
                            "compile_report",
                            compile_schema_hash,
                            "/receipt/usage/total_logical_units",
                            {"kind": "integer_identity"},
                            "minimize",
                            False,
                        ),
                        (
                            "section_coverage_q",
                            "compile_report",
                            compile_schema_hash,
                            "/search_statistics/chord_query_count",
                            {"kind": "integer_identity"},
                            "maximize",
                            False,
                        ),
                        (
                            "sounding_role_count",
                            "compile_report",
                            compile_schema_hash,
                            "/search_statistics/progression_query_count",
                            {"kind": "integer_identity"},
                            "maximize",
                            False,
                        ),
                        (
                            "transformed_recall_count",
                            "compile_report",
                            compile_schema_hash,
                            "/search_statistics/chord_candidates_examined",
                            {"kind": "integer_identity"},
                            "maximize",
                            False,
                        ),
                    ]
                )
            ],
            "manifest_hash": "",
        },
        "manifest_hash",
    )
    report_schema_hash = _raw_schema_hash("evaluation_report_1_1.schema.json")
    promotion_by_id = {row["metric_id"]: row for row in decision["promoted_metrics"]}
    challenger = _seal(
        {
            "schema": "cps.challenger-acceptance-policy",
            "schema_version": "1.1.0",
            "genre_intent_hash": intent["intent_hash"],
            "calibration_decision_hash": decision["decision_hash"],
            "evaluation_manifest_hash": evaluation["manifest_hash"],
            "required_hard_checks": ["compile_activity_valid"],
            "metrics": [
                {
                    "id": row["id"],
                    "direction": row["direction"],
                    "noninferiority_margin_q": promotion_by_id[row["id"]][
                        "noninferiority_margin_q"
                    ],
                    "improvement_margin_q": promotion_by_id[row["id"]]["improvement_margin_q"],
                    "ordinal": ordinal,
                    "source": {
                        "artifact_kind": "evaluation_report",
                        "schema_hash": report_schema_hash,
                        "json_pointer": f"/metrics/{row['ordinal']}/value",
                    },
                }
                for ordinal, row in enumerate(
                    metric for metric in evaluation["metrics"] if metric["id"] in promotion_by_id
                )
            ],
            "pareto_rule": "all-noninferior-one-improved/v1",
            "tie_rule": "calibrated-margin-tuple-then-program-hash/v1",
            "policy_hash": "",
        },
        "policy_hash",
    )
    return {
        "genre_similarity_spec": similarity,
        "genre_intent": intent,
        "evaluation_manifest": evaluation,
        "challenger_acceptance_policy": challenger,
    }


def write_genre_evaluation_authority(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    for name, document in build_genre_evaluation_authority().items():
        (root / f"{name}.json").write_bytes(canonical_bytes(document))
