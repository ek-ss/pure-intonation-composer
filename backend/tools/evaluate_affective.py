"""Evaluate the symbolic affect layer without invoking Native JI or PIL."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from app.songprogram.affective import evaluate_affective  # noqa: E402
from app.songprogram.search import canonical_bytes  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True, type=Path)
    parser.add_argument(
        "--manifest",
        type=Path,
        default=BACKEND / "songprogram_conformance" / "profiles" / "affective_interpretation_v1.json",
    )
    parser.add_argument("--output", required=True, type=Path)
    arguments = parser.parse_args()
    project = json.loads(arguments.project.read_text(encoding="utf-8"))
    manifest = json.loads(arguments.manifest.read_text(encoding="utf-8"))
    report = evaluate_affective(project, manifest)
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_bytes(canonical_bytes(report))
    print(report["report_hash"])


if __name__ == "__main__":
    main()
