"""Parallel Native-JI, PIL, and reference-genre evaluation for SearchLoop."""

from __future__ import annotations

import hashlib
from copy import deepcopy
from dataclasses import dataclass
from fractions import Fraction
from typing import Any, Callable, Mapping, Sequence

from .compiler import _canonical, _rhe
from .native_ji import evaluate_native_ji
from .perceptual import project_hash, run_perceptual_interpretation
from .perceptual_genre import run_phase5_interpretation


class ParallelEvaluationError(ValueError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def _artifact_hash(value: Mapping[str, Any], member: str) -> str:
    try:
        body = {key: item for key, item in value.items() if key != member}
        prefix = (f"cps-artifact-hash/v1\0{value['schema']}\0{value['schema_version']}\0").encode()
    except (KeyError, TypeError):
        raise ParallelEvaluationError("EVALUATION_AUTHORITY_INVALID") from None
    return "sha256:" + hashlib.sha256(prefix + _canonical(body)).hexdigest()


def _sealed(value: Mapping[str, Any], member: str) -> bool:
    return isinstance(value.get(member), str) and value[member] == _artifact_hash(value, member)


def parallel_evaluation_authority_hash(authority: Mapping[str, Any]) -> str:
    return _artifact_hash(authority, "authority_hash")


def parallel_evaluation_report_hash(report: Mapping[str, Any]) -> str:
    return _artifact_hash(report, "report_hash")


def genre_similarity_q(
    candidate: Mapping[str, Any],
    references: Sequence[Mapping[str, Any]],
) -> int:
    """normalized-l1-q31/v1 with lower-median reference aggregation."""
    if not _sealed(candidate, "record_hash"):
        raise ParallelEvaluationError("GENRE_CANDIDATE_FEATURE_INVALID")
    vector = candidate.get("embedding_q31")
    if (
        not isinstance(vector, list)
        or not vector
        or any(type(value) is not int or not -(2**31) <= value <= 2**31 - 1 for value in vector)
    ):
        raise ParallelEvaluationError("GENRE_CANDIDATE_FEATURE_INVALID")
    scores = []
    maximum = 4_294_967_295 * len(vector)
    for reference in references:
        if not _sealed(reference, "record_hash"):
            raise ParallelEvaluationError("GENRE_REFERENCE_FEATURE_INVALID")
        other = reference.get("embedding_q31")
        if (
            reference.get("feature_extractor_manifest_hash")
            != candidate.get("feature_extractor_manifest_hash")
            or not isinstance(other, list)
            or len(other) != len(vector)
            or any(type(value) is not int or not -(2**31) <= value <= 2**31 - 1 for value in other)
        ):
            raise ParallelEvaluationError("GENRE_REFERENCE_FEATURE_INVALID")
        distance = sum(abs(left - right) for left, right in zip(vector, other, strict=True))
        scores.append(10_000 - _rhe(Fraction(10_000 * distance, maximum)))
    if not scores:
        raise ParallelEvaluationError("GENRE_CALIBRATION_REFERENCES_EMPTY")
    scores.sort()
    return scores[(len(scores) - 1) // 2]


def _validate_genre_authority(authority: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    intent = authority["genre_intent"]
    reference_set = authority["genre_reference_set_manifest"]
    similarity = authority["genre_similarity_spec"]
    calibration = authority["calibration_decision"]
    if (
        not _sealed(intent, "intent_hash")
        or not _sealed(reference_set, "manifest_hash")
        or not _sealed(similarity, "spec_hash")
        or not _sealed(calibration, "decision_hash")
        or intent.get("reference_set_manifest_hash") != reference_set.get("manifest_hash")
        or intent.get("feature_extractor_manifest_hash")
        != reference_set.get("feature_extractor_manifest_hash")
        or intent.get("genre_similarity_spec_hash") != similarity.get("spec_hash")
        or intent.get("calibration_decision_hash") != calibration.get("decision_hash")
        or calibration.get("status") != "promoted"
        or calibration.get("reference_set_manifest_hash") != reference_set.get("manifest_hash")
        or calibration.get("feature_extractor_manifest_hash")
        != reference_set.get("feature_extractor_manifest_hash")
        or not isinstance(calibration.get("metric_ids"), list)
        or "genre_similarity" not in calibration.get("metric_ids", [])
        or not isinstance(calibration.get("promoted_metrics"), list)
        or not any(
            row.get("metric_id") == "genre_similarity"
            for row in calibration.get("promoted_metrics", [])
            if isinstance(row, Mapping)
        )
        or similarity.get("algorithm") != "normalized-l1-q31/v1"
        or similarity.get("aggregation") != "lower-median-reference-score/v1"
    ):
        raise ParallelEvaluationError("GENRE_AUTHORITY_BINDING_MISMATCH")
    supplied = authority["genre_reference_feature_records"]
    if not isinstance(supplied, list):
        raise ParallelEvaluationError("GENRE_REFERENCE_FEATURE_INVALID")
    by_hash = {
        record.get("record_hash"): record for record in supplied if isinstance(record, Mapping)
    }
    member_hashes = {
        member.get("feature_record_hash")
        for member in reference_set.get("members", [])
        if isinstance(member, Mapping)
    }
    if len(by_hash) != len(supplied) or not set(by_hash).issubset(member_hashes):
        raise ParallelEvaluationError("GENRE_REFERENCE_FEATURE_INVALID")
    selected = []
    for member in reference_set.get("members", []):
        if member.get("partition") != similarity.get("reference_partition"):
            continue
        record = by_hash.get(member.get("feature_record_hash"))
        if record is None:
            raise ParallelEvaluationError("GENRE_REFERENCE_FEATURE_MISSING")
        selected.append(record)
    if not selected:
        raise ParallelEvaluationError("GENRE_CALIBRATION_REFERENCES_EMPTY")
    return selected


def evaluate_parallel(
    project: Mapping[str, Any],
    authority: Mapping[str, Any],
    candidate_genre_feature_record: Mapping[str, Any],
    *,
    cache_dir: str | None = None,
) -> dict[str, Any]:
    """Evaluate all branches without allowing one branch to replace another."""
    required = {
        "schema",
        "schema_version",
        "native_ji_manifest",
        "pil_manifest",
        "segmentation_policy",
        "feature_spec",
        "chord_vocabulary",
        "voice_matching_policy",
        "trajectory_template_set",
        "genre_model",
        "genre_intent",
        "genre_reference_set_manifest",
        "genre_similarity_spec",
        "calibration_decision",
        "genre_reference_feature_records",
        "authority_hash",
    }
    if (
        not isinstance(authority, Mapping)
        or set(authority) != required
        or authority.get("schema") != "cps.parallel-evaluation-authority"
        or authority.get("schema_version") != "1.0.0"
        or authority.get("authority_hash") != parallel_evaluation_authority_hash(authority)
    ):
        raise ParallelEvaluationError("EVALUATION_AUTHORITY_INVALID")
    references = _validate_genre_authority(authority)
    if candidate_genre_feature_record.get("feature_extractor_manifest_hash") != authority[
        "genre_reference_set_manifest"
    ].get("feature_extractor_manifest_hash"):
        raise ParallelEvaluationError("GENRE_EXTRACTOR_BINDING_MISMATCH")

    native = evaluate_native_ji(project, authority["native_ji_manifest"])
    pil = run_perceptual_interpretation(
        project,
        authority["pil_manifest"],
        native_ji_report_hash=native["report_hash"],
        segmentation_policy=authority["segmentation_policy"],
        feature_spec=authority["feature_spec"],
        chord_vocabulary=authority["chord_vocabulary"],
        voice_matching_policy=authority["voice_matching_policy"],
        trajectory_template_set=authority["trajectory_template_set"],
        cache_dir=cache_dir,
    )
    if pil.get("status") != "success":
        raise ParallelEvaluationError("PIL_EVALUATION_FAILED")
    phase5 = run_phase5_interpretation(
        project,
        authority["pil_manifest"],
        authority["genre_model"],
        segmentation_policy=authority["segmentation_policy"],
        feature_spec=authority["feature_spec"],
        chord_vocabulary=authority["chord_vocabulary"],
        voice_matching_policy=authority["voice_matching_policy"],
        trajectory_template_set=authority["trajectory_template_set"],
        phase4_report=pil,
        native_ji_report_hash=native["report_hash"],
        cache_dir=cache_dir,
    )
    similarity = genre_similarity_q(candidate_genre_feature_record, references)
    best = phase5[0]
    quality = [
        similarity,
        native["metrics"][0]["value_q"],
        best["typicality_q"],
        best["idiomaticity_q"],
        10_000 - best["cliche_dependence_q"],
    ]
    report = {
        "schema": "cps.parallel-evaluation-report",
        "schema_version": "1.0.0",
        "project_hash": project_hash(project),
        "authority_hash": authority["authority_hash"],
        "genre_intent_hash": authority["genre_intent"]["intent_hash"],
        "native_ji_report": native,
        "pil_report": pil,
        "pil_genre_results": phase5,
        "genre_similarity_q": similarity,
        "quality_metric_ids": [
            "genre_similarity_q",
            "native_ji.coherence",
            "pil_genre.typicality_q",
            "pil_genre.idiomaticity_q",
            "pil_genre.inverse_cliche_q",
        ],
        "quality": quality,
        "report_hash": "",
    }
    report["report_hash"] = parallel_evaluation_report_hash(report)
    return report


GenreFeatureProvider = Callable[[Mapping[str, Any]], Mapping[str, Any]]


@dataclass(frozen=True)
class SearchEvaluationAdapter:
    """Callable matching ``SearchLoopSeams.evaluate``."""

    authority: Mapping[str, Any]
    feature_provider: GenreFeatureProvider
    cache_dir: str | None = None

    def __call__(
        self,
        project: dict[str, Any],
        descriptor: dict[str, Any],
        fingerprint: dict[str, Any],
        connected_output: dict[str, Any],
    ) -> dict[str, Any]:
        del descriptor, fingerprint, connected_output
        feature = self.feature_provider(deepcopy(project))
        return evaluate_parallel(project, self.authority, feature, cache_dir=self.cache_dir)
