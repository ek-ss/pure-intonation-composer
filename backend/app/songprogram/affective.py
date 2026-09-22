"""Deterministic symbolic affect interpretation parallel to Native JI and PIL."""

from __future__ import annotations

import hashlib
from fractions import Fraction
from typing import Any, Mapping

from .compiler import _canonical, _mc, _rhe
from .perceptual import project_hash


class AffectiveError(ValueError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def _artifact_hash(value: Mapping[str, Any], member: str) -> str:
    body = {key: item for key, item in value.items() if key != member}
    prefix = (f"cps-artifact-hash/v1\0{value['schema']}\0{value['schema_version']}\0").encode()
    return "sha256:" + hashlib.sha256(prefix + _canonical(body)).hexdigest()


def affective_manifest_hash(manifest: Mapping[str, Any]) -> str:
    return _artifact_hash(manifest, "manifest_hash")


def affective_report_hash(report: Mapping[str, Any]) -> str:
    return _artifact_hash(report, "report_hash")


def _clamp(value: int, low: int, high: int) -> int:
    return min(high, max(low, value))


def _mean(values: list[int]) -> int:
    return _rhe(Fraction(sum(values), len(values))) if values else 0


def _phase_mc(ratio: Fraction) -> int:
    return _mc(ratio) % 1_200_000


def _triangular(phase: int, target: int, radius: int) -> int:
    distance = abs(phase - target)
    distance = min(distance, 1_200_000 - distance)
    return max(0, 10_000 - _rhe(Fraction(10_000 * distance, radius)))


def _event_ratio(event: Mapping[str, Any]) -> Fraction:
    try:
        ratio = Fraction(event["ratio"])
    except (KeyError, TypeError, ValueError, ZeroDivisionError):
        raise AffectiveError("AFFECTIVE_PROJECT_INVALID") from None
    if ratio <= 0 or event["ratio"] != f"{ratio.numerator}/{ratio.denominator}":
        raise AffectiveError("AFFECTIVE_PROJECT_INVALID")
    return ratio


def _metrics(events: list[Mapping[str, Any]], project: Mapping[str, Any], radius: int) -> dict[str, int | None]:
    notes = [event for event in events if event.get("kind") == "note"]
    if not notes:
        raise AffectiveError("AFFECTIVE_INSUFFICIENT_NOTES")
    tracks = {track["id"]: track for track in project["tracks"]}
    pitched = [event for event in notes if tracks[event["track_id"]]["role"] != "drums"]
    if not pitched:
        raise AffectiveError("AFFECTIVE_INSUFFICIENT_NOTES")

    grouped: dict[int, list[Fraction]] = {}
    for event in pitched:
        grouped.setdefault(event["start_tick"], []).append(_event_ratio(event))
    major_support: list[int] = []
    minor_support: list[int] = []
    tension: list[int] = []
    consonant = (0, 300_000, 400_000, 500_000, 700_000, 800_000, 900_000)
    for ratios in grouped.values():
        ordered = sorted(ratios)
        root = ordered[0]
        for ratio in ordered[1:]:
            phase = _phase_mc(ratio / root)
            major_support.append(_triangular(phase, 400_000, radius))
            minor_support.append(_triangular(phase, 300_000, radius))
        for left in range(len(ordered)):
            for right in range(left + 1, len(ordered)):
                phase = _phase_mc(ordered[right] / ordered[left])
                similarity = max(_triangular(phase, target, radius) for target in consonant)
                tension.append(10_000 - similarity)
    major_q = _mean(major_support)
    minor_q = _mean(minor_support)
    majorness_q = _clamp(major_q - minor_q, -10_000, 10_000)

    absolute_mc = [_mc(Fraction(project["lattice"]["base_frequency_millihz"], 440_000) * _event_ratio(event)) for event in pitched]
    register_q = _clamp(_rhe(Fraction(_mean(absolute_mc), 300)) - 5_000, -10_000, 10_000)
    ordered_notes = sorted(pitched, key=lambda event: (event["start_tick"], event["id"]))
    directions = []
    for left, right in zip(ordered_notes, ordered_notes[1:]):
        delta = _mc(_event_ratio(right) / _event_ratio(left))
        directions.append(10_000 if delta > 0 else -10_000 if delta < 0 else 0)
    direction_q = _mean(directions)
    valence_q = _clamp(_rhe(Fraction(6 * majorness_q + 2 * register_q + 2 * direction_q, 10)), -10_000, 10_000)

    clock = project["clock"]
    tempo_q = _clamp(_rhe(Fraction(clock["tempo_milli_bpm"] - 60_000, 12)), 0, 10_000)
    duration_beats = Fraction(max(event["start_tick"] + event["duration_ticks"] for event in notes), clock["ticks_per_beat"])
    onset_q = _clamp(_rhe(Fraction(len(notes) * 10_000, 8 * duration_beats)), 0, 10_000)
    velocity_q = _clamp(_rhe(Fraction(sum(event["velocity"] for event in notes) * 10_000, 127 * len(notes))), 0, 10_000)
    arousal_q = _rhe(Fraction(4 * tempo_q + 3 * onset_q + 3 * velocity_q, 10))
    return {
        "perceived_valence_q": valence_q,
        "arousal_q": arousal_q,
        "harmonic_majorness_q": majorness_q,
        "tonal_tension_q": _mean(tension),
        "timbral_brightness_q": None,
        "confidence_q": _clamp(2_000 + len(pitched) * 250, 0, 10_000),
    }


def evaluate_affective(project: Mapping[str, Any], manifest: Mapping[str, Any]) -> dict[str, Any]:
    required = {
        "schema", "schema_version", "algorithm", "implementation_build_id",
        "numeric_contract", "major_template_millicents", "minor_template_millicents",
        "template_radius_millicents", "valence_component_weights_q",
        "arousal_component_weights_q", "audio_feature_policy", "manifest_hash",
    }
    if (
        not isinstance(manifest, Mapping)
        or set(manifest) != required
        or manifest.get("schema") != "cps.affective-interpretation-manifest"
        or manifest.get("schema_version") != "1.0.0"
        or manifest.get("algorithm") != "symbolic-affect-five-axis/v1"
        or manifest.get("numeric_contract") != "cps-numeric/decimal-log2-rhe-v1"
        or manifest.get("major_template_millicents") != 400_000
        or manifest.get("minor_template_millicents") != 300_000
        or manifest.get("valence_component_weights_q") != {"majorness": 6000, "register": 2000, "pitch_direction": 2000}
        or manifest.get("arousal_component_weights_q") != {"tempo": 4000, "onset_rate": 3000, "velocity": 3000}
        or manifest.get("audio_feature_policy") != "not_evaluated_without_bound_pcm_extractor/v1"
        or manifest.get("manifest_hash") != affective_manifest_hash(manifest)
        or type(manifest.get("template_radius_millicents")) is not int
        or not 1 <= manifest["template_radius_millicents"] <= 200_000
    ):
        raise AffectiveError("AFFECTIVE_MANIFEST_INVALID")
    whole = _metrics(list(project.get("events", [])), project, manifest["template_radius_millicents"])
    ticks_per_bar = project["clock"]["ticks_per_beat"] * project["clock"]["beats_per_bar"]
    sections = []
    for section in project.get("form", []):
        start = section["start_bar"] * ticks_per_bar
        end = start + section["bars"] * ticks_per_bar
        selected = [event for event in project["events"] if start <= event["start_tick"] < end]
        if not any(event.get("kind") == "note" for event in selected):
            continue
        sections.append({"section_id": section["id"], "start_tick": start, "end_tick": end, "metrics": _metrics(selected, project, manifest["template_radius_millicents"])})
    report = {
        "schema": "cps.affective-interpretation-report", "schema_version": "1.0.0",
        "project_hash": project_hash(project), "manifest_hash": manifest["manifest_hash"],
        "implementation_build_id": manifest["implementation_build_id"], "status": "success",
        "whole_song": whole, "sections": sections,
        "audio_feature_status": "not_evaluated", "error": None, "report_hash": "",
    }
    report["report_hash"] = affective_report_hash(report)
    return report
