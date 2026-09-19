"""Non-authoritative G1 composition-viability feature extraction."""

from __future__ import annotations

import hashlib
from collections import Counter, defaultdict
from typing import Any, Mapping

from .search import canonical_bytes


class CompositionViabilityError(ValueError):
    pass


def _q(numerator: int, denominator: int) -> int:
    return 0 if denominator <= 0 else max(0, min(10000, round(10000 * numerator / denominator)))


def _score_violations(count: int, opportunities: int) -> int:
    return 10000 - _q(count, max(1, opportunities))


def composition_viability_report_hash(report: Mapping[str, Any]) -> str:
    payload = {key: value for key, value in report.items() if key != "report_hash"}
    return "sha256:" + hashlib.sha256(
        b"cps.composition-viability-feature-report/1.0\0" + canonical_bytes(payload)
    ).hexdigest()


def extract_composition_viability(
    program: Mapping[str, Any], project: Mapping[str, Any]
) -> dict[str, Any]:
    try:
        sections = list(project["form"])
        tracks = {track["id"]: track["role"] for track in project["tracks"]}
        events = [event for event in project["events"] if event["kind"] in {"note", "drum"}]
        clock = project["clock"]
        ticks_per_bar = clock["beats_per_bar"] * clock["ticks_per_beat"]
    except (KeyError, TypeError):
        raise CompositionViabilityError("COMPOSITION_VIABILITY_INPUT_INVALID") from None
    if not sections or ticks_per_bar <= 0:
        raise CompositionViabilityError("COMPOSITION_VIABILITY_INPUT_INVALID")
    section_by_id = {section["id"]: section for section in sections}
    material_by_instance = {
        instance["id"]: instance["material_id"]
        for instance in project.get("material_instances", [])
        if isinstance(instance, Mapping)
        and isinstance(instance.get("id"), str)
        and isinstance(instance.get("material_id"), str)
    }
    events_by_section: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for event in events:
        if event.get("section_id") not in section_by_id or event.get("track_id") not in tracks:
            raise CompositionViabilityError("COMPOSITION_VIABILITY_INPUT_INVALID")
        events_by_section[event["section_id"]].append(event)

    roles = [section["role"] for section in sections]
    form_violations = int(roles[0] != "intro") + int(roles[-1] != "outro")
    form_violations += sum(
        role == "build" and (index + 1 == len(roles) or roles[index + 1] not in {"drop", "final"})
        for index, role in enumerate(roles)
    )
    form_violations += sum(
        role == "final" and any(later not in {"final", "outro"} for later in roles[index + 1 :])
        for index, role in enumerate(roles)
    )

    total_bars = sum(section["bars"] for section in sections)
    phrase_boundaries = [bar * ticks_per_bar for bar in range(2, total_bars, 2)]
    absolute_starts = {event["start_tick"] for event in events}
    absolute_ends = {event["start_tick"] + event["duration_ticks"] for event in events}
    boundary_hits = sum(
        boundary in absolute_starts or boundary in absolute_ends for boundary in phrase_boundaries
    )

    phrase_fingerprints: list[tuple[tuple[str, int], ...]] = []
    for start_bar in range(0, total_bars - 1, 2):
        start = start_bar * ticks_per_bar
        end = start + 2 * ticks_per_bar
        fingerprint = tuple(
            sorted(
                (tracks[event["track_id"]], event["start_tick"] - start)
                for event in events
                if start <= event["start_tick"] < end
            )
        )
        if fingerprint:
            phrase_fingerprints.append(fingerprint)
    fingerprint_counts = Counter(phrase_fingerprints)
    recurrent_phrases = sum(count for count in fingerprint_counts.values() if count >= 2)
    distinct_phrases = len(fingerprint_counts)
    development_q = _q(max(0, distinct_phrases - 1), max(1, len(phrase_fingerprints) - 1))

    harmony_sets = []
    role_masks = []
    section_event_counts = []
    material_sets = []
    for section in sections:
        rows = events_by_section[section["id"]]
        harmony_sets.append(
            tuple(
                sorted(
                    {
                        event["ratio"]
                        for event in rows
                        if tracks[event["track_id"]] == "harmony" and event.get("ratio")
                    }
                )
            )
        )
        role_masks.append(tuple(sorted({tracks[event["track_id"]] for event in rows})))
        section_event_counts.append(len(rows))
        material_sets.append(
            {
                material_by_instance.get(instance_id, instance_id)
                for event in rows
                if (instance_id := event.get("source", {}).get("material_instance_id"))
            }
        )
    distinct_harmony = len({value for value in harmony_sets if value})
    home_return = bool(harmony_sets[0]) and harmony_sets[0] == harmony_sets[-1]

    onset_bins = {event["start_tick"] % ticks_per_bar * 16 // ticks_per_bar for event in events}
    second_half = sum(event["start_tick"] % ticks_per_bar >= ticks_per_bar // 2 for event in events)
    groove_q = (_q(len(onset_bins), 16) + _q(second_half, len(events))) // 2
    contrast_q = (
        _q(len(set(role_masks)), len(sections))
        + _q(len(set(section_event_counts)), len(sections))
    ) // 2
    shared_adjacent = sum(
        bool(left & right) for left, right in zip(material_sets, material_sets[1:])
    )

    drum_starts = {event["start_tick"] for event in events if tracks[event["track_id"]] == "drums"}
    bass = [event for event in events if tracks[event["track_id"]] == "bass"]
    melody = [event for event in events if tracks[event["track_id"]] == "melody"]
    harmony_occurrences = project.get("harmony_occurrences", [])
    coordinated_bass = sum(event["start_tick"] in drum_starts for event in bass)
    bound_melody = sum(
        any(
            occurrence["section_id"] == event["section_id"]
            and occurrence["start_tick"] <= event["start_tick"]
            and event["start_tick"] + event["duration_ticks"]
            <= occurrence["start_tick"] + occurrence["duration_ticks"]
            for occurrence in harmony_occurrences
        )
        for event in melody
    )
    coordination_q = (
        _q(coordinated_bass, len(bass)) + _q(bound_melody, len(melody))
    ) // 2
    melody_sections = {
        event["section_id"] for event in melody
    }
    foreground_q = _q(len(melody_sections), len(sections))

    final_rows = events_by_section[sections[-1]["id"]]
    peak_count = max(section_event_counts)
    ending_density_drop = bool(final_rows) and len(final_rows) < peak_count
    ending_home = home_return
    ending_q = (int(roles[-1] == "outro") + int(ending_density_drop) + int(ending_home)) * 10000 // 3

    metrics = {
        "formal_arc_consistency_q": _score_violations(form_violations, len(sections)),
        "phrase_boundary_strength_q": _q(boundary_hits, len(phrase_boundaries)),
        "audible_motif_recurrence_q": _q(recurrent_phrases, len(phrase_fingerprints)),
        "motif_development_distance_q": development_q,
        "harmonic_motion_q": (_q(distinct_harmony, min(4, len(sections))) + int(home_return) * 10000) // 2,
        "groove_distribution_q": groove_q,
        "section_contrast_q": contrast_q,
        "adjacent_section_continuity_q": _q(shared_adjacent, len(sections) - 1),
        "part_coordination_q": coordination_q,
        "foreground_presence_q": foreground_q,
        "ending_closure_q": ending_q,
    }
    report = {
        "schema": "cps.composition-viability-feature-report",
        "schema_version": "1.0.0",
        "non_authoritative": True,
        "usage": "g1_calibration_feature_only_not_archive_admission",
        "program_id": program.get("program_id"),
        "project_id": project.get("project_id"),
        "metrics_q": metrics,
        "diagnostics": {
            "total_bars": total_bars,
            "section_count": len(sections),
            "event_count": len(events),
            "form_violation_count": form_violations,
            "phrase_boundary_count": len(phrase_boundaries),
            "phrase_boundary_hit_count": boundary_hits,
            "phrase_fingerprint_count": len(phrase_fingerprints),
            "distinct_phrase_fingerprint_count": distinct_phrases,
            "distinct_harmony_state_count": distinct_harmony,
            "home_return": home_return,
            "occupied_sixteenth_bin_count": len(onset_bins),
            "second_half_onset_count": second_half,
            "melody_section_count": len(melody_sections),
            "bass_event_count": len(bass),
            "bass_kick_aligned_count": coordinated_bass,
            "melody_event_count": len(melody),
            "melody_harmony_bound_count": bound_melody,
        },
        "report_hash": "",
    }
    report["report_hash"] = composition_viability_report_hash(report)
    return report
