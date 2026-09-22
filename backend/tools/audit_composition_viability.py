"""Audit pre-genre composition viability signals for a generated cohort.

The report is diagnostic and deliberately non-authoritative. It exposes
obvious proxy failures in the current full-song generator without converting
uncalibrated musical heuristics into an archive gate.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from app.songprogram.search import canonical_bytes  # noqa: E402


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def _form_diagnostics(roles: list[str]) -> dict[str, int]:
    violations: Counter[str] = Counter()
    for index, role in enumerate(roles):
        if role == "intro" and index != 0:
            violations["intro_after_first"] += 1
        if role == "outro" and index != len(roles) - 1:
            violations["outro_before_last"] += 1
        if role == "final" and any(
            later not in {"final", "outro"} for later in roles[index + 1 :]
        ):
            violations["final_before_nonterminal_section"] += 1
        if role == "build" and (
            index == len(roles) - 1 or roles[index + 1] not in {"drop", "final"}
        ):
            violations["build_without_immediate_release"] += 1
    return {
        key: violations[key]
        for key in (
            "intro_after_first",
            "outro_before_last",
            "final_before_nonterminal_section",
            "build_without_immediate_release",
        )
    }


def audit_candidate(
    seed: int,
    program: dict[str, Any],
    project: dict[str, Any],
    validity: dict[str, Any] | None = None,
) -> dict[str, Any]:
    tracks = {track["id"]: track["role"] for track in project["tracks"]}
    section_ids = [section["id"] for section in project["form"]]
    section_roles = [section["role"] for section in project["form"]]
    events_by_section: dict[str, list[dict[str, Any]]] = defaultdict(list)
    event_count_by_role: Counter[str] = Counter()
    sounding_sections_by_role: dict[str, set[str]] = defaultdict(set)
    for event in project["events"]:
        role = tracks[event["track_id"]]
        events_by_section[event["section_id"]].append(event)
        event_count_by_role[role] += 1
        sounding_sections_by_role[role].add(event["section_id"])

    harmony_pitch_sets = []
    for section_id in section_ids:
        pitches = {
            event["ratio"]
            for event in events_by_section[section_id]
            if event["kind"] == "note" and tracks[event["track_id"]] == "harmony"
        }
        if pitches:
            harmony_pitch_sets.append(tuple(sorted(pitches)))

    ticks_per_bar = (
        project["clock"]["beats_per_bar"] * project["clock"]["ticks_per_beat"]
    )
    onset_bins = 16
    active_bins_by_role: dict[str, set[int]] = defaultdict(set)
    second_half_onsets = 0
    for event in project["events"]:
        role = tracks[event["track_id"]]
        within_bar = event["start_tick"] % ticks_per_bar
        active_bins_by_role[role].add(min(onset_bins - 1, within_bar * onset_bins // ticks_per_bar))
        second_half_onsets += within_bar >= ticks_per_bar // 2

    form = _form_diagnostics(section_roles)
    total_events = len(project["events"])
    melody_sections = len(sounding_sections_by_role.get("melody", set()))
    harmony_distinct = len(set(harmony_pitch_sets))
    return {
        "seed": seed,
        "current_archive_eligible": (
            validity.get("archive_eligible") if validity is not None else None
        ),
        "section_role_sequence": section_roles,
        "form_transition_diagnostics": form,
        "form_transition_violation_count": sum(form.values()),
        "foreground_diagnostics": {
            "melody_event_count": event_count_by_role["melody"],
            "melody_sounding_section_count": melody_sections,
            "melody_section_coverage_basis_points": (
                round(10_000 * melody_sections / len(section_ids)) if section_ids else 0
            ),
        },
        "harmony_diagnostics": {
            "harmony_sounding_section_count": len(harmony_pitch_sets),
            "distinct_section_pitch_set_count": harmony_distinct,
            "static_section_pitch_set": len(harmony_pitch_sets) >= 2 and harmony_distinct == 1,
        },
        "rhythm_diagnostics": {
            "event_count": total_events,
            "second_half_of_bar_onset_count": second_half_onsets,
            "second_half_of_bar_onset_basis_points": (
                round(10_000 * second_half_onsets / total_events) if total_events else 0
            ),
            "active_sixteenth_bins_by_role": {
                role: len(bins) for role, bins in sorted(active_bins_by_role.items())
            },
        },
        "role_diagnostics": {
            "event_count_by_role": dict(sorted(event_count_by_role.items())),
            "sounding_section_count_by_role": {
                role: len(sections)
                for role, sections in sorted(sounding_sections_by_role.items())
            },
        },
        "program_section_count": len(program["form"]),
    }


def audit_cohort(cohort: Path) -> dict[str, Any]:
    rows = []
    for directory in sorted(cohort.glob("seed-*")):
        if not directory.is_dir() or not (directory / "program.json").is_file():
            continue
        try:
            seed = int(directory.name.removeprefix("seed-"))
        except ValueError:
            continue
        validity_path = directory / "mock_song_validity.json"
        rows.append(
            audit_candidate(
                seed,
                _load(directory / "program.json"),
                _load(directory / "project.json"),
                _load(validity_path) if validity_path.is_file() else None,
            )
        )
    if not rows:
        raise ValueError(f"no generated candidates found in {cohort}")

    eligible = [row for row in rows if row["current_archive_eligible"] is True]
    event_total = sum(row["rhythm_diagnostics"]["event_count"] for row in rows)
    second_half_total = sum(
        row["rhythm_diagnostics"]["second_half_of_bar_onset_count"] for row in rows
    )
    return {
        "schema": "cps.composition-viability-diagnostic-report",
        "schema_version": "0.1.0",
        "non_authoritative": True,
        "usage": "baseline_diagnosis_only_not_archive_admission",
        "cohort": str(cohort),
        "candidate_count": len(rows),
        "summary": {
            "current_archive_eligible_count": len(eligible),
            "candidate_without_melody_count": sum(
                row["foreground_diagnostics"]["melody_event_count"] == 0 for row in rows
            ),
            "eligible_without_melody_count": sum(
                row["foreground_diagnostics"]["melody_event_count"] == 0
                for row in eligible
            ),
            "candidate_with_static_section_harmony_count": sum(
                row["harmony_diagnostics"]["static_section_pitch_set"] for row in rows
            ),
            "candidate_with_form_transition_violation_count": sum(
                row["form_transition_violation_count"] > 0 for row in rows
            ),
            "aggregate_second_half_of_bar_onset_basis_points": (
                round(10_000 * second_half_total / event_total) if event_total else 0
            ),
        },
        "rows": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cohort", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    report = audit_cohort(arguments.cohort)
    payload = canonical_bytes(report)
    if arguments.output is None:
        sys.stdout.buffer.write(payload + b"\n")
    else:
        arguments.output.parent.mkdir(parents=True, exist_ok=True)
        arguments.output.write_bytes(payload)


if __name__ == "__main__":
    main()
