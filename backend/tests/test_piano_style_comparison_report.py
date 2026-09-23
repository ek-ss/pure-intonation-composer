from __future__ import annotations

from app.songprogram.midi_export import export_evaluation_midi
from tools.evaluate_piano_style_comparison import evaluate, midi_track_notes


def test_comparison_reports_missing_cases_without_claiming_completion(tmp_path) -> None:
    report = evaluate(tmp_path, 2)
    assert report["complete"] is False
    assert report["rows"] == []
    assert len(report["missing"]) == 8
    assert all(summary["completed"] == 0 for summary in report["summary"].values())


def test_midi_counter_reads_only_the_named_piano_track(tmp_path) -> None:
    project = {
        "clock": {"tempo_milli_bpm": 120000, "beats_per_bar": 4, "ticks_per_beat": 480},
        "lattice": {"base_frequency_millihz": 440000},
        "tracks": [{"id": "trk_piano", "role": "texture"},
                   {"id": "trk_melody", "role": "melody"}],
        "events": [
            {"id": "ev_a", "kind": "note", "track_id": "trk_piano", "start_tick": 0,
             "duration_ticks": 240, "ratio": "1/1", "velocity": 80},
            {"id": "ev_b", "kind": "note", "track_id": "trk_melody", "start_tick": 0,
             "duration_ticks": 240, "ratio": "3/2", "velocity": 80},
        ],
    }
    midi, _ = export_evaluation_midi(project, program_by_track={"trk_piano": 0})
    path = tmp_path / "test.mid"
    path.write_bytes(midi)
    assert midi_track_notes(path, "trk_piano") == (1, {0})
    assert midi_track_notes(path, "trk_melody") == (1, {81})
