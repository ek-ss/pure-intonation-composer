"""Create a lineage-safe split and label-free G2 listening assignment."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from app.songprogram.composition_calibration import (  # noqa: E402
    build_blind_assignment,
    split_lineages,
)
from app.songprogram.search import canonical_bytes  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidates", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--calibration-basis-points", type=int, default=7000)
    parser.add_argument("--assignment-seed", type=int, default=0)
    arguments = parser.parse_args()
    source = json.loads(arguments.candidates.read_text(encoding="utf-8"))
    split = split_lineages(
        source["candidates"], calibration_basis_points=arguments.calibration_basis_points
    )
    arguments.output.mkdir(parents=True, exist_ok=True)
    (arguments.output / "lineage_split.json").write_bytes(canonical_bytes(split))
    for partition in ("calibration", "holdout"):
        assignment = build_blind_assignment(
            split, partition=partition, assignment_seed=arguments.assignment_seed
        )
        (arguments.output / f"blind_{partition}.json").write_bytes(
            canonical_bytes(assignment)
        )


if __name__ == "__main__":
    main()
