from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from fractions import Fraction
from itertools import combinations
from math import comb
from random import Random

from app.tuning.analysis import cents, monzo
from app.tuning.ratios import reduce_to_octave


@dataclass(frozen=True)
class HarmonicNode:
    """A CPS subset and the pitch class created by multiplying its factors."""

    factors: tuple[int, ...]
    ratio: Fraction


@dataclass(frozen=True)
class HarmonicGraph:
    """Johnson graph J(n, k) whose nodes are CPS factor subsets."""

    nodes: tuple[HarmonicNode, ...]
    edges: tuple[tuple[int, int], ...]
    adjacency: tuple[tuple[int, ...], ...]


def build_johnson_graph(factors: list[int], choose: int) -> HarmonicGraph:
    """Build J(n, k) from unique positive CPS factors.

    Two nodes are adjacent exactly when their subsets differ in one factor.
    """
    if not factors or any(factor < 1 for factor in factors):
        raise ValueError("factors must contain positive integers")
    if len(set(factors)) != len(factors):
        raise ValueError("factors must be unique")
    if not 1 <= choose <= len(factors):
        raise ValueError("choose must be between 1 and the number of factors")

    subsets = list(combinations(factors, choose))
    nodes = tuple(
        HarmonicNode(subset, reduce_to_octave(_product(subset))) for subset in subsets
    )
    adjacency = [[] for _ in nodes]
    edges: list[tuple[int, int]] = []
    for left, right in combinations(range(len(nodes)), 2):
        if len(set(nodes[left].factors).intersection(nodes[right].factors)) == choose - 1:
            edges.append((left, right))
            adjacency[left].append(right)
            adjacency[right].append(left)

    expected_size = comb(len(factors), choose)
    if len(nodes) != expected_size:  # Defensive invariant for future node strategies.
        raise RuntimeError("Johnson graph node count is invalid")
    return HarmonicGraph(nodes, tuple(edges), tuple(tuple(neighbors) for neighbors in adjacency))


def shortest_path(graph: HarmonicGraph, start: int, end: int) -> list[int]:
    """Return the shortest inclusive path between two node indices."""
    _validate_index(graph, start)
    _validate_index(graph, end)
    queue = deque([start])
    previous = {start: None}
    while queue:
        node = queue.popleft()
        if node == end:
            path: list[int] = []
            while node is not None:
                path.append(node)
                node = previous[node]
            return list(reversed(path))
        for neighbor in graph.adjacency[node]:
            if neighbor not in previous:
                previous[neighbor] = node
                queue.append(neighbor)
    raise ValueError("nodes are disconnected")


def random_walk(graph: HarmonicGraph, start: int, steps: int, seed: int) -> list[int]:
    """Return a deterministic random walk, including the starting node."""
    _validate_index(graph, start)
    if steps < 0:
        raise ValueError("steps must be non-negative")
    random = Random(seed)
    walk = [start]
    for _ in range(steps):
        walk.append(random.choice(graph.adjacency[walk[-1]]))
    return walk


def weighted_walk(
    graph: HarmonicGraph, start: int, steps: int, seed: int, metric: str = "harmonic"
) -> list[int]:
    """Return a deterministic walk weighted toward closer harmonic neighbors."""
    _validate_index(graph, start)
    if steps < 0:
        raise ValueError("steps must be non-negative")
    random = Random(seed)
    walk = [start]
    for _ in range(steps):
        current = walk[-1]
        neighbors = graph.adjacency[current]
        weights = [1 / (1 + distance(graph.nodes[current].ratio, graph.nodes[node].ratio, metric)) for node in neighbors]
        walk.append(random.choices(neighbors, weights=weights, k=1)[0])
    return walk


def distance(left: Fraction, right: Fraction, metric: str) -> float:
    """Measure symmetric distance between two ratios using the selected metric."""
    if metric == "harmonic":
        interval = left / right
        return float(sum(abs(exponent) for exponent in monzo(interval).values()))
    if metric == "monzo":
        left_monzo, right_monzo = monzo(left), monzo(right)
        primes = set(left_monzo) | set(right_monzo)
        return float(sum(abs(left_monzo.get(prime, 0) - right_monzo.get(prime, 0)) for prime in primes))
    if metric == "cent":
        return abs(cents(left / right))
    raise ValueError("metric must be harmonic, monzo, or cent")


def _product(values: tuple[int, ...]) -> Fraction:
    product = Fraction(1)
    for value in values:
        product *= value
    return product


def _validate_index(graph: HarmonicGraph, index: int) -> None:
    if not 0 <= index < len(graph.nodes):
        raise ValueError("node index is outside the graph")
