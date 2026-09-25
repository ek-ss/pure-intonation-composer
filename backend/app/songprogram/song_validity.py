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
    prefix = (b"cps-artifact-hash/v1\0cps.song-validity-assessment\0"
              + assessment["schema_version"].encode() + b"\0")
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
    pcm_continuity: Mapping[str, Any] | None,
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
        "no_fully_silent_one_second_window": (pcm_continuity or {}).get(
            "fully_silent_one_second_window_count"
        )
        == 0,
        "arrangement_development_passed": arrangement.get("status") == "passed",
        "polyphony_within_track_limits": _polyphony_within_track_limits(project),
        "non_identity_transformed_recall_across_sections": transformed_recall,
    }
    unchecked = ["no_fully_silent_one_second_window"] if pcm_continuity is None else []
    assessment = {
        "schema": "cps.song-validity-assessment",
        "schema_version": "1.1.0" if unchecked else "1.0.0",
        "status": "incomplete" if unchecked else "passed" if all(checks.values()) else "failed",
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
            "fully_silent_one_second_window_count": (pcm_continuity or {}).get(
                "fully_silent_one_second_window_count"
            ),
            "distinct_role_mask_count": arrangement.get("distinct_role_mask_count"),
        },
        "failure_codes": [key for key, passed in checks.items() if not passed and key not in unchecked],
        "assessment_hash": "",
    }
    if unchecked:
        assessment["unchecked_checks"] = unchecked
    assessment["assessment_hash"] = _hash(assessment)
    return assessment


def _rest_count_rule(program: Mapping[str, Any], project: Mapping[str, Any]) -> bool:
    """Per-measure silence must not exceed one beat, and no measure is silent.

    This replaces the PCM silent-time specification for piano-solo songs.  It is
    evaluated on the symbolic event list (no PCM required) so a ``--skip-wav``
    generation can still be assessed.  Silence is the time when no note or drum
    event is sounding on any track.
    """
    clock = program["clock"]
    ticks_per_beat = clock["ticks_per_beat"]
    ticks_per_bar = ticks_per_beat * clock["beats_per_bar"]
    total_bars = sum(section["bars"] for section in program["form"])
    total_ticks = total_bars * ticks_per_bar
    if total_ticks <= 0:
        return False
    difference = [0] * (total_ticks + 1)
    for event in project["events"]:
        if event.get("kind") not in {"note", "drum"}:
            continue
        start = event["start_tick"]
        end = min(start + event["duration_ticks"], total_ticks)
        if start < 0 or start >= end:
            continue
        difference[start] += 1
        difference[end] -= 1
    active = 0
    for bar in range(total_bars):
        bar_start = bar * ticks_per_bar
        bar_end = bar_start + ticks_per_bar
        silence = 0
        for tick in range(bar_start, bar_end):
            active += difference[tick]
            if active == 0:
                silence += 1
        # A wholly silent measure (whole rest) is forbidden.
        if silence >= ticks_per_bar:
            return False
        # At most one beat of silence per measure (a quarter rest).
        if silence > ticks_per_beat:
            return False
    return True


def assess_piano_solo(
    program: Mapping[str, Any],
    project: Mapping[str, Any],
) -> dict[str, Any]:
    """Apply the piano-solo completed-song hard checks.

    A piano song realizes exactly two core roles (``harmony`` + ``melody``) on
    separate piano tracks.  Compared with :func:`assess_completed_song` this
    drops the PCM silent-time window, the symbolic coverage gate, the
    arrangement-development check, and the transformed-recall check (all of
    which assume a full band), lowers the core-role minimum to two, and adds a
    per-measure rest-count rule.
    """
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
    core_roles = emitted_roles & {"harmony", "melody"}
    checks = {
        "bars_16_to_64": 16 <= total_bars <= 64,
        "sections_3_to_8": 3 <= len(sections) <= 8,
        "every_section_realized": realized_sections == section_ids,
        "minimum_two_core_sounding_roles": len(core_roles) >= 2,
        "rest_count_rule": _rest_count_rule(program, project),
        "polyphony_within_track_limits": _polyphony_within_track_limits(project),
    }
    assessment = {
        "schema": "cps.song-validity-assessment",
        "schema_version": "1.2.0",
        "status": "passed" if all(checks.values()) else "failed",
        "archive_eligible": all(checks.values()),
        "hard_checks": checks,
        "diagnostics": {
            "bars": total_bars,
            "section_count": len(sections),
            "event_count": len(project["events"]),
            "emitted_core_roles": sorted(core_roles),
        },
        "failure_codes": [key for key, passed in checks.items() if not passed],
        "assessment_hash": "",
    }
    assessment["assessment_hash"] = _hash(assessment)
    return assessment
