"""Prepare G1 diagnostics and G2 blind assignments for generated song cohorts."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
from pathlib import Path
from statistics import mean

BACKEND = Path(__file__).resolve().parents[1]
REPO = BACKEND.parent
sys.path.insert(0, str(BACKEND))

from app.songprogram.composition_calibration import build_blind_assignment, split_lineages  # noqa: E402
from app.songprogram.composition_viability import (  # noqa: E402
    composition_viability_report_hash, extract_composition_viability,
)
from app.songprogram.mutation import program_hash  # noqa: E402
from app.songprogram.perceptual import project_hash  # noqa: E402
from app.songprogram.search import canonical_bytes  # noqa: E402


def _load(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON object required: {path}")
    return value


def _sha(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _seal(value: dict, domain: str, member: str) -> dict:
    result = {**value, member: ""}
    result[member] = "sha256:" + hashlib.sha256(
        domain.encode() + b"\0" + canonical_bytes({k: v for k, v in result.items() if k != member})
    ).hexdigest()
    return result


def _candidate(label: str, directory: Path, seed: int, repository: Path) -> tuple[dict, dict]:
    program = _load(directory / "program.json")
    project = _load(directory / "project.json")
    receipt = _load(directory / "receipt.json")
    features = _load(directory / "g1_features.json")
    validity = _load(directory / "song_validity.json")
    audio = directory / "reference.wav"
    if not audio.is_file():
        audio = directory / "preview.wav"
    if not audio.is_file():
        raise ValueError(f"audio missing: {directory}")
    if (receipt.get("seed") != seed
            or receipt.get("program_hash") != program_hash(program)
            or receipt.get("project_hash") != project_hash(project)
            or receipt.get("wav_hash") != _sha(audio)
            or receipt.get("g1_feature_report_hash") != features.get("report_hash")
            or receipt.get("song_validity_hash") != validity.get("assessment_hash")
            or features.get("report_hash") != composition_viability_report_hash(features)
            or features != extract_composition_viability(program, project)
            or validity.get("archive_eligible") != receipt.get("archive_eligible")):
        raise ValueError(f"artifact binding mismatch: {directory}")
    source = audio.resolve()
    if not source.is_relative_to(repository / "local_authority"):
        raise ValueError(f"audio must be under local_authority: {audio}")
    candidate = {
        "candidate_id": f"{label}-seed-{seed:04d}",
        # Variants of the same seed cannot cross calibration/holdout.
        "lineage_id": f"generated-seed-{seed:04d}", "cohort": label,
        "audio_path": str(source.relative_to(repository)), "audio_hash": receipt["wav_hash"],
        "g1_feature_report_hash": features["report_hash"],
    }
    diagnostic = {
        "candidate_id": candidate["candidate_id"], "lineage_id": candidate["lineage_id"],
        "cohort": label, "seed": seed,
        "g0_archive_eligible": validity["archive_eligible"],
        "g0_failure_codes": validity["failure_codes"],
        "g1_metrics_q": features["metrics_q"],
        "g1_feature_report_hash": features["report_hash"],
    }
    return candidate, diagnostic


def prepare(
    cohorts: dict[str, Path], output: Path, *, seeds: int,
    assignment_seed: int = 0, calibration_basis_points: int = 7000,
    repository: Path = REPO,
) -> dict:
    repository = repository.resolve()
    output = output.resolve()
    if not output.is_relative_to(repository / "local_authority"):
        raise ValueError("output must be under local_authority for the blind audio API")
    if not cohorts or not 1 <= seeds <= 1000:
        raise ValueError("at least one cohort and 1..1000 seeds are required")
    candidates, diagnostics = [], []
    for label, root in sorted(cohorts.items()):
        if not label or not label.replace("_", "").replace("-", "").isalnum():
            raise ValueError(f"invalid cohort label: {label}")
        for seed in range(seeds):
            directory = root / f"seed-{seed:04d}"
            required = ("program.json", "project.json", "receipt.json", "g1_features.json",
                        "song_validity.json")
            if not all((directory / name).is_file() for name in required):
                raise ValueError(f"incomplete cohort, missing seed {seed}: {root}")
            candidate, diagnostic = _candidate(label, directory, seed, repository)
            candidates.append(candidate)
            diagnostics.append(diagnostic)
    split = split_lineages(candidates, calibration_basis_points=calibration_basis_points)
    g1 = {
        "schema": "cps.generated-song-g1-diagnostic", "schema_version": "1.0.0",
        "non_authoritative": True, "cohort_labels": sorted(cohorts), "seed_count": seeds,
        "candidates": diagnostics,
        "mean_metrics_by_cohort_q": {
            label: {key: round(mean(row["g1_metrics_q"][key] for row in diagnostics
                                    if row["cohort"] == label))
                    for key in diagnostics[0]["g1_metrics_q"]}
            for label in sorted(cohorts)
        },
        "g0_eligible_by_cohort": {
            label: sum(row["g0_archive_eligible"] for row in diagnostics
                       if row["cohort"] == label)
            for label in sorted(cohorts)
        },
    }
    g1 = _seal(g1, "cps.generated-song-g1-diagnostic/v1", "report_hash")
    assignments = {}
    audio_sources = {}
    for partition in ("calibration", "holdout"):
        assignment = build_blind_assignment(
            split, partition=partition, assignment_seed=assignment_seed
        )
        for row in assignment["assignments"]:
            source = repository / row["audio_path"]
            destination = output / "audio" / partition / f"{row['blind_id']}.wav"
            audio_sources[destination] = (source, row["audio_hash"])
            row["audio_path"] = str(destination.relative_to(repository))
        assignments[partition] = _seal(
            assignment, "cps.composition-blind-assignment/v1", "assignment_hash"
        )
    # Never overwrite an active listening assignment with a different hash.
    for partition, assignment in assignments.items():
        path = output / f"blind_{partition}.json"
        if path.exists() and _load(path) != assignment:
            raise ValueError(f"existing blind assignment differs: {path}")
    split_path = output / "private_lineage_split.json"
    if split_path.exists() and _load(split_path) != split:
        raise ValueError(f"existing private split differs: {split_path}")
    output.mkdir(parents=True, exist_ok=True)
    for destination, (source, expected_hash) in audio_sources.items():
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists():
            if _sha(destination) != expected_hash:
                raise ValueError(f"blind audio has changed: {destination}")
            continue
        try:
            os.link(source, destination)
        except OSError:
            shutil.copyfile(source, destination)
    (output / "g1_report.json").write_bytes(canonical_bytes(g1))
    split_path.write_bytes(canonical_bytes(split))
    for partition, assignment in assignments.items():
        (output / f"blind_{partition}.json").write_bytes(canonical_bytes(assignment))
    return {
        "g1_report_hash": g1["report_hash"],
        "candidates": len(candidates),
        "blind_calibration": len(assignments["calibration"]["assignments"]),
        "blind_holdout": len(assignments["holdout"]["assignments"]),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cohort", action="append", required=True, metavar="LABEL=DIRECTORY")
    parser.add_argument("--seeds", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--assignment-seed", type=int, default=0)
    parser.add_argument("--calibration-basis-points", type=int, default=7000)
    args = parser.parse_args()
    cohorts = {}
    for item in args.cohort:
        if "=" not in item:
            parser.error("--cohort must be LABEL=DIRECTORY")
        label, path = item.split("=", 1)
        if label in cohorts:
            parser.error(f"duplicate cohort label: {label}")
        cohorts[label] = Path(path)
    try:
        result = prepare(cohorts, args.output, seeds=args.seeds,
                         assignment_seed=args.assignment_seed,
                         calibration_basis_points=args.calibration_basis_points)
    except (ValueError, OSError, KeyError, json.JSONDecodeError) as error:
        parser.error(str(error))
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
