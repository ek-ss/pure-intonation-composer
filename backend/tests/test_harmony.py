from fastapi.testclient import TestClient

from app.composition.harmony import generate_harmony
from app.graphs.harmonic import build_johnson_graph
from app.main import app


client = TestClient(app)


def test_harmony_length_is_configurable_and_seed_is_deterministic() -> None:
    graph = build_johnson_graph([1, 3, 5, 7], 2)
    first = generate_harmony(graph, length=12, seed=42)
    second = generate_harmony(graph, length=12, seed=42)
    assert len(first.nodes) == 12
    assert first == second


def test_harmony_transitions_are_always_graph_edges() -> None:
    graph = build_johnson_graph([1, 3, 5, 7, 9], 2)
    progression = generate_harmony(graph, length=24, seed=7)
    assert all(
        right in graph.adjacency[left]
        for left, right in zip(progression.nodes, progression.nodes[1:])
    )


def test_harmony_api_returns_requested_progression_length() -> None:
    response = client.post(
        "/api/compose/harmony",
        json={"factors": [1, 3, 5, 7], "choose": 2, "length": 5, "seed": 12},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["length"] == 5
    assert len(payload["chords"]) == 5
