from __future__ import annotations

from dataclasses import dataclass
from random import Random

from app.graphs.harmonic import HarmonicGraph, distance


@dataclass(frozen=True)
class HarmonyProgression:
    """A connected sequence of Johnson graph node indices and transition scores."""

    nodes: tuple[int, ...]
    transition_scores: tuple[float, ...]


def generate_harmony(
    graph: HarmonicGraph,
    length: int,
    seed: int,
    start: int = 0,
    metric: str = "harmonic",
) -> HarmonyProgression:
    """Generate a reproducible, connected harmonic progression.

    Each next chord is selected from the current node's neighbors. A lower
    interval distance earns a higher selection weight, retaining local
    harmonic continuity while the seed makes the result repeatable.
    """
    if length < 1:
        raise ValueError("length must be at least one")
    if not 0 <= start < len(graph.nodes):
        raise ValueError("node index is outside the graph")

    random = Random(seed)
    nodes = [start]
    scores: list[float] = []
    for _ in range(length - 1):
        current = nodes[-1]
        neighbors = graph.adjacency[current]
        if not neighbors:
            raise ValueError("cannot continue from a disconnected node")
        candidates = [
            _transition_score(graph, current, neighbor, metric) for neighbor in neighbors
        ]
        next_node = random.choices(neighbors, weights=candidates, k=1)[0]
        nodes.append(next_node)
        scores.append(_transition_score(graph, current, next_node, metric))
    return HarmonyProgression(tuple(nodes), tuple(scores))


def _transition_score(
    graph: HarmonicGraph, current: int, candidate: int, metric: str) -> float:
    """Score a graph edge so closer intervals are preferred but never excluded."""
    interval_distance = distance(
        graph.nodes[current].ratio, graph.nodes[candidate].ratio, metric
    )
    common_factors = len(
        set(graph.nodes[current].factors).intersection(graph.nodes[candidate].factors)
    )
    return (common_factors + 1) / (interval_distance + 1)
