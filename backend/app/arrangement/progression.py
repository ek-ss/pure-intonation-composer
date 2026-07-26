from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from math import log2
from random import Random

from app.arrangement.chords import ChordInstance, TransitionEdge
from app.arrangement.form import ArrangementSection
from app.arrangement.profiles import GenreProfile

BEAM_WIDTH = 8


@dataclass(frozen=True)
class ProgressionSlot:
    index: int
    section_id: str
    instance_index: int
    start_subdivision: int
    duration_subdivisions: int
    transition: TransitionEdge | None
    cost: float


def plan_chord_slots(
    sections: list[ArrangementSection], subdivisions_per_bar: int
) -> list[tuple[ArrangementSection, int, int]]:
    """Split every section into (section, start_subdivision, duration) chord slots."""
    slots: list[tuple[ArrangementSection, int, int]] = []
    for section in sections:
        span = section.bars * subdivisions_per_bar
        count = max(1, round(section.bars * section.harmony_density * 2))
        base = section.start_bar * subdivisions_per_bar
        for index in range(count):
            start = base + round(index * span / count)
            end = base + round((index + 1) * span / count)
            slots.append((section, start, end - start))
    return slots


def generate_progression(
    profile: GenreProfile,
    instances: list[ChordInstance],
    graph: list[list[TransitionEdge]],
    sections: list[ArrangementSection],
    slots: list[tuple[ArrangementSection, int, int]],
    harmonic_complexity: float,
    repetition: float,
    seed: int,
) -> tuple[list[ProgressionSlot], list[str]]:
    """Bounded seeded beam search over the chord-transition graph."""
    trace: list[str] = []
    preferred = set(profile.harmony.preferred_tags)
    available_tags = {tag for instance in instances for tag in instance.tags}
    missing = preferred - available_tags
    for tag in sorted(missing):
        trace.append(
            f"preference relaxed: no chord tagged '{tag}' exists in the vocabulary; "
            "using the closest valid chords"
        )
    random = Random(seed ^ 0x5EED)
    motif_memory: dict[str, list[int]] = {}
    beam: list[tuple[float, list[int]]] = [(0.0, [])]
    last_slot_of_section = _section_final_slots(slots)

    for slot_index, (section, start, duration) in enumerate(slots):
        motif = motif_memory.get(section.canonical_role)
        position = sum(1 for s, _, _ in slots[:slot_index] if s.id == section.id)
        candidates = _score_slot(
            profile,
            instances,
            graph,
            beam,
            section,
            slot_index in last_slot_of_section,
            motif,
            position,
            harmonic_complexity,
            repetition,
            random,
        )
        candidates.sort(key=lambda item: (item[0], item[1]))
        beam = candidates[:BEAM_WIDTH]
        if slot_index in last_slot_of_section:
            best = beam[0][1]
            motif_memory.setdefault(
                section.canonical_role,
                best[len(best) - position - 1 :],
            )
    best_sequence = beam[0][1]
    result = []
    for slot_index, (section, start, duration) in enumerate(slots):
        instance_index = best_sequence[slot_index]
        transition = (
            graph[best_sequence[slot_index - 1]][instance_index] if slot_index else None
        )
        result.append(
            ProgressionSlot(
                index=slot_index,
                section_id=section.id,
                instance_index=instance_index,
                start_subdivision=start,
                duration_subdivisions=duration,
                transition=transition,
                cost=round(beam[0][0], 6),
            )
        )
    trace.append(
        f"progression: {len(result)} chord slots over {len(sections)} sections, "
        f"beam cost {beam[0][0]:.3f}"
    )
    return result, trace


def _score_slot(
    profile: GenreProfile,
    instances: list[ChordInstance],
    graph: list[list[TransitionEdge]],
    beam: list[tuple[float, list[int]]],
    section: ArrangementSection,
    is_section_final: bool,
    motif: list[int] | None,
    position: int,
    harmonic_complexity: float,
    repetition: float,
    random: Random,
) -> list[tuple[float, list[int]]]:
    weights = profile.harmony.weights
    preferred = set(profile.harmony.preferred_tags)
    avoid = set(profile.harmony.avoid_tags)
    energy = section.energy_at(section.start_bar + section.bars // 2)
    complexity_target = 1.5 + 3 * harmonic_complexity * (0.3 + 0.7 * energy)
    scored: list[tuple[float, list[int]]] = []
    sounding_signatures = [_sounding_signature(instance) for instance in instances]
    for cost_so_far, sequence in beam:
        for instance_index, instance in enumerate(instances):
            cost = cost_so_far
            if sequence:
                edge = graph[sequence[-1]][instance_index]
                cost += weights.voice_leading * edge.voice_leading_cents / 600
                cost += weights.root_motion * min(
                    edge.root_motion_cents, profile.harmony.max_root_motion_cents
                ) / 600
                cost -= weights.common_tone * edge.common_tones / max(len(instance.tones), 1)
                if (
                    sounding_signatures[instance_index]
                    == sounding_signatures[sequence[-1]]
                ):
                    cost += weights.repetition * (1 - repetition)
                    cost += (1 - repetition) * (1.5 + weights.common_tone)
            cost += weights.complexity * abs(instance.complexity - complexity_target) / 6
            cost += weights.section_energy * abs(instance.tension - energy * 0.8)
            if is_section_final:
                stability = 1 - instance.tension
                if "stable" in instance.tags or "cadential" in instance.tags:
                    stability = min(1.0, stability + 0.3)
                cost += (
                    weights.cadence * profile.harmony.cadence_stability * (1 - stability)
                )
            if preferred & set(instance.tags):
                cost -= 0.3
            if avoid & set(instance.tags):
                cost += 0.8
            if (
                motif is not None
                and position < len(motif)
                and sounding_signatures[motif[position]]
                == sounding_signatures[instance_index]
            ):
                cost -= weights.motif * (0.25 + 0.75 * repetition)
            size_mismatch = abs(len(instance.tones) - profile.harmony.chord_size_preference)
            cost += 0.1 * size_mismatch
            cost += random.random() * 1e-6  # seeded tie-break
            scored.append((cost, [*sequence, instance_index]))
    return scored


def _sounding_signature(instance: ChordInstance) -> tuple[Fraction, ...]:
    """Identify harmonically equivalent instances by their sounding pitch classes."""
    return tuple(sorted(set(instance.tones)))


def _section_final_slots(slots: list[tuple[ArrangementSection, int, int]]) -> set[int]:
    finals: set[int] = set()
    for index in range(len(slots) - 1):
        if slots[index][0].id != slots[index + 1][0].id:
            finals.add(index)
    finals.add(len(slots) - 1)
    return finals


def voice_progression(
    progression: list[ProgressionSlot],
    instances: list[ChordInstance],
    register_low: float,
    register_high: float,
) -> list[tuple[Fraction, ...]]:
    """Place chord tones in the register, minimizing per-voice cents movement."""
    voiced: list[tuple[Fraction, ...]] = []
    previous: tuple[Fraction, ...] | None = None
    for slot in progression:
        instance = instances[slot.instance_index]
        placed = []
        for tone_index, tone in enumerate(instance.tones):
            reference = (
                previous[min(tone_index, len(previous) - 1)] if previous else None
            )
            placed.append(_place_in_register(tone, register_low, register_high, reference))
        voiced.append(tuple(placed))
        previous = tuple(placed)
    return voiced


def _place_in_register(
    pitch_class: Fraction, low: float, high: float, reference: Fraction | None
) -> Fraction:
    candidates = [pitch_class * Fraction(2) ** octave for octave in range(-4, 5)]
    in_range = [
        candidate for candidate in candidates if low <= float(candidate) <= high
    ]
    pool = in_range or candidates
    if reference is None:
        return min(pool, key=lambda candidate: (abs(float(candidate) - (low + high) / 2), candidate))
    return min(
        pool,
        key=lambda candidate: (
            abs(1200 * log2(float(candidate / reference))),
            candidate,
        ),
    )
