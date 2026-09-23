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


def _named_track_note_ons(midi: bytes, track_name: str) -> int:
    position = 14
    for _ in range(int.from_bytes(midi[10:12], "big")):
        assert midi[position:position + 4] == b"MTrk"
        length = int.from_bytes(midi[position + 4:position + 8], "big")
        data = midi[position + 8:position + 8 + length]
        position += 8 + length
        index, name, notes = 0, None, 0

        def vlq() -> int:
            nonlocal index
            value = 0
            while True:
                part = data[index]
                index += 1
                value = (value << 7) | (part & 127)
                if part < 128:
                    return value

        while index < len(data):
            vlq()
            status = data[index]
            index += 1
            if status == 0xFF:
                kind = data[index]
                index += 1
                size = vlq()
                payload = data[index:index + size]
                index += size
                if kind == 3:
                    name = payload.decode("ascii")
                if kind == 47:
                    break
            elif status in (0xF0, 0xF7):
                index += vlq()
            elif status & 0xF0 in (0xC0, 0xD0):
                index += 1
            else:
                if status & 0xF0 == 0x90 and data[index + 1] != 0:
                    notes += 1
                index += 2
        if name == track_name:
            return notes
    raise AssertionError(f"MIDI track missing: {track_name}")


def test_evaluation_midi_is_deterministic_and_hash_bound() -> None:
    midi, manifest = export_evaluation_midi(_project())
    assert midi == export_evaluation_midi(_project())[0]
    assert midi.startswith(b"MThd\x00\x00\x00\x06\x00\x00\x00\x01\x01\xe0MTrk")
    assert midi.endswith(b"\x00\xff\x2f\x00")
    assert manifest["algorithm"] == "smf0-per-note-channel-pitch-bend/v1"
    assert manifest["midi_hash"] == "sha256:" + hashlib.sha256(midi).hexdigest()
    assert manifest["manifest_hash"].startswith("sha256:")


def test_piano_track_uses_acoustic_piano_program_without_changing_other_roles() -> None:
    project = _project()
    project["tracks"].append({"id": "trk_piano", "role": "texture"})
    project["events"].append({
        "id": "ev_cccccccccccccccccccc", "kind": "note", "track_id": "trk_piano",
        "start_tick": 480, "duration_ticks": 240, "velocity": 80, "ratio": "1/1",
    })
    legacy, _ = export_evaluation_midi(project)
    midi, manifest = export_evaluation_midi(project, program_by_track={"trk_piano": 0})
    assert midi != legacy
    assert midi[8:12] == b"\x00\x01\x00\x04"  # conductor + three named tracks
    assert manifest["schema_version"] == "1.1.0"
    assert manifest["program_by_track"] == {"trk_piano": 0}
    assert manifest["algorithm"] == "smf1-named-tracks-per-note-pitch-bend/v1"
    assert b"\xff\x03\x09trk_piano" in midi
    assert b"\xc0\x00" in midi
    assert _named_track_note_ons(midi, "trk_piano") == 1
    assert _named_track_note_ons(midi, "trk_mel") == 1
    assert manifest["midi_hash"] == "sha256:" + hashlib.sha256(midi).hexdigest()
