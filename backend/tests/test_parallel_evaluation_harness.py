from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.songprogram.evaluation_harness import (
    MockSearchEvaluationAdapter,
    ParallelEvaluationError,
    SearchEvaluationAdapter,
    _artifact_hash,
    evaluate_parallel_mock,
    genre_similarity_q,
)
from app.songprogram.native_ji import NativeJIError, evaluate_native_ji


BACKEND = Path(__file__).resolve().parents[1]
FIXTURES = BACKEND / "songprogram_conformance" / "fixtures"


def _load(path: Path) -> dict:
    return json.loads(path.read_text())


def _feature(values: list[int], source: str) -> dict:
    record = {
        "schema": "cps.genre-feature-record",
        "schema_version": "1.0.0",
        "feature_extractor_manifest_hash": "sha256:" + "11" * 32,
        "source_audio_artifact_hash": source,
        "segment_start_frame": 0,
        "segment_frame_count": 48000,
        "embedding_q31": values,
        "record_hash": "",
    }
    record["record_hash"] = _artifact_hash(record, "record_hash")
    return record


def test_native_ji_production_matches_independent_golden() -> None:
    case = _load(FIXTURES / "pil_oracle" / "pil_nonfunctional_two_reports.json")
    manifest = _load(FIXTURES / "native_ji" / "pil_nonfunctional_manifest.json")
    expected = _load(FIXTURES / "native_ji" / "pil_nonfunctional_report.json")
    assert evaluate_native_ji(case["project"], manifest) == expected


def test_native_ji_rejects_mutated_manifest() -> None:
    case = _load(FIXTURES / "pil_oracle" / "pil_nonfunctional_two_reports.json")
    manifest = _load(FIXTURES / "native_ji" / "pil_nonfunctional_manifest.json")
    manifest["distance_cap"] += 1
    with pytest.raises(NativeJIError, match="NATIVE_JI_MANIFEST_INVALID"):
        evaluate_native_ji(case["project"], manifest)


def test_genre_similarity_is_lower_median_and_order_independent() -> None:
    candidate = _feature([0, 0], "sha256:" + "20" * 32)
    references = [
        _feature([0, 0], "sha256:" + "21" * 32),
        _feature([2**31 - 1, 2**31 - 1], "sha256:" + "22" * 32),
        _feature([-(2**31), -(2**31)], "sha256:" + "23" * 32),
    ]
    forward = genre_similarity_q(candidate, references)
    reverse = genre_similarity_q(candidate, list(reversed(references)))
    assert forward == reverse == 5000


def test_genre_similarity_rejects_extractor_substitution() -> None:
    candidate = _feature([0], "sha256:" + "20" * 32)
    reference = _feature([0], "sha256:" + "21" * 32)
    reference["feature_extractor_manifest_hash"] = "sha256:" + "99" * 32
    reference["record_hash"] = _artifact_hash(reference, "record_hash")
    with pytest.raises(ParallelEvaluationError, match="GENRE_REFERENCE_FEATURE_INVALID"):
        genre_similarity_q(candidate, [reference])


def test_search_adapter_uses_candidate_audio_feature_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    feature = _feature([1], "sha256:" + "20" * 32)
    calls: list[tuple[dict, dict]] = []

    def fake_parallel(project: dict, authority: dict, candidate: dict, *, cache_dir: str | None):
        calls.append((project, candidate))
        return {"quality": [1, 2, 3, 4, 5], "cache_dir": cache_dir}

    monkeypatch.setattr("app.songprogram.evaluation_harness.evaluate_parallel", fake_parallel)
    adapter = SearchEvaluationAdapter(
        authority={"authority_hash": "sha256:" + "01" * 32},
        feature_provider=lambda project: feature,
        cache_dir="/tmp/evaluation-cache",
    )
    result = adapter({"project": 1}, {}, {}, {})
    assert result["quality"] == [1, 2, 3, 4, 5]
    assert calls == [({"project": 1}, feature)]


def test_mock_search_adapter_uses_only_explicit_mock_entrypoint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    feature = _feature([1], "sha256:" + "20" * 32)
    calls: list[tuple[dict, dict]] = []

    def fake_mock(project: dict, authority: dict, candidate: dict, *, cache_dir: str | None):
        calls.append((project, candidate))
        return {
            "quality": [1, 2, 3, 4, 5],
            "evaluation_mode": "mock_failed_genre_discrimination",
            "production_decisions_allowed": False,
        }

    monkeypatch.setattr(
        "app.songprogram.evaluation_harness.evaluate_parallel_mock", fake_mock
    )
    adapter = MockSearchEvaluationAdapter(
        authority={"authority_hash": "sha256:" + "01" * 32},
        feature_provider=lambda project: feature,
        cache_dir="/tmp/evaluation-cache",
    )
    result = adapter({"project": 1}, {}, {}, {})
    assert result["evaluation_mode"] == "mock_failed_genre_discrimination"
    assert result["production_decisions_allowed"] is False
    assert calls == [({"project": 1}, feature)]


def test_mock_evaluator_rejects_production_authority_before_execution() -> None:
    authority = {
        "schema": "cps.parallel-evaluation-authority",
        "schema_version": "1.0.0",
        "authority_hash": "sha256:" + "00" * 32,
    }
    with pytest.raises(ParallelEvaluationError, match="EVALUATION_AUTHORITY_INVALID"):
        evaluate_parallel_mock({}, authority, {})
