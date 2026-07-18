from fastapi.testclient import TestClient

from app.main import app
from app.rhythm.drums import (
    LayerSpec,
    accent_velocities,
    analysis_length,
    analyze_layers,
    optimize_rotations,
    phase_offsets,
    project,
)
from app.rhythm.engine import euclidean_rhythm

client = TestClient(app)


def test_analysis_length_uses_lcm_and_bounded_window() -> None:
    assert analysis_length([4, 6]) == 12
    assert analysis_length([4, 6], max_steps=8) == 8
    assert analysis_length([13, 15, 16, 17]) == 512
    assert analysis_length([13, 15, 16, 17], max_steps=100_000) == 53_040


def test_project_repeats_cyclically() -> None:
    assert project([1, 0, 0], 7) == [1, 0, 0, 1, 0, 0, 1]
    assert project([1], 3) == [1, 1, 1]


def test_analyze_layers_densities_stay_within_bounds() -> None:
    result = analyze_layers({"a": [1, 0, 1, 0], "b": [1, 1, 1, 1]})
    density = result["density"]
    assert isinstance(density, dict)
    assert all(0.0 <= value <= 1.0 for value in density.values())
    assert density["a"] == 0.5
    assert result["combined_density"] == 1.0
    assert 0.0 <= float(result["combined_density"]) <= 1.0


def test_analyze_pairwise_collisions_match_brute_force() -> None:
    layers = {"kick": [1, 0, 0, 1, 0], "snare": [0, 1, 0, 1, 0], "hat": [1, 1, 1, 1, 1, 1, 1]}
    result = analyze_layers(layers)
    names = list(layers)
    length = result["analysis_length"]
    assert isinstance(length, int)
    brute = {
        f"{left}-{right}": sum(
            1
            for step in range(length)
            if layers[left][step % len(layers[left])] and layers[right][step % len(layers[right])]
        )
        for index, left in enumerate(names)
        for right in names[index + 1 :]
    }
    assert result["pairwise_collisions"] == brute


def test_analyze_identical_patterns_have_similarity_one() -> None:
    result = analyze_layers({"a": [1, 0, 1, 0], "b": [1, 0, 1, 0]})
    assert result["pairwise_similarity"] == {"a-b": 1.0}
    assert result["four_layer_collisions"] == 2


def test_analyze_complementary_patterns_collide_less_than_identical() -> None:
    identical = analyze_layers({"a": [1, 0, 1, 0, 1, 0, 1, 0], "b": [1, 0, 1, 0, 1, 0, 1, 0]})
    complementary = analyze_layers({"a": [1, 0, 1, 0, 1, 0, 1, 0], "b": [0, 1, 0, 1, 0, 1, 0, 1]})
    assert complementary["pairwise_collisions"] == {"a-b": 0}
    assert identical["pairwise_collisions"] == {"a-b": 4}
    assert complementary["combined_density"] == 1.0


def test_optimizer_snare_avoids_kick_collisions() -> None:
    results = optimize_rotations([LayerSpec("kick", 16, 4, rotation=0), LayerSpec("snare", 16, 2)])
    kick = next(result for result in results if result.name == "kick")
    snare = next(result for result in results if result.name == "snare")
    optimized_collisions = sum(1 for step in range(16) if kick.pattern[step] and snare.pattern[step])
    unrotated_snare = euclidean_rhythm(16, 2, 0)
    baseline_collisions = sum(1 for step in range(16) if kick.pattern[step] and unrotated_snare[step])
    assert kick.pattern[0] == 1
    assert baseline_collisions > 0
    assert optimized_collisions < baseline_collisions


def test_optimizer_is_deterministic() -> None:
    specs = [
        LayerSpec("kick", 16, 5),
        LayerSpec("snare", 16, 3),
        LayerSpec("hat", 13, 8),
        LayerSpec("perc", 17, 6),
    ]
    assert optimize_rotations(specs) == optimize_rotations(specs)


def test_optimizer_preserves_kick_rotation() -> None:
    results = optimize_rotations([LayerSpec("hat", 8, 5), LayerSpec("kick", 16, 4, rotation=3)])
    kick = next(result for result in results if result.name == "kick")
    assert kick.rotation == 3
    assert kick.pattern == euclidean_rhythm(16, 4, 3)


def test_optimizer_supports_unequal_cycle_lengths() -> None:
    results = optimize_rotations([LayerSpec("kick", 16, 4), LayerSpec("hat", 13, 8)])
    hat = next(result for result in results if result.name == "hat")
    assert len(hat.pattern) == 13
    assert 0 <= hat.rotation < 13
    assert set(hat.breakdown) == {
        "anchor",
        "complement",
        "syncopation",
        "collision_penalty",
        "density_penalty",
        "cluster_penalty",
        "similarity_penalty",
    }


def test_optimizer_handles_all_rest_and_all_hit_layers() -> None:
    results = optimize_rotations([LayerSpec("kick", 8, 0), LayerSpec("hat", 8, 8)])
    assert sum(results[0].pattern) == 0
    assert sum(results[1].pattern) == 8


def test_phase_offsets_shift_one_step_every_bar() -> None:
    spec = LayerSpec("hat", 16, 8, rotation=0, phase_increment=1, phase_update_bars=1)
    assert phase_offsets(spec, 4) == [0, 1, 2, 3]


def test_phase_offsets_support_negative_increment() -> None:
    spec = LayerSpec("hat", 16, 8, rotation=0, phase_increment=-1, phase_update_bars=1)
    assert phase_offsets(spec, 3) == [0, 15, 14]


def test_phase_offsets_wrap_modulo_steps() -> None:
    spec = LayerSpec("hat", 4, 2, rotation=0, phase_increment=1, phase_update_bars=1)
    assert phase_offsets(spec, 6) == [0, 1, 2, 3, 0, 1]


def test_phase_offsets_update_only_at_bar_boundaries() -> None:
    spec = LayerSpec("snare", 16, 2, rotation=0, phase_increment=1, phase_update_bars=4)
    assert phase_offsets(spec, 9) == [0, 0, 0, 0, 1, 1, 1, 1, 2]


def test_phase_offsets_disabled_when_increment_is_zero() -> None:
    spec = LayerSpec("kick", 16, 4, rotation=2, phase_increment=0, phase_update_bars=4)
    assert phase_offsets(spec, 9) == [2] * 9


def test_accent_velocities_emphasize_downbeats() -> None:
    velocities = accent_velocities([1] * 16, 100)
    assert velocities[0] == 120
    assert velocities[8] == 113
    assert velocities[4] == 107
    assert velocities[1] == 100
    assert velocities[0] > velocities[1]
    assert velocities[4] > velocities[5]


def test_accent_velocities_clamp_and_silence_rests() -> None:
    velocities = accent_velocities([1, 0, 1, 0], 127)
    assert velocities[0] == 127
    assert velocities[1] == 0
    assert velocities[3] == 0


def test_optimize_rotations_endpoint() -> None:
    response = client.post(
        "/api/rhythm/optimize-rotations",
        json={
            "layers": [
                {"name": "kick", "steps": 16, "pulses": 4, "rotation": 0},
                {"name": "snare", "steps": 16, "pulses": 2},
                {"name": "hat", "steps": 13, "pulses": 8},
            ]
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["analysis_length"] == 208
    assert [layer["name"] for layer in payload["layers"]] == ["kick", "snare", "hat"]
    assert payload["layers"][0]["rotation"] == 0
    assert len(payload["layers"][1]["breakdown"]) == 7


def test_optimize_rotations_endpoint_rejects_invalid_input() -> None:
    assert (
        client.post(
            "/api/rhythm/optimize-rotations",
            json={"layers": [{"name": "kick", "steps": 8, "pulses": 9}]},
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/rhythm/optimize-rotations",
            json={
                "layers": [
                    {"name": "kick", "steps": 8, "pulses": 2},
                    {"name": "kick", "steps": 8, "pulses": 3},
                ]
            },
        ).status_code
        == 422
    )


def test_analyze_endpoint() -> None:
    response = client.post(
        "/api/rhythm/analyze",
        json={
            "layers": [
                {"name": "a", "pattern": [1, 0, 1, 0]},
                {"name": "b", "pattern": [0, 1, 0, 1]},
            ]
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["analysis_length"] == 4
    assert payload["pairwise_collisions"] == {"a-b": 0}
    assert payload["combined_density"] == 1.0
    assert payload["pairwise_similarity"] == {"a-b": 0.0}


def test_analyze_endpoint_rejects_non_binary_patterns() -> None:
    response = client.post(
        "/api/rhythm/analyze",
        json={"layers": [{"name": "a", "pattern": [1, 2, 0]}]},
    )
    assert response.status_code == 422


def test_drums_generate_endpoint_is_deterministic() -> None:
    body = {
        "layers": [
            {"name": "kick", "steps": 16, "pulses": 5, "rotation": 0},
            {"name": "snare", "steps": 16, "pulses": 3, "phase_increment": 1},
            {"name": "hat", "steps": 13, "pulses": 8, "phase_increment": 1, "phase_update_bars": 3},
            {"name": "perc", "steps": 17, "pulses": 6, "phase_increment": 2, "phase_update_bars": 5},
        ],
        "bars": 8,
        "seed": 7,
    }
    first = client.post("/api/drums/generate", json=body)
    second = client.post("/api/drums/generate", json=body)
    assert first.status_code == 200
    assert first.json() == second.json()
    payload = first.json()
    assert payload["bars"] == 8
    assert [layer["name"] for layer in payload["layers"]] == ["kick", "snare", "hat", "perc"]
    for layer in payload["layers"]:
        assert len(layer["phase_offsets"]) == 8
        assert len(layer["velocities"]) == len(layer["pattern"])
        assert all(1 <= velocity <= 127 for velocity in layer["velocities"] if velocity)
    assert payload["metrics"]["analysis_length"] > 0
    assert payload["layers"][0]["phase_offsets"] == [0] * 8
    snare = payload["layers"][1]
    assert snare["phase_offsets"] == [(snare["rotation"] + bar // 4) % 16 for bar in range(8)]


def test_drums_generate_without_optimization_uses_given_rotations() -> None:
    response = client.post(
        "/api/drums/generate",
        json={
            "layers": [
                {"name": "kick", "steps": 8, "pulses": 2, "rotation": 3},
                {"name": "hat", "steps": 8, "pulses": 4},
            ],
            "bars": 2,
            "optimize": False,
        },
    )
    assert response.status_code == 200
    layers = response.json()["layers"]
    assert layers[0]["rotation"] == 3
    assert layers[0]["pattern"] == euclidean_rhythm(8, 2, 3)
    assert layers[1]["rotation"] == 0
    assert layers[1]["pattern"] == euclidean_rhythm(8, 4, 0)


def test_drums_generate_rejects_invalid_input() -> None:
    assert (
        client.post(
            "/api/drums/generate",
            json={"layers": [{"name": "kick", "steps": 8, "pulses": 2}], "bars": 0},
        ).status_code
        == 422
    )
