"""Prepare rights artifacts and intake from an owner-approved local transfer."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path, PurePosixPath
from typing import Any, Mapping

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from app.songprogram.connected import canonical_lf  # noqa: E402
from app.songprogram.evaluation_harness import _artifact_hash  # noqa: E402


def _object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("GENRE_AUTHORITY_JSON_OBJECT_REQUIRED")
    return value


def _sha(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _relative_clip(root: Path, value: Any) -> tuple[str, Path]:
    if not isinstance(value, str):
        raise ValueError("GENRE_AUTHORITY_CLIP_PATH_INVALID")
    pure = PurePosixPath(value)
    if pure.is_absolute() or ".." in pure.parts or len(pure.parts) != 3 or pure.parts[0] != "clips":
        raise ValueError("GENRE_AUTHORITY_CLIP_PATH_INVALID")
    path = root.joinpath(*pure.parts)
    if not path.is_file():
        raise ValueError("GENRE_AUTHORITY_CLIP_MISSING")
    return value, path


def prepare(
    root: Path,
    *,
    reference_set_id: str,
    issued_epoch_day: int,
) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    transfer_path = root / "transfer_manifest.json"
    transfer = _object(transfer_path)
    entries = transfer.get("entries")
    if (
        transfer.get("set_id") != reference_set_id
        or not isinstance(entries, list)
        or not entries
        or type(issued_epoch_day) is not int
        or issued_epoch_day < 0
    ):
        raise ValueError("GENRE_AUTHORITY_TRANSFER_INVALID")
    grant = {
        "schema": "cps.genre-reference-rights-grant",
        "schema_version": "1.0.0",
        "reference_set_id": reference_set_id,
        "transfer_manifest_hash": _sha(transfer_path.read_bytes()),
        "grantor_role": "asset_owner",
        "source_class": "user_supplied",
        "rights_basis": "user_supplied_explicit_grant",
        "storage_allowed": True,
        "feature_extraction_allowed": True,
        "evaluation_allowed": True,
        "expiry_epoch_day": None,
        "revoked": False,
        "attribution_required": False,
        "issued_epoch_day": issued_epoch_day,
        "grant_hash": "",
    }
    grant["grant_hash"] = _artifact_hash(grant, "grant_hash")
    policy = {
        "schema": "cps.genre-license-policy",
        "schema_version": "1.0.0",
        "allowed_rights_bases": ["user_supplied_explicit_grant"],
        "require_storage_right": True,
        "require_feature_extraction_right": True,
        "require_evaluation_right": True,
        "expiry_policy": "reject_at_or_after_expiry/v1",
        "revocation_policy": "reject_revoked/v1",
        "raw_audio_null_policy": "eligible_only_with_feature_record_and_verified_nonretention_grant/v1",
        "policy_hash": "",
    }
    policy["policy_hash"] = _artifact_hash(policy, "policy_hash")
    order = {"calibration": 0, "validation": 1, "holdout": 2}
    normalized: list[tuple[int, bytes, Mapping[str, Any], str, Path]] = []
    seen: set[str] = set()
    for entry in entries:
        if not isinstance(entry, Mapping):
            raise ValueError("GENRE_AUTHORITY_TRANSFER_INVALID")
        identifier, partition = entry.get("id"), entry.get("partition")
        if (
            not isinstance(identifier, str)
            or identifier in seen
            or partition not in order
            or not isinstance(entry.get("receipt_sha256"), str)
        ):
            raise ValueError("GENRE_AUTHORITY_TRANSFER_INVALID")
        seen.add(identifier)
        relative, clip_path = _relative_clip(root, entry.get("clip_relative_path"))
        if _sha(clip_path.read_bytes()) != entry.get("clip_wav_sha256"):
            raise ValueError("GENRE_AUTHORITY_AUDIO_HASH_MISMATCH")
        normalized.append((order[partition], identifier.encode(), entry, relative, clip_path))
    normalized.sort(key=lambda row: (row[0], row[1]))
    provenances = []
    sources = []
    for _, _, entry, relative, _ in normalized:
        identifier = entry["id"]
        provenance = {
            "schema": "cps.reference-source-provenance",
            "schema_version": "1.0.0",
            "reference_id": identifier,
            "source_class": grant["source_class"],
            "source_locator_hash": entry["receipt_sha256"],
            "rights_basis": grant["rights_basis"],
            "license_policy_hash": policy["policy_hash"],
            "storage_allowed": grant["storage_allowed"],
            "feature_extraction_allowed": grant["feature_extraction_allowed"],
            "evaluation_allowed": grant["evaluation_allowed"],
            "expiry_epoch_day": grant["expiry_epoch_day"],
            "revoked": grant["revoked"],
            "raw_audio_hash": entry["clip_wav_sha256"],
            "raw_audio_null_reason": None,
            "attribution_hash": None,
            "provenance_hash": "",
        }
        provenance["provenance_hash"] = _artifact_hash(provenance, "provenance_hash")
        provenances.append(provenance)
        sources.append(
            {
                "partition": entry["partition"],
                "provenance": f"provenance/{identifier}.json",
                "wav": f"../{relative}",
            }
        )
    intake = {
        "reference_set_id": reference_set_id,
        "evaluation_epoch_day": issued_epoch_day,
        "sources": sources,
    }
    return grant, policy, provenances, intake


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--reference-set-id", required=True)
    parser.add_argument("--issued-epoch-day", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    try:
        grant, policy, provenances, intake = prepare(
            arguments.root,
            reference_set_id=arguments.reference_set_id,
            issued_epoch_day=arguments.issued_epoch_day,
        )
    except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as error:
        parser.error(str(error))
    arguments.output.mkdir(parents=True, exist_ok=True)
    provenance_directory = arguments.output / "provenance"
    provenance_directory.mkdir(parents=True, exist_ok=True)
    (arguments.output / "rights_grant.json").write_bytes(canonical_lf(grant))
    (arguments.output / "genre_license_policy.json").write_bytes(canonical_lf(policy))
    for provenance in provenances:
        (provenance_directory / f"{provenance['reference_id']}.json").write_bytes(
            canonical_lf(provenance)
        )
    (arguments.output / "reference_intake.json").write_bytes(canonical_lf(intake))
    summary = {
        "reference_set_id": arguments.reference_set_id,
        "grant_hash": grant["grant_hash"],
        "license_policy_hash": policy["policy_hash"],
        "source_count": len(provenances),
    }
    sys.stdout.buffer.write(canonical_lf(summary))


if __name__ == "__main__":
    main()
