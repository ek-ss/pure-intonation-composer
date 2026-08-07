from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from functools import lru_cache
from hashlib import sha256
from io import BytesIO
from itertools import combinations, combinations_with_replacement
from math import exp, log2, pi, sin
from random import Random
import re
from statistics import fmean
from struct import pack
from typing import Any, Literal
from wave import open as wave_open

from pydantic import BaseModel, Field, field_validator, model_validator

from app.exporters.midi import (
    MidiArrangementTrack,
    MidiDrumHit,
    MidiNote,
    arrangement_midi_bytes,
)


TRITAVE_CENTS = 1200 * log2(3)
ODD_HARMONICS = (1, 3, 5, 7, 9, 11, 13, 15)


class BPScaleRequest(BaseModel):
    preset: Literal["core", "bounded-lattice", "generator-chain", "harmonic-odd", "13-edt", "manual"] = "bounded-lattice"
    prime_limit: Literal[5, 7, 11, 13] = 7
    b_min: int = Field(default=-2, ge=-8, le=8)
    b_max: int = Field(default=2, ge=-8, le=8)
    c_min: int = Field(default=-2, ge=-8, le=8)
    c_max: int = Field(default=2, ge=-8, le=8)
    generator_min: int = Field(default=-6, ge=-24, le=0)
    generator_max: int = Field(default=6, ge=0, le=24)
    max_tenney_height: float = Field(default=12, ge=1, le=40)
    max_pitches: int = Field(default=13, ge=3, le=49)
    root_frequency_hz: float = Field(default=220, ge=20, le=2000)
    ratios: list[str] = Field(default_factory=list, max_length=49)

    @model_validator(mode="after")
    def bounds_are_ordered(self) -> BPScaleRequest:
        if self.b_min > self.b_max or self.c_min > self.c_max:
            raise ValueError("exponent bounds must be ordered")
        if self.generator_min > self.generator_max:
            raise ValueError("generator bounds must be ordered")
        if self.preset == "manual" and not self.ratios:
            raise ValueError("manual scale requires at least one ratio")
        return self


class BPChordWeights(BaseModel):
    harmonicity: float = Field(default=0.25, ge=0, le=1)
    odd_overlap: float = Field(default=0.25, ge=0, le=1)
    root_clarity: float = Field(default=0.15, ge=0, le=1)
    compactness: float = Field(default=0.10, ge=0, le=1)
    roughness: float = Field(default=0.15, ge=0, le=1)
    complexity: float = Field(default=0.10, ge=0, le=1)


class BPChordSearchRequest(BaseModel):
    pitches: list[dict[str, Any]] = Field(min_length=2, max_length=49)
    voice_count: int = Field(default=3, ge=2, le=6)
    required_pitch_ids: list[str] = Field(default_factory=list, max_length=6)
    excluded_pitch_ids: list[str] = Field(default_factory=list, max_length=49)
    max_results: int = Field(default=24, ge=1, le=200)
    max_tenney_height: float = Field(default=18, ge=1, le=80)
    max_prime_distance: int = Field(default=16, ge=1, le=64)
    max_tritave_width: float = Field(default=0.75, ge=0.05, le=1)
    min_odd_harmonic_overlap: float = Field(default=0, ge=0, le=1)
    root_fixed: bool = False
    allow_duplicates: bool = False
    weights: BPChordWeights = Field(default_factory=BPChordWeights)


class BPProgressionRequest(BaseModel):
    chords: list[dict[str, Any]] = Field(min_length=2, max_length=200)
    length: int = Field(default=8, ge=4, le=16)
    start_chord_id: str | None = None
    end_chord_id: str | None = None
    center_chord_id: str | None = None
    target_tension_curve: list[float] = Field(default_factory=list, max_length=16)
    method: Literal["beam-search", "shortest-path", "cycle", "contrast-resolution", "random-walk"] = "beam-search"
    beam_width: int = Field(default=32, ge=4, le=128)
    seed: int = 357

    @field_validator("target_tension_curve")
    @classmethod
    def tension_is_normalized(cls, values: list[float]) -> list[float]:
        if any(value < 0 or value > 1 for value in values):
            raise ValueError("target tension values must be between zero and one")
        return values


class BPComposeRequest(BaseModel):
    scale: list[dict[str, Any]] = Field(min_length=3, max_length=49)
    chords: list[dict[str, Any]] = Field(default_factory=list, max_length=200)
    progression: list[dict[str, Any]] = Field(default_factory=list, max_length=16)
    duration_bars: int = Field(default=16, ge=4, le=64)
    tempo_bpm: float = Field(default=108, ge=40, le=240)
    beats_per_bar: Literal[3, 4, 5, 7] = 4
    form: Literal["loop", "AB", "ABA", "verse-chorus", "tension-resolution"] = "tension-resolution"
    chord_density: float = Field(default=0.72, ge=0, le=1)
    melodic_density: float = Field(default=0.55, ge=0, le=1)
    rhythmic_density: float = Field(default=0.5, ge=0, le=1)
    include_drone: bool = True
    timbre: Literal["odd-harmonic", "sine", "full-harmonic", "soft-square", "hollow-pluck"] = "odd-harmonic"
    root_frequency_hz: float = Field(default=110, ge=20, le=1000)
    seed: int = 357


class BPExportRequest(BaseModel):
    events: list[dict[str, Any]] = Field(min_length=1, max_length=20000)
    tempo_bpm: float = Field(default=108, ge=30, le=300)
    beats_per_bar: Literal[3, 4, 5, 7] = 4
    root_frequency_hz: float = Field(default=110, ge=20, le=2000)
    pitch_bend_range_semitones: int = Field(default=2, ge=1, le=48)
    sections: list[dict[str, Any]] = Field(default_factory=list, max_length=64)


class BPRenderRequest(BPExportRequest):
    timbre: Literal["odd-harmonic", "sine", "full-harmonic", "soft-square", "hollow-pluck"] = "odd-harmonic"
    sample_rate: int = Field(default=22050, ge=8000, le=48000)


def _ratio_text(value: Fraction) -> str:
    return f"{value.numerator}/{value.denominator}"


def parse_ratio(value: str) -> Fraction:
    text = value.strip().replace(" ", "")
    exponent_expression = re.fullmatch(r"(?:\d+\^-?\d+)(?:\*(?:\d+\^-?\d+))*", text)
    exponent_object = re.fullmatch(r"\{(?:[abc]:-?\d+,?){1,3}\}", text)
    try:
        if exponent_expression:
            ratio = Fraction(1)
            for factor in text.split("*"):
                base_text, exponent_text = factor.split("^", 1)
                base = int(base_text)
                exponent = int(exponent_text)
                ratio *= Fraction(base**exponent if exponent >= 0 else 1, 1 if exponent >= 0 else base ** (-exponent))
        elif exponent_object:
            exponents = {key: int(exponent) for key, exponent in re.findall(r"([abc]):(-?\d+)", text)}
            ratio = Fraction(1)
            for key, base in (("a", 3), ("b", 5), ("c", 7)):
                exponent = exponents.get(key, 0)
                ratio *= Fraction(base**exponent if exponent >= 0 else 1, 1 if exponent >= 0 else base ** (-exponent))
        else:
            ratio = Fraction(text)
    except (ValueError, ZeroDivisionError) as error:
        raise ValueError(f"invalid ratio: {value}") from error
    if ratio <= 0:
        raise ValueError("ratios must be positive")
    return ratio


def normalize_tritave(value: Fraction) -> tuple[Fraction, int]:
    register = 0
    while value < 1:
        value *= 3
        register -= 1
    while value >= 3:
        value /= 3
        register += 1
    return value, register


def _factor_integer(value: int) -> dict[int, int]:
    result: dict[int, int] = {}
    divisor = 2
    while divisor * divisor <= value:
        while value % divisor == 0:
            result[divisor] = result.get(divisor, 0) + 1
            value //= divisor
        divisor += 1
    if value > 1:
        result[value] = result.get(value, 0) + 1
    return result


def prime_exponents(value: Fraction) -> dict[str, int]:
    numerator = _factor_integer(value.numerator)
    denominator = _factor_integer(value.denominator)
    return {
        str(prime): numerator.get(prime, 0) - denominator.get(prime, 0)
        for prime in sorted(set(numerator) | set(denominator) | {3, 5, 7})
    }


@lru_cache(maxsize=4096)
def pitch_data(value: Fraction, root_frequency: float = 220) -> dict[str, Any]:
    normalized, register = normalize_tritave(value)
    exponents = prime_exponents(normalized)
    position = log2(float(normalized)) / log2(3)
    edt_step = round(position * 13) % 13
    edt_cents = edt_step / 13 * TRITAVE_CENTS
    cents = 1200 * log2(float(normalized))
    return {
        "id": f"bp-{normalized.numerator}-{normalized.denominator}",
        "ratio": _ratio_text(normalized),
        "numerator": normalized.numerator,
        "denominator": normalized.denominator,
        "prime_exponents": exponents,
        "b": exponents.get("5", 0),
        "c": exponents.get("7", 0),
        "tritave_register": register,
        "cents_from_root": round(cents, 5),
        "tritave_position": round(position, 8),
        "frequency_hz": round(root_frequency * float(normalized), 5),
        "tenney_height": round(log2(normalized.numerator * normalized.denominator), 5),
        "edt13_step": edt_step,
        "edt13_error_cents": round(cents - edt_cents, 5),
    }


def _bounded_lattice(request: BPScaleRequest) -> list[Fraction]:
    values: list[Fraction] = []
    for b in range(request.b_min, request.b_max + 1):
        c_values = range(request.c_min, request.c_max + 1) if request.prime_limit >= 7 else (0,)
        for c in c_values:
            raw = Fraction(5**b if b >= 0 else 1, 1 if b >= 0 else 5 ** (-b)) * Fraction(
                7**c if c >= 0 else 1, 1 if c >= 0 else 7 ** (-c)
            )
            value, _register = normalize_tritave(raw)
            if log2(value.numerator * value.denominator) <= request.max_tenney_height:
                values.append(value)
    return values


def generate_scale(request: BPScaleRequest | dict[str, Any]) -> dict[str, Any]:
    if not isinstance(request, BPScaleRequest):
        request = BPScaleRequest.model_validate(request)
    if request.preset == "core":
        values = [Fraction(1), Fraction(5, 3), Fraction(7, 3)]
    elif request.preset == "bounded-lattice":
        values = _bounded_lattice(request)
    elif request.preset == "generator-chain":
        values = [normalize_tritave(Fraction(5**n if n >= 0 else 1, 5 ** (-n)))[0] for n in range(request.generator_min, request.generator_max + 1)]
    elif request.preset == "harmonic-odd":
        values = [normalize_tritave(Fraction(value))[0] for value in (3, 5, 7, 9, 11, 13) if max(_factor_integer(value), default=1) <= request.prime_limit]
    elif request.preset == "13-edt":
        values = [Fraction(3 ** (step / 13)).limit_denominator(10_000_000) for step in range(13)]
    else:
        values = [normalize_tritave(parse_ratio(value))[0] for value in request.ratios]
    values = sorted(set(values), key=float)
    if Fraction(1) not in values:
        values.insert(0, Fraction(1))
    values = values[: request.max_pitches]
    pitches = [pitch_data(value, request.root_frequency_hz) for value in values]
    digest = sha256("|".join(item["ratio"] for item in pitches).encode("ascii")).hexdigest()[:12]
    return {
        "schema_version": "1.0",
        "id": f"bp-scale-{digest}",
        "name": {
            "core": "Pure 3:5:7 core",
            "bounded-lattice": "Extended 7-limit BP",
            "generator-chain": "3-5 generator chain",
            "harmonic-odd": "Harmonic odd set",
            "13-edt": "13-EDT comparison",
            "manual": "Custom BP scale",
        }[request.preset],
        "equave": 3,
        "temperament": "13-EDT" if request.preset == "13-edt" else "pure-ratio",
        "root_frequency_hz": request.root_frequency_hz,
        "generation_rule": request.preset,
        "pitches": pitches,
    }


def _pair_metrics(left: Fraction, right: Fraction) -> tuple[float, float, float]:
    interval, _ = normalize_tritave(right / left)
    height = log2(interval.numerator * interval.denominator)
    odd = 1.0 if interval.numerator % 2 and interval.denominator % 2 else 0.42
    odd_overlap = odd / (1 + height / 12)
    distance = abs(1200 * log2(float(interval)))
    distance = min(distance, TRITAVE_CENTS - distance)
    roughness = exp(-((distance - 180) / 150) ** 2)
    return height, odd_overlap, roughness


def _chord_metrics(pitches: tuple[dict[str, Any], ...], weights: BPChordWeights) -> dict[str, float]:
    ratios = [parse_ratio(str(pitch["ratio"])) for pitch in pitches]
    pairs = [_pair_metrics(ratios[a], ratios[b]) for a, b in combinations(range(len(ratios)), 2)]
    heights = [item[0] for item in pairs] or [0.0]
    overlaps = [item[1] for item in pairs] or [1.0]
    roughness_values = [item[2] for item in pairs] or [0.0]
    coordinates = [(int(pitch.get("b", 0)), int(pitch.get("c", 0))) for pitch in pitches]
    center_b = fmean(item[0] for item in coordinates)
    center_c = fmean(item[1] for item in coordinates)
    lattice_distance = fmean(abs(b - center_b) + abs(c - center_c) for b, c in coordinates)
    tenney = fmean(heights)
    complexity = min(1.0, tenney / 18)
    harmonicity = 1 / (1 + tenney / 10)
    overlap = fmean(overlaps)
    roughness = min(1.0, fmean(roughness_values))
    compactness = 1 / (1 + lattice_distance / 3)
    bass = min(ratios, key=float)
    bass_fit = fmean(1 / (1 + log2((ratio / bass).numerator * (ratio / bass).denominator) / 10) for ratio in ratios)
    root_clarity = min(1.0, bass_fit * (0.75 + 0.25 * overlap))
    stability = min(1.0, harmonicity * 0.28 + overlap * 0.28 + root_clarity * 0.24 + compactness * 0.20)
    positive = (
        weights.harmonicity * harmonicity
        + weights.odd_overlap * overlap
        + weights.root_clarity * root_clarity
        + weights.compactness * compactness
    )
    penalties = weights.roughness * roughness + weights.complexity * complexity
    total_weight = sum(weights.model_dump().values()) or 1
    total = max(0.0, min(1.0, (positive + weights.roughness + weights.complexity - penalties) / total_weight))
    return {
        "harmonicity": round(harmonicity, 5),
        "odd_harmonic_overlap": round(overlap, 5),
        "ratio_complexity": round(complexity, 5),
        "tenney_height": round(tenney, 5),
        "prime_distance": round(lattice_distance, 5),
        "tritave_compactness": round(compactness, 5),
        "roughness_estimate": round(roughness, 5),
        "spectral_centroid_spread": round(min(1.0, fmean(abs(log2(float(ratio / bass))) for ratio in ratios)), 5),
        "root_clarity": round(root_clarity, 5),
        "stability": round(stability, 5),
        "ambiguity": round(1 - root_clarity, 5),
        "total_score": round(total, 5),
    }


def chord_search(request: BPChordSearchRequest | dict[str, Any]) -> dict[str, Any]:
    if not isinstance(request, BPChordSearchRequest):
        request = BPChordSearchRequest.model_validate(request)
    excluded = set(request.excluded_pitch_ids)
    required = set(request.required_pitch_ids)
    pitches = [pitch for pitch in request.pitches if str(pitch["id"]) not in excluded]
    if request.voice_count > len(pitches) and not request.allow_duplicates:
        raise ValueError("voice count exceeds available pitches")
    candidates: list[dict[str, Any]] = []
    iterator = combinations_with_replacement(pitches, request.voice_count) if request.allow_duplicates else combinations(pitches, request.voice_count)
    fixed_root = str(pitches[0]["id"]) if pitches else ""
    for index, selected in enumerate(iterator):
        if index >= 100_000:
            break
        ids = {str(pitch["id"]) for pitch in selected}
        if not required <= ids:
            continue
        if request.root_fixed and fixed_root not in ids:
            continue
        metrics = _chord_metrics(selected, request.weights)
        if metrics["tenney_height"] > request.max_tenney_height or metrics["prime_distance"] > request.max_prime_distance or metrics["odd_harmonic_overlap"] < request.min_odd_harmonic_overlap:
            continue
        positions = sorted(float(pitch["tritave_position"]) for pitch in selected)
        gaps = [positions[index + 1] - positions[index] for index in range(len(positions) - 1)] + [1 + positions[0] - positions[-1]]
        width = 1 - max(gaps)
        if width > request.max_tritave_width:
            continue
        ratios = [str(pitch["ratio"]) for pitch in selected]
        chord_id = "bp-chord-" + sha256("|".join(ratios).encode("ascii")).hexdigest()[:10]
        candidates.append(
            {
                "id": chord_id,
                "pitch_ids": [str(pitch["id"]) for pitch in selected],
                "ratios": ratios,
                "normalized_integer_form": _integer_form(ratios),
                "root_pitch_id": str(selected[0]["id"]),
                "inversion_index": 0,
                "register_assignments": [0] * len(selected),
                "metrics": metrics,
                "tags": _chord_tags(metrics),
            }
        )
    candidates.sort(key=lambda item: float(item["metrics"]["total_score"]), reverse=True)
    return {
        "schema_version": "1.0",
        "candidate_count": len(candidates),
        "chords": candidates[: request.max_results],
        "pareto_front": _pareto(candidates)[: request.max_results],
    }


def _integer_form(ratios: list[str]) -> list[int]:
    fractions = [parse_ratio(value) for value in ratios]
    denominator = 1
    for value in fractions:
        denominator = denominator * value.denominator // _gcd(denominator, value.denominator)
    integers: list[int] = [
        int(value.numerator * (denominator // value.denominator)) for value in fractions
    ]
    divisor = integers[0]
    for integer in integers[1:]:
        divisor = _gcd(divisor, integer)
    return [integer // divisor for integer in integers]


def _gcd(left: int, right: int) -> int:
    while right:
        left, right = right, left % right
    return abs(left)


def _chord_tags(metrics: dict[str, float]) -> list[str]:
    result = []
    if metrics["stability"] > 0.68:
        result.append("center")
    if metrics["roughness_estimate"] > 0.55:
        result.append("tension")
    if metrics["odd_harmonic_overlap"] > 0.68:
        result.append("spectral-fusion")
    if metrics["ambiguity"] > 0.45:
        result.append("ambiguous")
    return result or ["color"]


def _pareto(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for candidate in candidates:
        metrics = candidate["metrics"]
        dominated = any(
            other["metrics"]["harmonicity"] >= metrics["harmonicity"]
            and other["metrics"]["odd_harmonic_overlap"] >= metrics["odd_harmonic_overlap"]
            and other["metrics"]["ratio_complexity"] <= metrics["ratio_complexity"]
            and other is not candidate
            for other in candidates
        )
        if not dominated:
            result.append(candidate)
    return result


def _tritave_voice_distance(left: dict[str, Any], right: dict[str, Any]) -> float:
    a = sorted(log2(float(parse_ratio(value))) / log2(3) for value in left["ratios"])
    b = sorted(log2(float(parse_ratio(value))) / log2(3) for value in right["ratios"])
    count = min(len(a), len(b))
    distance = sum(min(abs(a[index] - b[index]), 1 - abs(a[index] - b[index])) for index in range(count))
    return distance / max(1, count) + abs(len(a) - len(b)) * 0.2


def progression_search(request: BPProgressionRequest | dict[str, Any]) -> dict[str, Any]:
    if not isinstance(request, BPProgressionRequest):
        request = BPProgressionRequest.model_validate(request)
    chord_map = {str(chord["id"]): chord for chord in request.chords}
    start = chord_map.get(request.start_chord_id or "") or max(request.chords, key=lambda chord: float(chord["metrics"]["stability"]))
    center_id = request.center_chord_id or str(start["id"])
    end_id = request.end_chord_id or (center_id if request.method in {"cycle", "contrast-resolution"} else None)
    curve = request.target_tension_curve or _default_tension_curve(request.length, request.method)
    if len(curve) != request.length:
        curve = [curve[round(index * (len(curve) - 1) / (request.length - 1))] for index in range(request.length)]
    random = Random(request.seed)
    beam: list[tuple[list[dict[str, Any]], float]] = [([start], abs((1 - float(start["metrics"]["stability"])) - curve[0]))]
    for step in range(1, request.length):
        expanded: list[tuple[list[dict[str, Any]], float]] = []
        for path, cost in beam:
            previous = path[-1]
            pool = list(request.chords)
            if request.method == "random-walk":
                random.shuffle(pool)
                pool = pool[: min(24, len(pool))]
            for chord in pool:
                tension = 1 - float(chord["metrics"]["stability"])
                voice = _tritave_voice_distance(previous, chord)
                repeat = 0.34 if chord["id"] == previous["id"] else 0.0
                return_bias = -0.22 if step == request.length - 1 and chord["id"] == center_id else 0.0
                end_penalty = 2.0 if step == request.length - 1 and end_id and chord["id"] != end_id else 0.0
                expanded.append((path + [chord], cost + abs(tension - curve[step]) * 1.25 + voice * 0.55 + repeat + return_bias + end_penalty))
        expanded.sort(key=lambda item: item[1])
        beam = expanded[: request.beam_width]
    path, cost = beam[0]
    entries = []
    for index, chord in enumerate(path):
        previous = path[index - 1] if index else chord
        voice = _tritave_voice_distance(previous, chord) if index else 0.0
        common = len(set(previous["pitch_ids"]) & set(chord["pitch_ids"])) if index else len(chord["pitch_ids"])
        resolution = (float(chord["metrics"]["stability"]) - float(previous["metrics"]["stability"])) if index else 0.0
        entries.append(
            {
                "step": index,
                "chord_id": chord["id"],
                "ratios": chord["ratios"],
                "duration_beats": 4,
                "functional_role": _function_label(chord, center_id),
                "target_tension": round(curve[index], 4),
                "actual_tension": round(1 - float(chord["metrics"]["stability"]), 4),
                "voice_leading": round(voice, 5),
                "common_tones": common,
                "resolution_strength": round(resolution, 5),
            }
        )
    return {
        "schema_version": "1.0",
        "method": request.method,
        "center_chord_id": center_id,
        "target_tension_curve": [round(value, 4) for value in curve],
        "total_cost": round(cost, 5),
        "progression": entries,
        "loop_closure": round(_tritave_voice_distance(path[-1], path[0]), 5),
    }


def _default_tension_curve(length: int, method: str) -> list[float]:
    if method == "cycle":
        return [0.15 + 0.65 * sin(pi * index / (length - 1)) for index in range(length)]
    if method == "contrast-resolution":
        return [0.15 + 0.82 * sin(pi * index / (length - 1)) ** 1.5 for index in range(length)]
    return [0.18 + 0.62 * index / max(1, length - 1) if index < length * 0.65 else 0.72 * (length - 1 - index) / max(1, length * 0.35) for index in range(length)]


def _function_label(chord: dict[str, Any], center_id: str) -> str:
    if chord["id"] == center_id:
        return "Center"
    tension = 1 - float(chord["metrics"]["stability"])
    if tension > 0.72:
        return "Tension"
    if tension > 0.5:
        return "Expansion"
    if tension < 0.28:
        return "Resolution"
    return "Departure"


def compose(request: BPComposeRequest | dict[str, Any]) -> dict[str, Any]:
    if not isinstance(request, BPComposeRequest):
        request = BPComposeRequest.model_validate(request)
    random = Random(request.seed)
    progression = list(request.progression)
    chords = list(request.chords)
    if not progression:
        if not chords:
            chords = chord_search({"pitches": request.scale, "voice_count": 3, "max_results": 24})["chords"]
        progression = progression_search({"chords": chords, "length": min(8, request.duration_bars), "method": "contrast-resolution", "seed": request.seed})["progression"]
    chord_map = {str(chord["id"]): chord for chord in chords}
    total_beats = request.duration_bars * request.beats_per_bar
    chord_beats = request.beats_per_bar
    slots = max(1, total_beats // chord_beats)
    events: list[dict[str, Any]] = []
    sections = _composition_sections(
        request.duration_bars, request.form, request.beats_per_bar
    )
    scale_ratios = [parse_ratio(str(pitch["ratio"])) for pitch in request.scale]
    previous_melody = scale_ratios[0]
    for slot in range(slots):
        entry = progression[slot % len(progression)]
        chord = chord_map.get(str(entry.get("chord_id")))
        ratios = [parse_ratio(value) for value in (chord["ratios"] if chord else entry["ratios"])]
        start = slot * chord_beats
        section = next(item for item in sections if item["start_beat"] <= start < item["end_beat"])
        if random.random() <= request.chord_density or slot == 0:
            for voice, ratio in enumerate(ratios):
                events.append(_event("harmony", ratio, start + voice * 0.012, chord_beats * 0.88, 72 - voice * 3, section["role"], voice))
        bass = min(ratios, key=float) / 3
        events.append(_event("bass", bass, start, chord_beats * 0.82, 88, section["role"], 0))
        melody_steps = max(1, round(1 + request.melodic_density * 5))
        for step in range(melody_steps):
            onset = start + step * chord_beats / melody_steps
            candidates = ratios + scale_ratios
            candidates.sort(key=lambda ratio: abs(log2(float(ratio / previous_melody))))
            choice = candidates[min(len(candidates) - 1, random.randrange(min(4, len(candidates))))]
            previous_melody = choice
            if random.random() < request.melodic_density:
                events.append(_event("melody", choice * 3, onset, chord_beats / melody_steps * 0.64, 78 + random.randrange(-7, 8), section["role"], 0))
        for beat in range(chord_beats):
            position = start + beat
            if beat == 0 or random.random() < request.rhythmic_density:
                events.append(_drum_event("kick", 36, position, 92, section["role"]))
            if beat % 2 == 1:
                events.append(_drum_event("snare", 38, position, 86, section["role"]))
            if random.random() < request.rhythmic_density:
                events.append(_drum_event("hat", 42, position + 0.5, 62, section["role"]))
    if request.include_drone:
        events.append(_event("drone", parse_ratio(str(request.scale[0]["ratio"])) / 3, 0, total_beats, 48, "global", 0))
    events.sort(key=lambda item: (float(item["start_beat"]), str(item["part_role"])))
    metrics = _composition_metrics(events, progression, total_beats)
    return {
        "schema_version": "1.0",
        "equave": 3,
        "seed": request.seed,
        "metadata": {
            "tempo_bpm": request.tempo_bpm,
            "beats_per_bar": request.beats_per_bar,
            "duration_bars": request.duration_bars,
            "root_frequency_hz": request.root_frequency_hz,
            "form": request.form,
            "timbre": request.timbre,
        },
        "scale": request.scale,
        "sections": sections,
        "progression": progression,
        "events": events,
        "metrics": metrics,
    }


def _event(part: str, ratio: Fraction, start: float, duration: float, velocity: int, section: str, voice: int) -> dict[str, Any]:
    return {"part_role": part, "ratio": _ratio_text(ratio), "start_beat": round(start, 4), "duration_beats": round(duration, 4), "velocity": max(1, min(127, velocity)), "section_role": section, "voice": voice}


def _drum_event(part: str, note: int, start: float, velocity: int, section: str) -> dict[str, Any]:
    return {"part_role": part, "note": note, "start_beat": round(start, 4), "duration_beats": 0.12, "velocity": velocity, "section_role": section}


def _composition_sections(
    bars: int, form: str, beats_per_bar: int
) -> list[dict[str, Any]]:
    roles = {
        "loop": ("Center", "Expansion", "Return"),
        "AB": ("A", "B"),
        "ABA": ("A", "B", "A-return"),
        "verse-chorus": ("Verse", "Chorus", "Verse", "Final"),
        "tension-resolution": ("Center", "Departure", "Tension", "Resolution"),
    }[form]
    base, extra = divmod(bars, len(roles))
    result, cursor = [], 0
    for index, role in enumerate(roles):
        length = base + (1 if index < extra else 0)
        result.append({"id": f"bp-section-{index + 1}", "role": role, "start_bar": cursor, "bars": length, "start_beat": cursor * beats_per_bar, "end_beat": (cursor + length) * beats_per_bar})
        cursor += length
    return result


def _composition_metrics(events: list[dict[str, Any]], progression: list[dict[str, Any]], total_beats: int) -> dict[str, float]:
    tensions = [float(item.get("actual_tension", item.get("target_tension", 0.5))) for item in progression]
    target = [float(item.get("target_tension", 0.5)) for item in progression]
    match = 1 - fmean(abs(a - b) for a, b in zip(tensions, target, strict=True)) if tensions else 0
    pitched = [event for event in events if "ratio" in event]
    rhythmic = [event for event in events if "note" in event]
    return {
        "harmonic_coherence": round(1 - fmean(tensions) * 0.45 if tensions else 0.5, 4),
        "progression_directionality": round(max(tensions, default=0) - min(tensions, default=0), 4),
        "tension_curve_match": round(match, 4),
        "voice_leading_smoothness": round(1 - fmean(float(item.get("voice_leading", 0)) for item in progression), 4),
        "melodic_coherence": round(min(1, len([event for event in pitched if event["part_role"] == "melody"]) / max(1, total_beats)), 4),
        "rhythmic_coherence": round(min(1, len(rhythmic) / max(1, total_beats * 2)), 4),
        "spectral_compatibility": 0.82,
        "repetition_balance": round(min(1, len({tuple(item["ratios"]) for item in progression}) / max(1, len(progression)) * 1.8), 4),
        "novelty": round(min(1, len({event.get("ratio") for event in pitched}) / 13), 4),
        "loop_closure": round(1 - _progression_end_distance(progression), 4),
    }


def _progression_end_distance(progression: list[dict[str, Any]]) -> float:
    if len(progression) < 2:
        return 0.0
    first = {str(value) for value in progression[0]["ratios"]}
    last = {str(value) for value in progression[-1]["ratios"]}
    return 1 - len(first & last) / max(len(first), len(last), 1)


def export_midi(request: BPExportRequest | dict[str, Any]) -> bytes:
    if not isinstance(request, BPExportRequest):
        request = BPExportRequest.model_validate(request)
    roles = ("harmony", "bass", "melody", "drone")
    tracks = []
    for role in roles:
        notes = tuple(
            MidiNote(parse_ratio(str(event["ratio"])), float(event["start_beat"]), float(event["duration_beats"]), int(event["velocity"]))
            for event in request.events
            if event.get("part_role") == role and event.get("ratio")
        )
        if notes:
            tracks.append(MidiArrangementTrack(f"BP {role.title()}", notes=notes))
    drums = tuple(
        MidiDrumHit(int(event["note"]), float(event["start_beat"]), int(event["velocity"]))
        for event in request.events
        if event.get("note") is not None
    )
    if drums:
        tracks.append(MidiArrangementTrack("BP Rhythm", drums=drums))
    markers = [(round(float(section.get("start_beat", 0)) * 480), str(section.get("role", "Section"))) for section in request.sections]
    return arrangement_midi_bytes(tracks, request.tempo_bpm, request.beats_per_bar, base_frequency=request.root_frequency_hz, markers=markers, pitch_bend_range_semitones=request.pitch_bend_range_semitones)


def export_scala(pitches: list[dict[str, Any]], name: str = "Pure BP scale") -> str:
    ordered = sorted({parse_ratio(str(pitch["ratio"])) for pitch in pitches}, key=float)
    body = [f"{1200 * log2(float(value)):.6f}" for value in ordered if value != 1]
    body.append("3/1")
    return "\n".join((f"! {name.replace(' ', '_')}.scl", "!", name, str(len(body)), "!", *body, ""))


@dataclass(frozen=True)
class _AudioNote:
    frequency: float
    start: float
    duration: float
    velocity: int
    part: str


def render_audio(request: BPRenderRequest | dict[str, Any]) -> bytes:
    if not isinstance(request, BPRenderRequest):
        request = BPRenderRequest.model_validate(request)
    beat = 60 / request.tempo_bpm
    notes = [
        _AudioNote(request.root_frequency_hz * float(parse_ratio(str(event["ratio"]))), float(event["start_beat"]) * beat, float(event["duration_beats"]) * beat, int(event["velocity"]), str(event["part_role"]))
        for event in request.events
        if event.get("ratio")
    ]
    drum_events = [event for event in request.events if event.get("note") is not None]
    total = max([note.start + note.duration + 0.25 for note in notes] + [float(event["start_beat"]) * beat + 0.45 for event in drum_events] + [0.1])
    samples = [0.0] * (round(total * request.sample_rate) + 1)
    for note in notes:
        start = round(note.start * request.sample_rate)
        end = min(len(samples), round((note.start + note.duration + 0.18) * request.sample_rate))
        for index in range(start, end):
            elapsed = (index - start) / request.sample_rate
            envelope = min(1.0, elapsed / 0.015) * max(0.0, min(1.0, (note.duration + 0.18 - elapsed) / 0.18))
            samples[index] += _timbre_sample(request.timbre, note.frequency, elapsed) * envelope * note.velocity / 127 * 0.14
    for event in drum_events:
        start = round(float(event["start_beat"]) * beat * request.sample_rate)
        duration = 0.28 if int(event["note"]) == 36 else 0.16
        end = min(len(samples), start + round(duration * request.sample_rate))
        for index in range(start, end):
            elapsed = (index - start) / request.sample_rate
            envelope = exp(-elapsed / (duration / 4)) * int(event["velocity"]) / 127
            frequency = 70 - 28 * elapsed / duration if int(event["note"]) == 36 else 180
            samples[index] += sin(2 * pi * frequency * elapsed) * envelope * 0.18
    peak = max((abs(value) for value in samples), default=1.0)
    scale = min(1.0, 0.96 / peak)
    buffer = BytesIO()
    with wave_open(buffer, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(request.sample_rate)
        wav.writeframes(b"".join(pack("<h", round(max(-1, min(1, value * scale)) * 32767)) for value in samples))
    return buffer.getvalue()


def _timbre_sample(timbre: str, frequency: float, elapsed: float) -> float:
    phase = 2 * pi * frequency * elapsed
    if timbre == "sine":
        return sin(phase)
    if timbre == "soft-square":
        return sum(sin(phase * harmonic) / harmonic**1.5 for harmonic in ODD_HARMONICS[:5]) / 1.35
    if timbre == "hollow-pluck":
        return sum(sin(phase * harmonic) / harmonic**1.2 for harmonic in (1, 3, 7, 9)) / 1.5 * exp(-elapsed * 2.8)
    if timbre == "full-harmonic":
        return sum(sin(phase * harmonic) / harmonic**1.25 for harmonic in range(1, 10)) / 1.8
    return sum(sin(phase * harmonic) / harmonic**1.15 for harmonic in ODD_HARMONICS) / 1.75
