"""Assemble old/new/negative symbolic candidates for lineage-safe G1/G2 calibration."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from app.songprogram.search import canonical_bytes  # noqa: E402


def _feature_hash(directory: Path) -> str:
    return json.loads((directory / "g1_features.json").read_text())["report_hash"]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--old-cohort", type=Path, required=True)
    parser.add_argument("--new-cohort", type=Path, required=True)
    parser.add_argument("--negative-cohort", type=Path, required=True)
    parser.add_argument("--ceiling-manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    candidates = []
    old = json.loads((arguments.old_cohort / "cohort_report.json").read_text())
    for row in old["rows"]:
        if row["status"] != "success":
            continue
        directory = arguments.old_cohort / f"seed-{row['seed']:04d}"
        candidates.append(
            {
                "candidate_id": f"old-seed-{row['seed']:04d}",
                "lineage_id": f"old-seed-{row['seed']:04d}",
                "cohort": "old_generator",
                "audio_path": str(directory / "preview.wav"),
                "audio_hash": row["wav_hash"],
                "g1_feature_report_hash": _feature_hash(directory),
            }
        )
    new = json.loads((arguments.new_cohort / "cohort_report.json").read_text())
    for row in new["rows"]:
        if row["status"] != "success":
            continue
        directory = Path(row["artifact_directory"])
        candidates.append(
            {
                "candidate_id": f"new-seed-{row['seed']:04d}",
                "lineage_id": row["lineage_id"],
                "cohort": "new_generator",
                "audio_path": str(directory / "preview.wav"),
                "audio_hash": row["receipt"]["wav_hash"],
                "g1_feature_report_hash": row["receipt"]["g1_feature_report_hash"],
            }
        )
    negatives = json.loads((arguments.negative_cohort / "cohort_report.json").read_text())
    for row in negatives["rows"]:
        candidates.append(
            {
                "candidate_id": row["candidate_id"],
                "lineage_id": row["lineage_id"],
                "cohort": f"negative:{row['negative_type']}",
                "audio_path": row["audio_path"],
                "audio_hash": row["audio_hash"],
                "g1_feature_report_hash": row["g1_feature_report_hash"],
            }
        )
    ceiling = json.loads(arguments.ceiling_manifest.read_text())
    for row in ceiling["entries"]:
        candidates.append(
            {
                "candidate_id": row["candidate_id"],
                "lineage_id": row["lineage_id"],
                "cohort": "ceiling_reference",
                "audio_path": row["audio_path"],
                "audio_hash": row["audio_hash"],
            }
        )
    result = {
        "schema": "cps.composition-calibration-candidates",
        "schema_version": "1.0.0",
        "candidates": sorted(candidates, key=lambda row: row["candidate_id"]),
        "catalog_hash": "",
    }
    result["catalog_hash"] = "sha256:" + hashlib.sha256(
        b"cps.composition-calibration-candidates/v1\0"
        + canonical_bytes({key: value for key, value in result.items() if key != "catalog_hash"})
    ).hexdigest()
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_bytes(canonical_bytes(result))
    print(json.dumps({"count": len(candidates), "catalog_hash": result["catalog_hash"]}))


if __name__ == "__main__":
    main()
