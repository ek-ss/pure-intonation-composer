"""Standard-library oracle for Native JI lattice coherence v1.

This module is conformance authority and does not import production code.
"""

from __future__ import annotations

import hashlib
import json
from fractions import Fraction
from pathlib import Path
from typing import Any, Mapping


SCHEMAS = Path(__file__).with_name("schemas")


def canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def artifact_hash(value: Mapping[str, Any], self_member: str) -> str:
    body = {key: item for key, item in value.items() if key != self_member}
    prefix = (f"cps-artifact-hash/v1\0{value['schema']}\0{value['schema_version']}\0").encode()
    return "sha256:" + hashlib.sha256(prefix + canonical(body)).hexdigest()


def raw_sha256(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def project_hash(project: Mapping[str, Any]) -> str:
    preimage = (
        project["compiler"]["build_id"].encode() + b"\0project/1.2.0\0" + canonical(dict(project))
    )
    return "sha256:" + hashlib.sha256(preimage).hexdigest()


def rhe(numerator: int, denominator: int) -> int:
    quotient, remainder = divmod(numerator, denominator)
    twice = remainder * 2
    if twice > denominator or (twice == denominator and quotient % 2):
        quotient += 1
    return quotient


def _ratio(text: str) -> Fraction:
    value = Fraction(text)
    if text != f"{value.numerator}/{value.denominator}" or value <= 0:
        raise ValueError("invalid canonical ratio")
    return value


def _coordinate(event: Mapping[str, Any], project: Mapping[str, Any]) -> tuple[int, ...]:
    provenance = event["pitch_provenance"]
    vector = provenance["final_vector"]
    generators = project["lattice"]["generators"]
    if len(vector) != len(generators) or any(type(value) is not int for value in vector):
        raise ValueError("invalid final vector")
    exponent = provenance["equave_exponent"]
    if type(exponent) is not int:
        raise ValueError("invalid equave exponent")
    represented = _ratio(project["lattice"]["equave"]) ** exponent
    for generator, power in zip(generators, vector, strict=True):
        represented *= _ratio(generator) ** power
    if represented != _ratio(event["ratio"]) or provenance["final_ratio"] != event["ratio"]:
        raise ValueError("ratio/coordinate mismatch")
    return (exponent, *vector)


def _mean(values: list[int]) -> int | None:
    return rhe(sum(values), len(values)) if values else None


def evaluate(project: Mapping[str, Any], manifest: Mapping[str, Any]) -> dict[str, Any]:
    if artifact_hash(manifest, "manifest_hash") != manifest["manifest_hash"]:
        raise ValueError("manifest hash mismatch")
    if manifest["project_schema_hash"] != raw_sha256(
        SCHEMAS / "arrangement_project_1_2.schema.json"
    ):
        raise ValueError("project schema mismatch")
    if manifest["report_schema_hash"] != raw_sha256(
        SCHEMAS / "native_ji_evaluation_report.schema.json"
    ):
        raise ValueError("report schema mismatch")
    if manifest["within_group_weight_q"] + manifest["between_group_weight_q"] <= 0:
        raise ValueError("zero total weight")

    groups: dict[int, list[tuple[str, tuple[int, ...]]]] = {}
    for event in project["events"]:
        if event["kind"] == "note":
            groups.setdefault(event["start_tick"], []).append(
                (event["id"], _coordinate(event, project))
            )
    ordered = [sorted(groups[tick]) for tick in sorted(groups)]
    cap = manifest["distance_cap"]

    def score(left: tuple[int, ...], right: tuple[int, ...]) -> int:
        distance = sum(abs(a - b) for a, b in zip(left, right, strict=True))
        return max(0, 10_000 - rhe(10_000 * distance, cap))

    within_scores = []
    for group in ordered:
        for left in range(len(group)):
            for right in range(left + 1, len(group)):
                within_scores.append(score(group[left][1], group[right][1]))
    within_q = _mean(within_scores)

    transition_scores = []
    for left, right in zip(ordered, ordered[1:]):
        directed = [max(score(a[1], b[1]) for b in right) for a in left]
        directed += [max(score(a[1], b[1]) for a in left) for b in right]
        transition_scores.append(rhe(sum(directed), len(directed)))
    between_q = _mean(transition_scores)

    weighted = []
    if within_q is not None:
        weighted.append((within_q, manifest["within_group_weight_q"]))
    if between_q is not None:
        weighted.append((between_q, manifest["between_group_weight_q"]))
    weighted = [(value, weight) for value, weight in weighted if weight]
    if not weighted:
        raise ValueError("NATIVE_JI_INSUFFICIENT_NOTES")
    value_q = rhe(sum(value * weight for value, weight in weighted), sum(w for _, w in weighted))
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
    report["report_hash"] = artifact_hash(report, "report_hash")
    return report
