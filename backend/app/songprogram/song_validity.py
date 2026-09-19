"""Deterministic completed-song hard validity assessment."""

from __future__ import annotations

import hashlib
from collections import defaultdict
from typing import Any, Mapping

from .compiler import _canonical


class SongValidityError(ValueError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def _hash(assessment: Mapping[str, Any]) -> str:
    body = {key: value for key, value in assessment.items() if key != "assessment_hash"}
    prefix = b"cps-artifact-hash/v1\0cps.song-validity-assessment\0" b"1.0.0\0"
    return "sha256:" + hashlib.sha256(prefix + _canonical(body)).hexdigest()


def _polyphony_within_track_limits(project: Mapping[str, Any]) -> bool:
    limits = {track["id"]: track["maximum_polyphony"] for track in project["tracks"]}
    boundaries: dict[str, list[tuple[int, int]]] = defaultdict(list)
    for event in project["events"]:
        if event["kind"] not in {"note", "drum"}:
            continue
        boundaries[event["track_id"]].append((event["start_tick"], 1))
        boundaries[event["track_id"]].append(
            (event["start_tick"] + event["duration_ticks"], -1)
        )
    for track_id, points in boundaries.items():
        active = 0
        for _, delta in sorted(points, key=lambda item: (item[0], item[1])):
            active += delta
            if active > limits[track_id]:
                return False
    return True


def assess_completed_song(
    program: Mapping[str, Any],
    project: Mapping[str, Any],
    *,
    symbolic_coverage: Mapping[str, Any],
    arrangement: Mapping[str, Any],
    pcm_continuity: Mapping[str, Any],
) -> dict[str, Any]:
    """Apply the frozen GEN0 completed-song hard checks without preference scores."""
    try:
        sections = program["form"]
        realizations = program["realizations"]
        section_ids = {section["id"] for section in sections}
        realized_sections = {row["section_id"] for row in realizations}
        track_roles = {track["id"]: track["role"] for track in project["tracks"]}
        total_bars = sum(section["bars"] for section in sections)
    except (KeyError, TypeError):
        raise SongValidityError("SONG_VALIDITY_INPUT_INVALID") from None
    emitted_roles = {
        track_roles[event["track_id"]]
        for event in project["events"]
        if event.get("kind") in {"note", "drum"} and event.get("track_id") in track_roles
    }
    core_roles = emitted_roles & {"drums", "bass", "harmony", "melody"}
    material_sections: dict[str, set[str]] = defaultdict(set)
    transformed_materials: set[str] = set()
    for realization in realizations:
        material_sections[realization["material_id"]].add(realization["section_id"])
        if realization.get("pitch_transforms") or realization.get("rhythm_transforms"):
            transformed_materials.add(realization["material_id"])
    transformed_recall = any(
        len(material_sections[material_id]) >= 2 for material_id in transformed_materials
    )
    checks = {
        "bars_16_to_64": 16 <= total_bars <= 64,
        "sections_3_to_8": 3 <= len(sections) <= 8,
        "every_section_realized": realized_sections == section_ids,
        "minimum_three_core_sounding_roles": len(core_roles) >= 3,
        "symbolic_coverage_at_least_8500_bp": symbolic_coverage.get(
            "overall_coverage_basis_points"
        )
        is not None
        and symbolic_coverage["overall_coverage_basis_points"] >= 8500,
        "no_fully_silent_one_second_window": pcm_continuity.get(
            "fully_silent_one_second_window_count"
        )
        == 0,
        "arrangement_development_passed": arrangement.get("status") == "passed",
        "polyphony_within_track_limits": _polyphony_within_track_limits(project),
        "non_identity_transformed_recall_across_sections": transformed_recall,
    }
    assessment = {
        "schema": "cps.song-validity-assessment",
        "schema_version": "1.0.0",
        "status": "passed" if all(checks.values()) else "failed",
        "archive_eligible": all(checks.values()),
        "hard_checks": checks,
        "diagnostics": {
            "bars": total_bars,
            "section_count": len(sections),
            "event_count": len(project["events"]),
            "emitted_core_roles": sorted(core_roles),
            "overall_coverage_basis_points": symbolic_coverage.get(
                "overall_coverage_basis_points"
            ),
            "fully_silent_one_second_window_count": pcm_continuity.get(
                "fully_silent_one_second_window_count"
            ),
            "distinct_role_mask_count": arrangement.get("distinct_role_mask_count"),
        },
        "failure_codes": [key for key, passed in checks.items() if not passed],
        "assessment_hash": "",
    }
    assessment["assessment_hash"] = _hash(assessment)
    return assessment
