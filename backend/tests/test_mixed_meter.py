from fastapi.testclient import TestClient

from app.main import app
from app.rhythm.mixed_meter import DrumTrackConfig, _density, generate, pattern_library


client = TestClient(app)


def test_mixed_meter_pattern_arithmetic_and_phase_paths() -> None:
    patterns = {item["id"]: item for item in pattern_library()["patterns"]}
    assert patterns["MM_3535"]["total_beats"] == 16
    assert patterns["MM_3535"]["phase_path"] == [0, 3, 0, 3, 0]
    assert patterns["MM_3575"]["total_beats"] == 20
    assert patterns["MM_3575"]["phase_path"] == [0, 3, 0, 3, 0]
    assert all(pattern["alignment_modulo"] == 0 for pattern in patterns.values())
    eighths = client.post("/api/rhythm/mixed-meter/validate", json={"pattern": {"id": "eight", "name": "Eighths", "denominator": 8, "meters": [3, 5], "groupings": [[3], [2, 3]]}})
    assert eighths.status_code == 200
    assert eighths.json()["pattern"]["total_beats"] == 4


def test_mixed_meter_validation_reports_grouping_and_alignment_errors() -> None:
    grouping = client.post(
        "/api/rhythm/mixed-meter/validate",
        json={"pattern": {"id": "bad", "name": "Bad", "meters": [5], "groupings": [[2, 2]]}},
    )
    assert grouping.status_code == 422
    unaligned = client.post(
        "/api/rhythm/mixed-meter/validate",
        json={"pattern": {"id": "odd", "name": "Odd", "meters": [3], "groupings": [[3]]}},
    )
    assert unaligned.status_code == 422
    advanced = client.post(
        "/api/rhythm/mixed-meter/validate",
        json={"pattern": {"id": "odd", "name": "Odd", "meters": [3], "groupings": [[3]]}, "allow_unaligned": True},
    )
    assert advanced.status_code == 200
    assert advanced.json()["warnings"]


def test_mixed_meter_generation_is_deterministic_and_resolves_to_four_four() -> None:
    request = {"pattern_id": "MM_3575", "form": "two_stage_resolution", "seed": 3575, "density_profile": "chorus_impact"}
    first = client.post("/api/rhythm/mixed-meter/generate", json=request)
    second = client.post("/api/rhythm/mixed-meter/generate", json=request)
    assert first.status_code == 200
    assert first.json() == second.json()
    project = first.json()
    assert [section["role"] for section in project["sections"]] == ["stable", "tension", "pre_resolution", "resolved"]
    assert project["total_beats"] % 4 == 0
    assert project["sections"][-1]["pattern"]["meters"] == [4, 4, 4, 4]
    assert any(event["role"] == "crash" and event["section_id"] == "resolved" for event in project["events"])
    assert all(event["locked"] for event in project["events"] if event["structural_role"] == "macro" and event["role"] == "kick")


def test_density_modes_clamp_and_allow_negative_tension_response() -> None:
    increasing = DrumTrackConfig(id="hat", role="closed_hat", midi_note=42, density_mode="hybrid", base_density=0.5, tension_response=0.4)
    decreasing = DrumTrackConfig(id="hat", role="closed_hat", midi_note=42, density_mode="hybrid", base_density=0.5, tension_response=-0.4)
    assert _density(increasing, "build_up", "tension", 0.9) > _density(increasing, "build_up", "tension", 0.1)
    assert _density(decreasing, "skeletal_tension", "tension", 0.9) < _density(decreasing, "skeletal_tension", "tension", 0.1)
    clamped = DrumTrackConfig(id="kick", role="kick", midi_note=36, density_mode="hybrid", base_density=0.9, max_density=0.75, tension_response=1)
    assert _density(clamped, "build_up", "resolved", 1) == 0.75


def test_mixed_meter_midi_wav_and_compose_timeline_match_generated_events() -> None:
    project = generate({"pattern_id": "MM_3733", "form": "direct_resolution", "seed": 77, "tension_repeats": 1})
    midi = client.post("/api/rhythm/mixed-meter/export/midi", json={"project": project})
    assert midi.status_code == 200
    assert midi.content.startswith(b"MThd")
    assert b"\xff\x58\x04" in midi.content
    assert b"\xff\x06" in midi.content
    wav = client.post("/api/rhythm/mixed-meter/preview", json={"project": project})
    assert wav.status_code == 200
    assert wav.content.startswith(b"RIFF")
    assert project["compose_timeline"]["clock"]["total_ticks"] == round(project["total_beats"] * project["settings"]["ppq"])


def test_locked_event_survives_regeneration() -> None:
    locked = {"track_id": "track-percussion", "role": "percussion", "section_id": "tension", "cycle_index": 0, "bar_index": 4, "pulse_position": 17.25, "tick": 8280, "duration_ticks": 60, "midi_note": 39, "velocity": 100, "timing_offset_ms": 0, "structural_role": "offbeat", "locked": True}
    project = generate({"seed": 2, "locked_events": [locked]})
    assert any(event["track_id"] == locked["track_id"] and event["tick"] == locked["tick"] and event["locked"] for event in project["events"])
