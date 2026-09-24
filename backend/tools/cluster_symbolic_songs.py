"""Cluster successfully compiled WAV-free songs and select real Project medoids."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
REPO = BACKEND.parent
sys.path.insert(0, str(BACKEND))

from app.songprogram.composition_viability import extract_composition_viability  # noqa: E402
from app.songprogram.lattice_pitch_diagnostic import lattice_pitch_diagnostic  # noqa: E402
from app.songprogram.mutation import program_hash  # noqa: E402
from app.songprogram.perceptual import project_hash  # noqa: E402
from app.songprogram.search import canonical_bytes  # noqa: E402
from tools.cluster_section_seed_plans import cluster, distance, features as plan_features  # noqa: E402

ROLES = ("drums", "bass", "harmony", "melody", "texture", "piano")
G1_KEYS = ("audible_motif_recurrence_q", "motif_development_distance_q",
           "harmonic_motion_q", "groove_distribution_q", "section_contrast_q",
           "adjacent_section_continuity_q", "part_coordination_q", "foreground_presence_q")


def features(plan: dict, project: dict, g1: dict, lattice: dict) -> dict:
    result = plan_features(plan)
    tracks = {track["id"]: track["role"] for track in project["tracks"]}
    clock = project["clock"]
    bar = clock["ticks_per_beat"] * clock["beats_per_bar"]
    events = [event for event in project["events"] if event["kind"] in {"note", "drum"}]
    section_ids = [section["section_id"] for section in plan["sections"]]
    result["sounded_roles_by_section"] = [sorted({tracks[event["track_id"]] for event in events
                                                  if event["section_id"] == section_id})
                                         for section_id in section_ids]
    result["onset_share_by_role"] = {}
    result["events_per_bar_by_role_q"] = {}
    for role in ROLES:
        rows = [event for event in events if tracks[event["track_id"]] == role]
        bins = Counter((event["start_tick"] % bar) * 16 // bar for event in rows)
        result["onset_share_by_role"][role] = [round(10000 * bins[index] / len(rows)) if rows else 0
                                               for index in range(16)]
        result["events_per_bar_by_role_q"][role] = round(
            1000 * len(rows) / plan["total_bars"]
        )
    chords = {chord["id"]: chord for chord in project["resolved_chords"]}
    occurrences = project["harmony_occurrences"]
    counts = Counter(len(chords[row["resolved_chord_id"]]["voice_offsets"]) for row in occurrences)
    result["four_voice_share_q"] = round(10000 * counts[4] / len(occurrences)) if occurrences else 0
    result["distinct_resolved_chords_q"] = round(1000 * len(chords) / max(1, len(occurrences)))
    result["lattice_exposure_q"] = lattice["exposed_duration_share_q"]
    result["lattice_mean_gap_millicents"] = lattice["duration_weighted_mean_gap_millicents"]
    result["g1_metrics_q"] = {key: g1["metrics_q"][key] for key in G1_KEYS}
    return result


def distance_symbolic(left: dict, right: dict) -> float:
    base = distance(left, right)
    masks = sum(len(set(a) ^ set(b)) / len(ROLES)
                for a, b in zip(left["sounded_roles_by_section"], right["sounded_roles_by_section"]))
    masks /= max(1, max(len(left["sounded_roles_by_section"]), len(right["sounded_roles_by_section"])))
    onset = sum(abs(a - b) for role in ROLES
                for a, b in zip(left["onset_share_by_role"][role], right["onset_share_by_role"][role])) / (10000 * len(ROLES))
    density = sum(abs(left["events_per_bar_by_role_q"][role] - right["events_per_bar_by_role_q"][role])
                  for role in ROLES) / (4000 * len(ROLES))
    harmony = (abs(left["four_voice_share_q"] - right["four_voice_share_q"]) / 10000
               + abs(left["distinct_resolved_chords_q"] - right["distinct_resolved_chords_q"]) / 1000)
    lattice = (abs(left["lattice_exposure_q"] - right["lattice_exposure_q"]) / 10000
               + abs(left["lattice_mean_gap_millicents"] - right["lattice_mean_gap_millicents"]) / 50000)
    g1 = sum(abs(left["g1_metrics_q"][key] - right["g1_metrics_q"][key])
             for key in G1_KEYS) / (10000 * len(G1_KEYS))
    return base + 2 * masks + onset + density + harmony + lattice + g1


def _read(directory: Path) -> dict:
    return json.loads(directory.read_text())


def run(cohort: Path, output: Path, *, clusters: int = 16) -> dict:
    rows, failures = [], []
    cohort_report_path = cohort / "cohort_report.json"
    cohort_report = _read(cohort_report_path) if cohort_report_path.is_file() else None
    generation_failures = ([{"seed": item["seed"], "error": item["error"].splitlines()[-1]}
                            for item in cohort_report["rows"] if item["status"] == "failed"]
                           if cohort_report is not None else [])
    for directory in sorted(cohort.glob("seed-*")):
        if not directory.is_dir():
            continue
        seed = int(directory.name.removeprefix("seed-"))
        if not (directory / "receipt.json").is_file():
            continue
        receipt = _read(directory / "receipt.json")
        plan = _read(directory / "composition_plan.json")
        program = _read(directory / "program.json")
        project = _read(directory / "project.json")
        g1 = _read(directory / "g1_features.json")
        lattice = _read(directory / "lattice_pitch.json")
        validity = _read(directory / "song_validity.json")
        if (receipt["seed"] != seed or receipt.get("render_status") != "skipped"
                or receipt["plan_hash"] != plan["plan_hash"]
                or receipt["program_hash"] != program_hash(program)
                or receipt["project_hash"] != project_hash(project)
                or g1 != extract_composition_viability(program, project)
                or lattice != lattice_pitch_diagnostic(project)
                or receipt["song_validity_hash"] != validity["assessment_hash"]):
            raise ValueError(f"symbolic artifact mismatch: {directory}")
        if validity["failure_codes"]:
            failures.append({"seed": seed, "failure_codes": validity["failure_codes"]})
            continue
        rows.append({"seed": seed, "plan_hash": plan["plan_hash"],
                     "project_hash": receipt["project_hash"],
                     "features": features(plan, project, g1, lattice)})
    if not rows:
        raise ValueError("no valid symbolic songs")
    if clusters > len(rows):
        raise ValueError("more clusters than valid symbolic songs")
    groups = cluster(rows, clusters, metric=distance_symbolic)
    report = {"schema": "cps.symbolic-song-clusters", "schema_version": "1.0.0",
              "non_authoritative": True, "source_cohort": str(cohort.resolve().relative_to(REPO)),
              "attempted_count": cohort_report["seed_count"] if cohort_report else len(rows) + len(failures),
              "generation_failures": generation_failures,
              "compiled_count": len(rows) + len(failures), "symbolic_failure_count": len(failures),
              "symbolic_failures": failures, "feature_contract": "section-project-distance/v1",
              "rows": rows, "clusters": groups, "report_hash": ""}
    report["report_hash"] = "sha256:" + hashlib.sha256(
        b"cps.symbolic-song-clusters/v1\0" + canonical_bytes({
            key: value for key, value in report.items() if key != "report_hash"
        })
    ).hexdigest()
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists() and output.read_bytes() != canonical_bytes(report):
        raise ValueError("existing report differs")
    output.write_bytes(canonical_bytes(report))
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cohort", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--clusters", type=int, default=16)
    args = parser.parse_args()
    if (not args.output.resolve().is_relative_to(REPO / "local_authority")
            or not args.cohort.resolve().is_relative_to(REPO / "local_authority")):
        parser.error("paths must be in local_authority")
    try:
        report = run(args.cohort, args.output, clusters=args.clusters)
    except (ValueError, KeyError, OSError, json.JSONDecodeError) as error:
        parser.error(str(error))
    print(json.dumps({"attempted": report["attempted_count"], "compiled": report["compiled_count"],
                      "symbolic_failures": report["symbolic_failure_count"],
                      "representatives": [row["representative_seed"] for row in report["clusters"]],
                      "report_hash": report["report_hash"]}, sort_keys=True))


if __name__ == "__main__":
    main()
