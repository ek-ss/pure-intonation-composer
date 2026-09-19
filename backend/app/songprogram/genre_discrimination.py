"""Diagnostic positive/negative discrimination for fixed genre FeatureRecords."""

from __future__ import annotations

import statistics
from fractions import Fraction
from typing import Any, Mapping, Sequence

from .compiler import _rhe
from .evaluation_harness import _artifact_hash, genre_similarity_q


class GenreDiscriminationError(ValueError):
    pass


def _summary(values: Sequence[int]) -> dict[str, int]:
    if not values:
        raise GenreDiscriminationError("GENRE_DISCRIMINATION_GROUP_EMPTY")
    ordered = sorted(values)
    return {
        "count": len(ordered),
        "minimum_q": ordered[0],
        "median_q": ordered[(len(ordered) - 1) // 2],
        "maximum_q": ordered[-1],
        "mean_q": round(statistics.mean(ordered)),
    }


def _performance(
    positive: Sequence[int], negative: Sequence[int], threshold: int
) -> dict[str, int]:
    tp = sum(score >= threshold for score in positive)
    fn = len(positive) - tp
    tn = sum(score < threshold for score in negative)
    fp = len(negative) - tn
    positive_recall = _rhe(Fraction(tp * 10_000, len(positive)))
    negative_recall = _rhe(Fraction(tn * 10_000, len(negative)))
    comparisons = len(positive) * len(negative)
    wins = sum(left > right for left in positive for right in negative)
    ties = sum(left == right for left in positive for right in negative)
    return {
        "true_positive": tp,
        "false_negative": fn,
        "true_negative": tn,
        "false_positive": fp,
        "positive_recall_q": positive_recall,
        "negative_recall_q": negative_recall,
        "balanced_accuracy_q": _rhe(Fraction(positive_recall + negative_recall, 2)),
        "auc_q": _rhe(Fraction((2 * wins + ties) * 10_000, 2 * comparisons)),
    }


def _calibration_threshold(positive: Sequence[int], negative: Sequence[int]) -> int:
    candidates = sorted({0, 10_001, *positive, *negative})
    ranked = []
    for threshold in candidates:
        result = _performance(positive, negative, threshold)
        ranked.append(
            (
                result["balanced_accuracy_q"],
                min(result["positive_recall_q"], result["negative_recall_q"]),
                threshold,
            )
        )
    return max(ranked)[2]


def evaluate_genre_discrimination(
    *,
    positive_set_id: str,
    negative_set_id: str,
    positive: Mapping[str, Sequence[Mapping[str, Any]]],
    negative: Mapping[str, Sequence[Mapping[str, Any]]],
) -> dict[str, Any]:
    partitions = ("calibration", "validation", "holdout")
    if any(not positive.get(name) or not negative.get(name) for name in partitions):
        raise GenreDiscriminationError("GENRE_DISCRIMINATION_PARTITIONS_INCOMPLETE")
    calibration_references = list(positive["calibration"])
    manifest_hashes = {
        row.get("feature_extractor_manifest_hash")
        for cohort in (positive, negative)
        for name in partitions
        for row in cohort[name]
    }
    if len(manifest_hashes) != 1:
        raise GenreDiscriminationError("GENRE_DISCRIMINATION_EXTRACTOR_MISMATCH")
    scores: dict[str, dict[str, list[int]]] = {}
    for partition in partitions:
        positive_scores = []
        for candidate in positive[partition]:
            references = calibration_references
            if partition == "calibration":
                references = [row for row in calibration_references if row is not candidate]
            positive_scores.append(genre_similarity_q(candidate, references))
        negative_scores = [
            genre_similarity_q(candidate, calibration_references)
            for candidate in negative[partition]
        ]
        scores[partition] = {"positive": positive_scores, "negative": negative_scores}
    threshold = _calibration_threshold(
        scores["calibration"]["positive"], scores["calibration"]["negative"]
    )
    partition_reports = {
        name: {
            "positive_scores": _summary(scores[name]["positive"]),
            "negative_scores": _summary(scores[name]["negative"]),
            "performance": _performance(
                scores[name]["positive"], scores[name]["negative"], threshold
            ),
        }
        for name in partitions
    }
    diagnostics = []
    if partition_reports["validation"]["performance"]["auc_q"] < 7_500:
        diagnostics.append("validation_separation_insufficient")
    if partition_reports["holdout"]["performance"]["auc_q"] < 7_500:
        diagnostics.append("holdout_separation_insufficient")
    report = {
        "schema": "cps.genre-feature-discrimination-report",
        "schema_version": "1.0.0",
        "positive_set_id": positive_set_id,
        "negative_set_id": negative_set_id,
        "feature_extractor_manifest_hash": next(iter(manifest_hashes)),
        "calibration_reference_count": len(calibration_references),
        "threshold_q": threshold,
        "threshold_rule": "max-balanced-accuracy-then-min-recall-then-highest-threshold/calibration-only/v1",
        "partitions": partition_reports,
        "diagnostics": diagnostics,
        "diagnostic_only": True,
        "report_hash": "",
    }
    report["report_hash"] = _artifact_hash(report, "report_hash")
    return report
