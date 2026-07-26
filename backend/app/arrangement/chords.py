from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from math import log2

from app.tuning.analysis import cents
from app.tuning.ratios import reduce_to_octave

MAX_CHORD_INSTANCES = 128


@dataclass(frozen=True)
class BasicChordInput:
    """Validated, mode-agnostic view of one user-supplied basic chord."""

    id: str
    name: str
    mode: str  # absolute | degree_template | ratio_template
    tones: tuple[Fraction | int, ...]
    root_degree: int | None
    allowed_root_degrees: tuple[int, ...] | None
    tone_vectors: tuple[tuple[int, ...], ...] | None
    tags: tuple[str, ...]


@dataclass(frozen=True)
class ChordInstance:
    """One materialized chord: a template placed at a concrete root."""

    id: str
    template_id: str
    name: str
    mode: str
    root: Fraction
    tones: tuple[Fraction, ...]  # pitch classes in [1, 2)
    tags: tuple[str, ...]
    root_degree: int | None
    tone_vectors: tuple[tuple[int, ...], ...] | None
    cents_span: float
    complexity: float
    tension: float


@dataclass(frozen=True)
class TransitionEdge:
    source: int
    target: int
    root_motion_cents: float
    common_tones: int
    voice_leading_cents: float
    tension_change: float


def ratio_complexity(ratio: Fraction) -> float:
    """Count of prime factors (with multiplicity) in numerator and denominator."""
    total = 0
    for value in (abs(ratio.numerator), abs(ratio.denominator)):
        number = value
        divisor = 2
        while divisor * divisor <= number:
            while number % divisor == 0:
                total += 1
                number //= divisor
            divisor += 1
        if number > 1:
            total += 1
    return float(total)


def _tension(tones: tuple[Fraction, ...]) -> float:
    """Roughness proxy: mean dyad dissonance, 0 for simple intervals."""
    if len(tones) < 2:
        return 0.0
    total = 0.0
    pairs = 0
    for i in range(len(tones)):
        for j in range(i + 1, len(tones)):
            interval = reduce_to_octave(tones[j] / tones[i])
            total += 1 - 1 / (1 + ratio_complexity(interval))
            pairs += 1
    return round(total / pairs, 6)


def _cents_span(tones: tuple[Fraction, ...]) -> float:
    if len(tones) < 2:
        return 0.0
    return round(cents(max(tones) / min(tones)), 5)


def _normalize_tones(tones: list[Fraction]) -> tuple[Fraction, ...]:
    return tuple(reduce_to_octave(tone) for tone in tones)


def materialize_chords(
    chords: list[BasicChordInput], scale: list[Fraction]
) -> tuple[list[ChordInstance], list[str]]:
    """Materialize every basic chord over its allowed roots and analyze it.

    Returns the instances plus trace notes for any skipped materialization.
    """
    if not chords:
        raise ValueError("chord_vocabulary must contain at least one chord")
    scale_pcs = sorted({reduce_to_octave(ratio) for ratio in scale})
    if len(scale_pcs) < 2:
        raise ValueError("the scale must contain at least two distinct pitch classes")
    instances: list[ChordInstance] = []
    trace: list[str] = []
    for chord in chords:
        if chord.mode == "absolute":
            tones = _normalize_tones([_expect_ratio(tone, chord.id) for tone in chord.tones])
            instances.append(
                _make_instance(chord, chord.id, tones[0], tones, None, chord.tone_vectors)
            )
            continue
        roots = (
            list(chord.allowed_root_degrees)
            if chord.allowed_root_degrees is not None
            else list(range(len(scale_pcs)))
        )
        if chord.root_degree is not None:
            roots = [chord.root_degree]
        for degree in roots:
            if not 0 <= degree < len(scale_pcs):
                trace.append(
                    f"chord '{chord.id}': root degree {degree} is outside the scale "
                    f"(0..{len(scale_pcs) - 1}); skipped"
                )
                continue
            root = scale_pcs[degree]
            if chord.mode == "degree_template":
                tones = _normalize_tones(
                    [
                        scale_pcs[(degree + _expect_degree(tone, chord.id)) % len(scale_pcs)]
                        for tone in chord.tones
                    ]
                )
            else:  # ratio_template
                tones = _normalize_tones(
                    [root * _expect_ratio(tone, chord.id) for tone in chord.tones]
                )
            instance_id = f"{chord.id}@{degree}"
            instances.append(
                _make_instance(chord, instance_id, root, tones, degree, chord.tone_vectors)
            )
    if len(instances) > MAX_CHORD_INSTANCES:
        raise ValueError(
            f"chord vocabulary materializes to {len(instances)} instances; "
            f"the limit is {MAX_CHORD_INSTANCES} (narrow allowed_root_degrees)"
        )
    if len(instances) < 2:
        raise ValueError(
            "chord vocabulary must materialize at least two chord instances; "
            "check allowed_root_degrees and template modes"
        )
    return instances, trace


def _make_instance(
    chord: BasicChordInput,
    instance_id: str,
    root: Fraction,
    tones: tuple[Fraction, ...],
    root_degree: int | None,
    tone_vectors: tuple[tuple[int, ...], ...] | None,
) -> ChordInstance:
    complexity = round(sum(ratio_complexity(tone) for tone in tones) / len(tones), 6)
    return ChordInstance(
        id=instance_id,
        template_id=chord.id,
        name=chord.name,
        mode=chord.mode,
        root=root,
        tones=tones,
        tags=chord.tags,
        root_degree=root_degree,
        tone_vectors=tone_vectors,
        cents_span=_cents_span(tones),
        complexity=complexity,
        tension=_tension(tones),
    )


def _expect_ratio(tone: Fraction | int, chord_id: str) -> Fraction:
    if not isinstance(tone, Fraction):
        raise ValueError(
            f"chord '{chord_id}': absolute and ratio_template tones must be ratios"
        )
    if tone <= 0:
        raise ValueError(f"chord '{chord_id}': tones must be positive ratios")
    return tone


def _expect_degree(tone: Fraction | int, chord_id: str) -> int:
    if not isinstance(tone, int):
        raise ValueError(f"chord '{chord_id}': degree_template tones must be degree offsets")
    return tone


def build_transition_graph(instances: list[ChordInstance]) -> list[list[TransitionEdge]]:
    """Directed graph over instances with per-edge movement metrics."""
    graph: list[list[TransitionEdge]] = []
    for source_index, source in enumerate(instances):
        row = []
        for target_index, target in enumerate(instances):
            row.append(
                TransitionEdge(
                    source=source_index,
                    target=target_index,
                    root_motion_cents=_root_motion(source.root, target.root),
                    common_tones=len(set(source.tones) & set(target.tones)),
                    voice_leading_cents=_voice_leading_cost(source.tones, target.tones),
                    tension_change=round(target.tension - source.tension, 6),
                )
            )
        graph.append(row)
    return graph


def _root_motion(source: Fraction, target: Fraction) -> float:
    motion = abs(1200 * log2(float(target / source)))
    return round(min(motion, 1200 - motion), 5)


def _voice_leading_cost(
    source: tuple[Fraction, ...], target: tuple[Fraction, ...]
) -> float:
    """Greedy minimum cents movement between two pitch-class sets."""
    source_cents = sorted(cents(tone) for tone in source)
    target_cents = sorted(cents(tone) for tone in target)
    remaining = list(target_cents)
    total = 0.0
    for tone in source_cents:
        if not remaining:
            total += 300.0  # removed tone counts as half-cost deletion
            continue
        nearest = min(remaining, key=lambda candidate: abs(candidate - tone))
        total += abs(nearest - tone)
        remaining.remove(nearest)
    # Unmatched target tones count as new onsets at half cost.
    total += sum(300.0 for _ in remaining)
    return round(total / max(len(source), len(target)), 5)
