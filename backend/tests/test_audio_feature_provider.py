from __future__ import annotations

import io
import json
import struct
import wave
from pathlib import Path

import pytest

from app.songprogram.audio_features import (
    AudioFeatureError,
    extract_genre_feature_record,
    feature_extractor_manifest_hash,
    genre_feature_record_hash,
    validate_feature_extractor_manifest,
)


PROFILE = (
    Path(__file__).resolve().parents[1]
    / "songprogram_conformance"
    / "profiles"
    / "pcm32_genre_feature_extractor_v1.json"
)


def _manifest(frame_count: int = 320) -> dict:
    value = json.loads(PROFILE.read_text())
    value["segment_policy"]["frame_count"] = frame_count
    value["manifest_hash"] = feature_extractor_manifest_hash(value)
    return value


def _wav(samples: list[int], channels: int = 1) -> bytes:
    stream = io.BytesIO()
    with wave.open(stream, "wb") as output:
        output.setparams((channels, 4, 48000, len(samples) // channels, "NONE", "not compressed"))
        output.writeframes(struct.pack("<" + "i" * len(samples), *samples))
    return stream.getvalue()


def test_checked_snapshot_manifest_is_self_hashed() -> None:
    manifest = json.loads(PROFILE.read_text())
    validate_feature_extractor_manifest(manifest)
    assert manifest["manifest_hash"] == feature_extractor_manifest_hash(manifest)


def test_pcm_feature_extraction_is_deterministic_and_sealed() -> None:
    samples = [(-1 if index % 2 else 1) * (index * 1_000_000) for index in range(320)]
    payload = _wav(samples)
    first = extract_genre_feature_record(payload, _manifest())
    second = extract_genre_feature_record(payload, _manifest())
    assert first == second
    assert len(first["embedding_q31"]) == 32
    assert first["record_hash"] == genre_feature_record_hash(first)
    assert all(value >= 0 for value in first["embedding_q31"])


def test_stereo_downmix_uses_integer_half_even() -> None:
    samples = [value for _ in range(320) for value in (101, 100)]
    record = extract_genre_feature_record(_wav(samples, 2), _manifest())
    assert record["embedding_q31"][:16] == [100] * 16


def test_short_audio_is_rejected_without_padding() -> None:
    with pytest.raises(AudioFeatureError, match="AUDIO_FEATURE_SEGMENT_UNAVAILABLE"):
        extract_genre_feature_record(_wav([0] * 319), _manifest())
