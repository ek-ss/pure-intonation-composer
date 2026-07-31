from __future__ import annotations

from dataclasses import dataclass
from math import lcm

from app.rhythm.engine import euclidean_rhythm


@dataclass(frozen=True)
class LayerSpec:
    """Configuration for one percussion layer (rotation None means optimize)."""

    name: str
    steps: int
    pulses: int
    rotation: int | None = None
    phase_increment: int = 0
    phase_update_bars: int = 4
    base_velocity: int = 100


@dataclass(frozen=True)
class LayerResult:
    """Final rotated pattern and rotation-score breakdown for one layer."""

    name: str
    pattern: list[int]
    rotation: int
    score: float
    breakdown: dict[str, float]


def metrical_weight(index: int) -> int:
    """Simplified metrical weight: 4 on 16-step downbeats, 1 on off-16th steps."""
    if index % 16 == 0:
        return 4
    if index % 8 == 0:
        return 3
    if index % 4 == 0:
        return 2
    return 1


def analysis_length(step_counts: list[int], max_steps: int = 512) -> int:
    """Shared analysis-grid length: the layer LCM bounded by max_steps."""
    if not step_counts or any(count < 1 for count in step_counts) or max_steps < 1:
        raise ValueError("step counts must be positive and max_steps at least one")
    return min(lcm(*step_counts), max_steps)


def project(pattern: list[int], length: int) -> list[int]:
    """Repeat a binary pattern cyclically across the analysis grid."""
    if not pattern or any(value not in {0, 1} for value in pattern) or length < 1:
        raise ValueError("pattern must be a non-empty binary list and length at least one")
    size = len(pattern)
    return [pattern[index % size] for index in range(length)]


def _onsets(row: list[int]) -> list[int]:
    return [index for index, active in enumerate(row) if active]


def _syncopation(onsets: list[int], length: int) -> float:
    """Simplified syncopation: onset on a weak step followed by stronger steps.

    For each onset, the score is the maximum metrical weight within the next
    two grid steps (wrapping cyclically) minus the weight of the onset step.
    The mean over onsets is normalized by 3 and clamped to [0, 1].
    """
    if not onsets:
        return 0.0
    total = sum(
        max(metrical_weight((index + 1) % length), metrical_weight((index + 2) % length))
        - metrical_weight(index)
        for index in onsets
    )
    return max(0.0, min(1.0, (total / len(onsets)) / 3))


def _adjacent_onset_pairs(onsets: list[int]) -> int:
    return sum(1 for left, right in zip(onsets, onsets[1:]) if right - left == 1)


def analyze_layers(layers: dict[str, list[int]], max_steps: int = 512) -> dict[str, object]:
    """Compute density, collision, similarity, and syncopation metrics on the shared grid."""
    if not layers:
        raise ValueError("at least one layer is required")
    names = list(layers)
    length = analysis_length([len(layers[name]) for name in names], max_steps)
    grid = [project(layers[name], length) for name in names]
    combined = [1 if any(row[index] for row in grid) else 0 for index in range(length)]
    combined_onsets = _onsets(combined)
    pairs = [(left, right) for left in range(len(names)) for right in range(left + 1, len(names))]
    multi_target = min(4, len(names))
    return {
        "analysis_length": length,
        "density": {name: sum(row) / length for name, row in zip(names, grid)},
        "combined_density": sum(combined) / length,
        "pairwise_collisions": {
            f"{names[left]}-{names[right]}": sum(
                1 for step in range(length) if grid[left][step] and grid[right][step]
            )
            for left, right in pairs
        },
        "four_layer_collisions": sum(
            1 for step in range(length) if sum(row[step] for row in grid) >= multi_target
        ),
        "pairwise_similarity": {
            f"{names[left]}-{names[right]}": 1
            - sum(1 for step in range(length) if grid[left][step] != grid[right][step]) / length
            for left, right in pairs
        },
        "avg_inter_onset_interval": (
            sum(right - left for left, right in zip(combined_onsets, combined_onsets[1:]))
            / (len(combined_onsets) - 1)
            if len(combined_onsets) > 1
            else 0.0
        ),
        "syncopation": _syncopation(combined_onsets, length),
        "cluster_count": _adjacent_onset_pairs(combined_onsets),
    }


DEFAULT_SCORE_WEIGHTS: dict[str, float] = {
    "anchor": 1.0,
    "complement": 1.0,
    "syncopation": 0.5,
    "collision": 1.0,
    "density": 1.0,
    "cluster": 0.5,
    "similarity": 0.5,
}

_PAIR_COLLISION: dict[frozenset[str], float] = {
    frozenset(("kick", "snare")): 0.5,
    frozenset(("kick", "hat")): 0.1,
    frozenset(("kick", "perc")): 0.4,
    frozenset(("snare", "hat")): 0.1,
    frozenset(("snare", "perc")): 0.5,
    frozenset(("hat", "perc")): 0.2,
}
_DEFAULT_PAIR_COLLISION = 0.2

_ANCHOR_TARGETS: dict[str, tuple[int, ...]] = {
    "kick": (0, 4, 8, 12),
    "snare": (4, 12),
}


def _collision_penalty(
    name: str, row: list[int], placed: list[tuple[str, list[int]]], length: int, total_layers: int
) -> float:
    """Pair and multi-layer collision penalty involving the candidate, per grid step."""
    penalty = 0.0
    all_layers = min(4, total_layers)
    for step in range(length):
        if not row[step]:
            continue
        active = 1
        for placed_name, placed_row in placed:
            if placed_row[step]:
                active += 1
                penalty += _PAIR_COLLISION.get(
                    frozenset((name, placed_name)), _DEFAULT_PAIR_COLLISION
                )
        if all_layers >= 3 and active >= all_layers:
            penalty += 2.0
        elif active >= 3:
            penalty += 1.0
    return penalty / length


def _density_penalty(rows: list[list[int]], length: int) -> float:
    """Mean squared excess over the 0.3 density target in sliding 4-step windows."""
    layer_count = len(rows)
    total = 0.0
    for start in range(length):
        window_hits = sum(row[(start + offset) % length] for offset in range(4) for row in rows)
        total += max(0.0, window_hits / (4 * layer_count) - 0.3) ** 2
    return total / length


def _score_components(
    name: str, row: list[int], placed: list[tuple[str, list[int]]], length: int, total_layers: int
) -> dict[str, float]:
    hits = sum(row)
    targets = _ANCHOR_TARGETS.get(name, ())
    anchor = (
        sum(1 for step, active in enumerate(row) if active and step % 16 in targets) / hits
        if hits and targets
        else 0.0
    )
    complement = (
        sum(1 for step, active in enumerate(row) if active and not any(p[step] for _, p in placed)) / hits
        if hits
        else 0.0
    )
    combined_onsets = _onsets(
        [1 if active or any(p[step] for _, p in placed) else 0 for step, active in enumerate(row)]
    )
    similarity = max(
        (1 - sum(1 for step in range(length) if row[step] != p[step]) / length for _, p in placed),
        default=0.0,
    )
    return {
        "anchor": anchor,
        "complement": complement,
        "syncopation": _syncopation(_onsets(row), length),
        "collision_penalty": _collision_penalty(name, row, placed, length, total_layers),
        "density_penalty": _density_penalty([p for _, p in placed] + [row], length),
        "cluster_penalty": (
            _adjacent_onset_pairs(combined_onsets) / len(combined_onsets) if combined_onsets else 0.0
        ),
        "similarity_penalty": similarity,
    }


def _weighted_score(components: dict[str, float], weights: dict[str, float]) -> float:
    return (
        weights["anchor"] * components["anchor"]
        + weights["complement"] * components["complement"]
        + weights["syncopation"] * components["syncopation"]
        - weights["collision"] * components["collision_penalty"]
        - weights["density"] * components["density_penalty"]
        - weights["cluster"] * components["cluster_penalty"]
        - weights["similarity"] * components["similarity_penalty"]
    )


def optimize_rotations(
    specs: list[LayerSpec], max_steps: int = 512, weights: dict[str, float] | None = None
) -> list[LayerResult]:
    """Sequentially pick each layer's rotation against already-placed layers.

    The kick (layer named "kick") is placed first with its rotation kept as
    given (default 0); every remaining layer is optimized over all rotations
    in input order. Ties break to the lowest rotation index. Fully
    deterministic: no randomness is involved.
    """
    if not specs:
        raise ValueError("at least one layer is required")
    if len({spec.name for spec in specs}) != len(specs):
        raise ValueError("layer names must be unique")
    merged = {**DEFAULT_SCORE_WEIGHTS, **(weights or {})}
    length = analysis_length([spec.steps for spec in specs], max_steps)
    for spec in specs:
        euclidean_rhythm(spec.steps, spec.pulses)  # validates steps and pulses
    kick_index = next((index for index, spec in enumerate(specs) if spec.name == "kick"), None)
    order = ([kick_index] if kick_index is not None else []) + [
        index for index in range(len(specs)) if index != kick_index
    ]
    placed: list[tuple[str, list[int]]] = []
    results: dict[int, LayerResult] = {}
    for index in order:
        spec = specs[index]
        rotations = (
            [(spec.rotation or 0) % spec.steps] if index == kick_index else list(range(spec.steps))
        )
        best: LayerResult | None = None
        for rotation in rotations:
            rotated = euclidean_rhythm(spec.steps, spec.pulses, rotation)
            components = _score_components(spec.name, project(rotated, length), placed, length, len(specs))
            score = _weighted_score(components, merged)
            if best is None or score > best.score:
                best = LayerResult(spec.name, rotated, rotation, score, components)
        if best is None:
            raise ValueError("layer rotations could not be evaluated")
        results[index] = best
        placed.append((spec.name, project(best.pattern, length)))
    return [results[index] for index in range(len(specs))]


def phase_offsets(spec: LayerSpec, bars: int) -> list[int]:
    """Per-bar effective rotation offset, updated only at bar boundaries."""
    if bars < 1 or spec.steps < 1 or spec.phase_update_bars < 1:
        raise ValueError("bars, steps, and phase_update_bars must be at least one")
    base = (spec.rotation or 0) % spec.steps
    return [
        (base + (bar // spec.phase_update_bars) * spec.phase_increment) % spec.steps
        for bar in range(bars)
    ]


def accent_velocities(pattern: list[int], base_velocity: int, steps_per_bar: int = 16) -> list[int]:
    """Velocity per step (0 for rests) with metrical accents on strong steps."""
    if not pattern or any(value not in {0, 1} for value in pattern):
        raise ValueError("pattern must be a non-empty binary list")
    if not 1 <= base_velocity <= 127 or steps_per_bar < 1:
        raise ValueError("base_velocity must be 1..127 and steps_per_bar at least one")
    return [
        max(1, min(127, base_velocity + round(20 * (metrical_weight(index % steps_per_bar) - 1) / 3)))
        if active
        else 0
        for index, active in enumerate(pattern)
    ]
