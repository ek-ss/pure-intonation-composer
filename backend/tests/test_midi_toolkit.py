from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def _request() -> dict[str, object]:
    return {
        "notes": [
            {"midi_note": 60, "start_beats": 0.09, "duration_beats": 0.43, "velocity": 88},
            {"midi_note": 64, "start_beats": 0.10, "duration_beats": 0.46, "velocity": 92},
            {"midi_note": 67, "start_beats": 0.11, "duration_beats": 0.44, "velocity": 84},
            {"midi_note": 62, "start_beats": 0.39, "duration_beats": 0.24, "velocity": 104},
            {"midi_note": 69, "start_beats": 1.08, "duration_beats": 0.51, "velocity": 78},
        ],
        "root_midi": 60,
        "scale_ratios": ["1/1", "9/8", "5/4", "4/3", "3/2", "5/3", "15/8"],
        "quantize_division": 4,
        "quantize_strength": 1,
        "maximum_polyphony": 3,
    }


def test_midi_toolkit_quantizes_maps_and_groups_performance() -> None:
    first = client.post("/api/midi-toolkit/process", json=_request())
    second = client.post("/api/midi-toolkit/process", json=_request())
    assert first.status_code == 200
    assert first.json() == second.json()
    project = first.json()
    assert project["feature"] == "midi-creator-toolkit"
    assert project["analysis"]["captured_notes"] == 5
    assert project["analysis"]["motif_steps"] == 3
    assert project["analysis"]["anchor_chord"][0] == "1/1"
    assert project["analysis"]["prime_basis"] == [3, 5]
    motif = project["motif"]
    assert motif["notes"][0]["ratio"] == "1/1"
    assert motif["notes"][0]["harmony_tones"] == ["5/4", "3/2"]
    assert motif["polyphony_signature"]["maximum"] == 3
    assert {note["ratio"] for note in project["midi_notes"]} <= {
        "1/1", "9/8", "5/4", "3/2", "5/3"
    }
    midi = client.post(
        "/api/export/midi",
        json={
            "notes": project["midi_notes"],
            "base_frequency": 261.626,
            "pitch_bend": True,
        },
    )
    assert midi.status_code == 200
    assert midi.content.startswith(b"MThd")


def test_midi_toolkit_limits_polyphony_and_preserves_swing() -> None:
    request = _request()
    request["maximum_polyphony"] = 2
    request["swing"] = 0.25
    response = client.post("/api/midi-toolkit/process", json=request)
    assert response.status_code == 200
    project = response.json()
    assert project["motif"]["polyphony_signature"]["maximum"] == 2
    assert project["warnings"] == ["Reduced 1 notes to the maximum polyphony"]
    assert project["captured_notes"][3]["start_beats"] == 0.3125


def test_midi_toolkit_rejects_invalid_scales() -> None:
    request = _request()
    request["scale_ratios"] = ["1/1", "2/1", "3/2"]
    response = client.post("/api/midi-toolkit/process", json=request)
    assert response.status_code == 422


def test_midi_toolkit_lists_composer_scales_and_generators() -> None:
    response = client.get("/api/midi-toolkit/scales")
    assert response.status_code == 200
    catalog = response.json()
    preset_ids = {preset["id"] for preset in catalog["presets"]}
    assert {
        "fractional-pop-bright",
        "kawaii-prime-lattice",
        "jpop-minor-third-field",
        "bohlen-pierce-pure",
    } <= preset_ids
    assert catalog["generators"] == ["prime-limit-explorer"]
    bohlen_pierce = next(
        preset for preset in catalog["presets"] if preset["id"] == "bohlen-pierce-pure"
    )
    assert bohlen_pierce["equave_ratio"] == "3/1"


def test_midi_toolkit_maps_a_non_octave_equave() -> None:
    request = _request()
    request["notes"] = [
        {"midi_note": 72, "start_beats": 0, "duration_beats": 0.5, "velocity": 96}
    ]
    request["scale_id"] = "bohlen-pierce-pure"
    request["scale_name"] = "Pure 3:5:7 tritave"
    request["equave_ratio"] = "3/1"
    request["scale_ratios"] = ["1/1", "9/7", "7/5", "5/3", "15/7", "7/3", "25/9"]
    response = client.post("/api/midi-toolkit/process", json=request)
    assert response.status_code == 200
    project = response.json()
    assert project["settings"]["equave_ratio"] == "3/1"
    assert project["midi_notes"][0]["ratio"] == "3/1"


def test_midi_toolkit_maps_one_white_key_to_each_scale_degree() -> None:
    request = _request()
    request["notes"] = [
        {"midi_note": note, "start_beats": index / 4, "duration_beats": 0.2, "velocity": 96}
        for index, note in enumerate([60, 62, 64, 65, 67, 69, 71, 72])
    ]
    request["scale_ratios"] = [
        "1/1", "9/8", "6/5", "5/4", "4/3", "3/2", "13/8", "5/3", "7/4"
    ]
    response = client.post("/api/midi-toolkit/process", json=request)
    assert response.status_code == 200
    assert [note["ratio"] for note in response.json()["midi_notes"]] == [
        "1/1", "9/8", "6/5", "5/4", "4/3", "3/2", "13/8", "5/3"
    ]


def test_midi_toolkit_rejects_black_keys_for_white_key_mapping() -> None:
    request = _request()
    request["notes"] = [{"midi_note": 61, "start_beats": 0, "duration_beats": 0.5}]
    response = client.post("/api/midi-toolkit/process", json=request)
    assert response.status_code == 422
    assert "white MIDI keys only" in response.json()["detail"][0]["msg"]
