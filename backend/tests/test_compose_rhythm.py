from fractions import Fraction

import pytest
from fastapi.testclient import TestClient

from app.composition.rhythm import (
    CompositionClock,
    RhythmLayer,
    RhythmMapping,
    compile_rhythm,
    generate_compose_rhythm,
    transition_aware_durations,
)
from app.main import app


client = TestClient(app)


def _material() -> tuple[list[list[Fraction]], list[Fraction], list[list[Fraction]]]:
    return (
        [
            [Fraction(1), Fraction(5, 4), Fraction(3, 2)],
            [Fraction(9, 8), Fraction(4, 3), Fraction(5, 3)],
        ],
        [Fraction(1, 2), Fraction(9, 16)],
        [[Fraction(3, 2), Fraction(5, 3)]],
    )


def test_rhythm_layers_map_to_root_second_and_third_chord_tones() -> None:
    clock = CompositionClock(bars=1)
    chords, bass, melody = _material()
    layers = [
        RhythmLayer(name, (1, 0, 0, 0), (velocity, 0, 0, 0))
        for name, velocity in (("kick", 110), ("snare", 100), ("hat", 90))
    ]
    mappings = [
        RhythmMapping("kick", "chord_tone:0"),
        RhythmMapping("snare", "chord_tone:1"),
        RhythmMapping("hat", "chord_tone:2"),
    ]
    result = compile_rhythm(clock, chords, bass, melody, layers, mappings)
    at_start = [event for event in result.events if event.start_tick == 0]
    assert [event.ratio for event in at_start] == [
        Fraction(1),
        Fraction(5, 4),
        Fraction(3, 2),
    ]
    second_chord = [event for event in result.events if event.start_tick == 960]
    assert {event.ratio for event in second_chord} == {
        Fraction(9, 8),
        Fraction(4, 3),
        Fraction(5, 3),
    }


def test_role_mapping_targets_harmony_bass_and_melody() -> None:
    clock = CompositionClock(bars=1)
    chords, bass, melody = _material()
    layers = [
        RhythmLayer(name, (1, 0, 0, 0), (100, 0, 0, 0))
        for name in ("kick", "snare", "hat")
    ]
    result = compile_rhythm(
        clock,
        chords,
        bass,
        melody,
        layers,
        [
            RhythmMapping("kick", "bass"),
            RhythmMapping("snare", "harmony", collision="retrigger"),
            RhythmMapping("hat", "melody:0"),
        ],
    )
    ratios = [event.ratio for event in result.events if event.start_tick == 0]
    assert ratios.count(Fraction(1)) == 1
    assert set(ratios) == {
        Fraction(1, 2),
        Fraction(1),
        Fraction(5, 4),
        Fraction(3, 2),
    }
    assert result.metrics["max_simultaneous_attacks"] == 5


def test_changing_cardinality_uses_selected_overflow_policy() -> None:
    clock = CompositionClock(bars=1)
    chords = [[Fraction(1), Fraction(3, 2)], [Fraction(1)]]
    layer = RhythmLayer("perc", (1,), (100,))
    dropped = compile_rhythm(
        clock,
        chords,
        [],
        [],
        [layer],
        [RhythmMapping("perc", "chord_tone:1", overflow="drop")],
    )
    wrapped = compile_rhythm(
        clock,
        chords,
        [],
        [],
        [layer],
        [RhythmMapping("perc", "chord_tone:1", overflow="wrap")],
    )
    assert all(event.chord_index == 0 for event in dropped.events)
    assert any(event.chord_index == 1 for event in wrapped.events)


def test_voice_led_mapping_chooses_nearest_tone_independent_of_order() -> None:
    clock = CompositionClock(bars=1)
    layer = RhythmLayer("lead", (1,), (100,))
    mapping = RhythmMapping("lead", "chord_tone:0", policy="voice-led")
    first = compile_rhythm(
        clock,
        [[Fraction(3, 2)], [Fraction(1), Fraction(8, 5), Fraction(4, 3)]],
        [],
        [],
        [layer],
        [mapping],
    )
    reordered = compile_rhythm(
        clock,
        [[Fraction(3, 2)], [Fraction(4, 3), Fraction(1), Fraction(8, 5)]],
        [],
        [],
        [layer],
        [mapping],
    )
    first_second_chord = [event.ratio for event in first.events if event.chord_index == 1]
    reordered_second_chord = [
        event.ratio for event in reordered.events if event.chord_index == 1
    ]
    assert set(first_second_chord) == set(reordered_second_chord) == {Fraction(8, 5)}


def test_voice_led_register_is_applied_once() -> None:
    clock = CompositionClock(bars=1)
    result = compile_rhythm(
        clock,
        [[Fraction(1)], [Fraction(9, 8)]],
        [],
        [],
        [RhythmLayer("lead", (1,), (100,))],
        [
            RhythmMapping(
                "lead",
                "chord_tone:0",
                policy="voice-led",
                register_octave=1,
            )
        ],
    )
    assert result.events[0].ratio == Fraction(2)
    assert all(event.ratio < 3 for event in result.events)


def test_transition_aware_duration_fills_exact_clock() -> None:
    clock = CompositionClock(bars=3)
    chords, _bass, _melody = _material()
    first = transition_aware_durations(clock, chords, [None, 800], 9)
    second = transition_aware_durations(clock, chords, [None, 800], 9)
    assert first == second
    assert len(first) == len(chords)
    assert sum(first) == clock.total_subdivisions
    assert all(duration > 0 for duration in first)


def test_transition_aware_duration_can_vary_at_default_form_length() -> None:
    clock = CompositionClock(bars=8)
    chords = [[Fraction(1)], [Fraction(9, 8)]] * 4
    durations = transition_aware_durations(
        clock,
        chords,
        [None, 50, 900, 50, 900, 50, 900, 50],
        7,
    )
    assert sum(durations) == clock.total_subdivisions
    assert len(set(durations)) > 1


@pytest.mark.parametrize(
    "strategy",
    ["transition-aware", "semi-markov", "interlocking", "ratio-derived"],
)
def test_native_rhythm_strategies_are_deterministic(strategy: str) -> None:
    clock = CompositionClock(bars=2)
    chords, bass, melody = _material()
    arguments = (
        clock,
        chords,
        bass,
        melody,
        strategy,
        "interlocking",
        0.35,
        0.4,
        17,
        ["harmony", "bass", "melody:0"],
        [None, 600.0],
    )
    first = generate_compose_rhythm(*arguments)
    second = generate_compose_rhythm(*arguments)
    assert first == second
    _layers, _mappings, durations, compiled = first
    assert sum(durations) == clock.total_subdivisions
    assert compiled.events
    assert compiled.clock.total_ticks == 3840


def test_compose_rhythm_apply_endpoint() -> None:
    response = client.post(
        "/api/compose/rhythm/apply",
        json={
            "clock": {"bars": 1},
            "composition": {
                "chords": [["1/1", "5/4", "3/2"], ["9/8", "4/3", "5/3"]],
                "bass": ["1/2", "9/16"],
                "melody": [["3/2", "5/3"]],
            },
            "layers": [
                {"name": "kick", "pattern": [1, 0, 0, 0]},
                {"name": "snare", "pattern": [0, 0, 1, 0]},
            ],
            "mappings": [
                {"source_layer": "kick", "target": "bass"},
                {"source_layer": "snare", "target": "harmony"},
            ],
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["clock"]["total_ticks"] == 1920
    assert len(data["chord_spans"]) == 2
    assert data["metrics"]["event_count"] > 0


def test_compose_rhythm_generate_endpoint() -> None:
    payload = {
        "clock": {"bars": 2},
        "composition": {
            "chords": [["1/1", "5/4", "3/2"], ["9/8", "4/3", "5/3"]],
            "bass": ["1/2", "9/16"],
            "melody": [["3/2", "5/3"]],
            "transition_scores": [None, 500],
        },
        "strategy": "transition-aware",
        "profile": "grounded",
        "seed": 23,
        "targets": ["harmony", "bass", "melody:0"],
    }
    first = client.post("/api/compose/rhythm/generate", json=payload)
    second = client.post("/api/compose/rhythm/generate", json=payload)
    assert first.status_code == second.status_code == 200
    assert first.json() == second.json()
    data = first.json()
    assert sum(data["chord_durations"]) == 32
    assert len(data["layers"]) == 3
    assert data["events"]


def test_compose_rhythm_rejects_unknown_mapping_layer() -> None:
    response = client.post(
        "/api/compose/rhythm/apply",
        json={
            "clock": {"bars": 1},
            "composition": {"chords": [["1/1"]]},
            "layers": [{"name": "kick", "pattern": [1, 0, 0, 0]}],
            "mappings": [{"source_layer": "missing", "target": "harmony"}],
        },
    )
    assert response.status_code == 422
