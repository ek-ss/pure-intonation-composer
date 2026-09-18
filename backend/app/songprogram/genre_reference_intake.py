"""Rights-aware construction of genre reference manifests and features."""

from __future__ import annotations

import hashlib
from typing import Any, Mapping, Sequence

from .audio_features import extract_genre_feature_record
from .compiler import _canonical


class GenreReferenceIntakeError(ValueError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def _artifact_hash(value: Mapping[str, Any], member: str) -> str:
    body = {key: item for key, item in value.items() if key != member}
    prefix = (f"cps-artifact-hash/v1\0{value['schema']}\0{value['schema_version']}\0").encode()
    return "sha256:" + hashlib.sha256(prefix + _canonical(body)).hexdigest()


def build_genre_reference_set(
    *,
    reference_set_id: str,
    evaluation_epoch_day: int,
    extractor_manifest: Mapping[str, Any],
    license_policy: Mapping[str, Any],
    sources: Sequence[tuple[str, Mapping[str, Any], bytes]],
    license_policy_schema_hash: str,
    source_provenance_schema_hash: str,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Return a sealed ReferenceSetManifest and ordered FeatureRecords."""
    if (
        license_policy.get("schema") != "cps.genre-license-policy"
        or license_policy.get("schema_version") != "1.0.0"
        or license_policy.get("policy_hash") != _artifact_hash(license_policy, "policy_hash")
        or type(evaluation_epoch_day) is not int
        or evaluation_epoch_day < 0
    ):
        raise GenreReferenceIntakeError("GENRE_LICENSE_POLICY_INVALID")
    rows: list[tuple[str, dict[str, Any], dict[str, Any]]] = []
    seen: set[str] = set()
    allowed = set(license_policy.get("allowed_rights_bases", []))
    for partition, provenance, wav_payload in sources:
        if partition not in {"calibration", "validation", "holdout"}:
            raise GenreReferenceIntakeError("GENRE_REFERENCE_PARTITION_INVALID")
        reference_id = provenance.get("reference_id")
        if not isinstance(reference_id, str) or reference_id in seen:
            raise GenreReferenceIntakeError("GENRE_REFERENCE_ID_INVALID")
        seen.add(reference_id)
        if (
            provenance.get("schema") != "cps.reference-source-provenance"
            or provenance.get("schema_version") != "1.0.0"
            or provenance.get("provenance_hash") != _artifact_hash(provenance, "provenance_hash")
            or provenance.get("license_policy_hash") != license_policy.get("policy_hash")
            or provenance.get("rights_basis") not in allowed
            or provenance.get("storage_allowed") is not True
            or provenance.get("feature_extraction_allowed") is not True
            or provenance.get("evaluation_allowed") is not True
            or provenance.get("revoked") is not False
            or (
                provenance.get("expiry_epoch_day") is not None
                and evaluation_epoch_day >= provenance["expiry_epoch_day"]
            )
        ):
            raise GenreReferenceIntakeError("GENRE_REFERENCE_RIGHTS_INELIGIBLE")
        raw_hash = "sha256:" + hashlib.sha256(wav_payload).hexdigest()
        if provenance.get("raw_audio_hash") != raw_hash:
            raise GenreReferenceIntakeError("GENRE_REFERENCE_AUDIO_HASH_MISMATCH")
        record = extract_genre_feature_record(wav_payload, extractor_manifest)
        rows.append((partition, dict(provenance), record))
    if not rows:
        raise GenreReferenceIntakeError("GENRE_REFERENCE_SET_EMPTY")
    partitions = {row[0] for row in rows}
    if partitions != {"calibration", "validation", "holdout"}:
        raise GenreReferenceIntakeError("GENRE_REFERENCE_PARTITIONS_INCOMPLETE")
    order = {"calibration": 0, "validation": 1, "holdout": 2}
    rows.sort(key=lambda row: (order[row[0]], row[1]["reference_id"].encode()))
    members = [
        {
            "reference_id": provenance["reference_id"],
            "partition": partition,
            "source_provenance_hash": provenance["provenance_hash"],
            "feature_record_hash": record["record_hash"],
            "raw_audio_hash": provenance["raw_audio_hash"],
        }
        for partition, provenance, record in rows
    ]
    manifest = {
        "schema": "cps.genre-reference-set-manifest",
        "schema_version": "1.0.0",
        "reference_set_id": reference_set_id,
        "feature_extractor_manifest_hash": extractor_manifest["manifest_hash"],
        "license_policy_hash": license_policy["policy_hash"],
        "license_policy_schema_hash": license_policy_schema_hash,
        "source_provenance_schema_hash": source_provenance_schema_hash,
        "members": members,
        "manifest_hash": "",
    }
    manifest["manifest_hash"] = _artifact_hash(manifest, "manifest_hash")
    return manifest, [record for _, _, record in rows]
