from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from test_arrangement import generate_payload

client = TestClient(app)


def _arrangement(bars: int = 8) -> dict[str, object]:
    response = client.post(
        "/api/arrange/generate",
        json=generate_payload(
            "pop",
            clock={
                "bars": bars,
                "beats_per_bar": 4,
                "subdivisions_per_beat": 4,
            },
        ),
    )
    assert response.status_code == 200
    return response.json()


def _phase_payload(
    arrangement: dict[str, object],
    **overrides: object,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "arrangement": arrangement,
        "mode": "shared_chord_clock",
        "stream_a": {
            "id": "a",
            "rhythm": {
                "source": "euclidean",
                "cycle_steps": 16,
                "pulses": 4,
                "rotation": 0,
                "gate": 0.9,
            },
            "register_low_cents": 0,
            "register_high_cents": 2400,
            "pan": -0.25,
        },
        "stream_b": {
            "id": "b",
            "rhythm": {
                "source": "euclidean",
                "cycle_steps": 15,
                "pulses": 5,
                "rotation": 2,
                "gate": 0.65,
            },
            "register_low_cents": 1200,
            "register_high_cents": 3600,
            "pan": 0.25,
        },
        "phase_plan": {
            "process": "polymetric",
            "initial_offset_steps": 2,
            "convergence_points": [
                {"bar": 0, "protected": True},
                {"bar": arrangement["clock"]["bars"], "protected": True},
            ],
        },
        "seed": 42,
    }
    payload.update(overrides)
    return payload


def test_shared_clock_phase_is_deterministic_and_preserves_active_chord() -> None:
    arrangement = _arrangement()
    payload = _phase_payload(arrangement)
    first = client.post("/api/arrange/phase-shift", json=payload)
    second = client.post("/api/arrange/phase-shift", json=payload)
    assert first.status_code == 200, first.json()
    assert first.json() == second.json()
    data = first.json()
    assert data["metadata"]["feature"] == "harmonic-phase-shift"
    assert data["source_arrangement_digest"]
    assert data["phase_shift"]["metrics"]["rhythm_distinctness"][
        "onset_hamming_distance"
    ] >= 0.15
    slots = arrangement["harmony_progression"]
    for event in data["events"]:
        if event["phase_stream_id"] is None:
            continue
        source_slot = next(
            slot
            for slot in slots
            if slot["start_tick"]
            <= event["start_tick"]
            < slot["start_tick"] + slot["duration_ticks"]
        )
        assert event["source_slot_index"] == source_slot["index"]
        assert event["source_chord_id"] == source_slot["instance_id"]


def test_independent_clock_preserves_progression_order_and_converges() -> None:
    arrangement = _arrangement()
    payload = _phase_payload(
        arrangement,
        mode="independent_chord_clock",
        stream_a={
            "id": "a",
            "rhythm": {"cycle_steps": 8, "pulses": 3},
            "chord_durations": [8, 12],
            "register_low_cents": 0,
            "register_high_cents": 2400,
        },
        stream_b={
            "id": "b",
            "rhythm": {"cycle_steps": 7, "pulses": 2},
            "chord_durations": [5, 9],
            "register_low_cents": 1200,
            "register_high_cents": 3600,
        },
        phase_plan={
            "process": "convergent",
            "initial_offset_steps": 3,
            "convergence_points": [
                {"bar": 0, "protected": True},
                {"bar": 4, "protected": True},
                {"bar": 8, "protected": True},
            ],
        },
    )
    response = client.post("/api/arrange/phase-shift", json=payload)
    assert response.status_code == 200, response.json()
    data = response.json()
    source_order = [slot["index"] for slot in arrangement["harmony_progression"]]
    for stream_id in ("a", "b"):
        visits = []
        for event in data["events"]:
            if event["phase_stream_id"] != stream_id:
                continue
            if not visits or visits[-1] != event["source_slot_index"]:
                visits.append(event["source_slot_index"])
        for current, following in zip(visits, visits[1:]):
            expected = source_order[
                (source_order.index(current) + 1) % len(source_order)
            ]
            assert following == expected
    assert all(
        anchor["met"]
        for anchor in data["phase_shift"]["convergence_points"]
        if anchor["protected"]
    )


def test_discrete_phase_schedule_changes_offset() -> None:
    arrangement = _arrangement(4)
    payload = _phase_payload(
        arrangement,
        phase_plan={
            "process": "discrete",
            "initial_offset_steps": 1,
            "increment_steps": 1,
            "update_interval_bars": 1,
            "direction": "forward",
        },
    )
    response = client.post("/api/arrange/phase-shift", json=payload)
    assert response.status_code == 200
    offsets = [
        item["rhythm_offset"]
        for item in response.json()["phase_shift"]["phase_schedule"]
    ]
    assert offsets == [1, 2, 3, 4]


def test_adaptive_overlap_records_omitted_tones() -> None:
    arrangement = _arrangement(4)
    payload = _phase_payload(
        arrangement,
        overlap_policy={
            "resolution": "adaptive_voicing",
            "maximum_combined_density": 1,
            "maximum_active_tones": 3,
            "maximum_overlap_cost": 12,
            "minimum_hamming_distance": 0.1,
        },
    )
    response = client.post("/api/arrange/phase-shift", json=payload)
    assert response.status_code == 200
    assert (
        response.json()["phase_shift"]["metrics"]["optional_tone_omissions"] > 0
    )


def test_phase_project_exports_midi_and_wav() -> None:
    arrangement = _arrangement(4)
    phase_response = client.post(
        "/api/arrange/phase-shift", json=_phase_payload(arrangement)
    )
    assert phase_response.status_code == 200
    project = phase_response.json()
    midi = client.post("/api/arrange/midi", json={"arrangement": project})
    wav = client.post("/api/arrange/render", json={"arrangement": project})
    assert midi.status_code == 200
    assert midi.content[:4] == b"MThd"
    assert wav.status_code == 200
    assert wav.content[:4] == b"RIFF"


def test_fractional_phase_is_actionable_422() -> None:
    arrangement = _arrangement(4)
    response = client.post(
        "/api/arrange/phase-shift",
        json=_phase_payload(
            arrangement,
            phase_plan={"process": "fractional"},
        ),
    )
    assert response.status_code == 422
    assert "HP5" in response.json()["detail"]


def test_identical_full_cycles_fail_distinctness_validation() -> None:
    arrangement = _arrangement(4)
    full = {
        "source": "manual",
        "pattern": [1, 1, 1, 1],
        "cycle_steps": 4,
    }
    response = client.post(
        "/api/arrange/phase-shift",
        json=_phase_payload(
            arrangement,
            stream_a={"id": "a", "rhythm": full},
            stream_b={"id": "b", "rhythm": full},
            overlap_policy={"minimum_hamming_distance": 0.2},
        ),
    )
    assert response.status_code == 422
    assert "too similar" in response.json()["detail"]


def test_invalid_phase_source_project_is_422() -> None:
    response = client.post(
        "/api/arrange/phase-shift",
        json={"arrangement": {"schema_version": "1.1.0"}},
    )
    assert response.status_code == 422
