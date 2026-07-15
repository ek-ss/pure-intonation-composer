from fractions import Fraction

import pytest
from fastapi.testclient import TestClient

from app.composition.voice_leading import voice_lead
from app.main import app


client = TestClient(app)


def test_voice_leading_keeps_voices_ordered_and_respects_leap_limit() -> None:
    progression = voice_lead(
        [
            [Fraction(1), Fraction(5, 4), Fraction(3, 2)],
            [Fraction(9, 8), Fraction(4, 3), Fraction(5, 3)],
        ],
        max_leap_cents=300,
    )
    assert all(list(chord) == sorted(chord) for chord in progression.chords)
    assert all(leap <= 300 for leaps in progression.leap_cents for leap in leaps)
    assert progression.leap_cents[0] == (0.0, 0.0, 0.0)


def test_voice_leading_rejects_an_impossible_leap_limit() -> None:
    with pytest.raises(ValueError, match="max_leap_cents"):
        voice_lead(
            [[Fraction(1)], [Fraction(3, 2)]],
            max_leap_cents=10,
            register_low_cents=0,
            register_high_cents=1200,
        )


def test_voice_leading_api_returns_non_crossing_voicings() -> None:
    response = client.post(
        "/api/compose/voice-leading",
        json={
            "chords": [["1/1", "5/4", "3/2"], ["9/8", "4/3", "5/3"]],
            "max_leap_cents": 300,
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["voice_count"] == 3
    assert all(
        [voice["cents"] for voice in chord] == sorted(voice["cents"] for voice in chord)
        for chord in payload["chords"]
    )
