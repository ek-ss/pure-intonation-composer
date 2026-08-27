from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def _explorer_request(mixed_meter: dict[str, object]) -> dict[str, object]:
    return {
        "style": "kawaii_fractional_future_pop",
        "seed": 83571,
        "candidate_count": 4,
        "cluster_count": 2,
        "tempo_bpm": 146,
        "length_bars": 24,
        "mixed_meter": mixed_meter,
    }


def test_explorer_generates_deterministic_mixed_meter_candidates() -> None:
    request = _explorer_request(
        {
            "enabled": True,
            "source": "generate",
            "integration_mode": "replace_drums",
            "pattern_id": "MM_3575",
            "form": "two_stage_resolution",
            "density_profile": "chorus_impact",
            "variation": 0.35,
            "syncopation": 0.4,
        }
    )
    first = client.post("/api/composition-explorer/explore", json=request)
    second = client.post("/api/composition-explorer/explore", json=request)
    assert first.status_code == 200
    assert first.json() == second.json()
    result = first.json()
    assert result["mixed_meter_enabled"] is True
    song = result["representatives"][0]
    mixed = song["mixed_meter"]
    assert mixed["enabled"] is True
    assert mixed["source"] == "generate"
    assert mixed["integration_mode"] == "replace_drums"
    assert mixed["event_count"] > 0
    assert mixed["timeline"]["bars"][0]["start_beat"] == 0
    signatures = {
        (bar["meter"], bar["denominator"])
        for bar in mixed["timeline"]["bars"]
    }
    assert {(3, 4), (4, 4), (5, 4)} <= signatures
    assert song["features"]["meter_variety"] > 0
    assert song["features"]["meter_displacement"] > 0
    drum_events = [event for event in song["events"] if "note" in event]
    assert drum_events
    assert all("mixed_meter_role" in event for event in drum_events)
    assert len(
        {
            tuple(
                (event["start_beat"], event["note"])
                for event in representative["events"]
                if "mixed_meter_role" in event
            )
            for representative in result["representatives"]
        }
    ) == len(result["representatives"])


def test_explorer_imports_and_layers_a_mixed_meter_project() -> None:
    source_response = client.post(
        "/api/rhythm/mixed-meter/generate",
        json={
            "pattern_id": "MM_3733",
            "form": "direct_resolution",
            "seed": 3733,
            "density_profile": "skeletal_tension",
        },
    )
    assert source_response.status_code == 200
    source = source_response.json()
    response = client.post(
        "/api/composition-explorer/explore",
        json=_explorer_request(
            {
                "enabled": True,
                "source": "import",
                "integration_mode": "layer_drums",
                "project": source,
            }
        ),
    )
    assert response.status_code == 200
    song = response.json()["representatives"][0]
    assert song["mixed_meter"]["source_project"]["seed"] == 3733
    drum_events = [event for event in song["events"] if "note" in event]
    assert any("mixed_meter_role" in event for event in drum_events)
    assert any("mixed_meter_role" not in event for event in drum_events)

    invalid = client.post(
        "/api/composition-explorer/explore",
        json=_explorer_request(
            {
                "enabled": True,
                "source": "import",
                "project": {"feature": "not-mixed-meter"},
            }
        ),
    )
    assert invalid.status_code == 422


def test_vital_midi_preserves_mixed_meter_and_section_markers() -> None:
    explore = client.post(
        "/api/composition-explorer/explore",
        json=_explorer_request(
            {
                "enabled": True,
                "source": "generate",
                "integration_mode": "replace_drums",
                "pattern_id": "MM_3535",
            }
        ),
    )
    assert explore.status_code == 200
    song = explore.json()["representatives"][0]
    midi = client.post(
        "/api/compose/vital-pack/midi",
        json={
            "events": song["events"],
            "tempo_bpm": song["metadata"]["tempo_bpm"],
            "base_frequency": song["metadata"]["base_frequency"],
            "time_signatures": [
                [bar["start_beat"], bar["meter"], bar["denominator"]]
                for bar in song["mixed_meter"]["timeline"]["bars"]
            ],
            "section_markers": [
                [section["start_bar"] * 4, section["name"]]
                for section in song["sections"]
            ],
        },
    )
    assert midi.status_code == 200
    assert midi.content.startswith(b"MThd")
    assert midi.content.count(b"\xff\x58\x04") >= 4
    assert b"\xff\x06" in midi.content
