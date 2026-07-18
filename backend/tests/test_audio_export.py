from fractions import Fraction
from math import log2

import pytest
from fastapi.testclient import TestClient

from app.audio.render import Envelope, NoteEvent, render_wav
from app.exporters.midi import MidiNote, microtonal_midi_bytes, midi_bytes
from app.main import app


client = TestClient(app)


def test_offline_render_produces_a_wav_file() -> None:
    data = render_wav(
        [NoteEvent(Fraction(3, 2), 0, 0.03)],
        waveform="additive",
        envelope=Envelope(0.005, 0.005, 0.5, 0.01),
        sample_rate=8000,
    )
    assert data[:4] == b"RIFF"
    assert b"WAVE" in data[:16]


def test_midi_export_produces_a_standard_midi_header() -> None:
    assert midi_bytes([MidiNote(Fraction(3, 2), 0, 1)])[:4] == b"MThd"


def test_render_and_export_apis_return_downloads() -> None:
    render = client.post(
        "/api/render/wav",
        json={"events": [{"ratio": "3/2", "start_seconds": 0, "duration_seconds": 0.02}], "sample_rate": 8000},
    )
    assert render.status_code == 200 and render.content[:4] == b"RIFF"
    midi = client.post(
        "/api/export/midi",
        json={"notes": [{"ratio": "3/2", "start_beats": 0, "duration_beats": 1}]},
    )
    assert midi.status_code == 200 and midi.content[:4] == b"MThd"


def test_microtonal_midi_produces_a_standard_midi_header() -> None:
    assert microtonal_midi_bytes([MidiNote(Fraction(3, 2), 0, 1)])[:4] == b"MThd"


def test_microtonal_midi_emits_pitch_bend_matching_the_exact_ratio() -> None:
    data = microtonal_midi_bytes([MidiNote(Fraction(3, 2), 0, 1)])
    semitones = 12 * log2(220 * float(Fraction(3, 2)) / 440)
    bend = semitones - round(semitones)
    assert abs(bend * 100 - 1.955) < 0.01  # 702-cent fifth bends ~+2 cents off E4
    value = 8192 + round(bend / 2 * 8192)
    assert bytes((0xE0, value & 0x7F, value >> 7)) in data
    assert bytes((0x90, 69 + round(semitones), 100)) in data


def test_microtonal_midi_skips_channel_10_and_reuses_channels() -> None:
    notes = [MidiNote(Fraction(3, 2), float(index), 0.5) for index in range(16)]
    data = microtonal_midi_bytes(notes)
    assert bytes((0x9A, 64, 100)) in data  # 11th note lands on channel 11 (0-indexed 10)
    for skipped in (0x99, 0x89, 0xE9):
        assert bytes((skipped,)) not in data  # nothing on GM percussion channel 10
    assert data.count(bytes((0x90, 64, 100))) == 2  # 16th note reuses channel 1


def test_microtonal_midi_validates_pitch_bend_range() -> None:
    note = [MidiNote(Fraction(3, 2), 0, 1)]
    with pytest.raises(ValueError):
        microtonal_midi_bytes(note, pitch_bend_range_semitones=0)
    with pytest.raises(ValueError):
        microtonal_midi_bytes(note, pitch_bend_range_semitones=49)


def test_midi_export_endpoint_with_pitch_bend_retunes_notes() -> None:
    response = client.post(
        "/api/export/midi",
        json={"notes": [{"ratio": "3/2", "start_beats": 0, "duration_beats": 1}], "pitch_bend": True},
    )
    assert response.status_code == 200 and response.content[:4] == b"MThd"
    semitones = 12 * log2(220 * 1.5 / 440)
    value = 8192 + round((semitones - round(semitones)) / 2 * 8192)
    assert bytes((0xE0, value & 0x7F, value >> 7)) in response.content


def test_midi_export_endpoint_rejects_invalid_pitch_bend_range() -> None:
    response = client.post(
        "/api/export/midi",
        json={
            "notes": [{"ratio": "3/2", "start_beats": 0, "duration_beats": 1}],
            "pitch_bend": True,
            "pitch_bend_range_semitones": 0,
        },
    )
    assert response.status_code == 422
