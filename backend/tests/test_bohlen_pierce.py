from fractions import Fraction

from fastapi.testclient import TestClient

from app.bp.engine import BPChordSearchRequest, chord_search, generate_scale, normalize_tritave, parse_ratio
from app.main import app


client = TestClient(app)


def test_tritave_normalization_preserves_exact_ratios() -> None:
    assert normalize_tritave(Fraction(5)) == (Fraction(5, 3), 1)
    assert normalize_tritave(Fraction(7)) == (Fraction(7, 3), 1)
    assert normalize_tritave(Fraction(5, 9)) == (Fraction(5, 3), -1)
    normalized, register = normalize_tritave(Fraction(25, 7))
    assert Fraction(1) <= normalized < 3
    assert normalized * 3**register == Fraction(25, 7)
    assert parse_ratio("3^-1 * 5^2") == Fraction(25, 3)
    assert parse_ratio("{a:-1,b:1,c:0}") == Fraction(5, 3)


def test_bp_scale_generation_has_exact_coordinates_and_edt_comparison() -> None:
    scale = generate_scale({"preset": "bounded-lattice", "b_min": -2, "b_max": 2, "c_min": -2, "c_max": 2, "max_pitches": 13})
    assert scale["equave"] == 3
    assert 3 <= len(scale["pitches"]) <= 13
    assert scale["pitches"][0]["ratio"] == "1/1"
    for pitch in scale["pitches"]:
        ratio = Fraction(pitch["ratio"])
        assert 1 <= ratio < 3
        assert pitch["b"] == pitch["prime_exponents"].get("5", 0)
        assert 0 <= pitch["edt13_step"] < 13


def test_bp_chord_progression_and_composition_are_reproducible() -> None:
    scale = generate_scale({"preset": "bounded-lattice", "max_pitches": 9})
    searched = chord_search(BPChordSearchRequest(pitches=scale["pitches"], voice_count=3, max_results=16))
    assert searched["chords"]
    first_chord = searched["chords"][0]
    assert len(first_chord["ratios"]) == 3
    assert 0 <= first_chord["metrics"]["total_score"] <= 1
    progression_request = {
        "chords": searched["chords"],
        "length": 6,
        "center_chord_id": first_chord["id"],
        "end_chord_id": first_chord["id"],
        "target_tension_curve": [0.1, 0.3, 0.7, 0.9, 0.4, 0.1],
        "method": "contrast-resolution",
        "seed": 357,
    }
    first = client.post("/api/bp/progressions/search", json=progression_request)
    second = client.post("/api/bp/progressions/search", json=progression_request)
    assert first.status_code == 200
    assert first.json() == second.json()
    progression = first.json()["progression"]
    assert progression[-1]["chord_id"] == first_chord["id"]
    composition_request = {
        "scale": scale["pitches"],
        "chords": searched["chords"],
        "progression": progression,
        "duration_bars": 4,
        "seed": 5357,
    }
    composition = client.post("/api/bp/compose/generate", json=composition_request)
    assert composition.status_code == 200
    project = composition.json()
    assert {event["part_role"] for event in project["events"]} >= {"harmony", "bass", "melody", "kick", "snare"}
    assert project["metrics"]["tension_curve_match"] >= 0


def test_bp_download_endpoints_return_midi_wav_and_tritave_scala() -> None:
    events = [{"part_role": "harmony", "ratio": "5/3", "start_beat": 0, "duration_beats": 0.1, "velocity": 90}]
    midi = client.post("/api/bp/export/midi", json={"events": events, "tempo_bpm": 120, "root_frequency_hz": 110})
    assert midi.status_code == 200
    assert midi.content.startswith(b"MThd")
    wav = client.post("/api/bp/render/audio", json={"events": events, "tempo_bpm": 240, "root_frequency_hz": 110, "sample_rate": 8000})
    assert wav.status_code == 200
    assert wav.content.startswith(b"RIFF")
    scala = client.post("/api/bp/export/scala", json={"name": "BP test", "pitches": [{"ratio": "1/1"}, {"ratio": "5/3"}, {"ratio": "7/3"}]})
    assert scala.status_code == 200
    assert scala.text.rstrip().endswith("3/1")


def test_bp_api_rejects_invalid_manual_scale() -> None:
    response = client.post("/api/bp/scales/generate", json={"preset": "manual", "ratios": []})
    assert response.status_code == 422
