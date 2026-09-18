"""Pinned deterministic PCM32 genre feature provider."""

from __future__ import annotations

import hashlib
import io
import struct
import wave
from fractions import Fraction
from pathlib import Path
from typing import Any, Mapping

from .compiler import _canonical, _rhe


class AudioFeatureError(ValueError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def _artifact_hash(value: Mapping[str, Any], member: str) -> str:
    body = {key: item for key, item in value.items() if key != member}
    prefix = (f"cps-artifact-hash/v1\0{value['schema']}\0{value['schema_version']}\0").encode()
    return "sha256:" + hashlib.sha256(prefix + _canonical(body)).hexdigest()


def feature_extractor_manifest_hash(manifest: Mapping[str, Any]) -> str:
    return _artifact_hash(manifest, "manifest_hash")


def genre_feature_record_hash(record: Mapping[str, Any]) -> str:
    return _artifact_hash(record, "record_hash")


def validate_feature_extractor_manifest(manifest: Mapping[str, Any]) -> None:
    required = {
        "schema",
        "schema_version",
        "extractor_id",
        "extractor_version",
        "extractor_build_hash",
        "input_audio_contract_hash",
        "model_config_hash",
        "model_weights_hash",
        "runtime_hash",
        "sample_rate_hz",
        "channel_policy",
        "segment_policy",
        "embedding_dimension",
        "quantization",
        "manifest_hash",
    }
    if (
        not isinstance(manifest, Mapping)
        or set(manifest) != required
        or manifest.get("schema") != "cps.feature-extractor-manifest"
        or manifest.get("schema_version") != "1.0.0"
        or manifest.get("extractor_id") != "cps.pcm32-temporal-energy-zcr"
        or manifest.get("extractor_version") != "1.0.0"
        or manifest.get("sample_rate_hz") != 48_000
        or manifest.get("channel_policy") != "mono_downmix_rhe_q31/v1"
        or manifest.get("embedding_dimension") != 32
        or manifest.get("quantization") != "signed_q31_rhe/v1"
        or manifest.get("segment_policy", {}).get("algorithm") != "fixed-frame-window/v1"
        or manifest.get("extractor_build_hash")
        != "sha256:" + hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
        or manifest.get("manifest_hash") != feature_extractor_manifest_hash(manifest)
    ):
        raise AudioFeatureError("AUDIO_FEATURE_MANIFEST_INVALID")
    segment = manifest["segment_policy"]
    if (
        type(segment.get("start_frame")) is not int
        or segment["start_frame"] < 0
        or type(segment.get("frame_count")) is not int
        or segment["frame_count"] < 32
    ):
        raise AudioFeatureError("AUDIO_FEATURE_MANIFEST_INVALID")


def _mono_pcm32(wav_payload: bytes, manifest: Mapping[str, Any]) -> list[int]:
    try:
        with wave.open(io.BytesIO(wav_payload), "rb") as source:
            channels = source.getnchannels()
            frames = source.getnframes()
            if (
                source.getframerate() != manifest["sample_rate_hz"]
                or source.getsampwidth() != 4
                or channels not in (1, 2)
                or source.getcomptype() != "NONE"
            ):
                raise AudioFeatureError("AUDIO_FEATURE_INPUT_CONTRACT_MISMATCH")
            samples = struct.unpack("<" + "i" * (frames * channels), source.readframes(frames))
    except (EOFError, struct.error, wave.Error):
        raise AudioFeatureError("AUDIO_FEATURE_INPUT_INVALID") from None
    if channels == 1:
        return list(samples)
    return [
        _rhe(Fraction(samples[index] + samples[index + 1], 2))
        for index in range(0, len(samples), 2)
    ]


def extract_genre_feature_record(wav_payload: bytes, manifest: Mapping[str, Any]) -> dict[str, Any]:
    """Extract 16 temporal energy and 16 zero-crossing Q1.31 bins."""
    validate_feature_extractor_manifest(manifest)
    pcm = _mono_pcm32(wav_payload, manifest)
    start = manifest["segment_policy"]["start_frame"]
    count = manifest["segment_policy"]["frame_count"]
    if start + count > len(pcm):
        raise AudioFeatureError("AUDIO_FEATURE_SEGMENT_UNAVAILABLE")
    segment = pcm[start : start + count]
    boundaries = [_rhe(Fraction(index * count, 16)) for index in range(17)]
    energy: list[int] = []
    crossings: list[int] = []
    for left, right in zip(boundaries, boundaries[1:]):
        values = segment[left:right]
        if not values:
            raise AudioFeatureError("AUDIO_FEATURE_SEGMENT_INVALID")
        energy.append(_rhe(Fraction(sum(abs(value) for value in values), len(values))))
        crossing_count = sum((a < 0 <= b) or (b < 0 <= a) for a, b in zip(values, values[1:]))
        crossings.append(_rhe(Fraction(crossing_count * (2**31 - 1), max(1, len(values) - 1))))
    record = {
        "schema": "cps.genre-feature-record",
        "schema_version": "1.0.0",
        "feature_extractor_manifest_hash": manifest["manifest_hash"],
        "source_audio_artifact_hash": "sha256:" + hashlib.sha256(wav_payload).hexdigest(),
        "segment_start_frame": start,
        "segment_frame_count": count,
        "embedding_q31": energy + crossings,
        "record_hash": "",
    }
    record["record_hash"] = genre_feature_record_hash(record)
    return record


class FixedSnapshotFeatureProvider:
    """SearchLoop provider resolving Project audio through a caller-owned renderer."""

    def __init__(self, manifest: Mapping[str, Any], render_wav: Any) -> None:
        validate_feature_extractor_manifest(manifest)
        self.manifest = dict(manifest)
        self.render_wav = render_wav

    def __call__(self, project: Mapping[str, Any]) -> dict[str, Any]:
        payload = self.render_wav(project)
        if not isinstance(payload, bytes):
            raise AudioFeatureError("AUDIO_FEATURE_PROVIDER_OUTPUT_INVALID")
        return extract_genre_feature_record(payload, self.manifest)
