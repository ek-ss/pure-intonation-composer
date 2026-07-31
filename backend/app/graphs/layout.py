from __future__ import annotations

from dataclasses import dataclass

from app.graphs.harmonic import HarmonicGraph
from app.tuning.analysis import cents

SORT_MODES = ("lexicographic", "product", "pitch")


@dataclass(frozen=True)
class LayeredGridLayout:
    """Deterministic reference-node layered grid layout (docs/visualization.md)."""

    reference: int
    sort_mode: str
    positions: tuple[tuple[float, float], ...]
    shared_counts: tuple[int, ...]
    distances: tuple[int, ...]
    layers: tuple[tuple[int, tuple[int, ...]], ...]
    edge_directions: tuple[str, ...]


def reference_layered_grid_layout(
    graph: HarmonicGraph,
    reference: int,
    *,
    horizontal_spacing: float = 1.5,
    vertical_spacing: float = 1.8,
    center_layers: bool = True,
    sort_mode: str = "lexicographic",
    reference_on_top: bool = True,
) -> LayeredGridLayout:
    """Layer graph nodes by shared-element count with the reference node.

    Layers are centered horizontally and ordered deterministically within
    each layer. No randomness is used, so identical inputs always produce
    identical coordinates.
    """
    if not graph.nodes:
        raise ValueError("graph must not be empty")
    if not 0 <= reference < len(graph.nodes):
        raise ValueError(f"reference node {reference} does not exist in the graph")
    sizes = {len(node.factors) for node in graph.nodes}
    if len(sizes) != 1:
        raise ValueError("all combination nodes must have the same size")
    if any(len(set(node.factors)) != len(node.factors) for node in graph.nodes):
        raise ValueError("combination nodes must contain unique elements")
    if horizontal_spacing <= 0 or vertical_spacing <= 0:
        raise ValueError("spacing values must be positive")
    if sort_mode not in SORT_MODES:
        raise ValueError(f"sort mode must be one of {', '.join(SORT_MODES)}")

    choose = sizes.pop()
    reference_set = set(graph.nodes[reference].factors)
    shared_counts = tuple(len(set(node.factors) & reference_set) for node in graph.nodes)

    layers: dict[int, list[int]] = {}
    for index, shared in enumerate(shared_counts):
        layers.setdefault(shared, []).append(index)

    positions = [(0.0, 0.0)] * len(graph.nodes)
    sorted_layers: list[tuple[int, tuple[int, ...]]] = []
    for shared in sorted(layers, reverse=True):
        members = sorted(layers[shared], key=lambda index: _sort_key(graph, index, sort_mode))
        count = len(members)
        for position, index in enumerate(members):
            x = horizontal_spacing * (position - (count - 1) / 2) if center_layers else horizontal_spacing * position
            y = vertical_spacing * shared if reference_on_top else -vertical_spacing * shared
            positions[index] = (x, y)
        sorted_layers.append((shared, tuple(members)))

    edge_directions = tuple(
        _edge_direction(shared_counts[source], shared_counts[target])
        for source, target in graph.edges
    )
    return LayeredGridLayout(
        reference=reference,
        sort_mode=sort_mode,
        positions=tuple(positions),
        shared_counts=shared_counts,
        distances=tuple(choose - shared for shared in shared_counts),
        layers=tuple(sorted_layers),
        edge_directions=edge_directions,
    )


def _sort_key(graph: HarmonicGraph, index: int, sort_mode: str) -> tuple[int, ...] | int | float:
    node = graph.nodes[index]
    if sort_mode == "lexicographic":
        return node.factors
    if sort_mode == "product":
        product = 1
        for factor in node.factors:
            product *= factor
        return product
    return cents(node.ratio)


def _edge_direction(source_shared: int, target_shared: int) -> str:
    if target_shared > source_shared:
        return "inward"
    if target_shared < source_shared:
        return "outward"
    return "lateral"
