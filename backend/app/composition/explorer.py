"""Instrument-constrained, multi-candidate composition exploration."""

from __future__ import annotations

from collections import Counter
from fractions import Fraction
from hashlib import sha256
from math import exp, log2, sqrt
from random import Random
from statistics import fmean, pstdev
from typing import Any

from app.composition.instrument_profiles import (
    INSTRUMENT_PROFILES,
    STYLE_DEFAULT_PALETTES,
    public_instrument_profiles,
)


STYLE_NAMES = {
    "fractional_pop": "Fractional Pop",
    "fractional_jpop": "Fractional J-Pop",
    "kawaii_fractional_future_pop": "Kawaii Fractional Future Pop",
    "mixed": "Mixed Fractional Style",
}

BASE_STYLES = (
    "fractional_pop",
    "fractional_jpop",
    "kawaii_fractional_future_pop",
)

FORM_GRAMMARS: dict[str, tuple[tuple[str, ...], ...]] = {
    "fractional_pop": (
        ("intro", "verse", "pre", "chorus", "verse", "chorus", "bridge", "chorus", "outro"),
        ("intro", "verse", "chorus", "verse", "pre", "chorus", "break", "final", "outro"),
        ("verse", "verse", "chorus", "bridge", "chorus", "instrumental", "final", "outro"),
        ("intro", "verse", "pre", "chorus", "break", "chorus", "final", "outro"),
    ),
    "fractional_jpop": (
        ("intro", "a", "b", "chorus", "a", "b", "chorus", "bridge", "final", "outro"),
        ("intro", "a", "a_variation", "b", "chorus", "instrumental", "b", "final", "outro"),
        ("a", "b", "chorus", "break", "a_variation", "chorus", "bridge", "final", "outro"),
        ("intro", "a", "b", "chorus", "minimal", "b", "chorus", "final", "outro"),
    ),
    "kawaii_fractional_future_pop": (
        ("intro", "verse", "pre", "drop", "minimal", "verse", "pre", "final", "outro"),
        ("intro", "minimal", "verse", "pre", "drop", "break", "verse", "final", "outro"),
        ("verse", "pre", "drop", "instrumental", "minimal", "pre", "final", "outro"),
        ("intro", "verse", "drop", "break", "verse", "pre", "drop", "final", "outro"),
    ),
}

ROLE_ENERGY = {
    "intro": 0.22,
    "verse": 0.42,
    "a": 0.44,
    "a_variation": 0.52,
    "pre": 0.66,
    "b": 0.67,
    "chorus": 0.86,
    "drop": 0.94,
    "final": 1.0,
    "bridge": 0.58,
    "instrumental": 0.72,
    "minimal": 0.30,
    "break": 0.34,
    "outro": 0.20,
}

FEATURE_KEYS = (
    "form_variety",
    "section_contrast",
    "root_variety",
    "root_motion",
    "tension_smoothness",
    "harmony_repetition",
    "melody_density",
    "rest_space",
    "syncopation",
    "drum_density",
    "instrument_coverage",
    "part_turnover",
)

DEFAULT_EVALUATION_WEIGHTS = {
    "structural_coherence": 1.0,
    "section_contrast": 1.0,
    "harmonic_interest": 1.0,
    "tension_smoothness": 0.9,
    "melodic_identity": 0.9,
    "rhythmic_identity": 0.8,
    "repetition_balance": 1.0,
    "ratio_color_usage": 0.7,
    "instrumentation_fit": 1.1,
}


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return min(high, max(low, value))


def _seed(master: int, candidate: int, component: str) -> int:
    digest = sha256(f"{master}:{candidate}:{component}".encode("ascii")).digest()
    return int.from_bytes(digest[:8], "big") & 0x7FFFFFFF


def _ratio_text(value: Fraction) -> str:
    return f"{value.numerator}/{value.denominator}"


def _octave(value: Fraction) -> Fraction:
    while value < 1:
        value *= 2
    while value >= 2:
        value /= 2
    return value


def _parse_scale(values: list[str]) -> tuple[Fraction, ...]:
    result: list[Fraction] = []
    for value in values:
        ratio = _octave(Fraction(value))
        if ratio not in result:
            result.append(ratio)
    result.sort(key=float)
    if Fraction(1) not in result:
        raise ValueError("scale_ratios must contain 1/1")
    return tuple(result)


def _fit_ratio(value: Fraction, midi_range: list[int], base_frequency: float) -> Fraction:
    base_midi = 69 + 12 * log2(base_frequency / 440)
    target = (midi_range[0] + midi_range[1]) / 2
    result = value
    while base_midi + 12 * log2(float(result)) < target - 6:
        result *= 2
    while base_midi + 12 * log2(float(result)) > target + 6:
        result /= 2
    return result


def _weighted_choice(random: Random, items: list[Any], costs: list[float], temperature: float) -> Any:
    if not items:
        raise ValueError("cannot sample an empty candidate list")
    if temperature <= 0.001:
        return items[costs.index(min(costs))]
    minimum = min(costs)
    weights = [exp(-(cost - minimum) / max(0.04, temperature)) for cost in costs]
    target = random.random() * sum(weights)
    cursor = 0.0
    for item, weight in zip(items, weights, strict=True):
        cursor += weight
        if cursor >= target:
            return item
    return items[-1]


def _style_weights(config: dict[str, Any]) -> dict[str, float]:
    style = str(config["style"])
    if style != "mixed":
        return {item: float(item == style) for item in BASE_STYLES}
    raw = dict(config.get("style_mix") or {})
    weights = {item: max(0.0, float(raw.get(item, 0.0))) for item in BASE_STYLES}
    total = sum(weights.values())
    if total <= 0:
        raise ValueError("mixed style requires at least one positive style weight")
    return {item: value / total for item, value in weights.items()}


def _choose_style(random: Random, weights: dict[str, float]) -> str:
    target = random.random() * sum(weights.values())
    cursor = 0.0
    for style in BASE_STYLES:
        cursor += weights[style]
        if cursor >= target:
            return style
    return BASE_STYLES[-1]


def _default_instrument_selections(
    style: str, weights: dict[str, float]
) -> list[dict[str, Any]]:
    if style != "mixed":
        return [{"id": item} for item in STYLE_DEFAULT_PALETTES[style]]
    result: list[dict[str, Any]] = []
    for instrument_id in STYLE_DEFAULT_PALETTES["mixed"]:
        affinity = sum(
            weights[item]
            for item in BASE_STYLES
            if instrument_id in STYLE_DEFAULT_PALETTES[item]
        )
        if affinity > 0:
            result.append(
                {"id": instrument_id, "priority": min(1.0, 0.35 + affinity * 0.65)}
            )
    return result


def _instrument_palette(config: dict[str, Any]) -> tuple[list[dict[str, Any]], list[str]]:
    selections = list(config.get("instrument_palette") or [])
    if not selections:
        selections = _default_instrument_selections(
            str(config["style"]), _style_weights(config)
        )
    profiles: list[dict[str, Any]] = []
    warnings: list[str] = []
    seen: set[str] = set()
    for selection in selections:
        instrument_id = str(selection["id"]).upper()
        if instrument_id in seen:
            continue
        seen.add(instrument_id)
        source = INSTRUMENT_PROFILES.get(instrument_id)
        if source is None:
            warnings.append(f"Unknown preset {instrument_id} was ignored")
            continue
        profile = dict(source)
        preferred = list(selection.get("preferred_roles") or [])
        if preferred:
            profile["roles"] = list(dict.fromkeys(preferred + list(profile["roles"])))
        profile["priority"] = float(selection.get("priority", 0.7))
        profiles.append(profile)
    if not profiles:
        raise ValueError("instrument_palette does not contain a known PI preset")
    roles = {role for profile in profiles for role in profile["roles"]}
    if "bass" not in roles:
        policy = str(config.get("missing_role_policy", "warn"))
        if policy == "substitute":
            substitute = min(
                (profile for profile in profiles if profile["drum_note"] is None),
                key=lambda profile: int(profile["midi_range"][0]),
                default=None,
            )
            if substitute is not None:
                substitute["roles"] = list(substitute["roles"]) + ["bass"]
                warnings.append(f"{substitute['id']} provides low-mid root support in place of bass")
        elif policy == "warn":
            warnings.append("No bass preset: low root support will be omitted")
    if "harmony" not in roles and "rhythmic_harmony" not in roles:
        warnings.append("No dedicated harmony preset: a pulse or lead preset will provide harmony")
    return profiles, warnings


def _form(
    style: str,
    style_weights: dict[str, float],
    length_bars: int,
    temperature: float,
    random: Random,
    profiles: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    form_style = _choose_style(random, style_weights) if style == "mixed" else style
    grammar = FORM_GRAMMARS[form_style]
    variant = 0 if random.random() > temperature else random.randrange(len(grammar))
    roles = list(grammar[variant])
    available_roles = {role for profile in profiles for role in profile["roles"]}
    if "pulse" not in available_roles and "rhythmic_harmony" not in available_roles:
        roles = ["break" if role == "minimal" else role for role in roles]
    block_count = length_bars // 4
    removable = ("intro", "outro", "instrumental", "break", "bridge", "minimal", "a_variation")
    while len(roles) > block_count:
        index = next((roles.index(role) for role in removable if role in roles), len(roles) - 2)
        roles.pop(index)
    blocks = [1 for _ in roles]
    remaining = block_count - len(roles)
    expansion_weights = [2.2 if role in {"verse", "a", "chorus", "drop", "final"} else 1.0 for role in roles]
    while remaining:
        target = random.choices(range(len(roles)), weights=expansion_weights, k=1)[0]
        blocks[target] += 1
        remaining -= 1
    sections: list[dict[str, Any]] = []
    cursor = 0
    for index, (role, count) in enumerate(zip(roles, blocks, strict=True)):
        energy_jitter = (random.random() - 0.5) * 0.18 * temperature
        energy = _clamp(ROLE_ENERGY[role] + energy_jitter, 0.1, 1.0)
        bars = count * 4
        sections.append(
            {
                "id": f"section-{index + 1}",
                "name": role.replace("_", " ").title(),
                "role": role,
                "start_bar": cursor,
                "bars": bars,
                "energy": round(energy, 3),
                "grammar_variant": variant,
                "form_style": form_style,
            }
        )
        cursor += bars
    return sections


def _root_target_semitones(
    style: str,
    role: str,
    local_bar: int,
    style_weights: dict[str, float] | None = None,
) -> float:
    """Return the style target as a 12-TET semitone offset from the tonic."""
    pop = (0, 4, 5, 3)
    patterns = {
        "fractional_pop": pop,
        "fractional_jpop": {
            "a": (0, 4, 1, 4),
            "a_variation": (0, 2, 5, 4),
            "b": (1, 3, 4, 4),
            "chorus": pop,
            "final": (0, 4, 5, 3),
        }.get(role, pop),
        "kawaii_fractional_future_pop": {
            "drop": (0, 5, 3, 4),
            "minimal": (0, 4),
            "final": (0, 5, 3, 4),
        }.get(role, pop),
    }
    if style != "mixed":
        pattern = patterns[style]
        return float(pattern[local_bar % len(pattern)])
    weights = style_weights or {item: 1 / len(BASE_STYLES) for item in BASE_STYLES}
    return sum(
        weights[item] * patterns[item][local_bar % len(patterns[item])]
        for item in BASE_STYLES
    )


def _target_ratio(semitones: float) -> float:
    return 2 ** (semitones / 12)


def _octave_cents_distance(left: Fraction | float, right: Fraction | float) -> float:
    distance = abs(1200 * log2(float(left) / float(right))) % 1200
    return min(distance, 1200 - distance)


def _nearest_scale_degree(scale: tuple[Fraction, ...], target: float) -> int:
    return min(
        range(len(scale)),
        key=lambda degree: (_octave_cents_distance(scale[degree], target), degree),
    )


def _harmony(
    style: str,
    style_weights: dict[str, float],
    scale: tuple[Fraction, ...],
    sections: list[dict[str, Any]],
    temperature: float,
    random: Random,
    maximum_voices: int,
) -> list[dict[str, Any]]:
    bar_context: list[tuple[dict[str, Any], int]] = []
    for section in sections:
        for local_bar in range(int(section["bars"])):
            bar_context.append((section, local_bar))

    beam: list[tuple[list[int], float]] = [([], 0.0)]
    width = max(12, round(12 + temperature * 20))
    for section, local_bar in bar_context:
        candidates: list[tuple[list[int], float]] = []
        for roots, cost in beam:
            previous = roots[-1] if roots else 0
            for degree in range(len(scale)):
                circular = _octave_cents_distance(scale[degree], scale[previous]) / 100
                target_semitones = _root_target_semitones(
                    style, str(section["role"]), local_bar, style_weights
                )
                target_ratio = _target_ratio(target_semitones)
                target_distance = _octave_cents_distance(
                    scale[degree], target_ratio
                ) / 100
                repetition = 0.7 if degree == previous else 0.0
                motion_target = 1.0 + float(section["energy"]) * 1.8
                movement = abs(circular - motion_target) * 0.12
                target_cost = target_distance * (0.52 - temperature * 0.30)
                cadence = 0.0
                if local_bar == int(section["bars"]) - 1:
                    cadence = _octave_cents_distance(scale[degree], 1.0) / 100 * 0.55
                candidates.append((roots + [degree], cost + repetition + movement + target_cost + cadence))
        candidates.sort(key=lambda item: item[1])
        beam = candidates[:width]

    sequences = [item[0] for item in beam]
    costs = [item[1] for item in beam]
    roots = _weighted_choice(random, sequences, costs, temperature)
    slots: list[dict[str, Any]] = []
    bar = 0
    for section in sections:
        for local_bar in range(int(section["bars"])):
            degree = roots[bar]
            role = str(section["role"])
            target_semitones = _root_target_semitones(
                style, role, local_bar, style_weights
            )
            target_ratio = _target_ratio(target_semitones)
            voice_count = 3
            if role in {"chorus", "drop", "final"} and maximum_voices >= 4:
                voice_count = 3 if local_bar < max(2, int(section["bars"]) // 3) else 4
            voice_count = min(maximum_voices, voice_count)
            offsets = (0, 2, 4, 6)[:voice_count]
            tones = [scale[(degree + offset) % len(scale)] for offset in offsets]
            root_motion = 0.0 if not slots else _octave_cents_distance(
                scale[degree], scale[int(slots[-1]["root_degree"])]
            ) / 600
            tension = _clamp(float(section["energy"]) * 0.55 + root_motion * 0.8)
            slots.append(
                {
                    "bar": bar + 1,
                    "section_id": section["id"],
                    "section_role": role,
                    "root_degree": degree,
                    "root_ratio": _ratio_text(scale[degree]),
                    "style_target_semitones_12tet": round(target_semitones, 4),
                    "style_target_ratio": round(target_ratio, 8),
                    "style_target_degree": _nearest_scale_degree(scale, target_ratio),
                    "tones": [_ratio_text(tone) for tone in tones],
                    "voice_count": voice_count,
                    "tension": round(tension, 3),
                }
            )
            bar += 1
    return slots


def _role_score(profile: dict[str, Any], role: str, section_role: str) -> float:
    aliases = {
        "lead": {"lead", "vocal", "countermelody"},
        "vocal": {"vocal", "lead"},
        "harmony": {"harmony", "rhythmic_harmony", "pad", "arpeggio"},
        "pulse": {"pulse", "rhythmic_harmony", "arpeggio"},
        "accent": {"accent", "countermelody"},
    }
    roles = set(profile["roles"])
    compatible = aliases.get(role, {role})
    affinity = 1.0 if role in roles else 0.72 if roles & compatible else 0.0
    section_fit = 1.0 if section_role in profile["section_affinity"] else 0.45
    range_width = (int(profile["midi_range"][1]) - int(profile["midi_range"][0])) / 80
    priority = float(profile.get("priority", 0.7))
    return affinity * 0.55 + section_fit * 0.2 + _clamp(range_width) * 0.1 + priority * 0.15


def _section_roles(section_role: str, profiles: list[dict[str, Any]]) -> list[str]:
    available = {role for profile in profiles for role in profile["roles"]}
    result: list[str] = []
    if section_role in {"minimal", "break", "intro"} and available & {"pulse", "rhythmic_harmony"}:
        result.append("pulse")
    else:
        result.append("harmony")
    if "bass" in available and section_role not in {"intro", "minimal", "outro"}:
        result.append("bass")
    if section_role in {"verse", "a", "a_variation", "b", "pre", "chorus", "drop", "final"}:
        result.append("vocal" if "vocal" in available else "lead")
    if section_role in {"chorus", "drop", "final", "instrumental", "outro"}:
        result.append("accent")
    for drum in ("kick", "snare", "hat", "perc"):
        if drum in available and section_role not in {"intro", "outro"}:
            result.append(drum)
    return result


def _assign_parts(
    sections: list[dict[str, Any]],
    profiles: list[dict[str, Any]],
    temperature: float,
    random: Random,
) -> list[dict[str, Any]]:
    assignments: list[dict[str, Any]] = []
    recent: Counter[str] = Counter()
    for section in sections:
        used: set[str] = set()
        for role in _section_roles(str(section["role"]), profiles):
            candidates = [profile for profile in profiles if _role_score(profile, role, str(section["role"])) >= 0.48]
            if not candidates:
                continue
            scores = [_role_score(profile, role, str(section["role"])) for profile in candidates]
            costs = [1 - score + recent[profile["id"]] * temperature * 0.035 for profile, score in zip(candidates, scores, strict=True)]
            available = [index for index, profile in enumerate(candidates) if profile["id"] not in used]
            if available:
                candidates = [candidates[index] for index in available]
                scores = [scores[index] for index in available]
                costs = [costs[index] for index in available]
            chosen = _weighted_choice(random, candidates, costs, temperature)
            score = _role_score(chosen, role, str(section["role"]))
            assignments.append(
                {
                    "section_id": section["id"],
                    "section_role": section["role"],
                    "part_role": role,
                    "instrument_id": chosen["id"],
                    "assignment_score": round(score, 3),
                }
            )
            used.add(str(chosen["id"]))
            recent[str(chosen["id"])] += 1
    return assignments


def _note_event(
    profile: dict[str, Any],
    ratio: Fraction, start: float, duration: float, velocity: int,
    part_role: str, section_role: str, base_frequency: float,
) -> dict[str, Any]:
    fitted = _fit_ratio(ratio, list(profile["midi_range"]), base_frequency)
    return {
        "instrument_id": profile["id"],
        "start_beat": round(start, 4),
        "duration_beats": round(duration, 4),
        "velocity": max(1, min(127, velocity)),
        "ratio": _ratio_text(fitted),
        "part_role": part_role,
        "section_role": section_role,
    }


def _events(
    scale: tuple[Fraction, ...],
    sections: list[dict[str, Any]],
    harmony: list[dict[str, Any]],
    assignments: list[dict[str, Any]],
    profiles: list[dict[str, Any]],
    random: Random,
    base_frequency: float,
    rhythm_temperature: float,
) -> list[dict[str, Any]]:
    profile_map = {str(profile["id"]): profile for profile in profiles}
    assignment_map = {
        (str(item["section_id"]), str(item["part_role"])): str(item["instrument_id"])
        for item in assignments
    }
    section_map = {str(section["id"]): section for section in sections}
    result: list[dict[str, Any]] = []
    motif = (0, 2, 4, 2, 5, 4, 1, 0)
    for slot in harmony:
        section = section_map[str(slot["section_id"])]
        section_id = str(section["id"])
        section_role = str(section["role"])
        energy = float(section["energy"])
        start = (int(slot["bar"]) - 1) * 4.0
        root = Fraction(str(slot["root_ratio"]))
        tones = [Fraction(value) for value in slot["tones"]]

        harmony_id = assignment_map.get((section_id, "harmony"))
        if harmony_id:
            profile = profile_map[harmony_id]
            harmony_onsets = (0.0, 1.5, 2.75) if section_role in {"drop", "final"} else (0.5, 2.5) if profile["articulation"] in {"short", "keys"} else (0.0,)
            limit = min(len(tones), int(profile["max_polyphony"]))
            if harmony_id == "PI18" and int(slot["bar"]) - int(section["start_bar"]) <= 2:
                limit = min(3, limit)
            for onset in harmony_onsets:
                for voice, tone in enumerate(tones[:limit]):
                    result.append(_note_event(profile, tone, start + onset + voice * 0.014, 0.58 if len(harmony_onsets) > 1 else 3.4, round(62 + energy * 34 - voice * 3), "harmony", section_role, base_frequency))

        bass_id = assignment_map.get((section_id, "bass"))
        if bass_id:
            profile = profile_map[bass_id]
            for onset in ((0.0, 2.0) if energy > 0.55 else (0.0,)):
                result.append(_note_event(profile, root, start + onset, 1.65 if energy > 0.55 else 3.4, round(64 + energy * 34), "bass", section_role, base_frequency))

        lead_id = assignment_map.get((section_id, "vocal")) or assignment_map.get((section_id, "lead"))
        if lead_id and random.random() < 0.62 + energy * 0.28:
            profile = profile_map[lead_id]
            density = 3 + round(energy * 3 + rhythm_temperature * 2)
            lead_onsets = (0.0, 0.75, 1.5, 2.5, 3.25, 3.65)[:density]
            phrase_offset = random.randrange(len(motif))
            for index, onset in enumerate(lead_onsets):
                degree = (int(slot["root_degree"]) + motif[(phrase_offset + index) % len(motif)]) % len(scale)
                next_onset = lead_onsets[index + 1] if index + 1 < len(lead_onsets) else 4.0
                result.append(_note_event(profile, scale[degree], start + onset, max(0.18, (next_onset - onset) * 0.66), round(67 + energy * 32 + random.randrange(-4, 5)), "vocal" if "vocal" in profile["roles"] else "lead", section_role, base_frequency))

        pulse_id = assignment_map.get((section_id, "pulse"))
        if pulse_id:
            profile = profile_map[pulse_id]
            pulses = max(2, round(3 + rhythm_temperature * 5 + energy * 2))
            for step in range(pulses):
                onset = step * 4 / pulses
                degree = (int(slot["root_degree"]) + (step * 2)) % len(scale)
                result.append(_note_event(profile, scale[degree], start + onset, min(0.38, 3.1 / pulses), round(56 + energy * 30), "pulse", section_role, base_frequency))

        accent_id = assignment_map.get((section_id, "accent"))
        if accent_id and (int(slot["bar"]) % 2 == 0 or section_role == "final"):
            profile = profile_map[accent_id]
            degree = (int(slot["root_degree"]) + 4) % len(scale)
            result.append(_note_event(profile, scale[degree], start + 3.5, 0.3, round(72 + energy * 28), "accent", section_role, base_frequency))

        drum_patterns = {
            "kick": (0.0, 2.0) if energy < 0.72 else (0.0, 1.5, 2.0, 3.25),
            "snare": (1.0, 3.0),
            "hat": tuple(step * (1.0 if energy < 0.55 else 0.5) for step in range(4 if energy < 0.55 else 8)),
            "perc": (2.75,) if energy < 0.7 else (0.75, 2.75, 3.5),
        }
        for drum_role, drum_onsets in drum_patterns.items():
            instrument_id = assignment_map.get((section_id, drum_role))
            if not instrument_id:
                continue
            profile = profile_map[instrument_id]
            for onset in drum_onsets:
                result.append(
                    {
                        "instrument_id": instrument_id,
                        "start_beat": round(start + onset, 4),
                        "duration_beats": 0.12,
                        "velocity": round(62 + energy * 38),
                        "note": profile["drum_note"],
                        "part_role": drum_role,
                        "section_role": section_role,
                    }
                )
    result.sort(key=lambda event: (float(event["start_beat"]), str(event["instrument_id"])))
    return result


def _features(
    scale: tuple[Fraction, ...], sections: list[dict[str, Any]], harmony: list[dict[str, Any]],
    assignments: list[dict[str, Any]], events: list[dict[str, Any]], profiles: list[dict[str, Any]],
) -> dict[str, float]:
    roots = [int(slot["root_degree"]) for slot in harmony]
    root_motion = [
        _octave_cents_distance(scale[a], scale[b]) / 600
        for a, b in zip(roots, roots[1:])
    ]
    energies = [float(section["energy"]) for section in sections]
    tensions = [float(slot["tension"]) for slot in harmony]
    melodic = [event for event in events if event["part_role"] in {"lead", "vocal"}]
    drums = [event for event in events if "note" in event]
    pitched = [event for event in events if "ratio" in event]
    used = {str(event["instrument_id"]) for event in events}
    assignment_sets: list[set[str]] = []
    for section in sections:
        assignment_sets.append({str(item["instrument_id"]) for item in assignments if item["section_id"] == section["id"]})
    turnover = [len(a ^ b) / max(1, len(a | b)) for a, b in zip(assignment_sets, assignment_sets[1:])]
    total_bars = max(1, len(harmony))
    melodic_bars = {int(float(event["start_beat"]) // 4) for event in melodic}
    syncopated = [event for event in events if abs(float(event["start_beat"]) % 1) > 0.01]
    pitch_classes = {_octave(Fraction(str(event["ratio"]))) for event in pitched}
    return {
        "form_variety": round(_clamp(len({section["role"] for section in sections}) / 8), 4),
        "section_contrast": round(_clamp(pstdev(energies) * 3 if len(energies) > 1 else 0), 4),
        "root_variety": round(len(set(roots)) / len(scale), 4),
        "root_motion": round(_clamp((fmean(root_motion) if root_motion else 0) / max(1, len(scale) / 2)), 4),
        "tension_smoothness": round(1 - _clamp(fmean(abs(a - b) for a, b in zip(tensions, tensions[1:])) * 2 if len(tensions) > 1 else 0), 4),
        "harmony_repetition": round(sum(a == b for a, b in zip(roots, roots[1:])) / max(1, len(roots) - 1), 4),
        "melody_density": round(_clamp(len(melodic) / total_bars / 6), 4),
        "rest_space": round(1 - len(melodic_bars) / total_bars, 4),
        "syncopation": round(len(syncopated) / max(1, len(events)), 4),
        "drum_density": round(_clamp(len(drums) / total_bars / 16), 4),
        "instrument_coverage": round(len(used) / len(profiles), 4),
        "part_turnover": round(fmean(turnover) if turnover else 0, 4),
        "ratio_color": round(len(pitch_classes) / len(scale), 4),
        "assignment_fit": round(fmean(float(item["assignment_score"]) for item in assignments) if assignments else 0, 4),
    }


def _scores(features: dict[str, float], custom_weights: dict[str, float]) -> dict[str, float]:
    scores = {
        "structural_coherence": _clamp(0.45 + features["tension_smoothness"] * 0.35 + (1 - abs(features["harmony_repetition"] - 0.28)) * 0.2),
        "section_contrast": features["section_contrast"],
        "harmonic_interest": _clamp(features["root_variety"] * 0.55 + features["root_motion"] * 0.45),
        "tension_smoothness": features["tension_smoothness"],
        "melodic_identity": _clamp(features["melody_density"] * 0.65 + features["rest_space"] * 0.35),
        "rhythmic_identity": _clamp(features["syncopation"] * 0.55 + features["drum_density"] * 0.45),
        "repetition_balance": 1 - abs(features["harmony_repetition"] - 0.28),
        "ratio_color_usage": features["ratio_color"],
        "instrumentation_fit": _clamp(features["assignment_fit"] * 0.65 + features["instrument_coverage"] * 0.25 + features["part_turnover"] * 0.1),
    }
    weights = DEFAULT_EVALUATION_WEIGHTS | {key: _clamp(float(value), 0.1, 3.0) for key, value in custom_weights.items() if key in DEFAULT_EVALUATION_WEIGHTS}
    overall = sum(scores[key] * weights[key] for key in scores) / sum(weights.values())
    return {key: round(value, 4) for key, value in scores.items()} | {"overall": round(overall, 4)}


def _distance(left: dict[str, Any], right: dict[str, Any]) -> float:
    return sqrt(sum((float(left["features"][key]) - float(right["features"][key])) ** 2 for key in FEATURE_KEYS) / len(FEATURE_KEYS))


def _cluster(candidates: list[dict[str, Any]], count: int) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    count = min(count, len(candidates))
    medoids = [0]
    while len(medoids) < count:
        medoids.append(max((index for index in range(len(candidates)) if index not in medoids), key=lambda index: min(_distance(candidates[index], candidates[medoid]) for medoid in medoids)))
    groups: list[list[int]] = []
    for _ in range(16):
        groups = [[] for _ in medoids]
        for index, candidate in enumerate(candidates):
            target = min(range(len(medoids)), key=lambda group: _distance(candidate, candidates[medoids[group]]))
            groups[target].append(index)
        updated = [min(group, key=lambda member: sum(_distance(candidates[member], candidates[other]) for other in group)) for group in groups]
        if updated == medoids:
            break
        medoids = updated

    clusters: list[dict[str, Any]] = []
    representatives: list[dict[str, Any]] = []
    for cluster_index, members in enumerate(groups):
        medoid = medoids[cluster_index]
        maximum = max((_distance(candidates[member], candidates[medoid]) for member in members), default=1.0) or 1.0
        representative = max(members, key=lambda member: float(candidates[member]["scores"]["overall"]) * 0.65 + (1 - _distance(candidates[member], candidates[medoid]) / maximum) * 0.35)
        for member in members:
            candidates[member]["cluster_id"] = f"cluster-{cluster_index + 1}"
        feature = max(FEATURE_KEYS, key=lambda key: fmean(float(candidates[member]["features"][key]) for member in members))
        clusters.append(
            {
                "id": f"cluster-{cluster_index + 1}",
                "label": feature.replace("_", " ").title(),
                "size": len(members),
                "medoid_id": candidates[medoid]["id"],
                "representative_id": candidates[representative]["id"],
                "member_ids": [candidates[member]["id"] for member in members],
            }
        )
        representatives.append(candidates[representative])
    return clusters, representatives


def _candidate(config: dict[str, Any], index: int, profiles: list[dict[str, Any]], warnings: list[str]) -> dict[str, Any]:
    master = int(config["seed"])
    locks = set(config.get("locked_components") or [])
    component_seeds = {
        name: _seed(master, 0 if name in locks else index, name)
        for name in ("form", "harmony", "melody", "rhythm", "arrangement", "performance")
    }
    scale = _parse_scale(list(config["scale_ratios"]))
    style_weights = _style_weights(config)
    form_random = Random(component_seeds["form"])
    harmony_random = Random(component_seeds["harmony"])
    arrangement_random = Random(component_seeds["arrangement"])
    event_random = Random(component_seeds["melody"] ^ component_seeds["rhythm"])
    sections = _form(str(config["style"]), style_weights, int(config["length_bars"]), float(config["form_temperature"]), form_random, profiles)
    harmony_profiles = [profile for profile in profiles if set(profile["roles"]) & {"harmony", "rhythmic_harmony", "pad", "arpeggio"}]
    maximum_voices = max((int(profile["max_polyphony"]) for profile in harmony_profiles), default=2)
    harmony = _harmony(str(config["style"]), style_weights, scale, sections, float(config["harmony_temperature"]), harmony_random, maximum_voices)
    assignments = _assign_parts(sections, profiles, float(config["part_temperature"]), arrangement_random)
    events = _events(scale, sections, harmony, assignments, profiles, event_random, float(config["base_frequency"]), float(config["rhythm_temperature"]))
    features = _features(scale, sections, harmony, assignments, events, profiles)
    scores = _scores(features, dict(config.get("evaluation_weights") or {}))
    candidate_seed = _seed(master, index, "candidate")
    return {
        "id": f"song-{candidate_seed}",
        "genome": {
            "version": 1,
            "style": config["style"],
            "style_mix": style_weights,
            "master_seed": master,
            "candidate_index": index,
            "component_seeds": component_seeds,
            "temperatures": {
                "form": config["form_temperature"],
                "harmony": config["harmony_temperature"],
                "parts": config["part_temperature"],
                "rhythm": config["rhythm_temperature"],
            },
            "instrument_palette": [profile["id"] for profile in profiles],
        },
        "metadata": {
            "style": config["style"],
            "style_name": STYLE_NAMES[str(config["style"])],
            "style_mix": style_weights,
            "form_style": sections[0]["form_style"],
            "tempo_bpm": config["tempo_bpm"],
            "length_bars": config["length_bars"],
            "base_frequency": config["base_frequency"],
            "warnings": warnings,
        },
        "scale_ratios": [_ratio_text(value) for value in scale],
        "sections": sections,
        "harmony": harmony,
        "assignments": assignments,
        "events": events,
        "features": features,
        "scores": scores,
    }


def explore_compositions(config: dict[str, Any]) -> dict[str, Any]:
    """Generate, evaluate, cluster, and select representative song plans."""
    profiles, warnings = _instrument_palette(config)
    candidates = [_candidate(config, index, profiles, warnings) for index in range(int(config["candidate_count"]))]
    clusters, representatives = _cluster(candidates, int(config["cluster_count"]))
    summaries = [
        {key: value for key, value in candidate.items() if key not in {"events", "harmony", "assignments"}}
        | {"event_count": len(candidate["events"]), "section_roles": [section["role"] for section in candidate["sections"]]}
        for candidate in candidates
    ]
    return {
        "schema_version": "1.0",
        "style": config["style"],
        "style_mix": _style_weights(config),
        "seed": config["seed"],
        "candidate_count": len(candidates),
        "cluster_count": len(clusters),
        "instrument_profiles": profiles,
        "warnings": warnings,
        "clusters": clusters,
        "candidates": summaries,
        "representatives": representatives,
        "evaluation_weights": DEFAULT_EVALUATION_WEIGHTS | dict(config.get("evaluation_weights") or {}),
    }


def explorer_profiles() -> dict[str, Any]:
    return {
        "instruments": public_instrument_profiles(),
        "style_defaults": {key: list(value) for key, value in STYLE_DEFAULT_PALETTES.items()},
        "styles": STYLE_NAMES,
        "evaluation_weights": DEFAULT_EVALUATION_WEIGHTS,
    }
