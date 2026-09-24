"""Prescreen many composition seeds by deterministic plan features and medoids."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Callable

BACKEND = Path(__file__).resolve().parents[1]
REPO = BACKEND.parent
sys.path.insert(0, str(BACKEND))

from app.songprogram.composition_generation import generate_composition_plan  # noqa: E402
from app.songprogram.search import canonical_bytes  # noqa: E402

DEFAULT_PROFILE = BACKEND / "songprogram_conformance/profiles/g1_experiments/section_variation.json"
FUNCTIONS = ("opening", "statement", "preparation", "arrival", "contrast", "return", "closure")
OPERATIONS = ("rest", "statement", "recall", "answer", "rhythmic_displacement", "fragmentation", "cadential_release")


def features(plan: dict) -> dict:
    sections = plan["sections"]
    states = Counter(row["harmonic_function"] for row in plan["harmonic_trajectory"])
    operations = Counter(row["operation"] for row in plan["motif_plan"]["occurrences"])
    per_function = {}
    for function in FUNCTIONS:
        rows = [row for row in sections if row["function"] == function]
        per_function[function] = [
            5000 * len(rows),
            round(10000 * sum(row["bars"] for row in rows) / (16 * max(1, len(rows)))),
            round(sum(row["energy_q"] for row in rows) / max(1, len(rows))),
            round(sum(row["density_q"] for row in rows) / max(1, len(rows))),
        ]
    return {
        "opening": [sections[0]["bars"], sections[0]["energy_q"],
                    sections[0]["density_q"], sections[0]["foreground_state"]],
        "closure": [sections[-1]["bars"], sections[-1]["energy_q"],
                    sections[-1]["density_q"], sections[-1]["foreground_state"]],
        "form": [section["function"] for section in sections],
        "per_function": per_function,
        "harmonic_function_share": {key: round(10000 * states[key] / len(plan["harmonic_trajectory"]))
                                    for key in ("home", "departure", "preparation", "arrival", "return")},
        "motif_operation_share": {key: round(10000 * operations[key] / len(plan["motif_plan"]["occurrences"]))
                                  for key in OPERATIONS},
    }


def distance(left: dict, right: dict) -> float:
    # Sections are intentionally more important than noisy motif-choice counts.
    boundary = sum(2.0 if left[key][3] != right[key][3] else 0.0
                   for key in ("opening", "closure"))
    boundary += sum(abs(left[key][index] - right[key][index]) / divisor
                    for key in ("opening", "closure")
                    for index, divisor in ((0, 8), (1, 10000), (2, 10000)))
    form = 2.0 if left["form"] != right["form"] else 0.0
    section = sum(abs(a - b) for key in FUNCTIONS
                  for a, b in zip(left["per_function"][key], right["per_function"][key])) / (10000 * len(FUNCTIONS))
    harmonic = sum(abs(left["harmonic_function_share"][key] - right["harmonic_function_share"][key])
                   for key in left["harmonic_function_share"])
    motif = sum(abs(left["motif_operation_share"][key] - right["motif_operation_share"][key])
                for key in OPERATIONS)
    return boundary + form + 3 * section + (harmonic + motif) / 10000


def cluster(rows: list[dict], count: int, *, metric: Callable[[dict, dict], float] = distance) -> list[dict]:
    if not 1 <= count <= len(rows):
        raise ValueError("cluster count outside cohort")
    cache: dict[tuple[int, int], float] = {}

    def gap(a: int, b: int) -> float:
        key = (min(a, b), max(a, b))
        if key not in cache:
            cache[key] = metric(rows[a]["features"], rows[b]["features"])
        return cache[key]

    # Greedy covering seeds, followed by deterministic within-cluster medoids.
    centers = [0]
    while len(centers) < count:
        centers.append(max((index for index in range(len(rows)) if index not in centers),
                           key=lambda index: (min(gap(index, center) for center in centers), -rows[index]["seed"])))
    for _ in range(5):
        groups: dict[int, list[int]] = defaultdict(list)
        for index in range(len(rows)):
            center = min(centers, key=lambda value: (gap(index, value), rows[value]["seed"]))
            groups[center].append(index)
        updated = [min(groups[center], key=lambda index: (
            sum(gap(index, member) for member in groups[center]), rows[index]["seed"]
        )) for center in centers]
        if updated == centers:
            break
        centers = updated
    groups = defaultdict(list)
    for index in range(len(rows)):
        center = min(centers, key=lambda value: (gap(index, value), rows[value]["seed"]))
        groups[center].append(index)
    return [{
        "representative_seed": rows[center]["seed"],
        "member_count": len(groups[center]),
        "member_seeds": [rows[index]["seed"] for index in groups[center]],
        "mean_distance_milli": round(1000 * sum(gap(index, center) for index in groups[center]) / len(groups[center])),
        "opening": rows[center]["features"]["opening"],
        "closure": rows[center]["features"]["closure"],
        "form": rows[center]["features"]["form"],
    } for center in sorted(centers, key=lambda index: rows[index]["seed"])]


def run(profile_path: Path, output: Path, *, seeds: int = 1000, clusters: int = 16) -> dict:
    if not 1 <= seeds <= 10000:
        raise ValueError("seeds must be in 1..10000")
    profile = json.loads(profile_path.read_text())
    rows = []
    for seed in range(seeds):
        plan = generate_composition_plan(profile, seed)
        rows.append({"seed": seed, "plan_hash": plan["plan_hash"], "features": features(plan)})
    groups = cluster(rows, clusters)
    report = {
        "schema": "cps.section-plan-cluster-prescreen", "schema_version": "1.0.0",
        "non_authoritative": True, "stage": "composition_plan_only_no_project_no_wav",
        "profile_hash": profile["profile_hash"], "seed_count": seeds,
        "feature_contract": "section-plan-distance/v1", "clusters": groups,
        "rows": rows, "report_hash": "",
    }
    report["report_hash"] = "sha256:" + hashlib.sha256(
        b"cps.section-plan-cluster-prescreen/v1\0" + canonical_bytes({
            key: value for key, value in report.items() if key != "report_hash"
        })
    ).hexdigest()
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists() and output.read_bytes() != canonical_bytes(report):
        raise ValueError("existing cluster report differs")
    output.write_bytes(canonical_bytes(report))
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", type=Path, default=DEFAULT_PROFILE)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seeds", type=int, default=1000)
    parser.add_argument("--clusters", type=int, default=16)
    args = parser.parse_args()
    if not args.output.resolve().is_relative_to(REPO / "local_authority"):
        parser.error("output must be in local_authority")
    try:
        report = run(args.profile, args.output, seeds=args.seeds, clusters=args.clusters)
    except (ValueError, OSError, json.JSONDecodeError) as error:
        parser.error(str(error))
    print(json.dumps({"seeds": report["seed_count"], "representatives": [
        row["representative_seed"] for row in report["clusters"]],
        "report_hash": report["report_hash"]}, sort_keys=True))


if __name__ == "__main__":
    main()
