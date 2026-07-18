from app.rhythm.engine import euclidean_rhythm, humanize, phase_shift, state_transition_graph


def test_euclidean_rhythm_has_exact_pulse_count() -> None:
    pattern = euclidean_rhythm(13, 5)
    assert len(pattern) == 13
    assert sum(pattern) == 5


def test_state_graph_edges_have_hamming_distance_one() -> None:
    graph = state_transition_graph(4)
    assert len(graph["nodes"]) == 16
    assert all(sum(left != right for left, right in zip(source, target)) == 1 for source, target in graph["edges"])


def test_phase_shift_supports_independent_cycle_lengths() -> None:
    shifted = phase_shift([[1, 0, 0], [1, 0, 1, 0]], 12, [0, 1])
    assert shifted[0] == [1, 0, 0, 1, 0, 0, 1, 0, 0, 1, 0, 0]
    assert len(shifted[1]) == 12


def test_humanization_is_deterministic_with_a_seed() -> None:
    assert humanize([1, 0, 1, 0], 42) == humanize([1, 0, 1, 0], 42)


def test_drum_midi_export_contains_percussion_events() -> None:
    from app.exporters.midi import MidiDrumHit, drum_midi_bytes

    data = drum_midi_bytes([MidiDrumHit(36, 0, 100), MidiDrumHit(36, 0.5, 80)])
    assert data.startswith(b"MThd")
    assert bytes((0x99, 36, 100)) in data
    assert bytes((0x99, 36, 80)) in data
    assert bytes((0x89, 36, 0)) in data


def test_drum_midi_export_rejects_invalid_hits() -> None:
    import pytest

    from app.exporters.midi import MidiDrumHit, drum_midi_bytes

    with pytest.raises(ValueError):
        drum_midi_bytes([MidiDrumHit(200, 0, 100)])
    with pytest.raises(ValueError):
        drum_midi_bytes([MidiDrumHit(36, -1, 100)])


def test_rhythm_midi_endpoint_exports_active_steps() -> None:
    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    response = client.post("/api/export/rhythm/midi", json={"pattern": [1, 0, 1, 0], "note": 38, "velocities": [100, 0, 60, 0]})
    assert response.status_code == 200
    assert response.headers["content-type"] == "audio/midi"
    assert response.content.startswith(b"MThd")
    assert bytes((0x99, 38, 100)) in response.content
    assert bytes((0x99, 38, 60)) in response.content


def test_rhythm_midi_endpoint_validates_input() -> None:
    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    assert client.post("/api/export/rhythm/midi", json={"pattern": [1, 2, 0]}).status_code == 422
    assert client.post("/api/export/rhythm/midi", json={"pattern": [1, 0], "velocities": [100]}).status_code == 422


def test_rhythm_midi_endpoint_cycles_repeat_the_pattern() -> None:
    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    response = client.post("/api/export/rhythm/midi", json={"pattern": [1, 0, 0, 0], "note": 36, "cycles": 2})
    assert response.status_code == 200
    assert response.content.count(bytes((0x99, 36, 100))) == 2
    # Note-off of the first hit ends at tick 120, so the second note-on at
    # beat len(pattern)/steps_per_beat = 1.0 (tick 480) is encoded after a
    # 360-tick delta (variable-length 0x82 0x68).
    assert b"\x82\x68" + bytes((0x99, 36, 100)) in response.content


def test_rhythm_midi_endpoint_default_cycles_match_legacy_output() -> None:
    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    body = {"pattern": [1, 0, 1, 0], "note": 38, "velocities": [100, 0, 60, 0]}
    plain = client.post("/api/export/rhythm/midi", json=body)
    explicit = client.post("/api/export/rhythm/midi", json={**body, "cycles": 1})
    assert plain.status_code == explicit.status_code == 200
    assert plain.content == explicit.content


def test_rhythm_midi_endpoint_layers_mode_uses_layer_notes() -> None:
    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    response = client.post(
        "/api/export/rhythm/midi",
        json={
            "layers": [
                {"pattern": [1, 0], "note": 36},
                {"pattern": [0, 1], "note": 38, "velocities": [0, 90]},
            ],
            "cycles": 2,
        },
    )
    assert response.status_code == 200
    assert response.content.count(bytes((0x99, 36, 100))) == 2
    assert response.content.count(bytes((0x99, 38, 90))) == 2


def test_rhythm_midi_endpoint_rejects_missing_pattern_and_layers() -> None:
    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    assert client.post("/api/export/rhythm/midi", json={"note": 36}).status_code == 422
