from app.songprogram.lattice_pitch_diagnostic import lattice_pitch_diagnostic


def test_exact_octaves_voice_time_and_distinct_pitch_classes() -> None:
    project = {
        "tracks": [{"id": "h", "role": "harmony"}, {"id": "m", "role": "melody"},
                   {"id": "d", "role": "drums"}],
        "events": [
            {"kind": "note", "track_id": "h", "ratio": "1/1", "duration_ticks": 100},
            {"kind": "note", "track_id": "h", "ratio": "2/1", "duration_ticks": 100},
            {"kind": "note", "track_id": "m", "ratio": "7/4", "duration_ticks": 10},
            {"kind": "note", "track_id": "m", "ratio": "7/2", "duration_ticks": 10},
            {"kind": "drum", "track_id": "d", "duration_ticks": 1000},
        ],
    }
    result = lattice_pitch_diagnostic(project)
    assert result["exposed_note_count"] == 2
    assert result["distinct_pitch_class_count"] == 2
    assert result["exposed_distinct_pitch_class_count"] == 1
    assert result["exposed_note_share_q"] == 5000
    assert result["exposed_duration_share_q"] == 909
    assert 31_000 < result["maximum_gap_millicents"] < 32_000
    assert result["by_role"]["melody"]["exposed_duration_ticks"] == 20


def test_threshold_and_empty_song_are_reference_diagnostics() -> None:
    project = {"tracks": [{"id": "h", "role": "harmony"}], "events": [
        {"kind": "note", "track_id": "h", "ratio": "10/9", "duration_ticks": 20},
    ]}
    assert lattice_pitch_diagnostic(project)["exposed_duration_share_q"] == 10000
    assert lattice_pitch_diagnostic(project, threshold_millicents=20_000)["exposed_note_count"] == 0
    assert lattice_pitch_diagnostic({"tracks": [], "events": []})["exposed_duration_share_q"] == 0
