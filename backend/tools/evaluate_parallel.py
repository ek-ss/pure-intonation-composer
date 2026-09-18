"""Evaluate one compiled Project through Native JI, PIL, and genre references."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from app.songprogram.connected import canonical_lf  # noqa: E402
from app.songprogram.evaluation_harness import (  # noqa: E402
    ParallelEvaluationError,
    evaluate_parallel,
)
from app.songprogram.native_ji import NativeJIError  # noqa: E402
from app.songprogram.perceptual import PilError  # noqa: E402


def _object(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--authority", type=Path, required=True)
    parser.add_argument("--candidate-genre-feature", type=Path, required=True)
    parser.add_argument("--cache-directory", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    for option, path in (
        ("--project", arguments.project),
        ("--authority", arguments.authority),
        ("--candidate-genre-feature", arguments.candidate_genre_feature),
    ):
        if not path.is_file():
            parser.error(f"{option} does not exist or is not a file: {path}")
    try:
        report = evaluate_parallel(
            _object(arguments.project),
            _object(arguments.authority),
            _object(arguments.candidate_genre_feature),
            cache_dir=None if arguments.cache_directory is None else str(arguments.cache_directory),
        )
    except (
        OSError,
        json.JSONDecodeError,
        ValueError,
        NativeJIError,
        PilError,
        ParallelEvaluationError,
    ) as error:
        code = getattr(error, "code", type(error).__name__)
        parser.error(str(code))
    arguments.output.mkdir(parents=True, exist_ok=True)
    outputs = {
        "parallel_evaluation_report.json": report,
        "native_ji_report.json": report["native_ji_report"],
        "pil_report.json": report["pil_report"],
        "pil_genre_results.json": report["pil_genre_results"],
    }
    for name, value in outputs.items():
        (arguments.output / name).write_bytes(canonical_lf(value))
    sys.stdout.buffer.write(canonical_lf(report))


if __name__ == "__main__":
    main()
