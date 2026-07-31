from fractions import Fraction

from fastapi.testclient import TestClient

from app.composition.bass import generate_bass
from app.composition.melody import generate_melody
from app.main import app
from app.tuning.analysis import cents


client = TestClient(app)
CHORDS = [[Fraction(1), Fraction(5, 4), Fraction(3, 2)], [Fraction(9, 8), Fraction(4, 3), Fraction(5, 3)]]


def test_bass_supports_each_chord_and_respects_leap_limit() -> None:
    bass = generate_bass(CHORDS, max_leap_cents=900)
    assert len(bass.notes) == len(CHORDS)
    assert all(leap <= 900 for leap in bass.leap_cents)
    assert all(-2400 <= cents(note) <= 0 for note in bass.notes)


def test_melody_is_deterministic_and_stays_in_register() -> None:
    first = generate_melody(CHORDS, voice_count=2, seed=42, register_low_cents=600, register_high_cents=2400)
    second = generate_melody(CHORDS, voice_count=2, seed=42, register_low_cents=600, register_high_cents=2400)
    assert first == second
    assert all(600 <= cents(note) <= 2400 for voice in first.voices for note in voice)


def test_bass_and_melody_apis_return_tracks() -> None:
    payload = {"chords": [["1/1", "5/4", "3/2"], ["9/8", "4/3", "5/3"]]}
    assert client.post("/api/compose/bass", json=payload).status_code == 200
    melody = client.post("/api/compose/melody", json={**payload, "voice_count": 2, "seed": 4})
    assert melody.status_code == 200
    assert len(melody.json()["voices"]) == 2
