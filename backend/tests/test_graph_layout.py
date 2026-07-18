import pytest

from app.graphs.harmonic import build_johnson_graph, shortest_path
from app.graphs.layout import reference_layered_grid_layout


@pytest.fixture()
def eikosany():
    return build_johnson_graph([1, 3, 5, 7, 9, 11], 3)


def test_cps63_layer_sizes_are_1_9_9_1(eikosany) -> None:
    layout = reference_layered_grid_layout(eikosany, 0)
    sizes = {shared: len(members) for shared, members in layout.layers}
    assert sizes == {3: 1, 2: 9, 1: 9, 0: 1}


def test_reference_is_centered_in_top_layer(eikosany) -> None:
    layout = reference_layered_grid_layout(eikosany, 0)
    assert layout.positions[0] == (0.0, 1.8 * 3)
    assert layout.shared_counts[0] == 3
    assert layout.distances[0] == 0


def test_every_layer_is_horizontally_centered(eikosany) -> None:
    layout = reference_layered_grid_layout(eikosany, 0)
    for _, members in layout.layers:
        assert abs(sum(layout.positions[index][0] for index in members)) < 1e-9


def test_layout_is_deterministic(eikosany) -> None:
    assert reference_layered_grid_layout(eikosany, 2) == reference_layered_grid_layout(eikosany, 2)


def test_shared_count_matches_johnson_distance(eikosany) -> None:
    layout = reference_layered_grid_layout(eikosany, 0)
    for index in range(len(eikosany.nodes)):
        assert len(shortest_path(eikosany, 0, index)) - 1 == layout.distances[index]


def test_sort_modes_change_order_not_layers(eikosany) -> None:
    lexicographic = reference_layered_grid_layout(eikosany, 0, sort_mode="lexicographic")
    product = reference_layered_grid_layout(eikosany, 0, sort_mode="product")
    pitch = reference_layered_grid_layout(eikosany, 0, sort_mode="pitch")
    assert {shared: len(members) for shared, members in lexicographic.layers} == {shared: len(members) for shared, members in product.layers}
    assert lexicographic.positions != product.positions or product.positions != pitch.positions


def test_edge_directions_are_relative_to_reference(eikosany) -> None:
    layout = reference_layered_grid_layout(eikosany, 0)
    assert len(layout.edge_directions) == len(eikosany.edges)
    for (source, target), direction in zip(eikosany.edges, layout.edge_directions):
        expected = {1: "inward", -1: "outward", 0: "lateral"}[layout.shared_counts[target] - layout.shared_counts[source]]
        assert direction == expected


def test_layout_validation(eikosany) -> None:
    with pytest.raises(ValueError, match="does not exist"):
        reference_layered_grid_layout(eikosany, 99)
    with pytest.raises(ValueError, match="sort mode"):
        reference_layered_grid_layout(eikosany, 0, sort_mode="random")
    with pytest.raises(ValueError, match="spacing"):
        reference_layered_grid_layout(eikosany, 0, horizontal_spacing=0)


def test_layout_endpoint() -> None:
    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    response = client.post(
        "/api/harmonic-graph",
        json={"factors": [1, 3, 5, 7, 9, 11], "choose": 3, "layout": "reference_layered_grid", "reference": 0},
    )
    assert response.status_code == 200
    layout = response.json()["layout"]
    assert layout["kind"] == "reference_layered_grid"
    assert [len(layer["nodes"]) for layer in layout["layers"]] == [1, 9, 9, 1]
    assert len(layout["positions"]) == 20
    assert response.json()["nodes"][0]["sub_ratio"]
