"""Production Native JI lattice-coherence evaluation."""

from __future__ import annotations

import hashlib
from fractions import Fraction
from typing import Any, Mapping

from .compiler import _canonical, _rhe
from .perceptual import project_hash


class NativeJIError(ValueError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def _artifact_hash(value: Mapping[str, Any], member: str) -> str:
    body = {key: item for key, item in value.items() if key != member}
    prefix = (f"cps-artifact-hash/v1\0{value['schema']}\0{value['schema_version']}\0").encode()
    return "sha256:" + hashlib.sha256(prefix + _canonical(body)).hexdigest()


def native_ji_manifest_hash(manifest: Mapping[str, Any]) -> str:
    return _artifact_hash(manifest, "manifest_hash")


def native_ji_report_hash(report: Mapping[str, Any]) -> str:
    return _artifact_hash(report, "report_hash")


def _ratio(text: Any) -> Fraction:
    try:
        value = Fraction(text)
    except (TypeError, ValueError, ZeroDivisionError):
        raise NativeJIError("NATIVE_JI_PROJECT_INVALID") from None
    if not isinstance(text, str) or text != f"{value.numerator}/{value.denominator}" or value <= 0:
        raise NativeJIError("NATIVE_JI_PROJECT_INVALID")
    return value


def _coordinate(event: Mapping[str, Any], project: Mapping[str, Any]) -> tuple[int, ...]:
    try:
        provenance = event["pitch_provenance"]
        vector = provenance["final_vector"]
        generators = project["lattice"]["generators"]
        exponent = provenance["equave_exponent"]
        if (
            not isinstance(vector, list)
            or len(vector) != len(generators)
            or any(type(value) is not int for value in vector)
            or type(exponent) is not int
        ):
            raise KeyError
        represented = _ratio(project["lattice"]["equave"]) ** exponent
        for generator, power in zip(generators, vector, strict=True):
            represented *= _ratio(generator) ** power
        if represented != _ratio(event["ratio"]) or provenance["final_ratio"] != event["ratio"]:
            raise KeyError
    except (KeyError, TypeError):
        raise NativeJIError("NATIVE_JI_PROJECT_INVALID") from None
    return (exponent, *vector)


def evaluate_native_ji(project: Mapping[str, Any], manifest: Mapping[str, Any]) -> dict[str, Any]:
    required = {
        "schema",
        "schema_version",
        "algorithm",
        "implementation_build_id",
        "project_schema_hash",
        "report_schema_hash",
        "metric_id",
        "coordinate_order",
        "distance",
        "distance_cap",
        "within_group_weight_q",
        "between_group_weight_q",
        "manifest_hash",
    }
    if (
        not isinstance(manifest, Mapping)
        or set(manifest) != required
        or manifest.get("schema") != "cps.native-ji-evaluation-manifest"
        or manifest.get("schema_version") != "1.0.0"
        or manifest.get("algorithm") != "native-ji-lattice-coherence/v1"
        or manifest.get("metric_id") != "native_ji.coherence"
        or manifest.get("coordinate_order") != ["equave_exponent", "final_vector"]
        or manifest.get("distance") != "lattice-l1/v1"
        or manifest.get("manifest_hash") != native_ji_manifest_hash(manifest)
    ):
        raise NativeJIError("NATIVE_JI_MANIFEST_INVALID")
    cap = manifest["distance_cap"]
    within_weight = manifest["within_group_weight_q"]
    between_weight = manifest["between_group_weight_q"]
    if (
        type(cap) is not int
        or cap < 1
        or any(
            type(value) is not int or not 0 <= value <= 10_000
            for value in (within_weight, between_weight)
        )
        or within_weight + between_weight == 0
    ):
        raise NativeJIError("NATIVE_JI_MANIFEST_INVALID")

    groups: dict[int, list[tuple[str, tuple[int, ...]]]] = {}
    try:
        for event in project["events"]:
            if event["kind"] == "note":
                groups.setdefault(event["start_tick"], []).append(
                    (event["id"], _coordinate(event, project))
                )
    except (KeyError, TypeError):
        raise NativeJIError("NATIVE_JI_PROJECT_INVALID") from None
    ordered = [sorted(groups[tick]) for tick in sorted(groups)]

    def score(left: tuple[int, ...], right: tuple[int, ...]) -> int:
        distance = sum(abs(a - b) for a, b in zip(left, right, strict=True))
        return max(0, 10_000 - _rhe(Fraction(10_000 * distance, cap)))

    within_scores = [
        score(group[left][1], group[right][1])
        for group in ordered
        for left in range(len(group))
        for right in range(left + 1, len(group))
    ]
    transition_scores = []
    for left, right in zip(ordered, ordered[1:]):
        directed = [max(score(a[1], b[1]) for b in right) for a in left]
        directed += [max(score(a[1], b[1]) for a in left) for b in right]
        transition_scores.append(_rhe(Fraction(sum(directed), len(directed))))
    within_q = _rhe(Fraction(sum(within_scores), len(within_scores))) if within_scores else None
    between_q = (
        _rhe(Fraction(sum(transition_scores), len(transition_scores)))
        if transition_scores
        else None
    )
    weighted = [
        (value, weight)
        for value, weight in ((within_q, within_weight), (between_q, between_weight))
        if value is not None and weight > 0
    ]
    if not weighted:
        raise NativeJIError("NATIVE_JI_INSUFFICIENT_NOTES")
    value_q = _rhe(
        Fraction(
            sum(value * weight for value, weight in weighted),
            sum(weight for _, weight in weighted),
        )
    )
    report = {
        "schema": "cps.native-ji-evaluation-report",
        "schema_version": "1.0.0",
        "project_hash": project_hash(project),
        "manifest_hash": manifest["manifest_hash"],
        "implementation_build_id": manifest["implementation_build_id"],
        "status": "success",
        "metrics": [
            {
                "metric_id": "native_ji.coherence",
                "direction": "maximize",
                "value_q": value_q,
                "within_q": within_q,
                "between_q": between_q,
            }
        ],
        "error": None,
        "report_hash": "",
    }
    report["report_hash"] = native_ji_report_hash(report)
    return report
