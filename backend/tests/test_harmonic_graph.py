from math import comb

from fastapi.testclient import TestClient

from app.graphs.harmonic import build_johnson_graph, distance, random_walk, shortest_path, weighted_walk
from app.main import app
from app.tuning.ratios import parse_ratio


client = TestClient(app)


def test_johnson_graph_has_combinatorial_node_count_and_is_connected() -> None:
    graph = build_johnson_graph([1, 3, 5, 7, 9, 11], 3)
    assert len(graph.nodes) == comb(6, 3) == 20
    assert len(shortest_path(graph, 0, len(graph.nodes) - 1)) > 1


def test_distance_metrics_are_symmetric_and_zero_for_identical_ratios() -> None:
    left, right = parse_ratio("3/2"), parse_ratio("5/4")
    for metric in ("harmonic", "monzo", "cent"):
        assert distance(left, right, metric) == distance(right, left, metric)
        assert distance(left, left, metric) == 0


def test_walks_are_deterministic_with_a_fixed_seed() -> None:
    graph = build_johnson_graph([1, 3, 5, 7], 2)
    assert random_walk(graph, 0, 10, 42) == random_walk(graph, 0, 10, 42)
    assert weighted_walk(graph, 0, 10, 42) == weighted_walk(graph, 0, 10, 42)


def test_harmonic_graph_api_exposes_nodes_edges_and_walk() -> None:
    response = client.post(
        "/api/harmonic-graph",
        json={"factors": [1, 3, 5, 7], "choose": 2, "operation": "random_walk", "steps": 3, "seed": 7},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["node_count"] == 6
    assert payload["edge_count"] == 12
    assert len(payload["walk"]) == 4
