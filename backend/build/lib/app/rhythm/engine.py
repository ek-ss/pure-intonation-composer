from __future__ import annotations

from dataclasses import dataclass
from random import Random


@dataclass(frozen=True)
class HumanizedHit:
    step: int
    timing_offset_ms: float
    velocity: int


def euclidean_rhythm(steps: int, pulses: int, rotation: int = 0) -> list[int]:
    """Distribute pulses as evenly as possible across a fixed number of steps."""
    if not 1 <= steps <= 256 or not 0 <= pulses <= steps:
        raise ValueError("pulses must be between zero and steps, and steps must be 1..256")
    pattern = [1 if (index * pulses) % steps < pulses else 0 for index in range(steps)]
    offset = rotation % steps
    return pattern[-offset:] + pattern[:-offset] if offset else pattern


def state_transition_graph(steps: int) -> dict[str, object]:
    """Build the binary rhythm state graph where every edge has Hamming distance one."""
    if not 1 <= steps <= 12:
        raise ValueError("state graph steps must be between 1 and 12")
    nodes = [format(value, f"0{steps}b") for value in range(1 << steps)]
    edges = [
        (node, node[:bit] + ("0" if node[bit] == "1" else "1") + node[bit + 1 :])
        for node in nodes
        for bit in range(steps)
        if node < node[:bit] + ("0" if node[bit] == "1" else "1") + node[bit + 1 :]
    ]
    return {"nodes": nodes, "edges": edges}


def phase_shift(patterns: list[list[int]], length: int, phases: list[int] | None = None) -> list[list[int]]:
    """Expand independent cyclic patterns into a shared timeline with per-layer phases."""
    if length < 1 or not patterns or any(not pattern for pattern in patterns):
        raise ValueError("length and all patterns must be non-empty")
    if any(value not in {0, 1} for pattern in patterns for value in pattern):
        raise ValueError("patterns must contain only zeroes and ones")
    phases = phases or [0] * len(patterns)
    if len(phases) != len(patterns):
        raise ValueError("phases must have one value per pattern")
    return [
        [pattern[(step + phase) % len(pattern)] for step in range(length)]
        for pattern, phase in zip(patterns, phases)
    ]


def humanize(
    pattern: list[int],
    seed: int,
    timing_amount_ms: float = 12,
    velocity_amount: int = 10,
    base_velocity: int = 100,
) -> list[HumanizedHit]:
    """Apply deterministic timing and velocity variation to active rhythm steps."""
    if not pattern or any(value not in {0, 1} for value in pattern):
        raise ValueError("pattern must contain at least one zero or one value")
    if timing_amount_ms < 0 or velocity_amount < 0 or not 1 <= base_velocity <= 127:
        raise ValueError("humanization settings are invalid")
    random = Random(seed)
    return [
        HumanizedHit(
            step=index,
            timing_offset_ms=round(random.uniform(-timing_amount_ms, timing_amount_ms), 5),
            velocity=max(1, min(127, base_velocity + random.randint(-velocity_amount, velocity_amount))),
        )
        for index, active in enumerate(pattern)
        if active
    ]
