"""Render deterministic destructive G1 negatives from a generated positive cohort."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from app.songprogram.composition_viability import extract_composition_viability  # noqa: E402
from app.songprogram.perceptual import project_hash  # noqa: E402
from app.songprogram.renderer import render_reference  # noqa: E402
from app.songprogram.search import canonical_bytes  # noqa: E402
from tools.run_fixture_generation_cohort import RENDER_FIXTURE, _trial_catalog  # noqa: E402

NEGATIVE_TYPES = (
    "remove_foreground",
    "remove_groove",
    "desync_bass",
    "middle_silence",
    "truncate_ending",
    "flatten_dynamics",
)


def _transform(project: dict, negative_type: str) -> None:
    roles = {track["id"]: track["role"] for track in project["tracks"]}
    sections = project["form"]
    if negative_type == "remove_foreground":
        project["events"] = [event for event in project["events"] if roles[event["track_id"]] != "melody"]
    elif negative_type == "remove_groove":
        project["events"] = [event for event in project["events"] if roles[event["track_id"]] != "drums"]
    elif negative_type == "desync_bass":
        shift = project["clock"]["ticks_per_beat"] // 2
        for event in project["events"]:
            if roles[event["track_id"]] == "bass":
                event["start_tick"] += shift
    elif negative_type == "middle_silence":
        removed = {section["id"] for section in sections[len(sections) // 3 : 2 * len(sections) // 3]}
        project["events"] = [event for event in project["events"] if event["section_id"] not in removed]
    elif negative_type == "truncate_ending":
        removed = sections[-1]["id"]
        project["events"] = [event for event in project["events"] if event["section_id"] != removed]
    elif negative_type == "flatten_dynamics":
        for event in project["events"]:
            event["velocity"] = 48
    else:
        raise ValueError("NEGATIVE_TYPE_UNKNOWN")


def _generate_one(task: tuple[dict, str, int, str, str]) -> dict:
    source, negative_type, ordinal, generation_manifest_path, output = task
    source_directory = Path(source["artifact_directory"])
    program = json.loads((source_directory / "program.json").read_text())
    project = json.loads((source_directory / "project.json").read_text())
    _transform(project, negative_type)
    generation_manifest = json.loads(Path(generation_manifest_path).read_text(encoding="utf-8"))
    _, catalog_bytes, _, assets = _trial_catalog(generation_manifest)
    render_manifest = json.loads((RENDER_FIXTURE / "render_manifest.json").read_text())
    rendered = render_reference(
        project,
        catalog_bytes,
        assets.__getitem__,
        render_manifest_digest=render_manifest["render_manifest_digest"],
        project_artifact_hash=project_hash(project),
    )
    features = extract_composition_viability(program, project)
    directory = Path(output) / negative_type / f"item-{ordinal:02d}"
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "project.json").write_bytes(canonical_bytes(project))
    (directory / "g1_features.json").write_bytes(canonical_bytes(features))
    (directory / "preview.wav").write_bytes(rendered.wav)
    return {
        "candidate_id": f"negative-{negative_type}-{ordinal:02d}",
        "lineage_id": source["lineage_id"],
        "negative_type": negative_type,
        "source_seed": source["seed"],
        "source_project_hash": source["receipt"]["project_hash"],
        "project_hash": project_hash(project),
        "audio_path": str(directory / "preview.wav"),
        "audio_hash": rendered.report["wav_hash"],
        "g1_feature_report_hash": features["report_hash"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-cohort", type=Path, required=True)
    parser.add_argument("--per-type", type=int, default=8)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--generation-manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    if not 8 <= arguments.per_type <= 12:
        parser.error("--per-type must be between 8 and 12")
    source_rows = json.loads(
        (arguments.source_cohort / "cohort_report.json").read_text(encoding="utf-8")
    )["rows"]
    source_rows = [row for row in source_rows if row["status"] == "success"]
    if len(source_rows) < arguments.per_type:
        parser.error("source cohort has too few successful candidates")
    tasks = [
        (source, negative_type, ordinal, str(arguments.generation_manifest), str(arguments.output))
        for negative_type in NEGATIVE_TYPES
        for ordinal, source in enumerate(source_rows[: arguments.per_type])
    ]
    with ProcessPoolExecutor(max_workers=arguments.workers) as executor:
        rows = list(executor.map(_generate_one, tasks))
    report = {
        "schema": "cps.composition-destructive-negative-cohort",
        "schema_version": "1.0.0",
        "per_type": arguments.per_type,
        "negative_types": list(NEGATIVE_TYPES),
        "rows": rows,
        "report_hash": "",
    }
    report["report_hash"] = "sha256:" + hashlib.sha256(
        b"cps.composition-destructive-negative-cohort/v1\0"
        + canonical_bytes({key: value for key, value in report.items() if key != "report_hash"})
    ).hexdigest()
    arguments.output.mkdir(parents=True, exist_ok=True)
    (arguments.output / "cohort_report.json").write_bytes(canonical_bytes(report))
    print(json.dumps({"count": len(rows), "report_hash": report["report_hash"]}))


if __name__ == "__main__":
    main()
