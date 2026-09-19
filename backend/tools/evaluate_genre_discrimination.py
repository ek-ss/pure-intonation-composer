"""Evaluate a staged positive/negative genre FeatureRecord cohort."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path, PurePosixPath
from typing import Any

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from app.songprogram.connected import canonical_lf  # noqa: E402
from app.songprogram.genre_discrimination import evaluate_genre_discrimination  # noqa: E402


def _object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("GENRE_DISCRIMINATION_JSON_OBJECT_REQUIRED")
    return value


def _load(root: Path, captions_path: Path) -> tuple[str, dict[str, list[dict[str, Any]]]]:
    captions = _object(captions_path)
    tracks = captions.get("tracks")
    index = json.loads((root / "feature_index.json").read_text(encoding="utf-8"))
    if not isinstance(tracks, list) or not isinstance(index, list):
        raise ValueError("GENRE_DISCRIMINATION_INPUT_INVALID")
    partition_by_id = {row["id"]: row["partition"] for row in tracks if isinstance(row, dict)}
    if len(partition_by_id) != len(tracks) or len(index) != len(tracks):
        raise ValueError("GENRE_DISCRIMINATION_INPUT_INVALID")
    result: dict[str, list[dict[str, Any]]] = {
        "calibration": [],
        "validation": [],
        "holdout": [],
    }
    seen = set()
    for item in index:
        if not isinstance(item, dict):
            raise ValueError("GENRE_DISCRIMINATION_INPUT_INVALID")
        identifier, relative = item.get("reference_id"), item.get("path")
        pure = PurePosixPath(relative) if isinstance(relative, str) else PurePosixPath("/")
        if (
            identifier in seen
            or identifier not in partition_by_id
            or pure.is_absolute()
            or ".." in pure.parts
            or len(pure.parts) != 2
            or pure.parts[0] != "features"
        ):
            raise ValueError("GENRE_DISCRIMINATION_INPUT_INVALID")
        seen.add(identifier)
        record = _object(root.joinpath(*pure.parts))
        if record.get("record_hash") != item.get("feature_record_hash"):
            raise ValueError("GENRE_DISCRIMINATION_INDEX_MISMATCH")
        result[partition_by_id[identifier]].append(record)
    if seen != set(partition_by_id):
        raise ValueError("GENRE_DISCRIMINATION_INPUT_INVALID")
    return captions["set_id"], result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--positive-features", type=Path, required=True)
    parser.add_argument("--positive-captions", type=Path, required=True)
    parser.add_argument("--negative-features", type=Path, required=True)
    parser.add_argument("--negative-captions", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    try:
        positive_id, positive = _load(arguments.positive_features, arguments.positive_captions)
        negative_id, negative = _load(arguments.negative_features, arguments.negative_captions)
        report = evaluate_genre_discrimination(
            positive_set_id=positive_id,
            negative_set_id=negative_id,
            positive=positive,
            negative=negative,
        )
    except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as error:
        parser.error(str(error))
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_bytes(canonical_lf(report))
    sys.stdout.buffer.write(canonical_lf(report))


if __name__ == "__main__":
    main()
