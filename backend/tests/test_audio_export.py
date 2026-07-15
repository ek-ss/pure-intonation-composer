from fractions import Fraction

from fastapi.testclient import TestClient

from app.audio.render import Envelope, NoteEvent, render_wav
from app.exporters.midi import MidiNote, midi_bytes
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
