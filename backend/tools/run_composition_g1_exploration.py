"""Explore generated songs in rounds using G0 eligibility and G1 Pareto feedback."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
REPO = BACKEND.parent
sys.path.insert(0, str(BACKEND))

from app.songprogram.piano_part import PIANO_STYLES  # noqa: E402
from app.songprogram.composition_realization import (  # noqa: E402
    realization_profile_hash, validate_realization_profile,
)
from app.songprogram.search import canonical_bytes  # noqa: E402
from tools.generate_composition_song import DEFAULT_PROFILE, DEFAULT_REALIZATION_PROFILE  # noqa: E402
from tools.prepare_song_evaluation import _candidate, _sha  # noqa: E402
from tools.run_composition_generation_cohort import _generate  # noqa: E402
from tools.run_fixture_generation_cohort import DEFAULT_GENERATION_MANIFEST  # noqa: E402

# Only dimensions whose current interpretation is monotonic participate in the
# frontier. Range-valued and constant diagnostics remain visible in every row.
OBJECTIVES = (
    "audible_motif_recurrence_q",
    "foreground_presence_q",
    "groove_distribution_q",
    "part_coordination_q",
    "adjacent_section_continuity_q",
)


def frontier(rows: list[dict], *, lattice_target_q: int | None = None) -> list[str]:
    """Return nondominated eligible candidates, collapsing identical vectors by seed."""
    eligible = [row for row in rows if row["status"] == "g0_eligible"]
    keys = (*OBJECTIVES, "lattice_target_proximity_q") if lattice_target_q is not None else OBJECTIVES
    winners = []
    for candidate in eligible:
        vector = candidate["g1_objectives_q"]
        if any(
            all(other["g1_objectives_q"][key] >= vector[key] for key in keys)
            and (any(other["g1_objectives_q"][key] > vector[key] for key in keys)
                 or other["seed"] < candidate["seed"])
            for other in eligible if other is not candidate
        ):
            continue
        winners.append(candidate["candidate_id"])
    return winners


def _seal(report: dict) -> dict:
    report["report_hash"] = "sha256:" + hashlib.sha256(
        b"cps.composition-g1-exploration/v1\0"
        + canonical_bytes({key: value for key, value in report.items() if key != "report_hash"})
    ).hexdigest()
    return report


def _write(output: Path, report: dict) -> None:
    payload = canonical_bytes(_seal(report))
    path = output / "g1_exploration.json"
    temporary = output / "g1_exploration.json.tmp"
    temporary.write_bytes(payload)
    temporary.replace(path)


def explore(
    output: Path, *, rounds: int, candidates_per_round: int, seed_offset: int = 0,
    source_cohort: Path | None = None, piano_style: str = "mixed",
    profile: Path = DEFAULT_PROFILE,
    realization_profile: Path = DEFAULT_REALIZATION_PROFILE,
    generation_manifest: Path = DEFAULT_GENERATION_MANIFEST,
    lattice_target_q: int | None = None,
    repository: Path = REPO,
) -> dict:
    repository = repository.resolve()
    output = output.resolve()
    if not output.is_relative_to(repository / "local_authority"):
        raise ValueError("output must be within local_authority")
    if (rounds < 1 or candidates_per_round < 1 or seed_offset < 0
            or seed_offset + rounds * candidates_per_round > 2**64
            or piano_style not in PIANO_STYLES):
        raise ValueError("invalid exploration budget, seed range, or piano style")
    if lattice_target_q is not None and not 0 <= lattice_target_q <= 10000:
        raise ValueError("lattice target must be in 0..10000")
    source = source_cohort.resolve() if source_cohort is not None else output / "candidates"
    if output == source or (source.is_relative_to(output) and source != output / "candidates"):
        raise ValueError("source cohort must not overlap exploration output")
    if source_cohort is not None and not source.is_dir():
        raise ValueError(f"source cohort does not exist: {source}")
    configuration = {
        "source_cohort": str(source) if source_cohort is not None else None,
        "piano_style": piano_style if source_cohort is None else None,
        "profile_hash": _sha(profile) if source_cohort is None else None,
        **({"realization_profile_hash": _sha(realization_profile)}
           if source_cohort is None else {}),
        "generation_manifest_hash": _sha(generation_manifest) if source_cohort is None else None,
        "seed_offset": seed_offset, "candidates_per_round": candidates_per_round,
        "objectives": list(OBJECTIVES), "selection": "g0-eligible-g1-pareto/v1",
    }
    if lattice_target_q is not None:
        configuration["lattice_target_q"] = lattice_target_q
        configuration["objectives"].append("lattice_target_proximity_q")
    expected_profile_hash = json.loads(profile.read_text(encoding="utf-8"))["profile_hash"] if source_cohort is None else None
    expected_realization_hash = None
    if source_cohort is None:
        realized = json.loads(realization_profile.read_text(encoding="utf-8"))
        validate_realization_profile(realized)
        expected_realization_hash = realization_profile_hash(realized)
    output.mkdir(parents=True, exist_ok=True)
    saved = output / "g1_exploration.json"
    previous = None
    if saved.exists():
        previous = json.loads(saved.read_text(encoding="utf-8"))
        if (previous.get("report_hash") != _seal({key: value for key, value in previous.items()
                                                  if key != "report_hash"})["report_hash"]
                or previous.get("configuration") != configuration):
            raise ValueError("existing exploration report is invalid or has different configuration")
        if len(previous["rounds"]) > rounds:
            raise ValueError("cannot shrink an existing exploration")
    report = {
        "schema": "cps.composition-g1-exploration", "schema_version": "1.0.0",
        "non_authoritative": True, "configuration": configuration, "rounds": [],
        "frontier": [], "report_hash": "",
    }
    rows = []
    for round_index in range(rounds):
        batch = []
        for ordinal in range(candidates_per_round):
            seed = seed_offset + round_index * candidates_per_round + ordinal
            directory = source / f"seed-{seed:04d}"
            if source_cohort is None:
                result = _generate(seed, str(source), str(profile), str(generation_manifest),
                                   piano_style, str(realization_profile))
                if result["status"] != "success":
                    raise ValueError(f"generation failed for seed {seed}: {result['error']}")
                receipt = json.loads((directory / "receipt.json").read_text(encoding="utf-8"))
                if (receipt.get("profile_hash") != expected_profile_hash
                        or receipt.get("realization_profile_hash") != expected_realization_hash
                        or receipt.get("piano_style", "none") != piano_style):
                    raise ValueError(f"cached generation profile/style differs for seed {seed}")
            candidate, diagnostic = _candidate("generated", directory, seed, repository)
            metrics = diagnostic["g1_metrics_q"]
            lattice = diagnostic["lattice_pitch"]
            objectives = {key: metrics[key] for key in OBJECTIVES}
            if lattice_target_q is not None:
                objectives["lattice_target_proximity_q"] = 10000 - abs(
                    lattice["exposed_duration_share_q"] - lattice_target_q
                )
            batch.append({
                "candidate_id": candidate["candidate_id"], "seed": seed,
                "status": "g0_eligible" if diagnostic["g0_archive_eligible"] else "g0_ineligible",
                "g0_failure_codes": diagnostic["g0_failure_codes"],
                "g1_metrics_q": metrics,
                "g1_objectives_q": objectives,
                "lattice_pitch": lattice,
                "g1_feature_report_hash": candidate["g1_feature_report_hash"],
                "audio_hash": candidate["audio_hash"],
                "artifact_directory": str(directory.relative_to(repository)),
            })
        rows.extend(batch)
        round_result = {"index": round_index, "candidates": batch,
                        "frontier": frontier(rows, lattice_target_q=lattice_target_q)}
        if previous and round_index < len(previous["rounds"]):
            if round_result != previous["rounds"][round_index]:
                raise ValueError(f"existing exploration artifacts differ at round {round_index}")
        report["rounds"].append(round_result)
        report["frontier"] = round_result["frontier"]
        if previous is None or round_index >= len(previous["rounds"]):
            _write(output, report)
    return _seal(report)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--rounds", type=int, required=True)
    parser.add_argument("--candidates-per-round", type=int, required=True)
    parser.add_argument("--seed-offset", type=int, default=0)
    parser.add_argument("--source-cohort", type=Path, help="evaluate existing songs instead of generating")
    parser.add_argument("--piano-style", choices=PIANO_STYLES, default="mixed")
    parser.add_argument("--profile", type=Path, default=DEFAULT_PROFILE)
    parser.add_argument("--realization-profile", type=Path, default=DEFAULT_REALIZATION_PROFILE)
    parser.add_argument("--generation-manifest", type=Path, default=DEFAULT_GENERATION_MANIFEST)
    parser.add_argument("--lattice-target-q", type=int,
                        help="optional target (0..10000) for >=10-cent pitched voice-time share")
    args = parser.parse_args()
    try:
        result = explore(
            args.output, rounds=args.rounds, candidates_per_round=args.candidates_per_round,
            seed_offset=args.seed_offset, source_cohort=args.source_cohort,
            piano_style=args.piano_style, profile=args.profile,
            realization_profile=args.realization_profile,
            generation_manifest=args.generation_manifest,
            lattice_target_q=args.lattice_target_q,
        )
    except (ValueError, KeyError, OSError, json.JSONDecodeError) as error:
        parser.error(str(error))
    print(json.dumps({"rounds": len(result["rounds"]), "candidates": sum(
        len(row["candidates"]) for row in result["rounds"]),
        "frontier": result["frontier"], "report_hash": result["report_hash"]}, sort_keys=True))


if __name__ == "__main__":
    main()
