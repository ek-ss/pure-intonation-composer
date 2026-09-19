from __future__ import annotations

from app.songprogram.audio_features import genre_feature_record_hash
from app.songprogram.genre_discrimination import evaluate_genre_discrimination


def _record(identifier: int, value: int) -> dict:
    record = {
        "schema": "cps.genre-feature-record",
        "schema_version": "1.0.0",
        "feature_extractor_manifest_hash": "sha256:" + "a" * 64,
        "source_audio_artifact_hash": "sha256:" + f"{identifier:064x}",
        "segment_start_frame": 0,
        "segment_frame_count": 1,
        "embedding_q31": [value],
        "record_hash": "",
    }
    record["record_hash"] = genre_feature_record_hash(record)
    return record


def test_discrimination_threshold_uses_calibration_and_separates_fixture() -> None:
    positive = {
        "calibration": [_record(1, 2_000_000_000), _record(2, 1_900_000_000)],
        "validation": [_record(3, 1_950_000_000)],
        "holdout": [_record(4, 1_980_000_000)],
    }
    negative = {
        "calibration": [_record(5, -2_000_000_000), _record(6, -1_900_000_000)],
        "validation": [_record(7, -1_950_000_000)],
        "holdout": [_record(8, -1_980_000_000)],
    }
    report = evaluate_genre_discrimination(
        positive_set_id="positive", negative_set_id="negative", positive=positive, negative=negative
    )
    assert report["partitions"]["validation"]["performance"]["auc_q"] == 10_000
    assert report["partitions"]["holdout"]["performance"]["balanced_accuracy_q"] == 10_000
    assert report["diagnostics"] == []
