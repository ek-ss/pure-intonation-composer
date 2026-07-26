from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.exporters.midi import MidiArrangementTrack, MidiNote, arrangement_midi_bytes
from app.main import app
from fractions import Fraction

client = TestClient(app)

SCALE = ["1/1", "9/8", "5/4", "4/3", "3/2", "5/3", "7/4", "15/8"]

CHORDS = [
    {
        "id": "tonic",
        "name": "Just major triad",
        "mode": "absolute",
        "tones": ["1/1", "5/4", "3/2"],
        "tags": ["stable"],
    },
    {
        "id": "color",
        "name": "Suspended color",
        "mode": "ratio_template",
        "tones": ["1/1", "4/3", "3/2", "7/4"],
        "allowed_root_degrees": [0, 3, 4],
        "tags": ["color", "suspended"],
    },
    {
        "id": "diatonic",
        "name": "Diatonic triad",
        "mode": "degree_template",
        "tones": [0, 2, 4],
        "allowed_root_degrees": [0, 1, 3, 4],
        "tags": ["stable"],
    },
]


def generate_payload(profile: str, **overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "scale": {"ratios": SCALE, "base_frequency": 220},
        "chord_vocabulary": CHORDS,
        "genre_profile": profile,
        "clock": {"bars": 8, "beats_per_bar": 4, "subdivisions_per_beat": 4},
        "seed": 42,
    }
    payload.update(overrides)
    return payload


def test_profiles_endpoint_lists_builtins() -> None:
    response = client.get("/api/arrange/profiles")
    assert response.status_code == 200
    ids = [profile["id"] for profile in response.json()["profiles"]]
    assert ids == ["pop", "ambient", "alternative_rock", "future_bass"]


@pytest.mark.parametrize("profile", ["pop", "ambient", "alternative_rock", "future_bass"])
def test_generate_for_each_profile(profile: str) -> None:
    response = client.post("/api/arrange/generate", json=generate_payload(profile))
    assert response.status_code == 200, response.json()
    data = response.json()
    assert data["schema_version"] == "1.0.0"
    clock = data["clock"]
    assert clock["bars"] == 8
    # Sections exactly fill the declared bar ranges.
    cursor = 0
    for section in data["form"]:
        assert section["start_bar"] == cursor
        cursor += section["bars"]
    assert cursor == clock["bars"]
    # Events stay inside the clock and reference existing tracks/sections.
    track_ids = {track["id"] for track in data["tracks"]}
    section_ids = {section["id"] for section in data["form"]}
    assert data["events"], "expected at least one event"
    for event in data["events"]:
        assert 0 <= event["start_tick"] < clock["total_ticks"]
        assert event["start_tick"] + event["duration_ticks"] <= clock["total_ticks"]
        assert event["track_id"] in track_ids
        assert event["section_id"] in section_ids
        if event["kind"] == "note":
            assert event["ratio"] is not None
        else:
            assert event["drum_note"] is not None
    # Progression fits the form and records transition metrics.
    assert data["harmony_progression"]
    assert data["harmony_progression"][0]["transition"] is None
    assert data["harmony_progression"][1]["transition"] is not None


@pytest.mark.parametrize("profile", ["pop", "ambient", "alternative_rock", "future_bass"])
def test_default_vocabulary_produces_sounding_harmonic_variety(profile: str) -> None:
    response = client.post("/api/arrange/generate", json=generate_payload(profile))
    assert response.status_code == 200
    signatures = {
        tuple(sorted(slot["tones"]))
        for slot in response.json()["harmony_progression"]
    }
    assert len(signatures) >= 2


def test_profiles_produce_different_arrangements() -> None:
    outputs = {}
    for profile in ["pop", "ambient", "alternative_rock", "future_bass"]:
        response = client.post("/api/arrange/generate", json=generate_payload(profile))
        outputs[profile] = response.json()
    forms = {profile: [s["role"] for s in data["form"]] for profile, data in outputs.items()}
    assert len({tuple(roles) for roles in forms.values()}) > 1
    tempos = {profile: data["clock"]["tempo_bpm"] for profile, data in outputs.items()}
    assert tempos["ambient"] < tempos["future_bass"]
    event_counts = {profile: len(data["events"]) for profile, data in outputs.items()}
    assert len(set(event_counts.values())) > 1


def test_determinism_same_seed() -> None:
    first = client.post("/api/arrange/generate", json=generate_payload("pop"))
    second = client.post("/api/arrange/generate", json=generate_payload("pop"))
    assert first.json() == second.json()


def test_different_seed_changes_progression_or_events() -> None:
    first = client.post("/api/arrange/generate", json=generate_payload("pop", seed=1))
    second = client.post("/api/arrange/generate", json=generate_payload("pop", seed=999))
    assert first.json() != second.json()


def test_unknown_profile_is_422() -> None:
    response = client.post("/api/arrange/generate", json=generate_payload("grunge"))
    assert response.status_code == 422
    assert "available profiles" in response.json()["detail"]


def test_single_absolute_chord_is_422() -> None:
    payload = generate_payload("pop", chord_vocabulary=[CHORDS[0]])
    response = client.post("/api/arrange/generate", json=payload)
    assert response.status_code == 422


def test_impossible_degree_template_is_422() -> None:
    chord = dict(CHORDS[2], allowed_root_degrees=[30, 31])
    payload = generate_payload("pop", chord_vocabulary=[CHORDS[0], chord])
    response = client.post("/api/arrange/generate", json=payload)
    assert response.status_code == 422


def test_relaxed_preference_is_reported() -> None:
    # No chord carries the 'power' tag the rock profile prefers.
    response = client.post(
        "/api/arrange/generate", json=generate_payload("alternative_rock")
    )
    assert response.status_code == 200
    messages = [entry["message"] for entry in response.json()["decision_trace"]]
    assert any("preference relaxed" in message and "power" in message for message in messages)


def test_ambient_without_drums_has_no_drum_events() -> None:
    payload = generate_payload("ambient", controls={"drums_enabled": False})
    response = client.post("/api/arrange/generate", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert all(event["kind"] == "note" for event in data["events"])
    assert "drums" not in {track["id"] for track in data["tracks"]}


def test_midi_export_type1_multitrack() -> None:
    arrangement = client.post(
        "/api/arrange/generate", json=generate_payload("pop")
    ).json()
    response = client.post("/api/arrange/midi", json={"arrangement": arrangement})
    assert response.status_code == 200
    data = response.content
    assert data[:4] == b"MThd"
    assert data[8:10] == b"\x00\x01"  # format 1
    track_count = int.from_bytes(data[10:12], "big")
    assert track_count == len(arrangement["tracks"]) + 1
    assert data.count(b"MTrk") == track_count


def test_midi_section_markers_follow_bar_positions() -> None:
    arrangement = client.post(
        "/api/arrange/generate", json=generate_payload("pop")
    ).json()
    response = client.post("/api/arrange/midi", json={"arrangement": arrangement})
    assert response.status_code == 200
    assert _midi_markers(response.content) == [
        (
            section["start_bar"]
            * arrangement["clock"]["beats_per_bar"]
            * arrangement["clock"]["ticks_per_beat"],
            section["role"],
        )
        for section in arrangement["form"]
    ]


def test_midi_export_rejects_invalid_project() -> None:
    response = client.post("/api/arrange/midi", json={"arrangement": {"clock": {}}})
    assert response.status_code == 422


def test_midi_export_rejects_malformed_event_as_422() -> None:
    arrangement = client.post(
        "/api/arrange/generate", json=generate_payload("pop")
    ).json()
    del arrangement["events"][0]["start_tick"]
    response = client.post("/api/arrange/midi", json={"arrangement": arrangement})
    assert response.status_code == 422


def test_export_rejects_event_beyond_clock() -> None:
    arrangement = client.post(
        "/api/arrange/generate", json=generate_payload("pop")
    ).json()
    arrangement["events"][0]["duration_ticks"] = arrangement["clock"]["total_ticks"] + 1
    response = client.post("/api/arrange/render", json={"arrangement": arrangement})
    assert response.status_code == 422


def test_channel_budget_error_is_actionable() -> None:
    notes = tuple(
        MidiNote(Fraction(128 + index, 128), 0.0, 2.0, 100) for index in range(16)
    )
    with pytest.raises(ValueError, match="channel budget"):
        arrangement_midi_bytes(
            [MidiArrangementTrack("stack", notes)], 120.0, 4, 480, 220.0
        )


def test_render_returns_wav() -> None:
    arrangement = client.post(
        "/api/arrange/generate", json=generate_payload("pop", clock={"bars": 4})
    ).json()
    response = client.post("/api/arrange/render", json={"arrangement": arrangement})
    assert response.status_code == 200
    assert response.content[:4] == b"RIFF"
    assert response.content[8:12] == b"WAVE"


def test_render_rejects_preview_over_sample_budget() -> None:
    arrangement_response = client.post(
        "/api/arrange/generate",
        json=generate_payload(
            "ambient",
            clock={
                "bars": 128,
                "beats_per_bar": 4,
                "subdivisions_per_beat": 4,
            },
        ),
    )
    assert arrangement_response.status_code == 200
    response = client.post(
        "/api/arrange/render",
        json={"arrangement": arrangement_response.json()},
    )
    assert response.status_code == 422
    assert "preview limit" in response.json()["detail"]


def test_arrange_clock_rejects_subdivision_that_does_not_fit_midi_ticks() -> None:
    response = client.post(
        "/api/arrange/generate",
        json=generate_payload(
            "pop",
            clock={"bars": 4, "beats_per_bar": 4, "subdivisions_per_beat": 7},
        ),
    )
    assert response.status_code == 422


def test_custom_form_must_match_clock_bars() -> None:
    form = {
        "sections": [
            {"role": "verse", "bars": 3, "energy_start": 0.4, "energy_end": 0.6},
        ]
    }
    response = client.post(
        "/api/arrange/generate",
        json=generate_payload("pop", form=form, clock={"bars": 8}),
    )
    assert response.status_code == 422
    matching = client.post(
        "/api/arrange/generate",
        json=generate_payload("pop", form=form, clock={"bars": 3}),
    )
    assert matching.status_code == 200
    assert [s["role"] for s in matching.json()["form"]] == ["verse"]


def test_inline_profile_override() -> None:
    profiles = client.get("/api/arrange/profiles").json()["profiles"]
    assert profiles
    arrangement = client.post(
        "/api/arrange/generate", json=generate_payload("pop")
    ).json()
    inline = arrangement["resolved_profile"]["profile"]
    inline["id"] = "pop_custom"
    inline["display_name"] = "Pop Custom"
    response = client.post(
        "/api/arrange/generate", json=generate_payload({"x": 1}, genre_profile=inline)
    )
    assert response.status_code == 200
    assert response.json()["resolved_profile"]["profile"]["id"] == "pop_custom"


def test_meter_outside_profile_is_422() -> None:
    response = client.post(
        "/api/arrange/generate",
        json=generate_payload("pop", clock={"bars": 8, "beats_per_bar": 3}),
    )
    assert response.status_code == 422


def _midi_markers(data: bytes) -> list[tuple[int, str]]:
    assert data[:4] == b"MThd"
    assert data[14:18] == b"MTrk"
    track_length = int.from_bytes(data[18:22], "big")
    track = data[22 : 22 + track_length]
    markers: list[tuple[int, str]] = []
    tick = 0
    offset = 0
    while offset < len(track):
        delta, offset = _read_variable_length(track, offset)
        tick += delta
        assert track[offset] == 0xFF
        event_type = track[offset + 1]
        offset += 2
        length, offset = _read_variable_length(track, offset)
        payload = track[offset : offset + length]
        offset += length
        if event_type == 0x06:
            markers.append((tick, payload.decode("utf-8")))
        if event_type == 0x2F:
            break
    return markers


def _read_variable_length(data: bytes, offset: int) -> tuple[int, int]:
    value = 0
    while True:
        byte = data[offset]
        offset += 1
        value = (value << 7) | (byte & 0x7F)
        if not byte & 0x80:
            return value, offset
