from __future__ import annotations

from fractions import Fraction

import pytest
from fastapi.testclient import TestClient

from app.lattice import (
    ExponentBasis,
    cents_distance,
    cumulative_offsets,
    differences_from_offsets,
    enumerate_domain,
    evaluate,
    generate_lattice_chord,
    invert_signs,
    lattice_distance,
    lattice_walk,
    monzo_distance,
    nearest_vector,
    normalize,
    reconstruct,
    reverse_path,
    rotate_path,
)
from app.main import app

client = TestClient(app)


def test_evaluate_and_normalize() -> None:
    basis = ExponentBasis((3, 5))
    raw = evaluate(basis, (1, -1))
    assert raw == Fraction(3, 5)
    normalized, shift = normalize(raw)
    assert normalized == Fraction(6, 5)
    assert shift == 1
    assert raw * 2**shift == normalized


def test_normalize_round_trip() -> None:
    for ratio in [Fraction(1), Fraction(3, 2), Fraction(7, 16), Fraction(45, 32), Fraction(5, 4)]:
        normalized, shift = normalize(ratio)
        assert Fraction(1) <= normalized < 2
        assert ratio * 2**shift == normalized


def test_dependencies_and_warnings() -> None:
    basis = ExponentBasis((3, 9))
    relations = basis.dependencies()
    assert len(relations) == 1
    (relation,) = relations
    # 3^a * 9^b == 1 for the reported relation
    assert evaluate(basis, relation) == 1
    assert any("dependent basis" in warning for warning in basis.warnings())


def test_octave_generator_warning() -> None:
    basis = ExponentBasis((2, 3))
    assert any("octave-only" in warning for warning in basis.warnings())


def test_enumerate_domain_collision_groups() -> None:
    basis = ExponentBasis((3, 9))
    points = enumerate_domain(basis, (0, 0), (2, 1))
    by_vector = {point.vector: point for point in points}
    # (2, 0) = 9/1 -> 9/8 ; (0, 1) = 9/1 -> 9/8 : same pitch class
    assert by_vector[(2, 0)].pitch_class_id == by_vector[(0, 1)].pitch_class_id
    assert by_vector[(2, 0)].collision_group == by_vector[(0, 1)].collision_group
    assert by_vector[(1, 0)].collision_group != by_vector[(2, 0)].collision_group


def test_enumerate_domain_limits() -> None:
    basis = ExponentBasis((3, 5))
    with pytest.raises(ValueError):
        enumerate_domain(basis, (-17, 0), (0, 0))
    with pytest.raises(ValueError):
        enumerate_domain(basis, (1, 0), (0, 0))


def test_differences_cumulative_round_trip() -> None:
    differences = [(1, 0), (0, 1), (-1, 1)]
    offsets = cumulative_offsets(differences)
    assert offsets[0] == (0, 0)
    assert offsets[-1] == (0, 2)
    assert differences_from_offsets(offsets) == differences


def test_reconstruct() -> None:
    basis = ExponentBasis((3, 5))
    offsets, tones = reconstruct(Fraction(1, 1), basis, [(1, 0), (0, 1)])
    assert offsets == [(0, 0), (1, 0), (1, 1)]
    assert tones[1].normalized_ratio == Fraction(3, 2)
    assert tones[2].normalized_ratio == Fraction(15, 8)


def test_generate_lattice_chord_is_deterministic_and_unique() -> None:
    basis = ExponentBasis((3, 5))
    arguments = (
        Fraction(1, 1),
        basis,
        [(1, 0), (0, 1), (-1, 0), (0, -1)],
        4,
        17,
        (-2, -2),
        (2, 2),
    )
    first = generate_lattice_chord(*arguments)
    second = generate_lattice_chord(*arguments)
    assert first == second
    differences, offsets, tones = first
    assert differences_from_offsets(offsets) == differences
    assert len({tone.normalized_ratio for tone in tones}) == len(tones) == 4


def test_generate_lattice_chord_rejects_unreachable_size() -> None:
    with pytest.raises(ValueError, match="cannot generate 3 unique tones"):
        generate_lattice_chord(
            Fraction(1, 1),
            ExponentBasis((2,)),
            [(1,)],
            3,
            0,
            (0,),
            (2,),
        )


def test_path_transforms() -> None:
    differences = [(1, 0), (0, 1), (-1, 1)]
    assert rotate_path(differences, 1) == [(0, 1), (-1, 1), (1, 0)]
    assert invert_signs(differences) == [(-1, 0), (0, -1), (1, -1)]
    basis = ExponentBasis((3, 5))
    new_root, reversed_differences = reverse_path(Fraction(1, 1), basis, differences)
    assert new_root == evaluate(basis, (0, 2))
    # Reversed path from the new root returns to the original root
    offsets = cumulative_offsets(reversed_differences)
    assert new_root * evaluate(basis, offsets[-1]) == Fraction(1, 1)


def test_walk_determinism_and_boundaries() -> None:
    basis = ExponentBasis((3, 5))
    allowed = [(1, 0), (-1, 0), (0, 1), (0, -1)]
    for boundary in ("stop", "reflect", "wrap", "resample"):
        first = lattice_walk(basis, (0, 0), allowed, 32, 7, (-2, -2), (2, 2), boundary)
        second = lattice_walk(basis, (0, 0), allowed, 32, 7, (-2, -2), (2, 2), boundary)
        assert first == second
        assert first[0] == (0, 0)
        for vector in first:
            assert all(-2 <= value <= 2 for value in vector)
        if boundary != "stop":
            assert len(first) == 33


def test_nearest_vector_perfect_fifth() -> None:
    basis = ExponentBasis((3, 5))
    vector, deviation = nearest_vector(basis, Fraction(3, 2), (-2, -2), (2, 2))
    assert vector == (1, 0)
    assert deviation == 0


def test_distances() -> None:
    basis = ExponentBasis((3, 5))
    assert lattice_distance((0, 0), (1, -1), 1) == 2.0
    assert lattice_distance((0, 0), (3, 4), 2) == 5.0
    assert monzo_distance(basis, (0, 0), (1, 0)) == 1.0
    assert cents_distance(basis, (0, 0), (1, 0)) == pytest.approx(498.045, abs=1e-3)


def test_scale_endpoint() -> None:
    response = client.post(
        "/api/exponent-lattice/scale",
        json={
            "generators": [3, 5],
            "minimum": [-2, -2],
            "maximum": [2, 2],
            "collision_policy": "keep",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["point_count"] == 25
    assert data["basis"]["generators"] == [3, 5]
    point = next(p for p in data["points"] if p["vector"] == [1, 0])
    assert point["normalized_ratio"] == "3/2"
    assert point["cents"] == pytest.approx(701.955, abs=1e-3)


def test_scale_endpoint_merge_policy() -> None:
    payload = {"generators": [3, 9], "minimum": [0, 0], "maximum": [2, 1], "collision_policy": "merge"}
    response = client.post("/api/exponent-lattice/scale", json=payload)
    assert response.status_code == 200
    data = response.json()
    pitch_classes = [point["pitch_class_id"] for point in data["points"]]
    assert len(pitch_classes) == len(set(pitch_classes))


def test_scale_endpoint_validation() -> None:
    response = client.post(
        "/api/exponent-lattice/scale",
        json={"generators": [3, 5], "minimum": [0], "maximum": [1, 1]},
    )
    assert response.status_code == 422


def test_harmony_endpoint() -> None:
    response = client.post(
        "/api/exponent-lattice/harmony",
        json={"root": "1/1", "generators": [3, 5], "differences": [[1, 0], [0, 1]]},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["offsets"] == [[0, 0], [1, 0], [1, 1]]
    assert [tone["normalized_ratio"] for tone in data["tones"]] == ["1/1", "3/2", "15/8"]
    assert data["root"] == "1/1"


def test_harmony_endpoint_root_vector_mismatch() -> None:
    response = client.post(
        "/api/exponent-lattice/harmony",
        json={
            "root": "5/4",
            "generators": [3, 5],
            "differences": [[1, 0]],
            "root_vector": [1, 0],
        },
    )
    assert response.status_code == 422


def test_chord_endpoint() -> None:
    payload = {
        "root": "5/4",
        "generators": [3, 5],
        "allowed_differences": [[1, 0], [0, 1], [-1, 0], [0, -1]],
        "tone_count": 4,
        "seed": 17,
        "minimum": [-2, -2],
        "maximum": [2, 2],
    }
    first = client.post("/api/exponent-lattice/chord", json=payload)
    second = client.post("/api/exponent-lattice/chord", json=payload)
    assert first.status_code == second.status_code == 200
    assert first.json() == second.json()
    data = first.json()
    assert data["root"] == "5/4"
    assert len(data["tones"]) == 4
    assert len(data["differences"]) == 3
    assert len({tone["normalized_ratio"] for tone in data["tones"]}) == 4


def test_walk_endpoint() -> None:
    response = client.post(
        "/api/exponent-lattice/walk",
        json={
            "generators": [3, 5],
            "start_vector": [0, 0],
            "allowed_differences": [[1, 0], [0, 1], [-1, 0]],
            "root": "5/4",
            "harmony_differences": [[1, 0], [0, 1]],
            "length": 12,
            "seed": 3,
            "minimum": [-2, -2],
            "maximum": [2, 2],
            "boundary": "reflect",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data["path"]) == len(data["pitches"]) == len(data["harmonies"]) == 13
    assert data["harmony_offsets"] == [[0, 0], [1, 0], [1, 1]]
    assert data["pitches"][0]["normalized_ratio"] == "5/4"
    assert [tone["normalized_ratio"] for tone in data["harmonies"][0]["tones"]] == [
        "5/4",
        "15/8",
        "75/64",
    ]
    for harmony in data["harmonies"]:
        for offset, tone in zip(data["harmony_offsets"], harmony["tones"]):
            assert tone["vector"] == [
                coordinate + delta
                for coordinate, delta in zip(harmony["root_vector"], offset)
            ]
    for pitch in data["pitches"]:
        numerator, denominator = pitch["normalized_ratio"].split("/")
        assert 1 <= int(numerator) / int(denominator) < 2


def test_walk_endpoint_defaults_to_root_only_harmony() -> None:
    response = client.post(
        "/api/exponent-lattice/walk",
        json={
            "generators": [3, 5],
            "start_vector": [0, 0],
            "allowed_differences": [[1, 0]],
            "length": 1,
            "seed": 0,
            "minimum": [0, 0],
            "maximum": [1, 1],
            "boundary": "stop",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["harmony_offsets"] == [[0, 0]]
    assert all(len(harmony["tones"]) == 1 for harmony in data["harmonies"])


def test_walk_endpoint_rejects_harmony_dimension_mismatch() -> None:
    response = client.post(
        "/api/exponent-lattice/walk",
        json={
            "generators": [3, 5],
            "start_vector": [0, 0],
            "allowed_differences": [[1, 0]],
            "harmony_differences": [[1, 0, 0]],
            "length": 1,
            "minimum": [0, 0],
            "maximum": [1, 1],
        },
    )
    assert response.status_code == 422


def test_analyze_endpoint() -> None:
    response = client.post(
        "/api/exponent-lattice/analyze",
        json={"generators": [3, 9], "vectors": [[2, 0], [0, 1]]},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["basis"]["dependencies"]
    assert len(data["distances"]) == 1
    distance = data["distances"][0]
    # 3^2 and 9^1 are the same pitch class: zero cents distance
    assert distance["cents"] == 0
    assert distance["lattice_l1"] == 3.0
