from __future__ import annotations

import hashlib

from app.songprogram.midi_export import export_evaluation_midi


def _project() -> dict:
    return {
        "clock": {"tempo_milli_bpm": 120000, "beats_per_bar": 4, "ticks_per_beat": 480},
        "lattice": {"base_frequency_millihz": 440000},
        "tracks": [
            {"id": "trk_drm", "role": "drums"},
            {"id": "trk_mel", "role": "melody"},
        ],
        "events": [
            {
                "id": "ev_aaaaaaaaaaaaaaaaaaaa",
                "kind": "note",
                "track_id": "trk_mel",
                "start_tick": 0,
                "duration_ticks": 480,
                "velocity": 100,
                "ratio": "3/2",
            },
            {
                "id": "ev_bbbbbbbbbbbbbbbbbbbb",
                "kind": "drum",
                "track_id": "trk_drm",
                "start_tick": 0,
                "duration_ticks": 120,
                "velocity": 110,
                "drum_note": 36,
            },
        ],
    }


def test_evaluation_midi_is_deterministic_and_hash_bound() -> None:
    midi, manifest = export_evaluation_midi(_project())
    assert midi == export_evaluation_midi(_project())[0]
    assert midi.startswith(b"MThd\x00\x00\x00\x06\x00\x00\x00\x01\x01\xe0MTrk")
    assert midi.endswith(b"\x00\xff\x2f\x00")
    assert manifest["algorithm"] == "smf0-per-note-channel-pitch-bend/v1"
    assert manifest["midi_hash"] == "sha256:" + hashlib.sha256(midi).hexdigest()
    assert manifest["manifest_hash"].startswith("sha256:")
