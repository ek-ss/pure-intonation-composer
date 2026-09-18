"""Measure duplicate and similarity spread of staged genre FeatureRecords."""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import sys
from collections import Counter
from pathlib import Path, PurePosixPath
from typing import Any

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from app.songprogram.connected import canonical_bytes, canonical_lf  # noqa: E402
from app.songprogram.evaluation_harness import genre_similarity_q  # noqa: E402


def _object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise ValueError("COHORT_AUDIT_JSON_OBJECT_REQUIRED")
    return value


def _percentile(values: list[int], numerator: int, denominator: int) -> int:
    ordered = sorted(values)
    return ordered[(len(ordered) - 1) * numerator // denominator]


def _indexed_record(root: Path, relative: Any) -> dict[str, Any]:
    if not isinstance(relative, str):
        raise ValueError("COHORT_AUDIT_PATH_INVALID")
    pure = PurePosixPath(relative)
    if (
        pure.is_absolute()
        or ".." in pure.parts
        or len(pure.parts) != 2
        or pure.parts[0] != "features"
    ):
        raise ValueError("COHORT_AUDIT_PATH_INVALID")
    return _object(root.joinpath(*pure.parts))


def audit(root: Path, captions_path: Path) -> dict[str, Any]:
    index = json.loads((root / "feature_index.json").read_text())
    captions = _object(captions_path)
    if not isinstance(index, list) or len(index) < 3:
        raise ValueError("COHORT_AUDIT_INDEX_INVALID")
    tracks = captions.get("tracks")
    if not isinstance(tracks, list):
        raise ValueError("COHORT_AUDIT_CAPTIONS_INVALID")
    partition_by_id = {
        row["id"]: row["partition"] for row in tracks if isinstance(row, dict) and "id" in row
    }
    if len(partition_by_id) != len(tracks):
        raise ValueError("COHORT_AUDIT_CAPTIONS_INVALID")
    rows = []
    seen: set[str] = set()
    for item in index:
        if not isinstance(item, dict):
            raise ValueError("COHORT_AUDIT_INDEX_INVALID")
        identifier = item["reference_id"]
        if identifier in seen or identifier not in partition_by_id:
            raise ValueError("COHORT_AUDIT_INDEX_INVALID")
        seen.add(identifier)
        record = _indexed_record(root, item["path"])
        if record["record_hash"] != item["feature_record_hash"]:
            raise ValueError("COHORT_AUDIT_INDEX_MISMATCH")
        rows.append((identifier, partition_by_id[identifier], record))
    if set(partition_by_id) != seen or set(partition_by_id.values()) != {
        "calibration",
        "validation",
        "holdout",
    }:
        raise ValueError("COHORT_AUDIT_PARTITION_INVALID")
    audio_hashes = Counter(record["source_audio_artifact_hash"] for _, _, record in rows)
    embeddings = Counter(tuple(record["embedding_q31"]) for _, _, record in rows)
    pairs = []
    pair_groups: dict[str, list[int]] = {}
    for left in range(len(rows)):
        for right in range(left + 1, len(rows)):
            left_id, left_partition, left_record = rows[left]
            right_id, right_partition, right_record = rows[right]
            score = genre_similarity_q(left_record, [right_record])
            key = "-".join(sorted((left_partition, right_partition)))
            pair_groups.setdefault(key, []).append(score)
            pairs.append((score, left_id, right_id))
    scores = [row[0] for row in pairs]
    diagnostics = []
    if len(audio_hashes) != len(rows):
        diagnostics.append("audio_hash_duplicates")
    if len(embeddings) != len(rows):
        diagnostics.append("embedding_duplicates")
    # Diagnostic only: not a calibration acceptance threshold.
    if min(scores) >= 9000:
        diagnostics.append("baseline_feature_separation_low")
    pair_summary = {
        key: {
            "pair_count": len(values),
            "minimum_q": min(values),
            "lower_quartile_q": _percentile(values, 1, 4),
            "median_q": _percentile(values, 1, 2),
            "upper_quartile_q": _percentile(values, 3, 4),
            "maximum_q": max(values),
            "mean_q": round(statistics.mean(values)),
        }
        for key, values in sorted(pair_groups.items())
    }
    report = {
        "schema": "cps.genre-feature-cohort-audit",
        "schema_version": "1.0.0",
        "set_id": captions["set_id"],
        "record_count": len(rows),
        "partition_counts": dict(sorted(Counter(row[1] for row in rows).items())),
        "unique_audio_hash_count": len(audio_hashes),
        "unique_embedding_count": len(embeddings),
        "pair_summary": pair_summary,
        "closest_pairs": [
            {"left_id": left, "right_id": right, "similarity_q": score}
            for score, left, right in sorted(pairs, key=lambda row: (-row[0], row[1], row[2]))[:10]
        ],
        "farthest_pairs": [
            {"left_id": left, "right_id": right, "similarity_q": score}
            for score, left, right in sorted(pairs, key=lambda row: (row[0], row[1], row[2]))[:10]
        ],
        "diagnostic_only": True,
        "diagnostics": diagnostics,
        "report_hash": "",
    }
    report["report_hash"] = (
        "sha256:"
        + hashlib.sha256(
            b"cps.genre-feature-cohort-audit/v1\0"
            + canonical_bytes({key: value for key, value in report.items() if key != "report_hash"})
        ).hexdigest()
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--features", type=Path, required=True)
    parser.add_argument("--captions", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    try:
        report = audit(arguments.features, arguments.captions)
    except (OSError, json.JSONDecodeError, KeyError, ValueError) as error:
        parser.error(str(error))
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_bytes(canonical_lf(report))
    sys.stdout.buffer.write(canonical_lf(report))


if __name__ == "__main__":
    main()
