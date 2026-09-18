from __future__ import annotations

import json
import importlib.util
from pathlib import Path
from types import ModuleType

import pytest

from app.songprogram.audio_features import genre_feature_record_hash


def _tool(name: str) -> ModuleType:
    path = Path(__file__).resolve().parents[1] / "tools" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


AUDIT = _tool("audit_genre_feature_cohort")
INGEST = _tool("ingest_genre_reference_transfer")


def _record(audio_digit: str, vector: list[int]) -> dict:
    record = {
        "schema": "cps.genre-feature-record",
        "schema_version": "1.0.0",
        "feature_extractor_manifest_hash": "sha256:" + "a" * 64,
        "source_audio_artifact_hash": "sha256:" + audio_digit * 64,
        "segment_start_frame": 0,
        "segment_frame_count": 480_000,
        "embedding_q31": vector,
        "record_hash": "",
    }
    record["record_hash"] = genre_feature_record_hash(record)
    return record


def test_transfer_paths_are_confined_to_declared_directory(tmp_path: Path) -> None:
    (tmp_path / "clips").mkdir()
    (tmp_path / "clips" / "ok.wav").write_bytes(b"wav")
    assert INGEST._resolved(tmp_path, "clips/ok.wav", "clips") == tmp_path / "clips" / "ok.wav"
    with pytest.raises(INGEST.TransferError, match="TRANSFER_PATH_INVALID"):
        INGEST._resolved(tmp_path, "clips/../outside.wav", "clips")


def test_audit_is_deterministic_and_flags_compressed_baseline(tmp_path: Path) -> None:
    features = tmp_path / "generated"
    (features / "features").mkdir(parents=True)
    rows = [
        ("cal", "calibration", _record("1", [100, 100])),
        ("val", "validation", _record("2", [101, 101])),
        ("hold", "holdout", _record("3", [102, 102])),
    ]
    index = []
    for identifier, _, record in rows:
        relative = f"features/{identifier}.json"
        (features / relative).write_text(json.dumps(record))
        index.append(
            {
                "reference_id": identifier,
                "feature_record_hash": record["record_hash"],
                "path": relative,
            }
        )
    (features / "feature_index.json").write_text(json.dumps(index))
    captions = tmp_path / "captions.json"
    captions.write_text(
        json.dumps(
            {
                "set_id": "test_set",
                "tracks": [
                    {"id": identifier, "partition": partition} for identifier, partition, _ in rows
                ],
            }
        )
    )
    first = AUDIT.audit(features, captions)
    second = AUDIT.audit(features, captions)
    assert first == second
    assert first["unique_audio_hash_count"] == 3
    assert first["unique_embedding_count"] == 3
    assert first["diagnostics"] == ["baseline_feature_separation_low"]


def test_audit_index_path_cannot_escape_feature_directory(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="COHORT_AUDIT_PATH_INVALID"):
        AUDIT._indexed_record(tmp_path, "features/../secret.json")
