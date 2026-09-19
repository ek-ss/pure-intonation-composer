from __future__ import annotations

from copy import deepcopy

from app.songprogram.song_validity import assess_completed_song


def _inputs() -> tuple[dict, dict, dict, dict, dict]:
    sections = [{"id": f"s{index}", "bars": bars} for index, bars in enumerate((6, 5, 5))]
    realizations = [
        {"section_id": "s0", "material_id": "m", "pitch_transforms": [], "rhythm_transforms": []},
        {"section_id": "s1", "material_id": "m", "pitch_transforms": [{"kind": "transpose"}], "rhythm_transforms": []},
        {"section_id": "s2", "material_id": "n", "pitch_transforms": [], "rhythm_transforms": []},
    ]
    program = {"form": sections, "realizations": realizations}
    tracks = [
        {"id": "d", "role": "drums", "maximum_polyphony": 2},
        {"id": "b", "role": "bass", "maximum_polyphony": 2},
        {"id": "h", "role": "harmony", "maximum_polyphony": 2},
    ]
    events = [
        {"kind": "drum", "track_id": "d", "start_tick": 0, "duration_ticks": 10},
        {"kind": "note", "track_id": "b", "start_tick": 0, "duration_ticks": 10},
        {"kind": "note", "track_id": "h", "start_tick": 0, "duration_ticks": 10},
    ]
    project = {"tracks": tracks, "events": events}
    return (
        program,
        project,
        {"overall_coverage_basis_points": 9000},
        {"status": "passed", "distinct_role_mask_count": 2},
        {"fully_silent_one_second_window_count": 0},
    )


def test_completed_song_hard_gate_passes_only_all_checks() -> None:
    result = assess_completed_song(*_inputs()[:2], symbolic_coverage=_inputs()[2], arrangement=_inputs()[3], pcm_continuity=_inputs()[4])
    assert result["status"] == "passed"
    assert result["archive_eligible"] is True
    assert result["failure_codes"] == []


def test_completed_song_hard_gate_exposes_recall_failure() -> None:
    program, project, coverage, arrangement, continuity = _inputs()
    invalid = deepcopy(program)
    invalid["realizations"][1]["pitch_transforms"] = []
    result = assess_completed_song(invalid, project, symbolic_coverage=coverage, arrangement=arrangement, pcm_continuity=continuity)
    assert result["archive_eligible"] is False
    assert result["failure_codes"] == ["non_identity_transformed_recall_across_sections"]
