from __future__ import annotations

import hashlib
import io
import json
import struct
import wave
from pathlib import Path

import pytest

from app.songprogram.audio_features import feature_extractor_manifest_hash
from app.songprogram.evaluation_harness import _artifact_hash
from app.songprogram.genre_reference_intake import (
    GenreReferenceIntakeError,
    build_genre_reference_set,
)


BACKEND = Path(__file__).resolve().parents[1]


def _wav() -> bytes:
    stream = io.BytesIO()
    with wave.open(stream, "wb") as output:
        output.setparams((1, 4, 48000, 64, "NONE", "not compressed"))
        output.writeframes(struct.pack("<" + "i" * 64, *range(64)))
    return stream.getvalue()


def _extractor() -> dict:
    path = (
        BACKEND / "songprogram_conformance" / "profiles" / "pcm32_genre_feature_extractor_v1.json"
    )
    value = json.loads(path.read_text())
    value["segment_policy"]["frame_count"] = 64
    value["manifest_hash"] = feature_extractor_manifest_hash(value)
    return value


def _policy() -> dict:
    value = {
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
    }
    value["policy_hash"] = _artifact_hash(value, "policy_hash")
    return value


def _provenance(reference_id: str, policy: dict, payload: bytes) -> dict:
    value = {
        "schema": "cps.reference-source-provenance",
        "schema_version": "1.0.0",
        "reference_id": reference_id,
        "source_class": "internal",
        "source_locator_hash": "sha256:" + "01" * 32,
        "rights_basis": "owned",
        "license_policy_hash": policy["policy_hash"],
        "storage_allowed": True,
        "feature_extraction_allowed": True,
        "evaluation_allowed": True,
        "expiry_epoch_day": None,
        "revoked": False,
        "raw_audio_hash": "sha256:" + hashlib.sha256(payload).hexdigest(),
        "raw_audio_null_reason": None,
        "attribution_hash": None,
        "provenance_hash": "",
    }
    value["provenance_hash"] = _artifact_hash(value, "provenance_hash")
    return value


def test_reference_intake_builds_all_partitions_and_features() -> None:
    payload, policy = _wav(), _policy()
    sources = [
        (partition, _provenance(f"kfb_{partition}", policy, payload), payload)
        for partition in ("holdout", "calibration", "validation")
    ]
    manifest, records = build_genre_reference_set(
        reference_set_id="kawaii_future_bass_v1",
        evaluation_epoch_day=20000,
        extractor_manifest=_extractor(),
        license_policy=policy,
        sources=sources,
        license_policy_schema_hash="sha256:" + "02" * 32,
        source_provenance_schema_hash="sha256:" + "03" * 32,
    )
    assert [member["partition"] for member in manifest["members"]] == [
        "calibration",
        "validation",
        "holdout",
    ]
    assert [record["record_hash"] for record in records] == [
        member["feature_record_hash"] for member in manifest["members"]
    ]
    assert manifest["manifest_hash"] == _artifact_hash(manifest, "manifest_hash")


def test_reference_intake_rejects_expired_rights() -> None:
    payload, policy = _wav(), _policy()
    provenance = _provenance("expired", policy, payload)
    provenance["expiry_epoch_day"] = 20000
    provenance["provenance_hash"] = _artifact_hash(provenance, "provenance_hash")
    with pytest.raises(GenreReferenceIntakeError, match="GENRE_REFERENCE_RIGHTS_INELIGIBLE"):
        build_genre_reference_set(
            reference_set_id="kawaii_future_bass_v1",
            evaluation_epoch_day=20000,
            extractor_manifest=_extractor(),
            license_policy=policy,
            sources=[("calibration", provenance, payload)],
            license_policy_schema_hash="sha256:" + "02" * 32,
            source_provenance_schema_hash="sha256:" + "03" * 32,
        )
