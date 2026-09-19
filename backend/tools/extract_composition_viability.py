"""Extract a non-authoritative G1 feature report from Program and Project JSON."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from app.songprogram.composition_viability import extract_composition_viability  # noqa: E402
from app.songprogram.search import canonical_bytes  # noqa: E402


def _object(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--program", type=Path, required=True)
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    try:
        report = extract_composition_viability(
            _object(arguments.program), _object(arguments.project)
        )
    except (OSError, json.JSONDecodeError, ValueError) as error:
        parser.error(str(error))
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_bytes(canonical_bytes(report))
    sys.stdout.buffer.write(canonical_bytes(report) + b"\n")


if __name__ == "__main__":
    main()
