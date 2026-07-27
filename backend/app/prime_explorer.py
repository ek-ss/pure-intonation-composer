"""Deterministic prime-lattice search primitives for the G12 Explorer."""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from itertools import combinations, permutations, product
from math import log2

from app.tuning.ratios import ratio_text

Vector = tuple[int, ...]
MAX_POINTS = 10_000


@dataclass(frozen=True)
class PrimePoint:
    vector: Vector
    ratio: Fraction
    normalized: Fraction
    octave_shift: int
    cents: float
    height: int


@dataclass(frozen=True)
class PitchCluster:
    id: str
    cents: float
    representative: PrimePoint
    sources: tuple[PrimePoint, ...]


def is_prime(value: int) -> bool:
    if value < 2:
        return False
    divisor = 2
    while divisor * divisor <= value:
        if value % divisor == 0:
            return False
        divisor += 1 if divisor == 2 else 2
    return True


def validate_basis(primes: tuple[int, ...]) -> None:
    if not 1 <= len(primes) <= 5:
        raise ValueError("prime basis must contain 1..5 primes")
    if len(set(primes)) != len(primes) or any(not is_prime(prime) for prime in primes):
        raise ValueError("prime basis must contain unique prime integers")


def normalize(ratio: Fraction) -> tuple[Fraction, int]:
    shift = 0
    while ratio >= 2:
        ratio /= 2
        shift -= 1
    while ratio < 1:
        ratio *= 2
        shift += 1
    return ratio, shift


def enumerate_points(primes: tuple[int, ...], exponent_limit: int, height_limit: int) -> list[PrimePoint]:
    validate_basis(primes)
    if not 0 <= exponent_limit <= 8:
        raise ValueError("exponent_limit must be between 0 and 8")
    if not 0 <= height_limit <= 32:
        raise ValueError("height_limit must be between 0 and 32")
    vectors = [
        tuple(vector)
        for vector in product(range(-exponent_limit, exponent_limit + 1), repeat=len(primes))
        if sum(abs(value) for value in vector) <= height_limit
    ]
    if len(vectors) > MAX_POINTS:
        raise ValueError(f"enumeration contains {len(vectors)} points, limit is {MAX_POINTS}")
    points: list[PrimePoint] = []
    for vector in sorted(vectors):
        ratio = Fraction(1)
        for prime, exponent in zip(primes, vector):
            ratio *= Fraction(prime) ** exponent
        normalized, octave_shift = normalize(ratio)
        points.append(
            PrimePoint(
                vector=vector,
                ratio=ratio,
                normalized=normalized,
                octave_shift=octave_shift,
                cents=1200 * log2(float(normalized)),
                height=sum(abs(value) for value in vector),
            )
        )
    return points


def circular_distance(left: float, right: float) -> float:
    difference = abs(left - right) % 1200
    return min(difference, 1200 - difference)


def _representative(points: list[PrimePoint]) -> PrimePoint:
    return min(points, key=lambda point: (point.height, point.vector, point.cents))


def cluster_points(points: list[PrimePoint], tolerance_cents: float) -> list[PitchCluster]:
    if not 0 < tolerance_cents <= 100:
        raise ValueError("tolerance_cents must be greater than 0 and at most 100")
    if not points:
        return []
    ordered = sorted(points, key=lambda point: (point.cents, point.height, point.vector))
    groups: list[list[PrimePoint]] = [[ordered[0]]]
    for point in ordered[1:]:
        if point.cents - groups[-1][-1].cents <= tolerance_cents:
            groups[-1].append(point)
        else:
            groups.append([point])
    if len(groups) > 1 and circular_distance(groups[0][0].cents, groups[-1][-1].cents) <= tolerance_cents:
        groups[0] = groups[-1] + groups[0]
        groups.pop()
    clusters = []
    for index, group in enumerate(groups):
        representative = _representative(group)
        clusters.append(PitchCluster(f"pc-{index}", representative.cents, representative, tuple(group)))
    return sorted(clusters, key=lambda cluster: (cluster.cents, cluster.representative.vector))


def select_scale(clusters: list[PitchCluster], target_count: int) -> list[PitchCluster]:
    """Farthest-point sampling on a circular pitch space, rooted at 1/1 when present."""
    if not 1 <= target_count <= len(clusters):
        raise ValueError("target_count must be between 1 and the number of pitch classes")
    root = min(clusters, key=lambda cluster: (circular_distance(cluster.cents, 0), cluster.representative.height, cluster.id))
    selected = [root]
    remaining = [cluster for cluster in clusters if cluster.id != root.id]
    while len(selected) < target_count:
        candidate = max(
            remaining,
            key=lambda cluster: (
                min(circular_distance(cluster.cents, chosen.cents) for chosen in selected),
                -cluster.representative.height,
                tuple(-value for value in cluster.representative.vector),
            ),
        )
        selected.append(candidate)
        remaining.remove(candidate)
    return sorted(selected, key=lambda cluster: cluster.cents)


def scale_metrics(scale: list[PitchCluster]) -> dict[str, object]:
    cents_values = [cluster.cents for cluster in scale]
    gaps = [
        (cents_values[(index + 1) % len(cents_values)] - cents_values[index]) % 1200
        for index in range(len(cents_values))
    ]
    return {
        "gaps_cents": [round(gap, 5) for gap in gaps],
        "min_gap_cents": round(min(gaps), 5),
        "max_gap_cents": round(max(gaps), 5),
        "gap_range_cents": round(max(gaps) - min(gaps), 5),
    }


def point_payload(point: PrimePoint) -> dict[str, object]:
    return {
        "vector": list(point.vector),
        "ratio": ratio_text(point.ratio),
        "normalized_ratio": ratio_text(point.normalized),
        "octave_shift": point.octave_shift,
        "cents": round(point.cents, 5),
        "height": point.height,
    }


def explore(primes: tuple[int, ...], exponent_limit: int, height_limit: int, tolerance_cents: float, target_count: int) -> dict[str, object]:
    points = enumerate_points(primes, exponent_limit, height_limit)
    clusters = cluster_points(points, tolerance_cents)
    if target_count > len(clusters):
        raise ValueError(f"target_count must not exceed {len(clusters)} generated pitch classes")
    scale = select_scale(clusters, target_count)
    return {
        "basis": list(primes),
        "point_count": len(points),
        "cluster_count": len(clusters),
        "tolerance_cents": tolerance_cents,
        "clusters": [
            {
                "id": cluster.id,
                "cents": round(cluster.cents, 5),
                "representative": point_payload(cluster.representative),
                "sources": [point_payload(point) for point in cluster.sources],
            }
            for cluster in clusters
        ],
        "scale": [
            {"id": cluster.id, "cents": round(cluster.cents, 5), "representative": point_payload(cluster.representative)}
            for cluster in scale
        ],
        "metrics": scale_metrics(scale),
    }


def _mst_length(points: list[PitchCluster]) -> float:
    if len(points) < 2:
        return 0.0
    used = {0}
    total = 0.0
    while len(used) < len(points):
        distance, index = min(
            (circular_distance(points[source].cents, points[target].cents), target)
            for source in used
            for target in range(len(points))
            if target not in used
        )
        used.add(index)
        total += distance
    return total


def discover_chords(
    primes: tuple[int, ...], exponent_limit: int, height_limit: int,
    tolerance_cents: float, target_count: int, tone_count: int, candidate_limit: int,
) -> dict[str, object]:
    points = enumerate_points(primes, exponent_limit, height_limit)
    scale = select_scale(cluster_points(points, tolerance_cents), target_count)
    if not 2 <= tone_count <= min(6, len(scale)):
        raise ValueError("tone_count must be between 2 and the scale size (maximum 6)")
    root = min(scale, key=lambda cluster: (circular_distance(cluster.cents, 0), cluster.id))
    candidates = []
    for others in combinations([cluster for cluster in scale if cluster.id != root.id], tone_count - 1):
        chord = [root, *others]
        distances = [circular_distance(left.cents, right.cents) for left, right in combinations(chord, 2)]
        mean_distance = sum(distances) / len(distances)
        height = sum(cluster.representative.height for cluster in chord) / len(chord)
        metrics = {
            "mst_cents": round(_mst_length(chord), 5),
            "diameter_cents": round(max(distances), 5),
            "mean_distance_cents": round(mean_distance, 5),
            "mean_height": round(height, 5),
            "pair_consonance": round(sum(1 / (1 + distance / 100) for distance in distances) / len(distances), 5),
            "algorithm_version": "g12-chord-v1",
        }
        vectors = [cluster.representative.vector for cluster in chord]
        shape_id = ";".join(",".join(str(value - vectors[0][dimension]) for dimension, value in enumerate(vector)) for vector in vectors
        )
        candidates.append((metrics["mst_cents"], metrics["mean_height"], shape_id, chord, metrics))
    candidates.sort(key=lambda item: (item[0], item[1], item[2]))
    return {
        "scale": [
            {"id": cluster.id, "cents": round(cluster.cents, 5), "representative": point_payload(cluster.representative)}
            for cluster in scale
        ],
        "candidates": [
            {
                "id": f"chord-{index}",
                "shape_id": shape_id,
                "tones": [{"id": cluster.id, "cents": round(cluster.cents, 5), "representative": point_payload(cluster.representative)} for cluster in chord],
                "metrics": metrics,
            }
            for index, (_mst, _height, shape_id, chord, metrics) in enumerate(candidates[:candidate_limit])
        ],
    }


def progression_metrics(chords: list[list[float]]) -> list[dict[str, object]]:
    if len(chords) < 2:
        return []
    transitions: list[dict[str, object]] = []
    for previous, current in zip(chords, chords[1:]):
        if len(previous) != len(current):
            raise ValueError("all progression chords must have the same voice count")
        assignments = [sum(circular_distance(left, right) for left, right in zip(previous, order)) for order in permutations(current)]
        common = len({round(value, 4) for value in previous} & {round(value, 4) for value in current})
        transitions.append({"common_tones": common, "johnson_distance": len(previous) - common, "voice_leading_cents": round(min(assignments), 5)})
    return transitions
