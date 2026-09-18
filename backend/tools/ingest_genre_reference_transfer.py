"""Audit an ACE-Step reference transfer and extract staged FeatureRecords."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import wave
from collections import Counter
from pathlib import Path, PurePosixPath
from typing import Any

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from app.songprogram.audio_features import extract_genre_feature_record  # noqa: E402
from app.songprogram.connected import canonical_bytes, canonical_lf  # noqa: E402


class TransferError(ValueError):
    pass


def _object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TransferError("TRANSFER_JSON_OBJECT_REQUIRED")
    return value


def _sha(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _resolved(root: Path, relative: Any, prefix: str) -> Path:
    if not isinstance(relative, str):
        raise TransferError("TRANSFER_PATH_INVALID")
    pure = PurePosixPath(relative)
    if pure.is_absolute() or ".." in pure.parts or not pure.parts or pure.parts[0] != prefix:
        raise TransferError("TRANSFER_PATH_INVALID")
    path = root.joinpath(*pure.parts)
    if not path.is_file():
        raise TransferError("TRANSFER_FILE_MISSING")
    return path


def ingest(
    root: Path, caption_path: Path, extractor_manifest_path: Path
) -> tuple[dict[str, Any], list[tuple[str, dict[str, Any]]]]:
    transfer_path = root / "transfer_manifest.json"
    transfer, captions = _object(transfer_path), _object(caption_path)
    extractor = _object(extractor_manifest_path)
    if transfer.get("set_id") != captions.get("set_id"):
        raise TransferError("TRANSFER_SET_ID_MISMATCH")
    entries, tracks = transfer.get("entries"), captions.get("tracks")
    if not isinstance(entries, list) or not isinstance(tracks, list) or len(entries) != len(tracks):
        raise TransferError("TRANSFER_CARDINALITY_MISMATCH")
    by_id = {track.get("id"): track for track in tracks if isinstance(track, dict)}
    if len(by_id) != len(tracks):
        raise TransferError("TRANSFER_CAPTION_ID_INVALID")
    failures: list[dict[str, str]] = []
    extracted: list[tuple[str, dict[str, Any]]] = []
    seen: set[str] = set()
    partition_counts: Counter[str] = Counter()
    for entry in entries:
        if not isinstance(entry, dict):
            failures.append({"id": "unknown", "code": "TRANSFER_ENTRY_INVALID"})
            continue
        try:
            identifier, partition = entry["id"], entry["partition"]
            if identifier in seen or partition not in {"calibration", "validation", "holdout"}:
                raise TransferError("TRANSFER_ENTRY_ID_INVALID")
            seen.add(identifier)
            track = by_id.get(identifier)
            if track is None or track.get("partition") != partition:
                raise TransferError("TRANSFER_CAPTION_BINDING_MISMATCH")
            master = _resolved(root, entry["master_relative_path"], "masters")
            clip = _resolved(root, entry["clip_relative_path"], "clips")
            receipt_path = _resolved(root, entry["receipt_relative_path"], "receipts")
            receipt_bytes = receipt_path.read_bytes()
            if (
                _sha(master.read_bytes()) != entry["master_wav_sha256"]
                or _sha(clip.read_bytes()) != entry["clip_wav_sha256"]
                or _sha(receipt_bytes) != entry["receipt_sha256"]
            ):
                raise TransferError("TRANSFER_HASH_MISMATCH")
            receipt = json.loads(receipt_bytes)
            if not isinstance(receipt, dict):
                raise TransferError("TRANSFER_RECEIPT_INVALID")
            for key in ("seed", "caption", "lyrics", "bpm", "keyscale"):
                if receipt.get(key) != track.get(key):
                    raise TransferError("TRANSFER_RECEIPT_BINDING_MISMATCH")
            if (
                receipt.get("id") != identifier
                or receipt.get("partition") != partition
                or receipt.get("master_wav_sha256") != entry["master_wav_sha256"]
                or receipt.get("clip_wav_sha256") != entry["clip_wav_sha256"]
            ):
                raise TransferError("TRANSFER_RECEIPT_BINDING_MISMATCH")
            with wave.open(str(clip), "rb") as source:
                observed = {
                    "frame_count": source.getnframes(),
                    "sample_rate": source.getframerate(),
                    "channels": source.getnchannels(),
                    "pcm_format": "PCM_32" if source.getsampwidth() == 4 else "INVALID",
                }
            if any(entry.get(key) != value for key, value in observed.items()):
                raise TransferError("TRANSFER_AUDIO_METADATA_MISMATCH")
            record = extract_genre_feature_record(clip.read_bytes(), extractor)
            if record["source_audio_artifact_hash"] != entry["clip_wav_sha256"]:
                raise TransferError("TRANSFER_FEATURE_BINDING_MISMATCH")
            extracted.append((identifier, record))
            partition_counts[partition] += 1
        except (KeyError, OSError, json.JSONDecodeError, ValueError, wave.Error) as error:
            failures.append({"id": str(entry.get("id", "unknown")), "code": str(error)})
    status = "passed" if not failures else "failed"
    report = {
        "schema": "cps.genre-reference-transfer-ingest-report",
        "schema_version": "1.0.0",
        "set_id": transfer.get("set_id"),
        "transfer_manifest_sha256": _sha(transfer_path.read_bytes()),
        "caption_set_sha256": _sha(caption_path.read_bytes()),
        "feature_extractor_manifest_hash": extractor.get("manifest_hash"),
        "entry_count": len(entries),
        "partition_counts": dict(sorted(partition_counts.items())),
        "feature_record_count": len(extracted),
        "status": status,
        "authority_status": "staged_pending_rights_and_calibration",
        "failures": failures,
        "report_hash": "",
    }
    report["report_hash"] = _sha(
        b"cps.genre-reference-transfer-ingest-report/v1\0"
        + canonical_bytes({key: value for key, value in report.items() if key != "report_hash"})
    )
    if failures:
        raise TransferError("TRANSFER_INGEST_FAILED:" + canonical_bytes(report).decode())
    extracted.sort(key=lambda item: item[0].encode())
    return report, extracted


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--captions", type=Path, required=True)
    parser.add_argument("--extractor-manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    try:
        report, records = ingest(arguments.root, arguments.captions, arguments.extractor_manifest)
    except (OSError, json.JSONDecodeError, ValueError) as error:
        parser.error(str(error))
    arguments.output.mkdir(parents=True, exist_ok=True)
    feature_directory = arguments.output / "features"
    feature_directory.mkdir(parents=True, exist_ok=True)
    index = []
    for identifier, record in records:
        relative = f"features/{identifier}.json"
        (arguments.output / relative).write_bytes(canonical_lf(record))
        index.append(
            {
                "reference_id": identifier,
                "feature_record_hash": record["record_hash"],
                "path": relative,
            }
        )
    (arguments.output / "feature_index.json").write_bytes(canonical_lf(index))
    (arguments.output / "ingest_report.json").write_bytes(canonical_lf(report))
    sys.stdout.buffer.write(canonical_lf(report))


if __name__ == "__main__":
    main()
