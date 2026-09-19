from __future__ import annotations

import copy

from app.songprogram.composition_viability import (
    composition_viability_report_hash,
    extract_composition_viability,
)


def _inputs() -> tuple[dict, dict]:
    form = [
        {"id": "sec_000", "role": "intro", "bars": 2, "start_bar": 0},
        {"id": "sec_001", "role": "build", "bars": 2, "start_bar": 2},
        {"id": "sec_002", "role": "outro", "bars": 2, "start_bar": 4},
    ]
    tracks = [
        {"id": "trk_drums", "role": "drums"},
        {"id": "trk_bass", "role": "bass"},
        {"id": "trk_harmony", "role": "harmony"},
        {"id": "trk_melody", "role": "melody"},
    ]
    events = []
    harmony_occurrences = []
    for section_index, section in enumerate(form):
        section_start = section["start_bar"] * 1920
        for bar in range(2):
            start = section_start + bar * 1920
            for role, offset in (("drums", 0), ("drums", 960), ("bass", 0)):
                events.append(
                    {
                        "kind": "drum" if role == "drums" else "note",
                        "track_id": f"trk_{role}",
                        "section_id": section["id"],
                        "start_tick": start + offset,
                        "duration_ticks": 120,
                        "ratio": None if role == "drums" else "1/1",
                        "source": {"material_instance_id": f"shared_{role}"},
                    }
                )
            events.append(
                {
                    "kind": "note", "track_id": "trk_harmony", "section_id": section["id"],
                    "start_tick": start, "duration_ticks": 1920,
                    "ratio": "1/1" if section_index != 1 else "3/2",
                    "source": {"material_instance_id": "shared_harmony"},
                }
            )
            harmony_occurrences.append(
                {"section_id": section["id"], "start_tick": start, "duration_ticks": 1920}
            )
        events.append(
            {
                "kind": "note", "track_id": "trk_melody", "section_id": section["id"],
                "start_tick": section_start + 480, "duration_ticks": 240, "ratio": "1/1",
                "source": {"material_instance_id": "shared_motif"},
            }
        )
    return (
        {"program_id": "sp_test"},
        {
            "project_id": "prj_test", "clock": {"beats_per_bar": 4, "ticks_per_beat": 480},
            "form": form, "tracks": tracks, "events": events,
            "harmony_occurrences": harmony_occurrences,
        },
    )


def test_stage_d_report_is_deterministic_bounded_and_self_hashed() -> None:
    program, project = _inputs()
    first = extract_composition_viability(program, project)
    assert first == extract_composition_viability(program, project)
    assert first["report_hash"] == composition_viability_report_hash(first)
    assert all(0 <= value <= 10000 for value in first["metrics_q"].values())
    assert first["non_authoritative"] is True
    assert first["usage"] == "g1_calibration_feature_only_not_archive_admission"


def test_form_shuffle_reduces_only_diagnostic_not_authority() -> None:
    program, project = _inputs()
    baseline = extract_composition_viability(program, project)
    broken = copy.deepcopy(project)
    broken["form"][0]["role"], broken["form"][-1]["role"] = (
        broken["form"][-1]["role"],
        broken["form"][0]["role"],
    )
    result = extract_composition_viability(program, broken)
    assert result["metrics_q"]["formal_arc_consistency_q"] < baseline["metrics_q"][
        "formal_arc_consistency_q"
    ]
    assert result["non_authoritative"] is True


def test_continuity_resolves_material_instances_to_source_material() -> None:
    program, project = _inputs()
    for ordinal, event in enumerate(project["events"]):
        event["source"]["material_instance_id"] = f"mi_{ordinal}"
    project["material_instances"] = [
        {
            "id": event["source"]["material_instance_id"],
            "material_id": f"shared_{event['track_id']}",
        }
        for event in project["events"]
    ]
    result = extract_composition_viability(program, project)
    assert result["metrics_q"]["adjacent_section_continuity_q"] == 10000
